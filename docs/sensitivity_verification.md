# Separate verification of sensitivity results

Independent reviewer: OpenAI Codex / GPT-6 Astra, High reasoning, separate session. This is AI verification; human sign-off remains pending. No numerical defect was found.

| Check | Evidence |
|---|---|
| Actual core.js output versus independent vector/time calculation | All **56 unique cases** match all four metrics exactly over 43,824 hours |
| Independent scalar loop | Six critical cases match exactly: Haworth 1/3/10 m, Shackleton 1 m, Chang'e 4 LDEM128, Peak near Shackleton alternate PGDA |
| Production control | All **19 unique 2 m sites** exactly match existing mask, serialized surface elevation and four metrics |
| Full horizon without early stopping | Haworth 1 m and Peak alternate chain: 720 × 8001 = **5,760,720 samples each**, maximum raw-mask difference **0°** |
| Independent great-circle / Cartesian geometry, 12 azimuths per case | Maximum difference 4.9533e-10° and 1.3659e-10° respectively |
| Native LDEM128 pixel registration and units | **15 independently addressed HTTP 206 pixel reads**, five at each nonpolar site, exactly match cached native float32 km values converted to float64 metres |
| Native image identity | Content-Range total 4,246,732,800 bytes and ETag match the download; pixel-centre coordinates independently reconstructed from the label |
| Observer elevation from raw pixels | Independently interpolated ground heights agree within 6e-12 m |
| Height adapter | R + (adapter h0 + 2)/1000 equals R + (serialized true DEM h0 + tested height)/1000 |
| Chain isolation | Nonpolar changes only the near-field sampler at the same 150 km gate; polar uses 20 m to 3 km / 60 m to 60 km and the unchanged fallback tail |

The 56 unique cases comprise 19 production controls, 18 non-2 m height cases, three nonpolar DEM alternatives and sixteen polar alternatives. The three polar controls used by both experiments are not double-counted.

Machine-readable results: [sensitivity_verification.json](sensitivity_verification.json). The saved record separates scalar checks that were performed from cases not selected for the scalar loop; an unselected case is not a failure. The independent audit implementation is included as a reproduction block below. It operates only on diagnostic caches and read-only production inputs.

The existing engine/download unit tests also passed: `python -m pytest pipeline/test_horizon.py pipeline/tests/test_fetch_global.py -q` — **26 passed**.

This verifies computation and controlled comparisons. It does not independently survey the terrain, determine the true spacecraft mounting height, calibrate uncertainty, or establish that the alternative DEM is more accurate. Related PGDA products share LOLA observations; the unchanged far field was not independently validated by changing its data source.

## Independent audit reproduction

Save the block as data/processed/assumptions/review/independent_review.py after producing the diagnostic cases, creating that directory if needed. From the repository root, run each mode:

```powershell
python data/processed/assumptions/review/independent_review.py metrics
python data/processed/assumptions/review/independent_review.py horizons
python data/processed/assumptions/review/independent_review.py pixels
```

