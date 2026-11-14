import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('task_w',Path(__file__).parents[1]/'task_w_sensitivity.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_far_samples_unchanged_by_near_toggle():
    for polar in [False,True]:
        full,far=m.distances(polar)
        assert np.array_equal(full[full>=200],far)
        production=np.geomspace(5 if polar else 200,300000,8001 if polar else 4001)
        assert np.array_equal(full if polar else far,production)

def test_height_and_near_field_effects():
    d=np.array([5.,100.,200.,1000.]);h=np.array([[5.,0.,0.,0.]])
    result=m.reduce_cases(np,h,d,0.)
    for near in [False,True]:
        assert result[(0,near)][0]>=result[(2,near)][0]>=result[(10,near)][0]
    assert result[(2,True)][0]>result[(2,False)][0]

def test_dark_runs_include_endpoints():
    assert m.dark_run([False,False,True,False])==2
    assert m.dark_run([True,True])==0
    assert m.dark_run([False]*7)==7
