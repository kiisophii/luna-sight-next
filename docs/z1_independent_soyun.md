# Z1 time statistics — independent three-site verification (Soyun Jeong)

Producer: Jiyong Sung (PR #80). Checker: Soyun Jeong, 2026-11-15. Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
Script: `pipeline/verify_z1_independent_soyun.py` (own code; no producer or earlier-checker module imported or run). Full results: `docs/z1_independent_soyun.json`. **No production file was changed.**

## Summary

| Item | Result |
|---|---|
| Sites (formal scope) | ARTEMIS_MALAPERT, ARTEMIS_CABEUS_B, CHANGE6 |
| Hourly cells per site | 43,824 (2026-01-01T00Z – 2030-12-31T23Z, each cell [i, i+1)); 131,472 for the three sites |
| Z1 fields compared (3 sites) | 108 (36 per site) |
| Fields failing the criterion | **0** |
| Fields not exactly equal | **0** |
| Max / median fraction difference | 0.0 / 0.0 pp over 9 values (criterion ≤ 0.1 pp) |
| Max / median duration difference | 0.0 / 0.0 h over 51 values (criterion ≤ 1 h) |
| Counts, station hours, clipping metadata | all exact |
| metrics/ cross-check (sun/earth/both frac, longest dark) | ARTEMIS_MALAPERT: exact, ARTEMIS_CABEUS_B: exact, CHANGE6: exact |
| windows/ cross-check (visible intervals, top-10 gaps, visible hours, clipping) | ARTEMIS_MALAPERT: exact, ARTEMIS_CABEUS_B: exact, CHANGE6: exact |
| Supplement: all 33 sites | Z1 fields exact at 33/33; metrics exact 33/33; windows exact 33/33; failing fields 0 of 1188 |

## Site selection

PR #82 (Minchul) checked APOLLO17, CHANGE4 and SHACKLETON_RIM; the integrator sampled CHANGE6 and ARTEMIS_HAWORTH. The task suggested APOLLO11, ARTEMIS_HAWORTH and CHANGE6 and allowed a stronger edge-case selection. Grouping the 33 published files by which run groups are clipped at which edge gives five patterns:

| Clipping pattern (dark / no-Earth / sunlit) | Sites | Covered by PR #82 | This check |
|---|---|---|---|
| none / none / start + end (two runs) | 17 (incl. APOLLO11) | APOLLO17, SHACKLETON_RIM | — |
| end / none / start | 12 (incl. HAWORTH, MALAPERT) | — | ARTEMIS_MALAPERT |
| start + end (two runs) / none / none | 2 (CABEUS_B, IM3_REINER_GAMMA) | — | ARTEMIS_CABEUS_B |
| start + end / whole period / none | 1 (CHANGE6) | — | CHANGE6 |
| start / whole period / end | 1 (CHANGE4) | CHANGE4 | — |

APOLLO11 was replaced because it has the same pattern and the same Earth-always case as PR #82's APOLLO17. ARTEMIS_HAWORTH was replaced by ARTEMIS_MALAPERT, which has Haworth's clipping pattern *and* is a polar site where Earth is always visible (null no-Earth mean), and whose end-clipped dark run (365 h) is shorter than its longest complete dark run (415 h), testing that clipped and complete maxima are kept apart. CHANGE6 was kept although the integrator sampled it, because it is the only site of its pattern. With PR #82, all five patterns are now independently checked.

| Site | Why |
|---|---|
| ARTEMIS_MALAPERT | South polar but Earth ALWAYS visible: no-Earth runs absent (mean_h null, longest_h 0) and station counts limited only by the stations; dark run clipped at the END (365 h, not the longest 415 h) and sunlit run clipped at the START (236 h). Pattern shared by 12 sites, none checked by PR #82. |
| ARTEMIS_CABEUS_B | South polar, intermittent Earth (12,988 h) and the smallest Sun+Earth total of all sites (4,671 h); dark runs clipped at BOTH edges (two runs), no clipped sunlit run; 67 complete no-Earth runs; KDSA / >=1 / >=2 counts all partial. Not checked by PR #82 or the integrator. |
| CHANGE6 | Far side, Earth NEVER visible: one whole-period no-Earth run clipped at both ends (complete_count 0, complete_mean_h null) and all station counts 0; dark runs clipped at both edges. The only site with this pattern; PR #82's CHANGE4 differs (dark clipped at start, sunlight at end). |

Together they cover: Earth always / intermittent / never visible; no-Earth runs absent, 67 complete runs, and one whole-period run clipped at both ends; a clipped sunlit start with a clipped dark end, dark runs clipped at both edges, and no clipped sunlit run; station counts limited only by station availability, partial, and zero.

## Method

- **Inputs read directly**, hashes below: `sites.json` (lat, lon), `ephem.bin` float32 → float64 and `ephem.json` (start, step, n, columns), `horizon/<ID>.json` (`h0_m`, 720-bin mask, 0.5° step, observer 2 m), `korea/stations.json` (four 10° station bit arrays).
- **Geometry (core.js definitions, own code).** Local frame east/north/up from lat, lon; observer at (R + (h0 + 2 m)/1000) km along up, R = 1737.4 km; Sun and Earth vectors minus observer (topocentric); azimuth atan2(E, N) in 0–360°, elevation atan2(U, √(E²+N²)); mask linearly interpolated between 0.5° bins with wrap. Ephemeris row at integer hour i is row i; the last hour uses rows n−2, n−1 with t = 1, as `bodyVec`.
- **Sunlit**: visible fraction of a 0.2666° disc above the locally flat mask line, (acos y − y√(1−y²))/π with y = (mask − el)/0.2666, sunlit when ≥ 0.5. **Earth visible**: Earth-centre elevation strictly above the mask. **Both** = sunlit AND Earth visible. Hour i represents [i, i+1).
- **Two evaluations** of every hourly state: a literal per-hour scalar loop (Python `math`) and a NumPy version. They must agree bit for bit; the smallest distance of any hour from either threshold is reported, to show no hour is near a tie where libm rounding could flip it.
- **Runs**: an explicit state machine finds maximal runs of dark (not sunlit), no-Earth and sunlit hours as [start, end). A run is clipped at the start if it begins at hour 0 and at the end if it ends at 43,824. `count`, `total_h`, `mean_h`, `longest_h` use all observed runs; `complete_*` exclude every clipped run; means are null with no runs and `longest_h` is 0. A clipped run's length is only the observed part; nothing is extrapolated.
- **Stations**: base64-decoded bytes, hour k = bit (k mod 8) of byte ⌊k/8⌋ (LSB first), decoded with explicit shifts and cross-checked against `numpy.unpackbits(bitorder='little')`. A link hour = Earth visible AND station bit (Moon ≥ 10° at the station); sunlight is **not** required. Counted: KDSA linked, ≥ 1 of 4 stations, ≥ 2 of 4. This is geometric line of sight to an available station, not guaranteed radio communication.
- **Criteria**: fractions ≤ 0.1 pp; durations ≤ 1 h; integer run counts, station-hour counts and the clipped-run lists exact. Every difference is reported unrounded.
- **Cross-checks**: `metrics/<ID>.json` (sun_frac, earth_frac, both_frac, longest_dark_h) and `windows/<ID>.json` (every Sun/Earth visible interval with UTC edges and clipping flags, top-10 gaps sorted by duration then start, visible hours) are rebuilt from my own hourly states and compared for exact equality.

## ARTEMIS_MALAPERT

h0 = 4728.31 m. Scalar vs NumPy state bits differing: Sun 0, Earth 0. Closest hour to a threshold: Sun visible fraction 0.00514 from 0.5; Earth centre 0.0164° from the mask.

| Field | Mine | Published | |Δ| | Criterion | Result |
|---|---|---|---|---|---|
| `lat` | -85.942 | -85.942 | 0 | exact | PASS |
| `lon` | -0.944 | -0.944 | 0 | exact | PASS |
| `window` | start_utc=2026-01-01T00:00:00Z, end_utc=2031-01-01T00:00:00Z, step_h=1, n=43824 | start_utc=2026-01-01T00:00:00Z, end_utc=2031-01-01T00:00:00Z, step_h=1, n=43824 | 0 | exact | PASS |
| `sunlit_h` | 19740 | 19740 | 0 | <= 1 h (also exact reported) | PASS |
| `earth_visible_h` | 43824 | 43824 | 0 | <= 1 h (also exact reported) | PASS |
| `both_h` | 19740 | 19740 | 0 | <= 1 h (also exact reported) | PASS |
| `sun_frac (pp)` | 45.04381161 | 45.04381161 | 0 | <= 0.1 pp | PASS |
| `earth_frac (pp)` | 100 | 100 | 0 | <= 0.1 pp | PASS |
| `both_frac (pp)` | 45.04381161 | 45.04381161 | 0 | <= 0.1 pp | PASS |
| `dark_runs.count` | 62 | 62 | 0 | exact (integer count) | PASS |
| `dark_runs.total_h` | 24084 | 24084 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.mean_h` | 388.4516129 | 388.4516129 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.longest_h` | 415 | 415 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.complete_count` | 61 | 61 | 0 | exact (integer count) | PASS |
| `dark_runs.complete_mean_h` | 388.8360656 | 388.8360656 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.complete_longest_h` | 415 | 415 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.clipped_runs` | [43459,43824) 365 h E | [43459,43824) 365 h E | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `no_earth_runs.count` | 0 | 0 | 0 | exact (integer count) | PASS |
| `no_earth_runs.total_h` | 0 | 0 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.mean_h` | null | null | null | <= 1 h; null must match null | PASS |
| `no_earth_runs.longest_h` | 0 | 0 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.complete_count` | 0 | 0 | 0 | exact (integer count) | PASS |
| `no_earth_runs.complete_mean_h` | null | null | null | <= 1 h; null must match null | PASS |
| `no_earth_runs.complete_longest_h` | 0 | 0 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.clipped_runs` | [] | [] | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `sunlit_runs.count` | 62 | 62 | 0 | exact (integer count) | PASS |
| `sunlit_runs.total_h` | 19740 | 19740 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.mean_h` | 318.3870968 | 318.3870968 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.longest_h` | 340 | 340 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.complete_count` | 61 | 61 | 0 | exact (integer count) | PASS |
| `sunlit_runs.complete_mean_h` | 319.7377049 | 319.7377049 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.complete_longest_h` | 340 | 340 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.clipped_runs` | [0,236) 236 h S | [0,236) 236 h S | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `station_link_h.kdsa_h` | 18213 | 18213 | 0 | exact (station-hour count) | PASS |
| `station_link_h.at_least_1_h` | 43246 | 43246 | 0 | exact (station-hour count) | PASS |
| `station_link_h.at_least_2_h` | 25717 | 25717 | 0 | exact (station-hour count) | PASS |

Per-station link hours (mine): KDSA 18,213, DSN_GOLDSTONE 18,297, DSN_MADRID 17,964, DSN_CANBERRA 18,377. Link hours (≥ 1 station) while the site is dark: 23,782 — counted, as sunlight is not required.

Cross-checks:

| Product | Field | Mine | Published | Exact |
|---|---|---|---|---|
| metrics | `sun_frac` | 0.4504381161 | 0.4504381161 | yes |
| metrics | `earth_frac` | 1 | 1 | yes |
| metrics | `both_frac` | 0.4504381161 | 0.4504381161 | yes |
| metrics | `longest_dark_h` | 415 | 415 | yes |
| windows | `sun.visible` | 62 | 62 | yes |
| windows | `sun.longest_gaps` | 10 | 10 | yes |
| windows | `sun.visible_hours` | 19740 | 19740 | yes |
| windows | `earth.visible` | 1 | 1 | yes |
| windows | `earth.longest_gaps` | 0 | 0 | yes |
| windows | `earth.visible_hours` | 43824 | 43824 | yes |

Same-quantity overlap between the published products (windows/metrics vs Z1): sun_visible_hours =, earth_visible_hours =, sun_interval_count =, sun_longest =, dark_longest =, noearth_longest =, metrics_longest_dark =.

## ARTEMIS_CABEUS_B

h0 = 3626.87 m. Scalar vs NumPy state bits differing: Sun 0, Earth 0. Closest hour to a threshold: Sun visible fraction 0.000175 from 0.5; Earth centre 0.000192° from the mask.

| Field | Mine | Published | |Δ| | Criterion | Result |
|---|---|---|---|---|---|
| `lat` | -83.763 | -83.763 | 0 | exact | PASS |
| `lon` | -69.983 | -69.983 | 0 | exact | PASS |
| `window` | start_utc=2026-01-01T00:00:00Z, end_utc=2031-01-01T00:00:00Z, step_h=1, n=43824 | start_utc=2026-01-01T00:00:00Z, end_utc=2031-01-01T00:00:00Z, step_h=1, n=43824 | 0 | exact | PASS |
| `sunlit_h` | 17313 | 17313 | 0 | <= 1 h (also exact reported) | PASS |
| `earth_visible_h` | 12988 | 12988 | 0 | <= 1 h (also exact reported) | PASS |
| `both_h` | 4671 | 4671 | 0 | <= 1 h (also exact reported) | PASS |
| `sun_frac (pp)` | 39.50575027 | 39.50575027 | 0 | <= 0.1 pp | PASS |
| `earth_frac (pp)` | 29.63672873 | 29.63672873 | 0 | <= 0.1 pp | PASS |
| `both_frac (pp)` | 10.65854326 | 10.65854326 | 0 | <= 0.1 pp | PASS |
| `dark_runs.count` | 85 | 85 | 0 | exact (integer count) | PASS |
| `dark_runs.total_h` | 26511 | 26511 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.mean_h` | 311.8941176 | 311.8941176 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.longest_h` | 485 | 485 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.complete_count` | 83 | 83 | 0 | exact (integer count) | PASS |
| `dark_runs.complete_mean_h` | 315.6024096 | 315.6024096 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.complete_longest_h` | 485 | 485 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.clipped_runs` | [0,145) 145 h S; [43653,43824) 171 h E | [0,145) 145 h S; [43653,43824) 171 h E | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `no_earth_runs.count` | 67 | 67 | 0 | exact (integer count) | PASS |
| `no_earth_runs.total_h` | 30836 | 30836 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.mean_h` | 460.238806 | 460.238806 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.longest_h` | 489 | 489 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.complete_count` | 67 | 67 | 0 | exact (integer count) | PASS |
| `no_earth_runs.complete_mean_h` | 460.238806 | 460.238806 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.complete_longest_h` | 489 | 489 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.clipped_runs` | [] | [] | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `sunlit_runs.count` | 84 | 84 | 0 | exact (integer count) | PASS |
| `sunlit_runs.total_h` | 17313 | 17313 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.mean_h` | 206.1071429 | 206.1071429 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.longest_h` | 314 | 314 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.complete_count` | 84 | 84 | 0 | exact (integer count) | PASS |
| `sunlit_runs.complete_mean_h` | 206.1071429 | 206.1071429 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.complete_longest_h` | 314 | 314 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.clipped_runs` | [] | [] | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `station_link_h.kdsa_h` | 6075 | 6075 | 0 | exact (station-hour count) | PASS |
| `station_link_h.at_least_1_h` | 12969 | 12969 | 0 | exact (station-hour count) | PASS |
| `station_link_h.at_least_2_h` | 8422 | 8422 | 0 | exact (station-hour count) | PASS |

Per-station link hours (mine): KDSA 6,075, DSN_GOLDSTONE 6,013, DSN_MADRID 6,099, DSN_CANBERRA 4,847. Link hours (≥ 1 station) while the site is dark: 8,305 — counted, as sunlight is not required.

Cross-checks:

| Product | Field | Mine | Published | Exact |
|---|---|---|---|---|
| metrics | `sun_frac` | 0.3950575027 | 0.3950575027 | yes |
| metrics | `earth_frac` | 0.2963672873 | 0.2963672873 | yes |
| metrics | `both_frac` | 0.1065854326 | 0.1065854326 | yes |
| metrics | `longest_dark_h` | 485 | 485 | yes |
| windows | `sun.visible` | 84 | 84 | yes |
| windows | `sun.longest_gaps` | 10 | 10 | yes |
| windows | `sun.visible_hours` | 17313 | 17313 | yes |
| windows | `earth.visible` | 68 | 68 | yes |
| windows | `earth.longest_gaps` | 10 | 10 | yes |
| windows | `earth.visible_hours` | 12988 | 12988 | yes |

Same-quantity overlap between the published products (windows/metrics vs Z1): sun_visible_hours =, earth_visible_hours =, sun_interval_count =, sun_longest =, dark_longest =, noearth_longest =, metrics_longest_dark =.

## CHANGE6

h0 = -5256.22 m. Scalar vs NumPy state bits differing: Sun 0, Earth 0. Closest hour to a threshold: Sun visible fraction 0.00236 from 0.5; Earth centre 33.1° from the mask.

| Field | Mine | Published | |Δ| | Criterion | Result |
|---|---|---|---|---|---|
| `lat` | -41.6385 | -41.6385 | 0 | exact | PASS |
| `lon` | -153.9852 | -153.9852 | 0 | exact | PASS |
| `window` | start_utc=2026-01-01T00:00:00Z, end_utc=2031-01-01T00:00:00Z, step_h=1, n=43824 | start_utc=2026-01-01T00:00:00Z, end_utc=2031-01-01T00:00:00Z, step_h=1, n=43824 | 0 | exact | PASS |
| `sunlit_h` | 21787 | 21787 | 0 | <= 1 h (also exact reported) | PASS |
| `earth_visible_h` | 0 | 0 | 0 | <= 1 h (also exact reported) | PASS |
| `both_h` | 0 | 0 | 0 | <= 1 h (also exact reported) | PASS |
| `sun_frac (pp)` | 49.71476816 | 49.71476816 | 0 | <= 0.1 pp | PASS |
| `earth_frac (pp)` | 0 | 0 | 0 | <= 0.1 pp | PASS |
| `both_frac (pp)` | 0 | 0 | 0 | <= 0.1 pp | PASS |
| `dark_runs.count` | 63 | 63 | 0 | exact (integer count) | PASS |
| `dark_runs.total_h` | 22037 | 22037 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.mean_h` | 349.7936508 | 349.7936508 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.longest_h` | 364 | 364 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.complete_count` | 61 | 61 | 0 | exact (integer count) | PASS |
| `dark_runs.complete_mean_h` | 357.3278689 | 357.3278689 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.complete_longest_h` | 364 | 364 | 0 | <= 1 h; null must match null | PASS |
| `dark_runs.clipped_runs` | [0,192) 192 h S; [43776,43824) 48 h E | [0,192) 192 h S; [43776,43824) 48 h E | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `no_earth_runs.count` | 1 | 1 | 0 | exact (integer count) | PASS |
| `no_earth_runs.total_h` | 43824 | 43824 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.mean_h` | 43824 | 43824 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.longest_h` | 43824 | 43824 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.complete_count` | 0 | 0 | 0 | exact (integer count) | PASS |
| `no_earth_runs.complete_mean_h` | null | null | null | <= 1 h; null must match null | PASS |
| `no_earth_runs.complete_longest_h` | 0 | 0 | 0 | <= 1 h; null must match null | PASS |
| `no_earth_runs.clipped_runs` | [0,43824) 43824 h SE | [0,43824) 43824 h SE | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `sunlit_runs.count` | 62 | 62 | 0 | exact (integer count) | PASS |
| `sunlit_runs.total_h` | 21787 | 21787 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.mean_h` | 351.4032258 | 351.4032258 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.longest_h` | 358 | 358 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.complete_count` | 62 | 62 | 0 | exact (integer count) | PASS |
| `sunlit_runs.complete_mean_h` | 351.4032258 | 351.4032258 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.complete_longest_h` | 358 | 358 | 0 | <= 1 h; null must match null | PASS |
| `sunlit_runs.clipped_runs` | [] | [] | 0 | exact (start_i, end_i, duration_h, flags) | PASS |
| `station_link_h.kdsa_h` | 0 | 0 | 0 | exact (station-hour count) | PASS |
| `station_link_h.at_least_1_h` | 0 | 0 | 0 | exact (station-hour count) | PASS |
| `station_link_h.at_least_2_h` | 0 | 0 | 0 | exact (station-hour count) | PASS |

Per-station link hours (mine): KDSA 0, DSN_GOLDSTONE 0, DSN_MADRID 0, DSN_CANBERRA 0. Link hours (≥ 1 station) while the site is dark: 0 — counted, as sunlight is not required.

Cross-checks:

| Product | Field | Mine | Published | Exact |
|---|---|---|---|---|
| metrics | `sun_frac` | 0.4971476816 | 0.4971476816 | yes |
| metrics | `earth_frac` | 0 | 0 | yes |
| metrics | `both_frac` | 0 | 0 | yes |
| metrics | `longest_dark_h` | 364 | 364 | yes |
| windows | `sun.visible` | 62 | 62 | yes |
| windows | `sun.longest_gaps` | 10 | 10 | yes |
| windows | `sun.visible_hours` | 21787 | 21787 | yes |
| windows | `earth.visible` | 0 | 0 | yes |
| windows | `earth.longest_gaps` | 1 | 1 | yes |
| windows | `earth.visible_hours` | 0 | 0 | yes |

Same-quantity overlap between the published products (windows/metrics vs Z1): sun_visible_hours =, earth_visible_hours =, sun_interval_count =, sun_longest =, dark_longest =, noearth_longest =, metrics_longest_dark =.

## Clipped runs (three sites)

| Site | Group | Clipped runs (mine) | Published | complete_count mine / pub | complete_mean_h mine / pub |
|---|---|---|---|---|---|
| ARTEMIS_MALAPERT | dark_runs | [43459,43824) 365 h E | [43459,43824) 365 h E | 61 / 61 | 388.8360656 / 388.8360656 |
| ARTEMIS_MALAPERT | no_earth_runs | [] | [] | 0 / 0 | null / null |
| ARTEMIS_MALAPERT | sunlit_runs | [0,236) 236 h S | [0,236) 236 h S | 61 / 61 | 319.7377049 / 319.7377049 |
| ARTEMIS_CABEUS_B | dark_runs | [0,145) 145 h S; [43653,43824) 171 h E | [0,145) 145 h S; [43653,43824) 171 h E | 83 / 83 | 315.6024096 / 315.6024096 |
| ARTEMIS_CABEUS_B | no_earth_runs | [] | [] | 67 / 67 | 460.238806 / 460.238806 |
| ARTEMIS_CABEUS_B | sunlit_runs | [] | [] | 84 / 84 | 206.1071429 / 206.1071429 |
| CHANGE6 | dark_runs | [0,192) 192 h S; [43776,43824) 48 h E | [0,192) 192 h S; [43776,43824) 48 h E | 61 / 61 | 357.3278689 / 357.3278689 |
| CHANGE6 | no_earth_runs | [0,43824) 43824 h SE | [0,43824) 43824 h SE | 0 / 0 | null / null |
| CHANGE6 | sunlit_runs | [] | [] | 62 / 62 | 351.4032258 / 351.4032258 |

S = clipped at the period start (hour 0), E = clipped at the end (exclusive hour 43,824). Clipped durations are observed parts only.

## Supplement: all 33 sites with the same code

Not part of the three-site requirement; recorded because the same code runs in seconds.

| Site | Z1 fields | Not exact | Failing | metrics | windows | Scalar≠NumPy bits | Min Sun margin | Min Earth margin (°) |
|---|---|---|---|---|---|---|---|---|
| ARTEMIS_MALAPERT (selected) | 36 | 0 | 0 | exact | exact | 0 | 0.0051 | 0.016 |
| ARTEMIS_CABEUS_B (selected) | 36 | 0 | 0 | exact | exact | 0 | 0.00018 | 0.00019 |
| CHANGE6 (selected) | 36 | 0 | 0 | exact | exact | 0 | 0.0024 | 33 |
| APOLLO11 | 36 | 0 | 0 | exact | exact | 0 | 0.016 | 56 |
| APOLLO12 | 36 | 0 | 0 | exact | exact | 0 | 0.0065 | 56 |
| APOLLO14 | 36 | 0 | 0 | exact | exact | 0 | 0.0062 | 59 |
| APOLLO15 | 36 | 0 | 0 | exact | exact | 0 | 0.0018 | 43 |
| APOLLO16 | 36 | 0 | 0 | exact | exact | 0 | 0.0058 | 60 |
| APOLLO17 | 36 | 0 | 0 | exact | exact | 0 | 0.0015 | 32 |
| LUNA16 | 36 | 0 | 0 | exact | exact | 0 | 0.0033 | 24 |
| LUNA20 | 36 | 0 | 0 | exact | exact | 0 | 0.00027 | 17 |
| LUNA24 | 36 | 0 | 0 | exact | exact | 0 | 0.0061 | 17 |
| CHANGE3 | 36 | 0 | 0 | exact | exact | 0 | 0.011 | 33 |
| CHANGE4 | 36 | 0 | 0 | exact | exact | 0 | 0.0012 | 38 |
| CHANGE5 | 36 | 0 | 0 | exact | exact | 0 | 0.0027 | 17 |
| CHANDRAYAAN3 | 36 | 0 | 0 | exact | exact | 0 | 0.0023 | 6.8 |
| SLIM | 36 | 0 | 0 | exact | exact | 0 | 0.0038 | 47 |
| IM1 | 36 | 0 | 0 | exact | exact | 0 | 0.00052 | 2.4 |
| IM2 | 36 | 0 | 0 | exact | exact | 0 | 7.7e-08 | 3.2e-05 |
| BLUE_GHOST1 | 36 | 0 | 0 | exact | exact | 0 | 0.0088 | 16 |
| ARTEMIS_HAWORTH | 36 | 0 | 0 | exact | exact | 0 | 6.2e-05 | 6e-05 |
| ARTEMIS_MOUTON_PLATEAU | 36 | 0 | 0 | exact | exact | 0 | 0.00061 | 0.0002 |
| ARTEMIS_MOUTON | 36 | 0 | 0 | exact | exact | 0 | 3.1e-05 | 0.00046 |
| ARTEMIS_NOBILE_RIM1 | 36 | 0 | 0 | exact | exact | 0 | 0.00024 | 0.00013 |
| ARTEMIS_NOBILE_RIM2 | 36 | 0 | 0 | exact | exact | 0 | 0.00062 | 3.5e-05 |
| ARTEMIS_DE_GERLACHE_RIM2 | 36 | 0 | 0 | exact | exact | 0 | 0.00015 | 0.00021 |
| ARTEMIS_SLATER_PLAIN | 36 | 0 | 0 | exact | exact | 0 | 0.00015 | 0.00012 |
| SHACKLETON_RIM | 36 | 0 | 0 | exact | exact | 0 | 0.00013 | 0.00013 |
| CONNECTING_RIDGE | 36 | 0 | 0 | exact | exact | 0 | 7.9e-05 | 9.8e-05 |
| PEAK_NEAR_SHACKLETON | 36 | 0 | 0 | exact | exact | 0 | 7e-05 | 0.0002 |
| DE_GERLACHE_RIM1 | 36 | 0 | 0 | exact | exact | 0 | 1.1e-05 | 0.00013 |
| SHOEMAKER_RIM_A | 36 | 0 | 0 | exact | exact | 0 | 0.0001 | 0.00012 |
| IM3_REINER_GAMMA | 36 | 0 | 0 | exact | exact | 0 | 8.3e-05 | 20 |

## Input hashes

| File | Bytes | SHA-256 (raw bytes) | SHA-256 (CRLF→LF) |
|---|---|---|---|
| `web/data/sites.json` | 16,271 | `bc98c7cef1ed53720c298517d21fe9cc70727cc6da8179525da7b5e5a4b64017` | `075c0d4bb175e7bf02f045fe868241080cadfa05e9a2463bf0ca9f7d8860462b` |
| `web/data/ephem.bin` | 1,051,776 | `c0a226391f7a47c22c71d8b187cc98fb80101631bee37bd13b32a6870f965da3` | `—` |
| `web/data/ephem.json` | 323 | `c6294c416a16bcc34d08752b8f0541d803e2e5784af09ce291b0a211269f52b8` | `f6fb776afba51c8b497b2d34f9de18aaa6408548d27434c31cb17f9b54579f2c` |
| `web/data/korea/stations.json` | 32,249 | `68648959897999c63f7141250ad65bc018533ebea39236b7a3a0978032d33b80` | `68648959897999c63f7141250ad65bc018533ebea39236b7a3a0978032d33b80` |
| `web/js/core.js` | 10,036 | `50a431098cf74afac8fd0dd6e390e33ff4a53885f931b906ac49245080a5c394` | `e9edd76f1d0f6f58917409a2b6a29e43309439ae1ac2306c79511d8ba4d28434` |
| `web/data/horizon/ARTEMIS_MALAPERT.json` | 6,231 | `a274da886f22c9ac622d1819bfe6444f0647e94dd781d797fa5914e0aafc0ac1` | `a274da886f22c9ac622d1819bfe6444f0647e94dd781d797fa5914e0aafc0ac1` |
| `web/data/detail/time_stats/ARTEMIS_MALAPERT.json` | 2,506 | `667d0cc7f49c548f44eafdb539bf7a88498e1d237aec4e63b1d1d54b636a40e0` | `91c611696442767cb0e1feb0dc1c4d2695f6516f2c09c5d65c2b0ff53b17147d` |
| `web/data/metrics/ARTEMIS_MALAPERT.json` | 214 | `d9ba2595feb614c123abb8f09e5d189f05eadcfeb15f77c716b413f5a45294ff` | `e3e06836d23544579dd38a8d9494d968c441637caada64db30b6bdf80b959133` |
| `web/data/windows/ARTEMIS_MALAPERT.json` | 15,632 | `fbf919e0e43390e8fc5952bd5ae1f67f4fa6d0bf47ff84bf294f9123ec5256ad` | `cfeb2a0d7ba944430e267ccd1d90c18d3423a22d601b3c22304c26825a2c2c4b` |
| `web/data/horizon/ARTEMIS_CABEUS_B.json` | 6,336 | `145a651dc9df04ff9c942b854095d74b69f7f33408f89be0e29d956e3ad882e6` | `145a651dc9df04ff9c942b854095d74b69f7f33408f89be0e29d956e3ad882e6` |
| `web/data/detail/time_stats/ARTEMIS_CABEUS_B.json` | 2,537 | `8322930ca70c27c774a58c67a929d513993f1aa6b5110d6d71654c6dddfe3064` | `ac2fa9167833252ce001721be6ebaa4ba0d298f6dec11cbe2e67cd40174efe8f` |
| `web/data/metrics/ARTEMIS_CABEUS_B.json` | 232 | `ee1123277e036fe8b7227a63af030354d944330b9523dce130c2e61cf823a3c7` | `95e777ca34fd7080890126d59ce348d3b7f2f1fe588d1271c3fdd69977dafaf5` |
| `web/data/windows/ARTEMIS_CABEUS_B.json` | 35,403 | `27ac85635ebe6fed2bcbb470c4dde6618aed34594a15defcb98981b649747c03` | `c7567aa2e25c23fe8bc5c957850a4fbcd3bbbabf7ad67c7b96e4a668a880b90f` |
| `web/data/horizon/CHANGE6.json` | 5,552 | `6d277cdc7617cab663768c711fc52cbc76c29783cef8f224727e09df442c2375` | `6d277cdc7617cab663768c711fc52cbc76c29783cef8f224727e09df442c2375` |
| `web/data/detail/time_stats/CHANGE6.json` | 2,644 | `702041d0d3c3004f2fdc55c74c19876deffe6ec6d60e85f45d6bfd50ea284b80` | `19d916da760809304893663606a927b8d8ff9e5eb725da3e9c14488282590311` |
| `web/data/metrics/CHANGE6.json` | 187 | `d2686e0f9dd6a72d5ee081bcf048483fe9e722986397bc8abd40c29271f7b0ac` | `f008014ff9314ff26d9bbc5fcca4989d804a5cafbe441f089caf65877d2e2e54` |
| `web/data/windows/CHANGE6.json` | 15,625 | `2eb304b59c20fa9cbf3e7708a88821a76c5af1bf5c53ab7c3c314c3c6e788e6f` | `c24cc446454d640064902b03007b7cafcbaf127d84689aeca4503ebbc2eefc39` |

Source hashes recorded inside each published Z1 file vs the current inputs (match on raw or LF-normalised bytes): ARTEMIS_MALAPERT: horizon ✓, ephem ✓, ephem_meta ✓, sites ✓, stations ✓, core ✓; ARTEMIS_CABEUS_B: horizon ✓, ephem ✓, ephem_meta ✓, sites ✓, stations ✓, core ✓; CHANGE6: horizon ✓, ephem ✓, ephem_meta ✓, sites ✓, stations ✓, core ✓.

## Limits

- The ephemeris, horizons and station bit arrays are taken as given inputs; they were not regenerated here (they have their own ledger rows: ephem, horizon task A, korea task C).
- core.js runs in JavaScript (V8); this check uses Python/NumPy double precision. The reported threshold margins show how far the closest hour is from a tie; at that distance a 1-ulp libm difference cannot flip a state.
- Station 'link' is geometric: Earth visible from the site AND Moon ≥ 10° at the station. It does not model antenna scheduling, link budget or terrain at the station.
- Clipped runs are censored at 2026-01-01T00Z and 2031-01-01T00Z; their physical durations are unknown and are not inferred.
- Formal scope is three sites; the 33-site supplement uses the same code and is not a second independent implementation.
