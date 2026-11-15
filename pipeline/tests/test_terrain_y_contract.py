"""Reject incomplete terrain products and unsupported precise/safety claims."""
import hashlib
import importlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).parents[1]))


def fixture(tmp_path, polar=False):
    sid='TEST_SITE';sites={sid:dict(id=sid,lat=-85 if polar else 0,lon=0)}
    (tmp_path/'terrain').mkdir();(tmp_path/'relay').mkdir()
    relay=dict(params=dict(slope_box_m=250),candidates=dict(e_m=[0],n_m=[0],slope_deg=[1.2]))
    p=tmp_path/'relay'/f'{sid}.json';p.write_text(json.dumps(relay))
    sha=hashlib.sha256(p.read_bytes()).hexdigest()
    kind='polar_detailed' if polar else 'coarse_relay_comparison'
    source=dict(resolution_m=5,dem_name='PGDA',url='https://example.com/dem',window_path='raw.npz',window_sha256='0'*64,metadata={}) if polar else dict(label='coarse (SLDEM2015 59 m / LDEM_64)',dem_sources=[])
    obj=dict(schema_version=1,id=sid,lat=sites[sid]['lat'],lon=0,frame='MOON_ME_DE421',kind=kind,mock=False,
        thresholds_deg=[8,15],thresholds_label='reference_only',source=source,method=None,landing_slope_deg=None,
        slope_by_radius_m=None,roughness_within_500m=None,
        relay_box=dict(slope_deg=1.2,box_m=250,source_path=f'web/data/relay/{sid}.json',source_sha256=sha,candidate_index=0,e_m=0,n_m=0,provenance='copied existing rounded slope'),
        inputs=dict(producer_sha256='0'*64,sites_sha256='0'*64,relay_sha256=sha,parameters={},signature='0'*64),verification_status='author_checks_only_team_verification_pending')
    if polar:
        obj.update(method=dict(slope_window_cells=3,slope_center_span_projected_m=10,slope_footprint_projected_m=15,reference_radius_m=1737400,roughness_window_width_ground_m=50,roughness_window_cells=11,roughness_sample_center_span_ground_m=49.9),landing_slope_deg=1.5,
            slope_by_radius_m={str(r):dict(n=100,median_deg=2,p95_deg=3,max_deg=4,flat_fraction={'8':.8,'15':1},sampled_area_m2=2000) for r in (100,500,1000)},roughness_within_500m=dict(n=100,median_m=.1,p95_m=.2))
    index=dict(schema_version=1,mock=False,thresholds_deg=[8,15],thresholds_label='reference_only',sites=[dict(id=sid,path=f'{sid}.json',kind=kind,dem_resolution_m=5 if polar else None)])
    (tmp_path/'terrain/index.json').write_text(json.dumps(index))
    return sites,obj


def check(tmp_path,sites,obj):
    obj['content_sha256']=hashlib.sha256(json.dumps({k:v for k,v in obj.items() if k!='content_sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    (tmp_path/'terrain/TEST_SITE.json').write_text(json.dumps(obj))
    errors=[]
    importlib.import_module('check_terrain_y').check_terrain_y(tmp_path,sites,lambda w,m:errors.append(f'{w}: {m}'))
    return errors


def test_valid_coarse_and_reject_false_detail(tmp_path):
    sites,obj=fixture(tmp_path)
    assert check(tmp_path,sites,obj)==[]
    obj['landing_slope_deg']=1.234
    assert any('coarse' in e for e in check(tmp_path,sites,obj))


def test_relay_value_must_match_published_source(tmp_path):
    sites,obj=fixture(tmp_path);obj['relay_box']['slope_deg']=2.5
    assert any('relay' in e for e in check(tmp_path,sites,obj))


def test_flat_fraction_and_reference_label_enforced(tmp_path):
    sites,obj=fixture(tmp_path,True)
    assert check(tmp_path,sites,obj)==[]
    obj['slope_by_radius_m']['100']['flat_fraction']['8']=1.1
    obj['thresholds_label']='safe'
    errs=check(tmp_path,sites,obj)
    assert any('fraction' in e for e in errs)
    assert any('reference' in e for e in errs)


def test_missing_advertised_product_is_error(tmp_path):
    sites,obj=fixture(tmp_path)
    errors=[]
    importlib.import_module('check_terrain_y').check_terrain_y(tmp_path,sites,lambda w,m:errors.append(m))
    assert any('missing' in e for e in errors)


def test_changed_cached_content_is_error(tmp_path):
    sites,obj=fixture(tmp_path)
    assert check(tmp_path,sites,obj)==[]
    obj['relay_box']['slope_deg']=1.3
    (tmp_path/'terrain/TEST_SITE.json').write_text(json.dumps(obj))
    errors=[]
    importlib.import_module('check_terrain_y').check_terrain_y(tmp_path,sites,lambda w,m:errors.append(m))
    assert any('content' in e for e in errors)
