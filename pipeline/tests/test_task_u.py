import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def test_north_projection_matches_proj():
    from task_u_check import north_xy
    from pyproj import Proj
    lat=np.array([75.,80.,85.,89.9,90.]);lon=np.array([0.,90.,-90.,179.,-179.])
    ref=Proj('+proj=stere +lat_0=90 +lat_ts=90 +lon_0=0 +R=1737400 +units=m')
    np.testing.assert_allclose(north_xy(lat,lon),ref(lon,lat),rtol=0,atol=1e-8)

def test_flat_sphere_and_chain_gate():
    from task_u_check import march,chain_sample
    a=lambda lat,lon:np.zeros_like(lat)+10
    b=lambda lat,lon:np.zeros_like(lat)+20
    assert chain_sample([(a,3000),(b,300000)],[80,80],[0,0],[3000,3001]).tolist()==[10,20]
    d=np.geomspace(5,300000,8001)
    r=march(87,179,[(lambda la,lo:np.zeros_like(la),300000)],d,12)
    theta=d/1737400
    expected=np.degrees(np.max(np.arctan2(1737400*np.cos(theta)-(1737400+2),1737400*np.sin(theta))))
    np.testing.assert_allclose(r['mask'],expected,rtol=0,atol=1e-10)


def test_missing_fine_pixels_fall_through_not_zero():
    from task_u_check import chain_sample
    fine=lambda lat,lon:np.where(lat>85,100.,np.nan)
    coarse=lambda lat,lon:np.zeros_like(lat)+50
    assert chain_sample([(fine,3000),(coarse,300000)],[86,80],[0,0],[5,5]).tolist()==[100,50]


def test_north_dem_registration_and_invalid_frame(tmp_path):
    from task_u_check import NorthDEM,north_xy
    import json
    import pytest
    x,y=north_xy(85.,0.)
    meta=dict(frame='MOON_ME_DE421',reference_radius_m=1737400,projection='+lat_0=90',
              pixel_registration='center',units='m',resolution_m=10,radius_m=3000)
    # record() deliberately permits external temporary test inputs.
    p=tmp_path/'north.npz'
    def write():
        np.savez(p,height_m=np.array([[1.,2.],[3.,4.]]),x_m=[x-5,x+5],y_m=[y+5,y-5],metadata=json.dumps(meta))
    write()
    assert NorthDEM(p)(np.array([85.]),np.array([0.]))[0]==2.5
    meta['projection']='+lat_0=-90';write()
    with pytest.raises(AssertionError):NorthDEM(p)
