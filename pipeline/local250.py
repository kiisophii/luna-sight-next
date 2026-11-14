"""Resumable 250 m south-polar grids, exact card18 horizons + actual core.js.

python pipeline/local250.py run --source-root <card18 checkout> --backend gpu
python pipeline/local250.py verify --source-root <card18 checkout>
"""
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS']:
    os.environ[name]='1'
import argparse
import atexit
import concurrent.futures as cf
import ctypes
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import random
import time

import numpy as np
import horizon as hz
import local_maps as lm

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/local250'
RAW=WORK/'raw'
OUT=ROOT/'web/data/local250'
GRID=dict(rows=41,cols=41,spacing_m=250,origin_e_m=-5000,origin_n_m=-5000,
          order='row-major, south to north and west to east; nodes, not cell averages')
FIRST=['SHACKLETON_RIM','ARTEMIS_HAWORTH','ARTEMIS_MALAPERT','CONNECTING_RIDGE']


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
    for attempt in range(30):
        try:tmp.replace(path);return
        except PermissionError:
            if attempt==29:raise
            time.sleep(.1)


def ordered_sites():
    sites=[s for s in read(ROOT/'web/data/sites.json') if s['lat']<=-75]
    assert len(sites)==16
    return [next(s for s in sites if s['id']==sid) for sid in FIRST]+[s for s in sites if s['id'] not in FIRST]


def grid_points(site):
    points=[]
    for n in range(-5000,5001,250):
        for e in range(-5000,5001,250):
            lat,lon=hz.destination(site['lat'],site['lon'],np.degrees(np.arctan2(e,n)),np.hypot(e,n))
            if e==n==0:lat,lon=site['lat'],site['lon']
            points.append(dict(index=len(points),e_m=e,n_m=n,lat=float(lat),lon=float(lon)))
    return points


def valid_checkpoint(path,key,p):
    try:
        if not lm.resume_valid(path,key,p['index']):return False
        r=read(path)
        return all(r[k]==p[k] for k in p)
    except (OSError,ValueError,KeyError,TypeError):return False


def validate_map(obj):
    assert obj['grid']==GRID and len(obj['points'])==1681
    assert obj['params']==lm.PARAMS and obj['frame']=='MOON_ME_DE421' and obj['radius_m']==hz.R_M
    assert obj['window']==dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824)
    assert obj['complete'] is True and obj['mock'] is False
    for p,want in zip(obj['points'],grid_points(obj['center'])):
        assert all(p[k]==v for k,v in want.items()) and lm.valid_metrics(p)
    baseline=read(ROOT/'web/data/metrics'/f"{obj['id']}.json")
    assert all(obj['points'][840][k]==baseline[k] for k in lm.METRICS),'Centre differs from production metrics'


def ensure_terrain(site,source):
    """Reuse expanded cache bytes; fetch only absent sources with original gates."""
    import fetch_polar as fp
    import polar_prefetch
    if not getattr(ensure_terrain,'patched',False):
        polar_prefetch.install(4);ensure_terrain.patched=True
    status_path=WORK/'terrain_status.json'
    status=read(status_path) if status_path.exists() else {}
    for res,gate in lm.GATES.items():
        key=f"{site['id']}/{res}"
        target=RAW/'polar'/str(res)/(site['id']+'.npz')
        old=source/'data/processed/card18/raw/polar'/str(res)/(site['id']+'.npz')
        if target.exists():
            with np.load(target,allow_pickle=False) as z:lm.validate_source_metadata(json.loads(str(z['metadata'])),site,gate)
            continue
        if status.get(key,{}).get('status')=='outside_source_coverage':continue
        if old.exists():
            with np.load(old,allow_pickle=False) as z:lm.validate_source_metadata(json.loads(str(z['metadata'])),site,gate)
            target.parent.mkdir(parents=True,exist_ok=True);os.link(old,target)
            status[key]=dict(status='ok',reused_from=str(old))
        elif lm.not_covered(source/'data/processed/card18/raw',site['id'],res):
            status[key]=dict(status='outside_source_coverage',evidence='existing card18 download status')
        else:
            print(f"FETCH {key} expanded storage radius {gate+16} km",flush=True)
            try:
                fp.fetch(site,res,(gate+16)*1000,RAW/'polar',allow_partial=True)
                status[key]=dict(status='ok')
            except fp.SourceCoverageError as e:
                status[key]=dict(status='outside_source_coverage',note=str(e))
            except ValueError as e:
                if 'no valid elevations' not in str(e):raise
                status[key]=dict(status='outside_source_coverage',note=str(e))
        write(status_path,status)
    (RAW/'global').mkdir(parents=True,exist_ok=True)
    for ppd in [64,16]:
        for suffix in ['img','lbl']:
            name=f'ldem_{ppd}_float.{suffix}';target=RAW/'global'/name
            if not target.exists():os.link(source/'data/raw/global'/name,target)


