# Task F — sparse native-resolution south-polar terrain

Jiyong; base main `89a9af1`. Candidate adds native PGDA 5/10 m tiles around catalogue regions to the existing browser terrain chain. All 16 south-polar centres and two fixed-seed nearby points per centre were compared (48 points, seed 2026111506). This is a developer comparison against card-8, not independent verification by another team member and not ground-truth accuracy.

## Decision and limits

Promote the sparse tiles for integrator review: mean and maximum absolute errors improve for all four metrics, and Sun/Earth/both agreement improves at all three previously reported headline centres. **Not every point or metric improves.** In particular SHACKLETON_RIM longest-dark error changes from −2 h to +14 h. The original plan phrase “headline locations do not worsen” was too broad; the decision uses the original task F fraction-error objective and explicitly accepts this duration tradeoff. No claim of all-metric non-regression.

These patches do not make the browser chain identical to card-8. Beyond 3 km it still uses the existing coarser chain; native-source gaps fall through. Remaining maximum differences on this sample are not bounds elsewhere. Sparse patch edges and distant terrain remain limitations. Catalogue horizon/metrics, local maps and all JS definitions are unchanged.

## Full-sample results

Absolute difference from card-8; fractions in percentage points (pp), duration in hours. Both paths use the same production ephemeris and actual core.js inclusive hourly definitions for 2026–2030; 720 azimuths, curvature, 2 m observer, 5 m to 300 km geometric march.

| Metric | Mean before → after | Median before → after | Maximum before → after | Points worsened |
|---|---:|---:|---:|---:|
| rms_deg | 0.135191 → 0.038113 | 0.106877 → 0.027628 | 0.756665 → 0.261385 | 1 |
| max_deg | 0.513125 → 0.149510 | 0.444700 → 0.114650 | 2.111400 → 0.816900 | 0 |
| sun_frac_diff | 0.494022 → 0.112429 | 0.344560 → 0.071878 | 3.984118 → 0.588719 | 5 |
| earth_frac_diff | 0.316132 → 0.065746 | 0.070737 → 0.022819 | 3.653249 → 0.502008 | 7 |
| both_frac_diff | 0.399039 → 0.090418 | 0.208790 → 0.067315 | 2.350310 → 0.486035 | 6 |
| longest_dark_h_diff | 33.354167 → 1.166667 | 1.500000 → 0.000000 | 696.000000 → 14.000000 | 3 |

## All 16 catalogue centres

Signed differences; Sun/Earth/both in pp and dark in h. Every centre reference exactly matched its current stored horizon and metrics; original CPU checked each GPU centre. Full 48-point table, coordinates, every metric, angles and loading bytes: [points.csv](task_f/points.csv).

