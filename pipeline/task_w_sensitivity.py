"""Task W: standalone complete assumption sensitivity; no repository imports.

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
WORK=ROOT/'data/processed/task_w'
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
    def __init__(self,site,raw,global_root,xp,polar_root):
        self.sources=[];self.manifest=[];self.xp=xp
        if site['lat']<=-75:
            for res,gate in [(5,3000),(10,25000),(20,25000),(60,60000),(80,60000),(240,200000)]:
                p=polar_root/str(res)/(site['id']+'.npz')
                if not p.exists():continue
                with np.load(p,allow_pickle=False) as z:
                    meta=json.loads(str(z['metadata']));x=z['x_m'];y=z['y_m'];h=z['height_m']
                    assert meta['frame']=='MOON_ME_DE421' and meta['reference_radius_m']==R
                    assert meta['resolution_m']==res and meta['pixel_registration']=='center'
                    assert h.shape==(len(y),len(x)) and np.allclose(np.diff(x),res,rtol=0,atol=1e-7) and np.allclose(np.diff(y),-res,rtol=0,atol=1e-7)
                    self.sources.append(dict(kind='polar',array=xp.asarray(h),x0=float(x[0]),y0=float(y[0]),res=res,gate_m=gate))
                self.manifest.append(dict(path=str(p),sha256=source_hash(p),metadata=meta,gate_m=gate))
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
            if s['kind']=='polar':
                rho=2*R*xp.tan(xp.pi/4+xp.radians(lat)/2)
                x=rho*xp.sin(xp.radians(lon));y=rho*xp.cos(xp.radians(lon))
                v=bilinear(xp,s['array'],(s['y0']-y)/s['res'],(x-s['x0'])/s['res'])
            elif s['kind']=='window':
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

def distances(polar):
    polar_grid=np.geomspace(5.,300000.,8001)
    full=polar_grid if polar else np.r_[polar_grid[polar_grid<200],np.geomspace(200.,300000.,4001)]
    return full,full[full>=200]

def reduce_cases(xp,heights,d,ground):
    rt=R+heights;ct=xp.cos(d/R);st=xp.sin(d/R);out={}
    for height in (0,2,10):
        angle=xp.degrees(xp.arctan2(rt*ct-(R+ground+height),rt*st))
        out[(height,True)]=xp.max(angle,axis=1)
        out[(height,False)]=xp.max(xp.where(d>=200,angle,-xp.inf),axis=1)
    return out

def horizons(xp,site,terrain,cpu_control=False):
    """March every ray; reuse terrain samples for all six physical assumptions."""
    lat,lon=site['lat'],site['lon']
    ground=float(terrain.sample(xp,xp.asarray([lat]),xp.asarray([lon]),xp.asarray([0.]))[0])
    assert np.isfinite(ground)
    base_dist,_=distances(lat<=-75);d=xp.asarray(base_dist)
    up,east,north=[xp.asarray(v) for v in frame(lat,lon)];out={(height,near):[] for height in (0,2,10) for near in (False,True)}
    ct=xp.cos(d/R)[None,:];st=xp.sin(d/R)[None,:]
    for first in range(0,720,60):
        if cpu_control:
            dd=np.broadcast_to(base_dist,(60,len(base_dist))).copy()
            az=np.broadcast_to(np.arange(first,first+60)[:,None]*.5,dd.shape).copy()
            lo,la,_=GEOD.fwd(np.full(dd.shape,lon),np.full(dd.shape,lat),az,dd)
        else:
            az=xp.radians(xp.arange(first,first+60,dtype=xp.float64)*.5)[:,None]
            direction=xp.cos(az)[...,None]*north+xp.sin(az)[...,None]*east
            pos=ct[...,None]*up+st[...,None]*direction
            la=xp.degrees(xp.arctan2(pos[...,2],xp.hypot(pos[...,0],pos[...,1])))
            lo=xp.degrees(xp.arctan2(pos[...,1],pos[...,0]))
        terrain_h=terrain.sample(xp,la,lo,xp.broadcast_to(d,la.shape))
        if not bool(xp.all(xp.isfinite(terrain_h))):raise ValueError('Missing DEM sample')
        if cpu_control:
            la,lo=np.radians(la),np.radians(lo)
            target=np.stack([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)],axis=-1)*(R+terrain_h)[...,None]
            cases={}
            for height in (0,2,10):
                ray=target-up*(R+ground+height)
                angle=np.degrees(np.arctan2(ray@up,np.hypot(ray@east,ray@north)))
                cases[(height,True)]=angle.max(axis=1)
                cases[(height,False)]=np.where(base_dist>=200,angle,-np.inf).max(axis=1)
        else:cases=reduce_cases(xp,terrain_h,d,ground)
        for key,mask in cases.items():out[key].append(mask if xp is np else xp.asnumpy(mask))
    return ground,{key:np.concatenate(value) for key,value in out.items()}

def dark_run(sun):
    edges=np.diff(np.r_[0,~np.asarray(sun,dtype=bool),0].astype(np.int8))
    return int((np.flatnonzero(edges==-1)-np.flatnonzero(edges==1)).max(initial=0))

def metrics(lat,lon,ground,mask,ephem,height=2):
    up,east,north=frame(lat,lon);observer=up*(R+ground+height)/1000
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
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw',type=Path,default=ROOT/'data/raw')
    ap.add_argument('--polar-root',type=Path,default=ROOT/'data/processed/local250/raw/polar')
    ap.add_argument('--global-root',type=Path,default=ROOT/'data/processed/local250/raw/global')
    ap.add_argument('--site',action='append');ap.add_argument('--backend',choices=['gpu','cpu'],default='gpu')
    a=ap.parse_args();resources();WORK.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        import msvcrt
        lock=(WORK/'runner.lock').open('a+b');lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);atexit.register(lock.close)
    xp=np
    if a.backend=='gpu':import cupy as xp
    meta=read(ROOT/'web/data/ephem.json')
    assert meta['n']==43824 and meta['step_h']==1 and meta['start']=='2026-01-01T00:00:00Z' and not meta['mock']
    assert meta['frame']=='MOON_ME_DE421' and meta['units']=='km'
    eph=np.fromfile(ROOT/'web/data/ephem.bin',dtype='<f4').reshape(43824,6).astype(float)
    assert np.isfinite(eph).all()
    sites=read(ROOT/'web/data/sites.json');assert len(sites)==33
    sites.sort(key=lambda s:(s['lat']>-75,s['id']!='SHACKLETON_RIM',s['id']))
    if a.site:sites=[s for s in sites if s['id'] in a.site]
    assert sites
    controls={'SHACKLETON_RIM','APOLLO17','CHANGE4'}
    started=time.time();output=[]
    common=dict(ephem_sha256=sha(ROOT/'web/data/ephem.bin'),ephem_meta_sha256=sha(ROOT/'web/data/ephem.json'),
                catalogue_sha256=sha(ROOT/'web/data/sites.json'),core_definition_sha256=sha(ROOT/'web/js/core.js'),
                code_sha256=sha(Path(__file__)),backend=a.backend)
    for si,site in enumerate(sites):
        sid=site['id'];begin=time.time();t=Terrain(site,a.raw,a.global_root,xp,a.polar_root)
        baseline_h=read(ROOT/'web/data/horizon'/f'{sid}.json');baseline_m=read(ROOT/'web/data/metrics'/f'{sid}.json')
        production_near=site['lat']<=-75
        expected=(.005,8000) if production_near else (.2,4000)
        assert (baseline_h['engine']['min_km'],baseline_h['engine']['n_steps'])==expected
        assert baseline_h['obs_height_m']==2 and baseline_h['az_step_deg']==.5 and baseline_h['max_range_km']==300
        identity=dict(**common,site=site,sources=t.manifest,horizon_sha256=sha(ROOT/'web/data/horizon'/f'{sid}.json'),
                      metrics_sha256=sha(ROOT/'web/data/metrics'/f'{sid}.json'))
        fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        destination=WORK/f'{sid}.json'
        record=read(destination) if destination.exists() else {}
        if record.get('fingerprint')==fingerprint and record.get('complete'):
            output.append(record);print('RESUME',sid,flush=True)
        else:
            ground,masks=horizons(xp,site,t)
            record=dict(id=sid,identity=identity,fingerprint=fingerprint,complete=False,production_near=production_near,
                        h0_m=round(ground,2),cases=[])
            for (height,near),mask in masks.items():
                mask=np.round(mask,4);m=metrics(site['lat'],site['lon'],round(ground,2),mask,eph,height)
                diff={k:(m[k]-baseline_m[k])*(1 if k.endswith('_h') else 100) for k in KEYS}
                angles=mask-np.array(baseline_h['mask'])
                record['cases'].append(dict(height_m=height,near_field=near,metrics=m,diff_vs_production=diff,mask=mask.tolist(),
                    horizon_rms_deg=float(np.sqrt(np.mean(angles**2))),horizon_max_deg=float(np.max(np.abs(angles)))))
                write(destination,record)
            base=next(c for c in record['cases'] if c['height_m']==2 and c['near_field']==production_near)
            record['baseline']=dict(metrics_difference=base['diff_vs_production'],max_angle_deg=base['horizon_max_deg'],
                exact_metrics=all(base['metrics'][k]==baseline_m[k] for k in KEYS),
                passes=base['horizon_max_deg']<=.05 and all(abs(base['diff_vs_production'][k])<=(1 if k.endswith('_h') else .1) for k in KEYS))
            if sid in controls:
                cpu=Terrain(site,a.raw,a.global_root,np,a.polar_root);cg,cm=horizons(np,site,cpu,True);checks=[]
                for key,mask in cm.items():
                    other=metrics(site['lat'],site['lon'],round(cg,2),np.round(mask,4),eph,key[0])
                    saved=next(c for c in record['cases'] if (c['height_m'],c['near_field'])==key)
                    angle=float(np.max(np.abs(mask-masks[key])))
                    dif={k:(other[k]-saved['metrics'][k])*(1 if k.endswith('_h') else 100) for k in KEYS}
                    checks.append(dict(height_m=key[0],near_field=key[1],max_angle_deg=angle,metric_diff=dif))
                    if angle>1e-6 or any(abs(v)>1e-9 for v in dif.values()):raise ValueError(f'CPU control failed: {sid} {key} {angle} {dif}')
                record['cpu_controls']=checks;del cpu
            record['elapsed_s']=time.time()-begin;record['complete']=True;write(destination,record);output.append(record)
            print('DONE',sid,'6 cases','baseline',record['baseline'],'seconds',round(record['elapsed_s'],2),flush=True)
        del t
        if xp is not np:xp.get_default_memory_pool().free_all_blocks()
        elapsed=time.time()-started
        print('PROGRESS',si+1,'/',len(sites),'elapsed_s',round(elapsed,1),'ETA_s',round(elapsed/(si+1)*(len(sites)-si-1),1),flush=True)
        dest=ROOT/'docs/task_w_sensitivity.json' if len(sites)==33 else WORK/'partial_report.json'
        write(dest,dict(complete=len(output)==len(sites),n_sites=len(output),n_cases=sum(len(x['cases']) for x in output),
                       runtime_s=elapsed,inputs=common,sites=output))

if __name__=='__main__':main()

