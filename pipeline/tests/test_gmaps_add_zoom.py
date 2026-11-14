"""Offline test for pipeline/gmaps_add_zoom.py on a fake ppd-1 store exported with global_maps.export.

python -m pytest pipeline/tests/test_gmaps_add_zoom.py -q
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import global_maps as gm  # noqa: E402
import gmaps_add_zoom as gz  # noqa: E402


def fake_store(d):
    st = gm.Store(d, 1, signature={"ephem": {"mock": False}, "near": {"name": "LDEM_64", "res_m": 474},
                                   "far": {"name": "LDEM_16", "res_m": 1895}, "naz": 360, "near_km": 150,
                                   "max_km": 300, "step_frac": 0.01, "n_steps": 283, "obs_height_m": 2,
                                   "sun_radius_deg": 0.2666, "engine_version": 1})
    lat, lon = gm.grid_axes(1)
    la, lo = np.meshgrid(lat, lon, indexing="ij")
    res = np.zeros((180 * 360, 6))
    res[:, 0] = (0.5 + 0.5 * np.sin(np.radians(lo)) * np.cos(np.radians(la))).ravel()
    res[:, 1] = (0.5 + 0.5 * np.cos(np.radians(lo))).ravel()
    res[:, 2] = np.minimum(res[:, 0], res[:, 1]) * 0.5
    st.write_rows(0, 180, res)
    return st


def digests(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(folder).rglob("*")) if p.is_file() and p.name != "index.json"}


def test_add_level_keeps_existing_files(tmp_path):
    st = fake_store(tmp_path / "store")
    web = tmp_path / "web"
    idx = gm.export(st, web, overview=(256, 128), log=lambda *_: None)
    zmax = max(L["z"] for L in idx["tiles"]["levels"])
    before = digests(web)
    args = type("A", (), {"store": str(tmp_path / "store"), "web": str(web), "z": zmax + 1,
                          "report": str(tmp_path / "check.json")})
    assert gz.cmd_add(args) == 0
    new = json.loads((web / "index.json").read_text())
    L = gz.level(zmax + 1)
    assert new["tiles"]["levels"][-1] == L and new["added_levels"][0]["z"] == zmax + 1
    after = digests(web)
    assert {k: after[k] for k in before} == before                          # old tiles untouched
    added = sorted(set(after) - set(before))
    assert len(added) == 3 * L["nx"] * L["ny"]
    assert gz.cmd_check(args) == 0
    rep = json.loads(Path(args.report).read_text())
    assert rep["ok"] and all(d["tiles_missing"] == 0 and d["value_nan"] == 0 for d in rep["layers"].values())
    with pytest.raises(SystemExit):                                         # never overwrites a level
        gz.cmd_add(args)


def test_level_geometry():
    assert gz.level(3) == {"z": 3, "width": 8192, "height": 4096, "nx": 16, "ny": 8}
    assert gz.level(4) == {"z": 4, "width": 16384, "height": 8192, "nx": 32, "ny": 16}
    # the exporter's own rule for the 948 m grid stops at z3
    assert max(2, int(round(np.log2(11520 / 1024.0)))) == 3
