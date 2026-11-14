"""Export complete task-A results without hiding failed or unavailable sites."""
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics

root=Path(os.environ.get('LLSN_VERIFICATION_ROOT',Path(__file__).resolve().parent)).resolve()
out=root/'data/processed/task_a'
dest=root/'docs/task_a_horizons'
dest.mkdir(parents=True,exist_ok=True)
sites=json.loads((root/'web/data/sites.json').read_text(encoding='utf-8'))
records=[]
missing=[]
for site in sites:
    p=out/(site['id']+'.json')
    if p.exists(): records.append(json.loads(p.read_text()))
    else: missing.append(site['id'])
fields=['id','azimuth_deg','stored_deg','independent_deg','difference_deg','pass_0_05_deg','peak_distance_m']
for filename,sampled in [('all_23760_angles.csv',False),('requested_330_random_angles.csv',True)]:
    with (dest/filename).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in records:
            for k in (r['random_indices'] if sampled else range(720)):
                delta=r['difference_deg'][k]
                w.writerow(dict(id=r['id'],azimuth_deg=k*.5,stored_deg=r['stored_mask_deg'][k],
                    independent_deg=r['mask_deg'][k],difference_deg=delta,pass_0_05_deg=abs(delta)<=.05,
                    peak_distance_m=r['peak_distance_m'][k]))
fail_angles=sum(len(r['failures_deg']) for r in records)
fail_sun=[r['id'] for r in records if abs(r['sun_difference_pp'])>1]
summary=dict(complete=len(records)==33,sites_completed=len(records),sites_missing=missing,
    angles_compared=720*len(records),angle_failures=fail_angles,sun_failures=fail_sun,
    max_abs_deg=max((r['max_abs_deg'] for r in records),default=None),
    median_abs_deg=statistics.median([abs(d) for r in records for d in r['difference_deg']]) if records else None,
    max_abs_sun_pp=max((abs(r['sun_difference_pp']) for r in records),default=None),
    passed=len(records)==33 and not fail_angles and not fail_sun,
    input_commit=records[0]['input_commit'] if records else None,
    checker='Minchul Kim',verification_scope='All 33 sites, all 720 published azimuth bins; full 43824-hour sunlight per site; independent finite-step brute force on original DEMs; no production imports')
(dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
(dest/'results.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
lines=['# Task A — full independent horizon recomputation','',
    'Checker: Minchul Kim. Original horizon producers: Jiyong Sung (16 polar) and Soyun Jeong (17 non-polar). No production horizon, DEM sampler, pipeline module or web JS module is imported. Shared source datasets are not independent physical ground truth.','',
    'All 720 azimuth bins at every site are compared. The requested seeded 10 random bins per site are an additional CSV, not the whole verification scope. Sunlight uses all 43,824 hourly ephemeris vectors and the complete newly recomputed masks at all 33 sites, expanding the prompt’s ambiguous ten-site wording.','',
    'Observer height: 2 m above independently sampled terrain. Radius: 1737.4 km. Exact spherical curvature, east-positive longitude, north-clockwise azimuth. Original source priority/range and near-field cutoff follow each published header (5 m polar; 200 m non-polar). No flat substitute and no early stop. Uniform native-resolution-based distance segments are recorded in the checker; finite step sizes do not establish an exact continuous maximum.','',
    'Thresholds: every absolute angle difference <= 0.05 degrees; absolute sunlight difference <= 1 percentage point. Strict comparisons use unrounded values. Failed and missing sites are retained.','',
    '| Site | Rays | Max angle difference (deg) | Median (deg) | Failing rays | Stored Sun fraction | Own Sun fraction | Sun difference (pp) |',
    '|---|---:|---:|---:|---:|---:|---:|---:|']
byid={r['id']:r for r in records}
for s in sites:
    r=byid.get(s['id'])
    if r:
        lines.append(f"| {r['id']} | 720 | {r['max_abs_deg']:.9f} | {r['median_abs_deg']:.9f} | {len(r['failures_deg'])} | {r['stored_sun_frac']:.10f} | {r['own_sun_frac']:.10f} | {r['sun_difference_pp']:+.9f} |")
    else:lines.append(f"| {s['id']} | 0 | BLOCKED | — | — | — | — | — |")
lines+=['','## Machine-readable results','',json.dumps(summary,indent=2),'',
    'See all_23760_angles.csv for every angle, requested_330_random_angles.csv for the predetermined random selections, and results.json for masks, source metadata, height checks and distances. Failed rays are identified by pass_0_05_deg=false; no row is dropped.','',
    'Reproduce from the repository root with Python 3.11 and requirements-independent.txt installed:',
    '```sh','export LLSN_VERIFICATION_ROOT="$PWD"','export OPENBLAS_NUM_THREADS=1',
    'python -m unittest discover -s verification/task_a -p test_independent_geometry.py -v',
    'python verification/task_a/verify_horizons_independent.py --run',
    'python verification/task_a/report_task_a.py','```','',
    'Downloads and per-12-ray checkpoints resume under ignored data/raw/independent_a and data/processed/task_a. Source hosts are allowlisted to PDS Geosciences and PGDA only. A blocked unrelated telemetry connection is never retried. Source byte ranges are checked before decode; no raw DEM is committed.']
(dest/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(summary))
