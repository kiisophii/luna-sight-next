"""Validate recovered task A results and persist evidence; never change production."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone, timedelta
import numpy as np
import verify_horizons_independent as checker

root = Path(os.environ['LLSN_VERIFICATION_ROOT'])
dest = root / 'docs/task_a_horizons'
original_summary = json.loads((dest/'summary.json').read_text())
assert original_summary['complete'] and original_summary['near_refinement_complete']
assert original_summary['current_run_id'] == '43655770217'
sites = json.loads((root/'web/data/sites.json').read_text())
assert len(sites) == 33
old = '89a9af12d2b1b59490546f4409eb5b88debf8eca'
paths = ['web/data/sites.json', 'web/data/ephem.bin', 'web/data/ephem.json']
paths += [f'web/data/{kind}/{s["id"]}.json' for s in sites for kind in ('horizon','metrics')]
identities = []
for path in paths:
    current = (root/path).read_bytes()
    past = subprocess.check_output(['git','show',f'{old}:{path}'],cwd=root)
    assert current == past, f'Input changed: {path}'
    identities.append(dict(path=path, sha256=hashlib.sha256(current).hexdigest()))
failures = []
for s in sites:
    r = json.loads((root/'data/processed/task_a'/f'{s["id"]}.json').read_text())
    assert r['id'] == s['id'] and r['rays'] == 720 and r['observer_height_m'] == 2
    assert r['input_commit'] == old and r['near_refinement']['rays'] == 720
    assert r['near_refinement']['checker_sha256'] == hashlib.sha256((root/'verification/task_a/refine_near_field.py').read_bytes()).hexdigest()
    ref = json.loads((root/'web/data/horizon'/f'{s["id"]}.json').read_text())
    arrays = [np.array(r[k],dtype=float) for k in ('mask_deg','stored_mask_deg','difference_deg')]
    assert all(a.shape == (720,) and np.isfinite(a).all() for a in arrays)
    own, stored, delta = arrays
    assert np.array_equal(stored,np.array(ref['mask']))
    assert np.allclose(own-stored,delta,rtol=0,atol=1e-14)
    assert np.flatnonzero(abs(delta)>.05).tolist() == r['failures_deg']
    assert math.isclose(float(abs(delta).max()),r['max_abs_deg'],abs_tol=1e-14)
    initial = np.array(r['initial_comparison']['mask_deg'])
    assert np.all(own >= initial)
    frac = checker.sunlight(s,own,r['own_h0_m'])
    assert frac == r['own_sun_frac']
    metric = json.loads((root/'web/data/metrics'/f'{s["id"]}.json').read_text())
    assert r['stored_sun_frac'] == metric['sun_frac']
    assert checker.sunlight(s,stored,ref['h0_m']) == metric['sun_frac']
    assert math.isclose(100*(frac-metric['sun_frac']),r['sun_difference_pp'],abs_tol=1e-13)
    for k in r['failures_deg']:
        failures.append(dict(id=s['id'],azimuth_deg=k*.5,stored_deg=stored[k],independent_deg=own[k],
                             difference_deg=delta[k],peak_distance_m=r['peak_distance_m'][k]))
assert len(failures) == 1 and failures[0]['id'] == 'CHANGE6' and failures[0]['azimuth_deg'] == 231
# Regenerate the full tables from every checkpoint, retaining the calculation run ID.
os.environ['GITHUB_RUN_ID'] = '43655770217'
os.environ['LLSN_PREVIOUS_RUN_ID'] = '43655358830'
subprocess.run(['python','verification/task_a/report_task_a.py'],cwd=root,check=True)
summary = json.loads((dest/'summary.json').read_text())
assert summary == original_summary
with (dest/'failed_angles.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(failures[0]));w.writeheader();w.writerows(failures)
for file, count in [('all_23760_angles.csv',23760),('requested_330_random_angles.csv',330),
                    ('initial_full_range_angles.csv',23760)]:
    with (dest/file).open(newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==count
audit=dict(input_snapshot=old,latest_main_at_resume='274e676665d71e56a9fb7ddc7ead13e65d15aecf',
    inputs_byte_identical=True,input_files=identities,
    computation_run_id=43655770217,artifact_id=14137059934,
    artifact_zip_sha256='32872ee53320ed959bd7e6bf11ef1fd567247c236df231ba6958ae07eff2f40d',
    finalizer_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
    hourly_sunlight_rechecked=33*43824,
    failed_angles=failures,production_files_changed=False)
(dest/'resume_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
report=(dest/'report.md').read_text()
report+='\n## Final result and resumed-input audit\n\n'
report+='Computation is complete, but the angular acceptance criterion FAILS at CHANGE6 azimuth 231 degrees: stored 0.1695 degrees, independent 0.22996302810083656 degrees, difference +0.06046302810083656 degrees at 10,620 m. No production value was changed. All other 23,759 angles pass; all 33 sunlight fractions pass (maximum 0.011409273457463343 percentage points). Median absolute angular difference is 0.00015040598244903808 degrees.\n\n'
report+='The initial coarse checker had 19 failing rays; a uniform dense near-field extension over ALL 33 sites and ALL 720 bins resolves 18, leaving the above original-terrain discrepancy. Both stages remain published; this is finite-step model agreement, not absolute physical truth.\n\n'
report+='The original calculation completed in run [43655770217](https://github.com/kiisophii/lunar-landing-site-navigator/actions/runs/43655770217). Its red status is the deliberate failed numerical assertion AFTER all computation and export steps succeeded. The recovered artifact is checked for 33 complete refined results; all 1,446,192 hourly sunlight states were evaluated again. The latest main at resume, '+audit['latest_main_at_resume']+', has byte-identical sites, 33 masks, 33 metrics and ephemeris inputs relative to the calculation snapshot. See resume_audit.json for every SHA-256.\n'
(dest/'report.md').write_text(report)
p=root/'docs/verification_ledger.md'
ledger=p.read_text()
lines=ledger.splitlines()
for i,line in enumerate(lines):
    if line.startswith('| 3 | `horizon/`'):
        cols=line.split('|')
        cols[5]=' **Integrator, merge a7a0978 (PR #14):** SHACKLETON_RIM, 10 azimuths, max 0.0035 deg (historical sample). **Other member, task A (PR #65):** full independent original-DEM recomputation by Minchul; 33/33 sites x 720 bins = 23,760 angles; all 43,824 hourly Sun states/site. 23,759 angles pass; CHANGE6 231 deg differs +0.0604630281 deg (FAIL vs 0.05 deg). Median absolute angle 0.000150406 deg. All 33 Sun fractions pass, max 0.0114092735 pp (threshold 1 pp). [Full evidence](task_a_horizons/report.md); prior integrator sample remains recorded in git history. '
        cols[6]=' Original production commits unchanged; task A PR #65, calculation run 43655770217 '
        cols[7]=' Independently verified (historical integrator sample); task A full recomputation complete, angular criterion FAIL (1/23,760), sunlight PASS (33/33) '
        lines[i]='|'.join(cols)
    if line.startswith('- `horizon/`:'):
        lines[i]='- `horizon/`: task A fully recomputed 33/33 sites and 23,760 angles; one unresolved angular failure at CHANGE6 231 deg (+0.0604630281 deg vs 0.05 deg). All 33 sunlight fractions pass. See PR #65 and task_a_horizons/report.md.'
ledger='\n'.join(lines)+'\n'
ledger+='\n## Task A full horizon recomputation — 2026-11-15, PR #65\n\n'
ledger+='Checker: Minchul Kim; producers: Jiyong Sung (16 polar), Soyun Jeong (17 non-polar). Every published bin and hourly sunlight fraction was recomputed with separate original-DEM readers and geometry, without pipeline/web JS imports. **Complete does not mean PASS:** 1/23,760 angular failures remains (CHANGE6, 231 deg, +0.0604630281 deg); Sun 33/33 PASS, max 0.0114092735 pp. Initial 19 failures and all refined results are retained. Latest-main input equality and full tables: [report](task_a_horizons/report.md), [audit](task_a_horizons/resume_audit.json), [failed ray](task_a_horizons/failed_angles.csv). The previous snapshot counts, sample-only wording, and shared 0.004-degree sentence above are historical and must not be read as current bounds for this full check. No production data changed; integrator review is pending.\n'
p.write_text(ledger)
p=root/'docs/SI_USAGE.md'
stamp=datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
if 'Morning task A independent horizons' not in p.read_text():
    with p.open('a') as history:
        history.write('\n' + "| 2026-11-15 07:45 (KST) | Minchul Kim | Morning task A independent horizons | ChatGPT Codex (GPT-6) | Independently recompute all 33 non-self-produced horizon masks at all 720 azimuth bins from original DEMs, retain 10 seeded random comparisons per site, then recompute full-hour sunlight at all sites | verification/task_a/, .github/workflows/verify-task-a.yml, docs/task_a_horizons/ (results pending), docs/SI_USAGE.md | AI implemented separate source readers and geometry with no pipeline/web JS imports; 6 analytic/isolation controls PASS; independent sunlight using stored masks matches all 33 published metrics exactly. This is an initial execution checkpoint, not a PASS for the new DEM horizons. Original DEM fetch and full run are pending. | No independent human rerun or complete result claimed. |" + '\n')
with p.open('a') as f:
    f.write('\n| '+stamp+' (KST) | Minchul Kim | Task A full independent verification | ChatGPT Codex (GPT-6) | Resume complete original-DEM 33 x 720 ray calculation; preserve latest main, validate recovered artifact and input hashes, recompute 33 x 43,824 Sun states, publish every comparison including one angular failure | verification/task_a/, .github/workflows/verify-task-a.yml, docs/task_a_horizons/, docs/verification_ledger.md, docs/SI_USAGE.md | TO CHECK | TO CHECK |\n')
# Machine-check that no published products were mutated.
assert not subprocess.check_output(['git','diff','--name-only','--','web/data'],cwd=root,text=True).strip()
print(json.dumps(summary))
print('All evidence integrity checks passed. Numerical angular failure remains disclosed.')
