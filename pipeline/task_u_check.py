"""Task U: independent north-polar source-DEM reference vs actual browser Worker.
Reference uses only stdlib/NumPy; no producer geometry or metric imports.
Own earlier independent formulas are retained with a new north-polar reader.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import argparse
import functools
import gzip
import hashlib
import json
import math
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_u'
R=1737400.0
FILES={}

def north_xy(lat, lon):
    rho=2*R*np.tan(np.pi/4-np.deg2rad(lat)/2)
    return rho*np.sin(np.deg2rad(lon)), -rho*np.cos(np.deg2rad(lon))


class NorthDEM:
    def __init__(self,path):
        with np.load(record(path),allow_pickle=False) as z:
            self.a=z['height_m'].astype(float)
            self.x,self.y=z['x_m'].astype(float),z['y_m'].astype(float)
            self.meta=json.loads(str(z['metadata']))
        assert self.meta['frame']=='MOON_ME_DE421'
        assert self.meta['reference_radius_m']==R
        assert '+lat_0=90' in self.meta['projection']
        assert self.meta['pixel_registration']=='center' and self.meta['units']=='m'
        self.res=float(self.meta['resolution_m']);self.to=float(self.meta['radius_m'])
        assert np.allclose(np.diff(self.x),self.res) and np.allclose(np.diff(self.y),-self.res)

    def __call__(self,lat,lon):
        x,y=north_xy(lat,lon)
        return interpolate(self.a,(self.y[0]-y)/self.res,(x-self.x[0])/self.res)


def record(path):
    path = Path(path)
    key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    if key not in FILES:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for buf in iter(lambda: f.read(4 * 1024 * 1024), b''):
                h.update(buf)
        FILES[key] = dict(sha256=h.hexdigest(), bytes=path.stat().st_size)
    return path


def readjson(path):
    return json.loads(record(path).read_text(encoding='utf-8'))


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def interpolate(a, row, col, wrap=False):
    """Independent four-corner weighted interpolation; input centres are integers."""
    row, col = np.broadcast_arrays(np.asarray(row, float), np.asarray(col, float))
    shape = row.shape
    row, col = row.ravel(), col.ravel()
    valid = (row >= 0) & (row <= a.shape[0]-1)
    if not wrap:
        valid &= (col >= 0) & (col <= a.shape[1]-1)
    out = np.full(row.size, np.nan)
    y, x = row[valid], col[valid]
    yi = np.minimum(np.floor(y).astype(int), a.shape[0]-2)
    xi = np.floor(x).astype(int) if wrap else np.minimum(np.floor(x).astype(int), a.shape[1]-2)
    fy, fx = y-yi, x-xi
    xl, xr = xi % a.shape[1], (xi+1) % a.shape[1]
    out[valid] = ((1-fy)*(1-fx)*a[yi,xl] + (1-fy)*fx*a[yi,xr]
                  + fy*(1-fx)*a[yi+1,xl] + fy*fx*a[yi+1,xr])
    return out.reshape(shape)


class Cyl:
    def __init__(self, path):
        path = record(path)
        text = record(path.with_suffix('.lbl')).read_text(encoding='latin-1')
        fields = {}
        for line in text.splitlines():
            if '=' in line:
                k,v = line.split('=',1)
                if k.strip() not in fields:
                    fields[k.strip()] = v.split('<')[0].strip().strip('"')
        self.ppd = float(fields['MAP_RESOLUTION'])
        self.lpo = float(fields['LINE_PROJECTION_OFFSET'])
        self.spo = float(fields['SAMPLE_PROJECTION_OFFSET'])
        self.clon = float(fields['CENTER_LONGITUDE'])
        self.scale = float(fields['SCALING_FACTOR']) * 1000
        assert float(fields['OFFSET']) == R/1000 and fields['UNIT'] == 'KILOMETER'
        self.a = np.memmap(path, mode='r', dtype='<f4', shape=(int(fields['LINES']),int(fields['LINE_SAMPLES'])))
        self.res = R*math.pi/180/self.ppd

    def __call__(self, lat, lon):
        row = np.clip(self.lpo-lat*self.ppd,0,self.a.shape[0]-1)
        col = self.spo+(np.mod(lon,360)-self.clon)*self.ppd
        return interpolate(self.a,row,col,wrap=True)*self.scale


def chain_sample(chain, lat, lon, distance):
    lat,lon,distance = np.broadcast_arrays(lat,lon,distance)
    shape=lat.shape
    lat,lon,distance = lat.ravel(),lon.ravel(),distance.ravel()
    out=np.full(lat.size,np.nan)
    for sampler,limit in chain:
        use=np.flatnonzero(~np.isfinite(out) & (distance <= limit))
        if use.size:
            out[use]=sampler(lat[use],lon[use])
    assert np.isfinite(out).all(), 'Uncovered terrain sample; no silent fallback to zero'
    return out.reshape(shape)


def march(lat,lon,chain,dist,naz):
    """Full CPU march with spherical direct-geodesic formula; no early stopping."""
    h0=float(chain_sample(chain,[lat],[lon],[0])[0])
    phi,lam=np.deg2rad([lat,lon])
    theta=dist[None,:]/R
    sin_t,cos_t=np.sin(theta),np.cos(theta)
    mask=[]
    for first in range(0,naz,12):
        az=np.deg2rad(np.arange(first,min(first+12,naz))*360/naz)[:,None]
        p=np.arcsin(np.clip(np.sin(phi)*cos_t+np.cos(phi)*sin_t*np.cos(az),-1,1))
        l=lam+np.arctan2(np.sin(az)*sin_t*np.cos(phi),cos_t-np.sin(phi)*np.sin(p))
        h=chain_sample(chain,np.rad2deg(p),np.rad2deg(l),dist[None,:])
        rt=R+h
        angles=np.arctan2(rt*cos_t-(R+h0+2),rt*sin_t)
        mask.extend(np.rad2deg(angles.max(axis=1)).tolist())
    return dict(h0_m=h0,mask=mask)


def metrics(lat,lon,horizon,eph,*,sunlit_time=False):
    """Own vector projections, circular mask interpolation and disk-segment area."""
    phi,lam=np.deg2rad([lat,lon])
    up=np.array([np.cos(phi)*np.cos(lam),np.cos(phi)*np.sin(lam),np.sin(phi)])
    east=np.array([-np.sin(lam),np.cos(lam),0.])
    north=np.array([-np.sin(phi)*np.cos(lam),-np.sin(phi)*np.sin(lam),np.cos(phi)])
    obs=(R+horizon['h0_m']+2)/1000*up
    mask=np.asarray(horizon['mask'])
    margins=[]
    for col in [0,3]:
        v=eph[:,col:col+3].astype(float)-obs
        e,n,z=v@east,v@north,v@up
        el=np.rad2deg(np.arctan2(z,np.hypot(e,n)))
        a=np.mod(np.arctan2(e,n)/(2*np.pi)*len(mask),len(mask))
        i=np.floor(a).astype(int);f=a-i
        margins.append(el-(mask[i]*(1-f)+mask[(i+1)%len(mask)]*f))
    y=np.clip(-margins[0]/0.2666,-1,1)
    disk=(np.arccos(y)-y*np.sqrt(1-y*y))/np.pi
    earth=margins[1]>0
    return dict(sun=float((disk>=.5).mean() if sunlit_time else disk.mean()),
                earth=float(earth.mean()),both=float(((disk>=.5)&earth).mean()))


class BrowserTiles:
    """Own gzip/predictor reader and tiled interpolation, not hterrain.js."""
    def __init__(self,point_lat):
        self.root=ROOT/'web/data/hterrain'
        self.index=readjson(self.root/'index.json')
        self.polar=readjson(self.root/'polar_s/index.json')
        self.cache={}
        self.levels=[l for l in self.polar['levels'] if point_lat<=l.get('lat_edge_deg',-75)]

    def tile(self,path,n,q=None):
        if path not in self.cache:
            b=gzip.decompress(record(self.root/path).read_bytes())
            if q is None:
                a=np.frombuffer(b,dtype='<i2').reshape(n,n).astype(np.int64).cumsum(axis=1)
            else:
                base=int.from_bytes(b[:4],'little',signed=True)
                a=np.frombuffer(b[4:],dtype='<i2').reshape(n,n).astype(np.int64)
                a=(a.cumsum(axis=0).cumsum(axis=1)+base)*q
            self.cache[path]=a.astype(float)
        return self.cache[path]

    def sampled(self,lv,lat,lon,polar=False,name=None):
        if polar:
            rho=2*R*np.tan(np.pi/4+np.deg2rad(lat)/2)
            row=(lv['y0_m']-rho*np.cos(np.deg2rad(lon)))/lv['res_m']
            col=(rho*np.sin(np.deg2rad(lon))-lv['x0_m'])/lv['res_m']
            stride=lv['tile_px'];size=lv['nt']*stride
            valid=(row>=0)&(row<=size)&(col>=0)&(col<=size)
            r0=np.minimum(np.floor(row).astype(int),size-1)
            c0=np.minimum(np.floor(col).astype(int),size-1)
        else:
            ppd=lv['ppd'];height,width=180*ppd,360*ppd;stride=lv['n']-1
            row=np.clip((90-lat)*ppd-.5,0,height-1)
            col=(lon+180)*ppd-.5
            r0=np.minimum(np.floor(row).astype(int),height-2)
            c0=np.floor(col).astype(int)
            valid=np.ones(lat.shape,bool)
        fr,fc=row-r0,col-c0
        if not polar:c0%=width
        ty,tx=r0//stride,c0//stride
        out=np.full(lat.size,np.nan)
        # Different tile traversal from Worker; sample all corners explicitly.
        for yy,xx in set(zip(ty[valid].tolist(),tx[valid].tolist())):
            key=f'{yy}_{xx}'
            if polar and key not in lv['tiles']:continue
            take=valid&(ty==yy)&(tx==xx)
            path=(lv['url'] if polar else self.index['url'].replace('{grid}',name)).replace('{ty}_{tx}',key)
            a=self.tile(path,lv['n'],lv['q_m'] if polar else None)
            rr,cc=r0[take]-yy*stride,c0[take]-xx*stride
            fy,fx=fr[take],fc[take]
            out[take]=((1-fy)*(1-fx)*a[rr,cc]+(1-fy)*fx*a[rr,cc+1]
                       +fy*(1-fx)*a[rr+1,cc]+fy*fx*a[rr+1,cc+1])
        return out

    def chain(self):
        result=[]
        for lv in self.levels:
            result.append((functools.partial(self.sampled,lv,polar=True),lv['to_km']*1000))
        for name in ['near','far']:
            lv=self.index['grids'][name]
            result.append((functools.partial(self.sampled,lv,name=name),lv['to_km']*1000))
        return result


def worker_results(points):
    from playwright.sync_api import sync_playwright
    class Handler(SimpleHTTPRequestHandler):
        extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'text/javascript'}
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT/'web')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
            page=browser.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/data/ephem.json')
            result=page.evaluate('''async points => {
              const core=await import('/js/core.js');
              core.state.ephem=new Float32Array(await (await fetch('/data/ephem.bin')).arrayBuffer());
              core.state.n=core.state.ephem.length/6;
              const rows=[];
              for(const p of points){
                const w=new Worker('/js/custom_horizon_worker.js',{type:'module'});
                const h=await new Promise((resolve,reject)=>{
                  const timer=setTimeout(()=>{w.terminate();reject(new Error('Worker timeout'))},180000);
                  w.onerror=e=>{clearTimeout(timer);w.terminate();reject(new Error(e.message))};
                  w.onmessage=e=>{if(e.data.type==='done'||e.data.type==='error'){
                    clearTimeout(timer);w.terminate();e.data.type==='done'?resolve(e.data):reject(new Error(e.data.message));}};
                  w.postMessage({...p,base:location.origin+'/data/'});
                });
                core.state.horizons.set(p.id,{...h,az_step_deg:.5});
                rows.push({...p,worker:h,core_metrics:core.metrics(p)});
              }
              return rows;
            }''',points)
            browser.close()
        return result
    finally:server.shutdown()


def comparison(a,b,am,bm):
    delta=np.asarray(a['mask'])-b['mask']
    return dict(rms_deg=float(np.sqrt(np.mean(delta**2))),max_abs_deg=float(abs(delta).max()),
                **{k+'_diff_pp':100*(am[k]-bm[k]) for k in ('sun','earth','both')})


def run(mode):
    started=time.perf_counter()
    points=readjson(WORK/'points.json')
    ep=np.fromfile(record(ROOT/'web/data/ephem.bin'),dtype='<f4').reshape(-1,6)
    for name in ('core.js','custom_horizon_worker.js','hterrain.js'):
        record(ROOT/'web/js'/name)
    for name in ('index.json','polar_s/index.json'):
        record(ROOT/'web/data/hterrain'/name)
    for tile in sorted((ROOT/'web/data/hterrain/tiles').rglob('*.i16.gz')):
        record(tile)
    record(Path(__file__))
    common=dict(FILES)
    browser_path=WORK/'browser.json'
    signature=hashlib.sha256(json.dumps(common,sort_keys=True).encode()).hexdigest()
    if mode=='browser':
        rows=worker_results(points)
        save(browser_path,dict(signature=signature,rows=rows,inputs=common,
                              elapsed_s=time.perf_counter()-started))
        print('Browser complete',len(rows),flush=True)
        return
    browser=readjson(browser_path)
    assert browser['signature']==signature,'Browser inputs or checker changed; rerun browser mode'
    globroot=ROOT/'data/processed/local250/raw/global'
    glob=[(Cyl(globroot/f'ldem_{p}_float.img'),300000) for p in (64,16)]
    common.update({k:v for k,v in FILES.items() if 'ldem_' in k})
    rows=[];pending=[]
    for i,(p,b) in enumerate(zip(points,browser['rows'])):
        assert p['id']==b['id']
        near=10 if p['lat']>=83 else 20 if p['lat']>=80 else 30
        paths=[WORK/'raw'/str(r)/(p['id']+'.npz') for r in (near,60,240)]
        if not all(q.exists() for q in paths):
            pending.append(p['id']);continue
        for q in paths:record(q)
        inputs={**common,**{str(q.relative_to(ROOT)):FILES[str(q.relative_to(ROOT))] for q in paths}}
        sig=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
        dest=WORK/'nodes'/(p['id']+'.json')
        cached=json.loads(dest.read_text()) if dest.exists() else None
        if cached and cached.get('signature')==sig:
            rows.append(cached);continue
        t=time.perf_counter()
        sources=[NorthDEM(q) for q in paths]
        chain=[(s,s.to) for s in sources]+glob
        ref=march(p['lat'],p['lon'],chain,np.geomspace(5,300000,8001),720)
        matched=march(p['lat'],p['lon'],chain,np.geomspace(200,300000,4001),720)
        w=b['worker'];result={}
        for stride in (1,2):
            period={key:metrics(p['lat'],p['lon'],h,ep[::stride],sunlit_time=True)
                    for key,h in [('reference',ref),('matched_start_reference',matched),('browser',w)]}
            period['difference']=comparison(w,ref,period['browser'],period['reference'])
            period['matched_start_difference']=comparison(w,matched,period['browser'],period['matched_start_reference'])
            result[f'{stride}h']=period
        own=result['1h']['browser']
        core_delta={k:100*(b['core_metrics'][k+'_frac']-own[k]) for k in ('sun','earth','both')}
        assert max(abs(v) for v in core_delta.values())<1e-9,'Own loop disagrees with actual core'
        control=None
        if i in (0,10,20):
            tiled=BrowserTiles(p['lat'])
            same=march(p['lat'],p['lon'],tiled.chain(),np.geomspace(200,300000,4001),720)
            sm=metrics(p['lat'],p['lon'],same,ep,sunlit_time=True)
            control=comparison(w,same,own,sm)
            control['rounded_mask_exact']=bool(np.array_equal(np.round(same['mask'],4),w['mask']))
            assert control['rounded_mask_exact'],'Same-tile independent CPU differs from Worker'
            assert control['sun_diff_pp']==0 and control['earth_diff_pp']==0
        row=dict(**p,signature=sig,source_metadata=[s.meta for s in sources],reference=ref,
                 matched_start_reference=matched,browser=w,metrics=result,core_loop_diff_pp=core_delta,
                 same_tile_control=control,elapsed_s=time.perf_counter()-t,inputs=inputs)
        save(dest,row);rows.append(row)
        print(p['id'],result['2h']['difference'],flush=True)
    report=dict(input_main='274e676',seed=2026111503,complete=len(rows)==30,
                point_count=len(rows),pending=pending,browser_elapsed_s=browser['elapsed_s'],
                reference_elapsed_s=sum(r['elapsed_s'] for r in rows),rows=rows,files=FILES)
    if rows:
        rms=np.array([r['metrics']['2h']['difference']['rms_deg'] for r in rows])
        sun=np.array([abs(r['metrics']['2h']['difference']['sun_diff_pp']) for r in rows])
        report['summary']=dict(median_rms_deg=float(np.median(rms)),max_rms_deg=float(max(rms)),
            max_abs_angle_deg=max(r['metrics']['2h']['difference']['max_abs_deg'] for r in rows),
            max_abs_sun_pp=float(max(sun)),median_abs_sun_pp=float(np.median(sun)),
            max_abs_earth_pp=max(abs(r['metrics']['2h']['difference']['earth_diff_pp']) for r in rows),
            max_abs_both_pp=max(abs(r['metrics']['2h']['difference']['both_diff_pp']) for r in rows),
            rms_criterion_pass=bool(np.median(rms)<=.2),sun_criterion_pass=bool(np.all(sun<=2)),
            sun_exceedances=[r['id'] for r in rows if abs(r['metrics']['2h']['difference']['sun_diff_pp'])>2],
            common_angle_exceedances=[r['id'] for r in rows if r['metrics']['2h']['difference']['max_abs_deg']>.05],
            common_fraction_exceedances=[r['id'] for r in rows if any(abs(r['metrics']['2h']['difference'][k+'_diff_pp'])>.1 for k in ('sun','earth','both'))])
    save(ROOT/'docs/task_u_north_check.json',report)
    print('Complete',report['complete'],'pending',pending,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['browser','reference'],required=True)
    run(parser.parse_args().mode)
