"""Card23: resumable 100 m neighbourhood grids with actual hourly core.js metrics."""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):
    os.environ[_key]='1'
import argparse
import concurrent.futures as cf
import ctypes
import json
from pathlib import Path
import time
import numpy as np
import horizon as hz
import run_horizons as rh
from local_maps import CoreMetrics,PARAMS,METRICS,sha_file,fingerprint,valid_metrics

ROOT=Path(__file__).resolve().parents[1]
RADII=(100,300,500)

def grid_points(site):
    points=[]
    for north in range(-500,501,100):
        for east in range(-500,501,100):
            lat,lon=hz.destination(site['lat'],site['lon'],np.degrees(np.arctan2(east,north)),np.hypot(east,north))
            if east==north==0:lat,lon=site['lat'],site['lon']
            points.append(dict(index=len(points),e_m=east,n_m=north,lat=float(lat),lon=float(lon)))
    return points

def summarize(points):
    output={}
    for radius in RADII:
        selected=[p for p in points if np.hypot(p['e_m'],p['n_m'])<=radius+1e-7]
        stats=dict(radius_m=radius,n=len(selected))
        for metric in METRICS:
            a=np.array([p[metric] for p in selected]);q=np.quantile(a,[.1,.5,.9],method='linear')
            stats[metric]=dict(min=float(a.min()),max=float(a.max()),p10=float(q[0]),median=float(q[1]),p90=float(q[2]))
        output[str(radius)]=stats
    return output

def check_center(actual,expected):
    differences={k:actual[k]-expected[k] for k in METRICS}
    if any(differences.values()):raise ValueError('Catalogue centre mismatch: '+str(differences))
    return dict(matches=True,differences=differences)

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
    for attempt in range(30):
        try:tmp.replace(path);return
        except PermissionError:
            if attempt==29:raise
            time.sleep(.1)

def valid_checkpoint(path,key,point):
    try:
        r=read(path);h=r['horizon']
        return r['input_key']==key and r['point']==point and valid_metrics(r['metrics']) and len(h['mask'])==720 and np.isfinite(h['mask']).all() and np.isfinite(h['h0_m']) and h['engine']['n_missing_samples']==0
    except (OSError,ValueError,KeyError,TypeError):return False

def build_chain(site,raw):
    # User decision: retain each site's existing catalogue method/terrain chain.
    return rh.build_chain(site,raw,300.)

def catalogue_params(site):
    h=read(ROOT/'web/data/horizon'/f"{site['id']}.json");e=h['engine']
    if h['lat']!=site['lat'] or h['lon']!=site['lon'] or h['az_step_deg']!=.5 or h['obs_height_m']!=2:
        raise ValueError('Catalogue horizon identity/geometry differs')
    return dict(min_km=e['min_km'],max_km=e['max_km'],n_steps=e['n_steps'],obs_height_m=2.,
                early_stop=e.get('early_stop',True),hmax_m=e.get('hmax_m',hz.HMAX_M))

