import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('task_c',Path(__file__).parents[1]/'task_c_check.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_root_keeps_rising_and_setting_brackets():
    roots=m.bisect_roots(lambda x: np.sin(x),np.array([3.,6.]),np.array([4.,7.]),np.array([True,False]),tolerance=.00001)
    assert np.allclose(roots,[np.pi,2*np.pi],rtol=0,atol=.00001)

def test_midnight_and_minute_floor():
    assert m.daily_rows([[14*3600+59*60+59.9,15*3600+61.2,42.]])=={'2026-01-01':[['23:59','24:00',42.]],'2026-01-02':[['00:00','00:01',42.]]}

def test_lsb_decode():
    assert m.unpack('gQE=',10).tolist()==[True,False,False,False,False,False,False,True,True,False]
