"""Validate optional section 22 maps and their discovery index."""
import hashlib
import json
from pathlib import Path
import numpy as np
from local250 import GRID,grid_points
from local_maps import params_for,valid_metrics,METRICS

def index_hash(path):
    """Portable digest for Git text files on Windows and deployed LF checkouts."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def validate_record(obj,site,baseline):
    def require(condition,message):
        if not condition:raise ValueError(message)
    require(obj['id']==site['id'] and obj['center']=={k:site[k] for k in ('lat','lon')},'catalogue centre mismatch')
    require(obj['grid']==GRID and len(obj['points'])==1681,'expected complete 41x41 250 m grid')
    require(obj['params']==params_for(site),'range settings do not match site production method')
    require(obj['window']==dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824),'ephemeris window mismatch')
    require(obj['frame']=='MOON_ME_DE421' and obj['radius_m']==1737400.,'frame/radius mismatch')
    require(obj['complete'] is True and obj['mock'] is False,'partial or mock map')
    for point,want in zip(obj['points'],grid_points(site)):
        require(all(point[k]==v for k,v in want.items()),'node order/coordinate mismatch')
        require(valid_metrics(point),'invalid node metrics')
        require(np.isfinite(point['h0_m']) and point['ground_resolution_m']>0,'invalid terrain metadata')
    require(all(obj['points'][840][k]==baseline[k] for k in METRICS),'centre metrics mismatch')
    require(obj['provenance']['grid']==GRID and obj['provenance']['params']==params_for(site),'provenance settings mismatch')

def check_local250(data,sites,err,warn):
    folder=Path(data)/'local250'
    if not folder.exists():return
    paths=sorted(p for p in folder.glob('*.json') if p.name!='index.json')
    for path in paths:
        try:
            obj=json.loads(path.read_text(encoding='utf-8'))
            base=json.loads((Path(data)/'metrics'/path.name).read_text(encoding='utf-8'))
            validate_record(obj,sites[path.stem],base)
        except (ValueError,KeyError,TypeError,OSError) as e:err('local250/'+path.name,str(e))
    index=folder/'index.json'
    if index.exists():
        try:
            obj=json.loads(index.read_text(encoding='utf-8'));rows=obj['sites']
            if obj['schema_version']!=1 or obj['sha256_normalization']!='CRLF_to_LF' or len(rows)!=len(paths) or {r['id'] for r in rows}!={p.stem for p in paths}:
                raise ValueError('index IDs/count do not match complete map files')
            for row in rows:
                p=folder/(row['id']+'.json')
                if row['file']!=p.name or row['sha256']!=index_hash(p):raise ValueError('index path/hash mismatch')
                if row['grid']!=GRID or row['center']!={k:sites[row['id']][k] for k in ('lat','lon')}:raise ValueError('index grid/centre mismatch')
        except (ValueError,KeyError,TypeError,OSError) as e:err('local250/index.json',str(e))
    print(f'local250: {len(paths)} site maps checked')
