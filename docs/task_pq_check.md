# Task P/Q — complete independent windows and monthly recomputation

**PASS.** Jiyong Sung independently recomputed all **33/33 sites**, **3,022 Sun + 969 Earth visible intervals**, **472 published longest-gap records**, and **1,980/1,980 site-months**. All compared numerical values equal the production serialization. All counts, edges, durations, clipping flags and structural checks satisfy their criteria. No missing or extra intervals.

Input Git HEAD: `30861435db18baa0c85c226638712741a4a8bd55`. Run: `2026-11-15T00:05:45.036117+00:00`; CPU checking/evidence time **1.714 s**. Single process, NumPy FP64 with BLAS/OMP threads fixed to 1; no GPU. 0/33 sites resumed from content-hashed independent state caches.

## Method and scope

P producer: Minchul (card 15-B). Q producer: Sua (monthly seasons). Jiyong did not produce either product. The checker imports only Python standard-library modules and NumPy; it does not import or execute any production module. It copies the definitions from `web/js/core.js` and `docs/data_contract.md` into a separate implementation. Both producing scripts were read to identify the complete stored scope.

The checker reads the little-endian float32 ephemeris, promotes to float64, subtracts the observer at 1737.4 km + terrain height + 2 m for both bodies, projects onto local east/north/up, and interpolates the cyclic 0.5-degree stored mask. Sunlit means the visible circular solar-disk fraction (radius 0.2666 degrees) is at least 0.5; Earth centre is strictly above the mask. Each site has 43,824 hourly samples from 2026-01-01 through 2030-12-31.

P compares every maximal visible run, visible-hour total, and all published top-ten longest gaps, sorted by duration descending/start ascending. Intervals are half-open one-hour bins with domain clipping; the last bin ends 2031-01-01. **The 2-minute edge tolerance checks stored hourly-bin boundaries, not physical or sub-hour rise/set accuracy.** All complement runs are recomputed to select the published longest gaps.

Q compares all 60 UTC calendar months per site, including leap February, hours/Sun/Earth/both counts and fractions, longest darkness cut at the month boundaries, all three 709-hour month-centred lunation fractions, the four subsolar/subearth latitude min/max series, and all five-year totals. Subbody latitude uses the Moon-centred vector. JavaScript rounding (floor(x * scale + 0.5), including negative latitude ties) is applied only to the separately recorded serialized expectation; thresholds use the unrounded independent value.

This is full implementation agreement on the **existing ephemeris and stored horizons**. It does not validate the kernels or terrain against the real Moon, recompute horizons from DEMs, establish physical error bounds, or change the scope of other ledger products.

## Measured differences

Signed difference = stored minus independent unrounded value. Raw residuals below are the retained finite-decimal serialization differences. Every original and recomputed value is in the full CSV; no failure or small discrepancy is rounded away.

| Product/value | Values | Raw max absolute | Raw median absolute | Raw signed min / max | Serialized max / median | Criterion |
|---|---:|---:|---:|---:|---:|---:|
| P interval edges (min) | 8,926 | 0 | 0 | 0 / 0 | 0 / 0 | <= 2 |
| P durations/totals (h) | 4,529 | 0 | 0 | 0 / 0 | 0 / 0 | <= 1 |
| Q monthly/lunation/total fractions (pp) | 11,979 | 0.005 | 0.00173483779972 | -0.00496473906911 / 0.005 | 0 / 0 | <= 0.1 |
| Q latitude extrema (deg) | 7,920 | 0.000498162080848 | 0.000263335699816 | -0.000498162080848 / 0.000497630146986 | 0 / 0 | <= 0.05 |
| Q hour counts/durations (h) | 9,966 | 0 | 0 | 0 / 0 | 0 / 0 | <= 1 |

All **58,301 comparison records** pass. Scientific/structural failures: **0**; serialized numerical mismatches: **0**.

## Provenance byte differences retained

There are **66 raw source-hash differences**, recorded individually in [the provenance table](task_pq_provenance_differences.csv). P stored LF hashes for `core.js` and `build_windows.mjs`; this Windows checkout has CRLF. Converting only CRLF to LF reproduces each recorded source hash exactly. No code/content differences are waived. All ephemeris, metadata, site-object and horizon hashes match exactly. The full source manifest preserves the actual checkout bytes for every input and the checker itself; hashes are rechecked after computation. These byte differences are provenance notes, not numeric failures.

## All-site table

