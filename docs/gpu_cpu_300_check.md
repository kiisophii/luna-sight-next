# Southern 948 m GPU versus original CPU check

**All 300 requested latitude-stratified cells pass the 0.5 percentage-point threshold. A second, disjoint 300-cell GPU-only cohort also passes.** At identical float32 storage precision, all three metrics match exactly at all 600 cells. This demonstrates implementation consistency, not absolute physical accuracy.

## Scope and provenance

- Assigned rows: **3103–5759 inclusive** (`3103:5760`), 32 pixels/degree, 11,520 columns. Pixel centres: `lat = 90 - (row + 0.5)/32`, `lon = -180 + (col + 0.5)/32`, MOON_ME.
- The delivered shard contains **352 preserved CPU rows (3103–3454)** and **2,305 GPU rows (3455–5759)**. The requested sample contains 247 GPU and 53 CPU cells; the supplementary sample contains 300 GPU cells. There are 600 unique cells, including 547 GPU cells.
- Recomputed with the **unchanged original CPU `pipeline/global_maps.py`**. No CUDA code, copied metric formula or GPU-produced horizon mask enters the CPU reference. Its SHA256 matches the original run at [a526acf](https://github.com/kiisophii/lunar-landing-site-navigator/blob/a526acfc30b60176e50a7553ce44c78172bcc85d/pipeline/global_maps.py). Current horizon.py and ephemeris also match original input hashes.
- LDEM_64 to 150 km; LDEM_16 to 300 km; 360 azimuths; 283 radial samples; lunar curvature; 2 m observer; solar radius 0.2666 degrees. Production 2026–2030 ephemeris at **3 h**, 14,608 samples. The older contract proposal's 2 h default was not substituted.
- Every delivered output file and original input was SHA256-checked against the handoff manifest before sampling. Store opened read-only; production data unchanged.
- [Summary, seeds, strata, signatures and hashes](gpu_cpu_300_check.json); [every sampled cell and difference](gpu_cpu_300_cells.csv); [exact reproduction script](gpu_cpu_300_reproduce.md).
- Sources already recorded in [DATASETS.md](../data/DATASETS.md): [LOLA PDS](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/) and [NAIF kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/).

## Definitions and results

Original global-map definitions are preserved: **sun = mean visible solar-disc fraction**; Earth = fraction of samples with Earth's centre above the horizon; both = fraction with solar-disc fraction >= 0.5 AND Earth visible. Site-level core.js `sun_frac` in the near-field table instead counts hours classified as sunlit (>= 0.5). These quantities and their 3 h versus 1 h sampling must not be conflated. Matching the CPU does not validate a change of scientific definition.

`abs_diff_pp = 100 * abs(stored_float32_fraction - unrounded_CPU_fraction)`. The table does not round these differences to zero. A separate check casts the CPU result to the same float32 storage precision.

| Cohort | Metric | Maximum absolute difference (%p) | Mean absolute difference (%p) | Max with same float32 storage (%p) |
|---|---|---:|---:|---:|
| Assigned 300 | sun | 2.358203388e-6 | 6.851588043e-7 | 0 |
| Assigned 300 | earth | 2.957382705e-6 | 3.055386214e-7 | 0 |
| Assigned 300 | both | 2.539562627e-6 | 3.071390344e-7 | 0 |
| GPU-only 300 | sun | 2.593857940e-6 | 6.808081327e-7 | 0 |
| GPU-only 300 | earth | 2.898626761e-6 | 2.548400250e-7 | 0 |
| GPU-only 300 | both | 2.480806682e-6 | 2.894156731e-7 | 0 |

**Cells exceeding 0.5 pp: none** in either cohort. All CPU results were finite with zero missing terrain samples. Residuals disappear at identical storage precision, consistent with float32 rounding.

## Latitude-stratified random sampling

Uniform random row/column cell draws within each stratum, without replacement; NumPy PCG64. Seeds `202611143001` (assigned) and `202611143002` (GPU-only). The second cohort excludes cells already selected in the first. This is a fresh sample; the prior 42-point external check was not available for overlap analysis.

| Latitude band (south) | Assigned rows [start, stop) | Assigned count | GPU-only rows [start, stop) | GPU-only count |
|---|---|---:|---|---:|
| ~7–10 degrees | 3103:3200 | 30 | No GPU rows | 0 |
| 10–20 degrees | 3200:3520 | 30 | 3455:3520 (~18–20 S) | 30 |
| 20–30 degrees | 3520:3840 | 30 | 3520:3840 | 30 |
| 30–40 degrees | 3840:4160 | 30 | 3840:4160 | 30 |
| 40–50 degrees | 4160:4480 | 30 | 4160:4480 | 30 |
| 50–60 degrees | 4480:4800 | 30 | 4480:4800 | 30 |
| 60–70 degrees | 4800:5120 | 30 | 4800:5120 | 30 |
| 70–80 degrees | 5120:5440 | 30 | 5120:5440 | 30 |
| 80–85 degrees | 5440:5600 | 30 | 5440:5600 | 45 |
| 85–90 degrees | 5600:5760 | 30 | 5600:5760 | 45 |
| Total | | **300** | | **300** |

The 80–90 S region contains **60 requested and 90 supplementary cells**. Exact latitude centres and selected longitudes are in the CSV/JSON. These deliberately stratified means are sample means, not area-weighted global errors. Unsampled cells are not guaranteed correct by this audit.

## Five-site near-field comparison

The existing five-site calculation was rerun for this PR: [comparison table and limitations](near_field_check.md), [refreshed numerical evidence](near_field_check.json). Production baselines still match. Native terrain is approximately 59 m SLDEM; starting rays at 5 m does not create 5 m DEM resolution.

All five sites and their entire 300 m discs are outside the four broadest original north/south Sun/Earth PGDA AVGVISIB raster rectangles. Original PDS labels were fetched again successfully with identical hashes: [retrieval evidence](near_field_labels_recheck.json). **Direct PGDA centre and min/max values are unavailable**, so neither method can be ranked against PGDA here. This is a coverage limitation, not a failed download or a zero value.

No isolated positive-spike candidates were found under the documented native-pixel heuristic. This does not prove real relief or rule out correlated DEM errors, negative spikes or unresolved terrain; an independent higher-resolution elevation reference is required for that distinction.

## Verification and runtime

- Six CPU threads; original input/output hashing, engine setup and **600 fresh point recomputations took 2.980 s** with cached Numba compilation. This is a sample audit, not a repeat of the full grid. Near-field rerun: **9.594 s**.
- `python -m pytest pipeline/test_global_maps.py pipeline/test_near_field_check.py -q`: **9 passed**, two existing Rasterio deprecation warnings.
- Per-cell records, sampling, percentage-point arithmetic, original input hashes and original PGDA footprints are retained for separate review. Reproduction uses resumable 30-cell batches in ignored diagnostic storage.
- [Separate-session review](gpu_cpu_300_review.md) passed: independent sample/arithmetic reconstruction, 12 direct CPU recomputations, all input/output hashes, fresh original labels, independent stereographic coverage checks and all 151 native supporting/observer pixels. No blocking findings; human sign-off remains pending.
