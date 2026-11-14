# Reproduce the CPU audit

Save the Python block below as data/processed/gpu_cpu_300/reproduce.py in the review checkout. Use the project's Python environment with NumPy and Numba. The source root must contain the original delivered data/processed/gmaps_ppd32/, card14_jiyong_run/handoff_manifest.json, cpu_preservation.json and raw DEMs. The review checkout supplies the unchanged CPU pipeline after verification against original SHA256 hashes. No CUDA code is imported.

```powershell
python data/processed/gpu_cpu_300/reproduce.py --source-root C:/Users/jy02s/Documents/lunar-card8-jiyong
```

Output: data/processed/gpu_cpu_300/result.json. For a completely fresh run, pass --out with a new directory. Existing 30-cell batches are reused only after their cells/input/signature token matches. Resume elapsed time is not a fresh-compute benchmark. The committed CSV and summary JSON are lossless projections of the records and metadata respectively.

```python
"""Read-only CPU audit of delivered southern grid; run from the review repo root."""
import argparse,hashlib,json,sys,time,os
from pathlib import Path
from datetime import datetime,timezone
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
import numba

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--repo-root',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path,default=Path('data/processed/gpu_cpu_300'));a=ap.parse_args()
 start=time.perf_counter();a.out.mkdir(parents=True,exist_ok=True)
 sys.path.insert(0,str(a.repo_root/'pipeline'));import global_maps as gm
 numba.set_num_threads(6)
 run=a.source_root/'data/processed/card14_jiyong_run';folder=a.source_root/'data/processed/gmaps_ppd32'
 manifest=json.loads((run/'handoff_manifest.json').read_text());original=json.loads((run/'cpu_preservation.json').read_text())
 cpu_rows=set(original['completed_rows']);assert cpu_rows==set(range(3103,3455))
 hashes={}
 for k,expected in manifest['input_sha256'].items():
  p=(a.repo_root if k.startswith(('pipeline/','web/')) else a.source_root)/k
  actual=sha(p);assert actual==expected,(k,actual,expected);hashes[k]=actual
 file_hashes={}
 for name,info in manifest['files'].items():
  actual=sha(folder/name);assert actual==info['sha256'],name;file_hashes[name]=actual
 store=gm.Store(folder,32,readonly=True);assert np.all(store.done[3103:5760]==1)
 near,far=gm.load_dems(a.source_root/'data/raw','LDEM_64','LDEM_16');eng=gm.Engine(near,far,gm.load_ephem(a.repo_root/'web/data/ephem.bin',3))
 assert eng.signature()==store.meta['signature']
 used=set();cohorts={}
 for name,seed,bounds,counts in [
 ('assigned_300',202611143001,[3103,3200,3520,3840,4160,4480,4800,5120,5440,5600,5760],[30]*10),
 ('gpu_only_300',202611143002,[3455,3520,3840,4160,4480,4800,5120,5440,5600,5760],[30]*7+[45,45])]:
  rng=np.random.Generator(np.random.PCG64(seed));cells=[];strata=[]
  for i,(r0,r1,n) in enumerate(zip(bounds[:-1],bounds[1:],counts)):
   selected=[]
   while len(selected)<n:
    flat=int(rng.integers(0,(r1-r0)*11520));r,c=r0+flat//11520,flat%11520
    if (r,c) in used:continue
    used.add((r,c));selected.append(dict(row=r,col=c,stratum=i))
   cells.extend(selected);strata.append(dict(row_start=r0,row_stop_exclusive=r1,n=n,lat_north_center=90-(r0+.5)/32,lat_south_center=90-(r1-.5)/32))
  cohorts[name]=dict(seed=seed,strata=strata,cells=cells)
 records=[];lat,lon=gm.grid_axes(32)
 for name,cohort in cohorts.items():
  for b in range(0,300,30):
   cells=cohort['cells'][b:b+30];r=np.array([c['row'] for c in cells]);c=np.array([c['col'] for c in cells]);cache=a.out/f'{name}_{b:03d}.npz'
   token=hashlib.sha256(json.dumps([cells,hashes,eng.signature()],sort_keys=True).encode()).hexdigest()
   if cache.exists():
    with np.load(cache) as z:
     assert str(z['token'])==token;ref=z['cpu'].copy()
   else:
    ref=eng.points(lat[r],lon[c]);np.savez(cache,cpu=ref,token=token)
   assert np.isfinite(ref).all() and np.all(ref[:,5]==0)
   saved=np.column_stack([store.arr[k][r,c] for k in gm.LAYERS]);diff=np.abs(saved-ref[:,:3])*100;quant=np.abs(saved-ref[:,:3].astype(np.float32)).astype(float)*100
   for j,cell in enumerate(cells):
    records.append(dict(cohort=name,**cell,lat=float(lat[r[j]]),lon=float(lon[c[j]]),backend='CPU_preserved' if int(r[j]) in cpu_rows else 'GPU',stored_fractions=saved[j].astype(float).tolist(),cpu_fractions=ref[j,:3].tolist(),abs_diff_pp=diff[j].tolist(),same_float32_abs_diff_pp=quant[j].tolist(),cpu_missing_samples=int(ref[j,5])))
   print(name,b+len(cells),'/300',flush=True)
 summaries={}
 for name in cohorts:
  rows=[r for r in records if r['cohort']==name];d=np.array([r['abs_diff_pp'] for r in rows]);q=np.array([r['same_float32_abs_diff_pp'] for r in rows]);summaries[name]=dict(n=len(rows),gpu_count=sum(r['backend']=='GPU' for r in rows),cpu_preserved_count=sum(r['backend']=='CPU_preserved' for r in rows),south_80_90_count=sum(r['lat']<=-80 for r in rows),metrics={k:dict(max_abs_diff_pp=float(d[:,i].max()),mean_abs_diff_pp=float(d[:,i].mean()),max_same_float32_abs_diff_pp=float(q[:,i].max())) for i,k in enumerate(gm.LAYERS)},cells_exceeding_0_5_pp=[dict(row=r['row'],col=r['col'],abs_diff_pp=r['abs_diff_pp']) for r in rows if max(r['abs_diff_pp'])>.5])
 result=dict(computed_utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.perf_counter()-start,threshold_pp=.5,layers=list(gm.LAYERS),threads=numba.get_num_threads(),numpy_version=np.__version__,numba_version=numba.__version__,cpu_original_commit=manifest['source_commit'],original_input_sha256=hashes,delivered_files_sha256=file_hashes,handoff_manifest_sha256=sha(run/'handoff_manifest.json'),gpu_source_sha256=manifest['gpu_source_sha256'],signature=eng.signature(),sampling={k:{f:v for f,v in x.items() if f!='cells'} for k,x in cohorts.items()},summary=summaries,records=records,scope='Numerical implementation consistency against original CPU pipeline, not physical truth. Cohorts are disjoint; fixed PCG64 seeds, uniform draws within row strata, rejection of previously drawn cells.')
 (a.out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps(summaries,indent=2),flush=True);print('elapsed_s',result['elapsed_s'],flush=True)
if __name__=='__main__':main()
```
