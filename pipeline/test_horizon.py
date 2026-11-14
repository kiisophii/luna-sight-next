"""Tests for pipeline/horizon.py.  Run:  python -m pytest pipeline/test_horizon.py -q"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as hz  # noqa: E402

R = hz.R_M


def angdist_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (haversine)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(np.asarray(lon2) - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def mesa(lat_c, lon_c, height, top_r_m, base_r_m):
    """Truncated cone: flat top of radius top_r_m, linear flank to base_r_m, 0 elsewhere."""
    def f(lat, lon):
        d = angdist_m(lat_c, lon_c, lat, lon)
        return height * np.clip((base_r_m - d) / (base_r_m - top_r_m), 0, 1)
    return f


def el_exact(height_m, dist_m, obs_r):
    th = dist_m / R
    rt = R + height_m
    return math.degrees(math.atan2(rt * math.cos(th) - obs_r, rt * math.sin(th)))


FLAT = [(hz.FunctionSampler(lambda la, lo: np.zeros_like(la), "FLAT", 1.0), 400.0)]


# (a) flat sphere -> analytic dip for an observer 2 m above the surface
def test_flat_sphere_dip():
    res = hz.compute_horizon(10.0, 20.0, FLAT)
    dip = -math.degrees(math.acos(R / (R + 2.0)))          # = -0.0869 deg
    assert res["h0_m"] == 0.0
    assert np.allclose(res["mask"], dip, atol=1e-4), (res["mask"].min(), res["mask"].max(), dip)


# (b) synthetic cone mountain at a known distance and height
@pytest.mark.parametrize("az_deg,dist_km,height_m", [(30.0, 20.0, 3000.0), (247.5, 120.0, 6000.0)])
def test_cone_mountain_elevation(az_deg, dist_km, height_m):
    lat0, lon0 = 10.0, 20.0
    la, lo = hz.destination(lat0, lon0, np.array([az_deg]), np.array([dist_km * 1000.0]))
    top_r = 300.0
    terrain = hz.FunctionSampler(mesa(float(la.ravel()[0]), float(lo.ravel()[0]), height_m, top_r, 8000.0))
    res = hz.compute_horizon(lat0, lon0, [(terrain, 400.0)])
    k = int(round(az_deg / hz.AZ_STEP_DEG))
    # highest point of the flat top as seen from the observer = its nearest edge
    want = el_exact(height_m, dist_km * 1000.0 - top_r, R + 2.0)
    assert abs(res["mask"][k] - want) < 0.02, (res["mask"][k], want)
    # far from the mountain the horizon is the flat-sphere dip
    opposite = (k + hz.N_AZ // 2) % hz.N_AZ
    assert abs(res["mask"][opposite] + math.degrees(math.acos(R / (R + 2.0)))) < 1e-4


# (c) azimuth convention: a mountain due east shows up at index 180 (= 90 deg)
def test_east_mountain_index():
    lat0, lon0 = 0.0, 0.0
    la, lo = hz.destination(lat0, lon0, np.array([90.0]), np.array([15000.0]))
    assert abs(float(la.ravel()[0])) < 1e-9 and float(lo.ravel()[0]) > 0   # east = +lon
    terrain = hz.FunctionSampler(mesa(float(la.ravel()[0]), float(lo.ravel()[0]), 2000.0, 50.0, 2000.0))
    res = hz.compute_horizon(lat0, lon0, [(terrain, 400.0)])
    assert int(np.argmax(res["mask"])) == 180
    n = hz.N_AZ
    la, lo = hz.destination(lat0, lon0, np.array([0.0]), np.array([15000.0]))   # due north
    terrain = hz.FunctionSampler(mesa(float(la.ravel()[0]), float(lo.ravel()[0]), 2000.0, 50.0, 2000.0))
    assert int(np.argmax(hz.compute_horizon(lat0, lon0, [(terrain, 400.0)])["mask"])) in (0, n)


def test_early_stop_does_not_change_result():
    lat0, lon0 = -45.0, 170.0
    rng = np.random.default_rng(1)
    peaks = [(rng.uniform(0, 360), rng.uniform(5, 250), rng.uniform(500, 5000)) for _ in range(12)]
    fs = []
    for az, d, h in peaks:
        la, lo = hz.destination(lat0, lon0, np.array([az]), np.array([d * 1000.0]))
        fs.append(mesa(float(la.ravel()[0]), float(lo.ravel()[0]), h, 200.0, 15000.0))
    terrain = hz.FunctionSampler(lambda la, lo: np.max([f(la, lo) for f in fs], axis=0))
    a = hz.compute_horizon(lat0, lon0, [(terrain, 400.0)], early_stop=True, n_steps=1500)
    b = hz.compute_horizon(lat0, lon0, [(terrain, 400.0)], early_stop=False, n_steps=1500)
    assert np.array_equal(a["mask"], b["mask"])


def test_chain_falls_through_to_coarser_sampler():
    """Fine sampler covers only 5 km (NaN beyond); coarse one supplies the rest."""
    lat0, lon0 = 0.0, 0.0
    fine = hz.FunctionSampler(lambda la, lo: np.where(angdist_m(lat0, lon0, la, lo) < 5000, 0.0, np.nan),
                              "FINE", 5)
    coarse = hz.FunctionSampler(lambda la, lo: np.full_like(la, 100.0), "COARSE", 1000)
    res = hz.compute_horizon(lat0, lon0, [(fine, 300.0), (coarse, 300.0)])
    names = [d["name"] for d in res["dem_sources"]]
    assert names == ["FINE", "COARSE"]
    assert res["dem_sources"][0]["to_km"] < 5.0
    assert res["n_missing"] == 0


def test_polar_stereo_matches_pyproj():
    pyproj = pytest.importorskip("pyproj")
    p = pyproj.Proj("+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m")
    lat = np.array([-89.9, -88.0, -85.5, -80.0, -70.0])
    lon = np.array([0.0, 45.0, -120.0, 179.0, -60.0])
    x, y = hz.polar_stereo_xy(lat, lon)
    px, py = p(lon, lat)
    assert np.allclose(x, px, atol=1e-3) and np.allclose(y, py, atol=1e-3)


def test_samplers_roundtrip(tmp_path):
    """Adapters read synthetic caches in the card 2 / card 3 formats correctly."""
    # polar stereographic cache with a plane z = 0.01*x + 0.02*y
    x = np.arange(-5000.0, 5001.0, 20.0)
    y = np.arange(5000.0, -5001.0, -20.0) + 30000.0
    X, Y = np.meshgrid(x, y)
    np.savez(tmp_path / "p.npz", height_m=(0.01 * X + 0.02 * Y).astype(np.float32), x_m=x, y_m=y,
             metadata='{"resolution_m": 20, "radius_m": 5000, '
                      '"projection": "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400.0 +units=m"}')
    s = hz.PolarStereoSampler(tmp_path / "p.npz")
    lat = np.array([-89.0105, -89.0])
    lon = np.array([1.0, 179.0])
    px, py = hz.polar_stereo_xy(lat, lon)
    v = s.sample(lat, lon)
    assert abs(v[0] - (0.01 * px[0] + 0.02 * py[0])) < 0.05 and np.isnan(v[1])
    assert s.name == "PGDA_LOLA_20M" and s.radius_km == 5.0
    # lat/lon window crossing the 180 deg meridian
    lat_c = 10.0 - (np.arange(200) + 0.5) / 64
    lon_u = 178.0 + (np.arange(300) + 0.5) / 64          # 178 .. 182.7 E (unwrapped)
    LA, LU = np.meshgrid(lat_c, lon_u, indexing="ij")
    np.savez(tmp_path / "w.npz", height_m=(100 * LA + 10 * LU).astype(np.float32), lat=lat_c,
             lon=(lon_u + 180) % 360 - 180, lon_unwrapped=lon_u, meta='{"radius_km": 30}')
    w = hz.LatLonWindowSampler(tmp_path / "w.npz")
    v = w.sample(np.array([9.0, 9.0, 9.0]), np.array([179.5, -179.5, 170.0]))
    assert abs(v[0] - (900 + 1795)) < 0.1 and abs(v[1] - (900 + 1805)) < 0.1 and np.isnan(v[2])


def test_global_cyl_sampler(tmp_path):
    ppd, nl, ns = 4, 720, 1440
    lbl = tmp_path / "ldem_4_float.lbl"
    lbl.write_text(f"""LINES = {nl}