| Site | Sun before → after | Earth before → after | Both before → after | Dark before → after |
|---|---:|---:|---:|---:|
| SHACKLETON_RIM | +1.220792 → -0.015973 | +0.047919 → +0.020537 | +0.515699 → -0.041073 | -2.000000 → +14.000000 |
| PEAK_NEAR_SHACKLETON | +2.427893 → +0.109529 | +0.296641 → -0.100402 | +1.665754 → +0.034228 | -197.000000 → -1.000000 |
| ARTEMIS_MALAPERT | +0.198521 → +0.093556 | +0.000000 → +0.000000 | +0.198521 → +0.093556 | -5.000000 → -1.000000 |
| IM1 | +0.344560 → +0.344560 | +0.000000 → +0.000000 | +0.344560 → +0.344560 | -2.000000 → -2.000000 |
| IM2 | +0.077583 → +0.041073 | +0.189394 → +0.189394 | +0.146039 → +0.116375 | -1.000000 → -1.000000 |
| ARTEMIS_CABEUS_B | +0.796367 → -0.093556 | +0.180267 → +0.015973 | +0.444962 → -0.041073 | -8.000000 → +0.000000 |
| ARTEMIS_HAWORTH | +0.511135 → +0.118656 | +3.137550 → -0.098120 | +1.928167 → -0.027382 | -1.000000 → +0.000000 |
| ARTEMIS_MOUTON_PLATEAU | +0.177985 → +0.054765 | +0.146039 → +0.006846 | +0.155166 → +0.020537 | +1.000000 → +0.000000 |
| ARTEMIS_MOUTON | -0.344560 → +0.104965 | -0.602410 → -0.070737 | -0.604691 → +0.013691 | +2.000000 → +0.000000 |
| ARTEMIS_NOBILE_RIM1 | +0.255568 → -0.031946 | +0.568182 → -0.182548 | +0.606973 → -0.166575 | -5.000000 → +1.000000 |
| ARTEMIS_NOBILE_RIM2 | +0.031946 → +0.045637 | -0.285232 → -0.036510 | -0.123220 → +0.022819 | +0.000000 → +0.000000 |
| ARTEMIS_DE_GERLACHE_RIM2 | -0.150602 → -0.075301 | -0.134629 → -0.177985 | -0.157448 → -0.132348 | +7.000000 → +2.000000 |
| ARTEMIS_SLATER_PLAIN | +0.232749 → +0.260131 | -0.102683 → +0.061610 | +0.015973 → +0.116375 | -1.000000 → -1.000000 |
| CONNECTING_RIDGE | -0.999452 → +0.349124 | -0.175703 → +0.502008 | -0.721066 → +0.486035 | +0.000000 → +0.000000 |
| DE_GERLACHE_RIM1 | +0.422143 → +0.020537 | +0.000000 → +0.000000 | +0.189394 → +0.036510 | +0.000000 → +0.000000 |
| SHOEMAKER_RIM_A | +0.068456 → -0.011409 | +0.002282 → +0.002282 | -0.009127 → +0.011409 | +0.000000 → +0.000000 |

## Every regression

Any increase in absolute error, with no rounding-based exemption. Units as above.

| Metric | Point | Signed before | Signed after |
|---|---|---:|---:|
| rms_deg | ARTEMIS_NOBILE_RIM2 | +0.027236809 | +0.027296092 |
| sun_frac_diff | SHACKLETON_RIM_R1 | +0.109529025 | +0.162011683 |
| sun_frac_diff | ARTEMIS_HAWORTH_R1 | +0.054764513 | +0.120938299 |
| sun_frac_diff | ARTEMIS_MOUTON_PLATEAU_R2 | +0.086710478 | -0.205366922 |
| sun_frac_diff | ARTEMIS_NOBILE_RIM2 | +0.031945966 | +0.045637094 |
| sun_frac_diff | ARTEMIS_SLATER_PLAIN | +0.232749179 | +0.260131435 |
| earth_frac_diff | PEAK_NEAR_SHACKLETON_R2 | +0.000000000 | +0.025100402 |
| earth_frac_diff | ARTEMIS_HAWORTH_R1 | +0.018254838 | +0.020536692 |
| earth_frac_diff | ARTEMIS_MOUTON_PLATEAU_R2 | +0.050200803 | +0.057046367 |
| earth_frac_diff | ARTEMIS_NOBILE_RIM2_R1 | +0.082146769 | +0.093556042 |
| earth_frac_diff | ARTEMIS_NOBILE_RIM2_R2 | +0.059328222 | +0.088992333 |
| earth_frac_diff | ARTEMIS_DE_GERLACHE_RIM2 | -0.134629427 | -0.177984666 |
| earth_frac_diff | CONNECTING_RIDGE | -0.175702811 | +0.502008032 |
| both_frac_diff | SHACKLETON_RIM_R1 | +0.034227820 | +0.066173786 |
| both_frac_diff | ARTEMIS_HAWORTH_R1 | +0.018254838 | +0.086710478 |
| both_frac_diff | ARTEMIS_MOUTON_PLATEAU_R2 | +0.068455641 | -0.098119752 |
| both_frac_diff | ARTEMIS_SLATER_PLAIN | +0.015972983 | +0.116374589 |
| both_frac_diff | SHOEMAKER_RIM_A | -0.009127419 | +0.011409273 |
| both_frac_diff | SHOEMAKER_RIM_A_R1 | +0.000000000 | +0.041073384 |
| longest_dark_h_diff | SHACKLETON_RIM | -2.000000000 | +14.000000000 |
| longest_dark_h_diff | PEAK_NEAR_SHACKLETON_R2 | +0.000000000 | -1.000000000 |
| longest_dark_h_diff | ARTEMIS_MOUTON_PLATEAU_R2 | +0.000000000 | +1.000000000 |

