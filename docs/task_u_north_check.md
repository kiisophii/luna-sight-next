# Task U — north-polar custom terrain

Checker: **Jiyong Sung**; browser global terrain producer: Sua. Inputs: main `274e676`. Thirty synthetic points, seed `2026111503`, ten area-uniform points in each of 75–80, 80–85 and 85–90 degrees N. No production data, algorithm or accuracy badge changed.

## Result

**FAIL** against VALIDATION row 14: median horizon RMS ≤0.2° and every point |Sun difference| ≤2 percentage points. Median RMS is **0.559387°**, maximum RMS **4.740184°**; largest angular difference **10.087463°**. Maximum |Sun difference| **5.348667 pp**, |Earth difference| **13.298649 pp**, |both| **5.175246 pp**. These are sampled differences against another DEM chain, not measured physical errors or universal bounds.

Keep the north-polar lower-accuracy/unvalidated badge. Passing agreement on identical tiles does not establish adequate terrain resolution. This PR supplies evidence for a later north-polar terrain improvement; it does not change the UI.

## What was compared

- System under test: actual Chrome `custom_horizon_worker.js` and `core.js`, with the current global 32 ppd near tiles (2×2 means of LDEM_64, approximately 948 m) to 150 km, LDEM_16 to 300 km; 200 m ray start, 4,001 distances, 720 azimuths. North points do not use the south-polar patches.
- Independent reference: original [PGDA north-polar product 98](https://pgda.gsfc.nasa.gov/products/98). Nearest available 10 m (≥83 N), 20 m (80–83 N) or 30 m (75–80 N) to 3 km; 60 m to 60 km; 240 m to 200 km; original LDEM_64 through 300 km, with LDEM_16 only as a missing-data fallback. 5 m ray start and 8,001 logarithmic distances. Resolution gates are centred on each observer. Partial source footprints fall through to the next available source; no extrapolated or zero terrain.
- Both use bilinear sampling, spherical curvature, 2 m observer, 720 azimuths, MOON_ME DE421 and R=1737400 m. Reference uses its own centre terrain height; this source-dependent observer elevation is included in the total difference.
- Reference geometry and metrics import no producer modules. Source download alone reuses the HTTP GeoTIFF reader. Independent Python north-stereographic equations are tested against PROJ. The full ray maximum has no producer early-stop optimization.
- Primary metric table uses every second production ephemeris hour, matching the earlier row-14 comparison cadence (2026–2030, 21,912 samples). The JSON also records all 43,824 hourly samples. Sun is the fraction of bins with ≥50% solar disk visible; Earth is centre strictly above terrain; both is their conjunction.
- A second source-DEM control uses the browser's 200 m start and 4,001 distances. This controls ray sampling as a bundle; it does **not** isolate only <200 m relief because radial density also changes. Its remaining difference also includes DEM resolution, source selection and centre height.

This north-specific reference is not the south card-8 5 m chain and is not an absolute truth model. PGDA DEM noise, missing sub-pixel relief, source footprints, 0.5° azimuth spacing and time sampling remain limits. Thirty points cannot rule out worse unsampled terrain.

## All 30 points

Difference sign is browser − original-DEM reference. Angles compare full 720-bin masks. Percentages below are **percentage points**, not relative percent.

| Point | Lat, lon N/E | Near DEM m | RMS ° | Max angle ° | Sun pp | Earth pp | Both pp | Sun >2 pp? |
|---|---|---:|---:|---:|---:|---:|---:|---|
| NORTH_75_01 | 75.370492, -38.040535 | 30 | 0.897739 | 2.166555 | +0.743885 | +13.298649 | +5.175246 | no |
| NORTH_75_02 | 78.857179, -150.544101 | 30 | 0.433322 | 1.261362 | +0.707375 | +0.000000 | +0.000000 | no |
| NORTH_75_03 | 76.30161, 34.140722 | 30 | 0.404955 | 1.525391 | -0.086710 | +0.000000 | -0.086710 | no |
| NORTH_75_04 | 79.091262, -156.64427 | 30 | 0.498265 | 1.003854 | +0.844286 | +0.000000 | +0.000000 | no |
| NORTH_75_05 | 79.670804, -46.276705 | 30 | 0.592897 | 1.595867 | +1.994341 | +0.287514 | +1.442132 | no |
| NORTH_75_06 | 76.15138, -4.842523 | 30 | 0.525877 | 1.618803 | -0.009127 | +0.000000 | -0.009127 | no |
| NORTH_75_07 | 75.318501, 13.028697 | 30 | 0.175628 | 0.705445 | -0.077583 | +0.000000 | -0.077583 | no |
| NORTH_75_08 | 78.517517, 109.541482 | 30 | 1.670362 | 3.946364 | +1.414750 | +0.000000 | +0.000000 | no |
| NORTH_75_09 | 79.641143, -119.82793 | 30 | 0.416976 | 1.232627 | -0.004564 | +0.000000 | +0.000000 | no |
| NORTH_75_10 | 77.894143, -158.081219 | 30 | 2.701249 | 6.250972 | +4.595655 | +0.000000 | +0.000000 | FAIL |
| NORTH_80_01 | 81.868285, -128.234048 | 20 | 0.290247 | 0.898277 | -0.292077 | +0.000000 | +0.000000 | no |
| NORTH_80_02 | 80.80341, 49.640731 | 20 | 0.331624 | 1.286290 | +0.059328 | +0.360533 | +0.251004 | no |
| NORTH_80_03 | 84.290985, -79.863231 | 10 | 0.452863 | 1.231811 | -0.164294 | +1.008580 | +0.515699 | no |
| NORTH_80_04 | 80.407259, 56.203982 | 20 | 4.740184 | 10.087463 | -1.058781 | +0.000000 | +0.000000 | no |
| NORTH_80_05 | 82.046717, 116.525827 | 20 | 0.504223 | 1.184123 | -0.264695 | +0.000000 | +0.000000 | no |
| NORTH_80_06 | 81.886242, 170.252609 | 20 | 0.324043 | 1.154302 | +1.871121 | +0.000000 | +0.000000 | no |
| NORTH_80_07 | 82.383779, 81.255466 | 20 | 2.765094 | 5.182498 | +3.103322 | +5.376050 | +1.994341 | FAIL |
| NORTH_80_08 | 81.943234, 113.731219 | 20 | 2.281388 | 5.695374 | -4.664111 | +0.556773 | -1.086163 | FAIL |
| NORTH_80_09 | 84.010682, 121.100832 | 10 | 3.758212 | 8.458716 | -5.348667 | +0.000000 | +0.000000 | FAIL |
| NORTH_80_10 | 83.770055, 66.501129 | 10 | 0.280021 | 1.025645 | -0.077583 | -0.187112 | -0.077583 | no |
| NORTH_85_01 | 88.623982, -111.115875 | 10 | 0.286769 | 0.898778 | -0.543081 | -0.885360 | -0.561336 | no |
| NORTH_85_02 | 86.099697, 73.585781 | 10 | 0.723075 | 2.465479 | +4.837532 | +0.155166 | +1.752464 | FAIL |
| NORTH_85_03 | 86.254578, -133.412235 | 10 | 0.176795 | 1.011589 | +0.237313 | +0.000000 | +0.000000 | no |
| NORTH_85_04 | 86.725365, -109.392562 | 10 | 0.073474 | 0.504610 | +0.041073 | -0.059328 | -0.013691 | no |
| NORTH_85_05 | 85.489546, 29.099046 | 10 | 1.060614 | 2.696685 | +3.906535 | +1.469514 | +3.089631 | FAIL |
| NORTH_85_06 | 86.442001, -47.928059 | 10 | 0.912400 | 2.140457 | +2.756480 | +3.066813 | +2.532859 | FAIL |
| NORTH_85_07 | 86.10642, 31.496533 | 10 | 0.823947 | 2.000863 | +1.118109 | +0.844286 | +1.122673 | no |
| NORTH_85_08 | 86.738958, 6.836987 | 10 | 2.407117 | 6.260642 | +2.158635 | +7.005294 | +2.929901 | FAIL |
| NORTH_85_09 | 88.679849, -110.499132 | 10 | 1.000819 | 2.841395 | +0.305769 | -0.013691 | +0.269259 | no |
| NORTH_85_10 | 89.241603, -40.124428 | 10 | 1.327752 | 3.090273 | -2.062797 | +0.000000 | +0.000000 | FAIL |

## Latitude bands and matched-start control

| Band | Median RMS ° | Max abs Sun pp | Matched-start median RMS ° | Matched-start max abs Sun pp |
|---|---:|---:|---:|---:|
| 75-80N | 0.512071 | 4.595655 | 0.512016 | 4.508945 |
| 80-85N | 0.478543 | 5.348667 | 0.478540 | 5.348667 |
| 85-90N | 0.868173 | 4.837532 | 0.852755 | 3.906535 |

## Independent implementation controls

At one preselected point per band (3 points), independently decoded **identical browser tiles** and full CPU rays reproduce all **2,160 rounded angles exactly**. Unrounded maximum difference is 0.000049995°. Sun/Earth/both differences are zero. The independent hourly metric loop versus actual browser core at all 30 points differs by at most 0 pp.

The common O–W stricter flags (not row-14 acceptance) are retained in the JSON: 30/30 have a bin difference >0.05°, 25/30 have any fraction difference >0.1 pp. No failing row is removed.

Browser elapsed: 26.80 s. Sum of measured independent per-point calculations: 53.51 s. These exclude original raster acquisition, cached-input hashing and report generation; they are not total end-to-end task time.

## Reproduce and provenance

```powershell
python -u pipeline/task_u_fetch.py
python -u pipeline/task_u_check.py --mode browser
python -u pipeline/task_u_check.py --mode reference
python pipeline/task_u_report.py
python -m pytest pipeline/tests/test_task_u.py -q
```

Fetch is resumable by original HTTP blocks and source windows. Reference checkpoints are invalidated by checker, ephemeris, browser/index and source-window hashes; incomplete acquisition is explicitly reported as pending, never a full pass. Run reference mode again after acquisition completes. Sources and local window hashes, full source metadata, every 720-angle mask, hourly/2-hour metrics and controls are in [the JSON evidence](task_u_north_check.json). The copied formulas originate from Jiyong's earlier independent verifier, not the terrain producer.