def run_site(site,raw,work,out,common,limit=None):
    if os.name=='nt':
        k=ctypes.WinDLL('kernel32');k.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.SetPriorityClass(ctypes.c_void_p(-1),0x4000)
    start=time.monotonic();sid=site['id'];chain=build_chain(site,raw);params=catalogue_params(site)
    terrain=[]
    for sampler,gate in chain:
        p=Path(sampler.path) if hasattr(sampler,'path') else raw/'global'/Path(sampler.data.filename).name
        rel=p.relative_to(ROOT).as_posix()
        item=dict(path=rel,sha256=common.get(rel) or sha_file(p),gate_km=gate,resolution_m=sampler.res_m)
        if p.suffix=='.img':item['label_sha256']=common[p.with_suffix('.lbl').relative_to(ROOT).as_posix()]
        terrain.append(item)
    provenance=dict(center=site,params=params,terrain_sources=terrain,files_sha256=common,
        baseline_horizon_sha256=sha_file(ROOT/f'web/data/horizon/{sid}.json'),
        baseline_metrics_sha256=sha_file(ROOT/f'web/data/metrics/{sid}.json'))
    key=fingerprint(provenance);provenance['input_key']=key
    points=grid_points(site);folder=work/sid;folder.mkdir(parents=True,exist_ok=True)
    todo=[p for p in points if not valid_checkpoint(folder/f"{p['index']:03d}.json",key,p)]
    if limit is not None:todo=todo[:limit]
    with CoreMetrics(ROOT) as core:
        for count,p in enumerate(todo,1):
            local=dict(site,lat=p['lat'],lon=p['lon'])
            result=hz.compute_horizon(p['lat'],p['lon'],chain,**params)
            if result['n_missing']:raise ValueError(sid+': missing terrain')
            h=hz.horizon_record(local,result);metrics=core.metrics(local,h)
            if not valid_metrics(metrics):raise ValueError(sid+': invalid core metrics')
            resolution=next(s.res_m for s,_ in chain if np.isfinite(s.sample(np.array([p['lat']]),np.array([p['lon']])))[0])
            write(folder/f"{p['index']:03d}.json",dict(point=p,input_key=key,horizon=h,metrics=metrics,ground_resolution_m=resolution))
            if count%30==0:print(f'{sid}: +{count}/{len(todo)} nodes',flush=True)
    if not all(valid_checkpoint(folder/f"{p['index']:03d}.json",key,p) for p in points):
        return dict(id=sid,complete=False,elapsed_s=time.monotonic()-start)
    records=[read(folder/f"{p['index']:03d}.json") for p in points]
    public=[dict(**r['point'],**r['metrics'],h0_m=r['horizon']['h0_m'],ground_resolution_m=r['ground_resolution_m'],dem_sources=r['horizon']['dem_sources']) for r in records]
    baseline=read(ROOT/'web/data/metrics'/f'{sid}.json')
    centre=check_center(public[60],baseline)
    centre['metrics_sha256']=sha_file(ROOT/'web/data/metrics'/f'{sid}.json')
    output=dict(id=sid,center=dict(lat=site['lat'],lon=site['lon']),frame='MOON_ME_DE421',radius_m=hz.R_M,
        grid=dict(rows=11,cols=11,spacing_m=100,origin_e_m=-500,origin_n_m=-500),
        window=dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824),params=params,
        points=public,radii=summarize(public),center_check=centre,provenance=provenance,complete=True,mock=False)
    validate(output);write(out/f'{sid}.json',output)
    return dict(id=sid,complete=True,computed_nodes=len(todo),elapsed_s=time.monotonic()-start)

def validate(record):
    points=record['points'];expected=grid_points(dict(id=record['id'],**record['center']))
    if len(points)!=121 or not record['complete'] or record['mock']:raise ValueError('Incomplete uncertainty map')
    if record['window']!=dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824):raise ValueError('Wrong ephemeris window')
    if record['params']!=catalogue_params(dict(id=record['id'],**record['center'])) or record['frame']!='MOON_ME_DE421':raise ValueError('Wrong physical parameters')
    for p,e in zip(points,expected):
        if any(p[k]!=e[k] for k in e) or not valid_metrics(p):raise ValueError('Invalid grid/metrics')
    if record['radii']!=summarize(points):raise ValueError('Invalid spatial statistics')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workers',type=int,default=6);ap.add_argument('--site',action='append')
    ap.add_argument('--polar-only',action='store_true');ap.add_argument('--nonpolar-only',action='store_true')
    ap.add_argument('--limit',type=int);a=ap.parse_args()
    if not 1<=a.workers<=6:ap.error('Use 1..6 workers per user CPU budget')
    sites=read(ROOT/'web/data/sites.json');sites.sort(key=lambda s:s['lat']>-75)
    if a.site:sites=[s for s in sites if s['id'] in a.site]
    if a.polar_only:sites=[s for s in sites if s['lat']<=-75]
    if a.nonpolar_only:sites=[s for s in sites if s['lat']>-75]
    raw=ROOT/'data/raw';work=ROOT/'data/processed/uncertainty';out=ROOT/'web/data/uncertainty'
    paths=['pipeline/horizon.py','pipeline/run_horizons.py','pipeline/coordinate_uncertainty.py','pipeline/local_maps.py','pipeline/local_metrics.mjs','pipeline/cache_metrics.mjs','web/js/core.js','web/data/ephem.bin','web/data/ephem.json']
    for ppd in [64,16]:paths += [f'data/raw/global/ldem_{ppd}_float.{ext}' for ext in ['img','lbl']]
    common={p:sha_file(ROOT/p) for p in paths}
    started=time.time();results=[]
    with cf.ProcessPoolExecutor(a.workers) as executor:
        futures={executor.submit(run_site,s,raw,work,out,common,a.limit):s['id'] for s in sites}
        for f in cf.as_completed(futures):
            try:r=f.result()
            except Exception as exc:r=dict(id=futures[f],complete=False,error=str(exc))
            results.append(r);write(work/'run_summary.json',dict(workers=a.workers,results=results,elapsed_s=time.time()-started))
            print(json.dumps(r),flush=True)
    return 0 if all(r['complete'] for r in results) else 1
if __name__=='__main__':raise SystemExit(main())
