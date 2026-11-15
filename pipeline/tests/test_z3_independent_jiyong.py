"""Analytic controls and deliberate corruption for the independent Z3 audit."""
import importlib.util
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "z3_independent", Path(__file__).resolve().parents[1] / "verify_z3_independent_jiyong.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_analytic_geometry_and_thresholds():
    # Equator, longitude zero: up=x, east=y, north=z.
    # Body at exactly the horizontal plane: Sun half visible; Earth not visible.
    eph = np.array([[1737.402, 10000, 0, 1737.402, 10000, 0]], dtype=float)
    sun, earth, diag = audit.hourly_flags(
        {"lat": 0, "lon": 0}, {"h0_m": 0, "mask": [0] * 720, "az_step_deg": 0.5}, eph
    )
    assert sun.tolist() == [True]
    assert earth.tolist() == [False]
    assert diag["min_sun_margin_deg"] == 0


def test_circular_interpolation():
    assert np.allclose(audit.mask_at(np.array([-45, 315, 360, 45]), [0, 1, 2, 3], 90), [1.5, 1.5, 0, 0.5])


def test_duration_and_censor_edges():
    sun = np.array([0, 0, 1, 0, 0, 1], dtype=bool)
    earth = np.ones(6, dtype=bool)
    row = audit.base_row(sun, earth, 0, 2)
    assert row == ['ok', 0, 2, 0, 0., 1., 0., 2, True, False]
    assert audit.base_row(sun, earth, 3, 2)[8:] == [False, False]
    assert audit.base_row(sun, earth, 1, 3)[8:] == [True, True]
    assert audit.base_row(sun, earth, 0, 6)[7:] == [2, True, False]
    assert audit.base_row(sun, earth, 1, 6) == ['out_of_range'] + [None] * 9


def test_half_day_final_cell():
    sun = np.ones(732, dtype=bool)
    sun[-1] = False
    row = audit.base_row(sun, sun, 24, 708)
    assert row[1:4] == [707, 707, 707]
    assert row[7:] == [1, False, True]
    assert audit.base_row(sun, sun, 48, 708)[0] == 'out_of_range'


def test_all_shift_statuses_and_sign():
    a = ['ok', 3, 5, 2, .3, .5, .2, 4, False, False]
    b = ['ok', 6, 4, 3, .6, .4, .3, 2, False, False]
    bad = ['out_of_range'] + [None] * 9
    assert audit.shift_row(a, b, 1) == ['ok', 1, 3, -1, 1, -2]
    assert audit.shift_row(b, a, 0) == ['ok', 0, -3, 1, -1, 2]
    assert audit.shift_row(a, None, -7)[0] == 'target_out_of_range'
    assert audit.shift_row(bad, a, 0)[0] == 'base_out_of_range'
    assert audit.shift_row(bad, None, -1)[0] == 'both_out_of_range'


def test_comparator_rejects_corruption():
    row = ['ok', 168, 168, 168, 1., 1., 1., 0, False, False]
    assert audit.row_differences(row, row, audit.ROW_COLUMNS, 168, False) == []
    for column, value in [(0, 'out_of_range'), (1, 160), (4, .99), (7, 5), (8, True)]:
        changed = row.copy()
        changed[column] = value
        diff = audit.row_differences(changed, row, audit.ROW_COLUMNS, 168, False)
        assert len(diff) == 1 and diff[0]['exceeds_criterion']
    bad = ['out_of_range'] + [None] * 9
    changed = bad.copy()
    changed[1] = 0
    assert audit.row_differences(changed, bad, audit.ROW_COLUMNS, 168, False)[0]['exceeds_criterion']
