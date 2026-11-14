# Task W — full 33-site assumption sensitivity

Jiyong, 2026-11-15; main baseline `89a9af1`. All 33 catalogue sites, all six cases per site, 198 full recomputations. No production files changed. This is a controlled model-sensitivity experiment, not an estimate of real terrain error or a new independent team-member verification of our own polar products.

## Result and interpretation

The 2 m production cases reproduce **33/33 metrics exactly**; 33/33 pass the comparison criteria. Maximum stored-mask difference: 0°. Full CPU controls at SHACKLETON_RIM, APOLLO17 and CHANGE4 cover all six cases (18 controls): max GPU/CPU angle difference 4.28577395795e-09°, max metric difference 0 (pp or h).

Differences below are signed changes relative to the published production result. The reporting thresholds are 0.1 pp for fractions, 0.05° for horizon maximum, and 1 h for longest darkness. Exceedances in modified assumptions are **sensitivity signals**, not failed implementation checks; only the production-baseline and CPU comparisons test reproduction. Every exceeding row is retained in [task_w_exceedances.csv](task_w_exceedances.csv).

159/198 cases exceed at least one reporting threshold. Maxima and medians below include all 198 cases, including the 33 unchanged baselines:

| Metric (pp, or h for dark) | Median absolute change | Maximum absolute change | Maximum case |
|---|---:|---:|---|
| sun_frac | 0.228185469 | 46.278294998 | ARTEMIS_DE_GERLACHE_RIM2, 0 m, near included |
| earth_frac | 0.000000000 | 18.937112085 | CONNECTING_RIDGE, 0 m, near included |
| both_frac | 0.204225995 | 28.091913107 | ARTEMIS_HAWORTH, 0 m, near included |
| longest_dark_h | 1.000000000 | 4499.000000000 | ARTEMIS_HAWORTH, 0 m, near included |

## Separate controlled effects

Maximum absolute changes within each group. Height contrasts preserve that group’s production near-field rule. Near2 is included minus excluded at 2 m. Polar production already includes this near field; nonpolar production excludes it. Thus the polar near2 result is not a newly discovered missing-near-field error.

| Contrast | Group | Sun max pp | Earth max pp | Both max pp | Dark max h |
|---|---|---:|---:|---:|---:|
| height0 | polar | 46.278295 | 18.937112 | 28.091913 | 4499.000000 |
| height0 | nonpolar | 0.248722 | 0.000000 | 0.248722 | 2.000000 |
| height10 | polar | 38.348850 | 10.183917 | 25.413016 | 427.000000 |
| height10 | nonpolar | 0.467780 | 0.000000 | 0.467780 | 4.000000 |
| near2 | polar | 13.371668 | 6.888919 | 12.144031 | 427.000000 |
| near2 | nonpolar | 0.798649 | 0.000000 | 0.798649 | 6.000000 |

## Per-site summary

Height effects retain that site’s production near-field rule. Near effect is **included minus excluded at 2 m**. All fraction changes are pp. Last column is the maximum absolute dark-duration change across all six cases. Full four-metric values and signed deltas for all 198 cases are in [task_w_cases.csv](task_w_cases.csv); full masks, sources and checkpoints are in [task_w_sensitivity.json](task_w_sensitivity.json).

| Site | Height 0−2 m Sun | Height 10−2 m Sun | Near effect Sun | Near effect Earth | Max dark change (h) |
|---|---:|---:|---:|---:|---:|
| SHACKLETON_RIM | -40.073932092 | +1.720518437 | -1.257301935 | +0.000000000 | 587 |
| ARTEMIS_CABEUS_B | -4.796458562 | +6.580868930 | -0.985761227 | +0.000000000 | 51 |
| ARTEMIS_DE_GERLACHE_RIM2 | -46.278294998 | +3.956736035 | -0.926433005 | -2.391383717 | 3727 |
| ARTEMIS_HAWORTH | -44.297645126 | +2.473530486 | -0.953815261 | -6.888919314 | 4499 |
| ARTEMIS_MALAPERT | -2.544267981 | +0.563618109 | -0.130065717 | +0.000000000 | 31 |
| ARTEMIS_MOUTON | -15.292990142 | +7.210660825 | +0.000000000 | +0.000000000 | 2872 |
| ARTEMIS_MOUTON_PLATEAU | -2.001186564 | +5.006389193 | +0.000000000 | +0.000000000 | 35 |
| ARTEMIS_NOBILE_RIM1 | -33.924333698 | +8.038974078 | -0.381069733 | -1.321193866 | 945 |
| ARTEMIS_NOBILE_RIM2 | -0.983479372 | +0.125502008 | +0.000000000 | -0.403888280 | 31 |
| ARTEMIS_SLATER_PLAIN | -6.124497992 | +1.750182548 | -0.052482658 | -0.349123768 | 1 |
| CONNECTING_RIDGE | -9.145673604 | +38.348849945 | -13.371668492 | -5.944231471 | 400 |
| DE_GERLACHE_RIM1 | -28.009766338 | +22.834519898 | -9.216411099 | +0.000000000 | 4265 |
| IM1 | -2.336619204 | +1.439850310 | -0.344560058 | +0.000000000 | 16 |
| IM2 | -0.609255203 | +0.807776561 | +0.000000000 | +0.000000000 | 1 |
| PEAK_NEAR_SHACKLETON | -41.358616283 | +18.706644761 | -13.154892296 | -1.300657174 | 427 |
| SHOEMAKER_RIM_A | -1.442132165 | +2.325209931 | -0.686838262 | +0.000000000 | 1 |
| APOLLO11 | -0.132347572 | +0.068455641 | -0.282949982 | +0.000000000 | 8 |
| APOLLO12 | -0.171139102 | +0.177984666 | -0.248722161 | +0.000000000 | 6 |
| APOLLO14 | -0.077583060 | +0.095837897 | +0.000000000 | +0.000000000 | 3 |
| APOLLO15 | -0.134629427 | +0.239594743 | +0.000000000 | +0.000000000 | 3 |
| APOLLO16 | -0.043355239 | +0.015972983 | +0.000000000 | +0.000000000 | 1 |
| APOLLO17 | -0.002281855 | +0.009127419 | +0.000000000 | +0.000000000 | 1 |
| BLUE_GHOST1 | -0.205366922 | +0.294359255 | +0.000000000 | +0.000000000 | 2 |
| CHANDRAYAAN3 | -0.196239503 | +0.467780212 | +0.000000000 | +0.000000000 | 4 |
| CHANGE3 | -0.084428624 | +0.077583060 | +0.000000000 | +0.000000000 | 5 |
| CHANGE4 | -0.075301205 | +0.257849580 | +0.000000000 | +0.000000000 | 3 |
| CHANGE5 | -0.125502008 | +0.123220153 | -0.798649142 | +0.000000000 | 22 |
| CHANGE6 | -0.139193136 | +0.335432640 | +0.000000000 | +0.000000000 | 3 |
| IM3_REINER_GAMMA | -0.248722161 | +0.440397955 | -0.374224169 | +0.000000000 | 8 |
| LUNA16 | -0.120938299 | +0.369660460 | +0.000000000 | +0.000000000 | 3 |
| LUNA20 | -0.002281855 | +0.025100402 | -0.120938299 | +0.000000000 | 2 |
| LUNA24 | -0.150602410 | +0.228185469 | +0.000000000 | +0.000000000 | 4 |
| SLIM | -0.013691128 | +0.036509675 | +0.000000000 | +0.000000000 | 0 |

