# Team validation table — Ginkgo Orbit (card 16)

Every check the team has run, in one place. Numbers are copied from the report file named in each row;
"PR" is the pull request that merged the check into main. Status: 2026-11-14 15:20 KST (after card 15 moved SHACKLETON_RIM and card 13 finished).
**Human review:** several "How a human checked it" cells in `docs/SI_USAGE.md` are still TO CHECK.

(The card 11 PGDA write-up moved from `docs/validation.md` to `docs/validation_pgda.md`, because
`validation.md` and `VALIDATION.md` are the same file name on Windows and macOS.)

| # | What is checked | Independent reference | Result | Criterion | Pass | Command / report | PR |
|---|---|---|---|---|---|---|---|
| 1 | Ephemeris 2026–2030 (`web/data/ephem.bin`): Sun & Earth az/el, 6 lunar test sites, 60 days, 12 h | JPL Horizons API (DE441) | 1,452 comparisons; sky-angle max 0.000016°; web float32 via `core.js` max az 0.00044°, el 0.000034° | < 0.01° | ✅ | `python pipeline/validate_ephem.py` → `docs/ephem_validation.json`, `docs/ephem_web_check.json` | #2 |
| 2 | Same for 6 real catalogue sites (Apollo 17, Chang'e 4, Shackleton R04 *old point*, Chandrayaan-3, SLIM, IM-1) | JPL Horizons | 1,452 comparisons, max 0.000034° | < 0.01° | ✅ | `python pipeline/validate_real_sites.py` → `docs/real_sites_horizons_check.json` | #6 → #12 |
| 3 | 18.6-year validation ephemeris (2020–2038, 2 h, 81,444 rows), checked without `ephem.py`/Skyfield | JPL Horizons, 4 sites every 38 h; overlap with ephem.bin; libration limits | 34,296 comparisons, max 0.000041°; 21,912 overlap rows bit-identical; libration lat ±6.86°, lon −8.05…8.08° | < 0.01° | ✅ | `python pipeline/verify_card10_npz.py` → `docs/card10_npz_independent_check.json` | #11 |
| 4 | Polar DEM windows (card 2): decoded heights | GDAL/rasterio direct pixel read | 30 checks, max difference 0 m | identical | ✅ | `docs/polar-validation.md` | #1 |
| 5 | Polar DEM cross-resolution agreement (5 points, 10–240 m vs 5 m) | 5 m DEM | 10–80 m: ≤ 1.39 m; 240 m: ≤ 8.99 m | "a few metres" | ⚠️ 240 m not met (explained in `docs/polar-resolution-diagnosis.md`) | `docs/polar-validation.md` | #1 |
| 6 | South-polar site horizons (card 8, 16 sites, 5–240 m chain) | brute-force re-march, 2.5 m uniform steps (2 sites × 10 azimuths) | max difference 0.00053° | — | ✅ | `docs/polar-horizon-verification.json`, `docs/polar-horizons.md` | #8 |
| 7 | Non-polar site horizons (card 9, 17 sites, all 720 azimuths) | own brute-force code (no `horizon.py`), same 0.2 km start | max 0.012–0.219° (0.016° with 1 m steps), RMS ≤ 0.026° | ~0.02° | ✅ | `python pipeline/verify_card9.py` → `docs/card9_verification.md` | #9 |
| 8 | **PGDA 85–90° S**, 240 random points (60/240 m terrain, 18.6 y): Sun, mean disc fraction | NASA PGDA AVGVISIB 60 m (Mazarico et al. 2011) | MAE 1.66 pp, RMSE 2.62 pp, r 0.985, bias −0.25 pp | — | ✅ | `python pipeline/validate_ours.py` → `web/data/validation.json`, `docs/validation_pgda.md` | #7 |
| 9 | Same: Earth, any part of the disc (PGDA's definition) | PGDA AVGVISIB_EARTH 60 m | MAE 1.24 pp, RMSE 3.37 pp, r 0.990 (app's stricter centre rule: MAE 3.87 pp) | — | ✅ | same | #7 |
| 10 | PGDA, 16 named south-polar sites with card 8 horizons | PGDA ±300 m | Sun MAE 3.67 pp, Earth 3.56 pp (5.56 / 4.52 with the coarser 60/240 m windows); new Shackleton rim point S: ours Sun 0.845 vs PGDA 0.871, Earth 0.538 vs 0.537 | — | ✅ (rims and peaks: large local PGDA spread) | `python pipeline/validate_ours.py --named-horizons web/data/horizon` | #10, card 16 Shackleton PR |
| 11 | Whole-Moon 3.8 km map engine, 75–85° S (400 points) | PGDA AVGVISIB 120 m; independent re-implementation | engine Sun MAE 2.19 pp, r 0.938; independent Sun MAE 2.12 pp, r 0.940; Earth (any) MAE 1.73 pp, r 0.989; engine vs independent MAE 0.37 pp | — | ✅ | `python pipeline/global_maps.py validate --n 400`; `docs/card9_verification.md` | #9 |
| 12 | PGDA truth extraction (card 5): pixel values and projection | rasterio direct read at projected coordinates | 5 points × Sun/Earth identical; projection vs GeoTIFF CRS 0.000 m | identical | ✅ | `python pipeline/validate.py --selftest` | #3 |
| 13 | Site metrics (card 10): app `core.js` vs Python port, 2026–2030 hourly | separate vectorised Python port | identical on 3 synthetic fixtures and all 33 real sites; new SHACKLETON_RIM metrics re-run with `core.js` = card 13's file exactly (Sun 0.848, Earth 0.499, longest dark 75 h) | 4 decimals | ✅ | `node pipeline/test_metrics.mjs`, `node pipeline/cache_metrics.mjs` → `docs/metrics_equivalence_check.json` | #12, #14 |
| 14 | Browser custom-site horizon: global path (948 m LDEM_64 tiles) and, ≥ 75° S, the PGDA polar path (20 m / 60 m to 3 km, 240 m to 150 km; s4) | Python `horizon.py` on the same tiles; full LDEM_64; **card-8 chain (PGDA 5–240 m) at 16 catalogue sites + 30 random points 75–90° S** | JS vs Python RMS ≤ 5e-11° (both paths); global vs LDEM_64 RMS 0.02–0.16°. Polar, before → after: catalogue median RMS 0.975° → **0.085°** (max 4.87° → 0.18°), |Δsun| max 33.7 → 2.4 pp; random median 0.652° → **0.027°** (max 0.32°), |Δsun| max 30.3 → 0.43 pp | median RMS ≤ 0.2° and |Δsun| ≤ 2 pp per point | ✅ 75–85° S; ⚠️ 85–90° S — **known limit:** at PEAK_NEAR_SHACKLETON the browser sunlight is +2.40 pp above the card-8 chain (RMS 0.141°; card 8 uses 5 m there, the browser 20 m), over the 2 pp target; the app shows "Lower accuracy here" with this limit and the numbers; north of 75° N not validated (badge) | `python pipeline/validate_custom_polar.py` → `docs/custom_polar_validation.json`, `docs/custom_polar.md`; `docs/custom_horizon_validation.json` | phase 3, s4 branch |
| 15 | Ground-station Moon az/el (KDSA, Goldstone, Madrid, Canberra) | JPL Horizons, 100 random hours per station (seed 16) | max 0.0012° | < 0.05° | ✅ | `python pipeline/verify_korea.py` → `docs/korea_links_check.json` | card 16 PR |
| 16 | Station "Moon ≥ 10°" bits, all 43,824 h × 4 stations | Horizons hourly elevations | 2 of 175,296 station-hours differ, both within 0.0008° of 10° | threshold only | ✅ | same | card 16 PR |
| 17 | Site–station link hours (33 sites) | brute force for 5 sites without `korea_links.py` (own Earth-visibility code + Horizons station bits) | differences ≤ 1 h (threshold hours); own Earth visibility = app metrics exactly | ≤ 2 h | ✅ | same, `docs/korea_links.md` | card 16 PR |
| 18 | Relay tower (card 13): tower link fractions | independent verifier (no production geometry; PROJ geodesics + own 3D rays), 3 sites, same DEMs | max full-window difference 0.0011 pp; 30-epoch mismatches 0/0/0 | ≤ 1 pp, ≤ 1 % mismatches | ✅ (3 sites; implementation check, not terrain truth) | `python pipeline/verify_card13_relay.py` → `docs/card13_independent.json`, `docs/card13_relay_report.md` | #14 |

## Not validated (stated limits)
- No ground truth for site horizons beyond the DEMs themselves (no surface photographs compared).
- Link windows are geometry only: no link budget, no antenna scheduling; permission to use KDSA coordinates is pending.
- SHACKLETON_RIM moved (card 15, PR #16) from the R04 DEM-centre point on the inner crater wall to the Gläser et al. (2017) rim point S (−89.6866, −162.81; datum alignment with MOON_ME unverified). Rows 10, 13, 17 use the new point; rows 1–2 and older reports keep the old point as historical records.
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
