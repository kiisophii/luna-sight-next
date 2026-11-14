# Card 2: south-polar DEM cache (Jiyong)

## Run

From the repository root (Python 3.10+):

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r pipeline/requirements-polar.txt
.venv/Scripts/python pipeline/fetch_polar.py
```

Reads `web/data/sites.json` when present. Until then, three explicitly synthetic
`TEST_POLAR_*` points are used; they are not verified landing-site coordinates and
are never written into the shared site catalog. Southern sites at <= -80 degrees
are selected. Use `--site ID`, `--res 5 10`, `--sites path.json` to narrow a run.
For a smoke test, use `--radius-m 100 --output data/raw/polar_smoke`.

| Resolution (m) | Projected window radius (km) |
|---|---|
| 5 | 3 |
| 10 | 25 |
| 20 | 25 (implementation choice; card did not specify) |
| 60, 80 | 60 |
| 240 | 200 |

Windows are pixel-aligned squares enclosing these projected radii, not clipped
circles or geodesic buffers. Projection scale varies with distance from the pole.
Requests beyond a source's rectangular extent fail explicitly; invalid terrain
pixels remain NaN, and an all-nodata window is rejected. A missing high-resolution
window does not silently substitute a coarser product. Failures produce a nonzero
exit after other windows have been attempted.

## Local cache contract (does not alter shared web formats)

`data/raw/polar/<resolution>/<ID>.npz`, readable with `allow_pickle=False`:

- `height_m`: little-endian float32, rows north to south, NaN for no data.
- `x_m`, `y_m`: 1D pixel-center projected coordinates, x ascending/y descending.
- `metadata`: JSON string: source URL, size/validators, site, source pixel bounds,
  radius, resolution, projection, reference radius, frame and original GeoTIFF tags.

Coordinates: spherical south polar stereographic, origin -90/0 degrees, scale 1,
R=1737400 m, MOON_ME DE421. Heights are metres above that sphere. PixelIsArea and
PixelIsPoint are handled explicitly. Curvature and 2 m observer height belong to
phase-2 horizon calculation; neither modifies these raw terrain heights.

Source TIFFs are accessed through HTTP Range. Full-resolution intersecting TIFF
tiles/strips are decoded, with surrounding 1 MiB transport blocks retained under
`_blocks/`. This entails bounded extra bytes around needed tiles, not full-file
downloads. Logs report image/block payload bytes fetched in that run; the tiny
metadata probe and HTTP header overhead are excluded. Each completed block survives
interruption; an incomplete block is downloaded again (at most 1 MiB), and the NPZ
is atomically replaced only after decoding succeeds. Rerun the same command to resume.
Cache namespaces include URL, byte size, ETag, Last-Modified and block size. Every
response is checked against the initial validators and Content-Range. Do not run
multiple writers against the same output root. PGDA rejects some If-Range requests;
response validators are compared directly instead. No credentials are required.

## Verification (separate from generation)

```powershell
.venv/Scripts/python -m pytest pipeline/tests/test_fetch_polar.py -q
.venv/Scripts/python pipeline/verify_polar.py --site TEST_POLAR_1
.venv/Scripts/python pipeline/check_polar_landmark.py
```

The second command selects five seeded common coordinates, compares bilinearly
sampled heights across all six resolutions, then independently decodes matching
pixels using GDAL/Rasterio and checks pixel-center coordinates. For GDAL, downloaded
byte blocks are assembled into a local sparse TIFF, not a second full download.
Windows requires NTFS sparse-file support (`fsutil sparse setflag`). Verification
reports go under ignored `data/processed/`. They are automated evidence, not a
human check; SI log human-check cells remain TO CHECK.

Different DEM generations and spatial averaging can produce differences greater
than a few metres on steep terrain. Report the differences; do not shift elevations
to force agreement. The landmark command uses NASA/TP-20250002845 Table A2.1-1
(p.75), Site04 (-89.7668, -171.87). It checks analytic versus pyproj projection,
inverse round-trip, coverage in the named Site04 regional DEM, and agreement with
the 5 m mosaic at the same pixel center. This is a region-center check, not an
independent survey of a summit. On 2026-11-14, the regional and mosaic elevations
were 771.043212890625 m and 770.6483764648438 m (difference -0.39483642578125 m),
with the nearest pixel center 3.2725984153628063 m from the reference coordinate.

Sources: [PGDA 81](https://pgda.gsfc.nasa.gov/products/81) (5 m, Barker 2021) and
[PGDA 90](https://pgda.gsfc.nasa.gov/products/90) (10–240 m, Barker 2023).
Exact file URLs and citations are in `data/DATASETS.md`.
