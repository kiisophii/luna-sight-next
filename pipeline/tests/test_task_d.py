import importlib.util
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('task_d',Path(__file__).parents[1]/'task_d_check.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_rgb_height_encoding():
    rgb=np.array([[[0,0,0],[78,32,0],[156,64,0]]],dtype=np.uint8)
    assert m.decode(rgb).tolist()==[[-10000.,0.,10000.]]

def test_box_phase_uses_original_window_origin():
    a=np.arange(64,dtype=np.float32).reshape(8,8)
    # At downsampled centre (0,0), the original 2x2 block mean is 4.5.
    assert m.filtered_sample(a,.5,.5,2)==4.5
    assert m.filtered_sample(a,2.5,2.5,2)==22.5
    assert np.isnan(m.filtered_sample(a,-.1,0,2))

def test_tile_shared_vertex_location():
    a=m.vertex('south',4,7,8,22,257)
    b=m.vertex('south',4,8,8,22,1)
    assert np.allclose(a,b,rtol=0,atol=1e-12)

def test_inventory_checks_longitude_wrap(tmp_path,monkeypatch):
    from PIL import Image
    monkeypatch.setattr(m,'GLOBE',tmp_path)
    monkeypatch.setattr(m,'ROOT',tmp_path)
    folder=tmp_path/'band/4';folder.mkdir(parents=True)
    for x in (79,0):
        a=np.zeros((259,259,3),dtype=np.uint8);a[...,0]=78;a[...,1]=32
        if x==79:a[1:258,257,1]=33
        Image.fromarray(a).save(folder/f'{x}_24.png')
    result=m.inventory({'tiles':{'band':[[4,79,24],[4,0,24]]}})
    assert result['seams_checked']==1
    assert result['seam_max_m']==.5
