"""run_relay.py never computes a site without a real DEM: it is recorded as pending terrain.

    python -m pytest pipeline/test_run_relay.py -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_relay as rr  # noqa: E402


def test_missing_dem_is_pending_and_indexed(tmp_path):
    raw = tmp_path / "raw"            # empty: no DEM caches at all
    web = tmp_path / "web"
    (web / "relay").mkdir(parents=True)
    site = {"id": "NO_DEM_SITE", "lat": 20.0, "lon": 30.0}
    sid, status, msg = rr.run_one(site, raw, web, tmp_path / "work", dict(rr.RUN_PARAMS), force=False)
    assert (sid, status) == ("NO_DEM_SITE", "PENDING") and "missing DEM" in msg
    assert not (web / "relay" / "NO_DEM_SITE.json").exists()
    idx = rr.write_index(web, [site], {sid: msg})
    assert idx["ids"] == [] and "NO_DEM_SITE" in idx["pending_terrain"]
    assert json.loads((web / "relay" / "index.json").read_text())["pending_terrain"]["NO_DEM_SITE"] == msg


def test_index_lists_only_existing_files(tmp_path):
    web = tmp_path / "web"
    (web / "relay").mkdir(parents=True)
    (web / "relay" / "A.json").write_text("{}")
    idx = rr.write_index(web, [{"id": "A"}, {"id": "B"}], {"A": "stale reason"})
    assert idx["ids"] == ["A"]
    assert idx["pending_terrain"] == {"B": "not computed yet"}
