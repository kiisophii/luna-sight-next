# Task X — 250 m neighbourhoods for all 17 nonpolar catalogue sites

Jiyong Sung, OpenAI Codex-assisted, 2026-11-15. No existing polar local250 or local/ file is changed.

**17 × 1,681 = 28,577 nodes** over ±5 km east/north, 250 m spacing. All 17 centre nodes equal their production metrics exactly. The new discovery index lists all 33 complete site maps, including the unchanged 16 polar maps.

Index SHA256 normalizes CRLF to LF before hashing (`sha256_normalization: CRLF_to_LF`) so it remains valid on Windows and GitHub Pages. Scientific provenance/evidence retains actual execution-byte hashes.

## Definitions and source coverage

Card9/card20 nonpolar definitions are preserved: 720 azimuths; 4,001 geometric distances from 200 m to 300 km; lunar curvature; observer 2 m; SLDEM2015 512 ppd (~59 m) within 150 km, followed by LDEM_64/16. CHANDRAYAAN3 is outside SLDEM coverage and uses the production global fallback. No 5 m near-field extension is introduced. Source NPZ windows are expanded to 166 km to cover the entire shifted footprint; their radial application gate remains centred on each node. Core.js receives the same 4-decimal-degree mask and 2-decimal-metre ground serialization, then evaluates all 43,824 hourly samples in 2026–2030.

Fractions use the core sunlit threshold (at least half the solar disk), Earth centre visibility, and their conjunction. Longest darkness is a non-wrapping hourly run. Geometric Earth visibility is not a guaranteed radio link or station availability. Grid spacing is not DEM resolution.

## Per-site checks

| Site | New nodes | Shared 1 km nodes | Max shared fraction difference (pp) | Median abs fraction difference (pp) | Max dark difference (h) |
|---|---:|---:|---:|---:|---:|
| CHANDRAYAAN3 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| APOLLO11 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| APOLLO12 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| APOLLO14 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| APOLLO15 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| APOLLO16 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| APOLLO17 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| LUNA16 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| LUNA20 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| LUNA24 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| CHANGE3 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| CHANGE4 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| CHANGE5 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| CHANGE6 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| SLIM | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| BLUE_GHOST1 | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |
| IM3_REINER_GAMMA | 1681 | 121 | 0.000000000 | 0.000000000 | 0 |

All 2,057 shared nodes compared; max fraction difference **0.000000000 pp**, dark **0 h**. All signed differences remain in [overlap CSV](task_x_overlaps.csv); no failed row is discarded.

## Radius statistics

The [radius CSV](task_x_radii.csv) reports min/max/Q1/Q3/IQR of all four metrics per site. **1/3/5 km discs use the new 250 m nodes. 10 km discs use the existing 1 km nodes, explicitly labelled spacing_m=1000.** A ±5 km square cannot measure a complete 10 km disc; no extrapolation or mislabeled 10 km fine-grid statistic is provided. Fractions are stored as 0–1; multiply fraction differences by 100 for percentage points. The square corners extend to 7.071 km and are retained in the map.

## Numerical validation and runtime

CPU production versus FP64 CUDA: centre + four corners for every site (**85 points**), all metric dictionaries exactly equal. Summed horizon timings CPU **23.46 s**, GPU **0.44 s** (small batches, not an end-to-end speedup). No fast math; 128-distance CUDA launches bound display-GPU work. Recorded per-site angle differences and metric equality are in [results](task_x_results.json). The runner additionally asserts matching sample counts and DEM-source records during each preflight.

Separate CPU full-ray geometry and independent time loop: [developer check](task_x_check.json), five random nodes each from APOLLO17, CHANGE4 and CHANDRAYAAN3: max fraction difference **0.000000000 pp**, longest-dark difference **0 h**, across both unrounded and serialized comparisons. This is a developer check organized by Jiyong, **not the task-required independent sign-off by another team member**; that sign-off remains for Sua/the team before merge. Same-input agreement does not establish absolute physical accuracy.

Full invocation wall time **977.2 s**, including source waits, CPU/GPU preflights, core.js, checkpoint writes and exports. Downloading began earlier in parallel. 16 nodes resumed from the initial pilot; that pilot is excluded from this invocation time. P/Q ran independently on CPU during X. Two physical cores were reserved; GPU batches contain at most 16 nodes. Per-node input fingerprints support restart; only complete site maps are published.

## Reproduce

```powershell
python pipeline/task_x_fetch.py
python pipeline/task_x.py
python pipeline/task_x_verify.py
python pipeline/task_x_report.py
python -m pytest pipeline/tests/test_task_x.py pipeline/tests/test_local250.py -q
python pipeline/check_contract.py
```

Fetch can run concurrently with the GPU runner; it waits for each complete source NPZ. Use the existing LDEM64/16 raw IMG+LBL files under data/processed/local250/raw/global. GPU execution needs CuPy/CUDA; acquisition uses requests, NumPy and optional truststore. Production per-site provenance includes raw/code/ephemeris hashes and source URLs. Raw data and per-node checkpoints remain ignored. A checkout with CRLF may require LF normalization of the unchanged core.js/build_windows.mjs when checking historical windows provenance; report raw and normalized check results separately.

Sources: [SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [LOLA global floats](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/), [NAIF ephemeris](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/), [source register](../data/DATASETS.md).
