## Proposed detail PSR format (Task Z2; 2026-11-15, Jiyong)

`web/data/detail/psr/<ID>.json` for all 16 catalogue sites at latitude <= -80 degrees, plus `index.json`. Existing products are unchanged. Produced by `pipeline/detail_psr.py` from native full-resolution NASA PGDA `LPSR_80S_20MPP_ADJ.TIF` windows, never overview values.

Each site file has:

| Field | Definition |
|---|---|
| `schema_version`, `id`, `lat`, `lon`, `mock` | Version 1, catalogue identity/coordinates; mock=false |
| `inside_psr` | true/false for the native pixel containing the point; null if no-data/outside coverage. Half-open raster row/column addressing on pixel boundaries. |
| `site_class` | 1=PSR, 0=not PSR, null=unknown |
| `nearest_pixel_center` | null if no PSR center found within radius; otherwise `{lat,lon,x_m,y_m,distance_m,bearing_deg,nearest_guaranteed,row,col}`. Row/col are 0-based in the full native raster. |
| `nearest_boundary` | Same geographic/projected coordinate, distance, bearing and guarantee fields (without row/col), or null when no known 1/0 boundary found within radius. This is the boundary of the union of native pixel squares, inverse projected onto the sphere; internal class-1/class-1 edges, no-data interfaces and window edges are excluded. It is **not** the separately distributed interpolated vector contour. |
| `distance_to_psr_area_m` | Zero if inside; nearest known boundary distance if outside; null for unknown site classification or no known boundary. Consult the boundary guarantee flag for completeness. |
| `distance_lower_bound_m` | Search radius only when complete coverage finds neither PSR center nor boundary and the site is outside PSR; otherwise null. Display `> radius`, never a guessed nearest distance. |
| `status` | `found`, `none_within_radius`, or `incomplete_coverage`; found requires a guaranteed nearest PSR center (or boundary when no center is within radius). |
| `search` | `radius_m`, `complete_within_radius`, `unsearched_or_nodata_lower_bound_m`, `window_edge_lower_bound_m`, nullable `nodata_lower_bound_m`, `nodata_pixels`, `pixels`, `projection_max_scale`. No-data count is for the full fetched rectangle, not only the search disk. |
| `source` | Exact raster URL/product page/DOIs, HTTP ETag/Last-Modified/size, native shape/dtype/codes/no-data, CRS/frame/radius, native first pixel center, original GDAL metadata and original vector-polygon class cross-check. |
| `provenance` | Producer hash, native `[r0,r1,c0,c1]` exclusive-end window, first window center, little-endian float32 window SHA256 and ignored local cache path. Source codes observed exclude NaN. |
| `input_signature` | SHA256 over site coordinates, radius, source metadata, normalized producer and fetch-module hashes; stale results are recomputed. |
| `definitions`, `warning`, `verification` | Machine-readable explanations; warning is `PSR ≠ confirmed ice.`; independent team verification pending. |

Distances are shortest spherical surface geodesics on R=1737400 m, with inverse stereographic coordinates before computing distance. Initial bearing is north=0 clockwise in [0,360); bearing is null at a geographic pole or zero distance. No surface slope, terrain traverse feasibility, observer height or ice measurement is implied. Boundary distance is positive for a point strictly inside PSR, while distance **to the PSR area** is zero there.

`index.json` contains `schema_version:1`, `count:16`, `sites:[{id,file,status,sha256}]`, `source_url`, `warning`, `mock:false`, and an aggregate input signature. File hashes normalize CRLF to LF. A prior index is withdrawn before preflight; the replacement is atomically published only after all requested sites have completed. Each site JSON and cached window is also written atomically. Durable per-site checkpoints verify both input signatures and content hashes before resuming; cached class arrays carry a checked SHA256.

Search completeness is conservative: the requested projected rectangle encloses the entire 10 km spherical disk plus a two-pixel margin, then clips to source extent if necessary. Maximum stereographic scale over the fetched rectangle gives a lower bound to any unseen perimeter or no-data footprint. A nearest result is guaranteed only if its spherical distance is smaller than this bound. `complete_within_radius` requires the bound >= radius. Thus unknown data never become class 0 and cannot produce a false lower-bound claim. IM1's rectangle is clipped by the northern source edge: its entire 10 km search disk is not covered, but its nearest result is guaranteed because the candidate is much closer than the missing-data lower bound.
