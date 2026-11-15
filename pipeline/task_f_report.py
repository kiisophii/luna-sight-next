"""Summarise all pinned F points, retaining regressions and unrounded metrics."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_f'
OUT=ROOT/'docs/task_f'
METRICS=['sun_frac','earth_frac','both_frac','longest_dark_h']

def main():
    data={name:json.loads((WORK/file).read_text()) for name,file in
          [('reference','reference.json'),('before','browser_before.json'),('after','browser_after.json')]}
    assert all(d['complete'] and len(d['points'])==48 for d in data.values())
    assert all([p['id'] for p in d['points']]==[p['id'] for p in data['reference']['points']] for d in data.values())
    rows=[]
    for ref,before,after in zip(*(data[n]['points'] for n in ['reference','before','after'])):
        assert ref['lat']==before['lat']==after['lat'] and ref['lon']==before['lon']==after['lon']
        row={k:ref[k] for k in ['id','parent','kind','lat','lon']}
        for label,point in [('before',before),('after',after)]:
            angles=np.array(point['mask'])-np.array(ref['mask'])
            row[label+'_rms_deg']=float(np.sqrt(np.mean(angles**2)))
            row[label+'_max_deg']=float(np.max(np.abs(angles)))
            for key in METRICS:
                scale=1 if key.endswith('_h') else 100
                row[label+'_'+key+'_diff']=(point['metrics'][key]-ref['metrics'][key])*scale
            for key in ['cold_local_ms','compressed_bytes','tile_count']:row[label+'_'+key]=point[key]
        rows.append(row)
    summary={}
    for metric in ['rms_deg','max_deg']+[k+'_diff' for k in METRICS]:
        item={}
        for label in ['before','after']:
            a=np.abs([r[label+'_'+metric] for r in rows])
            item[label]=dict(mean=float(a.mean()),median=float(np.median(a)),max=float(a.max()))
        item['regressions']=[r['id'] for r in rows if abs(r['after_'+metric])>abs(r['before_'+metric])+1e-12]
        summary[metric]=item
    for key in ['compressed_bytes','cold_local_ms','tile_count']:
        summary[key]={label:dict(median=float(np.median([r[label+'_'+key] for r in rows])),max=max(r[label+'_'+key] for r in rows)) for label in ['before','after']}
    build=json.loads((WORK/'polar_s/build_report.json').read_text())
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [ROOT/'web/data/ephem.bin',ROOT/'web/data/ephem.json',ROOT/'web/data/sites.json',ROOT/'web/js/core.js',ROOT/'web/js/hterrain.js',
             ROOT/'pipeline/horizon.py',ROOT/'pipeline/local250_gpu.py',ROOT/'pipeline/local250_gpu.cu',ROOT/'pipeline/task_f_browser.mjs']}
    OUT.mkdir(exist_ok=True)
    report=dict(complete=True,count=48,seed=2026111506,summary=summary,rows=rows,build=build,reference=data['reference'],inputs=hashes)
    profiles=({label:[json.loads((WORK/f'profile_{label}_{i}.json').read_text()) for i in range(1,4)] for label in ['before','after']}
              if (WORK/'profile_before_1.json').exists() else json.loads((OUT/'results.json').read_text())['serial_profiles'])
    report['serial_profiles']=profiles
    (OUT/'results.json').write_text(json.dumps(report,indent=1,allow_nan=False)+'\n',encoding='utf-8')
    for label in ['before','after']:(OUT/(label+'.json')).write_text(json.dumps(data[label],allow_nan=False)+'\n',encoding='utf-8')
    with (OUT/'points.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2));print('ADDITIONAL_BYTES',build['additional_bytes'])
    lines=['# Task F — sparse native-resolution south-polar terrain', '',
      'Jiyong; base main `89a9af1`. Candidate adds native PGDA 5/10 m tiles around catalogue regions to the existing browser terrain chain. All 16 south-polar centres and two fixed-seed nearby points per centre were compared (48 points, seed 2026111506). This is a developer comparison against card-8, not independent verification by another team member and not ground-truth accuracy.', '',
      '## Decision and limits', '',
      'Promote the sparse tiles for integrator review: mean and maximum absolute errors improve for all four metrics, and Sun/Earth/both agreement improves at all three previously reported headline centres. **Not every point or metric improves.** In particular SHACKLETON_RIM longest-dark error changes from −2 h to +14 h. The original plan phrase “headline locations do not worsen” was too broad; the decision uses the original task F fraction-error objective and explicitly accepts this duration tradeoff. No claim of all-metric non-regression.', '',
      'These patches do not make the browser chain identical to card-8. Beyond 3 km it still uses the existing coarser chain; native-source gaps fall through. Remaining maximum differences on this sample are not bounds elsewhere. Sparse patch edges and distant terrain remain limitations. Catalogue horizon/metrics, local maps and all JS definitions are unchanged.', '',
      '## Full-sample results', '',
      'Absolute difference from card-8; fractions in percentage points (pp), duration in hours. Both paths use the same production ephemeris and actual core.js inclusive hourly definitions for 2026–2030; 720 azimuths, curvature, 2 m observer, 5 m to 300 km geometric march.', '',
      '| Metric | Mean before → after | Median before → after | Maximum before → after | Points worsened |',
      '|---|---:|---:|---:|---:|']
    for key in ['rms_deg','max_deg']+[k+'_diff' for k in METRICS]:
        s=summary[key];cells=[f"{s['before'][a]:.6f} → {s['after'][a]:.6f}" for a in ['mean','median','max']]
        lines.append('| '+key+' | '+' | '.join(cells)+f" | {len(s['regressions'])} |")
    lines+=['','## All 16 catalogue centres','','Signed differences; Sun/Earth/both in pp and dark in h. Every centre reference exactly matched its current stored horizon and metrics; original CPU checked each GPU centre. Full 48-point table, coordinates, every metric, angles and loading bytes: [points.csv](task_f/points.csv).','','| Site | Sun before → after | Earth before → after | Both before → after | Dark before → after |','|---|---:|---:|---:|---:|']
    for r in rows:
        if r['kind']=='centre':
            cells=[f"{r['before_'+k+'_diff']:+.6f} → {r['after_'+k+'_diff']:+.6f}" for k in METRICS]
            lines.append('| '+r['id']+' | '+' | '.join(cells)+' |')
    lines+=['','## Every regression','','Any increase in absolute error, with no rounding-based exemption. Units as above.','','| Metric | Point | Signed before | Signed after |','|---|---|---:|---:|']
    for key in ['rms_deg','max_deg']+[k+'_diff' for k in METRICS]:
        for r in rows:
            if r['id'] in summary[key]['regressions']:lines.append(f"| {key} | {r['id']} | {r['before_'+key]:+.9f} | {r['after_'+key]:+.9f} |")
    lines+=['','## Payload and local timing','','210 additional sparse tiles (118 p5, 92 p10), **19,884,973 compressed bytes total**. A user downloads only the required tiles, not the complete set. Across the 48 points, median requested compressed terrain bytes changed from 6,417,423 to 6,726,539; maximum from 6,924,326 to 7,247,606. These counts exclude JS/ephemeris/index/HTTP overhead.','','The full 48-point runs were concurrent and their timing is not a controlled speed comparison. The table below instead uses three serial cold-JS-cache repeats per path, alternating before/after order. OS file caching is not flushed. Timer includes local file reads, gzip decode, terrain march and core metrics; **not browser FPS, network latency or time-to-interactive**. Ryzen 5600X desktop; accuracy comes at extra computation cost.','','| Point | Before median ms | After median ms |','|---|---:|---:|']
    for j,p in enumerate(profiles['before'][0]['points']):
        vals={label:float(np.median([run['points'][j]['cold_local_ms'] for run in profiles[label]])) for label in profiles}
        lines.append(f"| {p['id']} | {vals['before']:.0f} | {vals['after']:.0f} |")
    lines+=['','## Sources, encoding and reproduction','','Native [PGDA 5 m](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/ldem_87s_5mpp.tif) and [PGDA 10 m](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF), MOON_ME DE421, metres above R=1737400 m. Existing catalogue-window caches provide original pixels; source hashes, bounds and per-tile window offsets are recorded in [results.json](task_f/results.json). No resampling or gap filling. 0.25 m quantization gives at most 0.125 m height encoding error, checked for every encoded pixel. This height bound is not an angular or visibility-error bound.','','Tiles intersect 4 km projected discs around all 16 sites; only completely available finite tiles are published. p5/p10 are used to 3 km, followed by unchanged p20/p60/p240/global levels. The projection and first-pixel-centre offsets preserve the native lattice. The actual JS decoder/sampler is exercised on the test points.','','The saved [baseline index](task_f/baseline_index.json) pins the pre-change chain even after promotion. Full before/after masks and raw metrics are in [before.json](task_f/before.json) and [after.json](task_f/after.json). Input and execution-file SHA-256 hashes are in results.json; checkout CRLF/LF conversion can alter text-file byte hashes. Reference generation uses original horizon.py + validated FP64 GPU and actual core.js, explicitly not an independent implementation.','','From the repository root, with NumPy/pyproj, CuPy for the reference GPU, Node, and the original cached source windows present:','','```powershell','python pipeline/task_f_tiles.py','python pipeline/task_f_reference.py','node pipeline/task_f_browser.mjs data/processed/task_f/points.json data/processed/task_f/browser_before.json','node pipeline/task_f_browser.mjs data/processed/task_f/points.json data/processed/task_f/browser_after.json data/processed/task_f/polar_s','python -m pytest pipeline/tests/test_task_f_tiles.py','```','','The builder resumes by validating existing tile bytes against current original pixels. Its source defaults are `data/processed/local250/raw/polar`; the reference uses the same raw root plus global LDEM_64/16. Timings/profile inputs are preserved in results.json. Builder initial run 39.3 s; 48-point reference 88.3 s. Review/implementation time is additional. Existing broad-polar validation remains historical; these 48 regional checks do not replace a new full-polar validation run.','']
    (ROOT/'docs/task_f_custom_polar.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__':main()
