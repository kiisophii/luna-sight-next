"""Pinned full-card8 reference at every polar catalogue site and nearby test points."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import time
import numpy as np
from pyproj import Geod
import horizon as hz
from local250_gpu import PolarGPU
from local_maps import CoreMetrics

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_f'
GATES={5:3,10:25,20:25,60:60,80:60,240:200}

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(path)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--raw',type=Path,default=ROOT/'data/processed/local250/raw');a=ap.parse_args()
    WORK.mkdir(parents=True,exist_ok=True);rng=random.Random(2026111506);geod=Geod(a=hz.R_M,b=hz.R_M)
    sites=[s for s in json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8')) if s['lat']<=-75]
    first=['SHACKLETON_RIM','PEAK_NEAR_SHACKLETON','ARTEMIS_MALAPERT']
    sites=sorted(sites,key=lambda s:first.index(s['id']) if s['id'] in first else 3)
    points=[]
    for site in sites:
        points.append(dict(id=site['id'],parent=site['id'],lat=site['lat'],lon=site['lon'],kind='centre'))
        for i in range(2):
            distance=1000*math.sqrt(rng.random());bearing=rng.uniform(0,360)
            lon,lat,_=geod.fwd(site['lon'],site['lat'],bearing,distance)
            points.append(dict(id=f"{site['id']}_R{i+1}",parent=site['id'],lat=lat,lon=lon,kind='nearby',distance_m=distance))
    save(WORK/'points.json',points)
    output=[];manifests={};started=time.time()
    with CoreMetrics(ROOT) as core:
        for site in sites:
            chain=[];manifest=[]
            for res,gate in GATES.items():
                path=a.raw/'polar'/str(res)/f"{site['id']}.npz"
                if path.exists():
                    chain.append((hz.PolarStereoSampler(path),gate));manifest.append(dict(path=str(path),sha256=digest(path),gate_km=gate))
            for ppd in (64,16):
                path=a.raw/'global'/f'ldem_{ppd}_float.img';chain.append((hz.GlobalCylSampler(path),300))
                manifest.append(dict(path=str(path),sha256=digest(path),gate_km=300))
            group=[p for p in points if p['parent']==site['id']];gpu=PolarGPU(chain)
            try:
                results,_=gpu.points(group)
                cpu=hz.compute_horizon(site['lat'],site['lon'],chain,min_km=.005,max_km=300,n_steps=8000,obs_height_m=2)
                assert np.max(np.abs(results[0]['mask']-cpu['mask']))<1e-6
                for p,result in zip(group,results):
                    h=hz.horizon_record(p,result);m=core.metrics(p,h)
                    if p['kind']=='centre':
                        old=json.loads((ROOT/'web/data/horizon'/f"{site['id']}.json").read_text())
                        old_metrics=json.loads((ROOT/'web/data/metrics'/f"{site['id']}.json").read_text())
                        assert h['mask']==old['mask'] and all(m[k]==old_metrics[k] for k in m),site['id']
                    output.append(dict(**p,h0_m=h['h0_m'],mask=h['mask'],metrics=m))
                manifests[site['id']]=manifest
                save(WORK/'reference.json',dict(seed=2026111506,complete=len(output)==48,points=output,sources=manifests,
                    code_sha256=digest(Path(__file__)),elapsed_s=time.time()-started))
                print('REFERENCE',site['id'],'centre exact; points',len(output),flush=True)
            finally:gpu.close()

if __name__=='__main__':main()
