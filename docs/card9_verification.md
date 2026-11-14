# Card 9 — independent verification (2026-11-14 KST)

Run by Claude Code for Soyun Jeong. **Not yet checked by a human.** Code: `pipeline/verify_card9.py`.
It does not import `horizon.py` or `global_maps.py`; it reads terrain with its own code or with card 3's `fetch_global.py`.
Numbers: `docs/card9_verification.json`. Per-point values: `data/processed/verify_card9_pgda_points.jsonl` (git-ignored).
No card 9 output was overwritten, and the global map was not recomputed.

## 1. PGDA comparison (card 9 check in `docs/2단계_분배.md`)

### Truth: `AVGVISIB_75S_120M_201608.TIF` (+ `_EARTH`)
- Source: https://pgda.gsfc.nasa.gov/products/69 (Mazarico et al. 2011, Icarus 211, 1066–1081), downloaded from https://pgda.gsfc.nasa.gov/data/MoonIllumination/.
- Grid: 7624 × 7624 int16, value = DN × 4e-5, no-data −32768.
- Projection: polar stereographic, `+R=1737400`, 120 m/px, pixel-is-area, corner ±457.44 km. This is the same projection formula as ours (checked by reading the GeoTIFF tie point and pixel scale).
- Definition (product page): solar illumination of the **finite disc**, and Earth "visible if **any part** of its disc is not obscured".
- Period: averaged over **hourly** steps spanning **18.6 years**. The exact start and end dates are **not stated**. The GeoTIFF `START_TIME/STOP_TIME` (2009-07-13 … 2013-07-18) are LOLA data times, not the illumination window.
- Observer height and terrain resolution used by PGDA: not stated (unverified).

### Our side
- Ephemeris: **one full 18.6-year nodal cycle**, 2020-01-01 … 2038-07-31T22Z every 2 h (81,444 steps).
  - Regenerated with card 1's `ephem.generate()`. The production `ephem.bin` was not touched.
  - 21,912 overlapping rows are bit-identical to `web/data/ephem.bin`, the same check card 10 reported for its file.
  - The npz file hash differs from card 10's (`358526e0…`) because npz is a zip archive.
- Terrain: the same DEMs as the 3.8 km map (LDEM_64 to 150 km, LDEM_16 to 300 km).
  - 720 azimuths, 200 m steps to 150 km and 500 m to 300 km, no early stop, observer 2 m, exact curvature.
- Points: 400 random points, uniform by area, 75–85° S, seed 42 (the same points as `global_maps.py validate --n 400`).

### Results (n = 400 valid points, 0 missing DEM samples)
| Ours | vs PGDA | MAE (pp) | RMSE (pp) | bias (pp) | r | ours inside PGDA 3×3 (±120 m) range |
|---|---|---|---|---|---|---|
| **sun_mean** (map definition, mean disc fraction) | sun | **2.119** | **4.407** | +0.706 | **0.9399** | 54.0 % |
| sun_any (any part of the disc) | sun | 2.300 | 4.794 | +1.590 | 0.9349 | 49.2 % |
| **earth_any** (= PGDA definition) | earth | **1.733** | 5.357 | +0.850 | **0.9891** | 80.8 % |
| earth_ctr (map definition, stricter by design) | earth | 3.249 | 6.061 | −2.142 | 0.9875 | 63.2 % |

The map engine itself (`global_maps.py validate --n 400`, same points and ephemeris) gives Sun MAE 2.185 pp, RMSE 4.539, r 0.9379. Earth (centre) gives MAE 3.137 pp.
The independent and engine Sun values agree to MAE 0.37 pp, r 0.998. Most of the 5.4 pp maximum gap comes from the different azimuth count (720 vs 360) and step sizes.
PGDA values read with tifffile and with rasterio are identical (max difference 4e-5, the JSON rounding).

### Where the errors come from
- The error grows with the local PGDA spread: correlation 0.62 between |ours − PGDA| and the 3×3 PGDA range.
- 44 points have |Δ| > 5 pp; 22 of them have a PGDA 3×3 range wider than 10 pp.
- The 10 largest errors are all on crater walls or floors (mask max 6–19°), where PGDA changes by up to 30–47 pp within ±120 m. Our near-field terrain is 474 m (LDEM_64) versus PGDA's finer terrain.
- Without the 7 permanently shadowed points that are 0 in both: n 393, MAE 2.16 pp, RMSE 4.45 pp, r 0.931.
- By band: 80–85° S MAE 2.42 pp (bias +1.20); 75–80° S MAE 1.94 pp (bias +0.41).
- There is no pass/fail threshold for card 9 in the team documents. For reference, card 11 (85–90° S, 60 m terrain) got MAE 1.66 pp and r 0.985.