| Site | Sun intervals | Earth intervals | Longest gaps (Sun/Earth) | Months | Q raw fraction max (pp) | Q raw angle max (deg) | Duration/edge max | Status |
|---|---:|---:|---:|---:|---:|---:|---|---|
| APOLLO11 | 63 | 1 | 10/0 | 60 | 0.005 | 0.000498162080848 | 0 h / 0 min | PASS |
| APOLLO12 | 62 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| APOLLO14 | 62 | 1 | 10/0 | 60 | 0.00469675599436 | 0.000498162080848 | 0 h / 0 min | PASS |
| APOLLO15 | 62 | 1 | 10/0 | 60 | 0.00486600846262 | 0.000498162080848 | 0 h / 0 min | PASS |
| APOLLO16 | 63 | 1 | 10/0 | 60 | 0.005 | 0.000498162080848 | 0 h / 0 min | PASS |
| APOLLO17 | 63 | 1 | 10/0 | 60 | 0.00486600846262 | 0.000498162080848 | 0 h / 0 min | PASS |
| LUNA16 | 63 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| LUNA20 | 63 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| LUNA24 | 63 | 1 | 10/0 | 60 | 0.00494623655913 | 0.000498162080848 | 0 h / 0 min | PASS |
| CHANGE3 | 62 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| CHANGE4 | 62 | 0 | 10/1 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| CHANGE5 | 62 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| CHANGE6 | 62 | 0 | 10/1 | 60 | 0.00494623655913 | 0.000498162080848 | 0 h / 0 min | PASS |
| CHANDRAYAAN3 | 63 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| SLIM | 63 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| IM1 | 62 | 1 | 10/0 | 60 | 0.00479548660084 | 0.000498162080848 | 0 h / 0 min | PASS |
| IM2 | 75 | 68 | 10/10 | 60 | 0.00496473906911 | 0.000498162080848 | 0 h / 0 min | PASS |
| BLUE_GHOST1 | 63 | 1 | 10/0 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_CABEUS_B | 84 | 68 | 10/10 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_HAWORTH | 179 | 68 | 10/10 | 60 | 0.005 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_MALAPERT | 62 | 1 | 10/0 | 60 | 0.00496473906911 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_MOUTON_PLATEAU | 63 | 68 | 10/10 | 60 | 0.00494623655914 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_MOUTON | 133 | 68 | 10/10 | 60 | 0.00495063469677 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_NOBILE_RIM1 | 101 | 68 | 10/10 | 60 | 0.00494623655913 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_NOBILE_RIM2 | 84 | 68 | 10/10 | 60 | 0.00496473906911 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_DE_GERLACHE_RIM2 | 96 | 68 | 10/10 | 60 | 0.00496473906911 | 0.000498162080848 | 0 h / 0 min | PASS |
| ARTEMIS_SLATER_PLAIN | 125 | 68 | 10/10 | 60 | 0.005 | 0.000498162080848 | 0 h / 0 min | PASS |
| SHACKLETON_RIM | 226 | 68 | 10/10 | 60 | 0.00496473906911 | 0.000498162080848 | 0 h / 0 min | PASS |
| CONNECTING_RIDGE | 108 | 68 | 10/10 | 60 | 0.005 | 0.000498162080848 | 0 h / 0 min | PASS |
| PEAK_NEAR_SHACKLETON | 186 | 68 | 10/10 | 60 | 0.00497884344147 | 0.000498162080848 | 0 h / 0 min | PASS |
| DE_GERLACHE_RIM1 | 199 | 68 | 10/10 | 60 | 0.005 | 0.000498162080848 | 0 h / 0 min | PASS |
| SHOEMAKER_RIM_A | 176 | 68 | 10/10 | 60 | 0.00496473906911 | 0.000498162080848 | 0 h / 0 min | PASS |
| IM3_REINER_GAMMA | 62 | 1 | 10/0 | 60 | 0.00469675599436 | 0.000498162080848 | 0 h / 0 min | PASS |

## Evidence and reproduction

- [Run summary, every source hash, and mismatch lists](task_pq_check.json)
- [Every scalar/structural comparison, including all intervals and min/max](task_pq_comparisons.csv)
- [All 1,980 month rows](task_pq_months.csv)
- [All threshold failures (header only when none)](task_pq_failures.csv)
- [All raw source-hash differences](task_pq_provenance_differences.csv)

From the repository root, using the NumPy environment:

```powershell
$py = "C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe"
& $py -m unittest discover -s pipeline/tests -p test_task_pq.py
& $py pipeline/task_pq_check.py
& $py pipeline/task_pq_report.py
```

Use `--resume` on the checker to reuse independently generated hourly state caches. Cache fingerprints include the full ephemeris, site list, horizon and checker bytes; packed-state payload hashes are checked before reuse. The default command always recomputes every state. Runtime caches/progress markers need not be committed. The checker overwrites prior PASS state with RUNNING before opening inputs and exits nonzero on error/incompleteness. The report refuses changed source/evidence hashes, incomplete coverage or failed checks. Production files are unchanged.
