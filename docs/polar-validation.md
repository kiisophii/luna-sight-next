# Card 2 validation — 2026-11-14 (Jiyong)

Follow-up: [resolution diagnosis](polar-resolution-diagnosis.md) explains the
240 m discrepancy using fresh source bytes, independent GDAL checks and 1,728
resolution-matched cells. Original pointwise measurements below are preserved.

Automated evidence; human checks remain TO CHECK. All reported terrain values were calculated during this run.

## Results

- All 18 full-radius windows (three synthetic sites, six resolutions) completed successfully.
- 11 offline tests pass. Shared contract check: zero errors and ten pre-existing mock-data/source warnings.
- Independent code review checked actual TIFF metadata, pixel centers, bounds and cache behavior.
- GDAL/Rasterio independently decoded five pixels at each resolution (30 checks): maximum absolute difference from cached heights = 0 m. Pixel-center coordinates match within 1e-6 m.
- Integration smoke test: all six resolutions for the current catalog SHACKLETON_RIM mock point. This is not the source-backed Site04 coordinate.

## Cross-resolution differences

TEST_POLAR_1: five common projected coordinates, seed 42, bilinear interpolation. Differences in metres relative to the 5 m DEM.

| Point | 10 m | 20 m | 60 m | 80 m | 240 m |
|---|---|---|---|---|---|
| 1 | 0.770206 | 1.019725 | 0.082863 | -0.232003 | 0.326539 |
| 2 | 0.504607 | 0.496236 | 0.427658 | 0.553080 | 1.122979 |
| 3 | -0.171372 | 0.305601 | -1.386103 | -1.263919 | -8.988411 |
| 4 | 0.285335 | 0.368183 | 0.294907 | 0.457929 | 1.283371 |
| 5 | 0.084341 | 0.132029 | 0.520930 | 0.510519 | -1.796298 |

Maximum absolute difference: 10–80 m = 1.386103 m; 240 m = 8.988411 m. The broad few-metre acceptance statement is **not met at every resolution**. Coarse spatial averaging is a plausible explanation, not a proven diagnosis. No offsets were applied to force agreement. Five points do not establish global accuracy.

## Landmark check

NASA Site04 region center: (-89.7668, -171.87). Analytic and pyproj stereographic coordinates agree (error 0.0 m); inverse coordinates agree within 1e-9 degrees.
Regional DEM height = 771.043212890625 m; mosaic = 770.6483764648438 m; difference = -0.39483642578125 m. The nearest pixel center is 3.2725984153628063 m away. This checks a region center, not a surveyed summit.

## Inventory

| Site | Resolution (m) | Rows × columns | Finite pixels (%) |
|---|---|---|---|
| TEST_POLAR_1 | 10 | 5001 × 5000 | 100.000 |
| TEST_POLAR_2 | 10 | 5000 × 5001 | 100.000 |
| TEST_POLAR_3 | 10 | 5000 × 5001 | 100.000 |
| TEST_POLAR_1 | 20 | 2501 × 2500 | 100.000 |
| TEST_POLAR_2 | 20 | 2500 × 2501 | 100.000 |
| TEST_POLAR_3 | 20 | 2500 × 2501 | 100.000 |
| TEST_POLAR_1 | 240 | 1668 × 1668 | 100.000 |
| TEST_POLAR_2 | 240 | 1668 × 1668 | 100.000 |
| TEST_POLAR_3 | 240 | 1668 × 1667 | 100.000 |
| TEST_POLAR_1 | 5 | 1201 × 1200 | 100.000 |
| TEST_POLAR_2 | 5 | 1200 × 1201 | 100.000 |
| TEST_POLAR_3 | 5 | 1200 × 1201 | 100.000 |
| TEST_POLAR_1 | 60 | 2001 × 2000 | 100.000 |
| TEST_POLAR_2 | 60 | 2000 × 2001 | 100.000 |
| TEST_POLAR_3 | 60 | 2000 × 2001 | 100.000 |
| TEST_POLAR_1 | 80 | 1501 × 1500 | 100.000 |
| TEST_POLAR_2 | 80 | 1500 × 1501 | 100.000 |
| TEST_POLAR_3 | 80 | 1500 × 1501 | 100.000 |

## Reproduce and sources

See [polar.md](polar.md) for commands. Detailed local reports: `data/processed/polar_verification.json` and `data/processed/polar_landmark.json`. Raw data and caches are not committed.

- https://pgda.gsfc.nasa.gov/products/81 — 5 m, Barker et al. 2021.
- https://pgda.gsfc.nasa.gov/products/90 — 10–240 m, Barker et al. 2023.
- https://pgda.gsfc.nasa.gov/products/78 — regional Site04 DEM.
- https://ntrs.nasa.gov/api/citations/20250002845/downloads/M2M-30044%20Lunar%20Surface%20Data%20Book%20Baseline_Final.pdf — Table A2.1-1, p.75, Site04 coordinate.
- Exact file URLs and attribution: `data/DATASETS.md`.

Resume check: rerunning all 18 identical requests fetched **0 additional terrain/block payload bytes** (metadata probes excluded). All 18 existing NPZ files were reused.
