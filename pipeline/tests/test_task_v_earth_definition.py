"""Analytic checks for the independent Task V runner."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

SPEC = importlib.util.spec_from_file_location("task_v", Path(__file__).parents[1] / "task_v_earth_definition.py")
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


def test_south_pole_and_cardinal_projection():
    assert V.xy(-90, 123) == (0, 0)
    x, y = V.xy(-89, 90)
    assert x == pytest.approx(2 * V.RADIUS_M * np.tan(np.deg2rad(.5)))
    assert abs(y) < 1e-10


def test_horizon_wrap_and_negative_azimuth():
    mask = np.zeros(720)
    mask[719], mask[0] = 10, 20
    np.testing.assert_allclose(V.horizon_at(mask, np.array([359.75, -.25, 0, 360])), [15, 15, 20, 20])


def test_dem_plane_interpolation_and_missing_rejection():
    terrain = np.array([[0., 2., 4.], [3., 5., 7.], [6., 8., 10.]])
    assert V.interpolate_dem(terrain, 0, 20, 10, 5, 15) == pytest.approx(2.5)
    assert np.isnan(V.interpolate_dem(terrain, 0, 20, 10, -1, 15))


def test_earth_radius_and_centre_strict_tangent():
    # Equator lon=0: east=y, north=z, up=x. Observer subtraction
    # makes first vector exactly tangent and second 0.5 deg below terrain.
    distance = 384400
    angle = np.deg2rad(-.5)
    earth = np.array([[1737.402, distance, 0],
                      [1737.402 + distance * np.sin(angle), distance * np.cos(angle), 0],
                      [1737.402 + distance * np.sin(np.deg2rad(-2)), distance * np.cos(np.deg2rad(-2)), 0]])
    result = V.earth_fractions(earth, 0, 0, 0, np.zeros(720))
    assert result["centre_count"] == 0
    assert result["any_part_count"] == 2
    assert result["angular_radius_min_deg"] == pytest.approx(np.rad2deg(np.arcsin(6371 / distance)))


def test_observer_height_changes_topocentric_clearance():
    earth = np.array([[1737.401, 384400., 0]])
    assert V.earth_fractions(earth, 0, 0, 0, np.zeros(720), height=0)["centre_count"] == 1
    assert V.earth_fractions(earth, 0, 0, 0, np.zeros(720), height=2)["centre_count"] == 0


def test_bad_inputs_fail_closed():
    with pytest.raises(ValueError):
        V.earth_fractions(np.zeros((0, 3)), 0, 0, 0, np.zeros(720))
    with pytest.raises(ValueError):
        V.horizon_at(np.zeros(360), np.array([0]))
    with pytest.raises(ValueError):
        V.earth_fractions(np.zeros((1, 3)), 0, 0, 0, np.zeros(720))
    with pytest.raises(ValueError):
        V.statistics([np.nan], [0])


def test_constant_sphere_horizon_includes_curvature_and_observer():
    # On a sphere the closest sampled point sets the horizon for these ranges:
    # analytical horizon tangent distance sqrt(2Rh) ~2.6km, use ranges >=10km.
    terrain = np.zeros((2001, 2001), dtype=np.float32)
    distances = np.array([10000., 20000.])
    mask, ground = V.reconstruct_mask(-90., 0., terrain, -60000, 60000,
                                      terrain, -60000, 60000, distances)
    expected = np.rad2deg(np.arctan2(V.RADIUS_M * np.cos(10000/V.RADIUS_M) - V.RADIUS_M - 2,
                                   V.RADIUS_M * np.sin(10000/V.RADIUS_M)))
    assert ground == 0
    np.testing.assert_allclose(mask, expected, atol=1e-10)


def test_pgda_raw_integer_scale_and_neighborhood():
    raw = np.array([[0, 1, 2], [3, 25000, 5], [6, 7, 8]], dtype=np.int16)
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", width=3, height=3, count=1, dtype="int16",
                      transform=from_origin(-90, 90, 60, 60)) as ds:
            ds.write(raw, 1)
            result = V.read_truth(ds, -90, 0, 60)
            assert result["raw_dn"] == 25000
            assert result["value"] == 1
            assert result["minimum"] == 0
            assert result["maximum"] == 1
            assert result["row"] == result["col"] == 1


def test_definition_is_not_necessarily_error_improvement():
    rows = [dict(id="a", centre=.5, any_part=.6, pgda=dict(value=.5, minimum=.5, maximum=.5), stored_any_delta_pp=0),
            dict(id="b", centre=.1, any_part=.2, pgda=dict(value=.2, minimum=.2, maximum=.2), stored_any_delta_pp=0)]
    summary = V.summarize(rows)
    assert summary["improved_points"] == summary["worsened_points"] == 1
    assert summary["mae_reduction_pp"] == pytest.approx(0)
    assert summary["definition_increase_mean_pp"] == pytest.approx(10)
