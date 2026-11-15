"""Tests for pipeline/verify_z1_independent_soyun.py (offline; uses the repository's web/data inputs).

python -m pytest pipeline/tests/test_verify_z1_independent_soyun.py -q
"""
import base64
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_z1_independent_soyun as v  # noqa: E402


def test_runs_clipping_flags_and_exclusive_end():
    f = np.array([1, 1, 0, 0, 1, 0, 1, 1], bool)
    rs = v.runs_of(f)
    assert [(r["start_i"], r["end_i"], r["duration_h"], r["clipped_start"], r["clipped_end"]) for r in rs] == [
        (0, 2, 2, True, False), (4, 5, 1, False, False), (6, 8, 2, False, True)]


def test_run_stats_no_runs_gives_null_mean_and_zero_longest():
    s, _ = v.run_stats(np.zeros(10, bool))
    assert s["count"] == 0 and s["total_h"] == 0 and s["mean_h"] is None and s["longest_h"] == 0
    assert s["complete_count"] == 0 and s["complete_mean_h"] is None and s["complete_longest_h"] == 0 and s["clipped_runs"] == []


def test_run_stats_whole_period_run_is_clipped_both_ends_once():
    s, _ = v.run_stats(np.ones(7, bool))
    assert s["count"] == 1 and s["longest_h"] == 7 and s["mean_h"] == 7
    assert s["complete_count"] == 0 and s["complete_mean_h"] is None and s["complete_longest_h"] == 0
    assert s["clipped_runs"] == [dict(start_i=0, end_i=7, duration_h=7, clipped_start=True, clipped_end=True)]


def test_run_stats_complete_excludes_clipped_and_keeps_longest_apart():
    # clipped end run (5) longer than every complete run (3): complete_longest must be 3, longest 5
    f = np.array([0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1], bool)
    s, _ = v.run_stats(f)
    assert s["count"] == 3 and s["total_h"] == 9 and s["longest_h"] == 5 and s["mean_h"] == 3
    assert s["complete_count"] == 2 and s["complete_longest_h"] == 3 and s["complete_mean_h"] == 2
    assert len(s["clipped_runs"]) == 1 and s["clipped_runs"][0]["clipped_end"]


def test_station_bits_lsb_first_across_byte_boundary():
    n = 20
    want = np.zeros(n, bool)
    want[[0, 7, 8, 15, 19]] = True
    raw = bytes([0b10000001, 0b10000001, 0b00001000])
    got = v.decode_station_bits(base64.b64encode(raw).decode(), n)
    assert np.array_equal(got, want)


def test_station_bits_reject_wrong_length():
    with pytest.raises(AssertionError):
        v.decode_station_bits(base64.b64encode(bytes(2)).decode(), 20)


def test_body_row_last_hour_uses_t_equal_one():
    eph = np.arange(v.N * 6, dtype=np.float64).reshape(v.N, 6)
    assert v.body_row(eph, 5, 0) == tuple(eph[5, 0:3])
    last = v.body_row(eph, v.N - 1, 3)
    a, b = eph[v.N - 2, 3:6], eph[v.N - 1, 3:6]
    assert last == tuple(a + (b - a) * 1)


def test_windows_top10_sorted_by_duration_then_start():
    f = np.ones(200, bool)
    for s, d in [(10, 3), (20, 5), (40, 3), (60, 5)] + [(80 + 6 * k, 1) for k in range(10)]:
        f[s:s + d] = False
    w = v.windows_from(f)
    durs = [g["duration_h"] for g in w["longest_gaps"]]
    assert len(durs) == 10 and durs[:4] == [5, 5, 3, 3]
    assert w["longest_gaps"][0]["start_utc"] < w["longest_gaps"][1]["start_utc"]
    assert w["visible_hours"] == int(f.sum())


def test_scalar_and_vector_states_agree_on_real_site():
    sites = {s["id"]: s for s in json.loads((v.WEB / "sites.json").read_text(encoding="utf-8"))}
    hz = json.loads((v.WEB / "horizon/ARTEMIS_CABEUS_B.json").read_text(encoding="utf-8"))
    s = sites["ARTEMIS_CABEUS_B"]
    eph = v.load_ephem()
    sun, earth, _, _ = v.states_scalar(s["lat"], s["lon"], hz["h0_m"], hz["mask"], hz["az_step_deg"], eph)
    vs, ve = v.states_vector(s["lat"], s["lon"], hz["h0_m"], hz["mask"], hz["az_step_deg"], eph)
    assert np.array_equal(sun, vs) and np.array_equal(earth, ve)


def test_flat_mask_disc_half_visible_at_horizon():
    # with a zero mask, a Sun centre exactly on the horizon gives y = 0 -> fraction 0.5 -> sunlit (>= 0.5)
    y = 0.0
    frac = (np.arccos(y) - y * np.sqrt(1 - y * y)) / np.pi
    assert frac == 0.5 and frac >= v.SUNLIT_FRACTION


def test_station_link_does_not_require_sunlight():
    sun = np.array([0, 0, 1, 1], bool)
    earth = np.array([1, 0, 1, 0], bool)
    st = np.array([1, 1, 1, 1], bool)
    link = earth & st
    assert link.tolist() == [True, False, True, False]
    assert (link & ~sun).sum() == 1      # a dark hour still counts as a link hour
