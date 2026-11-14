"""Validate and publish the 24 unprofiled benchmark runs; print Markdown rows."""
import hashlib
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
raw=ROOT/'data/processed/texture_stall'
out=Path(__file__).resolve().parent
summaries=[]
for name in ['baseline','fixed','baseline_4k','fixed_4k']:
    data=json.loads((raw/f'{name}.json').read_text(encoding='utf-8'))
    assert len(data['runs'])==6
    if data['variant']=='fixed':
        assert data['source_sha256']==hashlib.sha256((ROOT/'web/js/globe3d.js').read_bytes()).hexdigest()
        assert data['worker_sha256']==hashlib.sha256((ROOT/'web/js/globe_color_worker.js').read_bytes()).hexdigest()
    for run in data['runs']:
        assert not run.get('error') and not run['errors']
        assert run['color']['width']==data['texture_size']
        assert not any('moon_color_8k' in p for p in run['cold_server_requests'])
        assert len(run['texture_responses'])==1
        assert run['texture_responses'][0]['bytes']==data['texture_bytes']
    for profile in ['desktop','laptop']:
        runs=[x for x in data['runs'] if x['profile']==profile]
        assert len(runs)==3
        values={
            'upload_ms':[max(u['ms'] for u in x['uploads'] if u['width']==data['texture_size']) for x in runs],
            'max_frame_gap_ms':[x['south']['interval_max_ms'] for x in runs],
            'max_long_task_ms':[max([t['duration'] for t in x['south']['long_tasks']],default=0) for x in runs],
            'rotation_fps':[x['rotation']['actual_render_rate'] for x in runs],
            'cold_transfer_MB':[x['cold_transfer_bytes']/1e6 for x in runs],
            'cold_ready_s':[x['cold']['atMs']/1000 for x in runs],
            'south_ready_s':[x['south']['duration_s'] for x in runs],
            'zoom_local_payload_MB':[x['zoom_local_payload_bytes']/1e6 for x in runs],
        }
        summary=dict(variant=name,profile=profile,texture_bytes=data['texture_bytes'],
            values={k:dict(median=statistics.median(v),min=min(v),max=max(v),runs=v) for k,v in values.items()},
            quality_levels=[x['south']['after']['quality'] for x in runs])
        summaries.append(summary)
        def fmt(k,dec=1):
            v=summary['values'][k]
            return f"{v['median']:.{dec}f} ({v['min']:.{dec}f}–{v['max']:.{dec}f})"
        print(f"| {profile} | {name} | {fmt('upload_ms')} | {fmt('max_frame_gap_ms')} | {fmt('max_long_task_ms',0)} | {fmt('rotation_fps')} | {fmt('cold_transfer_MB',3)} |")
    (out/f'{name}.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
for name in ['verification','network_check']:
    (out/f'{name}.json').write_bytes((raw/f'{name}.json').read_bytes())
(out/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n',encoding='utf-8')
