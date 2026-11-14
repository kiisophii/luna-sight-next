# South-polar 250 m neighbourhood grids

Owner: Jiyong. Task started 2026-11-14 23:57 KST on branch `s3-local250-jiyong`, from main `a060ece`.

## Scope and method

Sixteen catalogue points south of 75° S; priority order is SHACKLETON_RIM, ARTEMIS_HAWORTH, ARTEMIS_MALAPERT, CONNECTING_RIDGE, followed by the other south-polar catalogue sites. Each grid has 41×41 nodes across ±5 km at 250 m spacing: 1,681 nodes per site, 26,896 total. Grid spacing is not terrain resolution. `web/data/local/` is unchanged; new complete files go only to `web/data/local250/`.

Uses card18's actual computation in `local_maps.py` (`local_impact.py` is its reporting layer): card8 PGDA 5/10/20/60/80/240 m chain with original 3/25/25/60/60/200 km observer-centred gates, global LDEM64/16 fallback to 300 km, curvature, 2 m observer, 720 azimuths and 8,001 geometric samples from 5 m to 300 km. Expanded windows are storage envelopes only. Real source coverage gaps fall through to the next original source; no synthetic extension. Actual unchanged `core.js` computes all four hourly metrics over 43,824 hours, 2026–2030, from the usual 4-decimal-degree horizon records.

## GPU selection and validation policy

The previous 948 m CUDA kernel supports a different global-DEM chain and is not used here. The new optional FP64 polar horizon adapter preserves CPU equations, source selection, 128-distance early-stop blocks and input values. Original float32 heights remain lossless; the adapter rejects any float64-to-float32 conversion that would change them. Metrics are not ported to CUDA.

Initial eight-point Shackleton spike (centre, corners, edges, nearby offsets): CPU horizons **4.3608 s**, GPU horizons **0.1117 s**, actual core metrics **0.0952 s for eight nodes**. This is one-CPU-thread versus GPU, not a measured all-core speedup; initialization is excluded from these kernel comparisons. All eight rounded masks and four metrics matched exactly. Largest unrounded angle difference was about **8.14e-10°**. Final end-to-end site runtimes and per-site checks are recorded below.

Before each site, compare centre + four corners against `horizon.py`: angle max <1e-6°, height <1e-6 m, actual four core metrics exactly equal, sample counts and source-distance summaries equal. The freshly computed centre must exactly equal the production metrics file. GPU batches are capped at 16 nodes and each launch handles at most 128 distances, keeping individual display-GPU jobs short.

## Resource use, progress and resumption

Desktop: Ryzen 5 5600X (6 physical/12 logical CPUs), RTX 5060. Windows reports AC power connected, no battery; high-performance power plan, automatic sleep and hibernate timeouts both 0 (never). The process additionally requests system-awake while running. CPU affinity reserves **two physical cores including their SMT siblings**, leaving 4 physical/8 logical CPUs available. GPU coordination/metrics normally needs far fewer CPU resources than the CPU fallback.

Each node is atomically checkpointed with source/code/ephemeris/grid input identity. Changed input identities invalidate old nodes; no incomplete public site file is exported. A process lock prevents two run writers. `data/processed/local250/progress.json` and the redirected run log contain counts, throughput and ETA. Completed source windows are reused through hard links; GPU execution keeps terrain in memory instead of duplicating expanded float64 rasters on disk. A short initial trial was stopped to remove verified duplicate task-only cache files, preserving original caches and existing maps; changed runner hashes forced fresh computation under the final implementation.

```powershell
python pipeline/local250.py run --source-root <checkout-with-card18-caches> --backend gpu --jobs 8
python pipeline/local250.py verify --source-root <checkout-with-card18-caches>
python -m pytest pipeline/tests/test_local250.py pipeline/tests/test_card8_horizons.py pipeline/tests/test_fetch_polar.py -q
```

GPU environment additionally requires CuPy/CUDA; CPU mode uses `--backend cpu`. Downloads use the existing validated PGDA HTTP Range/block-cache reader with 4 connections. For numerical verification, five fixed-seed random nodes are independently re-marched through the separate PROJ/ECEF brute-force card18 verifier and independent hourly loop. Fractions must agree within 1 pp; dark-run differences are reported explicitly. Verification also checks source set/gates/input hashes and records output/verifier hashes. A source/code change cannot silently certify old output. Hashes identify exact execution bytes, including text line endings; resumption invalidates checkpoints if those bytes change.

## Completion evidence

All **16 sites / 26,896 nodes** completed with no resumed nodes in the final run. Priority order was preserved. All 16 centres exactly match the four production metrics. The final run started **2026-11-15 00:08:35 KST**; all grids were complete at **00:36:27**, and independent verification finished at **00:37:41**.

| Phase | Wall time |
|---|---:|
| All 16 sites, including missing terrain downloads, preparation, CPU preflights and export | 27 min 52.2 s |
| Input/source checks and five independent brute-force nodes | 1 min 14.7 s |
| Final run through independent verification | **29 min 6.8 s** |