LINE_SAMPLES = {ns}
MAP_RESOLUTION = {ppd} <pix/deg>
LINE_PROJECTION_OFFSET = {nl / 2 - 0.5} <PIXEL>
SAMPLE_PROJECTION_OFFSET = {ns / 2 - 0.5} <PIXEL>
CENTER_LONGITUDE = 180.0 <DEG>
MAXIMUM_LATITUDE = 90.0 <DEG>
OFFSET = 1737.4
SCALING_FACTOR = 1
UNIT = KILOMETER
""")
    lat_c = 90 - (np.arange(nl) + 0.5) / ppd
    lon_c = (np.arange(ns) + 0.5) / ppd
    LA, LO = np.meshgrid(lat_c, lon_c, indexing="ij")
    (np.sin(np.radians(LO)) + LA / 100).astype("<f4").tofile(tmp_path / "ldem_4_float.img")
    g = hz.GlobalCylSampler(tmp_path / "ldem_4_float.img")
    v = g.sample(np.array([12.3, -40.0, 0.0]), np.array([-30.0, 120.0, 0.05]))
    want = (np.sin(np.radians([330.0, 120.0, 0.05])) + np.array([12.3, -40.0, 0.0]) / 100) * 1000
    assert np.allclose(v, want, atol=2.0), (v, want)    # bilinear error on a sine, metres
    assert g.name == "LDEM_4"
