"""Fetch original north-polar windows; existing HTTP reader used for acquisition only."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json
import math
from pathlib import Path
import numpy as np
from pyproj import Proj
import fetch_polar as fp
import polar_prefetch

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_u'
PROJ='+proj=stere +lat_0=90 +lat_ts=90 +lon_0=0 +R=1737400 +units=m'
SOURCES={10:'LDEM_83N_10MPP_ADJ.TIF',20:'LDEM_80N_20MPP_ADJ.TIF',30:'LDEM_75N_30MPP_ADJ.TIF',
    60:'LDEM_60N_60MPP_ADJ.TIF',240:'LDEM_60N_240MPP_ADJ.TIF'}

def points():
    rng=np.random.default_rng(2026111503);out=[]
    for low,high in ((75,80),(80,85),(85,90)):
        lat=np.degrees(np.arcsin(rng.uniform(np.sin(np.radians(low)),np.sin(np.radians(high)),10)))
        lon=rng.uniform(-180,180,10)
        for i,(la,lo) in enumerate(zip(lat,lon)):
            out.append(dict(id=f'NORTH_{low}_{i+1:02d}',lat=round(float(la),6),lon=round(float(lo),6),
                band=f'{low}-{high}N',synthetic=True))
    return out

def validate_crs(tags):
    expected=dict(GeogSemiMajorAxisGeoKey=1737400,GeogSemiMinorAxisGeoKey=1737400,
        ProjCoordTransGeoKey=15,ProjLinearUnitsGeoKey=9001,GeogAngularUnitsGeoKey=9102,
        ProjNatOriginLatGeoKey=90,ProjFalseEastingGeoKey=0,ProjFalseNorthingGeoKey=0,
        ProjScaleAtNatOriginGeoKey=1,ProjStraightVertPoleLongGeoKey=0)
    if any(k not in tags or not math.isclose(float(tags[k]),v,abs_tol=1e-8) for k,v in expected.items()):
        raise ValueError('Not the expected north-polar lunar CRS')

def project(lat,lon):
    if not (0<lat<=90 and -180<=lon<=180):raise ValueError('Expected north latitude/east longitude')
    return fp.POLAR(lon,lat)

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    pts=points();(WORK/'points.json').write_text(json.dumps(pts,indent=2),encoding='utf-8')
    fp.PROJ=PROJ;fp.POLAR=Proj(PROJ);fp.validate_crs=validate_crs;fp.project=project
    fp.BASE='https://pgda.gsfc.nasa.gov/data/LOLA_20mpp_NP/'
    fp.SOURCES={r:(name,3000) for r,name in SOURCES.items()}
    polar_prefetch.install(4)
    status={}
    for p in pts:
        near=10 if p['lat']>=83 else 20 if p['lat']>=80 else 30
        for resolution,radius in ((near,3000),(60,60000),(240,200000)):
            key=f"{p['id']}/{resolution}"
            fp.fetch(p,resolution,radius,WORK/'raw',allow_partial=True)
            status[key]='complete'
            (WORK/'fetch_status.json').write_text(json.dumps(status),encoding='utf-8')
        print('READY',p['id'],flush=True)

if __name__=='__main__':main()
