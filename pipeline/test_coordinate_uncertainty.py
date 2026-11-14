import json
import numpy as np
import pytest
import coordinate_uncertainty as cu

def test_grid_and_circular_statistics():
    site=dict(id='TEST',lat=-89.9,lon=179.9)
    points=cu.grid_points(site)
    assert len(points)==121 and points[60]['lat']==site['lat'] and points[60]['lon']==site['lon']
    assert (points[0]['e_m'],points[0]['n_m'])==(-500,-500)
    for p in points:
        p.update(sun_frac=(p['e_m']+500)/1000,earth_frac=.5,both_frac=0,longest_dark_h=p['index'])
    stats=cu.summarize(points)
    assert [stats[str(r)]['n'] for r in [100,300,500]]==[5,29,81]
    assert stats['300']['sun_frac']['min']==.2
    assert stats['300']['sun_frac']['max']==.8
    assert stats['300']['sun_frac']['median']==.5
    assert set(stats['100']['longest_dark_h'])=={'min','max','p10','median','p90'}
    assert all(-180<=p['lon']<=180 for p in points)

def test_centre_mismatch_rejected():
    a=dict(sun_frac=.5,earth_frac=.5,both_frac=.5,longest_dark_h=10)
    assert cu.check_center(a,a)['matches']
    with pytest.raises(ValueError,match='centre'):
        cu.check_center(a,dict(a,sun_frac=.6))

def test_legacy_per_site_parameters_keep_both_main_methods():
    sites={s['id']:s for s in cu.read(cu.ROOT/'web/data/sites.json')}
    polar=cu.catalogue_params(sites['SHACKLETON_RIM'])
    nonpolar=cu.catalogue_params(sites['APOLLO11'])
    assert (polar['min_km'],polar['n_steps'])==(.005,8000)
    assert (nonpolar['min_km'],nonpolar['n_steps'])==(.2,4000)
    assert polar['obs_height_m']==nonpolar['obs_height_m']==2

def test_checkpoint_key_and_geometry_are_validated(tmp_path):
    p=cu.grid_points(dict(id='X',lat=0,lon=0))[60]
    path=tmp_path/'060.json'
    value=dict(point=p,input_key='key',metrics=dict(sun_frac=.5,earth_frac=.5,both_frac=.5,longest_dark_h=10),horizon=dict(mask=[0.]*720,h0_m=0.,engine={'n_missing_samples':0}))
    path.write_text(json.dumps(value))
    assert cu.valid_checkpoint(path,'key',p)
    assert not cu.valid_checkpoint(path,'new',p)
    assert not cu.valid_checkpoint(path,'key',dict(p,lat=1))
    value['metrics']['sun_frac']=float('nan');path.write_text(json.dumps(value))
    assert not cu.valid_checkpoint(path,'key',p)
