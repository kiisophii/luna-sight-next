import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import local250 as l


def test_grid_and_priority():
    sites=l.ordered_sites();assert len(sites)==16
    assert [s['id'] for s in sites[:4]]==l.FIRST
    p=l.grid_points(sites[0]);assert len(p)==1681
    assert (p[0]['e_m'],p[0]['n_m'])==(-5000,-5000)
    assert (p[-1]['e_m'],p[-1]['n_m'])==(5000,5000)
    assert p[840]['lat']==sites[0]['lat'] and p[840]['lon']==sites[0]['lon']
    assert all(p[i+1]['e_m']-p[i]['e_m']==250 for i in range(40))


def test_checkpoint_rejects_changed_input_and_coordinate(tmp_path):
    p=dict(index=840,e_m=0,n_m=0,lat=-89.,lon=0.)
    value=dict(**p,input_key='a',metrics=dict(sun_frac=.5,earth_frac=.5,both_frac=.2,longest_dark_h=1),
        horizon=dict(mask=[0.]*720,h0_m=0.,engine=dict(n_missing_samples=0)))
    path=tmp_path/'840.json';l.write(path,value)
    assert l.valid_checkpoint(path,'a',p)
    assert not l.valid_checkpoint(path,'b',p)
    assert not l.valid_checkpoint(path,'a',dict(p,lat=-88.))
    value['horizon']['engine']['n_missing_samples']=1;l.write(path,value)
    assert not l.valid_checkpoint(path,'a',p)


def test_partial_or_wrong_centre_is_not_published():
    import pytest
    with pytest.raises(AssertionError):l.validate_map(dict(grid=l.GRID,points=[]))
