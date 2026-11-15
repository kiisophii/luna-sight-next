"""Task B: standalone full nonpolar uncertainty check; no repository imports.

Source acquisition is separate. Numerical code imports only NumPy, optional CuPy,
and PROJ; the producer's readers, horizon engine and metric functions are unused.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse
import atexit
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import numpy as np
from pyproj import Geod

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_b'
R=1737400.
GEOD=Geod(a=R,b=R)
KEYS=('sun_frac','earth_frac','both_frac','longest_dark_h')

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(value,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
    temp.replace(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def bilinear(xp,array,row,col,wrap=False):
    ny,nx=array.shape
    valid=xp.isfinite(row)&xp.isfinite(col)&(row>=0)&(row<=ny-1)
    if not wrap:valid&=(col>=0)&(col<=nx-1)
    y=xp.clip(xp.floor(row).astype(xp.int64),0,ny-2)
    x=xp.floor(col).astype(xp.int64)
    if not wrap:x=xp.clip(x,0,nx-2)
    a=row-y;b=col-x
    value=(1-a)*((1-b)*array[y,x%nx]+b*array[y,(x+1)%nx])+a*((1-b)*array[y+1,x%nx]+b*array[y+1,(x+1)%nx])
    return xp.where(valid,value,xp.nan)

class Terrain:
    def __init__(self,site,raw,global_root,xp):
        self.sources=[];self.manifest=[];self.xp=xp
        if abs(site['lat'])<60:
            p=raw/'sldem'/f"{site['id']}.npz"
            with np.load(p,allow_pickle=False) as z:
                meta=json.loads(str(z['meta']));lat=z['lat'];lon=z['lon_unwrapped'];h=z['height_m']
                assert meta['radius_km']>=151 and meta['site_lat']==site['lat'] and meta['site_lon']==site['lon']
                assert np.all(np.diff(lat)<0) and np.all(np.diff(lon)>0) and np.isfinite(h).all()
                self.sources.append(dict(kind='window',array=xp.asarray(h),lat0=float(lat[0]),lon0=float(lon[0]),
                    dlat=float((lat[0]-lat[-1])/(len(lat)-1)),dlon=float((lon[-1]-lon[0])/(len(lon)-1)),
                    mid=float((lon[0]+lon[-1])/2),gate_m=150000.))
            self.manifest.append(dict(path=str(p),sha256=sha(p),metadata=meta,gate_m=150000.))
        for ppd in (64,16):
            p=global_root/f'ldem_{ppd}_float.img';label=p.with_suffix('.lbl')
            text=label.read_text(encoding='latin-1')
            def value(k):return float(re.search(r'^\s*'+k+r'\s*=\s*([-+0-9.eE]+)',text,re.M)[1])
            ny,nx=int(value('LINES')),int(value('LINE_SAMPLES'))
            assert p.stat().st_size==ny*nx*4
            arr=np.memmap(p,dtype='<f4',shape=(ny,nx),mode='r')
            self.sources.append(dict(kind='global',array=xp.asarray(arr),ppd=value('MAP_RESOLUTION'),
                lpo=value('LINE_PROJECTION_OFFSET'),spo=value('SAMPLE_PROJECTION_OFFSET'),
                clon=value('CENTER_LONGITUDE'),scale=value('SCALING_FACTOR')*1000,gate_m=300000.))
            self.manifest.append(dict(path=str(p),sha256=source_hash(p),label_sha256=source_hash(label),gate_m=300000.))

    def sample(self,xp,lat,lon,d):
        out=xp.full(lat.shape,xp.nan,dtype=xp.float64)
        for s in self.sources:
            missing=xp.isnan(out)&(d<=s['gate_m']+1e-7)
            if not bool(xp.any(missing)):continue
            if s['kind']=='window':
                lu=(lon-s['mid']+180)%360+s['mid']-180
                v=bilinear(xp,s['array'],(s['lat0']-lat)/s['dlat'],(lu-s['lon0'])/s['dlon'])
            else:
                row=xp.clip(s['lpo']-lat*s['ppd'],0,s['array'].shape[0]-1)
                col=s['spo']+((lon%360)-s['clon'])*s['ppd']
                v=bilinear(xp,s['array'],row,col,True)*s['scale']
            out=xp.where(missing,v,out)
        return out

_hash_cache={}
def source_hash(path):
    stamp=(str(path),path.stat().st_size,path.stat().st_mtime_ns)
    if stamp not in _hash_cache:_hash_cache[stamp]=sha(path)
    return _hash_cache[stamp]

def frame(lat,lon):
    la,lo=np.radians([lat,lon]);up=np.array([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)])
    east=np.array([-np.sin(lo),np.cos(lo),0.]);return up,east,np.cross(up,east)

def horizon(xp,lat,lon,terrain):
    """Full Cartesian great-circle march, no producer early-stop shortcut."""
    ground=float(terrain.sample(xp,xp.asarray([lat]),xp.asarray([lon]),xp.asarray([0.]))[0])
    assert np.isfinite(ground)
    up,east,north=[xp.asarray(v) for v in frame(lat,lon)]
    d=xp.asarray(np.geomspace(200.,300000.,4001));ct=xp.cos(d/R)[None,:];st=xp.sin(d/R)[None,:]
    results=[]
    for first in range(0,720,120):
        az=xp.radians(xp.arange(first,first+120,dtype=xp.float64)*.5)[:,None]
        direction=xp.cos(az)[...,None]*north+xp.sin(az)[...,None]*east
        pos=ct[...,None]*up+st[...,None]*direction
        la=xp.degrees(xp.arctan2(pos[...,2],xp.hypot(pos[...,0],pos[...,1])))
        lo=xp.degrees(xp.arctan2(pos[...,1],pos[...,0]))
        heights=terrain.sample(xp,la,lo,xp.broadcast_to(d,la.shape))
        if not bool(xp.all(xp.isfinite(heights))):raise ValueError('Missing DEM sample')
        rt=R+heights
        angles=xp.degrees(xp.arctan2(rt*ct-(R+ground+2),rt*st))
        results.append(xp.max(angles,axis=1))
    mask=xp.concatenate(results)
    return ground,mask if xp is np else xp.asnumpy(mask)

def cpu_reference(lat,lon,terrain):
    """Separate PROJ destinations and ECEF vector subtraction, same full ranges."""
    up,east,north=frame(lat,lon)
    ground=float(terrain.sample(np,np.array([lat]),np.array([lon]),np.array([0.]))[0])
    observer=up*(R+ground+2);dist=np.geomspace(200.,300000.,4001);masks=[]
    for first in range(0,720,60):
        dd=np.broadcast_to(dist,(60,len(dist))).copy()
        az=np.broadcast_to(np.arange(first,first+60)[:,None]*.5,dd.shape).copy()
        lo,la,_=GEOD.fwd(np.full(dd.shape,lon),np.full(dd.shape,lat),az,dd)
        heights=terrain.sample(np,la,lo,dd)
        assert np.isfinite(heights).all()
        la,lo=np.radians(la),np.radians(lo)
        ray=np.stack([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)],axis=-1)*(R+heights)[...,None]-observer
        vertical=ray@up;horizontal=np.hypot(ray@east,ray@north)
        masks.extend(np.degrees(np.arctan2(vertical,horizontal)).max(axis=1).tolist())
    return ground,np.asarray(masks)

def dark_run(sun):
    edges=np.diff(np.r_[0,~np.asarray(sun,dtype=bool),0].astype(np.int8))
    return int((np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)).max(initial=0))

def metrics(lat,lon,ground,mask,ephem):
    up,east,north=frame(lat,lon);observer=up*(R+ground+2)/1000
    bits=[]
    for offset in (0,3):
        ray=ephem[:,offset:offset+3]-observer
        el=np.degrees(np.arctan2(ray@up,np.hypot(ray@east,ray@north)))
        az=np.degrees(np.arctan2(ray@east,ray@north))%360
        position=az*2;lower=np.floor(position).astype(int)%720;weight=position-np.floor(position)
        line=mask[lower]*(1-weight)+mask[(lower+1)%720]*weight
        bits.append(el>=line if offset==0 else el>line)
    sun,earth=bits
    return dict(sun_frac=float(sun.mean()),earth_frac=float(earth.mean()),both_frac=float((sun&earth).mean()),longest_dark_h=dark_run(sun))

def ranges(points):
    result={}
    for radius in (100,300,500):
        selected=[p for p in points if p['e_m']**2+p['n_m']**2<=radius**2]
        record=dict(n_nodes=len(selected))
        for k in KEYS:
            values=np.asarray([p[k] for p in selected])
            record[k]=dict(zip(('min','max','p10','median','p90'),map(float,[values.min(),values.max(),*np.percentile(values,[10,50,90])])) )
        result[str(radius)]=record
    return result

def report_path(n_sites):
    return ROOT/'docs/task_b_full_check.json' if n_sites==17 else WORK/'partial_report.json'

def points(site,record):
    out=[]
    assert len(record['nodes'])==121
    for i,p in enumerate(record['nodes']):
        assert all(np.isfinite(p[k]) for k in (*KEYS,'lat','lon','h0_m'))
        assert all(0<=p[k]<=1 for k in KEYS[:3]) and p['both_frac']<=min(p['sun_frac'],p['earth_frac'])
        assert 0<=p['longest_dark_h']<=43824 and int(p['longest_dark_h'])==p['longest_dark_h']
        e,n=(i%11-5)*100,(i//11-5)*100
        lon,lat,_=GEOD.fwd(site['lon'],site['lat'],float(np.degrees(np.arctan2(e,n))),float(np.hypot(e,n)))
        if e==n==0:lat,lon=site['lat'],site['lon']
        assert (p['index'],p['e_m'],p['n_m'])==(i,e,n)
        _,_,error=GEOD.inv(lon,lat,p['lon'],p['lat']);assert abs(error)<.001
        out.append(dict(index=i,e_m=e,n_m=n,lat=lat,lon=lon))
    return out

def resources():
    if os.name!='nt':return
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    atexit.register(lambda:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
    class Info(ctypes.Structure):
        _fields_=[('mask',ctypes.c_size_t),('relationship',ctypes.c_ulong),('data',ctypes.c_byte*16)]
    k=ctypes.windll.kernel32;size=ctypes.c_ulong();k.GetLogicalProcessorInformation(None,ctypes.byref(size))
    buf=ctypes.create_string_buffer(size.value)
    if not k.GetLogicalProcessorInformation(buf,ctypes.byref(size)):raise ctypes.WinError()
    info=ctypes.cast(buf,ctypes.POINTER(Info));cores=[info[i].mask for i in range(size.value//ctypes.sizeof(Info)) if info[i].relationship==0]
    mask=0
    for c in cores[:max(1,len(cores)-2)]:mask|=c
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(ctypes.c_void_p(-1),mask):raise ctypes.WinError()
    print('Reserved two physical CPU cores; affinity',hex(mask),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['benchmark','run'])
    ap.add_argument('--raw',type=Path,default=ROOT/'data/raw');ap.add_argument('--global-root',type=Path,required=True)
    ap.add_argument('--site',action='append');ap.add_argument('--backend',choices=['gpu','cpu'],default='gpu');a=ap.parse_args()
    resources();WORK.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        import msvcrt
        lock=(WORK/'runner.lock').open('a+b');lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);atexit.register(lock.close)
    xp=np
    if a.backend=='gpu':
        import cupy as xp
    meta=read(ROOT/'web/data/ephem.json')
    assert meta['n']==43824 and meta['step_h']==1 and meta['start']=='2026-01-01T00:00:00Z' and not meta['mock']
    assert meta['frame']=='MOON_ME_DE421' and meta['units']=='km'
    eph=np.fromfile(ROOT/'web/data/ephem.bin',dtype='<f4').reshape(43824,6).astype(float)
    assert np.isfinite(eph).all()
    sites=[s for s in read(ROOT/'web/data/sites.json') if s['lat']>-75];assert len(sites)==17
    if a.site:sites=[s for s in sites if s['id'] in a.site]
    started=time.time();summaries=[];all_rows=[];all_failures=[]
    for site in sites:
        sid=site['id'];begin=time.time();path=ROOT/'web/data/uncertainty'/f'{sid}.json';record=read(path)
        assert record['params']==dict(min_km=.2,max_km=300.,n_steps=4000,obs_height_m=2.) and record['complete'] and not record['mock']
        assert record['frame']=='MOON_ME_DE421' and record['radius_m']==R
        assert record['window']==dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824)
        assert record['center']=={k:site[k] for k in ('lat','lon')}
        pp=points(site,record)
        source=a.raw/'sldem'/f'{sid}.npz'
        if abs(site['lat'])<60 and not source.exists():
            print('WAIT source',sid,flush=True);deadline=time.time()+3600
            while not source.exists():
                if time.time()>deadline:raise TimeoutError(str(source))
                time.sleep(5)
        gpu=Terrain(site,a.raw,a.global_root,xp);cpu=Terrain(site,a.raw,a.global_root,np)
        identity=dict(sources=gpu.manifest,record_sha256=sha(path),code_sha256=sha(Path(__file__)),backend=a.backend,
            ephem_sha256=source_hash(ROOT/'web/data/ephem.bin'),ephem_meta_sha256=source_hash(ROOT/'web/data/ephem.json'),site=site)
        fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        preflight=[]
        for i in (60,0):
            p=pp[i];t=time.perf_counter();hg,mg=horizon(xp,p['lat'],p['lon'],gpu);gpu_s=time.perf_counter()-t
            t=time.perf_counter();hc,mc=cpu_reference(p['lat'],p['lon'],cpu);cpu_s=time.perf_counter()-t
            delta=float(np.max(np.abs(mg-mc)));gm=metrics(p['lat'],p['lon'],round(hg,2),np.round(mg,4),eph)
            cm=metrics(p['lat'],p['lon'],round(hc,2),np.round(mc,4),eph)
            assert delta<1e-6 and abs(hg-hc)<1e-6 and gm==cm,(sid,i,delta,gm,cm)
            preflight.append(dict(index=i,angle_max_abs_deg=delta,gpu_s=gpu_s,cpu_reference_s=cpu_s,rounded_metrics_equal=True))
        write(WORK/'preflight'/f'{sid}.json',preflight)
        print('PREFLIGHT',sid,preflight,flush=True)
        if a.mode=='benchmark':continue
        folder=WORK/'nodes'/sid;write(folder/'identity.json',identity);values=[];raw_values=[];new=0;loop_start=time.time()
        for p,published in zip(pp,record['nodes']):
            cp=folder/f"{p['index']:03d}.json"
            try:cached=read(cp) if cp.exists() else {}
            except (OSError,ValueError):cached={}
            intact=(cached.get('fingerprint')==fingerprint and len(cached.get('mask',[]))==720
                and np.isfinite(cached.get('mask',[])).all()
                and all(np.isfinite(cached.get(mode,{}).get(k,np.nan)) for mode in ('raw','rounded') for k in KEYS))
            if not intact:
                h,mask=horizon(xp,p['lat'],p['lon'],gpu)
                raw=metrics(p['lat'],p['lon'],h,mask,eph)
                rounded=metrics(p['lat'],p['lon'],round(h,2),np.round(mask,4),eph)
                cached=dict(**p,fingerprint=fingerprint,ground_m=h,mask=mask.tolist(),raw=raw,rounded=rounded)
                write(cp,cached);new+=1
            assert all(cached[k]==p[k] for k in p)
            values.append(dict(**p,**cached['rounded']));raw_values.append(dict(**p,**cached['raw']))
            differences={k:cached['rounded'][k]-published[k] for k in KEYS}
            raw_diff={k:cached['raw'][k]-published[k] for k in KEYS}
            fails=[k for k in KEYS[:3] if abs(differences[k])*100>1+1e-12]
            row=dict(id=sid,index=p['index'],e_m=p['e_m'],n_m=p['n_m'],lat=p['lat'],lon=p['lon'],
                published={k:published[k] for k in KEYS},independent=cached['rounded'],unrounded=cached['raw'],differences=differences,unrounded_differences=raw_diff,failed_metrics=fails)
            all_rows.append(row)
            if fails:all_failures.append(row)
            if (p['index']+1)%16==0 or p['index']==120:
                rate=new/max(time.time()-loop_start,.001)
                print('PROGRESS',sid,p['index']+1,'/121',round(rate,2),'nodes/s',flush=True)
                write(WORK/'progress.json',dict(site=sid,completed=p['index']+1,total=121,nodes_per_s=rate,eta_s=(120-p['index'])/rate if rate else None))
        summary=ranges(values);range_rows=[]
        for radius,group in summary.items():
            assert group['n_nodes']==record['ranges'][radius]['n_nodes']
            for k in KEYS:
                for statistic,v in group[k].items():
                    ref=record['ranges'][radius][k][statistic];assert np.isfinite(ref);delta=v-ref
                    row=dict(radius_m=int(radius),metric=k,statistic=statistic,independent=v,published=ref,difference=delta)
                    range_rows.append(row)
                    if k in KEYS[:3] and abs(delta)*100>1+1e-12:all_failures.append(dict(id=sid,**row))
        own=[p for p in all_rows if p['id']==sid]
        item=dict(id=sid,n_nodes=121,elapsed_s=time.time()-begin,new_nodes=new,identity=identity,preflight=preflight,ranges=range_rows,
            max_fraction_abs_diff_pp=max(abs(p['differences'][k])*100 for p in own for k in KEYS[:3]),
            max_unrounded_fraction_abs_diff_pp=max(abs(p['unrounded_differences'][k])*100 for p in own for k in KEYS[:3]),
            max_dark_abs_diff_h=max(abs(p['differences']['longest_dark_h']) for p in own))
        summaries.append(item);write(WORK/'sites'/f'{sid}.json',item)
        print('COMPLETE',sid,item['max_fraction_abs_diff_pp'],'pp',round(item['elapsed_s'],1),'s',flush=True)
        del gpu,cpu
        if xp is not np:xp.get_default_memory_pool().free_all_blocks()
    if a.mode=='run':
        report=dict(checker='Jiyong Sung',producer='Sua Kim (nonpolar uncertainty)',complete=len(summaries)==17,
            n_sites=len(summaries),n_nodes=len(all_rows),criterion_fraction_pp=1.,darkness_criterion='reported, no task B threshold',
            method='Independent Cartesian full ray march, CPU PROJ/ECEF controls, own hourly loop; no repository imports',
            backend=a.backend,elapsed_s=time.time()-started,finished_utc=datetime.now(timezone.utc).isoformat(),
            max_fraction_abs_diff_pp=max(s['max_fraction_abs_diff_pp'] for s in summaries),
            max_unrounded_fraction_abs_diff_pp=max(s['max_unrounded_fraction_abs_diff_pp'] for s in summaries),
            max_dark_abs_diff_h=max(s['max_dark_abs_diff_h'] for s in summaries),sites=summaries,nodes=all_rows,failures=all_failures)
        write(report_path(len(summaries)),report)
        print('FINISHED',report['n_sites'],report['n_nodes'],'failures',len(all_failures),'max pp',report['max_fraction_abs_diff_pp'],flush=True)

if __name__=='__main__':main()