## Payload and local timing

210 additional sparse tiles (118 p5, 92 p10), **19,884,973 compressed bytes total**. A user downloads only the required tiles, not the complete set. Across the 48 points, median requested compressed terrain bytes changed from 6,417,423 to 6,726,539; maximum from 6,924,326 to 7,247,606. These counts exclude JS/ephemeris/index/HTTP overhead.

The full 48-point runs were concurrent and their timing is not a controlled speed comparison. The table below instead uses three serial cold-JS-cache repeats per path, alternating before/after order. OS file caching is not flushed. Timer includes local file reads, gzip decode, terrain march and core metrics; **not browser FPS, network latency or time-to-interactive**. Ryzen 5600X desktop; accuracy comes at extra computation cost.

| Point | Before median ms | After median ms |
|---|---:|---:|
| SHACKLETON_RIM | 1142 | 1209 |
| ARTEMIS_MALAPERT | 959 | 1531 |
| ARTEMIS_NOBILE_RIM1 | 989 | 1618 |

## Sources, encoding and reproduction

Native [PGDA 5 m](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/ldem_87s_5mpp.tif) and [PGDA 10 m](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF), MOON_ME DE421, metres above R=1737400 m. Existing catalogue-window caches provide original pixels; source hashes, bounds and per-tile window offsets are recorded in [results.json](task_f/results.json). No resampling or gap filling. 0.25 m quantization gives at most 0.125 m height encoding error, checked for every encoded pixel. This height bound is not an angular or visibility-error bound.

Tiles intersect 4 km projected discs around all 16 sites; only completely available finite tiles are published. p5/p10 are used to 3 km, followed by unchanged p20/p60/p240/global levels. The projection and first-pixel-centre offsets preserve the native lattice. The actual JS decoder/sampler is exercised on the test points.

The saved [baseline index](task_f/baseline_index.json) pins the pre-change chain even after promotion. Full before/after masks and raw metrics are in [before.json](task_f/before.json) and [after.json](task_f/after.json). Input and execution-file SHA-256 hashes are in results.json; checkout CRLF/LF conversion can alter text-file byte hashes. Reference generation uses original horizon.py + validated FP64 GPU and actual core.js, explicitly not an independent implementation.

From the repository root, with NumPy/pyproj, CuPy for the reference GPU, Node, and the original cached source windows present:

```powershell
python pipeline/task_f_tiles.py
python pipeline/task_f_reference.py
node pipeline/task_f_browser.mjs data/processed/task_f/points.json data/processed/task_f/browser_before.json
node pipeline/task_f_browser.mjs data/processed/task_f/points.json data/processed/task_f/browser_after.json data/processed/task_f/polar_s
python -m pytest pipeline/tests/test_task_f_tiles.py
```

The builder resumes by validating existing tile bytes against current original pixels. Its source defaults are `data/processed/local250/raw/polar`; the reference uses the same raw root plus global LDEM_64/16. Timings/profile inputs are preserved in results.json. Builder initial run 39.3 s; 48-point reference 88.3 s. Review/implementation time is additional. Existing broad-polar validation remains historical; these 48 regional checks do not replace a new full-polar validation run.

## Release checks

Three encoding/alignment tests pass; separate AI review checked every pixel of all 210 tiles against its cited NPZ and confirmed source-coordinate spacing and hashes. The harness rounds h0 to 0.01 m whereas the worker retains unrounded h0: an additional all-48-point core check found no metric changes (maximum height rounding 0.004926 m). This is an AI review for the same author, not another team member's verification.

The full contract checker first reports 33 existing windows producer-hash errors caused by Windows CRLF checkout of build_windows.mjs. Temporarily restoring that unchanged file's committed LF byte form gives PASS with zero errors/warnings; the original checkout bytes were restored afterward. verify_ledger.py reports FAILURES: 0. No scientific data were altered to pass checks.
