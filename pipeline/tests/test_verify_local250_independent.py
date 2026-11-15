"""Offline tests for pipeline/verify_local250_independent.py (synthetic data only, no network).

python -m pytest pipeline/tests/test_verify_local250_independent.py -q
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_local250_independent as v  # noqa: E402


def test_offsets_are_great_circle_bearing_and_length():
    from pyproj import Geod
    g = Geod(a=v.R_M, b=v.R_M)
    for lat, lon, e, n in [(-89.6866, -162.81, 3250, -4750), (-84.5, 40.0, -5000, 5000), (-87.0, 179.9, 250, 0)]:
        la, lo = v.offset_to_latlon(lat, lon, e, n)
        lo2, la2, _ = g.fwd(lon, lat, math.degrees(math.atan2(e, n)), math.hypot(e, n))
        assert abs(la - la2) < 1e-9 and abs(((lo - lo2 + 180) % 360) - 180) < 1e-9
    assert v.offset_to_latlon(-88.0, 10.0, 0, 0) == (-88.0, 10.0)


def test_grid_layout_and_shared_offsets():
    nodes = v.grid_nodes(dict(lat=-89.0, lon=0.0), v.GRID250)
    assert len(nodes) == 1681 and nodes[840]["e_m"] == 0 and nodes[840]["n_m"] == 0
    assert nodes[0]["e_m"] == -5000 and nodes[0]["n_m"] == -5000 and nodes[40]["e_m"] == 5000 and nodes[41]["n_m"] == -4750
    shared = [p for p in nodes if p["e_m"] % 1000 == 0 and p["n_m"] % 1000 == 0]
    assert len(shared) == 121 and all(p["row"] % 4 == 0 and p["col"] % 4 == 0 for p in shared)


def test_distance_grid():
    s = v.distances_km()
    assert s.size == 8001 and abs(s[0] - 0.005) < 1e-15 and abs(s[-1] - 300) < 1e-9
    assert np.allclose(s, np.geomspace(0.005, 300, 8001), rtol=1e-12, atol=0)


def test_bilinear_nan_propagates_and_bounds():
    a = np.arange(16, dtype=np.float32).reshape(4, 4)
    assert v.bilinear(a, np.array([1.5]), np.array([2.25]))[0] == pytest.approx(1.5 * 4 + 2.25)
    assert np.isnan(v.bilinear(a, np.array([-0.01, 3.01]), np.array([1.0, 1.0]))).all()
    a[2, 2] = np.nan
    assert np.isnan(v.bilinear(a, np.array([1.0]), np.array([1.0 + 1e-9]))[0])   # zero weight on NaN is still NaN


def _flat_rows(sun_el_deg, earth_el_deg, lat=-89.0, lon=30.0):
    """Ephemeris rows putting Sun / Earth at given elevations due north of a site (far away, tiny parallax)."""
    up, east, north = v.enu(lat, lon)
    rows = np.zeros((v.N_HOURS, 6))
    for c0, el in ((0, sun_el_deg), (3, earth_el_deg)):
        el = np.radians(np.broadcast_to(el, v.N_HOURS))
        d = np.cos(el)[:, None] * north + np.sin(el)[:, None] * up
        rows[:, c0:c0 + 3] = d * 1.5e8
    return rows


def test_metric_definitions_vector_equals_literal():
    rng = np.random.default_rng(3)
    sun = rng.uniform(-1, 1.5, v.N_HOURS)
    earth = rng.uniform(-1, 1.5, v.N_HOURS)
    sun[100:400] = -5                                     # 300 dark hours in a row
    rows = _flat_rows(sun, earth)
    mask = list(np.round(rng.uniform(0, 0.6, 720), 4))
    a = v.core_metrics_vec(-89.0, 30.0, 1000.0, mask, rows)
    b = v.core_metrics_literal(-89.0, 30.0, 1000.0, mask, rows)
    assert a == b and a["longest_dark_h"] >= 300


def test_sun_disc_rule():
    # flat 0 deg mask, Sun centre exactly on the horizon -> half the disc visible -> sunlit (>= 0.5)
    rows = _flat_rows(np.zeros(v.N_HOURS), np.full(v.N_HOURS, -1.0))
    m = v.core_metrics_vec(-89.0, 30.0, 0.0, [0.0] * 720, rows)
    assert m["earth_frac"] == 0 and m["both_frac"] == 0 and m["longest_dark_h"] in (0, v.N_HOURS)


def _fake_ldem(ppd=1.0, fn=None):
    L = v.Ldem.__new__(v.Ldem)
    L.ppd, L.nl, L.ns = ppd, int(180 * ppd), int(360 * ppd)
    L.lpo, L.spo, L.clon = 90 * ppd - 0.5, 180 * ppd - 0.5, 180.0
    lat = 90 - (np.arange(L.nl) + 0.5) / ppd
    lon = (np.arange(L.ns) + 0.5) / ppd
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    L.a = (fn(LA, LO) / 1000.0).astype(np.float32)        # km like LDEM
    L.res_m = math.radians(1 / ppd) * v.R_M
    return L


def test_kernel_matches_numpy_bruteforce_on_synthetic_terrain(monkeypatch):
    monkeypatch.setattr(v, "N_STEPS", 600)
    s_km = v.distances_km()
    fwd = v.proj_fwd()
    terrain = lambda la, lo: 800 * np.sin(np.radians(lo) * 3) * np.cos(np.radians(la) * 40) + 30 * (la + 90) ** 2  # noqa: E731
    ld = _fake_ldem(1.0, terrain)
    # two synthetic polar windows (res 500 m gate 25 km; res 2000 m gate 200 km); a NaN hole in the fine one
    wins = []
    for res, gate, half in ((500.0, 25.0, 40e3), (2000.0, 200.0, 240e3)):
        xs = np.arange(-half, half + res / 2, res)
        X, Y = np.meshgrid(xs, xs[::-1])
        inv = __import__("pyproj").Transformer.from_crs(v.CRS, "+proj=longlat +R=1737400 +no_defs", always_xy=True)
        lo, la = inv.transform(X, Y)
        a = terrain(la, lo).astype(np.float32) + np.float32(res / 100)
        if res == 500.0:
            a[10:14, 70:75] = np.nan
        wins.append((res, gate, dict(a=a, x0=xs[0], y0=xs[::-1][0], res=res)))
    nodes = [(-89.2, 15.0), (-89.25, 110.0)]
    kern = v.build_kernel()
    ups, easts, norths = (np.array([v.enu(*p)[i] for p in nodes]) for i in range(3))
    empty = np.full((2, 2), np.nan, np.float32)
    geo = np.zeros((6, 4))
    geo[:, 3] = -1
    arrs = [empty] * 6
    for q, (res, gate, w) in zip((1, 5), wins):
        geo[q] = [w["x0"], w["y0"], res, gate]
        arrs[q] = w["a"]
    mask, h0, ground, used, missing = kern(ups, easts, norths, s_km, *arrs, geo, ld.a, np.array([ld.lpo, ld.spo, ld.clon, ld.ppd]),
                                           ld.a, np.array([ld.lpo, ld.spo, ld.clon, ld.ppd]))
    assert missing.sum() == 0
    for i, (la, lo) in enumerate(nodes):
        m2, h02, g2, used2 = v.brute_horizon(la, lo, [(5, 3.0, None)] + [(r, g, w) for r, g, w in wins], [("LDEM_64", ld), ("LDEM_16", ld)], fwd)
        assert abs(h0[i] - h02) < 1e-6 and ground[i] == 1 and g2 == 500.0
        assert np.max(np.abs(mask[i] - m2)) < 1e-7
        mine = {int(k): float(u) for k, u in enumerate(used[i].max(axis=0)) if u >= 0}
        assert set(mine) == {1, 5, 6}                 # fine window, coarse window, global beyond 200 km
        assert abs(mine[6] - 300.0) < 1e-9 and abs(used2["LDEM_64"] - 300.0) < 1e-9


def test_own_tile_decoder_predictor3_deflate(monkeypatch):
    import zlib
    rng = np.random.default_rng(5)
    th, tw = 8, 16
    a = (rng.normal(0, 800, (th, tw))).astype(np.float32)
    a[2, 3] = np.nan
    # TIFF floating-point predictor (encoder written from the TIFF Technical Note 3 description)
    be = a.astype(">f4").view(np.uint8).reshape(th, tw, 4).transpose(0, 2, 1).reshape(th, 4 * tw)
    diff = be.copy()
    diff[:, 1:] = (be[:, 1:].astype(np.int16) - be[:, :-1].astype(np.int16)) % 256
    blob = zlib.compress(diff.astype(np.uint8).tobytes())

    class R:
        content = blob

    monkeypatch.setattr("requests.get", lambda *a, **k: R())
    out = v.own_tile("http://x", 0, len(blob), th, tw)
    np.testing.assert_array_equal(out, a)
