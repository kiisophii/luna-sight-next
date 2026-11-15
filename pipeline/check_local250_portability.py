"""Measure the unchanged local250 product's cross-platform coordinate round-off."""
import json,subprocess,sys
from pathlib import Path
from local250 import grid_points
ROOT=Path(__file__).resolve().parents[1]
BASE='300b8499e3ea4cadf1e9f2c36a267ba91e935aee'
sites=json.loads((ROOT/'web/data/sites.json').read_text())
old=subprocess.check_output(['git','show',BASE+':pipeline/check_local250.py'],cwd=ROOT,text=True)
namespace={'__name__':'baseline_local250'}
exec(compile(old,'baseline_check_local250.py','exec'),namespace)
baseline=[]
namespace['check_local250'](ROOT/'web/data',{s['id']:s for s in sites},lambda w,m:baseline.append(dict(where=w,message=m)),lambda *a:None)
assert all(e['message']=='node order/coordinate mismatch' for e in baseline),baseline
rows=[];other=[]
for site in sites:
    record=json.loads((ROOT/'web/data/local250'/(site['id']+'.json')).read_text())
    maxlat=maxlon=0.;n=0
    for point,want in zip(record['points'],grid_points(site)):
        for key,value in want.items():
            if key in ('lat','lon'):
                diff=abs(point[key]-value)
                if key=='lat':maxlat=max(maxlat,diff)
                else:maxlon=max(maxlon,diff)
            elif point[key]!=value:other.append(dict(id=site['id'],key=key))
        n+=any(point[k]!=v for k,v in want.items())
    rows.append(dict(id=site['id'],nodes=len(record['points']),exact_coordinate_mismatches=n,max_lat_deg=maxlat,max_lon_deg=maxlon))
assert not other,other
maximum=max(max(r['max_lat_deg'],r['max_lon_deg']) for r in rows)
assert maximum<=1e-9,maximum
# Prove the scientific product and its generating geometry are unchanged from main.
subprocess.run(['git','diff','--exit-code',BASE,'--','web/data/local250','pipeline/local250.py','pipeline/horizon.py'],cwd=ROOT,check=True)
out=dict(baseline_main=BASE,baseline_errors=baseline,max_abs_coordinate_difference_deg=maximum,tolerance_deg=1e-9,noncoordinate_mismatches=other,sites=rows,production_data_changed=False)
p=ROOT/'docs/z3_checks/local250_portability.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('baseline_errors','sites')}))
