import json
from pathlib import Path
import numpy as np
import pytest
import horizon as hz
import local_maps as lm


def test_grid_geodesic_centre_order_and_polar_wrap():
    site = dict(id='TEST', lat=-89.9, lon=179.9)
    p = lm.grid_points(site)
    assert len(p) == 441 and p[220]['lat'] == pytest.approx(site['lat'])
    assert p[220]['lon'] == pytest.approx(site['lon'])
    assert (p[0]['e_m'], p[0]['n_m']) == (-10000, -10000)
    assert (p[-1]['e_m'], p[-1]['n_m']) == (10000, 10000)
    assert all(-180 <= x['lon'] <= 180 for x in p)
    from pyproj import Geod
    geod = Geod(a=1737400, b=1737400)
    for point in p:
        distance = geod.inv(site['lon'],site['lat'],point['lon'],point['lat'])[2]
        assert distance == pytest.approx(np.hypot(point['e_m'],point['n_m']),abs=1e-5)


def test_shared_sampler_preserves_values_but_not_expanded_gate(tmp_path):
    path=tmp_path/'source.npz'
    meta=dict(projection='+proj=stere +lat_0=-90 +R=1737400',resolution_m=5,radius_m=19000)
    np.savez(path,height_m=np.arange(9).reshape(3,3).astype(float),x_m=[-5,0,5],y_m=[5,0,-5],metadata=json.dumps(meta))
    descriptor=lm.prepare_sampler(path,tmp_path/'shared',3)
    sample=lm.load_sampler(descriptor)
    assert descriptor['gate_km']==3
    assert isinstance(sample.h,np.memmap)
    lat=np.array([-90.]);lon=np.array([0.])
    assert np.array_equal(sample.sample(lat,lon),hz.PolarStereoSampler(path).sample(lat,lon))


def test_reject_old_centre_or_unexpanded_window():
    site=dict(id='TEST',lat=-89,lon=2)
    meta=dict(site=site.copy(),radius_m=19000,frame='MOON_ME_DE421')
    lm.validate_source_metadata(meta,site,3)
    meta['radius_m']=3000
    with pytest.raises(ValueError,match='expanded'):
        lm.validate_source_metadata(meta,site,3)
    meta['radius_m']=19000;meta['site']['lon']=3
    with pytest.raises(ValueError,match='centre'):
        lm.validate_source_metadata(meta,site,3)


def test_resume_rejects_changed_inputs_and_corrupt_record(tmp_path):
    key=lm.fingerprint(dict(ephem='a',core='b',terrain='c',lat=-89))
    assert key != lm.fingerprint(dict(ephem='changed',core='b',terrain='c',lat=-89))
    path=tmp_path/'point.json'
    path.write_text(json.dumps(dict(input_key=key,index=2,metrics={'sun_frac':.5})))
    assert not lm.resume_valid(path,key,2)
    record=dict(input_key=key,index=2,metrics=dict(sun_frac=.5,earth_frac=.4,both_frac=.3,longest_dark_h=1),horizon=dict(mask=[0]*720,h0_m=0,engine={'n_missing_samples':0}))
    path.write_text(json.dumps(record))
    assert lm.resume_valid(path,key,2)
    assert not lm.resume_valid(path,key,1)
    assert not lm.resume_valid(path,'different',2)


def test_reject_incomplete_public_map():
    with pytest.raises(ValueError,match='441'):
        lm.validate_map(dict(points=[],grid=dict(rows=21,cols=21)))


def test_public_map_rejects_wrong_node_order_and_window():
    site=dict(id='TEST',lat=-89,lon=179)
    points=[dict(**p,h0_m=0,ground_resolution_m=5,sun_frac=.5,earth_frac=.6,both_frac=.3,longest_dark_h=2,dem_sources=[])
            for p in lm.grid_points(site)]
    record=dict(points=points,center=dict(lat=-89,lon=179),complete=True,mock=False,
        frame='MOON_ME_DE421',radius_m=1737400,params=lm.PARAMS,
        grid=dict(rows=21,cols=21,spacing_m=1000,origin_e_m=-10000,origin_n_m=-10000),
        window=dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824))
    lm.validate_map(record)
    record['points'][0]['e_m']=0
    with pytest.raises(ValueError,match='grid'):
        lm.validate_map(record)
    record['points'][0]['e_m']=-10000
    record['window']['n']=1
    with pytest.raises(ValueError,match='window'):
        lm.validate_map(record)


def test_actual_core_helper_matches_catalogue_centre():
    root=Path(__file__).resolve().parents[1]
    sid='SHACKLETON_RIM'
    site=next(s for s in json.loads((root/'web/data/sites.json').read_text(encoding='utf-8')) if s['id']==sid)
    horizon=json.loads((root/f'web/data/horizon/{sid}.json').read_text(encoding='utf-8'))
    expected=json.loads((root/f'web/data/metrics/{sid}.json').read_text(encoding='utf-8'))
    with lm.CoreMetrics(root) as core:
        actual=core.metrics(site,horizon)
    for k in ['sun_frac','earth_frac','both_frac','longest_dark_h']:
        assert actual[k]==expected[k]


def test_actual_core_extreme_masks_and_clipped_dark_run():
    site=dict(id='TEST_SYNTHETIC',lat=12.34,lon=56.78)
    horizon=dict(**site,h0_m=0,obs_height_m=2,az_step_deg=.5,mask=[90]*720,
        max_range_km=300,dem_sources=[{'name':'synthetic test fixture'}],mock=False)
    with lm.CoreMetrics() as core:
        assert core.metrics(site,horizon)==dict(sun_frac=0,earth_frac=0,both_frac=0,longest_dark_h=43824)
        horizon['mask']=[-90]*720
        assert core.metrics(site,horizon)==dict(sun_frac=1,earth_frac=1,both_frac=1,longest_dark_h=0)
