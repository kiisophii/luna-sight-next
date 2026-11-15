# Task Z2 — native 20 m PSR distances, all 16 south-polar sites

Produced by Jiyong's AI-assisted workflow on 2026-11-15. These are **author-side checks**, not the independent team verification required by the task board. All 16 catalogue coordinates were computed; no representative subset replaces the requested full result. **PSR ≠ confirmed ice.**

## Original sources and interpretation

- NASA PGDA [A New View of the Lunar South Pole from LOLA](https://pgda.gsfc.nasa.gov/products/90) links the exact [LPSR_80S_20MPP_ADJ.TIF](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.TIF). Cite Barker et al. (2023), [10.3847/PSJ/acf3e1](https://doi.org/10.3847/PSJ/acf3e1); dataset [10.60903/gsfcpgda-lola-spole](https://doi.org/10.60903/gsfcpgda-lola-spole).
- The original raster header was read, not inferred from a filename: native float32 30400 × 30400; 20 m pixels; NaN no-data; pixel-is-area; first pixel center (-303990, 303990) m. Original GDAL `z#actual_range={0,1}`, `_FillValue=nan`; all fetched finite values are 0 or 1.
- GeoTIFF keys explicitly give south polar stereographic, latitude of origin -90°, central longitude 0°, scale at pole 1, false easting/northing 0, both lunar axes 1737400 m. The [original PRJ](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.PRJ) agrees. The product page identifies MOON_ME/DE421.
- The raster header does not spell out a class legend. The producer cross-checks **1=PSR** using the original [PSR polygon CSV](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.CSV), first record only: a scanline interior point in polygon gid=1, (42420.000, 41710.123) m, samples native raster value 1. With the binary range, 0 denotes not-PSR. The first CSV record SHA256 is `eb4e36d4ff76a2e2e126b86d577375adf9d18d3c2878fc224b02549c95143162`. This is an explicit source cross-check rather than an undocumented class-code assumption.
- HTTP identity: 154221202 bytes; ETag `W/"9313a92-1887ec3cff0"`; Last-Modified `Sat, 03 Jun 2023 00:59:02 GMT`. Each site stores these validators, the source metadata and exact native window provenance.

## Meaning of the reported distances

The nearest pixel result is the minimum spherical geodesic distance to any class-1 native pixel center in the fetched window. The boundary result minimizes spherical distance continuously along each exposed class-1/class-0 pixel edge, after inverse stereographic projection. It therefore describes the union of native 20 m pixel footprints; it does not substitute the separately distributed interpolated vector contour. Class-1/class-1 edges are internal and ignored. Unknown interfaces and window edges never become invented PSR boundaries.

Both distances use the 1737400 m reference sphere; projected metres are never treated as exact surface metres. Bearings are initial azimuths from true north clockwise, not grid north. Bearings at the geographic pole or zero distance are undefined/null. For an interior site, distance to PSR **area** is zero, while nearest boundary distance can be positive. Unknown site membership gives a null area distance. The current 16 sites all sample class 0. Values below are rounded for display; JSON retains computed precision, which does not imply subpixel physical accuracy.

| Site | Center distance m | Center bearing ° | Boundary distance m | Boundary bearing ° | Entire 10 km disk covered |
|---|---:|---:|---:|---:|---|
| IM1 | 559.282 | 302.057 | 545.534 | 301.763 | false |
| IM2 | 493.953 | 87.617 | 480.565 | 87.091 | true |
| ARTEMIS_CABEUS_B | 260.306 | 130.595 | 246.755 | 131.476 | true |
| ARTEMIS_HAWORTH | 104.560 | 198.522 | 94.505 | 200.514 | true |
| ARTEMIS_MALAPERT | 416.962 | 183.944 | 406.576 | 182.612 | true |
| ARTEMIS_MOUTON_PLATEAU | 239.039 | 7.459 | 225.190 | 6.784 | true |
| ARTEMIS_MOUTON | 416.515 | 302.236 | 403.199 | 302.892 | true |
| ARTEMIS_NOBILE_RIM1 | 103.661 | 104.193 | 89.635 | 105.154 | true |
| ARTEMIS_NOBILE_RIM2 | 306.350 | 205.094 | 295.143 | 206.726 | true |
| ARTEMIS_DE_GERLACHE_RIM2 | 160.577 | 6.633 | 147.132 | 5.002 | true |
| ARTEMIS_SLATER_PLAIN | 259.383 | 194.626 | 245.287 | 194.865 | true |
| SHACKLETON_RIM | 164.661 | 220.156 | 150.876 | 221.304 | true |
| CONNECTING_RIDGE | 404.259 | 153.153 | 391.992 | 152.140 | true |
| PEAK_NEAR_SHACKLETON | 90.370 | 319.860 | 79.799 | 326.200 | true |
| DE_GERLACHE_RIM1 | 149.791 | 341.680 | 139.472 | 337.932 | true |
| SHOEMAKER_RIM_A | 289.024 | 350.049 | 278.861 | 348.112 | true |

Every nearest center and boundary has `nearest_guaranteed=true`. IM1's nominal 10 km window meets the TIFF's northern edge, so `complete_within_radius=false`; the nearest unsearched point is conservatively at least **4030.013 m** away, well beyond its 559.282/545.534 m candidates. The other 15 full disks have complete coverage. All fetched rectangles contain zero NaN pixels; no-data handling is nevertheless exercised with synthetic cases.

## Search guarantee

For spherical polar stereographic coordinates at radius rho, local scale is `k=1+(rho/(2R))²`. The requested projected rectangle uses an upper scale bound over the site's search cap and includes two pixels of margin. The request is clipped to the original source extent.

Within the fetched rectangle, the maximum corner rho bounds scale. Minimum Euclidean distance to the rectangle edge divided by this maximum scale is a conservative lower bound to any route leaving the searched domain. A geodesic reaching unknown pixels is similarly bounded by the nearest unknown pixel footprint divided by maximum scale; a path leaving the rectangle earlier is covered by the perimeter bound. A candidate nearer than both lower bounds is guaranteed nearest. Full-disk completeness requires both bounds at least the radius. If nothing is found in a complete search, the product emits a lower bound `> radius`; incomplete coverage cannot produce that assertion.

All exposed known pixel edges are considered. Their nearest projected points provide an initial upper bound; the scale bound eliminates only edges that cannot improve it. Remaining 20 m segments use 55 golden-section iterations plus both endpoints on the spherical-distance objective. This numerical precision is far below the pixel scale. It does not estimate ice content, terrain traverse distance, accessible routes or landing safety.

## Acquisition, resources and resume

Only HTTP Range requests are used by the existing tested `fetch_polar.RangeFile`: a one-byte metadata probe followed by cached 1 MiB ranges, with HTTP 206, exact Content-Range, ETag and Last-Modified checks. A server ignoring Range is rejected before reading its body. Native full-resolution tiles intersecting the requested windows are decoded; overviews are never used. The first CSV record comes from a 1 MiB prefix; the PRJ is 368 bytes. No full raster/CSV/vector file was downloaded.

Cached source ranges occupy **12583280 bytes** (12 MiB plus the 368-byte PRJ, across TIFF/CSV/PRJ) after source discovery and production. The TIFF is 154221202 bytes. Everything raw/intermediate is under ignored `data/processed/detail_z2/`, an existing junction to `D:/NASA-Lunar/storage/lunar-crosscheck-jiyong/data/processed/detail_z2/`. Published JSON contains only summary geometry and provenance.

- Original all-16 acquisition/compute pass: **31.619 s**, including **9437184 newly fetched TIFF bytes**; some source-discovery blocks were already cached.
- Final post-review all-16 forced recompute: **3.302 s**, zero new TIFF bytes.
- Final unchanged resume: **1.889 s**, all 16 reused, zero new TIFF bytes.
- One compute worker and one download thread; BLAS/OpenMP default capped to one. No GPU: all cached analysis completes in seconds and data transfer/kernel setup would add complexity to this small I/O-driven workload. No GPU performance claim is made without a benchmark.

Site identity, coordinates, radius, full source validators/metadata and normalized producer/fetch-module hashes determine input signatures. Exported result content hashes are also verified against durable checkpoints; changing a result without changing its signature does not permit resume. Cached class-array SHA256 is checked before reuse. All writes are atomic. The old manifest is removed before preflight, and the new index is published only when all 16 files have completed; interrupted runs retain per-site checkpoints. Per-run timing records are retained under the ignored `runs/` directory.

## Reproduce and verify

From the repository root, with NumPy, pyproj, requests, tifffile and the TIFF decoder dependencies used by `fetch_polar.py`:

```powershell
& C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe -X utf8 pipeline/detail_psr.py --force
& C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe -X utf8 -m pytest pipeline/tests/test_detail_psr.py -q
& C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe -X utf8 pipeline/detail_psr.py
```

The scoped suite passes **15 tests** covering polar bearing, projection scale/grid rotation, date line, zero-distance/inside-region behavior, union-vs-internal boundaries, unknown data, invalid class codes, incomplete windows, a near result despite distant missing coverage, boundary inside the search radius while its center is outside, stale signatures and result tampering. All 16 index content hashes were explicitly recomputed and matched.

For independent team verification, another person should choose at least three sites (include IM1 for source-edge handling), obtain the same native windows from NASA or the cache paths recorded in each JSON, and write their own class selection plus inverse projection/geodesic/minimization code without importing `pipeline/`. Compare center and boundary distances to <=1%; separately check containing pixel, true-north bearing convention, missing-data bounds and the original class-code evidence. The root integration performs a separate-formula AI author check; it does not satisfy the required independent-human/team ledger row.
