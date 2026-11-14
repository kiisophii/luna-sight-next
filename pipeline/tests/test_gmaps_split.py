"""Offline tests for pipeline/gmaps_split.py on small fake stores (ppd 1 = 180 x 360).

python -m pytest pipeline/tests/test_gmaps_split.py -q
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gmaps_split as gs  # noqa: E402

PPD, NLAT, NLON, NU = 1, 180, 360, 1000
SIG = {"engine_version": 1, "naz": 360, "near_km": 150.0, "max_km": 300.0, "step_frac": 0.01, "n_steps": 283,
       "obs_height_m": 2.0, "sun_radius_deg": 0.2666,
       "near": {"name": "LDEM_64", "file": "ldem_64_float.img", "bytes": 1, "res_m": 473.8},
       "far": {"name": "LDEM_16", "file": "ldem_16_float.img", "bytes": 1, "res_m": 1895.2},
       "ephem": {"file": "ephem.bin", "step_h": 3, "n_used": NU, "sha1_12": "abc", "start": "2026", "mock": False}}


def truth():
    rng = np.random.default_rng(1)
    earth = rng.integers(0, NU + 1, (NLAT, NLON)) / NU
    both = np.floor(earth * rng.uniform(0, 1, (NLAT, NLON)) * NU) / NU
    return {"sun": rng.uniform(0, 1, (NLAT, NLON)), "earth": earth, "both": both,
            "h0": rng.uniform(-9000, 10000, (NLAT, NLON)), "maskmax": rng.uniform(-2, 40, (NLAT, NLON))}


def make_store(d, rows, t, sig=SIG, tweak=None):
    """Fake global_maps store: values of `t` in `rows` (done), NaN elsewhere."""
    d = Path(d)
    d.mkdir(parents=True)
    r0, r1 = rows
    for f in gs.FIELDS:
        a = np.full((NLAT, NLON), np.nan, np.float32)
        a[r0:r1] = t[f][r0:r1]
        if tweak and f in tweak:
            tweak[f](a)
        np.save(d / f"{f}.npy", a)
    done = np.zeros(NLAT, np.uint8)
    done[r0:r1] = 1
    np.save(d / "done.npy", done)
    (d / "meta.json").write_text(json.dumps({"ppd": PPD, "nlat": NLAT, "nlon": NLON, "signature": sig,
                                             "created_utc": "x", "grid": gs.GRID}))
    return d


@pytest.fixture
def t():
    return truth()


def test_verify_pass_and_detects_problems(tmp_path, t):
    ok = make_store(tmp_path / "a", (0, 100), t)
    assert gs.verify_source(gs.Source(f"{ok}::0:100"))["ok"]
    # asking for rows that are not done
    r = gs.verify_source(gs.Source(f"{ok}::0:120"))
    assert not r["ok"] and any("not done" in p for p in r["problems"])

    def nan_row(a):
        a[5, 7] = np.nan

    def big(a):
        a[3, 3] = 1.5
    bad = make_store(tmp_path / "b", (0, 100), t, tweak={"sun": nan_row, "earth": big})
    r = gs.verify_source(gs.Source(f"{bad}::0:100"))
    assert not r["ok"]
    assert r["fields"]["sun"]["nan"] == 1 and r["fields"]["earth"]["out_of_range"] == 1
    mock = make_store(tmp_path / "c", (0, 100), t, sig={**SIG, "ephem": {**SIG["ephem"], "mock": True}})
    assert not gs.verify_source(gs.Source(f"{mock}::0:100"))["ok"]


def test_pack_check_roundtrip(tmp_path, t):
    st = make_store(tmp_path / "s", (0, 104), t)
    man = gs.pack(gs.Source(f"{st}::0:104"), tmp_path / "pkg", keep_row=103, log=lambda *_: None)
    assert man["rows"] == {"start": 0, "stop": 104, "stop_exclusive": True,
                           "lat_first": 89.5, "lat_last": 90 - 103.5}
    assert gs.check_package(tmp_path / "pkg", log=lambda *_: None) == []
    p = gs.Source(tmp_path / "pkg")
    np.testing.assert_array_equal(p.row("sun", 103), np.float32(t["sun"][103]))
    with np.load(tmp_path / "pkg" / "row_103.npz") as z:
        np.testing.assert_array_equal(z["both"], np.float32(t["both"][103]))
    del p                               # release the memmaps (Windows cannot rewrite a mapped file)
    import gc
    gc.collect()
    # corrupt one byte -> check fails
    f = tmp_path / "pkg" / "h0.npy"
    b = bytearray(f.read_bytes())
    b[-1] ^= 1
    f.write_bytes(bytes(b))
    assert gs.check_package(tmp_path / "pkg", log=lambda *_: None)
    # never packs an incomplete range, never into a non-empty folder
    with pytest.raises(SystemExit):
        gs.pack(gs.Source(f"{st}::0:110"), tmp_path / "pkg2", log=lambda *_: None)
    with pytest.raises(SystemExit):
        gs.pack(gs.Source(f"{st}::0:104"), tmp_path / "pkg", log=lambda *_: None)


def test_merge_with_overlap_row(tmp_path, t):
    a = make_store(tmp_path / "cpu", (0, 104), t)
    b = make_store(tmp_path / "gpu", (103, 180), t)
    gs.pack(gs.Source(f"{b}::103:180"), tmp_path / "gpu_pkg", keep_row=103, log=lambda *_: None)
    out = tmp_path / "merged"
    meta = gs.merge([f"{a}::0:104", str(tmp_path / "gpu_pkg")], out, log=lambda *_: None)
    assert meta["overlap_rows"] == [103] and meta["overlap_ok"]
    assert [m["rows_used"] for m in meta["merged_from"]] == [104, 76]
    for f in gs.FIELDS:
        np.testing.assert_array_equal(np.load(out / f"{f}.npy"), t[f].astype(np.float32))
    assert np.load(out / "done.npy").all()
    assert json.loads((out / "verify_report.json").read_text())["ok"]
    # merge never writes into an existing folder (protects the original stores)
    with pytest.raises(SystemExit):
        gs.merge([f"{a}::0:104", str(tmp_path / "gpu_pkg")], a, log=lambda *_: None)


def test_merge_refuses_disagreeing_overlap(tmp_path, t):
    a = make_store(tmp_path / "cpu", (0, 104), t)

    def shift(x):
        x[103, :10] += 0.01      # GPU differs in 10 columns of the overlap row
    b = make_store(tmp_path / "gpu", (103, 180), t, tweak={"sun": shift})
    with pytest.raises(SystemExit, match="disagree"):
        gs.merge([f"{a}::0:104", f"{b}::103:180"], tmp_path / "m", log=lambda *_: None)
    assert not (tmp_path / "m").exists()
    rep = json.loads((tmp_path / "m_overlap_report.json").read_text())
    c = next(iter(rep.values()))
    assert c["fields"]["sun"]["n_over_tol"] == 10 and abs(c["fields"]["sun"]["max_abs"] - 0.01) < 1e-6
    assert c["fields"]["earth"]["n_over_tol"] == 0 and "diagnosis" in c
    # a person may accept it with a recorded reason; the first part's row is used, nothing is averaged
    meta = gs.merge([f"{a}::0:104", f"{b}::103:180"], tmp_path / "m2", accept_reason="test", log=lambda *_: None)
    assert meta["overlap_accept_reason"] == "test"
    np.testing.assert_array_equal(np.load(tmp_path / "m2" / "sun.npy")[103], np.float32(t["sun"][103]))


def test_merge_refuses_gap_and_signature(tmp_path, t):
    a = make_store(tmp_path / "cpu", (0, 100), t)
    b = make_store(tmp_path / "gpu", (103, 180), t)
    with pytest.raises(SystemExit, match="covered by no part"):
        gs.merge([f"{a}::0:100", f"{b}::103:180"], tmp_path / "m", log=lambda *_: None)
    c = make_store(tmp_path / "gpu2", (100, 180), t, sig={**SIG, "ephem": {**SIG["ephem"], "step_h": 2}})
    with pytest.raises(SystemExit, match="signature differs"):
        gs.merge([f"{a}::0:100", f"{c}::100:180"], tmp_path / "m", log=lambda *_: None)


def test_compare_rows_exact_and_quantised(t):
    ra = {f: t[f][50] for f in gs.FIELDS}
    rb = {f: t[f][50].copy() for f in gs.FIELDS}
    assert gs.compare_rows(ra, rb, n_used=NU)["ok"]
    rb["earth"][0] += 1 / NU            # one sample of 1000 differs: within the default 1e-3 tolerance
    r = gs.compare_rows(ra, rb, n_used=NU)
    assert r["ok"] and abs(r["fields"]["earth"]["max_abs_in_samples"] - 1) < 1e-9
    rb["h0"][1] = np.nan
    assert not gs.compare_rows(ra, rb)["ok"]
