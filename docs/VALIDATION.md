# Team validation table — Ginkgo Orbit (card 16)

Every check the team has run, in one place. Numbers are copied from the report file named in each row;
"PR" is the pull request that merged the check into main. Status: 2026-11-14 13:30 KST.
**Human review:** several "How a human checked it" cells in `docs/SI_USAGE.md` are still TO CHECK.

(The card 11 PGDA write-up moved from `docs/validation.md` to `docs/validation_pgda.md`, because
`validation.md` and `VALIDATION.md` are the same file name on Windows and macOS.)

| # | What is checked | Independent reference | Result | Criterion | Pass | Command / report | PR |
|---|---|---|---|---|---|---|---|
| 1 | Ephemeris 2026–2030 (`web/data/ephem.bin`): Sun & Earth az/el, 6 lunar test sites, 60 days, 12 h | JPL Horizons API (DE441) | 1,452 comparisons; sky-angle max 0.000016°; web float32 via `core.js` max az 0.00044°, el 0.000034° | < 0.01° | ✅ | `python pipeline/validate_ephem.py` → `docs/ephem_validation.json`, `docs/ephem_web_check.json` | #2 |
| 2 | Same for 6 real catalogue sites (Apollo 17, Chang'e 4, Shackleton R04, Chandrayaan-3, SLIM, IM-1) | JPL Horizons | 1,452 comparisons, max 0.000034° | < 0.01° | ✅ | `python pipeline/validate_real_sites.py` → `docs/real_sites_horizons_check.json` | #6 → #12 |
| 3 | 18.6-year validation ephemeris (2020–2038, 2 h, 81,444 rows), checked without `ephem.py`/Skyfield | JPL Horizons, 4 sites every 38 h; overlap with ephem.bin; libration limits | 34,296 comparisons, max 0.000041°; 21,912 overlap rows bit-identical; libration lat ±6.86°, lon −8.05…8.08° | < 0.01° | ✅ | `python pipeline/verify_card10_npz.py` → `docs/card10_npz_independent_check.json` | #11 |
| 4 | Polar DEM windows (card 2): decoded heights | GDAL/rasterio direct pixel read | 30 checks, max difference 0 m | identical | ✅ | `docs/polar-validation.md` | #1 |
| 5 | Polar DEM cross-resolution agreement (5 points, 10–240 m vs 5 m) | 5 m DEM | 10–80 m: ≤ 1.39 m; 240 m: ≤ 8.99 m | "a few metres" | ⚠️ 240 m not met (explained in `docs/polar-resolution-diagnosis.md`) | `docs/polar-validation.md` | #1 |
| 6 | South-polar site horizons (card 8, 16 sites, 5–240 m chain) | brute-force re-march, 2.5 m uniform steps (2 sites × 10 azimuths) | max difference 0.00053° | — | ✅ | `docs/polar-horizon-verification.json`, `docs/polar-horizons.md` | #8 |
| 7 | Non-polar site horizons (card 9, 17 sites, all 720 azimuths) | own brute-force code (no `horizon.py`), same 0.2 km start | max 0.012–0.219° (0.016° with 1 m steps), RMS ≤ 0.026° | ~0.02° | ✅ | `python pipeline/verify_card9.py` → `docs/card9_verification.md` | #9 |
| 8 | **PGDA 85–90° S**, 240 random points (60/240 m terrain, 18.6 y): Sun, mean disc fraction | NASA PGDA AVGVISIB 60 m (Mazarico et al. 2011) | MAE 1.66 pp, RMSE 2.62 pp, r 0.985, bias −0.25 pp | — | ✅ | `python pipeline/validate_ours.py` → `web/data/validation.json`, `docs/validation_pgda.md` | #7 |
| 9 | Same: Earth, any part of the disc (PGDA's definition) | PGDA AVGVISIB_EARTH 60 m | MAE 1.24 pp, RMSE 3.37 pp, r 0.990 (app's stricter centre rule: MAE 3.87 pp) | — | ✅ | same | #7 |
| 10 | PGDA, 16 named south-polar sites with card 8 horizons | PGDA ±300 m | Sun MAE 3.63 pp, Earth 3.57 pp (5.59 / 4.53 with the coarser 60/240 m windows) | — | ✅ (rims and peaks: large local PGDA spread) | `python pipeline/validate_ours.py --named-horizons web/data/horizon` | #10 |
| 11 | Whole-Moon 3.8 km map engine, 75–85° S (400 points) | PGDA AVGVISIB 120 m; independent re-implementation | engine Sun MAE 2.19 pp, r 0.938; independent Sun MAE 2.12 pp, r 0.940; Earth (any) MAE 1.73 pp, r 0.989; engine vs independent MAE 0.37 pp | — | ✅ | `python pipeline/global_maps.py validate --n 400`; `docs/card9_verification.md` | #9 |
| 12 | PGDA truth extraction (card 5): pixel values and projection | rasterio direct read at projected coordinates | 5 points × Sun/Earth identical; projection vs GeoTIFF CRS 0.000 m | identical | ✅ | `python pipeline/validate.py --selftest` | #3 |
| 13 | Site metrics (card 10): app `core.js` vs Python port, 2026–2030 hourly | separate vectorised Python port | identical on 3 synthetic fixtures and all 33 real sites | 4 decimals | ✅ | `node pipeline/test_metrics.mjs` → `docs/metrics_equivalence_check.json` | #12 |
| 14 | Browser custom-site horizon (948 m tiles) | Python `horizon.py` on the same tiles; full LDEM_64; card 8 polar horizons | JS vs Python RMS ≤ 5e-11°; vs LDEM_64 RMS 0.02–0.16°, Sun ≤ 0.05 pp; vs card 8 polar median RMS 0.96° (max 4.87°) | — | ✅ (near the pole use catalogue sites) | `docs/custom_horizon_validation.json`, `docs/custom_sites_and_dates.md` | phase 3 |
| 15 | Ground-station Moon az/el (KDSA, Goldstone, Madrid, Canberra) | JPL Horizons, 100 random hours per station (seed 16) | max 0.0012° | < 0.05° | ✅ | `python pipeline/verify_korea.py` → `docs/korea_links_check.json` | card 16 PR |
| 16 | Station "Moon ≥ 10°" bits, all 43,824 h × 4 stations | Horizons hourly elevations | 2 of 175,296 station-hours differ, both within 0.0008° of 10° | threshold only | ✅ | same | card 16 PR |
| 17 | Site–station link hours (33 sites) | brute force for 5 sites without `korea_links.py` (own Earth-visibility code + Horizons station bits) | differences ≤ 1 h (threshold hours); own Earth visibility = app metrics exactly | ≤ 2 h | ✅ | same, `docs/korea_links.md` | card 16 PR |
| 18 | Relay tower (card 13) | — | **pending** (card 13 running) | — | ⏳ | — | — |

## Not validated (stated limits)
- No ground truth for site horizons beyond the DEMs themselves (no surface photographs compared).
- Link windows are geometry only: no link budget, no antenna scheduling; permission to use KDSA coordinates is pending.
- SHACKLETON_RIM is the published R04 DEM-centre point on the inner crater wall (coordinate/name fix: card 15). Rows 8–10, 13 and 17 change for that one site if its coordinates change.
- PGDA's exact 18.6-year dates and observer height are not stated (unverified).

## Validation paragraph for the submission (≤ 150 words)

**Validation.** We checked every number in the app against an independent source. Sun and Earth
directions agree with NASA JPL Horizons to within 0.0005° in more than 37,000 comparisons from 2020
to 2038. Terrain horizons were re-derived by brute force from NASA LOLA elevation models and agree
to about 0.02°. Against NASA's 18.6-year south-polar illumination maps (PGDA), our sunlight fractions
at 240 random points differ by 1.7 percentage points on average (r = 0.985) and Earth visibility by
1.2 points (r = 0.990); the largest errors are on steep crater walls, where PGDA itself changes
strongly within 60 m. The app's metrics are identical in JavaScript and in a separate Python
implementation. Moon visibility from Yeoju KDSA and NASA's three DSN complexes matches Horizons to
0.0012°. Limits: geometry only (no link budget) and coarser terrain away from the poles.
