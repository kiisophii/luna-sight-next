"""Offline tests for pipeline/verify_sites_independent_soyun.py (no network).

python -m pytest pipeline/tests/test_verify_sites_independent_soyun.py -q
"""
import json
import math
import sys
import zlib
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_sites_independent_soyun as v  # noqa: E402


@pytest.mark.parametrize("text,conv,axis,want,dec", [
    ("45.4562°S", "hemisphere", "lat", "-45.4562", 4),
    ("177.5885 °E", "hemisphere", "lon", "177.5885", 4),
    ("340.4884°E", "hemisphere", "lon", "-19.5116", 4),          # 0..360 E source
    ("308.0839°E", "hemisphere", "lon", "-51.9161", 4),
    ("58.725°W", "hemisphere", "lon", "-58.725", 3),
    ("43.0576° N", "hemisphere", "lat", "43.0576", 4),
    ("0.5137 S", "hemisphere", "lat", "-0.5137", 4),
    ("-23.4219", "signed_N_E", "lon", "-23.4219", 4),
    ("197.19", "signed_N_E", "lon", "-162.81", 2),                # Glaser Table 2 0..360 E
    ("−83.7630", "signed_N_E", "lat", "-83.7630", 4),        # AGU minus glyph
    ("3.63330", "signed_N_E", "lon", "3.63330", 5),
])
def test_parse_value(text, conv, axis, want, dec):
    val, d = v.parse_value(text, conv, axis)
    assert val == Decimal(want) and d == dec


def test_parse_rejects_wrong_axis_and_double_sign():
    with pytest.raises(ValueError):
        v.parse_value("45.1°E", "hemisphere", "lat")
    with pytest.raises(ValueError):
        v.parse_value("-45.1°S", "hemisphere", "lat")
    with pytest.raises(ValueError):
        v.parse_value("95.0", "signed_N_E", "lat")


def test_normalize_lon_edges():
    assert v.normalize_lon(Decimal("180")) == Decimal("-180")
    assert v.normalize_lon(Decimal("359.999")) == Decimal("-0.001")
    assert v.normalize_lon(Decimal("-180")) == Decimal("-180")
    assert v.normalize_lon(Decimal("540")) == Decimal("-180")


def test_great_circle_uses_lunar_radius():
    from pyproj import Geod
    g = Geod(a=v.R_M, b=v.R_M)
    for a, b, c, d in [(0, 0, 0, 1), (-89.6866, -162.81, -89.7668, -171.87), (20.1911, 30.7723, 20.1923, 30.7655), (10, 179.9, 10, -179.9)]:
        assert abs(v.gc_m(a, b, c, d) - g.inv(b, a, d, c)[2]) < 1e-6
    assert abs(v.gc_m(0, 0, 0, 1) - math.radians(1) * 1737400) < 1e-6      # 30.32 km per degree, not Earth's 111 km


def test_rounding_bound():
    # 4 decimals at the equator: half of 1e-4 deg in each axis
    b = v.rounding_bound_m(0, 4, 4)
    assert abs(b - math.hypot(0.5e-4, 0.5e-4) * math.radians(1) * v.R_M) < 1e-9
    assert v.rounding_bound_m(-80.13, 2, 2) > 150                      # IM-1 two decimals: ~150 m


def test_compare_one_exact_and_mismatch():
    r = v.compare_one("41.6385°S", "206.0148°E", "hemisphere", Decimal("-41.6385"), Decimal("-153.9852"))
    assert r["exact_equal"] and r["distance_m"] == 0 and r["within_rounding"]
    r = v.compare_one("41.6385°S", "206.0148°E", "hemisphere", Decimal("-41.6386"), Decimal("-153.9852"))
    assert not r["within_rounding"] and abs(r["distance_m"] - math.radians(1e-4) * v.R_M) < 1e-6


def test_normalize_restores_minus_glyph():
    assert v.normalize("PCB01 \x00 83.7630 \x00 69.9830\n") == "PCB01 −83.7630 −69.9830 "


def test_html_text_table_cells():
    t = v.normalize(v.html_text(b"<table><tr><td>Lunar Module</td><td>0.67416</td><td>23.47314</td></tr></table>"))
    assert "Lunar Module | 0.67416 | 23.47314" in t


def test_stereo_matches_proj():
    from pyproj import Transformer
    tr = Transformer.from_crs("+proj=longlat +R=1737400 +no_defs", "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m",
                              always_xy=True)
    rng = np.random.default_rng(1)
    la, lo = rng.uniform(-90, -80, 200), rng.uniform(-180, 180, 200)
    x, y = v.stereo(la, lo)
    X, Y = tr.transform(lo, la)
    assert np.max(np.abs(x - X)) < 1e-6 and np.max(np.abs(y - Y)) < 1e-6


def test_destination_bearing_roundtrip():
    la, lo = v.destination(-88.48, -88.34, 123.0, 16400.0)
    assert abs(v.gc_m(-88.48, -88.34, la, lo) - 16400.0) < 1e-6
    assert abs(((v.bearing_deg(-88.48, -88.34, la, lo) - 123.0 + 180) % 360) - 180) < 1e-6


def test_own_tile_predictor3(monkeypatch):
    th, tw = 4, 8
    a = np.random.default_rng(2).normal(0, 1000, (th, tw)).astype(np.float32)
    be = a.astype(">f4").view(np.uint8).reshape(th, tw, 4).transpose(0, 2, 1).reshape(th, 4 * tw)
    diff = be.copy()
    diff[:, 1:] = (be[:, 1:].astype(np.int16) - be[:, :-1].astype(np.int16)) % 256
    blob = zlib.compress(diff.astype(np.uint8).tobytes())

    class R:
        content = blob

    monkeypatch.setattr("requests.get", lambda *x, **k: R())
    np.testing.assert_array_equal(v.own_tile("http://x", 0, len(blob), th, tw), a)


def test_evidence_file_is_complete():
    ev = json.loads(v.EVIDENCE.read_text(encoding="utf-8"))
    sites = json.loads((v.ROOT / "web/data/sites.json").read_text(encoding="utf-8"))
    assert len(sites) == 33 and [e["id"] for e in ev["sites"]] == [s["id"] for s in sites]
    for e in ev["sites"]:
        assert e["lat_text"] in e["quote"] and e["lon_text"] in e["quote"] and e["source"] in ev["sources"]
        assert e["feature"]["type"] and e["location"]