### Period and cell effects (why the stored 2026–2030 map is not compared directly)
- At the same 400 exact points, the engine with 2026–2030 minus the engine with 18.6 years: MAE **0.09 pp** (max 0.4 pp). In this band the period matters little.
- The stored map holds **one value per 3.8 km cell, computed at the cell centre**. Cell value minus the exact point inside it (same period): MAE **3.17 pp**, max **30.7 pp**.
- So read the 3.8 km map as "value at the cell centre", not as the cell average or as a value valid for any point in the cell.

## 2. Site horizons recomputed by brute force

### Method
- Terrain read directly from the SLDEM2015 window (own bilinear) and LDEM_64/16 (`fetch_global.LdemFile`).
- Terrain points by Rodrigues rotation; elevation of the observer→point vector above the observer's tangent plane.
- Uniform 20 m steps to 150 km and 100 m to 300 km, no early stop.

### 20 azimuths per site (k = 7 + 36 j)
| Site | Max \|Δ\| (deg) | Mean \|Δ\| | h0 file vs DEM | Note |
|---|---|---|---|---|
| APOLLO17 | **0.0019** | 0.0004 | −2627.99 / −2627.99 m | — |
| CHANDRAYAAN3 (LDEM_64 only) | **0.0079** | 0.0007 | 528.91 / 528.91 m | — |
| CHANGE4 (window crosses 180°) | 0.8908 | 0.0966 | −5928.44 / −5928.44 m | **0.0148** when the brute force also starts at 0.2 km (see below) |

- **Curvature applied**: a flat-ground model would raise the masks by up to 0.46° (APOLLO17), 1.33° (CHANDRAYAAN3) and 1.60° (CHANGE4). The stored masks match the spherical computation.
- **Observer 2 m applied**: removing it changes the brute-force masks by up to 0.018° / 0.23° / 1.51°. The stored masks match the 2 m version.
- **Coordinates**: file lat/lon are identical to `sites.json`, and `h0_m` equals the DEM height at the site.

### All 720 azimuths, all 17 sites
Brute force with the **same 0.2 km start** as the engine:
- max |Δ| 0.012–0.219°, RMS ≤ 0.026°.
- The largest case (CHANGE5, 0.219°) is the brute force's own 20 m step. With 1 m steps it drops to max 0.016°, RMS 0.0015°.
- The engine is therefore correct within ~0.02°.

## 3. Finding: near-field cut-off at 0.2 km (design limit, not changed)
- `run_horizons.py` marches from `--min-km 0.2` (engine default, Sua). Terrain 20–200 m from the site is ignored.
- At 13 of the 17 sites, the 59 m SLDEM surface rises above the far horizon within 200 m in some directions.
  - Starting the brute force at 20 m raises those azimuths by up to 2.8° (CHANGE3).
  - The number of affected azimuths (> 0.05°) ranges from 0 to 489 of 720.
- **Effect on the metrics** (2026–2030, map definitions):
  - sun fraction changes by ≤ 0.75 pp (CHANGE5 0.5014 → 0.4939; most sites < 0.3 pp)
  - Earth visibility: **no change** at any site
- **Why it is not changed here**:
  - Within 200 m the 59 m DEM has only 2–3 pixels, so the height there is interpolation.
  - At 50 m, a 1 m height error is already 1.1° of elevation, so these near-field angles are not reliable from this DEM.
  - The cut-off is a documented engine parameter, not a bug.
  - Changing it would change Sua's engine default and all horizon files (cards 8, 9, 11), which is a team decision.

## 4. Not verified / limits
- PGDA's exact 18.6-year dates, its observer height and its terrain resolution are not stated (unverified). Our cycle is 2020–2038.
- This PGDA check covers 75–85° S only, not the mid-latitude map area.
- The map uses 360 azimuths and 474 m terrain everywhere. The site horizons use 720 azimuths and 59 m terrain.
- CHANDRAYAAN3 has no 59 m near field (`docs/global_terrain.md` §1).
