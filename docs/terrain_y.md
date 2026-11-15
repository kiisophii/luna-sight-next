# Task Y: local terrain descriptors

New `web/data/terrain/` contains 16 detailed south-polar products and 17 explicitly coarse comparison products, plus an index. The native original PGDA grid is 5 m at 8 sites, 10 m at 7, and 20 m at IM1. Every site includes the existing rounded 250 m-box relay-centre slope with its original hash; none of the existing relay, horizon, metric or UI files was changed.

## Definitions and interpretation

- The coordinate slope is a least-squares height plane through a 3×3 native-spaced sample grid centred exactly at the catalogue coordinate, using bilinear DEM heights. The span between outer sample centres is **10/20/40 m** for 5/10/20 m DEMs; the corresponding three-cell footprint is 15/30/60 m. These are terrain comparison scales, not proof of metre-scale landing-foot safety.
- Distribution slopes use 3×3 native pixel-centred planes. Stereographic scale and elevation radius are corrected by multiplying the projected gradient by `k*R/(R+h)`, `k=1+(rho/(2R))²`, `R=1737400 m`.
- Geodesic circles on the reference sphere use radii 100, 500 and 1000 m. Slope median, p95 and maximum are sample-centre statistics. Flat fractions use horizontal represented area `resolution²/k²`; circle boundary cells are included by their centres rather than clipped. `sampled_area_m2` makes that approximation visible.
- **8° and 15° are configurable reference cutoffs, not safe-landing limits.** Fractions are stored in [0,1], not percentages.
- Roughness is RMS vertical DEM-height residual from a best-fit plane in nominal 50 m ground-width square windows, summarized within 500 m. Only native sample centres inside ±25 m are included: 11×11 at 5 m, 5×5 at 10 m, 3×3 at 20 m. The actual centre span is recorded (about 50/40/40 m, with projection correction). This is not raw LOLA-spot roughness, obstacle size, or a direct measurement of rocks.
- The 17 non-polar records carry only the existing coarse 250 m-box comparison and source list; their fine-scale fields are null. The old relay values retain their original one-decimal rounding and were copied, not newly remeasured.

## South-polar summary

This table uses the 500 m radius. Full 100/500/1000 m distributions, maxima, represented areas and provenance are in each JSON. Differences between point and 250 m slope reflect different spatial baselines and sampling; they are not automatically calculation errors.

| Site | Native grid (m) | Coordinate slope (deg) | Existing 250 m slope (deg) | Area ≤8° (%) | Area ≤15° (%) | Roughness median / p95 (m) |
|---|---:|---:|---:|---:|---:|---:|
| ARTEMIS_CABEUS_B | 10 | 2.988 | 3.6 | 75.11 | 99.28 | 0.209 / 0.600 |
| ARTEMIS_DE_GERLACHE_RIM2 | 5 | 3.919 | 1.1 | 59.43 | 93.02 | 0.327 / 1.139 |
| ARTEMIS_HAWORTH | 5 | 4.179 | 1.5 | 78.54 | 99.42 | 0.315 / 0.677 |
| ARTEMIS_MALAPERT | 10 | 3.843 | 3.3 | 76.74 | 99.38 | 0.235 / 0.533 |
| ARTEMIS_MOUTON | 10 | 4.552 | 3.5 | 67.27 | 99.82 | 0.247 / 0.493 |
| ARTEMIS_MOUTON_PLATEAU | 10 | 0.075 | 1.0 | 94.17 | 99.82 | 0.226 / 0.573 |
| ARTEMIS_NOBILE_RIM1 | 10 | 2.762 | 4.0 | 82.14 | 99.84 | 0.211 / 0.438 |
| ARTEMIS_NOBILE_RIM2 | 10 | 1.370 | 1.1 | 68.07 | 88.14 | 0.176 / 0.426 |
| ARTEMIS_SLATER_PLAIN | 5 | 2.912 | 3.4 | 79.90 | 99.73 | 0.292 / 0.669 |
| CONNECTING_RIDGE | 5 | 3.535 | 3.5 | 69.71 | 92.76 | 0.332 / 0.724 |
| DE_GERLACHE_RIM1 | 5 | 1.119 | 3.6 | 69.01 | 96.27 | 0.336 / 0.679 |
| IM1 | 20 | 12.721 | 11.5 | 9.84 | 86.85 | 0.141 / 0.353 |
| IM2 | 10 | 3.088 | 2.1 | 99.01 | 99.99 | 0.139 / 0.344 |
| PEAK_NEAR_SHACKLETON | 5 | 6.090 | 2.4 | 77.88 | 99.90 | 0.270 / 0.571 |
| SHACKLETON_RIM | 5 | 2.124 | 1.0 | 15.62 | 54.01 | 0.476 / 0.870 |
| SHOEMAKER_RIM_A | 5 | 6.825 | 6.7 | 69.87 | 99.52 | 0.291 / 0.591 |

