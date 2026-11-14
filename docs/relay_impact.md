# Card 18 — measured relay impact

Owner: Jiyong. Card 13 real-terrain results, 2026–2030.

The denominator is all catalogue sites with exact hourly direct Earth visibility <50%. At each height, count sites whose direct OR selected single-tower link is ≥50%. This threshold is a communication-screening example, not a mission requirement or a guarantee of RF service.

| Scope | Direct <50% sites | Reached ≥50%: 5 m | 15 m | 30 m | 50 m |
| --- | --- | --- | --- | --- | --- |
| All 33 catalogue sites | 7 | 3 | 3 | 3 | 3 |
| Six local-grid regions | 2 | 2 | 2 | 2 | 2 |

## Single-tower availability and remaining outage

Each height cell is availability % / longest remaining outage h. Counts and outages use exact saved hourly visibility bits; percentage rounding is display only. Greedy three-tower network outages are not substituted for single-tower outages.

| Site | Direct % / outage h | 5 m | 15 m | 30 m | 50 m |
| --- | --- | --- | --- | --- | --- |
| CHANGE4 | 0.00% / 43824 h | 0.00% / 43824 h | 0.00% / 43824 h | 0.00% / 43824 h | 0.00% / 43824 h |
| CHANGE6 | 0.00% / 43824 h | 0.00% / 43824 h | 0.00% / 43824 h | 0.00% / 43824 h | 0.00% / 43824 h |
| ARTEMIS_CABEUS_B | 29.64% / 489 h | 76.11% / 193 h | 85.73% / 130 h | 88.71% / 129 h | 89.52% / 125 h |
| ARTEMIS_SLATER_PLAIN | 39.77% / 427 h | 46.14% / 380 h | 46.20% / 379 h | 46.28% / 379 h | 46.40% / 379 h |
| SHACKLETON_RIM | 49.94% / 353 h | 54.39% / 323 h | 54.41% / 323 h | 54.46% / 322 h | 54.49% / 322 h |
| CONNECTING_RIDGE | 43.89% / 394 h | 52.92% / 336 h | 54.20% / 325 h | 54.25% / 325 h | 54.29% / 325 h |
| SHOEMAKER_RIM_A | 43.45% / 403 h | 45.14% / 388 h | 45.16% / 388 h | 45.21% / 388 h | 45.30% / 387 h |

## Interpretation and limits

A geometric improvement does not supply power: the selected tower’s sunlight and longest darkness are separately retained in relay_impact.json. No battery, throughput, interference or Earth-station schedule is modelled. The chosen site and tower heights do not prove structural feasibility. Some low-direct sites are on the far side; nearby surface towers may not see Earth either.

Evidence includes exact single-tower timeline segments [start hour,length hours,code], with codes 0 none, 1 direct, 2 via selected tower. The report can be audited without treating a three-tower network as one tower. Source JSON and visibility-cache hashes are included.

Reproduce: `python pipeline/local_impact.py --relay` with matching Card 13 visibility checkpoints. [Machine-readable evidence](relay_impact.json), [Card 13 method and sources](card13_relay_report.md).
