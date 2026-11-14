# Card 3 — non-polar terrain cache and hand-off to the horizon calculation

Owner: Soyun Jeong (card 3, C2b). Code: `pipeline/fetch_global.py`, checks: `pipeline/verify_global.py`,
tests: `python -m unittest pipeline.tests.test_fetch_global -v`. Sources: `data/DATASETS.md`.
Nothing here changes the shared web formats in `docs/data_contract.md`.

## 1. Coverage by latitude
| Site latitude | Near field (0–150 km) | Who fetches |
|---|---|---|
| −60 < lat < 60 | SLDEM2015 512 ppd (59 m) window | card 3 (`data/raw/sldem/<ID>.npz`) |
| −80 < lat ≤ −60 | **gap**: no SLDEM. LOLA 60 m polar-stereographic grids exist (PGDA `LDEM_60S_60MPP_ADJ.TIF`, already in card 2's source list; PDS `ldem_60s_60m_float.img`) | nobody yet; card 2 filters `lat ≤ −80` and card 3 stops at ±60 |
| lat ≥ 60 | **gap**: PDS `ldem_60n_60m_float.img` (60 m) | nobody yet (no known landed site there) |
| lat ≤ −80 | PGDA polar DEMs 5–240 m | card 2 (`data/raw/polar/<res>/<ID>.npz`) |
| far field, all sites | LDEM_64 (474 m) or LDEM_16 (1.9 km), whole Moon | card 3 (`data/raw/global/`) |

`fetch_global.py` reports sites in the gaps as `status: outside_sldem` in `data/raw/global_manifest.json`.

**Card 9 (2026-11-14) — affected site:** CHANDRAYAAN3 (−69.3741°, 32.3200°) is the only one of the 17 non-polar sites in
the 60–80° S gap. Its horizon (`web/data/horizon/CHANDRAYAAN3.json`) uses **LDEM_64 (474 m) from 0 km**, i.e. no 59 m near field.
The other 16 sites use SLDEM2015 to 150 km. Terrain features smaller than ~1 km close to the lander (crater rims, boulders
within a few km) are therefore smoothed for CHANDRAYAAN3. Its mask should be read as a coarse horizon until a 60 m
polar product (§1 table) is added to the chain.
Windows that reach past ±60° are clipped at 60° and flagged `clipped_at_60deg`.

## 2. Files (all git-ignored, local only)
`data/raw/sldem/<ID>.npz` (load with `allow_pickle=False`):
| key | meaning |
|---|---|
| `height_m` | float32 `[rows, cols]`, metres above the 1737.4 km sphere, rows north → south, no NaN |
| `lat` | float64 `[rows]`, pixel-centre latitude (deg), descending, step 1/512° |
| `lon_unwrapped` | float64 `[cols]`, pixel-centre longitude (deg E), ascending, may leave 0…360 so the window is contiguous |
| `lon` | same as `lon_unwrapped` but wrapped to −180…180 (may jump at ±180) |
| `meta` | JSON string: `id, site_lat, site_lon, radius_km, plan, pad_px, tiles, validators, clipped_at_60deg, site_is_mock, …` |

The window is the lat/lon box around the radius-150 km circle plus 2 pixels on every side.
`verify_global.py` check E confirms all 3600 azimuths at 150 km (and 148 km) can be sampled.

`data/raw/global/ldem_16_float.img|.lbl`, `ldem_64_float.img|.lbl`: PDS float32 grids in **km** above 1737.4 km,
0…360° E, pixel-registered (row r centre = `(LINE_PROJECTION_OFFSET − r)/res`, col s centre =
`180 + (s − SAMPLE_PROJECTION_OFFSET)/res`). Read through `LdemFile`, which converts to metres and −180…180 input.

## 3. Python interface for phase 2
```python
import sys; sys.path.insert(0, 'pipeline')
import fetch_global as fg
near = fg.SldemWindow('data/raw/sldem/APOLLO17.npz')       # load once, sample many times
far = fg.LdemFile('data/raw/global/ldem_64_float.img', 'data/raw/global/ldem_64_float.lbl')
h0 = float(near.height(site_lat, site_lon))                   # terrain height (m) -> contract h0_m
h = near.height(lat_array, lon_array)                         # bilinear, m; raises ValueError outside
ok = near.contains(lat_array, lon_array)                      # use far.sample(...) where ~ok
```
- Heights are terrain only. The 2 m observer height (`obs_height_m`) and the lunar curvature belong to the horizon step.
  With radii `r_obs = R + h0 + 2` and `r_t = R + h(target)` (R = 1 737 400 m), and angular distance `θ` between the
  observer and the target, the elevation angle is `atan2(r_t·cos θ − r_obs, r_t·sin θ)`.
- `sample_window(npz, lat, lon)` still exists but reloads the file on every call. Use `SldemWindow` in loops.
- Card 2's polar cache uses projected `x_m, y_m` (polar stereographic) instead of `lat, lon`. Phase 2 needs one sampler
  that hides this difference.

## 4. Known data offsets (re-review 2026-11-14)
- Independent check against the polar-stereographic `LDEM_45S_400M` product (different projection and gridding), plus
  SLDEM vs LDEM_64 at 7 windows from 55° S to 55° N:
  - SLDEM2015 as read here: offset 0.000° in lat and lon against the stereographic grid. Rows agree with LDEM_64 within 0.001°.
  - LDEM_64 (cylindrical): displaced **east by about 0.0015–0.0035°** (0.1–0.2 LDEM_64 pixel; 26–69 m on the ground).
  - LDEM_16 (cylindrical): displaced east by about 0.010° (0.16 LDEM_16 pixel).
  - The previous "90–100 m between SLDEM and LDEM_64" is this LDEM displacement, not an error in the SLDEM windows.
- The cause is **unverified**. The offset is a fraction of a pixel (0.1–0.2 px). An error in reading the label convention
  would give 0.5 or 1 px, so the reading code is unlikely to be the cause. A gridding/resampling artefact in the cylindrical
  GDR products is the leading hypothesis, but no documentation was found.
- Impact on the horizon, if LDEM is used only beyond 150 km: 100 m horizontal displacement on a 30° slope changes the
  height by ≤ 58 m, which is ≤ 0.022° of elevation at 150 km. That is < 10 % of the solar disk radius (0.2666°).
  So no correction is applied. Do **not** use LDEM_64 for the near field without considering this.