For example, the Shackleton coordinate has a modest local slope while much of its 500 m neighbourhood exceeds the reference cutoffs. A single point value cannot describe the whole surrounding landing/search area. Resolution also changes the amount of detail resolved, so roughness or steep-area fractions at 5 m and 20 m should not be treated as a controlled same-resolution ranking.

## Coarse comparisons only

| Site | Existing 250 m slope (deg) |
|---|---:|
| APOLLO11 | 1.2 |
| APOLLO12 | 2.0 |
| APOLLO14 | 0.5 |
| APOLLO15 | 1.3 |
| APOLLO16 | 2.7 |
| APOLLO17 | 2.0 |
| BLUE_GHOST1 | 1.2 |
| CHANDRAYAAN3 | 0.6 |
| CHANGE3 | 1.8 |
| CHANGE4 | 0.7 |
| CHANGE5 | 0.6 |
| CHANGE6 | 1.7 |
| IM3_REINER_GAMMA | 1.4 |
| LUNA16 | 0.3 |
| LUNA20 | 8.5 |
| LUNA24 | 0.5 |
| SLIM | 8.4 |

## Validation and runtime

Separate author-check code uses explicit least-squares fits, its own projection inversion, distance/area masks and bilinear sampling on the original DEM windows. It checks Shackleton (5 m), Malapert (10 m) and IM1 (20 m), including all neighbourhood slope/flat-fraction samples and roughness windows. Maximum slope difference: **2.2306601e-12 deg**; flat-fraction difference: **0 percentage points**; roughness median/p95 difference: **1.11022302e-16 m**. All 33 relay-centre values/hashes match and all 17 coarse products have null detailed fields. [Full check](terrain_y_check.json).

These tiny numerical differences demonstrate implementation agreement on the same DEM, not absolute accuracy of the lunar surface. Source/frame/radius/native registration, current producer/site/relay hashes and analytic fixtures were also checked. There are 22 focused tests plus 2 subtests. Full data contract: 0 errors, 0 warnings. An unrelated existing Task X test initially failed under Windows CP949 and passed when rerun with `python -X utf8`; no unrelated code was changed. For the full contract, Git LF bytes of the existing `core.js` and `build_windows.mjs` were temporarily used and original CRLF bytes restored, matching the pre-existing stored window-input hashes.

Final generation: **29.53 s** for all 33, one CPU worker and four bounded HTTP-prefetch workers. Original raster blocks were already cached on D; metadata HTTP probes still occurred. This excludes initial NASA downloads, implementation and earlier experiments. Independent numerical recheck: **0.663 s**. [Per-site generation timings](terrain_y_run.json). A GPU was unnecessary for these small local windows.

Coverage and resume tests cover all-nodata fallback, source-edge clipping with a complete required neighbourhood, propagation of transport/validation failures, and rejection of altered cached numeric content. All source/code/config inputs and each product's canonical content hash are checked before reuse.

## Reproduce and hand off

```sh
python -X utf8 pipeline/build_terrain_y.py --workers 4
python -X utf8 pipeline/verify_terrain_y.py
python -X utf8 -m pytest pipeline/tests/test_terrain_y.py pipeline/tests/test_terrain_y_contract.py pipeline/test_verify_terrain_y.py -q
python -X utf8 pipeline/check_contract.py
```

**Status: author-verified only.** Separate AI review and a separately written numerical checker run for Jiyong do not satisfy the board's different-team-member requirement. Another member should independently read original DEM windows, implement the 3×3 fit and area summation, and check three sites at ≤0.5 deg slope difference and ≤1 pp flat-fraction difference, then append their own ledger evidence. Re-running our producer alone is reproduction, not that independent check.

For a fresh source window, use the existing validated acquisition CLI, for example:

```sh
python pipeline/fetch_polar.py --site SHACKLETON_RIM --res 5 --radius-m 1200 --output data/processed/terrain_y/raw
python pipeline/fetch_polar.py --site ARTEMIS_MALAPERT --res 10 --radius-m 1200 --output data/processed/terrain_y/raw
python pipeline/fetch_polar.py --site IM1 --res 20 --radius-m 1200 --output data/processed/terrain_y/raw
```

Source URLs/validators/bounds/window hashes are embedded in products. Raw windows are ignored and remain on D on this desktop. NASA [PGDA product 90](https://pgda.gsfc.nasa.gov/products/90) documents the adjusted DEM family and its separate laser-spot roughness product. Our native 5/10/20 m source links and attribution are in `data/DATASETS.md`. Existing site coordinate uncertainty, DEM errors, interpolation and unresolved features remain limitations; no safety certification follows.
