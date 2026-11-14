# Independent check: 3D globe tiles and custom-coordinate terrain tiles vs the original NASA LOLA DEMs

Checker: Soyun Jeong. Producer of both products: Sua Kim. Requested by the team lead on 2026-11-14. Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
Data: main `8eff7ac` (web version 28). Nothing in `web/data/`, `data/raw/` or the production code is changed.
Run: `python pipeline/verify_terrain_tiles.py` (about 30 s; needs internet) → `docs/terrain_tiles_verification.json`. Ledger entries: `docs/verification_ledger.md` C1, C2.

## Result
| Product | Samples | Max \|Δ\| | Mean \|Δ\| | Tolerance | Result |
|---|---|---|---|---|---|
| (5) 3D globe tiles `web/data/globe/` | 10 (3 band, 3 north cap, 4 south z7) | **0.218 m** | 0.088 m | 0.26 m | **PASS 10/10** |
| (6) custom-coordinate tiles `web/data/hterrain/` + `polar_s/` | 10 (4 near, 3 far, 3 polar) | **0.373 m** | 0.170 m | 0.51 m global; q/2 polar | **PASS 10/10** |

Per-sample tables (tile, lat/lon, original and tile height, |Δ|) are in the ledger entries and in the JSON.

## Independence
`pipeline/verify_terrain_tiles.py` imports no production module (`build_globe_tiles`, `build_site_hr_tiles`, `build_custom_terrain`, `build_polar_terrain`, `fetch_*`, `hterrain.js`). Everything is written from the formats documented in the products' `index.json`, `docs/globe3d.md` and the PDS / GeoTIFF metadata:
- tile decoders;
- vertex and node coordinates;
- block means;
- bilinear interpolation;
- the LDEM reader (label parsed again);
- the stereographic projection (pyproj from the CRS string in the index and the GeoTIFF).

## Originals and their integrity
| Original | Where read | Integrity / registration |
|---|---|---|
| LOLA LDEM_64 float V3.1 (64 ppd) | `data/raw/global/ldem_64_float.img` | Size = PDS Content-Length 1,061,683,200 B. **All 64 byte ranges used were re-fetched from PDS by HTTP Range: identical.** Label: PC_REAL 32-bit, km, OFFSET 1737.4, CENTER_LONGITUDE 180, LINE/SAMPLE_PROJECTION_OFFSET 5759.5 / 11519.5 → pixel centres lat = 90 − (r+0.5)/64, lon = (c+0.5)/64 (0–360 E); no MISSING_CONSTANT; frame "MEAN EARTH/POLAR AXIS OF DE421" |
| LOLA LDEM_16 float V3.1 (16 ppd) | `data/raw/global/ldem_16_float.img` | Size = PDS 66,355,200 B; 3 ranges re-fetched: identical; same label conventions |
| PGDA `LDEM_80S_20MPP_ADJ.TIF` | https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/ over HTTP (rasterio `/vsicurl/`), no local cache | 30,400², float32, NaN no-data, transform (20, −304000, 304000), AREA_OR_POINT = Area, `+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400`; Content-Length 2,696,082,051, Last-Modified 2023-07-07 |
| PGDA `LDEM_60S_60MPP_ADJ.TIF` | same | 31,040², transform (60, −931200, 931200), Area; 3,089,110,093 B |
| PGDA `LDEM_60S_240MPP_ADJ.TIF` | same | 7,760², transform (240, −931200, 931200), Area; 218,961,039 B |

Height reference: at the 4 south z7 points PGDA 20 m and LDEM_64 differ by 0.2–21 m (resolution only), so both are metres above the 1737.4 km sphere. No no-data pixel was met.

## Decoding and expected values
**(5) Globe PNG.**
- Decoding: h = (R·256 + G)/2 − 10000 m. The tile is 259 × 259 px with a 1-sample border, so pixel (i, j) = vertex (i−1, j−1).
- Band vertex: lon = −180 + (x·256 + k)·d, lat = 72 − (y·256 + k)·d, with d = 72°/2^z/256.
- Cap vertex: px = −560 km + (x·256 + k)·d, py = 560 km − (y·256 + k)·d (`index.json` → `band`, `cap`).
- Expected value, following `docs/globe3d.md` §2 / the build docstring: "LDEM_64 box-filtered for coarse levels", "finest source first".
  - LDEM levels: bilinear between the pixel centres of the coarsest k × k block mean of LDEM_64 whose pixel is ≤ 1.01 × the tile spacing (band z1 → 8 ppd, z2 → 16, z3 → 32; north z0 → 8, z1 → 16, z2 → 32). Rows are clamped at the poles; columns wrap.
  - South z7 (34.2 m): bilinear on PGDA 20 m at the vertex's projected coordinates.
- Selection (seed 20261115): random tiles that exist in `index.json`, random vertex.
  - South z7 tiles flagged `fine` near a south-polar site (lat ≤ −83°), vertex ≤ 9 km from the site, so it lies inside the 15 km 20 m windows.
  - South z8 is excluded because the checker made it (card 14).
- Tolerance 0.26 m: 0.25 m from the 0.5 m step, plus 0.01 m for float32 values and floating-point bilinear.
- Without the rule, the nearest-pixel or native-64-ppd value differs from the tile by up to 12.3 m (band z3). That is the averaging, not an error, so it would be a false FAIL.

**(6) Custom-coordinate tiles.**
- Global grids: gzip of n × n int16 LE, each row delta-coded (cumulative sum along rows).
  - Tile (ty, tx) local (i, j) = global node (min(ty·480 + i, last row), (tx·480 + j) mod columns).
  - Node centre: lat = 90 − (r+0.5)/ppd, lon = −180 + (c+0.5)/ppd.
  - Expected: near = mean of LDEM_64 rows 2r, 2r+1 and file columns 2c + 11520, +1 (mod 23040); far = LDEM_16 row r, column c + 2880 (mod 5760).
  - Tolerance 0.51 m (heights are rounded to 1 m), and the decoded value must equal round(expected).
  - The wrap case (`near/1_23`, last column) also equals the same node in tile `1_0` column 0. The clamp case (`far/5_4`, last row) is the last global row (−89.969°).
- Polar levels: gzip of int32 LE base + n × n int16 LE residuals. Heights = base + 2-D cumulative sum (inverse of the planar predictor), × q_m.
  - Level pixel (R, C) is at x = x0_m + C·res, y = y0_m − R·res. That lands exactly on an original pixel centre (checked, fraction < 10⁻⁶), and the expected value is that pixel.
  - Tolerance q/2 + 0.001 m (p20, p60: 0.126 m; p240: 0.251 m). Every value equals round(original/q)·q.

## Not covered
- The band fine levels z4–z7 (SLDEM2015 59 m windows, Chandrayaan-3 PGDA 60 m): SLDEM2015 was not read.
- The south z3–z6 fine levels: block means of the PGDA 20/60/80 m site windows, whose window origins (block phase) are not recorded in the repository.
- The albedo texture.
- These are samples (10 per product), not every tile.
- A PASS shows that the tiles encode the stated NASA DEMs as documented; it says nothing about the DEMs' own accuracy.
