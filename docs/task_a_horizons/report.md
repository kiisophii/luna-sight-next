# Task A — full independent horizon recomputation

Checker: Minchul Kim. Original horizon producers: Jiyong Sung (16 polar) and Soyun Jeong (17 non-polar). No production horizon, DEM sampler, pipeline module or web JS module is imported. Shared source datasets are not independent physical ground truth.

All 720 azimuth bins at every site are compared. The requested seeded 10 random bins per site are an additional CSV, not the whole verification scope. Sunlight uses all 43,824 hourly ephemeris vectors and the complete newly recomputed masks at all 33 sites, expanding the prompt’s ambiguous ten-site wording.

Observer height: 2 m above independently sampled terrain. Radius: 1737.4 km. Exact spherical curvature, east-positive longitude, north-clockwise azimuth. Original source priority/range and near-field cutoff follow each published header (5 m polar; 200 m non-polar). No flat substitute and no early stop. Uniform native-resolution-based distance segments are recorded in the checker; finite step sizes do not establish an exact continuous maximum.

Thresholds: every absolute angle difference <= 0.05 degrees; absolute sunlight difference <= 1 percentage point. Strict comparisons use unrounded values. Failed and missing sites are retained.

Near-field convergence: after the initial full 33-site run, every azimuth at every site was rechecked to 3 km using 0.025 m steps up to 200 m and 0.25 m thereafter, retaining the original site-specific start (5 or 200 m). The final mask is the maximum over the union of the two independent distance grids, not a fit to the published mask. The original 19 failing rays are preserved in initial_full_range_angles.csv and each result’s initial_comparison. New sunlight uses the final full masks over all 43,824 hours. This separates checker discretization from discrepancies supported by original terrain samples.

Execution provenance: the 17 non-polar results were completed in GitHub run 43649858746 with checker commit 537c358. The subsequent run resumes those exact results and computes the 16 polar sites after removing a query suffix rejected by PGDA. The geometry/sampling code is unchanged. Input horizon SHA-256 is checked again for every retained result. Earlier non-polar failures are retained, not discarded or recalculated to force a PASS.

| Site | Rays | Max angle difference (deg) | Median (deg) | Failing rays | Stored Sun fraction | Own Sun fraction | Sun difference (pp) |
|---|---:|---:|---:|---:|---:|---:|---:|
| APOLLO11 | 720 | 0.007785878 | 0.000076672 | 0 | 0.4965772180 | 0.4965772180 | +0.000000000 |
| APOLLO12 | 720 | 0.005121283 | 0.000140332 | 0 | 0.4992926250 | 0.4992926250 | +0.000000000 |
| APOLLO14 | 720 | 0.005678905 | 0.000228350 | 0 | 0.4907813070 | 0.4907813070 | +0.000000000 |
| APOLLO15 | 720 | 0.010604842 | 0.000231730 | 0 | 0.4720929171 | 0.4720929171 | +0.000000000 |
| APOLLO16 | 720 | 0.011560149 | 0.000178063 | 0 | 0.4955275648 | 0.4955275648 | +0.000000000 |
| APOLLO17 | 720 | 0.022502744 | 0.000273633 | 0 | 0.4774780942 | 0.4774780942 | +0.000000000 |
| LUNA16 | 720 | 0.003093790 | 0.000263187 | 0 | 0.4932685287 | 0.4932685287 | +0.000000000 |
| LUNA20 | 720 | 0.004568322 | 0.000117167 | 0 | 0.4784364732 | 0.4784364732 | +0.000000000 |
| LUNA24 | 720 | 0.006296847 | 0.000288520 | 0 | 0.4954819277 | 0.4954819277 | +0.000000000 |
| CHANGE3 | 720 | 0.005819694 | 0.000253182 | 0 | 0.5008671048 | 0.5008671048 | +0.000000000 |
| CHANGE4 | 720 | 0.009887718 | 0.000349466 | 0 | 0.4927437021 | 0.4927437021 | +0.000000000 |
| CHANGE5 | 720 | 0.016087678 | 0.000345222 | 0 | 0.5015516612 | 0.5015516612 | +0.000000000 |
| CHANGE6 | 720 | 0.060463028 | 0.000213343 | 1 | 0.4971476816 | 0.4971476816 | +0.000000000 |
| CHANDRAYAAN3 | 720 | 0.002970390 | 0.000186658 | 0 | 0.4794176707 | 0.4794176707 | +0.000000000 |
| SLIM | 720 | 0.005143265 | 0.000280370 | 0 | 0.4765197152 | 0.4765197152 | +0.000000000 |
| IM1 | 720 | 0.001753326 | 0.000076444 | 0 | 0.3888736765 | 0.3888508580 | -0.002281855 |
| IM2 | 720 | 0.002424873 | 0.000086721 | 0 | 0.4502783863 | 0.4502327492 | -0.004563709 |
| BLUE_GHOST1 | 720 | 0.005521785 | 0.000188318 | 0 | 0.4961436656 | 0.4961436656 | +0.000000000 |
| ARTEMIS_CABEUS_B | 720 | 0.001913470 | 0.000081160 | 0 | 0.3950575027 | 0.3950575027 | +0.000000000 |
| ARTEMIS_HAWORTH | 720 | 0.002864400 | 0.000125520 | 0 | 0.5473028478 | 0.5472572107 | -0.004563709 |
| ARTEMIS_MALAPERT | 720 | 0.001950035 | 0.000131735 | 0 | 0.4504381161 | 0.4504381161 | +0.000000000 |
| ARTEMIS_MOUTON_PLATEAU | 720 | 0.001664549 | 0.000092913 | 0 | 0.3758442862 | 0.3758442862 | +0.000000000 |
| ARTEMIS_MOUTON | 720 | 0.003088089 | 0.000101545 | 0 | 0.7155896313 | 0.7155439942 | -0.004563709 |
| ARTEMIS_NOBILE_RIM1 | 720 | 0.003167541 | 0.000086934 | 0 | 0.7289156627 | 0.7288700256 | -0.004563709 |
| ARTEMIS_NOBILE_RIM2 | 720 | 0.002309304 | 0.000131141 | 0 | 0.4518300475 | 0.4518300475 | +0.000000000 |
| ARTEMIS_DE_GERLACHE_RIM2 | 720 | 0.005323278 | 0.000101934 | 0 | 0.6836664841 | 0.6836208470 | -0.004563709 |
| ARTEMIS_SLATER_PLAIN | 720 | 0.002273646 | 0.000098348 | 0 | 0.4040480102 | 0.4039795546 | -0.006845564 |
| SHACKLETON_RIM | 720 | 0.005502629 | 0.000167281 | 0 | 0.8482566630 | 0.8481653888 | -0.009127419 |
| CONNECTING_RIDGE | 720 | 0.002242566 | 0.000091163 | 0 | 0.4705868930 | 0.4705412559 | -0.004563709 |
| PEAK_NEAR_SHACKLETON | 720 | 0.003127874 | 0.000103154 | 0 | 0.6678304126 | 0.6677163198 | -0.011409273 |
| DE_GERLACHE_RIM1 | 720 | 0.003399686 | 0.000161528 | 0 | 0.5208105148 | 0.5207192406 | -0.009127419 |
| SHOEMAKER_RIM_A | 720 | 0.002829853 | 0.000130686 | 0 | 0.1933643666 | 0.1933643666 | +0.000000000 |
| IM3_REINER_GAMMA | 720 | 0.004165439 | 0.000089979 | 0 | 0.4952765608 | 0.4952765608 | +0.000000000 |