def prepare(site,source,backend):
    ensure_terrain(site,source)
    chain=[];descriptors=[];terrain=[]
    for res,gate in lm.GATES.items():
        p=RAW/'polar'/str(res)/(site['id']+'.npz')
        if p.exists():
            if backend=='cpu':
                d=lm.prepare_sampler(p,WORK/'shared',gate)
                descriptors.append(d);sampler=lm.load_sampler(d);digest=d['sha256']
            else:
                # One GPU coordinator needs no duplicate on-disk shared float64 raster.
                sampler=hz.PolarStereoSampler(p);digest=lm.sha_file(p)
            chain.append((sampler,gate))
            terrain.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=digest,resolution_m=res,gate_km=gate))
    globals_=[]
    for ppd in [64,16]:
        p=RAW/'global'/f'ldem_{ppd}_float.img';s=hz.GlobalCylSampler(p);chain.append((s,300.));globals_.append(str(p))
        terrain.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=lm.sha_file(p),label_sha256=lm.sha_file(p.with_suffix('.lbl')),
                            resolution_m=s.res_m,gate_km=None))
    paths=['web/js/core.js','web/data/ephem.bin','web/data/ephem.json','pipeline/horizon.py',
           'pipeline/local_maps.py','pipeline/local_metrics.mjs','pipeline/cache_metrics.mjs',
           'pipeline/local250.py','pipeline/local250_gpu.py','pipeline/local250_gpu.cu']
    provenance=dict(terrain_sources=terrain,files_sha256={p:lm.sha_file(ROOT/p) for p in paths},center=site,params=lm.PARAMS,grid=GRID)
    key=lm.fingerprint(provenance);provenance['input_key']=key
    return chain,descriptors,globals_,provenance,key


def gpu_preflight(gpu,chain,site,points,core):
    selected=[points[i] for i in [840,0,40,1640,1680]]
    got,gpu_s=gpu.points(selected);rows=[];cpu_s=0
    for p,g in zip(selected,got):
        local=dict(id=f"{site['id']}_LOCAL250_{p['index']}",lat=p['lat'],lon=p['lon'])
        start=time.perf_counter();c=hz.compute_horizon(p['lat'],p['lon'],chain,**lm.PARAMS);cpu_s+=time.perf_counter()-start
        gh,ch=hz.horizon_record(local,g),hz.horizon_record(local,c)
        gm,cm=core.metrics(local,gh),core.metrics(local,ch)
        delta=float(np.max(np.abs(np.asarray(g['mask'])-c['mask'])))
        assert delta<1e-6 and abs(g['h0_m']-c['h0_m'])<1e-6 and gm==cm,(site['id'],p['index'],delta,gm,cm)
        assert g['n_samples']==c['n_samples'] and g['dem_sources']==c['dem_sources']
        if p['index']==840:
            baseline=read(ROOT/'web/data/metrics'/f"{site['id']}.json")
            assert all(gm[k]==baseline[k] for k in lm.METRICS),f"Centre mismatch {site['id']}"
        rows.append(dict(index=p['index'],mask_max_abs_deg=delta,rounded_mask_equal=gh['mask']==ch['mask'],metrics_equal=True))
    result=dict(site=site['id'],gpu_s=gpu_s,cpu_s=cpu_s,rows=rows)
    write(WORK/'preflight'/f"{site['id']}.json",result)
    print('PREFLIGHT',site['id'],f'CPU {cpu_s:.2f}s GPU {gpu_s:.2f}s, metrics exact',flush=True)
    return result


