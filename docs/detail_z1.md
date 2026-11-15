# Z1 — exact 2026–2030 time statistics

All 33 sites have complete 43,824-cell results in `web/data/detail/time_stats/`. The builder imports unchanged `web/js/core.js` and evaluates its predicates at every UTC hour. Existing `metrics/` fractions and longest dark run match exactly at every site. Existing `windows/` visible intervals, visible totals, top-10 gaps, and all associated clipping flags also match exactly at every site. Output totals use integers; means are unrounded JSON numbers.

| Site | Sunlit h | Earth h | Both h | Longest dark h | Longest sunlight h | KDSA h | >=1 station h | >=2 stations h |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| APOLLO17 | 20925 | 43824 | 20925 | 371 | 341 | 18213 | 43246 | 25717 |
| CHANGE4 | 21594 | 0 | 0 | 367 | 355 | 0 | 0 | 0 |
| SHACKLETON_RIM | 37174 | 21887 | 19441 | 75 | 2817 | 9986 | 21807 | 13940 |

Table source: the corresponding generated site JSON files, using the source hashes recorded in each file. Geometry inputs derive from [NAIF kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/) and the existing real terrain horizons documented in `data/DATASETS.md`. Station predicates come directly from `web/data/korea/stations.json`; coordinate sources are [NAIF/KARI KDSA01](https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf) and the [NASA DSN coverage handbook](https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf).

Observed runs touching either boundary are explicitly listed as `clipped_runs`; their full durations outside 2026–2030 are unknown. `count/mean_h/longest_h` summarize the observed parts, while `complete_*` exclude those runs. For CHANGE4 the no-Earth run spans the whole 43,824-cell period, is clipped at both ends, and has `complete_count:0, complete_mean_h:null`. APOLLO17 has no no-Earth runs, so `mean_h:null` and `longest_h:0`. These cases distinguish absent outages from unbounded observations. Station communication requires lunar Earth visibility as well as station Moon elevation >=10 degrees, and does not require sunlight.

Full recomputation took **0.6957492 s wall / 0.75 s CPU**, with **74.4921875 MiB peak RSS** on this workstation. One Node CPU worker was used; no BLAS or GPU computation. Validated resume took **0.0969594 s**, reused all 33 outputs, and checked current normalized-text input/output hashes. The archived full run is `docs/detail_z1_full_run.json`; latest resume is `docs/detail_z1_generation.json`. There were no failures. Published site JSON plus index total 85,353 bytes.

Reproduce from repository root:

```sh
node --test pipeline/detail_time_stats.test.mjs
node pipeline/detail_time_stats.mjs --force
node pipeline/detail_time_stats.mjs
python pipeline/check_contract.py
```

The five focused tests were written before their implementation/fix and observed failing, then passing. They cover complete/clipped run accounting, no-outage and whole-window cases, LSB-first byte boundaries with Earth gating, signature rejection, full real-data generation/resume, tampered-output repair, and failed-input unpublication. A failed or interrupted refresh cannot publish a partial index; per-site checkpoint hashes allow valid work to resume. Text hashes normalize CRLF to LF for checkout portability.

These are **author-side** checks. Independent recomputation by a different team member at three sites remains pending; another AI session reviewing or recalculating these outputs does not satisfy that team requirement. Full repository contract and broader suite results are recorded by the integration owner.
