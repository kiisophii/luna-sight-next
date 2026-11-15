# Task E — independent check of `web/data/local250/` (16 south-polar 250 m grids)

Producer: Jiyong Sung (PR #61). Checker: Soyun Jeong. Work by Claude Code; the human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
Data: main `89a9af1` (web version 34). No file in `web/data/`, `data/raw/` or the production code is changed.
Script: `pipeline/verify_local250_independent.py` (parts `shared`, `dem`, `full`, `rereader`, `report`; `tables` prints the tables below) → `docs/local250_independent_check.json`.
Ledger entry: `docs/verification_ledger.md`, row E1.

## Result

| Check | Scope | Max \|Δ\| fractions | Max \|Δ\| longest darkness | Criterion | Result |
|---|---|---|---|---|---|
| 1. 250 m vs 1 km grid at identical offsets | 16 sites × 121 = **1,936 nodes** | **0 pp** (0 mismatching nodes) | 0 h | (consistency, no tolerance needed) | identical |
| 2. Brute force from the DEMs, 5 random new nodes | 5 sites, 5 nodes not on the 1 km grid | **0 pp** | 0 h | ≤ 1 pp | **PASS 5/5** |
| 3. Full independent recomputation | **26,896 / 26,896 nodes** (16 × 1,681) | **0 pp** (max and median) | 0 h | ≤ 1 pp | **PASS 26,896 / 0 FAIL** |

In part 3 all four metrics are exactly equal at every node. h0 is equal to its 0.01 m storage at every node, and the ground resolution is equal at every node. The stored source names are a subset of the sources our full march used at every node.

**Sensitivity to the stored rounding.** The production metrics use masks rounded to 0.0001° and h0 rounded to 0.01 m (contract §15). Our primary result applies the same rounding. With our unrounded masks instead:
- 2,412 of 26,896 nodes change by 1–2 hours out of 43,824, at most **0.004564 pp**;
- the longest darkness changes at 24 nodes, by at most 4 h.

This is the documented storage quantization, not a disagreement. It is far inside the 1 pp criterion.

## Independence

- The script imports and runs nothing of the producer's code: `local250.py`, `local250_gpu.*`, `local_maps.py`, `horizon.py`, `fetch_polar.py`, `polar_prefetch.py`, `verify_card18_local.py`, `local_metrics.mjs` / `core.js`.
- It does not use the producer's DEM windows (`data/processed/local250/`, `card18` caches), nor his saved horizons or checkpoints.
- The definitions were taken from `docs/data_contract.md` §0, 3, 6, 15, 22 and `docs/local250.md`. For the exact sampling details, the producer's source code was **read but not run**:
  - the finest-first chain with NaN fall-through;
  - bilinear interpolation between pixel centres;
  - storage rounding;
  - h0 from the chain at the node.
- All of the following is new code written for this check:
  - the DEM readers;
  - the projection;
  - the bilinear interpolation;
  - the ray march;
  - the hour-by-hour loop.
- Two separate implementations were used:
  - **Part 2 (brute force):**
    - DEM windows were read again around each of the 5 nodes;
    - the stereographic projection used pyproj (PROJ, from the GeoTIFF CRS);
    - bilinear interpolation in numpy;
    - every one of the 720 × 8,001 samples, with no early stop;
    - the metrics came from a literal, scalar, hour-by-hour port of the `core.js` statements.
  - **Part 3 (all nodes):**
    - per-site windows;
    - a numba kernel using the closed-form spherical stereographic `x = 2R·py/(1−pz)`, `y = 2R·px/(1−pz)` (equal to PROJ within 3.5 × 10⁻¹⁰ m at 1,000 random points);
    - again all 720 × 8,001 samples per node, no early stop;
    - a vectorised version of the same hourly rules (equal to the literal loop in the tests).
  - At the 5 part-2 nodes, the part-3 masks equal the part-2 masks within 5.0 × 10⁻⁷°, which is the 6-decimal storage of part 2. h0 agrees within 2 × 10⁻¹¹ m.
- Node coordinates were recomputed from (e, n), using the great circle with bearing atan2(e, n) and length hypot(e, n). They agree with the stored lat/lon within 2.8 × 10⁻¹⁴°.
- The 5 nodes (seed 2026111505) are:
  - ARTEMIS_NOBILE_RIM2 1565
  - ARTEMIS_MOUTON 846
  - SHACKLETON_RIM 363
  - SHOEMAKER_RIM_A 1252
  - DE_GERLACHE_RIM1 1060

  Each is at a different site. None is on the 1 km grid, and none is one of the producer's 5 nodes in `docs/local250.md`.

## Originals and their integrity

| Original | How read | Record |
|---|---|---|
| PGDA `LOLA_5mpp/87S/ldem_87s_5mpp.tif` | HTTP Range from https://pgda.gsfc.nasa.gov/data/ | Content-Length 3,465,285,714 B, Last-Modified 2021-10-14; 40,000², 5 m, deflate + predictor 3, pixel-is-area, `+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400` |
| PGDA `LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF` | same | 5,116,709,568 B, 2023-07-07; 43,280², 10 m |
| PGDA `LDEM_80S_20MPP_ADJ.TIF` | same | 2,696,082,051 B; 30,400², 20 m |
| PGDA `LDEM_60S_60MPP_ADJ.TIF` | same | 3,089,110,093 B; 31,040², 60 m |
| PGDA `LDEM_80S_80MPP_ADJ.TIF` | same | 189,158,392 B; 7,600², 80 m |
| PGDA `LDEM_60S_240MPP_ADJ.TIF` | same | 218,961,039 B; 7,760², 240 m |
| LOLA LDEM_64 / LDEM_16 float V3.1 | `data/raw/global/` | SHA-256 `4dd151f2…` / `c6b790f1…`, the same hashes the producer's provenance lists; label checks: PC_REAL 32-bit, km above 1737.4 km, pixel centres, no missing constant |
| Ephemeris | `web/data/ephem.bin` | shared production input (43,824 hourly rows; not produced by the producer of `local250/`); SHA-256 in the JSON |

**DEM gates** (contract §15, measured from each node):
- 5 m to 3 km;
- 10 m and 20 m to 25 km;
- 60 m and 80 m to 60 km;
- 240 m to 200 km;
- then LDEM_64, then LDEM_16, to 300 km.

**Source coverage.**
- The 5 m mosaic does not cover 8 sites, and the 10 m mosaic does not cover IM1. They fall through to the next source, as in production.
- Windows were cut with a margin of (7.08 km + gate) × 1.01. That way every sample within the gate of any node is inside the window, and samples beyond the gate are not used.

**DEM reading** (all from the NASA server, no local PGDA cache).
- **First 9 sites** (IM1, IM2, ARTEMIS_CABEUS_B, ARTEMIS_HAWORTH, ARTEMIS_MALAPERT, ARTEMIS_MOUTON_PLATEAU, ARTEMIS_MOUTON, ARTEMIS_NOBILE_RIM1, ARTEMIS_NOBILE_RIM2) and the first part-2 run: windows read with GDAL `/vsicurl/`.
- **The GDAL failure.** With the cache options first used, GDAL failed repeatedly on one 5 m tile (42, 71), although the tile's bytes inflate correctly.
- **The fix.** GDAL was replaced by our own reader:
  - tifffile parses the IFD over HTTP Range;
  - zlib inflates each tile;
  - our own code undoes TIFF predictor 3.
- **Checks of the new reader.**
  - It returns bit-identical tiles to GDAL on 4 readable tiles.
  - The `rereader` part read all 45 windows cached by the GDAL reader again with the new reader. **All 45 are identical**: same bounds, same origin, every pixel equal (`gdal_windows_reread` in the JSON). Re-running the script from scratch with the new reader therefore gives the same inputs.
  - The 5-node brute force was run again with the new reader and gave identical metrics and masks (`dem_gdal_reader` in the JSON).

## Shared nodes (250 m vs 1 km)

Both grids' (e, n) offsets were matched exactly; nearest neighbours were not used. The two files' lat/lon at these nodes differ by 0.0° and h0 is equal.

| Site | Shared nodes | Median \|Δ\| (pp) | Max \|Δ\| (pp) | Max darkness Δ (h) | Mismatching nodes |
|---|---:|---:|---:|---:|---:|
| IM1 | 121 | 0.000000 | 0.000000 | 0 | 0 |
| IM2 | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_CABEUS_B | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_HAWORTH | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_MALAPERT | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_MOUTON_PLATEAU | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_MOUTON | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_NOBILE_RIM1 | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_NOBILE_RIM2 | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_DE_GERLACHE_RIM2 | 121 | 0.000000 | 0.000000 | 0 | 0 |
| ARTEMIS_SLATER_PLAIN | 121 | 0.000000 | 0.000000 | 0 | 0 |
| SHACKLETON_RIM | 121 | 0.000000 | 0.000000 | 0 | 0 |
| CONNECTING_RIDGE | 121 | 0.000000 | 0.000000 | 0 | 0 |
| PEAK_NEAR_SHACKLETON | 121 | 0.000000 | 0.000000 | 0 | 0 |
| DE_GERLACHE_RIM1 | 121 | 0.000000 | 0.000000 | 0 | 0 |
| SHOEMAKER_RIM_A | 121 | 0.000000 | 0.000000 | 0 | 0 |
| **Total** | **1,936** | 0 | 0 | 0 | **0** |

Medians and maxima are over the three fractions (sun, earth, both). Both grids were computed with the same card-18 definitions and DEM chain, so exact equality is expected. It shows that the two products are consistent; on its own it is not an independent check. Parts 2 and 3 are the independent checks.

## Five random nodes, brute force from the DEMs

| Site | Node (row, col) | e, n (m) | Lat, lon | Stored sun / earth / both / dark | Recomputed | \|Δ\| (pp, pp, pp, h) | Unrounded-mask \|Δ\| | Result |
|---|---|---|---|---|---|---|---|---|
| ARTEMIS_NOBILE_RIM2 | 1565 (38, 7) | -3250, 4500 | -83.904661, 55.471579 | 0.377487 / 0.477181 / 0.190489 / 504 | 0.377487 / 0.477181 / 0.190489 / 504 | 0, 0, 0, 0 | 0, 0, 0, 0 | PASS |
| ARTEMIS_MOUTON | 846 (20, 26) | 1500, 0 | -85.415734, 32.469926 | 0.475105 / 0.541370 / 0.261501 / 401 | 0.475105 / 0.541370 / 0.261501 / 401 | 0, 0, 0, 0 | 0, 0, 0, 0 | PASS |
| SHACKLETON_RIM | 363 (8, 35) | 3750, -3000 | -89.752433, -132.840990 | 0.201876 / 0.507644 / 0.119889 / 674 | 0.201876 / 0.507644 / 0.119889 / 674 | 0, 0, 0, 0 | 0, 0, 0, 0 | PASS |
| SHOEMAKER_RIM_A | 1252 (30, 22) | 500, 2500 | -87.996687, 12.360354 | 0.151561 / 0.425703 / 0.093830 / 2828 | 0.151561 / 0.425703 / 0.093830 / 2828 | 0, 0, 0, 0 | 0, 0, 0, 0 | PASS |
| DE_GERLACHE_RIM1 | 1060 (25, 35) | 3750, 1250 | -88.636559, -62.727609 | 0.321103 / 0.541484 / 0.208813 / 629 | 0.321103 / 0.541484 / 0.208813 / 629 | 0, 0, 0, 0 | 0.002282, 0, 0.002282, 0 | PASS |

Additional details for these nodes:
- h0 (m) recomputed / stored: 928.88 / 928.88, 6365.21 / 6365.21, 1003.32 / 1003.32, −807.29 / −807.29, 900.50 / 900.5.
- Ground resolution: 10, 10, 5, 5 and 5 m, all equal to the stored value.
- At DE_GERLACHE_RIM1, the unrounded mask flips one hour out of 43,824 (0.002282 pp). This is the same storage effect the producer reported at a different node.

## All 26,896 nodes

| Site | Nodes recomputed | PASS / FAIL | All 4 exact | Median \|Δ\| (pp) | Max \|Δ\| (pp) | Max \|Δ\| unrounded mask (pp) | Max darkness Δ (h) | h0 max Δ (m) | Ground res. equal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IM1 | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| IM2 | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_CABEUS_B | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_HAWORTH | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_MALAPERT | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_MOUTON_PLATEAU | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_MOUTON | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_NOBILE_RIM1 | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_NOBILE_RIM2 | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.002282 | 0 | 0.00 | 1681 |
| ARTEMIS_DE_GERLACHE_RIM2 | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| ARTEMIS_SLATER_PLAIN | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| SHACKLETON_RIM | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| CONNECTING_RIDGE | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| PEAK_NEAR_SHACKLETON | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| DE_GERLACHE_RIM1 | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| SHOEMAKER_RIM_A | 1681 | 1681 / 0 | 1681 | 0.000000 | 0.000000 | 0.004564 | 0 | 0.00 | 1681 |
| **Total** | **26,896** | **26,896 / 0** | **26,896** | 0 | **0** | 0.004564 | **0** | 0.00 | 26,896 |

Runtime on the checker's laptop (Intel Core Ultra 7 155H, 12 numba threads, no GPU):
- DEM windows over HTTP: 5,128 s;
- horizons: 2,435 s (about 150 s per site, 0.09 s per node);
- metrics: 385 s.

One checkpoint file per finished site makes the run resumable. The run was interrupted once, by the GDAL tile failure above, and resumed with the 9 finished sites kept.

## Limits

- Same inputs: the check uses the same NASA DEM files, the same gates and the same `ephem.bin` as production. It therefore confirms that the published numbers follow from those inputs as documented. It does not test:
  - the DEMs against the real surface;
  - the ephemeris (already checked against JPL Horizons, ledger row 2);
  - mission suitability.
- The masks themselves are not published, so masks could not be compared directly; the comparison is of the four metrics, h0, ground resolution and the source lists.
  - Production stops marching an azimuth early once no higher terrain is possible. Its source `to_km` can therefore be shorter than ours, because we march all 8,001 samples. For that reason we compare source names as a subset, not their distances.
- The part-1 equality is a consistency check between two products of the same pipeline (see above).
- The definitions' fine details came from reading the producer's code (not running it). If a definition in that code were itself wrong, this check would reproduce it.
