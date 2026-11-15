"""Acquire expanded native SLDEM windows without overwriting historical caches."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import json
from pathlib import Path
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
from fetch_global import fetch_site_window
from local250 import reserve_two_cores

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    reserve_two_cores()
    sites=json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
    out=ROOT/'data/processed/task_x/raw/sldem'
    for s in sites:
        if abs(s['lat'])>=60:continue
        print('FETCH',s['id'],flush=True)
        fetch_site_window(s,166,out,workers=3,sites_src='web/data/sites.json')
        print('READY',s['id'],flush=True)
