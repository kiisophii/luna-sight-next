"""Write the complete W table without rounding away threshold exceedances."""
import csv
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
KEYS=['sun_frac','earth_frac','both_frac','longest_dark_h']

def main():
    source=ROOT/'docs/task_w_sensitivity.json';report=json.loads(source.read_text())
    assert report['complete'] and report['n_sites']==33 and report['n_cases']==198
    sites=report['sites'];rows=[];controls=[];baselines=[];brief=[]
    for s in sites:
        cases={(c['height_m'],c['near_field']):c for c in s['cases']}
        assert len(cases)==6
        for h in (0,2,10):assert np.all(np.array(cases[h,True]['mask'])>=cases[h,False]['mask'])
        for near in (False,True):
            assert np.all(np.array(cases[0,near]['mask'])>=cases[2,near]['mask'])
            assert np.all(np.array(cases[2,near]['mask'])>=cases[10,near]['mask'])
        for c in s['cases']:
            row=dict(id=s['id'],height_m=c['height_m'],near_field=c['near_field'],production_case=c['height_m']==2 and c['near_field']==s['production_near'])
            row.update(c['metrics']);row.update({k+'_diff':v for k,v in c['diff_vs_production'].items()})
            row.update(horizon_rms_deg=c['horizon_rms_deg'],horizon_max_deg=c['horizon_max_deg'])
            exceed=[k for k in KEYS if abs(c['diff_vs_production'][k])>(1 if k.endswith('_h') else .1)]
            if c['horizon_max_deg']>.05:exceed.append('horizon_max_deg')
            row['exceeds_reporting_threshold']=';'.join(exceed);rows.append(row)
        baselines.append(dict(id=s['id'],**s['baseline']))
        for c in s.get('cpu_controls',[]):controls.append(dict(id=s['id'],**c))
        def delta(a,b,k):return (cases[a]['metrics'][k]-cases[b]['metrics'][k])*(1 if k.endswith('_h') else 100)
        near=s['production_near']
        brief.append(dict(id=s['id'],height0_sun=delta((0,near),(2,near),'sun_frac'),height10_sun=delta((10,near),(2,near),'sun_frac'),
                          near_sun=delta((2,True),(2,False),'sun_frac'),near_earth=delta((2,True),(2,False),'earth_frac'),
                          max_dark=max(abs(c['diff_vs_production']['longest_dark_h']) for c in s['cases'])))
    assert len(controls)==18
    summary=dict(baseline_exact=sum(s['baseline']['exact_metrics'] for s in sites),baseline_pass=sum(s['baseline']['passes'] for s in sites),
                 baseline_failures=[b for b in baselines if not b['passes']],cpu_max_angle_deg=max(c['max_angle_deg'] for c in controls),
                 cpu_max_metric_diff=max(abs(v) for c in controls for v in c['metric_diff'].values()),
                 total_compute_s=sum(s['elapsed_s'] for s in sites),latest_run_s=report['runtime_s'],case_count=198,
                 reporting_exceedances=sum(bool(r['exceeds_reporting_threshold']) for r in rows))
    for k in KEYS:
        values=np.abs([r[k+'_diff'] for r in rows]);worst=max(rows,key=lambda r:abs(r[k+'_diff']))
        summary[k]=dict(max=float(values.max()),median=float(np.median(values)),id=worst['id'],height_m=worst['height_m'],near_field=worst['near_field'])
    summary['baseline_max_angle_deg']=max(b['max_angle_deg'] for b in baselines)
    summary['baseline_max_metric_diff']={k:max(abs(b['metrics_difference'][k]) for b in baselines) for k in KEYS}
    contrasts=[]
    for label in ['height0','height10','near2']:
        for group in ['polar','nonpolar']:
            item=dict(contrast=label,group=group)
            for k in KEYS:
                values=[]
                for s in sites:
                    if s['production_near']!=(group=='polar'):continue
                    c={(v['height_m'],v['near_field']):v for v in s['cases']};near=s['production_near']
                    a,b=(((0,near),(2,near)) if label=='height0' else ((10,near),(2,near)) if label=='height10' else ((2,True),(2,False)))
                    diff=(c[a]['metrics'][k]-c[b]['metrics'][k])*(1 if k.endswith('_h') else 100)
                    values.append((abs(diff),s['id'],diff))
                maximum,sid,diff=max(values);item[k]=dict(max=maximum,id=sid,signed=diff)
            contrasts.append(item)
    summary['controlled_contrasts']=contrasts
    (ROOT/'docs/task_w_summary.json').write_text(json.dumps(dict(summary=summary,baselines=baselines,cpu_controls=controls),indent=2)+'\n',encoding='utf-8')
    for filename,selected in [('task_w_cases.csv',rows),('task_w_exceedances.csv',[r for r in rows if r['exceeds_reporting_threshold']])]:
        with (ROOT/'docs'/filename).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(selected)
    lines=['# Task W — full 33-site assumption sensitivity','','Jiyong, 2026-11-15; main baseline `89a9af1`. All 33 catalogue sites, all six cases per site, 198 full recomputations. No production files changed. This is a controlled model-sensitivity experiment, not an estimate of real terrain error or a new independent team-member verification of our own polar products.','','## Result and interpretation','',f"The 2 m production cases reproduce **{summary['baseline_exact']}/33 metrics exactly**; {summary['baseline_pass']}/33 pass the comparison criteria. Maximum stored-mask difference: {summary['baseline_max_angle_deg']:.12g}°. Full CPU controls at SHACKLETON_RIM, APOLLO17 and CHANGE4 cover all six cases (18 controls): max GPU/CPU angle difference {summary['cpu_max_angle_deg']:.12g}°, max metric difference {summary['cpu_max_metric_diff']:.12g} (pp or h).",'','Differences below are signed changes relative to the published production result. The reporting thresholds are 0.1 pp for fractions, 0.05° for horizon maximum, and 1 h for longest darkness. Exceedances in modified assumptions are **sensitivity signals**, not failed implementation checks; only the production-baseline and CPU comparisons test reproduction. Every exceeding row is retained in [task_w_exceedances.csv](task_w_exceedances.csv).','',f"{summary['reporting_exceedances']}/198 cases exceed at least one reporting threshold. Maxima and medians below include all 198 cases, including the 33 unchanged baselines:",'','| Metric (pp, or h for dark) | Median absolute change | Maximum absolute change | Maximum case |','|---|---:|---:|---|']
    for k in KEYS:
        v=summary[k];lines.append(f"| {k} | {v['median']:.9f} | {v['max']:.9f} | {v['id']}, {v['height_m']} m, near {'included' if v['near_field'] else 'excluded'} |")
    lines+=['','## Separate controlled effects','','Maximum absolute changes within each group. Height contrasts preserve that group’s production near-field rule. Near2 is included minus excluded at 2 m. Polar production already includes this near field; nonpolar production excludes it. Thus the polar near2 result is not a newly discovered missing-near-field error.','','| Contrast | Group | Sun max pp | Earth max pp | Both max pp | Dark max h |','|---|---|---:|---:|---:|---:|']
    for c in contrasts:lines.append('| '+c['contrast']+' | '+c['group']+' | '+' | '.join(f"{c[k]['max']:.6f}" for k in KEYS)+' |')
    lines+=['','## Per-site summary','','Height effects retain that site’s production near-field rule. Near effect is **included minus excluded at 2 m**. All fraction changes are pp. Last column is the maximum absolute dark-duration change across all six cases. Full four-metric values and signed deltas for all 198 cases are in [task_w_cases.csv](task_w_cases.csv); full masks, sources and checkpoints are in [task_w_sensitivity.json](task_w_sensitivity.json).','','| Site | Height 0−2 m Sun | Height 10−2 m Sun | Near effect Sun | Near effect Earth | Max dark change (h) |','|---|---:|---:|---:|---:|---:|']
    for b in brief:lines.append('| '+b['id']+' | '+' | '.join(f"{b[k]:+.9f}" for k in ['height0_sun','height10_sun','near_sun','near_earth'])+f" | {b['max_dark']} |")
    lines+=['','## Baseline failures','','None.' if not summary['baseline_failures'] else 'Failures are retained below; do not treat them as verified.']
    for fail in summary['baseline_failures']:lines.append('```json\n'+json.dumps(fail,indent=2)+'\n```')
    lines+=['','## Method and sources','','The standalone script copies our own task-B implementation into one file and imports only third-party/standard libraries: no imports from pipeline/ or web/js/. Native PGDA polar windows use 5 m to 3 km, 10/20 m to 25 km, 60/80 m to 60 km, 240 m to 200 km, then LDEM_64/16 to 300 km. Elsewhere SLDEM2015 59 m windows supply terrain to 150 km, then LDEM_64/16; CHANDRAYAAN3 uses global DEMs. Missing native coverage falls through. Source window metadata, pixel registration, hashes and DEM gates are embedded per site.','','[PGDA polar products](https://pgda.gsfc.nasa.gov/products/90), [PGDA 5 m](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/ldem_87s_5mpp.tif), [SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [LOLA PDS](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/) and the existing [dataset ledger](../data/DATASETS.md). Direct source URLs and original metadata are retained in each site record.','','The 720-azimuth full Cartesian great-circle march uses lunar curvature (R=1737400 m), FP64 CuPy, no early stop. CPU controls independently implement geometry using PROJ geodesic destinations and ECEF vector subtraction, but share the DEM sampler and metric loop. They are geometry/backend controls, not a second independent full pipeline. Polar production distances are the unchanged 8001-point geometric grid from 5 m to 300 km; exclusion removes its samples below 200 m. Nonpolar production keeps the unchanged 4001-point geometric grid from 200 m to 300 km; inclusion adds the polar grid samples below 200 m. Far samples never move when near field is toggled. This preserves the production baseline and avoids confounding near-field sensitivity with a new distant sampling grid.','','All six cases reuse identical terrain samples and vary only observer height and the near cutoff. Ground height is rounded to 0.01 m and horizon bins to 0.0001° as in catalogue files. The independent NumPy ephemeris loop uses all 43,824 inclusive hourly samples, 2026-01-01 through 2030-12-31: Sun disk fraction ≥0.5 (equivalent to Sun centre ≥ mask), Earth centre > mask, both conjunction, and longest sampled dark run including window endpoints. For counterfactual heights, observer height is changed consistently in the terrain angle and topocentric body vector. Production core.js hardcodes 2 m, so 0/10 m are explicitly a physical extension of its definitions; 2 m baseline reproduces it.','','Five-to-200 m terrain below the DEM’s native pixel size is interpolated terrain, not new measured detail. Height 0 m is an extreme ground-level model, not a claim about a real mounted instrument. Large duration changes can occur when a short lit interval joins or splits two dark runs; a small fraction change does not bound the longest outage. No statistical confidence interval or absolute physical accuracy follows from these scenarios.','','## Reproduction and runtime','',f"Stored per-site compute durations sum to {summary['total_compute_s']:.2f} s (including the initial two-site run and CPU controls). The final resumable invocation took {summary['latest_run_s']:.2f} s; source-load/resume overhead is included in that wall time. Implementation/review time is additional. RTX 5060, Ryzen 5600X; two physical CPU cores reserved and library thread pools limited to one.",'','```powershell','python -m pytest pipeline/tests/test_task_w.py -q','python pipeline/task_w_sensitivity.py','python pipeline/task_w_report.py','```','','Use the CuPy-capable Python for the runner. Source defaults are data/raw/sldem, data/processed/local250/raw/polar and data/processed/local250/raw/global; override the three --*-root/--raw arguments if needed. --site produces only an ignored partial report, never the full 33-site document. Per-case/site checkpoints validate input/source/code hashes before reuse. Original raw DEMs remain ignored. Text-file byte hashes may differ under CRLF/LF checkout conversion. [Baseline and CPU checks](task_w_summary.json) preserve all numerical comparisons.','','## Two-line Limits proposal','',f"Changing observer height and the treatment of terrain within 200 m changes modeled five-year illumination by up to {summary['sun_frac']['max']:.3f} pp across 33 tested sites; these are scenario differences, not measured absolute errors.",f"The corresponding maximum Earth-visibility change is {summary['earth_frac']['max']:.3f} pp and longest-dark change {summary['longest_dark_h']['max']:.0f} h; inspect site-specific assumptions and outage durations before comparing candidate sites.",'']
    (ROOT/'docs/task_w_sensitivity.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