## Baseline failures

None.

## Method and sources

The standalone script copies our own task-B implementation into one file and imports only third-party/standard libraries: no imports from pipeline/ or web/js/. Native PGDA polar windows use 5 m to 3 km, 10/20 m to 25 km, 60/80 m to 60 km, 240 m to 200 km, then LDEM_64/16 to 300 km. Elsewhere SLDEM2015 59 m windows supply terrain to 150 km, then LDEM_64/16; CHANDRAYAAN3 uses global DEMs. Missing native coverage falls through. Source window metadata, pixel registration, hashes and DEM gates are embedded per site.

[PGDA polar products](https://pgda.gsfc.nasa.gov/products/90), [PGDA 5 m](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/ldem_87s_5mpp.tif), [SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [LOLA PDS](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/) and the existing [dataset ledger](../data/DATASETS.md). Direct source URLs and original metadata are retained in each site record.

The 720-azimuth full Cartesian great-circle march uses lunar curvature (R=1737400 m), FP64 CuPy, no early stop. CPU controls independently implement geometry using PROJ geodesic destinations and ECEF vector subtraction, but share the DEM sampler and metric loop. They are geometry/backend controls, not a second independent full pipeline. Polar production distances are the unchanged 8001-point geometric grid from 5 m to 300 km; exclusion removes its samples below 200 m. Nonpolar production keeps the unchanged 4001-point geometric grid from 200 m to 300 km; inclusion adds the polar grid samples below 200 m. Far samples never move when near field is toggled. This preserves the production baseline and avoids confounding near-field sensitivity with a new distant sampling grid.

All six cases reuse identical terrain samples and vary only observer height and the near cutoff. Ground height is rounded to 0.01 m and horizon bins to 0.0001° as in catalogue files. The independent NumPy ephemeris loop uses all 43,824 inclusive hourly samples, 2026-01-01 through 2030-12-31: Sun disk fraction ≥0.5 (equivalent to Sun centre ≥ mask), Earth centre > mask, both conjunction, and longest sampled dark run including window endpoints. For counterfactual heights, observer height is changed consistently in the terrain angle and topocentric body vector. Production core.js hardcodes 2 m, so 0/10 m are explicitly a physical extension of its definitions; 2 m baseline reproduces it.

Five-to-200 m terrain below the DEM’s native pixel size is interpolated terrain, not new measured detail. Height 0 m is an extreme ground-level model, not a claim about a real mounted instrument. Large duration changes can occur when a short lit interval joins or splits two dark runs; a small fraction change does not bound the longest outage. No statistical confidence interval or absolute physical accuracy follows from these scenarios.

## Reproduction and runtime

Stored per-site compute durations sum to 99.94 s (including the initial two-site run and CPU controls). The final resumable invocation took 85.63 s; source-load/resume overhead is included in that wall time. Implementation/review time is additional. RTX 5060, Ryzen 5600X; two physical CPU cores reserved and library thread pools limited to one.

```powershell
python -m pytest pipeline/tests/test_task_w.py -q
python pipeline/task_w_sensitivity.py
python pipeline/task_w_report.py
```

Use the CuPy-capable Python for the runner. Source defaults are data/raw/sldem, data/processed/local250/raw/polar and data/processed/local250/raw/global; override the three --*-root/--raw arguments if needed. --site produces only an ignored partial report, never the full 33-site document. Per-case/site checkpoints validate input/source/code hashes before reuse. Original raw DEMs remain ignored. Text-file byte hashes may differ under CRLF/LF checkout conversion. [Baseline and CPU checks](task_w_summary.json) preserve all numerical comparisons.

## Two-line Limits proposal

Changing observer height and the treatment of terrain within 200 m changes modeled five-year illumination by up to 46.278 pp across 33 tested sites; these are scenario differences, not measured absolute errors.
The corresponding maximum Earth-visibility change is 18.937 pp and longest-dark change 4499 h; inspect site-specific assumptions and outage durations before comparing candidate sites.