```python
"""Read-only independent checks; outputs confined to this ignored review directory."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):
    os.environ[key]='1'
import json, math, sys, time, struct, urllib.request, hashlib
from pathlib import Path
import numpy as np
ROOT=Path.cwd(); OUT=ROOT/'data/processed/assumptions/review'; WORK=OUT.parent
sys.path.insert(0,str(ROOT/'pipeline'))
import horizon as hz
import run_horizons as rh
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
cases=[load(p) for p in sorted((WORK/'cases').glob('*.json'))]
ephem=np.fromfile(ROOT/'web/data/ephem.bin',dtype='<f4').reshape(-1,6).astype(float)
sites={s['id']:s for s in load(ROOT/'web/data/sites.json')}
report={'n_hours':len(ephem),'checks':[]}
def save():
    (OUT/f'{sys.argv[1]}_results.json').write_text(json.dumps(report,indent=2)+'\n')
def metrics(c,scalar=False):
    site=sites[c['id']]; lat,lon=map(math.radians,(site['lat'],site['lon']))
    sl,cl,so,co=math.sin(lat),math.cos(lat),math.sin(lon),math.cos(lon)
    rotation=np.array([[-so,co,0],[-sl*co,-sl*so,cl],[cl*co,cl*so,sl]])
    # Rotating the Moon-centred body first lets observer radius be subtracted
    # solely from its up component; independent of core's Cartesian subtraction.
    radius=1737.4+(c['true_dem_h0_m']+c['height_m'])/1000
    mask=c['mask']
    if scalar:
        lit=[]; earth=[]
        for row in ephem:
            visible=[]
            for offset in (0,3):
                x,y,z=map(float,row[offset:offset+3])
                e=-so*x+co*y
                n=-sl*co*x-sl*so*y+cl*z
                u=cl*co*x+cl*so*y+sl*z-radius
                az=math.degrees(math.atan2(e,n))%360
                k=int(az*2); f=az*2-k
                h=(1-f)*mask[k]+f*mask[(k+1)%720]
                el=math.degrees(math.atan2(u,math.sqrt(e*e+n*n)))
                visible.append(el>=h if offset==0 else el>h)
            lit.append(visible[0]);earth.append(visible[1])
        lit=np.array(lit);earth=np.array(earth)
    else:
        states=[]
        for offset in (0,3):
            v=ephem[:,offset:offset+3]@rotation.T
            v[:,2]-=radius
            az=np.degrees(np.arctan2(v[:,0],v[:,1]))%360
            horizon=np.interp(az,np.arange(721)/2,np.r_[mask,mask[0]])
            el=np.degrees(np.arctan2(v[:,2],np.hypot(v[:,0],v[:,1])))
            states.append(el>=horizon if offset==0 else el>horizon)
        lit,earth=states
    runs=np.diff(np.r_[-1,np.flatnonzero(lit),len(lit)])-1
    return dict(sun_frac=float(lit.mean()),earth_frac=float(earth.mean()),both_frac=float((lit&earth).mean()),longest_dark_h=int(max(runs)))

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='metrics':
        selected={('ARTEMIS_HAWORTH','production',h) for h in (1,3,10)}|{('SHACKLETON_RIM','production',1),('CHANGE4','LDEM128_near',2),('PEAK_NEAR_SHACKLETON','PGDA20_60_near',2)}
        baselines=0
        for c in cases:
            m=metrics(c);assert m==c['metrics'],(c['id'],m,c['metrics'])
            base_case=next(x for x in cases if x['id']==c['id'] and x['variant']=='production' and x['height_m']==2)
            before=base_case['inputs']['chain']; after=c['inputs']['chain']
            if c['variant']=='LDEM128_near':
                assert before[1:]==after[1:] and before[0]['to_km']==after[0]['to_km']==150
                assert after[0]['name']=='LDEM_128'
            elif c['variant']=='PGDA20_60_near':
                assert [(x['name'],x['to_km']) for x in after[:2]]==[('PGDA_LOLA_20M',3.),('PGDA_LOLA_60M',60.)]
                old_tail=[x for x in before if not x['name'].startswith('PGDA_') or x['res_m']>=80]
                assert after[2:]==old_tail
            else:
                assert before==after
            assert abs((c['adapter_h0_m']+2)-(c['true_dem_h0_m']+c['height_m']))<1e-10
            baseline=load(ROOT/f"web/data/horizon/{c['id']}.json")
            diff=np.asarray(c['mask'])-baseline['mask']
            assert abs(float(np.sqrt(np.mean(diff**2)))-c['mask_rms_deg'])<1e-14
            if c['variant']=='production' and c['height_m']==2:
                ref=load(ROOT/f"web/data/metrics/{c['id']}.json")
                assert all(m[k]==ref[k] for k in m)
                assert c['mask']==baseline['mask'] and c['true_dem_h0_m']==baseline['h0_m']
                baselines+=1
            scalar=(c['id'],c['variant'],c['height_m']) in selected
            if scalar:assert metrics(c,True)==m
            report['checks'].append(dict(id=c['id'],variant=c['variant'],height=c['height_m'],vector_exact=True,scalar_exact=scalar,metrics=m))
        report['baseline_exact_count']=baselines;save()
        print('METRICS PASS',len(cases),'cases;',len(selected),'scalar;',baselines,'exact production baselines',flush=True)
    elif mode=='horizons':
        for sid,variant,height in [('ARTEMIS_HAWORTH','production',1),('PEAK_NEAR_SHACKLETON','PGDA20_60_near',2)]:
            c=next(c for c in cases if (c['id'],c['variant'],c['height_m'])==(sid,variant,height))
            s=sites[sid];chain=rh.build_chain(s,ROOT/'data/raw',300)
            if variant!='production':
                by={round(x.res_m):x for x,g in chain if x.name.startswith('PGDA_')}
                chain=[(by[20],3.),(by[60],60.)]+[(x,g) for x,g in chain if not x.name.startswith('PGDA_') or round(x.res_m)>=80]
            params=c['inputs']['params'].copy();params['early_stop']=False
            t=time.monotonic();res=hz.compute_horizon(s['lat'],s['lon'],chain,obs_height_m=height,**params)
            err=float(np.max(np.abs(res['mask']-c['raw_mask'])))
            assert err==0 and res['n_missing']==0
            assert hz.horizon_record(s,res)['mask']==c['mask']
            # Independent great-circle destination formulas and Cartesian terrain
            # vectors, checked on 12 azimuths over the complete distance grid.
            lat,lon=map(math.radians,(s['lat'],s['lon']))
            distances=np.geomspace(params['min_km'],params['max_km'],params['n_steps']+1)
            theta=distances*1000/1737400
            up=np.array([math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)])
            origin=(1737400+res['h0_m']+height)*up
            subset_err=0
            for index in range(0,720,60):
                az=math.radians(index/2)
                la=np.arcsin(math.sin(lat)*np.cos(theta)+math.cos(lat)*np.sin(theta)*math.cos(az))
                lo=lon+np.arctan2(math.sin(az)*np.sin(theta)*math.cos(lat),np.cos(theta)-math.sin(lat)*np.sin(la))
                h=np.full(len(theta),np.nan)
                for sampler,gate in chain:
                    pick=np.isnan(h)&(distances<=gate)
                    h[pick]=sampler.sample(np.degrees(la[pick]),np.degrees(lo[pick]))
                p=np.column_stack((np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)))*(1737400+h)[:,None]
                vec=p-origin;vertical=vec@up
                horizontal=np.linalg.norm(vec-vertical[:,None]*up,axis=1)
                value=float(np.max(np.degrees(np.arctan2(vertical,horizontal))))
                subset_err=max(subset_err,abs(value-res['mask'][index]))
            assert subset_err<1e-6,subset_err
            item=dict(id=sid,variant=variant,height=height,early_stop_false_raw_max_diff_deg=err,independent_geometry_12_az_max_diff_deg=subset_err,n_samples=res['n_samples'],elapsed_s=time.monotonic()-t)
            report['checks'].append(item);save();print(item,flush=True)
    elif mode=='pixels':
        for sid in ('APOLLO17','CHANGE4','SLIM'):
            c=next(c for c in cases if c['id']==sid and c['variant']=='LDEM128_near')
            with np.load(WORK/f'ldem128/{sid}.npz') as z:
                image=z['height_m'];lats=z['lat'];lons=z['lon_unwrapped'];meta=json.loads(str(z['meta']))
            r0,r1,c0,c1=meta['plan']
            assert image.dtype==np.float64
            assert np.array_equal(lats,90-(np.arange(r0,r1)+.5)/128)
            assert np.array_equal(lons,(np.arange(c0,c1)+.5)/128)
            site=sites[sid];r=11519.5-site['lat']*128;cidx=site['lon']%360*128-.5
            rr,cc=int(math.floor(r)),int(math.floor(cidx));fr,fc=r-rr,cidx-cc
            points=[(rr,cc),(rr,cc+1),(rr+1,cc),(rr+1,cc+1),(r0,c1-1)]
            remote=[]
            for row,col in points:
                a=(row*46080+col)*4
                req=urllib.request.Request(meta['url'],headers={'Range':f'bytes={a}-{a+3}','Accept-Encoding':'identity','User-Agent':'LLSN-independent-review/1.0'})
                with urllib.request.urlopen(req,timeout=45) as response:
                    assert response.status==206
                    assert response.headers['Content-Range']==f'bytes {a}-{a+3}/4246732800'
                    assert response.headers['ETag']==meta['validator']
                    raw=response.read();assert len(raw)==4
                val=struct.unpack('<f',raw)[0]*1000
                assert val==image[row-r0,col-c0]
                remote.append(val)
            observed=(1-fr)*((1-fc)*remote[0]+fc*remote[1])+fr*((1-fc)*remote[2]+fc*remote[3])
            assert abs(observed-c['raw_dem_h0_m'])<1e-8
            item=dict(id=sid,independent_range_pixels=5,remote_exact=True,grid_registration_exact=True,observer_h0_m=observed,stored_h0_m=c['raw_dem_h0_m'],remote_bytes=4246732800,etag=meta['validator'])
            report['checks'].append(item);save();print(item,flush=True)
```
