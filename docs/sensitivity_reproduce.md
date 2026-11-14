# Reproduce the sensitivity experiments

Run from the repository root with the existing production raw caches and Python environment (NumPy/Numba), plus Node.js. Save each Python block under the indicated ignored data/processed/assumptions path. These scripts write no production files. The only downloads are three checked native LDEM_128 windows; polar products use the existing recorded raw caches.

```powershell
python data/processed/assumptions/fetch_ldem128.py
python data/processed/assumptions/compute.py heights
python data/processed/assumptions/compute.py nonpolar
python data/processed/assumptions/compute.py polar
```

Fetch uses at most four network workers; the numerical driver uses single-threaded library settings. Cases resume only when site, source hashes, ray parameters, tested height, baseline hashes and core/ephemeris identities match. If modifying the diagnostic driver itself, use a new empty cases directory: the cache token identifies numerical inputs, not arbitrary edits to the driver. Original diagnostic script hashes are in sensitivity_sources.json.

The unmodified core.js observer is adjusted only through a temporary adapter h0 = true serialized DEM h0 + tested height - 2. This must never be exported as real terrain h0. The case record always retains true_dem_h0_m and raw_dem_h0_m separately. No comparison changes its baseline DEM, ray grid or other variables except the explicitly selected assumption.

## fetch_ldem128.py

```python
import sys,json,math,time,hashlib,concurrent.futures
from pathlib import Path
import numpy as np
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'pipeline'))
import fetch_global as fg

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/'data/processed/assumptions/ldem128';out.mkdir(parents=True,exist_ok=True)
    url=fg.LDEM_DIR+'ldem_128_float.img';label=fg.get_text(fg.LDEM_DIR+'ldem_128_float.lbl')
    (out/'ldem_128_float.lbl').write_text(label,encoding='ascii')
    g=fg.Grid(label);size,validator=fg.probe(url)
    assert g.res==128 and size==g.lines*g.row_bytes
    sites={s['id']:s for s in json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))}
    for sid in ['APOLLO17','CHANGE4','SLIM']:
        t=time.monotonic();site=sites[sid];r0,r1,c0,c1,clipped=fg.window_plan(site['lat'],site['lon'],150.,ppd=128)
        assert not clipped and 0<=c0<c1<=g.samples
        folder=out/sid;folder.mkdir(exist_ok=True)
        identity=dict(url=url,validator=validator,remote_bytes=size,label_sha256=sha(out/'ldem_128_float.lbl'),plan=[r0,r1,c0,c1])
        stamp=folder/'source.json'
        if stamp.exists():assert json.loads(stamp.read_text())==identity
        stamp.write_text(json.dumps(identity,indent=2),encoding='utf-8')
        def job(start):
            stop=min(start+128,r1);p=folder/f'{start}-{stop}.npy'
            if not p.exists():
                a=fg.fetch_piece_rows(url,g.row_bytes,start,stop,c0,c1,validator)
                assert a.shape==(stop-start,c1-c0) and np.isfinite(a).all() and np.max(np.abs(a))<20
                np.save(p,a)
            return p
        starts=list(range(r0,r1,128))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(job,starts))
        km=np.concatenate([np.load(p) for p in files]);lat=g.row_lat(np.arange(r0,r1));lon=g.col_lon(np.arange(c0,c1))
        meta=dict(**identity,source_url=url,source_label_url=fg.LDEM_DIR+'ldem_128_float.lbl',radius_km=150.,site_id=sid,site_lat=site['lat'],site_lon=site['lon'],frame='MOON_ME_DE421',native_unit='km',unit='m',res_m=math.pi/180*1737400/128,part_sha256={p.name:sha(p) for p in files},elapsed_s=time.monotonic()-t)
        np.savez_compressed(out/f'{sid}.npz',height_m=km.astype(np.float64)*1000.,lat=lat,lon_unwrapped=lon,meta=json.dumps(meta))
        print(sid,km.shape,'bytes',km.nbytes,'elapsed',meta['elapsed_s'],flush=True)
    print('COMPLETE',flush=True)
if __name__=='__main__':main()
```

## compute.py

