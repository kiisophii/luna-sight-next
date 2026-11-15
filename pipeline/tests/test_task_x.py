import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def test_gpu_latlon_window_wrap_and_range(tmp_path):
    import cupy as cp
    import horizon as hz
    from task_x_gpu import NonpolarGPU
    path=tmp_path/'window.npz'
    np.savez(path,height_m=np.arange(20,dtype=np.float32).reshape(4,5),
        lat=np.array([2.,1.,0.,-1.]),lon_unwrapped=np.array([178.,179.,180.,181.,182.]),meta='{}')
    sampler=hz.LatLonWindowSampler(path)
    gpu=NonpolarGPU([(sampler,150.)])
    try:
        assert np.array_equal(gpu.dist,hz.distances_km(.2,300,4000))
        sample=gpu.module.get_function('sample_test')
        lat=np.array([1.5,0.,-1.,3.]);lon=np.array([-179.5,181.,182.,180.])
        out=cp.empty(4,dtype=cp.float64)
        sample((1,),(4,),(gpu.ptr,gpu.params,cp.asarray(lat),cp.asarray(lon),out))
        np.testing.assert_allclose(cp.asnumpy(out),sampler.sample(lat,lon),rtol=0,atol=1e-12,equal_nan=True)
    finally:gpu.close()

def test_contract_rejects_nonpolar_polar_range_and_incomplete_grid():
    from check_local250 import validate_record
    import json,copy,pytest
    root=Path(__file__).resolve().parents[2]
    obj=json.loads((root/'web/data/local250/CHANDRAYAAN3.json').read_text())
    site=next(s for s in json.loads((root/'web/data/sites.json').read_text(encoding='utf-8')) if s['id']==obj['id'])
    base=json.loads((root/'web/data/metrics/CHANDRAYAAN3.json').read_text())
    validate_record(obj,site,base)
    bad=copy.deepcopy(obj);bad['params']['min_km']=.005
    with pytest.raises(ValueError):validate_record(bad,site,base)
    bad=copy.deepcopy(obj);bad['points'].pop()
    with pytest.raises(ValueError):validate_record(bad,site,base)

def test_report_refuses_incomplete_verification_before_publication(tmp_path,monkeypatch):
    import json,pytest
    import task_x_report as report
    monkeypatch.setattr(report,'ROOT',tmp_path)
    monkeypatch.setattr(report,'OUT',tmp_path/'web/data/local250')
    (tmp_path/'docs').mkdir()
    (tmp_path/'docs/task_x_check.json').write_text(json.dumps(dict(complete=False,passed=False)))
    with pytest.raises(AssertionError,match='Complete passing'):
        report.main()
    assert not (tmp_path/'web').exists()

def test_report_refuses_stale_verified_input(tmp_path,monkeypatch):
    import json,pytest
    import task_x_report as report
    monkeypatch.setattr(report,'ROOT',tmp_path)
    monkeypatch.setattr(report,'OUT',tmp_path/'web/data/local250')
    (tmp_path/'docs').mkdir();(tmp_path/'input.bin').write_bytes(b'changed')
    value=dict(complete=True,passed=True,inputs={'input':dict(path='input.bin',sha256='0'*64)})
    (tmp_path/'docs/task_x_check.json').write_text(json.dumps(value))
    with pytest.raises(AssertionError,match='Stale input'):
        report.main()
    assert not (tmp_path/'web').exists()
