"""Jiyong's independent CPU ray marcher and published-product comparison.

No producer geometry, sampling, metrics, export or validation code is used by
the reference. --cpu-comparator additionally runs the original CPU engine as
the system under test. Browser Worker/core.js are also systems under test.
Run from repository root; raw inputs are read-only, evidence is resumable.
"""
import argparse
import functools
import gzip
import hashlib
import json
import math
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
R = 1737400.0
SEED = 53142026
FILES = {}


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


class Polar:
    def __init__(self, path):
        with np.load(record(path),allow_pickle=False) as z:
            self.a = z['height_m'].astype(float)
            self.x,self.y = z['x_m'].astype(float),z['y_m'].astype(float)
            self.meta = json.loads(str(z['metadata']))
        self.to = self.meta['radius_m']
        self.res = float(self.meta['resolution_m'])

    def __call__(self, lat, lon):
        rho = 2*R*np.tan(np.pi/4+np.deg2rad(lat)/2)
        x,y = rho*np.sin(np.deg2rad(lon)),rho*np.cos(np.deg2rad(lon))
        return interpolate(self.a,(self.y[0]-y)/(self.y[0]-self.y[1]),(x-self.x[0])/(self.x[1]-self.x[0]))


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


def map_check(raw,out,cpu_comparator=False):
    meta=readjson(ROOT/'web/data/gmaps/index.json')
    assert meta['ppd']==8 and meta['ephem']['step_h']==2 and meta['params']['naz']==360
    ep=np.fromfile(record(ROOT/'web/data/ephem.bin'),dtype='<f4').reshape(-1,6)[::2]
    near,far=[Cyl(raw/'global'/f'ldem_{p}_float.img') for p in [64,16]]
    chain=[(near,150000),(far,300000)]
    d=[];s=near.res/2
    while s<=300000+1e-6:
        d.append(s);s+=max(near.res if s<=150000 else far.res,.01*s)
    assert len(d)==meta['params']['n_steps']==283
    signature=hashlib.sha256((json.dumps(FILES,sort_keys=True)+
                             hashlib.sha256(Path(__file__).read_bytes()).hexdigest()).encode()).hexdigest()
    rng=np.random.default_rng(SEED)
    cells=[divmod(int(v),2880) for v in rng.choice(1440*2880,10,replace=False)]
    rows=[];computed={}
    def calc(r,c):
        key=f'{r}_{c}'
        if key not in computed:
            f=out/'map_nodes'/f'{key}.json'
            cached=json.loads(f.read_text()) if f.exists() else None
            if cached and cached.get('reference_signature')==signature:
                computed[key]=cached
            else:
                la,lo=90-(r+.5)/8,-180+(c+.5)/8
                h=march(la,lo,chain,np.array(d),360)
                computed[key]=dict(row=r,col=c,lat=la,lon=lo,reference_signature=signature,
                                   **h,metrics=metrics(la,lo,h,ep))
                save(f,computed[key])
        return computed[key]
    images={k:np.array(Image.open(record(ROOT/f'web/data/gmaps/{k}_values.png'))) for k in ['sun','earth','both']}
    for r,c in cells:
        central=calc(r,c)
        # Closest published overview pixel to this randomly selected source cell.
        yy=int(np.clip(np.rint((r+.5)*2048/1440-.5),0,2047))
        xx=int(np.clip(np.rint((c+.5)*4096/2880-.5),0,4095))
        sy=np.clip((yy+.5)*1440/2048-.5,0,1439)
        sx=np.clip((xx+.5)*2880/4096-.5,0,2879)
        y0,x0=int(np.floor(sy)),int(np.floor(sx));fy,fx=sy-y0,sx-x0
        neighbors=[calc(y0,x0),calc(y0,min(x0+1,2879)),calc(min(y0+1,1439),x0),calc(min(y0+1,1439),min(x0+1,2879))]
        expected={};unquantized={};stored={}
        for k in images:
            v=[np.float32(n['metrics'][k]) for n in neighbors]
            # Pillow's float export rounds after horizontal then vertical pass.
            a=np.float32(v[0]*(1-fx)+v[1]*fx);b=np.float32(v[2]*(1-fx)+v[3]*fx)
            value=np.float32(a*(1-fy)+b*fy)
            unquantized[k]=float(value);expected[k]=int(np.rint(np.float32(value*250)))
            stored[k]=int(images[k][yy,xx])
        rows.append(dict(source_cell=central,published_pixel=dict(row=yy,col=xx),
                         support_cells=[[n['row'],n['col']] for n in neighbors],
                         expected_dn=expected,stored_dn=stored,
                         unquantized=unquantized,
                         abs_diff_pp={k:abs(expected[k]-stored[k])*.4 for k in images},
                         quantization_abs_diff_pp={k:abs(unquantized[k]-stored[k]/250)*100 for k in images}))
        print('map cell',r,c,'published DN difference',rows[-1]['abs_diff_pp'],flush=True)
    if cpu_comparator:
        # Producer engine is an additional comparator ONLY; no reference calls it.
        record(ROOT/'pipeline/global_maps.py');record(ROOT/'pipeline/horizon.py')
        import global_maps as gm
        gm.numba.set_num_threads(2)
        engine=gm.Engine(gm.Dem(raw/'global/ldem_64_float.img'),gm.Dem(raw/'global/ldem_16_float.img'),gm.load_ephem(ROOT/'web/data/ephem.bin',2))
        actual,masks=engine.points([r['source_cell']['lat'] for r in rows],[r['source_cell']['lon'] for r in rows],keep_masks=True)
        for i,row in enumerate(rows):
            row['original_cpu_metrics']={k:float(actual[i,j]) for j,k in enumerate(['sun','earth','both'])}
            row['cpu_abs_diff_pp']={k:abs(row['source_cell']['metrics'][k]-row['original_cpu_metrics'][k])*100 for k in images}
            row['cpu_mask_max_abs_deg']=float(np.max(np.abs(masks[i]-row['source_cell']['mask'])))
    result=dict(seed=SEED,selection='10 uniform random source cells without replacement; 1440 x 2880',
                settings=meta,rows=rows,n_recomputed_cells=len(computed),
                max_published_diff_pp=max(v for r in rows for v in r['abs_diff_pp'].values()),
                max_quantization_abs_diff_pp=max(v for r in rows for v in r['quantization_abs_diff_pp'].values()),
                raw_grid_available=False)
    if cpu_comparator:result['max_cpu_abs_diff_pp']=max(v for r in rows for v in r['cpu_abs_diff_pp'].values())
    save(out/'map_check.json',result)
    assert result['max_published_diff_pp']==0, 'Published DN mismatch'
    assert result['max_quantization_abs_diff_pp']<=.20001, 'Outside PNG rounding bound'
    if cpu_comparator:assert result['max_cpu_abs_diff_pp']<1e-6, 'Independent CPU disagreement'