def run_site(site,source,backend,jobs,limit=None):
    begin=time.time();sid=site['id']
    chain,descriptors,globals_,provenance,key=prepare(site,source,backend)
    folder=WORK/'checkpoints'/sid;folder.mkdir(parents=True,exist_ok=True)
    write(folder/'provenance.json',provenance)
    points=grid_points(site);todo=[p for p in points if not valid_checkpoint(folder/f"{p['index']:03d}.json",key,p)]
    cached=1681-len(todo);todo.sort(key=lambda p:p['index']!=840)
    if limit is not None:todo=todo[:limit]
    print(f'START {sid} {cached}/1681 cached backend={backend}',flush=True)
    completed=0;compute_start=time.time()
    def progress():
        elapsed=time.time()-compute_start;rate=completed/max(elapsed,.001)
        eta=(1681-cached-completed)/rate if rate else None
        state=dict(site=sid,completed=cached+completed,total=1681,new=completed,elapsed_s=elapsed,nodes_per_s=rate,
                   eta_s=eta,updated_utc=datetime.now(timezone.utc).isoformat())
        write(WORK/'progress.json',state)
        print(f"PROGRESS {sid} {cached+completed}/1681 {rate:.2f} nodes/s ETA {eta/60 if eta else 0:.1f} min",flush=True)
    if backend=='gpu':
        from local250_gpu import PolarGPU
        gpu=PolarGPU(chain)
        try:
            with lm.CoreMetrics(ROOT) as core:
                gpu_preflight(gpu,chain,site,points,core)
                compute_start=time.time()
                for first in range(0,len(todo),16):
                    batch=todo[first:first+16];horizons,gpu_s=gpu.points(batch)
                    for p,result in zip(batch,horizons):
                        local=dict(id=f"{sid}_LOCAL250_{p['index']}",lat=p['lat'],lon=p['lon'])
                        h=hz.horizon_record(local,result);m=core.metrics(local,h);assert lm.valid_metrics(m)
                        ground_res=next(s.res_m for s,_ in chain if np.isfinite(s.sample(np.array([p['lat']]),np.array([p['lon']]))[0]))
                        write(folder/f"{p['index']:03d}.json",dict(**p,input_key=key,horizon=h,metrics=m,ground_resolution_m=ground_res,elapsed_s=None,backend='gpu'))
                        completed+=1
                    if completed%128==0 or completed==len(todo):progress()
        finally:gpu.close()
    else:
        with cf.ProcessPoolExecutor(jobs,initializer=lm.init_worker,initargs=(descriptors,globals_,key,site,str(folder))) as executor:
            futures=[executor.submit(lm.compute_point,p) for p in todo]
            for f in cf.as_completed(futures):
                f.result();completed+=1
                if completed%32==0 or completed==len(todo):progress()
    complete=all(valid_checkpoint(folder/f"{p['index']:03d}.json",key,p) for p in points)
    if not complete:return dict(id=sid,complete=False,elapsed_s=time.time()-begin)
    public=[]
    for p in points:
        r=read(folder/f"{p['index']:03d}.json")
        public.append(dict(**p,**r['metrics'],h0_m=r['horizon']['h0_m'],ground_resolution_m=r['ground_resolution_m'],dem_sources=r['horizon']['dem_sources']))
    obj=dict(id=sid,center={k:site[k] for k in ['lat','lon']},grid=GRID,
             window=dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824),params=lm.PARAMS,
             frame='MOON_ME_DE421',radius_m=hz.R_M,provenance=provenance,points=public,complete=True,mock=False)
    validate_map(obj);write(OUT/f'{sid}.json',obj)
    elapsed=time.time()-begin;print(f'COMPLETE {sid} {elapsed:.1f}s centre exact',flush=True)
    return dict(id=sid,complete=True,elapsed_s=elapsed,new_nodes=completed,resumed=cached,backend=backend)


