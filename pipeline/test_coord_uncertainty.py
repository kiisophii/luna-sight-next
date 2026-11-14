import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

import coord_uncertainty as cu

ROOT = Path(__file__).resolve().parents[1]
SITE = dict(id='TEST', lat=20.1911, lon=30.7723)


def test_grid_geometry():
    pts = cu.grid_points(SITE)
    assert len(pts) == 121 and [p['index'] for p in pts] == list(range(121))
    c = pts[60]
    assert (c['e_m'], c['n_m'], c['lat'], c['lon']) == (0, 0, SITE['lat'], SITE['lon'])
    assert (pts[0]['e_m'], pts[0]['n_m']) == (-500, -500) and (pts[10]['e_m'], pts[10]['n_m']) == (500, -500)
    # node 61 is 100 m east: same latitude to ~1e-6 deg, longitude +100 m
    d_lon = math.radians(pts[61]['lon'] - SITE['lon']) * 1737400 * math.cos(math.radians(SITE['lat']))
    assert abs(d_lon - 100) < 0.01 and abs(pts[61]['lat'] - SITE['lat']) < 1e-6
    # node 71 is 100 m north
    assert abs(math.radians(pts[71]['lat'] - SITE['lat']) * 1737400 - 100) < 0.01


def _fake_nodes():
    rng = np.random.default_rng(1)
    nodes = []
    for p in cu.grid_points(SITE):
        s, e = rng.uniform(0.3, 0.6), rng.uniform(0.5, 1)
        nodes.append(dict(**p, h0_m=0.0, sun_frac=s, earth_frac=e, both_frac=min(s, e) * 0.9,
                          longest_dark_h=int(rng.integers(300, 400))))
    return nodes


def test_radius_counts_and_stats():
    nodes = _fake_nodes()
    assert [cu.summarize(nodes, r)['n_nodes'] for r in cu.RADII_M] == [5, 29, 81]
    r = cu.summarize(nodes, 300)
    sel = [n['sun_frac'] for n in nodes if n['e_m'] ** 2 + n['n_m'] ** 2 <= 90000]
    assert r['sun_frac']['min'] == min(sel) and r['sun_frac']['max'] == max(sel)
    assert r['sun_frac']['median'] == pytest.approx(float(np.median(sel)))
    assert isinstance(r['longest_dark_h']['max'], int)


def _record():
    nodes = _fake_nodes()
    return dict(id='TEST', center=dict(lat=SITE['lat'], lon=SITE['lon']),
                grid=dict(rows=11, cols=11, spacing_m=100, origin_e_m=-500, origin_n_m=-500, order=''),
                window=cu.WINDOW, params=cu.PARAMS, frame='MOON_ME_DE421', radius_m=1737400.0,
                ranges={str(r): cu.summarize(nodes, r) for r in cu.RADII_M}, nodes=nodes,
                complete=True, mock=False)


def test_validate_record_accepts_and_rejects():
    rec = _record()
    cu.validate_record(rec, SITE)
    bad = copy.deepcopy(rec); bad['ranges']['300']['sun_frac']['max'] += 0.01
    with pytest.raises(ValueError):
        cu.validate_record(bad, SITE)
    bad = copy.deepcopy(rec); bad['nodes'][5]['lat'] += 0.001
    with pytest.raises(ValueError):
        cu.validate_record(bad, SITE)
    bad = copy.deepcopy(rec); bad['params'] = dict(rec['params'], min_km=0.005)
    with pytest.raises(ValueError):
        cu.validate_record(bad, SITE)
    cu.validate_record(bad, SITE, strict_params=False)


@pytest.mark.parametrize('path', sorted((ROOT / 'web/data/uncertainty').glob('*.json')))
def test_published_centre_equals_metrics(path):
    u = json.loads(path.read_text(encoding='utf-8'))
    m = json.loads((ROOT / 'web/data/metrics' / path.name).read_text(encoding='utf-8'))
    c = u['nodes'][60]
    assert (c['e_m'], c['n_m']) == (0, 0)
    for k in ('sun_frac', 'earth_frac', 'both_frac', 'longest_dark_h'):
        assert c[k] == m[k]