def polar_check(raw,out):
    sites=readjson(ROOT/'web/data/sites.json')
    ids=['SHACKLETON_RIM','PEAK_NEAR_SHACKLETON','ARTEMIS_MALAPERT']
    points=[{k:next(s for s in sites if s['id']==sid)[k] for k in ['id','lat','lon']} for sid in ids]
    eph=np.fromfile(record(ROOT/'web/data/ephem.bin'),dtype='<f4').reshape(-1,6)
    for name in ['custom_horizon_worker.js','hterrain.js','core.js']:record(ROOT/'web/js'/name)
    browser=worker_results(points)
    save(out/'browser_worker.json',browser)
    dist=np.geomspace(5,300000,8001)
    glob=[(Cyl(raw/'global'/f'ldem_{p}_float.img'),300000) for p in [64,16]]
    rows=[]
    for point,web in zip(points,browser):
        sid=point['id'];chain=[]
        for res in [5,10,20,60,80,240]:
            p=raw/'polar'/str(res)/(sid+'.npz')
            if p.exists():
                sampler=Polar(p);chain.append((sampler,min(sampler.to,300000)))
        assert chain,'Missing polar caches'
        ref=march(point['lat'],point['lon'],chain+glob,dist,720)
        tiled=BrowserTiles(point['lat'])
        same=march(point['lat'],point['lon'],tiled.chain(),dist,720)
        w=web['worker'];delta=np.array(w['mask'])-ref['mask'];same_delta=np.array(w['mask'])-same['mask']
        rm=metrics(point['lat'],point['lon'],ref,eph,sunlit_time=True)
        wm=metrics(point['lat'],point['lon'],w,eph,sunlit_time=True)
        sm=metrics(point['lat'],point['lon'],same,eph,sunlit_time=True)
        row=dict(**point,card8_chain=[dict(res_m=s.res,to_m=limit) for s,limit in chain],
                 card8=ref,independent_browser_tiles=same,worker=w,
                 card8_metrics=rm,worker_mask_independent_metrics=wm,browser_core_metrics=web['core_metrics'],same_tile_metrics=sm,
                 card8_comparison=dict(rms_deg=float(np.sqrt(np.mean(delta**2))),max_abs_deg=float(abs(delta).max()),sun_diff_pp=(wm['sun']-rm['sun'])*100),
                 same_tile_comparison=dict(rms_deg=float(np.sqrt(np.mean(same_delta**2))),max_abs_deg=float(abs(same_delta).max()),sun_diff_pp=(wm['sun']-sm['sun'])*100),
                 core_loop_sun_diff_pp=(web['core_metrics']['sun_frac']-wm['sun'])*100)
        row['same_tile_rounded_mask_exact']=bool(np.array_equal(np.round(same['mask'],4),w['mask']))
        rows.append(row);save(out/'polar_check.json',rows)
        assert row['same_tile_rounded_mask_exact'], 'Worker disagrees on identical tiles after rounding'
        assert row['same_tile_comparison']['max_abs_deg']<=.0000501
        assert row['same_tile_comparison']['sun_diff_pp']==0
        assert abs(row['core_loop_sun_diff_pp'])<1e-10
        print(sid,'card8',row['card8_comparison'],'same tiles',row['same_tile_comparison'],flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw',type=Path,required=True)
    ap.add_argument('--mode',choices=['map','polar','all'],default='all')
    ap.add_argument('--cpu-comparator',action='store_true')
    ap.add_argument('--out',type=Path,default=ROOT/'docs/crosscheck_maps_polar')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    if args.mode in ['map','all']:map_check(args.raw,args.out,args.cpu_comparator)
    if args.mode in ['polar','all']:polar_check(args.raw,args.out)
    save(args.out/f'inputs_{args.mode}.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),files=FILES,
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))


if __name__=='__main__':main()