def verify():
    from verify_card18_local import PointDEM,trace_mask,load_ephemeris,evaluate_metrics,compare_metrics,check_sources
    from verify_card13_relay import RADIUS
    maps={p.stem:read(p) for p in sorted(OUT.glob('*.json'))}
    assert maps,'No complete maps'
    checked={}
    for obj in maps.values():
        validate_map(obj)
        hashes=dict(obj['provenance']['files_sha256'])
        for t in obj['provenance']['terrain_sources']:
            hashes[t['path']]=t['sha256']
            if 'label_sha256' in t:hashes[str(Path(t['path']).with_suffix('.lbl'))]=t['label_sha256']
        for p,expected in hashes.items():
            if p not in checked:checked[p]=lm.sha_file(ROOT/p)
            assert checked[p]==expected,f'Stale input: {p}'
    chosen=random.Random(202611150250).sample([(sid,i) for sid in sorted(maps) for i in range(1681)],5)
    eph=load_ephemeris(ROOT/'web/data');dist=np.geomspace(5,300000,8001);rows=[]
    for sid,i in chosen:
        obj=maps[sid];p=obj['points'][i];dem=PointDEM(dict(id=sid,**obj['center']),p,RAW)
        source_check=check_sources(dem,obj['provenance']['terrain_sources'],ROOT)
        ground=float(dem(np.array([p['lat']]),np.array([p['lon']]))[0])
        mask=trace_mask(p['lat'],p['lon'],ground,2,dem,np.arange(720)*.5,dist)
        m=evaluate_metrics(p['lat'],p['lon'],ground,mask,eph);comparison=compare_metrics(m,p)
        assert comparison['passed'],(sid,i,comparison)
        rows.append(dict(id=sid,index=i,comparison=comparison,mask=mask.tolist(),ground_m=ground,sources=source_check))
        print('VERIFY',sid,i,'PASS',flush=True)
    result=dict(seed=202611150250,n_complete_sites=len(maps),centre_exact_count=len(maps),points=rows,
        max_fraction_abs_diff_pp=max(p['comparison'][k]['absolute_difference_pp'] for p in rows for k in lm.METRICS[:3]),
        max_dark_abs_diff_h=max(p['comparison']['longest_dark_h']['absolute_difference_h'] for p in rows),
        output_sha256={sid:lm.sha_file(OUT/f'{sid}.json') for sid in maps},
        verifier_sha256={p:lm.sha_file(ROOT/p) for p in ['pipeline/local250.py','pipeline/verify_card18_local.py','pipeline/verify_card13_relay.py']})
    write(ROOT/'docs/local250_check.json',result)
    return result


def reserve_two_cores():
    """Windows processor-core masks: reserve two physical cores including siblings."""
    if os.name!='nt':return
    class Info(ctypes.Structure):
        _fields_=[('mask',ctypes.c_size_t),('relationship',ctypes.c_ulong),('data',ctypes.c_byte*16)]
    kernel=ctypes.windll.kernel32;size=ctypes.c_ulong()
    kernel.GetLogicalProcessorInformation(None,ctypes.byref(size))
    buffer=ctypes.create_string_buffer(size.value)
    if not kernel.GetLogicalProcessorInformation(buffer,ctypes.byref(size)):raise ctypes.WinError()
    info=ctypes.cast(buffer,ctypes.POINTER(Info));cores=[info[i].mask for i in range(size.value//ctypes.sizeof(Info)) if info[i].relationship==0]
    mask=0
    for value in cores[:max(1,len(cores)-2)]:mask|=value
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(ctypes.c_void_p(-1),mask):raise ctypes.WinError()
    print(f'CPU affinity {mask:#x}: using {max(1,len(cores)-2)}/{len(cores)} physical cores; two reserved',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['run','verify'])
    ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--backend',choices=['gpu','cpu'],default='gpu')
    ap.add_argument('--jobs',type=int,default=max(1,(os.cpu_count() or 2)-2));ap.add_argument('--site',action='append')
    ap.add_argument('--limit',type=int);a=ap.parse_args();WORK.mkdir(parents=True,exist_ok=True)
    if a.mode=='run' and os.name=='nt':
        import msvcrt
        lock=(WORK/'runner.lock').open('a+b');lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        atexit.register(lock.close)
    if os.name=='nt':
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        atexit.register(lambda:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
        reserve_two_cores()
    if a.mode=='verify':verify();return
    started=time.time();runs=[]
    for s in ordered_sites():
        if a.site and s['id'] not in a.site:continue
        try:r=run_site(s,a.source_root,a.backend,a.jobs,a.limit)
        except Exception as e:
            write(WORK/'failure.json',dict(site=s['id'],error=repr(e),time_utc=datetime.now(timezone.utc).isoformat()))
            raise
        runs.append(r);write(WORK/'run.json',dict(start_epoch=started,end_epoch=time.time(),backend=a.backend,jobs=a.jobs,runs=runs))
    if a.limit is None:verify()


if __name__=='__main__':main()
