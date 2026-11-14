# Coordinate uncertainty (card 23)

"If the landing-site coordinate is off by r metres, how much can the numbers change?"
Each catalogue site gets 121 nodes (11 × 11, 100 m spacing, ±500 m). For a radius r the
nodes with hypot(east, north) ≤ r are used (100 m: 5, 300 m: 29, 500 m: 81 nodes).
Format: `docs/data_contract.md` section 18. Values are 2026-01-01 … 2030-12-31 hourly,
computed with the actual `web/js/core.js`. Nodes are point samples on the same DEM; DEM
height errors are not included.

<!-- NON-POLAR BEGIN -->
## Non-polar sites (lat > −75°, Sua, `pipeline/coord_uncertainty.py`)

Chain = production card 9 horizons (SLDEM2015 59 m to 150 km, LDEM_64/LDEM_16 to 300 km; CHANDRAYAAN3 LDEM_64/16), 0.2 km start, 4000 steps, 720 azimuths, 2 m observer. Centre node = `web/data/metrics/<ID>.json` exactly.

| Site | lat | Sun % centre | Sun % ±300 m (min–max) | Δ300 (pp) | Sun % ±500 m | Earth % ±300 m | Both % ±300 m | Longest dark h ±300 m |
|---|---|---|---|---|---|---|---|---|
| CHANGE3 | 44.12 | 50.1 | 43.5–50.2 | 6.6 | 43.5–50.2 | 100.0–100.0 | 43.5–50.2 | 360–406 (centre 360) |
| IM3_REINER_GAMMA | 7.58 | 49.5 | 48.7–50.0 | 1.3 | 48.7–50.0 | 100.0–100.0 | 48.7–50.0 | 357–367 (centre 361) |
| SLIM | -13.32 | 47.7 | 46.5–47.8 | 1.3 | 46.5–47.9 | 100.0–100.0 | 46.5–47.8 | 371–381 (centre 372) |
| APOLLO14 | -3.65 | 49.1 | 48.0–49.2 | 1.3 | 47.5–49.2 | 100.0–100.0 | 48.0–49.2 | 361–370 (centre 362) |
| CHANGE6 | -41.64 | 49.7 | 48.9–50.0 | 1.1 | 48.8–50.0 | 0.0–0.0 | 0.0–0.0 | 361–369 (centre 364) |
| LUNA16 | -0.51 | 49.3 | 48.7–49.7 | 1.0 | 48.6–49.8 | 100.0–100.0 | 48.7–49.7 | 357–364 (centre 360) |
| LUNA24 | 12.71 | 49.5 | 48.8–49.8 | 0.9 | 48.8–49.8 | 100.0–100.0 | 48.8–49.8 | 358–364 (centre 359) |
| LUNA20 | 3.79 | 47.8 | 47.0–47.9 | 0.9 | 46.4–47.9 | 100.0–100.0 | 47.0–47.9 | 370–376 (centre 371) |
| CHANGE5 | 43.06 | 50.2 | 49.3–50.2 | 0.9 | 43.5–50.2 | 100.0–100.0 | 49.3–50.2 | 360–366 (centre 360) |
| APOLLO17 | 20.19 | 47.7 | 46.9–47.8 | 0.9 | 46.1–47.9 | 100.0–100.0 | 46.9–47.8 | 371–378 (centre 371) |
| APOLLO12 | -3.01 | 49.9 | 49.3–50.1 | 0.8 | 47.0–50.1 | 100.0–100.0 | 49.3–50.1 | 355–361 (centre 356) |
| CHANGE4 | -45.46 | 49.3 | 48.7–49.5 | 0.7 | 47.9–49.5 | 0.0–0.0 | 0.0–0.0 | 365–371 (centre 367) |
| BLUE_GHOST1 | 18.56 | 49.6 | 49.3–49.9 | 0.6 | 48.3–49.9 | 100.0–100.0 | 49.3–49.9 | 357–361 (centre 359) |
| APOLLO15 | 26.13 | 47.2 | 46.8–47.4 | 0.6 | 46.5–47.5 | 100.0–100.0 | 46.8–47.4 | 376–380 (centre 377) |
| APOLLO11 | 0.67 | 49.7 | 49.2–49.8 | 0.5 | 48.6–49.9 | 100.0–100.0 | 49.2–49.8 | 356–360 (centre 357) |
| APOLLO16 | -8.97 | 49.6 | 49.2–49.6 | 0.4 | 48.7–49.6 | 100.0–100.0 | 49.2–49.6 | 358–361 (centre 359) |
| CHANDRAYAAN3 | -69.37 | 47.9 | 47.8–48.0 | 0.2 | 47.8–48.4 | 100.0–100.0 | 47.8–48.0 | 383–385 (centre 385) |

Independent check: `python pipeline/verify_coord_uncertainty.py` → `docs/coord_uncertainty_validation.json` (VALIDATION.md row 20).
<!-- NON-POLAR END -->
