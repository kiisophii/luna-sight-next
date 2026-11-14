"""Independent verifier checks with analytic geometry and real cache fixtures."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


def verifier():
    assert importlib.util.find_spec('verify_card18_local'), 'independent verifier is not implemented'
    import verify_card18_local
    return verify_card18_local


def test_selection_is_reproducible_unique_and_uses_entire_population():
    v = verifier()
    first = v.select_points()
    assert first == v.select_points()
    assert len(first) == len(set(first)) == 5
    assert all(site in v.SITE_IDS and 0 <= index < 441 for site, index in first)
    population = v.select_points(count=2646)
    assert len(set(population)) == 2646
    assert {index for site, index in population if site == 'SHACKLETON_RIM'} == set(range(441))


def test_cyclic_horizon_interpolation_crosses_north():
    v = verifier()
    mask = np.zeros(720)
    mask[719], mask[0], mask[1] = 10, 2, 6
    assert np.allclose(v.horizon_at(mask, np.array([359.75, 0, .25, 360])), [6, 2, 4, 2])


def test_metrics_use_topocentric_observer_and_distinct_equality_rules():
    v = verifier()
    # At (0, 0), local up=e_x, north=e_z, east=e_y. Build known rays.
    observer_km = (1737400 + 102) / 1000
    ephem = np.array([[observer_km, 100, 0, observer_km, 100, 0],
                      [observer_km-100, 100, 0, observer_km+100, 100, 0],
                      [observer_km-100, 100, 0, observer_km-100, 100, 0],
                      [observer_km+100, 100, 0, observer_km+100, 100, 0]])
    result = v.evaluate_metrics(0, 0, 100, np.zeros(720), ephem)
    assert result == dict(sun_frac=.5, earth_frac=.5, both_frac=.25, longest_dark_h=2)


def test_dark_runs_are_continuous_not_circular():
    v = verifier()
    assert v.longest_dark_run(np.array([False, False, True, False])) == 2
    assert v.longest_dark_run(np.array([False]*4)) == 4
    assert v.longest_dark_run(np.array([True]*4)) == 0


def test_comparison_enforces_one_pp_and_does_not_invent_dark_tolerance():
    v = verifier()
    expected = dict(sun_frac=.5, earth_frac=.6, both_frac=.4, longest_dark_h=10)
    within = dict(sun_frac=.51, earth_frac=.6, both_frac=.39, longest_dark_h=100)
    result = v.compare_metrics(within, expected)
    assert result['passed']
    assert result['longest_dark_h']['absolute_difference_h'] == 90
    assert 'passed' not in result['longest_dark_h']
    within['sun_frac'] = .511
    assert not v.compare_metrics(within, expected)['passed']


def cache_fixture(tmp_path):
    from pyproj import Proj
    projection = '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m'
    project = Proj(projection)
    x, y = project(0, -89)
    polar = tmp_path/'polar'/'5'
    polar.mkdir(parents=True)
    np.savez(polar/'TEST.npz', x_m=np.array([x-20000, x+20000]),
             y_m=np.array([y+20000, y-20000]), height_m=np.full((2, 2), 50.),
             metadata=json.dumps(dict(projection=projection, radius_m=19000)))
    global_dir = tmp_path/'global'
    global_dir.mkdir()
    np.full((181, 360), 7., dtype='<f4').tofile(global_dir/'ldem_16_float.img')
    (global_dir/'ldem_16_float.lbl').write_text('LINES = 181\nLINE_SAMPLES = 360\n'
        'MAP_RESOLUTION = 1\nLINE_PROJECTION_OFFSET = 90\nSAMPLE_PROJECTION_OFFSET = 0\n'
        'CENTER_LONGITUDE = 0\nSCALING_FACTOR = 0.001\n')


def test_expanded_cache_does_not_expand_gate_and_gate_follows_point(tmp_path):
    v = verifier()
    cache_fixture(tmp_path)
    point_lon, point_lat, _ = v.GEOD.fwd(0, -89, 90, 5000)
    terrain = v.PointDEM(dict(id='TEST', lat=-89, lon=0),
                         dict(lat=point_lat, lon=point_lon), tmp_path)
    lo, la, _ = v.GEOD.fwd(np.full(3, point_lon), np.full(3, point_lat),
                          np.full(3, 90.), np.array([0., 2999., 3001.]))
    assert np.allclose(terrain(la, lo), [50, 50, 7])
    assert terrain.sources[0]['max_km'] == 3


def test_missing_near_source_falls_back_without_zero_terrain(tmp_path):
    v = verifier()
    cache_fixture(tmp_path)
    point_lon, point_lat, _ = v.GEOD.fwd(0, -89, 90, 50000)
    terrain = v.PointDEM(dict(id='TEST', lat=-89, lon=0),
                         dict(lat=point_lat, lon=point_lon), tmp_path)
    assert terrain(np.array([point_lat]), np.array([point_lon]))[0] == 7


def test_manifest_detects_changed_source_and_unreported_source(tmp_path):
    v = verifier()
    cache_fixture(tmp_path)
    terrain = v.PointDEM(dict(id='TEST', lat=-89, lon=0), dict(lat=-89, lon=0), tmp_path)
    manifest = []
    for source in terrain.sources:
        path = Path(source['path'])
        manifest.append(dict(path=str(path.relative_to(tmp_path)), sha256=v.sha256(path),
                             gate_km=source['max_km']))
    assert len(v.check_sources(terrain, manifest, tmp_path)) == 2
    with pytest.raises(ValueError, match='source set'):
        v.check_sources(terrain, manifest[:1], tmp_path)
    manifest[0]['sha256'] = '0'*64
    with pytest.raises(ValueError, match='hash'):
        v.check_sources(terrain, manifest, tmp_path)


def test_ephemeris_rejects_wrong_window_or_size(tmp_path):
    v = verifier()
    meta = dict(start='2026-01-01T00:00:00Z', n=43824, step_h=1,
                frame='MOON_ME_DE421', units='km', mock=False)
    (tmp_path/'ephem.json').write_text(json.dumps(meta))
    np.zeros((2, 6), '<f4').tofile(tmp_path/'ephem.bin')
    with pytest.raises(ValueError, match='43824'):
        v.load_ephemeris(tmp_path)
    np.zeros((43824, 6), '<f4').tofile(tmp_path/'ephem.bin')
    assert v.load_ephemeris(tmp_path).shape == (43824, 6)
    meta['start'] = '2025-01-01T00:00:00Z'
    (tmp_path/'ephem.json').write_text(json.dumps(meta))
    with pytest.raises(ValueError, match='window'):
        v.load_ephemeris(tmp_path)


def maps_fixture(tmp_path):
    v = verifier()
    directory = tmp_path/'local'
    directory.mkdir()
    for site in v.SITE_IDS:
        points = []
        for index in range(441):
            east, north = (index % 21-10)*1000, (index // 21-10)*1000
            lon, lat, _ = v.GEOD.fwd(0, -89, np.degrees(np.arctan2(east, north)), np.hypot(east, north))
            points.append(dict(index=index, e_m=east, n_m=north, lat=lat, lon=lon,
                h0_m=0, sun_frac=.5, earth_frac=.5, both_frac=.5, longest_dark_h=10))
        record = dict(id=site, complete=True, mock=False, center=dict(lat=-89, lon=0),
            frame='MOON_ME_DE421', radius_m=1737400,
            window=dict(start='2026-01-01T00:00:00Z', n=43824, step_h=1),
            params=dict(min_km=.005, max_km=300, n_steps=8000, obs_height_m=2),
            grid=dict(rows=21, cols=21, spacing_m=1000, origin_e_m=-10000, origin_n_m=-10000),
            points=points)
        (directory/(site+'.json')).write_text(json.dumps(record))
    return directory/(v.SITE_IDS[0]+'.json')


@pytest.mark.parametrize('fault', ['row_order', 'coordinate', 'window', 'fraction', 'observer'])
def test_map_contract_rejects_wrong_grid_window_metrics_and_parameters(tmp_path, fault):
    v = verifier()
    path = maps_fixture(tmp_path)
    assert len(v.load_maps(tmp_path)) == 6
    record = json.loads(path.read_text())
    if fault == 'row_order':
        record['points'][0]['index'] = 1
    elif fault == 'coordinate':
        record['points'][0]['lon'] += 1
    elif fault == 'window':
        record['window']['n'] = 2
    elif fault == 'fraction':
        record['points'][0]['sun_frac'] = 5
    else:
        record['params']['obs_height_m'] = 20
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        v.load_maps(tmp_path)


def test_output_provenance_rejects_stale_production_inputs(tmp_path):
    v = verifier()
    source = tmp_path/'core.js'
    source.write_text('first')
    record = dict(provenance=dict(files_sha256={'core.js': v.sha256(source)}))
    v.check_output_inputs(record, tmp_path)
    source.write_text('changed')
    with pytest.raises(ValueError, match='input hash'):
        v.check_output_inputs(record, tmp_path)