These timings exclude earlier implementation/benchmarking and the interrupted initial trial. End-of-site GPU plus actual-core throughput was approximately 38–44 nodes/s. Downloads explain most of the per-site variation below. The first four sites finished within 3 min 53 s of the final run's start.

| Site (execution order) | Nodes | Site wall time, including preparation/downloads (s) |
|---|---:|---:|
| SHACKLETON_RIM | 1,681 | 64.24 |
| ARTEMIS_HAWORTH | 1,681 | 57.51 |
| ARTEMIS_MALAPERT | 1,681 | 53.75 |
| CONNECTING_RIDGE | 1,681 | 57.48 |
| IM1 | 1,681 | 90.83 |
| IM2 | 1,681 | 114.97 |
| ARTEMIS_CABEUS_B | 1,681 | 147.96 |
| ARTEMIS_MOUTON_PLATEAU | 1,681 | 84.82 |
| ARTEMIS_MOUTON | 1,681 | 108.63 |
| ARTEMIS_NOBILE_RIM1 | 1,681 | 91.30 |
| ARTEMIS_NOBILE_RIM2 | 1,681 | 133.30 |
| ARTEMIS_DE_GERLACHE_RIM2 | 1,681 | 138.59 |
| ARTEMIS_SLATER_PLAIN | 1,681 | 223.53 |
| PEAK_NEAR_SHACKLETON | 1,681 | 59.16 |
| DE_GERLACHE_RIM1 | 1,681 | 58.85 |
| SHOEMAKER_RIM_A | 1,681 | 184.55 |

### Numerical and regression checks

| Check | Result |
|---|---|
| GPU vs original CPU: centre + four corners at every site | **80/80 nodes**: stored masks and all four metrics exactly equal; sample counts/source summaries also equal |
| Maximum unrounded CPU/GPU horizon difference | **8.30e-10 degrees** |
| Centre vs existing production metrics | **16/16 exact**, all four metrics |
| Existing 1 km grid at shared coordinates | **1,936/1,936 exact**, all four metrics; original `local/` files unchanged |
| Independent PROJ coordinate reconstruction, all nodes | Maximum displacement **9.27e-8 m**, below 1 mm |
| Independent brute-force horizon + independent hourly loop | **5/5 pass**; maximum fraction difference **0.002281855 pp** vs 1 pp criterion |
| Independent longest-dark comparison | **0 hours** difference at all five nodes |
| Targeted Python tests | **21 passed**: local250, card8 horizon and polar-download tests |

The independent verifier uses full unrounded horizons. At SLATER_PLAIN node 554, the Sun/both classification differs by one hourly sample out of 43,824, or 0.002281855 pp. Re-rounding the independently traced masks to the production four-decimal-degree storage precision makes **all 720 mask entries and all four metrics exactly equal at all five nodes**. Thus this residual is the existing horizon storage quantization, not a GPU/CPU metric discrepancy. The unrounded independent comparison is retained in the report rather than replaced by the rounded result.

| Independent sample (seed 202611150250) | Index | Sun abs diff (pp) | Earth abs diff (pp) | Both abs diff (pp) | Dark abs diff (h) |
|---|---:|---:|---:|---:|---:|
| ARTEMIS_MOUTON_PLATEAU | 1084 | 0.000000000 | 0.000000000 | 0.000000000 | 0 |
| IM1 | 961 | 0.000000000 | 0.000000000 | 0.000000000 | 0 |
| ARTEMIS_SLATER_PLAIN | 1003 | 0.000000000 | 0.000000000 | 0.000000000 | 0 |
| ARTEMIS_MOUTON | 298 | 0.000000000 | 0.000000000 | 0.000000000 | 0 |
| ARTEMIS_SLATER_PLAIN | 554 | 0.002281855 | 0.000000000 | 0.002281855 | 0 |

Evidence: [runtime, 80 preflights, original-grid regression and rounding diagnostics](local250_runtime.json), [independent five-node check with masks, source checks and hashes](local250_check.json). Separate AI code review and a read-only final release audit found no important issue; the audit also verified 101 unique source/label/code/ephemeris file hashes. All results remain subject to human review in the SI log.

Execution used Python 3.10.2, `cupy-cuda12x` 14.2.0, NVIDIA driver 610.88 on the desktop above. No scientific production file or existing map was changed. This PR supplies the new data product and contract proposal; selecting `local250/` in the UI is integrator work.


Sources: [NASA PGDA polar DEMs](https://pgda.gsfc.nasa.gov/products/90), [LOLA global DEMs](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/), the existing production NAIF-derived ephemeris, [dataset provenance](../data/DATASETS.md) and [contract sections15/22](data_contract.md). Exact source hashes are retained per output. Numerical equivalence tests do not establish absolute DEM or mission-design accuracy.
