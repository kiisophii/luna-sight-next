import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('task_b_full_check',Path(__file__).parents[1]/'task_b_full_check.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_bilinear_wrap_and_missing():
    a=np.array([[0.,10.,20.],[30.,40.,50.]])
    assert m.bilinear(np,a,np.array([.5]),np.array([2.5]),True)[0]==25.
    assert np.isnan(m.bilinear(np,a,np.array([.5]),np.array([-1.]),False)[0])

def test_flat_sphere_curvature():
    class Flat:
        def sample(self,xp,lat,lon,d):return xp.zeros_like(lat)
    ground,mask=m.horizon(np,10.,175.,Flat())
    d=np.geomspace(200.,300000.,4001);theta=d/m.R
    expected=np.degrees(np.arctan2(m.R*np.cos(theta)-(m.R+2),m.R*np.sin(theta))).max()
    assert ground==0 and np.max(np.abs(mask-expected))<1e-8

def test_dark_runs_and_radius_statistics():
    assert m.dark_run([False,False,True,False,False,False])==3
    assert m.dark_run([True,True])==0
    points=[dict(e_m=e,n_m=n,sun_frac=.5,earth_frac=1.,both_frac=.5,longest_dark_h=3) for n in range(-500,501,100) for e in range(-500,501,100)]
    assert [m.ranges(points)[str(r)]['n_nodes'] for r in [100,300,500]]==[5,29,81]

def test_ray_beyond_window_gate_uses_global_source():
    terrain=m.Terrain.__new__(m.Terrain)
    terrain.sources=[dict(kind='window',gate_m=150000.,array=np.zeros((2,2)),lat0=1.,lon0=0.,dlat=1.,dlon=1.,mid=.5),
        dict(kind='global',gate_m=300000.,array=np.full((2,4),.01),lpo=1.,spo=0.,clon=0.,ppd=1.,scale=1000.)]
    assert terrain.sample(np,np.array([.5]),np.array([.5]),np.array([200000.]))[0]==10.

def test_partial_report_cannot_replace_full_report():
    assert m.report_path(1)!=m.report_path(17)
    assert m.report_path(17)==m.ROOT/'docs/task_b_full_check.json'