```python
"""Diagnostic-only sensitivity; production modules/files remain unchanged."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS']:os.environ[k]='1'
import argparse,copy,json,hashlib,sys,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
ROOT=Path.cwd();WORK=ROOT/'data/processed/assumptions';sys.path.insert(0,str(ROOT/'pipeline'))
import horizon as hz
import run_horizons as rh
from local_maps import CoreMetrics
IDS=['SHACKLETON_RIM','ARTEMIS_HAWORTH','ARTEMIS_MALAPERT','APOLLO17','CHANGE4','SLIM']
KEYS=['sun_frac','earth_frac','both_frac','longest_dark_h']
HASHES={}

def sha(p):
    p=Path(p)
    if str(p) not in HASHES:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
        HASHES[str(p)]=h.hexdigest()
    return HASHES[str(p)]

def identity(chain):
    out=[]
    for s,gate in chain:
        p=Path(getattr(s,'path',None) or s.data.filename)
        relative=p.relative_to(ROOT) if p.is_relative_to(ROOT) else Path('data/raw/global')/p.name
        out.append(dict(name=s.name,to_km=gate,res_m=s.res_m,path=relative.as_posix(),sha256=sha(p),metadata=getattr(s,'meta',{})))
    return out

def run_case(site,chain,height,variant,core,baseline,expected):
    started=time.perf_counter();sid=site['id'];params={k:baseline['engine'][k] for k in ['min_km','max_km','n_steps','early_stop','hmax_m']}
    ident=dict(site=site,chain=identity(chain),params=params,height_m=height,variant=variant,baseline_horizon_sha256=sha(ROOT/f'web/data/horizon/{sid}.json'),baseline_metrics_sha256=sha(ROOT/f'web/data/metrics/{sid}.json'),horizon_code_sha256=sha(ROOT/'pipeline/horizon.py'),core=core.identity)
    token=hashlib.sha256(json.dumps(ident,sort_keys=True).encode()).hexdigest();path=WORK/'cases'/f'{sid}_{variant}_{height}m.json';path.parent.mkdir(exist_ok=True)
    if path.exists():
        result=json.loads(path.read_text(encoding='utf-8'))
        if result['input_token']==token:return result
    res=hz.compute_horizon(site['lat'],site['lon'],chain,obs_height_m=height,**params)
    assert res['n_missing']==0
    rec=hz.horizon_record(site,res);rec['obs_height_m']=height
    # Unmodified core.js uses h0+2 only in observerPos. Shift only its in-memory
    # adapter input to represent true DEM h0+height. No DEM or output baseline shifts.
    adapter=copy.deepcopy(rec);adapter['h0_m']=rec['h0_m']+height-2.;adapter['obs_height_m']=2
    m=core.metrics(site,adapter)
    if variant=='production' and height==2:
        assert rec['mask']==baseline['mask'],sid+' baseline mask differs'
        assert rec['h0_m']==baseline['h0_m'],sid+' baseline ground differs'
        assert all(m[k]==expected[k] for k in KEYS),sid+' baseline metric differs'
    delta={k:(m[k]-expected[k])*(100 if k.endswith('_frac') else 1) for k in KEYS}
    dm=np.asarray(rec['mask'])-np.asarray(baseline['mask'])
    result=dict(id=sid,variant=variant,height_m=height,input_token=token,inputs=ident,metrics=m,difference_vs_production=delta,true_dem_h0_m=rec['h0_m'],raw_dem_h0_m=res['h0_m'],adapter_h0_m=adapter['h0_m'],dem_h0_delta_m=rec['h0_m']-baseline['h0_m'],mask_rms_deg=float(np.sqrt(np.mean(dm*dm))),mask_max_abs_diff_deg=float(np.max(np.abs(dm))),mask_mean_diff_deg=float(np.mean(dm)),mask=rec['mask'],raw_mask=res['mask'].tolist(),dem_sources=res['dem_sources'],n_missing_samples=res['n_missing'],n_samples=res['n_samples'],elapsed_s=time.perf_counter()-started,computed_utc=datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(sid,variant,height,'delta',delta,'mask_rms',result['mask_rms_deg'],'sec',round(result['elapsed_s'],2),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['heights','nonpolar','polar']);a=ap.parse_args()
    sites=json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'));lookup={s['id']:s for s in sites};ids=IDS if a.phase=='heights' else IDS[3:] if a.phase=='nonpolar' else [s['id'] for s in sites if s['lat']<=-75]
    if a.phase=='polar':assert len(ids)==16
    records=[];start=time.perf_counter()
    with CoreMetrics(ROOT) as core:
        for sid in ids:
            site=lookup[sid];base=json.loads((ROOT/f'web/data/horizon/{sid}.json').read_text());expected=json.loads((ROOT/f'web/data/metrics/{sid}.json').read_text());chain=rh.build_chain(site,ROOT/'data/raw',300.)
            b=run_case(site,chain,2,'production',core,base,expected);records.append(b)
            if a.phase=='heights':
                for h in [1,3,10]:records.append(run_case(site,chain,h,'production',core,base,expected))
            elif a.phase=='nonpolar':
                assert chain[0][0].name=='SLDEM2015' and chain[0][1]==150
                s=hz.LatLonWindowSampler(WORK/'ldem128'/f'{sid}.npz',name='LDEM_128',res_m=np.pi/180*hz.R_M/128)
                alternative=[(s,150.)]+chain[1:]
                records.append(run_case(site,alternative,2,'LDEM128_near',core,base,expected))
            else:
                by={int(round(s.res_m)):s for s,g in chain if s.name.startswith('PGDA_')}
                assert 20 in by and 60 in by
                alternative=[(by[20],3.),(by[60],60.)]+[(s,g) for s,g in chain if not s.name.startswith('PGDA_') or round(s.res_m)>=80]
                records.append(run_case(site,alternative,2,'PGDA20_60_near',core,base,expected))
    (WORK/f'{a.phase}.json').write_text(json.dumps(dict(phase=a.phase,records=records,elapsed_s=time.perf_counter()-start),indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('DONE',a.phase,len(records),round(time.perf_counter()-start,3),flush=True)
if __name__=='__main__':main()
```

