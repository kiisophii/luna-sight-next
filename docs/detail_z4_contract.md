# Proposed detail Z4 contract — nearest historical landings

`web/data/detail/history.json`, written by `python pipeline/detail_history.py`.
The specific Z4 task requests one aggregate file rather than per-site files/index.
This optional product does not modify existing catalogue coordinates or other products.

| Field | Definition |
|---|---|
| `schema_version`, `product`, `mock` | `1`, `nearest_historical_landings`, `false` |
| `radius_m`, `frame` | `1737400`, `MOON_ME_DE421`; coordinates follow the catalogue/Task R conventions |
| `nearest_count`, `site_count`, `mission_count` | `3`, `33`, `18` for the current inputs |
| `reference_utc` | `2026-11-15T00:00:00Z`; only actual CSV landings on/before this instant are candidates |
| `distance_definition`, `bearing_definition`, `tie_break`, `caveat` | Human-readable method and limitations; must remain attached when displaying this product |
| `missions[]` | Unique `id`, catalogue `name`, Task R `lat`, `lon`, `landing_utc`, `coordinate_source`, `time_source`, `note`, plus `official_source_url`, `official_source_agency` |
| `sites[]` | Catalogue `id`, `lat`, `lon`, and `nearest[]` |
| `nearest[]` | Three distinct other mission IDs; each has `rank` 1–3, `id`, finite `distance_m` in [0, pi*radius_m], `bearing_deg`, `bearing_status`, `official_source_url` |
| `bearing_status` | `defined`, `coincident`, `antipodal`, or `origin_pole` |
| `bearing_deg` | Finite [0,360) when defined; otherwise `null` |
| `provenance` | `sha256_normalization:"CRLF_to_LF"`, `inputs:[{path,sha256}]`, `generated_utc`, `elapsed_s`, `workers:1` |

Distances are shortest great-circle arcs on the reference sphere, calculated by
haversine with the argument clipped into [0,1]. Heights and intervening terrain
do not enter. Initial bearing uses `atan2(east,north)` at the query point.
Coincident and antipodal detection use an angular tolerance of 1e-14 radians;
coincident distances within this tolerance are stored as zero. At an exact
geographic pole, true north is singular and the initial bearing is null.

Sorting uses unrounded computed distance, then lexicographic mission ID for exact
ties. All 33 catalogue sites are queries, including planned sites. Candidates
are exclusively the 18 actual Task R landers. Matching IDs are excluded even if
catalogue and Task R coordinates differ. Catalogue `future`, `custom`,
`artemis3_region`, and `polar_peak` IDs cannot enter the candidate pool; a matching
CSV row fails the build. No filter is made relative to the query site's own
landing date: “historical” is evaluated at the fixed reference date.

The official mission URL provides mission context. It does not supersede the
CSV coordinate/time source or resolve recorded source disagreements. In
particular Blue Ghost 1 remains `(18.562,61.81)` from Task R. Numbers stored with
floating-point precision do not claim corresponding geolocation accuracy.
Historical proximity is not evidence of usable infrastructure, accessibility,
traversable route length, or an exhaustive inventory of lunar landers.

## Suggested optional checks for the shared checker

When the aggregate file exists: validate schema/constants/counts, the exact
catalogue ID set and coordinates, unique actual mission IDs and CSV coordinates,
three distinct other IDs per query, rank order, finite distance/bearing ranges,
null/status correspondence, candidate date eligibility, official URL agreement
between missions and nearest records, and normalized input hashes. Full geometry
and nearest-order verification should independently recompute all eligible
distances (not only the three exported records). Team verification still needs
a different person to recompute at least three sites with their own code and
distance agreement <=1%; AI author checks do not satisfy that requirement.
