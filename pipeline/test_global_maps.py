"""Tests for pipeline/global_maps.py on synthetic DEMs and a toy ephemeris.
Run:  python -m pytest pipeline/test_global_maps.py -q
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import global_maps as gm  # noqa: E402
import horizon as hz  # noqa: E402

R = gm.R_M


def mesa_fn(lat_c, lon_c, height, top_r_m, base_r_m):
    def f(lat, lon):
        p1, p2 = np.radians(lat_c), np.radians(lat)
        dl = np.radians(lon - lon_c)
        a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
        d = 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        return height * np.clip((base_r_m - d) / (base_r_m - top_r_m), 0, 1)
    return f


@pytest.fixture(scope="module")
def flat(tmp_path_factory):
    d = tmp_path_factory.mktemp("flat")
    near = gm.Dem(gm.write_synthetic_dem(d / "near_float.img", 8))
    far = gm.Dem(gm.write_synthetic_dem(d / "far_float.img", 4))
    eph = gm.load_ephem(gm.write_synthetic_ephem(d / "ephem.bin"), 2)
    return d, gm.Engine(near, far, eph)


MOUNT = (0.0, 20.0)          # observer; mesa 60 km due east


@pytest.fixture(scope="module")
def mountain(tmp_path_factory):
    d = tmp_path_factory.mktemp("mount")
    la, lo = hz.destination(MOUNT[0], MOUNT[1], np.array([90.0]), np.array([60000.0]))
    fn = mesa_fn(float(la.ravel()[0]), float(lo.ravel()[0]), 5000.0, 3000.0, 20000.0)
    near_p = gm.write_synthetic_dem(d / "near_float.img", 16, fn)
    far_p = gm.write_synthetic_dem(d / "far_float.img", 4, fn)
    eph = gm.load_ephem(gm.write_synthetic_ephem(d / "ephem.bin"), 2)
    return near_p, far_p, gm.Engine(gm.Dem(near_p), gm.Dem(far_p), eph)


def test_flat_sphere_sun_half_earth_near_far(flat):
    _, eng = flat
    pts = np.array([[0.0, 0.0], [0.0, 180.0], [0.0, 90.0], [45.0, -60.0], [-70.0, 10.0]])
    out = eng.points(pts[:, 0], pts[:, 1])
    sun, earth = out[:, 0], out[:, 1]
    assert np.all(np.abs(sun - 0.5) < 0.01), sun          # Sun in the equator plane: up half the time
    assert earth[0] == 1.0                                 # sub-Earth point
    assert earth[1] == 0.0                                 # far side
    assert earth[3] == 1.0 and earth[4] == 1.0             # Earth high in the sky there
    # both = sunlit AND Earth visible -> equals the sunlit share where the Earth is always up
    assert abs(out[0, 2] - 0.5) < 0.01 and out[1, 2] == 0.0
    # flat-sphere dip seen by a 2 m observer: about -0.087 deg (max of mask)
    dip = -math.degrees(math.acos(R / (R + 2.0)))
    assert abs(out[0, 4] - dip) < 0.01, out[0, 4]
    assert np.all(out[:, 5] == 0)                          # no missing terrain samples


def test_kernel_matches_horizon_py(mountain):
    near_p, far_p, eng = mountain
    out, masks = eng.points(np.array([MOUNT[0]]), np.array([MOUNT[1]]), keep_masks=True)
    chain = [(hz.GlobalCylSampler(near_p), 150.0), (hz.GlobalCylSampler(far_p), 300.0)]
    ref = hz.compute_horizon(MOUNT[0], MOUNT[1], chain)["mask"][::2]      # 720 -> 360 azimuths
    ours = masks[0]
    assert ours[90] > 3.0, ours[90]                                       # mesa due east (~4.4 deg)
    assert np.max(np.abs(ours - ref)) < 0.05, (np.argmax(np.abs(ours - ref)), np.max(np.abs(ours - ref)))


def test_mountain_delays_sunrise(mountain):
    *_, eng = mountain
    out = eng.points(np.array([MOUNT[0]]), np.array([MOUNT[1]]))
    # sunrise is in the east: the mesa (~4.4 deg high) hides ~4.4/360 of the synodic month
    assert 0.47 < out[0, 0] < 0.495, out[0, 0]
    assert out[0, 1] == 1.0                     # Earth at ~70 deg elevation


def test_resume_restart_and_export(flat, tmp_path):
    _, eng = flat
    folder = tmp_path / "gm"
    st = gm.Store(folder, 1, signature=eng.signature())
    assert gm.run_grid(eng, st, (80, 82), log=lambda *a, **k: None) == 2
    st2 = gm.Store(folder, 1, signature=eng.signature())            # "after a reboot"
    assert gm.run_grid(eng, st2, (80, 84), log=lambda *a, **k: None) == 2   # only the missing rows
    assert gm.run_grid(eng, st2, (80, 84), log=lambda *a, **k: None) == 0
    done = np.asarray(st2.done)
    assert done[80:84].all() and done.sum() == 4
    sun = np.asarray(st2.arr["sun"])
    assert np.all(np.isfinite(sun[80:84])) and np.all(np.isnan(sun[:80]))
    other = dict(eng.signature(), naz=180)
    with pytest.raises(SystemExit):
        gm.Store(folder, 1, signature=other)
    idx = gm.export(gm.Store(folder, 1, readonly=True), tmp_path / "web", log=lambda *a: None)
    assert idx["rows_done"] == 4 and idx["mock"] is True
    for name in gm.LAYERS:
        assert (tmp_path / "web" / f"{name}_overview.jpg").exists()
        from PIL import Image
        assert Image.open(tmp_path / "web" / f"{name}_overview.jpg").size == (4096, 2048)
        n_tiles = len(list((tmp_path / "web" / "tiles" / name).rglob("*.jpg")))
        assert n_tiles == sum(L["nx"] * L["ny"] for L in idx["tiles"]["levels"])
    json.loads((tmp_path / "web" / "index.json").read_text(encoding="utf-8"))


def test_cell_bound_is_conservative(mountain):
    near_p, _, eng = mountain
    # every cell within ~10 deg of the mesa must carry its 5 km height
    r, c = int(90 - MOUNT[0]), int(MOUNT[1] + 180)
    assert eng.bound[r, c] >= 4999.0
    assert eng.bound[r + 8, c - 8] >= 4999.0
    assert eng.bound[r, c + 60] < 100.0          # far away: flat


def test_validate_against_synthetic_pgda(flat, tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin
    _, eng = flat
    half = 470e3
    px = 5e3
    n = int(2 * half / px)
    crs = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
    paths = []
    for name, dn in (("sun.tif", 12500), ("earth.tif", 25000)):
        p = tmp_path / name
        with rasterio.open(p, "w", driver="GTiff", width=n, height=n, count=1, dtype="uint16", crs=crs,
                           transform=from_origin(-half, half, px, px)) as dst:
            dst.write(np.full((1, n, n), dn, np.uint16))
        paths.append(p)
    res = gm.validate(eng, paths[0], paths[1], n=20, seed=1, log=lambda *a: None)
    assert res["sun"]["n"] == 20
    assert res["sun"]["mae_pp"] < 2.0, res["sun"]         # flat sphere: ~50 % vs PGDA 0.5
    assert all(p["pgda_sun"] == 0.5 and p["pgda_earth"] == 1.0 for p in res["points"])
