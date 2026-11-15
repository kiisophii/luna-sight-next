"""Publish task X discovery index and summarize complete nonpolar grids."""
import csv
import json
from pathlib import Path
import numpy as np
from task_x import ROOT,WORK,OUT,sites,validate,read,write
from local_maps import METRICS,sha_file
from local250 import GRID
from check_local250 import index_hash

def csv_write(path,rows):
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    checks=read(ROOT/'docs/task_x_check.json')
    assert checks['complete'] and checks['passed'],'Complete passing developer verification is required'
    checked_hashes={}
    def verify_hash(path,expected):
        full=(ROOT/path).resolve()
        if full not in checked_hashes:checked_hashes[full]=sha_file(full)
        assert checked_hashes[full]==expected,f'Stale input: {path}'
    def verify_evidence(value):
        if isinstance(value,dict):
            if 'path' in value and 'sha256' in value:verify_hash(value['path'],value['sha256'])
            for child in value.values():verify_evidence(child)
        elif isinstance(value,list):
            for child in value:verify_evidence(child)
    verify_evidence(checks['inputs'])
    assert len(checks['sites'])==3 and all(len(s['nodes'])==5 for s in checks['sites'])
    for site_check in checks['sites']:verify_evidence(site_check['inputs'])
    radii=[];overlaps=[];summary=[];hashes={};preflights=[]
    for site in sites():
        sid=site['id'];path=OUT/f'{sid}.json';obj=read(path);validate(obj)
        for name,digest in obj['provenance']['files_sha256'].items():verify_hash(name,digest)
        for source in obj['provenance']['terrain_sources']:
            verify_hash(source['path'],source['sha256'])
            if 'label_sha256' in source:verify_hash(str(Path(source['path']).with_suffix('.lbl')),source['label_sha256'])
        oldpath=ROOT/'web/data/local'/f'{sid}.json';old=read(oldpath)
        hashes[sid]=dict(local250=sha_file(path),local=sha_file(oldpath),metrics=sha_file(ROOT/'web/data/metrics'/f'{sid}.json'))
        old_lookup={(p['e_m'],p['n_m']):p for p in old['points']}
        pairs=[]
        for p in obj['points']:
            key=(p['e_m'],p['n_m'])
            if key not in old_lookup:continue
            previous=old_lookup[key]
            assert abs(p['lat']-previous['lat'])<1e-10 and abs(p['lon']-previous['lon'])<1e-10
            row=dict(id=sid,index=p['index'],old_index=previous['index'],e_m=p['e_m'],n_m=p['n_m'])
            row.update({k:p[k]-previous[k] for k in METRICS});overlaps.append(row);pairs.append(row)
        assert len(pairs)==121
        max_pp=100*max(abs(r[k]) for r in pairs for k in METRICS[:3])
        max_dark=max(abs(r['longest_dark_h']) for r in pairs)
        for radius in (1,3,5,10):
            source=obj if radius<=5 else old
            selected=[p for p in source['points'] if np.hypot(p['e_m'],p['n_m'])<=radius*1000+1e-6]
            for metric in METRICS:
                a=np.array([p[metric] for p in selected]);q1,q3=np.quantile(a,[.25,.75],method='linear')
                radii.append(dict(id=sid,radius_km=radius,spacing_m=source['grid']['spacing_m'],n=len(selected),
                    metric=metric,min=float(a.min()),max=float(a.max()),q1=float(q1),q3=float(q3),iqr=float(q3-q1)))
        preflight=read(WORK/'preflight'/f'{sid}.json');assert len(preflight['rows'])==5 and all(r['metrics_equal'] for r in preflight['rows'])
        preflights.append(preflight)
        summary.append(dict(id=sid,n=1681,shared_nodes=121,shared_max_abs_pp=max_pp,shared_max_dark_h=max_dark,
            shared_median_abs_pp=float(np.median([abs(r[k])*100 for r in pairs for k in METRICS[:3]]))))
    entries=[]
    for site in read(ROOT/'web/data/sites.json'):
        path=OUT/f"{site['id']}.json";obj=read(path)
        assert obj['complete'] and len(obj['points'])==1681
        entries.append(dict(id=site['id'],file=path.name,center=obj['center'],grid=obj['grid'],sha256=index_hash(path)))
    write(OUT/'index.json',dict(schema_version=1,sha256_normalization='CRLF_to_LF',sites=entries))
    runtime=read(WORK/'run.json')
    dev_pp=max(abs(v) for s in checks['sites'] for n in s['nodes']
        for comparison in n['comparisons'].values() for v in comparison['fraction_difference_pp'].values())
    dev_dark=max(abs(c['longest_dark_difference_h']) for s in checks['sites'] for n in s['nodes'] for c in n['comparisons'].values())
    result=dict(complete=True,n_sites=17,n_nodes=28577,summary=summary,radius_statistics=radii,
        overlapping_nodes=overlaps,preflights=preflights,output_sha256=hashes,runtime=runtime,
        independent_developer_check_file='docs/task_x_check.json',independent_developer_check_sha256=sha_file(ROOT/'docs/task_x_check.json'),
        scope_note='10 km statistics use the existing 1 km grid. The 250 m product covers only the requested +/-5 km square.')
    write(ROOT/'docs/task_x_results.json',result)
    csv_write(ROOT/'docs/task_x_radii.csv',radii);csv_write(ROOT/'docs/task_x_overlaps.csv',overlaps)
    max_pp=max(s['shared_max_abs_pp'] for s in summary);dark=max(s['shared_max_dark_h'] for s in summary)
    cpu=sum(p['cpu_s'] for p in preflights);gpu=sum(p['gpu_s'] for p in preflights)
    lines=['# Task X — 250 m neighbourhoods for all 17 nonpolar catalogue sites','',
        'Jiyong Sung, OpenAI Codex-assisted, 2026-11-15. No existing polar local250 or local/ file is changed.', '',
        '**17 × 1,681 = 28,577 nodes** over ±5 km east/north, 250 m spacing. All 17 centre nodes equal their '
        'production metrics exactly. The new discovery index lists all 33 complete site maps, including the unchanged 16 polar maps.', '',
        'Index SHA256 normalizes CRLF to LF before hashing (`sha256_normalization: CRLF_to_LF`) so it remains '
        'valid on Windows and GitHub Pages. Scientific provenance/evidence retains actual execution-byte hashes.', '',
        '## Definitions and source coverage', '',
        'Card9/card20 nonpolar definitions are preserved: 720 azimuths; 4,001 geometric distances from 200 m to '
        '300 km; lunar curvature; observer 2 m; SLDEM2015 512 ppd (~59 m) within 150 km, followed by LDEM_64/16. '
        'CHANDRAYAAN3 is outside SLDEM coverage and uses the production global fallback. No 5 m near-field '
        'extension is introduced. Source NPZ windows are expanded to 166 km to cover the entire shifted footprint; '
        'their radial application gate remains centred on each node. Core.js receives the same 4-decimal-degree '
        'mask and 2-decimal-metre ground serialization, then evaluates all 43,824 hourly samples in 2026–2030.', '',
        'Fractions use the core sunlit threshold (at least half the solar disk), Earth centre visibility, and '
        'their conjunction. Longest darkness is a non-wrapping hourly run. Geometric Earth visibility is not '
        'a guaranteed radio link or station availability. Grid spacing is not DEM resolution.', '',
        '## Per-site checks', '',
        '| Site | New nodes | Shared 1 km nodes | Max shared fraction difference (pp) | Median abs fraction difference (pp) | Max dark difference (h) |',
        '|---|---:|---:|---:|---:|---:|']
    for s in summary:lines.append(f'| {s["id"]} | 1681 | 121 | {s["shared_max_abs_pp"]:.9f} | {s["shared_median_abs_pp"]:.9f} | {s["shared_max_dark_h"]} |')
    lines+=['',f'All 2,057 shared nodes compared; max fraction difference **{max_pp:.9f} pp**, dark **{dark} h**. '
        'All signed differences remain in [overlap CSV](task_x_overlaps.csv); no failed row is discarded.', '',
        '## Radius statistics', '',
        'The [radius CSV](task_x_radii.csv) reports min/max/Q1/Q3/IQR of all four metrics per site. '
        '**1/3/5 km discs use the new 250 m nodes. 10 km discs use the existing 1 km nodes, explicitly labelled '
        'spacing_m=1000.** A ±5 km square cannot measure a complete 10 km disc; no extrapolation or mislabeled '
        '10 km fine-grid statistic is provided. Fractions are stored as 0–1; multiply fraction differences by 100 '
        'for percentage points. The square corners extend to 7.071 km and are retained in the map.', '',
        '## Numerical validation and runtime', '',
        f'CPU production versus FP64 CUDA: centre + four corners for every site (**85 points**), all metric '
        f'dictionaries exactly equal. Summed horizon timings CPU **{cpu:.2f} s**, GPU **{gpu:.2f} s** '
        '(small batches, not an end-to-end speedup). No fast math; 128-distance CUDA launches bound display-GPU '
        'work. Recorded per-site angle differences and metric equality are in [results](task_x_results.json). '
        'The runner additionally asserts matching sample counts and DEM-source records during each preflight.', '',
        'Separate CPU full-ray geometry and independent time loop: [developer check](task_x_check.json), '
        f'five random nodes each from APOLLO17, CHANGE4 and CHANDRAYAAN3: max fraction difference **{dev_pp:.9f} pp**, '
        f'longest-dark difference **{dev_dark} h**, across both unrounded and serialized comparisons. This is a developer check organized by '
        'Jiyong, **not the task-required independent sign-off by another team member**; that sign-off remains '
        'for Sua/the team before merge. Same-input agreement does not establish absolute physical accuracy.', '',
        f'Full invocation wall time **{runtime["end_epoch"]-runtime["start_epoch"]:.1f} s**, including source waits, '
        'CPU/GPU preflights, core.js, checkpoint writes and exports. Downloading began earlier in parallel. '
        f'{sum(r["resumed"] for r in runtime["runs"])} nodes resumed from the initial pilot; that pilot is excluded from this invocation time. '
        'P/Q ran independently on CPU during X. Two physical cores were reserved; GPU batches contain at most '
        '16 nodes. Per-node input fingerprints support restart; only complete site maps are published.', '',
        '## Reproduce', '', '```powershell',
        'python pipeline/task_x_fetch.py',
        'python pipeline/task_x.py',
        'python pipeline/task_x_verify.py',
        'python pipeline/task_x_report.py',
        'python -m pytest pipeline/tests/test_task_x.py pipeline/tests/test_local250.py -q',
        'python pipeline/check_contract.py', '```', '',
        'Fetch can run concurrently with the GPU runner; it waits for each complete source NPZ. '
        'Use the existing LDEM64/16 raw IMG+LBL files under data/processed/local250/raw/global. '
        'GPU execution needs CuPy/CUDA; acquisition uses requests, NumPy and optional truststore. '
        'Production per-site provenance includes raw/code/ephemeris hashes and source URLs. Raw data and '
        'per-node checkpoints remain ignored. A checkout with CRLF may require LF normalization of the '
        'unchanged core.js/build_windows.mjs when checking historical windows provenance; report raw and '
        'normalized check results separately.', '',
        'Sources: [SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), '
        '[LOLA global floats](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/), '
        '[NAIF ephemeris](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/), [source register](../data/DATASETS.md).']
    (ROOT/'docs/task_x.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