## Machine-readable results

{
  "complete": true,
  "sites_completed": 33,
  "sites_missing": [],
  "angles_compared": 23760,
  "angle_failures": 1,
  "sun_failures": [],
  "max_abs_deg": 0.06046302810083656,
  "median_abs_deg": 0.00015040598244903808,
  "max_abs_sun_pp": 0.011409273457463343,
  "passed": false,
  "input_commit": "89a9af12d2b1b59490546f4409eb5b88debf8eca",
  "checker": "Minchul Kim",
  "verification_scope": "All 33 sites, all 720 published azimuth bins; full 43824-hour sunlight per site; independent finite-step brute force on original DEMs; no production imports",
  "previous_run_id": "43655358830",
  "current_run_id": "43655770217",
  "near_refined_sites": 33,
  "near_refinement_complete": true,
  "initial_angle_failures": 19,
  "initial_max_abs_deg": 0.11259736280829724
}

See all_23760_angles.csv for every angle, requested_330_random_angles.csv for the predetermined random selections, and results.json for masks, source metadata, height checks and distances. Failed rays are identified by pass_0_05_deg=false; no row is dropped.

Reproduce from the repository root with Python 3.11 and requirements-independent.txt installed:
```sh
export LLSN_VERIFICATION_ROOT="$PWD"
export OPENBLAS_NUM_THREADS=1
python -m unittest discover -s verification/task_a -p test_independent_geometry.py -v
python verification/task_a/verify_horizons_independent.py --run
python verification/task_a/refine_near_field.py
python verification/task_a/report_task_a.py
```

Downloads and per-12-ray checkpoints resume under ignored data/raw/independent_a and data/processed/task_a. Source hosts are allowlisted to PDS Geosciences and PGDA only. A blocked unrelated telemetry connection is never retried. Source byte ranges are checked before decode; no raw DEM is committed.

## Final result and resumed-input audit

Computation is complete, but the angular acceptance criterion FAILS at CHANGE6 azimuth 231 degrees: stored 0.1695 degrees, independent 0.22996302810083656 degrees, difference +0.06046302810083656 degrees at 10,620 m. No production value was changed. All other 23,759 angles pass; all 33 sunlight fractions pass (maximum 0.011409273457463343 percentage points). Median absolute angular difference is 0.00015040598244903808 degrees.

The initial coarse checker had 19 failing rays; a uniform dense near-field extension over ALL 33 sites and ALL 720 bins resolves 18, leaving the above original-terrain discrepancy. Both stages remain published; this is finite-step model agreement, not absolute physical truth.

The original calculation completed in run [43655770217](https://github.com/kiisophii/lunar-landing-site-navigator/actions/runs/43655770217). Its red status is the deliberate failed numerical assertion AFTER all computation and export steps succeeded. The recovered artifact is checked for 33 complete refined results; all 1,446,192 hourly sunlight states were evaluated again. The latest main at resume, 274e676665d71e56a9fb7ddc7ead13e65d15aecf, has byte-identical sites, 33 masks, 33 metrics and ephemeris inputs relative to the calculation snapshot. See resume_audit.json for every SHA-256.
