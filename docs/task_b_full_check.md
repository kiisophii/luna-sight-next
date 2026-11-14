# Task B — full independent nonpolar coordinate-uncertainty check

Producer: Sua Kim. Checker: Jiyong Sung. Inputs: main `89a9af1`. No production data changed.

**17 sites / 2,057 nodes / 1,020 radius statistics recomputed. Fraction failures: 0.**

| Check | Measured result |
|---|---:|
| Maximum node fraction difference, matching production serialization | 0 pp |
| Maximum radius-statistic fraction difference | 0 pp |
| Maximum node fraction difference, unrounded independent horizons | 0.00228185469149 pp |
| Longest-dark difference, production-rounded / unrounded | 0 / 0 h |
| GPU vs separate CPU PROJ/ECEF controls | 34 nodes; maximum 1.68222547003e-10 degrees; all rounded metrics equal |
| Full-run wall time (includes source waits, initialization, controls and writing) | 438.62 s |

Task B criterion: each Sun/Earth/both fraction and radius statistic within 1 percentage point. Longest darkness is also recomputed and every difference retained; task B gives no darkness pass threshold. CSV fraction differences are in fraction units (multiply by 100 for pp); darkness differences are hours.

| Site | Nodes | Max Sun (pp) | Max Earth (pp) | Max both (pp) | Max dark (h) | Max unrounded fraction (pp) |
|---|---:|---:|---:|---:|---:|---:|
| APOLLO11 | 121 | 0 | 0 | 0 | 0 | 0 |
| APOLLO12 | 121 | 0 | 0 | 0 | 0 | 0 |
| APOLLO14 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| APOLLO15 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| APOLLO16 | 121 | 0 | 0 | 0 | 0 | 0 |
| APOLLO17 | 121 | 0 | 0 | 0 | 0 | 0 |
| LUNA16 | 121 | 0 | 0 | 0 | 0 | 0 |
| LUNA20 | 121 | 0 | 0 | 0 | 0 | 0 |
| LUNA24 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| CHANGE3 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| CHANGE4 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| CHANGE5 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| CHANGE6 | 121 | 0 | 0 | 0 | 0 | 0 |
| CHANDRAYAAN3 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| SLIM | 121 | 0 | 0 | 0 | 0 | 0 |
| BLUE_GHOST1 | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |
| IM3_REINER_GAMMA | 121 | 0 | 0 | 0 | 0 | 0.00228185469149 |

## Independent method and scope

- No repository modules are imported by the verifier. It has its own SLDEM NPZ/PDS label reader, bilinear sampler, Cartesian great-circle directions, full horizon march and NumPy hourly visibility loop.
- Every 11x11 grid is independently reconstructed with PROJ geodesics. All 720 azimuths and all 4,001 geometric distances (200 m to 300 km) are traced at every node without production early stopping. Observer height is 2 m; curvature is included.
- SLDEM2015 is used to 150 km from each node, then LDEM_64 and LDEM_16. CHANDRAYAAN3 uses the global chain. Fresh 151 km source windows cover offset observers. Their download metadata, URLs, server validators and hashes are in the evidence. Global raster hashes match the published provenance. Fresh NPZ container hashes differ from producer containers, which contain acquisition metadata; this report does not claim byte-identical producer NPZ archives.
- Source acquisition uses the existing fetch_global downloader only. The verifier does not call its reader or any production geometry. The same NASA source product is tested; this is not validation against the real lunar surface.
- Independent hourly predicates over all 43,824 samples: solar centre on/above the horizon (equivalent to half of the solar disk visible), Earth centre strictly above; both is their conjunction. Longest darkness is a non-wrapping run of false hourly bins.
- Both full-precision and production-serialized (4 decimal degree masks, 2 decimal metre ground) cases are retained. Production serialization is applied to independently computed values, never substituted from stored masks.
- All min/max/p10/median/p90 statistics are recalculated for 100/300/500 m discs (5/29/81 nodes). All 121 nodes, including those outside the 500 m disc, are recomputed and compared.
- GPU acceleration is CuPy FP64 array math. Centre and one corner at each site are additionally marched by a separate CPU PROJ/ECEF implementation. Two physical CPU cores are reserved; source/code/ephemeris/target hashes key each per-node checkpoint. Partial runs cannot overwrite the full evidence report.

## Evidence and reproduction

- [Full evidence, inputs, preflights and all failures](task_b_full_check.json)
- [All 2,057 node comparisons](task_b_nodes.csv)
- [All 1,020 radius-statistic comparisons](task_b_ranges.csv)

```powershell
python -X utf8 pipeline/fetch_global.py --skip-global --radius-km 151 --workers 4
python -X utf8 pipeline/task_b_full_check.py run --global-root <directory-with-original-LDEM64-and-LDEM16>
python -X utf8 pipeline/task_b_report.py
python -m pytest pipeline/tests/test_task_b_full_check.py -q
```

GPU execution needs CuPy/CUDA; `--backend cpu` provides an independent NumPy full-march path. Raw sources and node checkpoints stay git-ignored. Source hashes identify exact execution bytes, including line endings.

Sources: [NASA PDS SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [NASA PDS LOLA global floats](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/), [NAIF kernel archive](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/), [project source register](../data/DATASETS.md), [contract section 18](data_contract.md).

All numerical discrepancies, including those below tolerance, remain in the full CSV/JSON. No failed row is removed. Separate AI code review found one operational partial-report overwrite issue, fixed before the full run; human review remains TO CHECK in the SI log.
