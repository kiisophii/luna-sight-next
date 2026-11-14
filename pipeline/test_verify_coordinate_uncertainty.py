"""Light analytic/fixture tests; never run the costly 15-node terrain audit."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_coordinate_uncertainty as v


def test_five_samples_per_regime_are_reproducible_and_without_replacement():
    chosen = v.select_points()
    assert chosen == v.select_points()
    assert len(chosen) == len(set(chosen)) == 15
    for sid in v.SAMPLE_IDS:
        assert len([index for site, index in chosen if site == sid]) == 5
    assert all(0 <= index < 121 for _, index in chosen)
    assert len(set(v.select_points(count_each=121))) == 363


def fixture_record():
    site = dict(id='TEST', lat=0., lon=0.)
    params = dict(min_km=.2, max_km=300., n_steps=4000, obs_height_m=2., early_stop=True, hmax_m=10800.)
    horizon = dict(id='TEST', mock=False, lat=0., lon=0., az_step_deg=.5, obs_height_m=2.,
        engine=dict(min_km=.2, max_km=300., n_steps=4000, early_stop=True, hmax_m=10800.,
        chain=[['LDEM_64', 300, 1, 0], ['LDEM_16', 300, 1, 0]]))
    points = []
    for index in range(121):
        east, north = (index % 11-5)*100, (index//11-5)*100
        lon, lat, _ = v.GEOD.fwd(0, 0, np.degrees(np.arctan2(east, north)), np.hypot(east, north))
        points.append(dict(index=index, e_m=east, n_m=north, lat=lat, lon=lon,
            sun_frac=(index+1)/43824, earth_frac=.5, both_frac=(index+1)/43824,
            longest_dark_h=100+index, h0_m=0., ground_resolution_m=59.,
            dem_sources=[dict(name='LDEM_64', res_m=474., to_km=300)]))
    baseline = {key: points[60][key] for key in v.METRICS}
    radii = {}
    for radius in (100, 300, 500):
        selected = [p for p in points if np.hypot(p['e_m'], p['n_m']) <= radius]
        summary = dict(n_nodes=len(selected))
        for key in v.METRICS:
            values = np.array([p[key] for p in selected])
            lo, med, hi = np.quantile(values, [.1, .5, .9], method='linear')
            summary[key] = dict(min=float(values.min()), max=float(values.max()),
                                p10=float(lo), median=float(med), p90=float(hi))
        radii[str(radius)] = summary
    provenance = dict(center=site, params=params, files_sha256={}, terrain_sources=[
        dict(path=f'data/raw/global/ldem_{ppd}_float.img', gate_km=300,
             resolution_m=1., sha256='0'*64, label_sha256='0'*64) for ppd in (64, 16)])
    provenance['input_key'] = hashlib.sha256(json.dumps(provenance, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    record = dict(id='TEST', complete=True, mock=False, center=dict(lat=0., lon=0.),
        frame='MOON_ME_DE421', radius_m=v.RADIUS, window=v.WINDOW.copy(), params=params,
        grid=dict(rows=11, cols=11, spacing_m=100, origin_e_m=-500, origin_n_m=-500, order='row-major'),
        nodes=points, ranges=radii, provenance=provenance,
        center_check=dict(matches=True, differences={k: 0 for k in v.METRICS}, metrics_sha256='BASELINE'))
    return record, site, baseline, horizon


def test_complete_schema_and_independent_circle_statistics():
    record, site, baseline, horizon = fixture_record()
    result = v.check_record(record, site, baseline, 'BASELINE', horizon)
    assert result['passed']
    assert [record['ranges'][str(radius)]['n_nodes'] for radius in (100, 300, 500)] == [5, 29, 81]


@pytest.mark.parametrize('fault', ['row_order', 'coordinate', 'window', 'fraction', 'stats', 'params', 'source_order', 'fingerprint'])
def test_contract_rejects_grid_statistics_and_legacy_method_changes(fault):
    record, site, baseline, horizon = fixture_record()
    if fault == 'row_order':
        record['nodes'][0]['index'] = 1
    elif fault == 'coordinate':
        record['nodes'][0]['lon'] += 1
    elif fault == 'window':
        record['window']['n'] -= 1
    elif fault == 'fraction':
        record['nodes'][0]['sun_frac'] = .123456
    elif fault == 'stats':
        record['ranges']['300']['sun_frac']['p10'] += .01
    elif fault == 'params':
        record['params']['min_km'] = .005
    elif fault == 'source_order':
        record['provenance']['terrain_sources'].reverse()
    else:
        record['provenance']['input_key'] = 'wrong'
    with pytest.raises(ValueError):
        v.check_record(record, site, baseline, 'BASELINE', horizon)


def test_centre_comparison_is_exact_and_does_not_silently_use_one_pp_tolerance():
    record, site, baseline, horizon = fixture_record()
    baseline['sun_frac'] += 1/43824
    result = v.check_record(record, site, baseline, 'BASELINE', horizon)
    assert not result['passed']
    assert not result['center_exact_match']
    assert not result['center_claim_matches']


def test_false_baseline_hash_claim_fails():
    record, site, baseline, horizon = fixture_record()
    assert not v.check_record(record, site, baseline, 'CHANGED', horizon)['passed']


def global_fixture(tmp_path):
    directory = tmp_path/'global'
    directory.mkdir()
    manifest = []
    for ppd, ground in ((64, 50.), (16, 7.)):
        path = directory/f'ldem_{ppd}_float.img'
        np.full((181, 360), ground, '<f4').tofile(path)
        path.with_suffix('.lbl').write_text('LINES = 181\nLINE_SAMPLES = 360\n'
            'MAP_RESOLUTION = 1\nLINE_PROJECTION_OFFSET = 90\nSAMPLE_PROJECTION_OFFSET = 0\n'
            'CENTER_LONGITUDE = 0\nSCALING_FACTOR = 0.001\n')
        manifest.append(dict(path=path.relative_to(tmp_path).as_posix(), sha256=v.sha256(path),
            gate_km=1 if ppd == 64 else 300, resolution_m=float(ppd),
            label_sha256=v.sha256(path.with_suffix('.lbl'))))
    return manifest


def test_global64_is_retained_and_manifest_gate_is_anchored_on_observer(tmp_path):
    manifest = global_fixture(tmp_path)
    site = dict(id='TEST', lat=70., lon=0.)
    lo, la, _ = v.GEOD.fwd(0., 70., 90., 5000.)
    terrain = v.ProvenanceDEM(site, dict(lat=la, lon=lo), tmp_path, manifest, tmp_path)
    lon, lat, _ = v.GEOD.fwd(np.full(3, lo), np.full(3, la), np.full(3, 90.), np.array([0., 999., 1001.]))
    assert np.allclose(terrain(lat, lon), [50., 50., 7.])
    assert [Path(s['path']).name for s in terrain.sources] == ['ldem_64_float.img', 'ldem_16_float.img']


@pytest.mark.parametrize('fault', ['omit_global64', 'terrain_hash', 'label_hash'])
def test_source_set_and_bytes_are_verified(tmp_path, fault):
    manifest = global_fixture(tmp_path)
    if fault == 'omit_global64':
        manifest = manifest[1:]
    elif fault == 'terrain_hash':
        manifest[0]['sha256'] = '0'*64
    else:
        manifest[0]['label_sha256'] = '0'*64
    with pytest.raises(ValueError):
        v.ProvenanceDEM(dict(id='TEST', lat=70., lon=0.), dict(lat=70., lon=0.), tmp_path, manifest, tmp_path)


@pytest.mark.parametrize('minimum,steps', [(.005, 8000), (.2, 4000)])
def test_ray_sampling_follows_legacy_params_and_record_rounding_is_explicit(monkeypatch, minimum, steps):
    record, _, _, _ = fixture_record()
    record['params'].update(min_km=minimum, n_steps=steps)
    record['nodes'][0]['h0_m'] = 10.12
    captured = []
    def trace(lat, lon, ground, height, terrain, azimuths, distances):
        assert len(azimuths) == 720
        assert azimuths[-1] == 359.5
        assert len(distances) == steps+1
        assert distances[0] == minimum*1000 and distances[-1] == 300000
        assert height == 2
        return np.full(720, 1.23456789)
    def evaluate(lat, lon, ground, mask, ephem):
        captured.append((ground, mask[0]))
        return {key: record['nodes'][0][key] for key in v.METRICS}
    class Terrain:
        verified_sources = []
        def __call__(self, lat, lon):
            return np.full(lat.shape, 10.12345)
    monkeypatch.setattr(v, 'trace_mask', trace)
    monkeypatch.setattr(v, 'evaluate_metrics', evaluate)
    result = v.verify_point('TEST', 0, record, np.zeros((1, 6)), Terrain())
    assert captured == [(10.12345, 1.23456789), (10.12, 1.2346)]
    assert result['passed']
    assert result['samples_per_ray'] == steps+1
