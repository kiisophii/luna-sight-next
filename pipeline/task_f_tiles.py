"""Build a sparse PGDA 5/10 m near-field candidate; never modify public data by default."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
from pyproj import Proj

ROOT=Path(__file__).resolve().parents[1]
PROJ='+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m'
PROJECT=Proj(PROJ)
T=512

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(obj,indent=1,allow_nan=False)+'\n',encoding='utf-8');temp.replace(p)

def encode(height,q):
    if not np.isfinite(height).all():raise ValueError('Missing source pixels must not be encoded')
    a=np.rint(height.astype(float)/q).astype(np.int64);base=int(a[0,0]);a=a-base
    residual=np.empty_like(a);residual[0,0]=0
    residual[0,1:]=np.diff(a[0]);residual[1:,0]=np.diff(a[:,0])
    residual[1:,1:]=a[1:,1:]-a[1:,:-1]-a[:-1,1:]+a[:-1,:-1]
    if residual.min() < -32768 or residual.max()>32767:raise ValueError('Residual exceeds int16')
    return gzip.compress(np.asarray(base,dtype='<i4').tobytes()+residual.astype('<i2').tobytes(),compresslevel=6,mtime=0)

def decode(blob,n,q):
    raw=gzip.decompress(blob)
    if len(raw)!=4+n*n*2:raise ValueError('Bad encoded size')
    base=np.frombuffer(raw[:4],dtype='<i4')[0]
    residual=np.frombuffer(raw[4:],dtype='<i2').reshape(n,n).astype(np.int64)
    return (residual.cumsum(0).cumsum(1)+base)*q

def source_offset(sx,sy,x0,y0,res):
    row,col=(y0-sy)/res,(sx-x0)/res
    if abs(row-round(row))>1e-6 or abs(col-round(col))>1e-6:raise ValueError('Source grid is not natively aligned')
    return round(row),round(col)

def wanted_tiles(sites,res,x0,y0,patch_m):
    keys=set();width=T*res
    for s in sites:
        x,y=PROJECT(s['lon'],s['lat'])
        for ty in range(math.floor((y0-y-patch_m)/width),math.floor((y0-y+patch_m)/width)+1):
            for tx in range(math.floor((x-x0-patch_m)/width),math.floor((x-x0+patch_m)/width)+1):
                left=x0+tx*width;top=y0-ty*width
                dx=max(left-x,0,x-(left+width));dy=max((top-width)-y,0,y-top)
                if dx*dx+dy*dy<=patch_m*patch_m:keys.add((ty,tx))
    return keys

def build(raw,out,patch_m=4000):
    started=time.time();sites=[s for s in json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8')) if s['lat']<=-75]
    original=ROOT/'docs/task_f/baseline_index.json'
    if not original.exists():original=ROOT/'web/data/hterrain/polar_s/index.json'
    index=json.loads(original.read_text());levels=[];reports=[]
    for res in (5,10):
        name=f'p{res}';q=.25;x0=-560000+res/2;y0=560000-res/2
        desired=wanted_tiles(sites,res,x0,y0,patch_m);records={};sources=[];source_url=None
        for path in sorted((raw/str(res)).glob('*.npz')):
            with np.load(path,allow_pickle=False) as z:
                meta=json.loads(str(z['metadata']));height=z['height_m'];sx=float(z['x_m'][0]);sy=float(z['y_m'][0])
                assert meta['frame']=='MOON_ME_DE421' and meta['reference_radius_m']==1737400 and meta['resolution_m']==res
                assert meta['pixel_registration']=='center'
                row0,col0=source_offset(sx,sy,x0,y0,res)
                identity=dict(path=str(path),sha256=sha(path),source_url=meta['source_url'],source_size_bytes=meta['source_size_bytes'],
                    source_bounds=meta['bounds'],window_x0_m=sx,window_y0_m=sy,shape=list(height.shape))
                sources.append(identity)
                if source_url is None:source_url=meta['source_url']
                assert source_url==meta['source_url']
                for ty,tx in sorted(desired):
                    key=f'{ty}_{tx}'
                    if key in records:continue
                    rr,cc=ty*T-row0,tx*T-col0
                    if rr<0 or cc<0 or rr+T>=height.shape[0] or cc+T>=height.shape[1]:continue
                    tile=height[rr:rr+T+1,cc:cc+T+1]
                    if not np.isfinite(tile).all():continue
                    dest=out/name/f'{key}.bin.gz';dest.parent.mkdir(parents=True,exist_ok=True)
                    target=np.rint(tile.astype(float)/q)*q
                    blob=dest.read_bytes() if dest.exists() else None
                    if blob is None or not np.array_equal(decode(blob,T+1,q),target):
                        blob=encode(tile,q);temp=dest.with_suffix('.tmp');temp.write_bytes(blob);temp.replace(dest)
                    back=decode(blob,T+1,q);delta=float(np.max(np.abs(back-tile)))
                    assert np.array_equal(back,target) and delta<=q/2+1e-9
                    records[key]=dict(source_path=str(path),source_sha256=identity['sha256'],source_row=rr,source_col=cc,
                        sha256=sha(dest),bytes=len(blob),max_quantization_error_m=delta)
                print(name,path.stem,'tiles',len(records),'/',len(desired),flush=True)
                dump(out/f'{name}_build_progress.json',dict(records=records,sources=sources))
        if not records:raise ValueError(f'No source coverage for {name}')
        level=dict(name=name,source=f'PGDA native {res} m, sparse catalogue-region near field',source_url=source_url,
            res_m=res,q_m=q,to_km=3.,lat_edge_deg=-75.,x0_m=x0,y0_m=y0,tile_px=T,n=T+1,nt=math.ceil(1120000/(T*res)),
            tiles=sorted(records),bytes=sum(v['bytes'] for v in records.values()),url=f'polar_s/{name}/'+'{ty}_{tx}.bin.gz',
            patch_radius_m=patch_m,coverage_note='Sparse full-valid tiles intersecting catalogue-region discs; missing keys fall through to coarser levels.')
        levels.append(level);reports.append(dict(level=level,requested_tiles=len(desired),omitted_tiles=len(desired)-len(records),records=records,sources=sources))
    index['levels']=levels+[lv for lv in index['levels'] if lv['name'] not in {'p5','p10'}]
    index['sparse_near_field']=dict(patch_radius_m=patch_m,observer_near_gate_km=3.,native_source_coverage_only=True,
        note='5/10 m available only on listed sparse tiles; remaining terrain keeps existing p20/p60/p240/global fallback.')
    dump(out/'index.json',index)
    report=dict(elapsed_s=time.time()-started,original_index_sha256=sha(original),builder_sha256=sha(Path(__file__)),
        candidate_index_sha256=sha(out/'index.json'),levels=reports,additional_bytes=sum(lv['bytes'] for lv in levels))
    dump(out/'build_report.json',report);print('BUILD COMPLETE',report['additional_bytes'],'bytes',round(report['elapsed_s'],1),'s',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'data/processed/local250/raw/polar')
    p.add_argument('--out',type=Path,default=ROOT/'data/processed/task_f/polar_s');p.add_argument('--patch-m',type=float,default=4000)
    a=p.parse_args();build(a.raw,a.out,a.patch_m)
