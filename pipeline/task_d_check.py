"""Independent native-pixel, window-phase, PNG seam and albedo checks for task D."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image
from pyproj import Proj

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_d'
GLOBE=ROOT/'web/data/globe'
R=1737400.
PROJ=Proj('+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m')
SEED=2026111504

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp')
    t.write_text(json.dumps(v,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8');t.replace(p)
def decode(rgb):return (rgb[...,0].astype(np.uint16)*256+rgb[...,1])/2.-10000
def spacing(kind,z):return 72*np.pi/180*R/(256*2**z) if kind=='band' else 1120000/(256*2**z)
def vertex(kind,z,x,y,row,col):
    if kind=='band':
        step=72/(256*2**z)
        return 72-(y*256+row-1)*step,(-180+(x*256+col-1)*step+180)%360-180
    step=spacing(kind,z);px=-560000+(x*256+col-1)*step;py=560000-(y*256+row-1)*step
    lon,lat=PROJ(px,py,inverse=True);return lat,lon

def block_mean(block):
    # Local hierarchical box means: no producer pyramid or sampler is imported.
    b=block
    while b.shape[0]>1:
        children=np.stack([b[0::2,0::2],b[0::2,1::2],b[1::2,0::2],b[1::2,1::2]])
        valid=np.isfinite(children);count=valid.sum(axis=0)
        b=np.divide(np.where(valid,children,0).sum(axis=0,dtype=float),count,
                    out=np.full(count.shape,np.nan),where=count>0).astype(np.float32)
    return float(b[0,0])

def filtered_sample(a,native_row,native_col,factor):
    row=(native_row-(factor-1)/2)/factor;col=(native_col-(factor-1)/2)/factor
    ny,nx=a.shape[0]//factor,a.shape[1]//factor
    if not (0<=row<=ny-1 and 0<=col<=nx-1) or min(ny,nx)<2:return float('nan')
    y=min(int(np.floor(row)),ny-2);x=min(int(np.floor(col)),nx-2);fy=row-y;fx=col-x
    vals=np.array([[block_mean(a[(y+i)*factor:(y+i+1)*factor,(x+j)*factor:(x+j+1)*factor]) for j in (0,1)] for i in (0,1)])
    return float(vals[0,0]*(1-fy)*(1-fx)+vals[0,1]*(1-fy)*fx+vals[1,0]*fy*(1-fx)+vals[1,1]*fy*fx)

def native_sources(polar_root,sldem_root):
    sources=[];provenance=[]
    for origin in read(ROOT/'docs/globe_south_window_origins.json')['windows']:
        res=origin['res_m'];relative=Path(origin['file']);p=polar_root/relative.relative_to('polar')
        if not p.exists():p=WORK/'raw'/relative
        with np.load(p,allow_pickle=False) as z:
            x=z['x_m'];y=z['y_m'];h=z['height_m'];metadata=json.loads(str(z['metadata']))
            assert metadata['resolution_m']==res and metadata['frame']=='MOON_ME_DE421' and metadata['reference_radius_m']==R
            assert h.shape==(len(y),len(x)) and np.allclose(np.diff(x),res,rtol=0,atol=1e-7) and np.allclose(np.diff(y),-res,rtol=0,atol=1e-7)
            assert metadata['source_url']==origin['source_url']
            row=(float(y[0])-origin['y0_m'])/res;col=(origin['x0_m']-float(x[0]))/res
            assert abs(row-round(row))<1e-6 and abs(col-round(col))<1e-6
            r,c=int(round(row)),int(round(col));ny,nx=origin['shape'];assert r>=0 and c>=0 and r+ny<=h.shape[0] and c+nx<=h.shape[1]
            assert abs(origin['x_last_m']-(origin['x0_m']+(nx-1)*res))<1e-6
            assert abs(origin['y_last_m']-(origin['y0_m']-(ny-1)*res))<1e-6
            window=h[r:r+ny,c:c+nx].copy()
        name=origin['file'];sources.append(dict(name=name,kind='polar',res=res,x0=origin['x0_m'],y0=origin['y0_m'],array=window))
        provenance.append(dict(name=name,cache=str(p),cache_sha256=sha(p),original=origin,crop_row=r,crop_col=c,metadata=metadata))
    for site in sorted(read(ROOT/'web/data/sites.json'),key=lambda s:s['id']):
        if abs(site['lat'])>=60:continue
        p=sldem_root/(site['id']+'.npz')
        angle=62000/R;dlat=np.degrees(angle);dlon=np.degrees(np.arcsin(np.sin(angle)/np.cos(np.radians(site['lat']))));pad=2/512
        north=min(site['lat']+dlat+pad,60);south=max(site['lat']-dlat-pad,-60);lon=site['lon']%360
        g0=int(np.floor((90-north)*512));g1=int(np.ceil((90-south)*512));k0=int(np.floor((lon-dlon-pad)*512));k1=int(np.ceil((lon+dlon+pad)*512))
        lat0=90-(g0+.5)/512;lon0=(k0+.5)/512
        with np.load(p,allow_pickle=False) as z:
            h=z['height_m'];la=z['lat'];lo=z['lon_unwrapped'];meta=json.loads(str(z['meta']))
            assert h.shape==(len(la),len(lo)) and meta['res_ppd']==512
            assert np.allclose(np.diff(la),-1/512,rtol=0,atol=1e-12) and np.allclose(np.diff(lo),1/512,rtol=0,atol=1e-12)
            row=(float(la[0])-lat0)*512;col=(lon0-float(lo[0]))*512
            assert abs(row-round(row))<1e-6 and abs(col-round(col))<1e-6
            r,c=int(round(row)),int(round(col));ny,nx=g1-g0,k1-k0
            assert r>=0 and c>=0 and r+ny<=h.shape[0] and c+nx<=h.shape[1]
            window=h[r:r+ny,c:c+nx].copy()
        name='sldem60/'+site['id']+'.npz';res=np.pi/180*R/512
        sources.append(dict(name=name,kind='sldem',res=res,lat0=lat0,lon0=lon0,array=window))
        provenance.append(dict(name=name,cache=str(p),cache_sha256=sha(p),origin_rule='62 km spherical cap, 2 native pixel padding, 512 ppd',
            global_bounds=[g0,g1,k0,k1],lat0=lat0,lon0=lon0,shape=[ny,nx],crop_row=r,crop_col=c,metadata=meta))
    sources.sort(key=lambda s:(s['res'],s['name']))
    return sources,provenance

def height_at(sources,global_data,lat,lon,step):
    for s in sources:
        if s['res']>step*1.01:continue
        max_power=5 if s['kind']=='polar' else 4
        factor=1
        while factor<2**max_power and s['res']*factor*2<=step*1.01:factor*=2
        if s['kind']=='polar':
            if lat>=0:continue
            x,y=PROJ(lon,lat);row=(s['y0']-y)/s['res'];col=(x-s['x0'])/s['res']
        else:row=(s['lat0']-lat)*512;col=((lon-s['lon0']+180)%360-180)*512
        v=filtered_sample(s['array'],row,col,factor)
        if np.isfinite(v):return v,s['name'],factor
    # At requested z levels the global fallback always uses native LDEM_64 (474 m).
    row=np.clip((90-lat)*64-.5,0,11519);col=(lon%360)*64-.5
    y=min(int(np.floor(row)),11518);x=int(np.floor(col));fy=row-y;fx=col-x
    a=np.array([[global_data[y+i,(x+j)%23040] for j in (0,1)] for i in (0,1)],dtype=np.float32)*np.float32(1000)
    return float(a[0,0]*(1-fy)*(1-fx)+a[0,1]*(1-fy)*fx+a[1,0]*fy*(1-fx)+a[1,1]*fy*fx),'LDEM_64',1

def sample_plan(index):
    rng=np.random.default_rng(SEED);sites=read(ROOT/'web/data/sites.json');plan=[]
    for kind,levels in [('band',range(4,8)),('south',range(3,7))]:
        for z in levels:
            candidates=[t for t in index['tiles'][kind] if t[0]==z];available={(t[1],t[2]) for t in candidates}
            for i in rng.choice(len(candidates),10,replace=False):
                _,x,y,*_=candidates[i];row,col=map(int,rng.integers(1,258,size=2))
                plan.append(dict(kind=kind,z=z,x=x,y=y,row=row,col=col,selection='random'))
            group=[s for s in sites if (abs(s['lat'])<60 if kind=='band' else s['lat']<=-75)]
            for i in rng.choice(len(group),10,replace=False):
                site=group[i]
                if kind=='band':
                    step=72/(256*2**z);gc=round((site['lon']+180)/step);gr=round((72-site['lat'])/step)
                else:
                    px,py=PROJ(site['lon'],site['lat']);step=spacing(kind,z);gc=round((px+560000)/step);gr=round((560000-py)/step)
                x,y=gc//256,gr//256;assert (x,y) in available,(site['id'],kind,z,x,y)
                plan.append(dict(kind=kind,z=z,x=x,y=y,row=gr%256+1,col=gc%256+1,selection='catalogue_control',site=site['id']))
    return plan

def inventory(index):
    missing=[];bad=[];edges={};hashes={};constants=[]
    for kind,tiles in index['tiles'].items():
        for z,x,y,*_ in tiles:
            p=GLOBE/kind/str(z)/f'{x}_{y}.png'
            if not p.exists():missing.append(str(p.relative_to(ROOT)));continue
            if not ((kind=='band' and 4<=z<=7) or (kind=='south' and 3<=z<=6)):continue
            with Image.open(p) as im:
                a=np.asarray(im);mode=im.mode
            if mode!='RGB' or a.shape!=(259,259,3) or np.any(a[...,2]!=0):bad.append(str(p.relative_to(ROOT)));continue
            v=a[...,0].astype(np.uint16)*256+a[...,1]
            if v.min()==v.max():constants.append(str(p.relative_to(ROOT)))
            edges[(kind,z,x,y)]={'left':v[1:258,1],'right':v[1:258,257],'top':v[1,1:258],'bottom':v[257,1:258]}
            hashes[str(p.relative_to(ROOT))]=sha(p)
    seams=[];count=0;maximum=0.
    for (kind,z,x,y),a in edges.items():
        next_x=(x+1)%(5*2**z) if kind=='band' else x+1
        for neighbor,key1,key2 in [((kind,z,next_x,y),'right','left'),((kind,z,x,y+1),'bottom','top')]:
            if neighbor not in edges:continue
            diff=np.abs(a[key1].astype(int)-edges[neighbor][key2].astype(int))/2;count+=1;maximum=max(maximum,float(diff.max()))
            if diff.any():seams.append(dict(tile=[kind,z,x,y],neighbor=list(neighbor),max_diff_m=float(diff.max()),n_vertices=int(np.count_nonzero(diff))))
    return dict(indexed_tiles=sum(map(len,index['tiles'].values())),missing=missing,decoded_target_tiles=len(edges),bad=bad,
                constants=constants,seams_checked=count,seam_max_m=maximum,seam_failures=seams,hashes=hashes)

def albedo(source):
    Image.MAX_IMAGE_PIXELS=None;original=Image.open(source).convert('RGB');records=[]
    for width in (8192,2048):
        target=GLOBE/f'moon_color_{width//1024}k.jpg';reference=original if original.width==width else original.resize((width,width//2),Image.Resampling.LANCZOS)
        with Image.open(target) as im:actual=np.asarray(im.convert('RGB')).astype(np.int16)
        expected=np.asarray(reference).astype(np.int16);assert actual.shape==expected.shape
        delta=actual.astype(float)-expected;rmse=float(np.sqrt(np.mean(delta**2)));mae=float(np.mean(np.abs(delta)))
        stream=io.BytesIO();reference.save(stream,format='JPEG',quality=88,optimize=True)
        replay=np.asarray(Image.open(io.BytesIO(stream.getvalue())).convert('RGB')).astype(np.int16)
        # Strided orientation diagnostic: compare matching pixels to obvious wrong orientations.
        a=actual[::16,::16];b=expected[::16,::16]
        variants={'correct':b,'flipped_lat':b[::-1],'flipped_lon':b[:,::-1],'shifted_180':np.roll(b,b.shape[1]//2,axis=1)}
        orientation={k:float(np.abs(a-v).mean()) for k,v in variants.items()}
        records.append(dict(file=str(target.relative_to(ROOT)),sha256=sha(target),shape=list(actual.shape),mae_dn=mae,rmse_dn=rmse,
            max_abs_dn=int(np.abs(delta).max()),psnr_db=float(20*np.log10(255/rmse)),reencoded_pixel_max_diff=int(np.abs(actual-replay).max()),
            reencoded_byte_equal=stream.getvalue()==target.read_bytes(),orientation_mae=orientation))
    return dict(source_url='https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif',source_sha256=sha(source),records=records)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--polar-root',type=Path,default=ROOT/'data/processed/local250/raw/polar')
    ap.add_argument('--sldem-root',type=Path,default=ROOT/'data/raw/sldem')
    ap.add_argument('--ldem64',type=Path,default=ROOT/'data/processed/local250/raw/global/ldem_64_float.img');a=ap.parse_args()
    WORK.mkdir(parents=True,exist_ok=True);started=time.time();index=read(GLOBE/'index.json');plan=sample_plan(index);save(WORK/'points.json',plan)
    sources,manifest=native_sources(a.polar_root,a.sldem_root)
    global_data=np.memmap(a.ldem64,dtype='<f4',shape=(11520,23040),mode='r');rows=[]
    for p in plan:
        lat,lon=vertex(p['kind'],p['z'],p['x'],p['y'],p['row'],p['col']);v,source,factor=height_at(sources,global_data,lat,lon,spacing(p['kind'],p['z']))
        file=GLOBE/p['kind']/str(p['z'])/f"{p['x']}_{p['y']}.png"
        with Image.open(file) as im:height=float(decode(np.asarray(im))[p['row'],p['col']])
        predicted=float(np.rint((np.float32(v)+np.float32(10000))*np.float32(2))/2-10000)
        rows.append(dict(**p,lat=lat,lon=lon,source=source,box_factor=factor,reference_m=v,stored_m=height,diff_m=height-v,
                         predicted_encoded_m=predicted,encoded_equal=height==predicted,passes=abs(height-v)<=.5))
        save(WORK/'samples.json',rows)
    print('VERTICES',len(rows),'max difference',max(abs(r['diff_m']) for r in rows),'failures',sum(not r['passes'] for r in rows),flush=True)
    inv=inventory(index);print('INVENTORY',inv['decoded_target_tiles'],'seams',inv['seams_checked'],'failed seams',len(inv['seam_failures']),flush=True)
    alb=albedo(WORK/'lroc_color_poles_8k.tif');print('ALBEDO',alb['records'],flush=True)
    result=dict(complete=True,seed=SEED,runtime_s=time.time()-started,samples=rows,sources=manifest,inventory=inv,albedo=alb,
        inputs={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'web/data/sites.json',GLOBE/'index.json',ROOT/'docs/globe_south_window_origins.json']},
        ldem64=dict(path=str(a.ldem64),sha256=sha(a.ldem64)))
    save(ROOT/'docs/task_d_check.json',result)

if __name__=='__main__':main()
