"""Validate paired runs and publish raw mesh/zoom evidence and summary."""
import hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
raw=ROOT/'data/processed/mesh_stall';out=Path(__file__).resolve().parent
summary=[]
for variant in ['baseline','fixed']:
    doc=json.loads((raw/f'{variant}.json').read_text())
    assert len(doc['runs'])==6
    if variant=='fixed':assert doc['source_sha256']==hashlib.sha256((ROOT/'web/js/globe3d.js').read_bytes()).hexdigest()
    for r in doc['runs']:
        assert not r.get('error') and not r['errors']
        assert r['color']['width']==8192
        assert all(c['empty_rendered_frames']==0 for c in r['zoom_cycles'])
    for profile in ['desktop','laptop']:
        runs=[r for r in doc['runs'] if r['profile']==profile]
        phases=[('south',[r['south'] for r in runs])]
        for i,name in enumerate(['detail_first','whole_again','detail_revisit']):phases.append((name,[r['zoom_cycles'][i] for r in runs]))
        for name,items in phases:
            values={
                'p95_ms':[p['interval_p95_ms'] for p in items],
                'max_gap_ms':[p['interval_max_ms'] for p in items],
                'long_tasks':[len(p['long_tasks']) for p in items],
                'max_task_ms':[max([t['duration'] for t in p['long_tasks']],default=0) for p in items],
                'settled_s':[p['duration_s'] for p in items],
            }
            row=dict(variant=variant,profile=profile,phase=name,
                values={k:dict(median=statistics.median(v),min=min(v),max=max(v),runs=v) for k,v in values.items()},
                quality=[p['after']['quality'] for p in items],tiles=[p['after']['tiles'] for p in items],triangles=[p['after']['triangles'] for p in items])
            summary.append(row)
            print(variant,profile,name,{k:round(v['median'],2) for k,v in row['values'].items()},'quality',row['quality'],'tiles',row['tiles'])
    (out/f'{variant}.json').write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8')
for name in ['baseline_geometry','fixed_geometry']:(out/f'{name}.json').write_bytes((raw/f'{name}.json').read_bytes())
(out/'diagnostic.json').write_bytes((raw/'profile/fixed_4k.json').read_bytes())
(out/'diagnostic_cpu.json').write_bytes((raw/'profile/fixed_4k_laptop_1_cpu.json').read_bytes())
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
