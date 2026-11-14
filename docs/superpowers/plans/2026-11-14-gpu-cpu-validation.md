# GPU/CPU validation documentation plan

**Goal:** Document a fresh latitude-stratified 300-cell CPU comparison of the delivered 948 m southern shard and the five-site near-field comparison. User requests a docs-only PR; do not modify production horizons, metrics, GPU outputs or pipeline code.

**Method:** Use the unchanged original `pipeline/global_maps.py` Engine.points on the same DEMs/ephemeris/settings. The shard retains 352 CPU rows, so add a separate 300-cell GPU-only cohort. Use fixed seeds, no replacement, explicit pixel centres, 3 h ephemeris, six CPU threads and resumable diagnostic batches. Report unrounded CPU versus stored float32 in percentage points, plus equal-storage-precision comparison. Save per-cell evidence, input hashes, sampling strata and a runnable reproduction block in docs.

**Review focus:** row stop 5760 is exclusive; southern 80–90 degree coverage; CPU-preserved rows must not be labelled GPU; fractions convert to percentage points by multiplying by 100; implementation agreement does not establish physical accuracy.

- [x] Hash inputs against original run, confirm output file integrity and unchanged CPU source.
- [x] Recompute both fixed-seed cohorts; aggregate max/mean absolute differences and all cells exceeding 0.5 pp.
- [x] Rerun existing five-site near-field document generator; validate original PGDA label footprints, native-pixel diagnostic limits and unchanged production baselines.
- [x] Review evidence independently, append SI log and verify docs-only diff. PR submission follows these completed checks.

Final review: separate-session review passed (docs/gpu_cpu_300_review.md). The requested PGDA numbers cannot exist outside the published raster footprint; missing values are retained as unavailable, with independently checked geometry rather than invented values. No production changes were made.

Pre-flight: the two numerical tasks share read-only DEM/ephemeris inputs, and neither consumes the other's outputs. Existing numeric code is reused; this is a verification/documentation task rather than a new production implementation.
