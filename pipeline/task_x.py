"""Resumable nonpolar 250 m grids using card9 CPU definitions and FP64 CUDA."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import atexit
import ctypes
import json
from pathlib import Path
import time
import numpy as np
import horizon as hz
import local_maps as lm
from local250 import GRID,grid_points,valid_checkpoint,read,write,reserve_two_cores

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_x'
OUT=ROOT/'web/data/local250'
PARAMS=lm.PARAMS_CARD9

def sites():
    values=[s for s in read(ROOT/'web/data/sites.json') if s['lat']>-75]
    assert len(values)==17
    return sorted(values,key=lambda s:s['id']!='CHANDRAYAAN3')

def validate(obj):
    assert obj['grid']==GRID and len(obj['points'])==1681
    assert obj['params']==PARAMS and obj['complete'] and not obj['mock']
    for p,w in zip(obj['points'],grid_points(obj['center'])):
        assert all(p[k]==v for k,v in w.items()) and lm.valid_metrics(p)
    base=read(ROOT/'web/data/metrics'/f"{obj['id']}.json")
    assert all(obj['points'][840][k]==base[k] for k in lm.METRICS),'Centre differs from production'

def prepare(site):
    chain=[];terrain=[]
    if abs(site['lat'])<60:
        p=WORK/'raw/sldem'/f"{site['id']}.npz"
        while not p.exists():
            print('WAIT_SOURCE',site['id'],flush=True);time.sleep(10)
        s=hz.LatLonWindowSampler(p)
        assert s.meta['radius_km']>=166 and s.meta['site_lat']==site['lat'] and s.meta['site_lon']==site['lon']
        chain.append((s,150.))
        terrain.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=lm.sha_file(p),resolution_m=round(s.res_m,1),gate_km=150.,metadata=s.meta))
    for ppd in (64,16):
        p=ROOT/'data/processed/local250/raw/global'/f'ldem_{ppd}_float.img'
        s=hz.GlobalCylSampler(p);chain.append((s,300.))
        terrain.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=lm.sha_file(p),label_sha256=lm.sha_file(p.with_suffix('.lbl')),resolution_m=s.res_m,gate_km=None))
    paths=['web/data/sites.json','web/data/ephem.bin','web/data/ephem.json','web/js/core.js','pipeline/horizon.py',
        'pipeline/local250.py','pipeline/local_maps.py','pipeline/local_metrics.mjs','pipeline/cache_metrics.mjs',
        'pipeline/task_x.py','pipeline/task_x_gpu.py','pipeline/task_x_gpu.cu']
    provenance=dict(terrain_sources=terrain,files_sha256={p:lm.sha_file(ROOT/p) for p in paths},center=site,params=PARAMS,grid=GRID)
    key=lm.fingerprint(provenance);provenance['input_key']=key
    return chain,provenance,key

def preflight(site,chain,gpu,core,points):
    selected=[points[i] for i in (840,0,40,1640,1680)]
    got,gpu_s=gpu.points(selected);rows=[];cpu_s=0
    for p,g in zip(selected,got):
        start=time.perf_counter();c=hz.compute_horizon(p['lat'],p['lon'],chain,**PARAMS);cpu_s+=time.perf_counter()-start
        local=dict(id=f"{site['id']}_LOCAL250_{p['index']}",lat=p['lat'],lon=p['lon'])
        gh,ch=hz.horizon_record(local,g),hz.horizon_record(local,c)
        gm,cm=core.metrics(local,gh),core.metrics(local,ch)
        delta=float(np.max(np.abs(np.asarray(g['mask'])-c['mask'])))
        assert delta<1e-6 and abs(g['h0_m']-c['h0_m'])<1e-6 and gm==cm,(site['id'],p['index'],delta,gm,cm)
        assert g['n_samples']==c['n_samples'] and g['dem_sources']==c['dem_sources']
        if p['index']==840:
            base=read(ROOT/'web/data/metrics'/f"{site['id']}.json")
            assert all(gm[k]==base[k] for k in lm.METRICS),site['id']
        rows.append(dict(index=p['index'],mask_max_abs_deg=delta,rounded_mask_equal=gh['mask']==ch['mask'],metrics_equal=True))
    result=dict(site=site['id'],cpu_s=cpu_s,gpu_s=gpu_s,rows=rows)
    write(WORK/'preflight'/f"{site['id']}.json",result)
    print('PREFLIGHT',site['id'],f'CPU {cpu_s:.2f}s GPU {gpu_s:.2f}s',flush=True)

def run(site,limit=None):
    from task_x_gpu import NonpolarGPU
    begin=time.time();sid=site['id'];chain,provenance,key=prepare(site)
    folder=WORK/'checkpoints'/sid;folder.mkdir(parents=True,exist_ok=True)
    write(folder/'provenance.json',provenance)
    points=grid_points(site)
    todo=[p for p in points if not valid_checkpoint(folder/f"{p['index']:04d}.json",key,p)]
    cached=1681-len(todo);todo.sort(key=lambda p:p['index']!=840)
    if limit is not None:todo=todo[:limit]
    print('START',sid,cached,'cached',flush=True)
    gpu=NonpolarGPU(chain);completed=0
    try:
        with lm.CoreMetrics(ROOT) as core:
            preflight(site,chain,gpu,core,points)
            start=time.time()
            for first in range(0,len(todo),16):
                batch=todo[first:first+16];results,_=gpu.points(batch)
                for p,h in zip(batch,results):
                    local=dict(id=f"{sid}_LOCAL250_{p['index']}",lat=p['lat'],lon=p['lon'])
                    record=hz.horizon_record(local,h);metrics=core.metrics(local,record);assert lm.valid_metrics(metrics)
                    ground_res=next(s.res_m for s,_ in chain if np.isfinite(s.sample(np.array([p['lat']]),np.array([p['lon']]))[0]))
                    write(folder/f"{p['index']:04d}.json",dict(**p,input_key=key,horizon=record,metrics=metrics,ground_resolution_m=ground_res,backend='gpu'))
                    completed+=1
                if completed%128==0 or completed==len(todo):
                    elapsed=time.time()-start;rate=completed/max(elapsed,.001)
                    state=dict(site=sid,completed=cached+completed,total=1681,nodes_per_s=rate,eta_s=(1681-cached-completed)/rate,elapsed_s=elapsed)
                    write(WORK/'progress.json',state)
                    print('PROGRESS',sid,cached+completed,'/1681',f'{rate:.2f} node/s ETA {state["eta_s"]/60:.1f} min',flush=True)
    finally:gpu.close()
    if not all(valid_checkpoint(folder/f"{p['index']:04d}.json",key,p) for p in points):
        return dict(id=sid,complete=False,elapsed_s=time.time()-begin)
    public=[]
    for p in points:
        r=read(folder/f"{p['index']:04d}.json")
        public.append(dict(**p,**r['metrics'],h0_m=r['horizon']['h0_m'],ground_resolution_m=r['ground_resolution_m'],dem_sources=r['horizon']['dem_sources']))
    obj=dict(id=sid,center={k:site[k] for k in ('lat','lon')},grid=GRID,params=PARAMS,
        window=dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824),frame='MOON_ME_DE421',radius_m=hz.R_M,
        provenance=provenance,points=public,complete=True,mock=False)
    validate(obj);write(OUT/f'{sid}.json',obj)
    result=dict(id=sid,complete=True,elapsed_s=time.time()-begin,new_nodes=completed,resumed=cached)
    print('COMPLETE',sid,result['elapsed_s'],flush=True)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--site',action='append');ap.add_argument('--limit',type=int);a=ap.parse_args()
    WORK.mkdir(parents=True,exist_ok=True);reserve_two_cores()
    if os.name=='nt':
        import msvcrt
        lock=(WORK/'runner.lock').open('a+b');lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);atexit.register(lock.close)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        atexit.register(lambda:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
    runs=[];start=time.time()
    for site in sites():
        if a.site and site['id'] not in a.site:continue
        runs.append(run(site,a.limit));write(WORK/'run.json',dict(start_epoch=start,end_epoch=time.time(),runs=runs))

if __name__=='__main__':main()
