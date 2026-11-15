"""Tests for pipeline/task_t_gmaps_ppd8_raw.py.

python -m pytest pipeline/tests/test_task_t_gmaps_ppd8_raw.py -q
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import task_t_gmaps_ppd8_raw as t  # noqa: E402


def test_npy_header_reads_shape_dtype_offset(tmp_path):
    p = tmp_path / "a.npy"
    np.save(p, np.zeros((3, 5), "<f4"))
    h = t.npy_header(p)
    assert h["descr"] == "<f4" and h["shape"] == [3, 5] and not h["fortran_order"] and h["data_offset"] == 128


def test_ephem_signature_matches_current_ephem_bin():
    meta = json.loads((t.ROOT / "docs/task_t/MANIFEST.json").read_text(encoding="utf-8"))["computation"]["meta_json"]
    sha, n = t.ephem_sha1_12(meta["signature"]["ephem"]["step_h"])
    assert sha == meta["signature"]["ephem"]["sha1_12"] == "bf98b99edc04" and n == 21912


def test_committed_checksums_cover_every_release_file():
    lines = (t.DOCS / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    names = [ln.split("  ", 1)[1] for ln in lines]
    assert names == t.FILES + ["MANIFEST.json"]
    assert all(len(ln.split("  ", 1)[0]) == 64 for ln in lines)


def test_manifest_grid_and_status():
    m = json.loads((t.ROOT / "docs/task_t/MANIFEST.json").read_text(encoding="utf-8"))
    assert m["grid"]["shape"] == [1440, 2880] and m["grid"]["ppd"] == 8
    assert m["independent_verification"].startswith("PENDING")
    for f in m["files"]:
        if f["name"] in ("sun.npy", "earth.npy", "both.npy", "h0.npy", "maskmax.npy"):
            assert f["npy"]["descr"] == "<f4" and f["npy"]["shape"] == [1440, 2880] and f["nan_count"] == 0


def test_bit_pattern_check_is_stricter_than_value_equality():
    a = np.array([0.0, np.nan], "<f4")
    b = np.array([-0.0, np.nan], "<f4")
    assert np.array_equal(a, b, equal_nan=True)                 # values "equal"
    assert not np.array_equal(a.view("<u4"), b.view("<u4"))     # but not the original bits


def test_pixel_centre_formula_edges():
    lat, lon = 90 - (np.array([0, 1439]) + 0.5) / 8, -180 + (np.array([0, 2879]) + 0.5) / 8
    assert lat.tolist() == [89.9375, -89.9375] and lon.tolist() == [-179.9375, 179.9375]


@pytest.mark.skipif(not (t.STAGE / "MANIFEST.json").exists(), reason="local release staging not present (git-ignored)")
def test_staged_release_is_bit_identical_to_originals():
    assert t.check(t.STAGE)["all_ok"]
