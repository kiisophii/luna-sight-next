"""Checks for pipeline/korea_links.py against independent JPL Horizons queries (needs internet).

    python -m pytest pipeline/test_korea_links.py -q
"""
import json
import sys
import urllib.parse
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import korea_links as K  # noqa: E402

KDSA = next(s for s in K.STATIONS if s["id"] == "KDSA")


@pytest.fixture(scope="module")
def E():
    return K.Ephem()


def horizons_observer(target, center, site_coord, times_utc):
    q = {"format": "text", "COMMAND": f"'{target}'", "MAKE_EPHEM": "YES", "EPHEM_TYPE": "OBSERVER",
         "CENTER": f"'{center}'", "COORD_TYPE": "GEODETIC", "SITE_COORD": f"'{site_coord}'",
         "TLIST": " ".join(f"'{t}'" for t in times_utc), "TIME_TYPE": "UT", "QUANTITIES": "'4'",
         "ANG_FORMAT": "DEG", "APPARENT": "AIRLESS", "CSV_FORMAT": "YES", "EXTRA_PREC": "YES"}
    txt = K._horizons(q)
    rows = txt.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    out = []
    for r in rows:
        p = [x.strip() for x in r.split(",")]
        nums = [x for x in p[1:] if x.replace(".", "", 1).replace("-", "", 1).isdigit()]
        out.append((float(nums[0]), float(nums[1])))   # azimuth, elevation (deg)
    return np.array(out)


def test_moon_elevation_yeoju_vs_horizons(E):
    times = ["2026-03-03 12:00", "2027-07-19 18:30", "2030-11-02 03:15"]
    site = f"{KDSA['lon']},{KDSA['lat']},{KDSA['height_m'] / 1000}"
    hz = horizons_observer("301", "coord@399", site, times)
    t = E.ts.utc([2026, 2027, 2030], [3, 7, 11], [3, 19, 2], [12, 18, 3], [0, 30, 15])
    alt, az = K.moon_altaz(E, KDSA, t)
    d_el = np.abs(alt - hz[:, 1])
    print("Horizons el", hz[:, 1], "ours", alt, "diff", d_el)
    assert np.all(d_el < 0.05)
    d_az = np.abs((az - hz[:, 0] + 180) % 360 - 180)
    assert np.all(d_az < 0.1)


def test_bitset_roundtrip_matches_elevation(E):
    p = K.OUT / "stations.json"
    if not p.exists():
        pytest.skip("run pipeline/korea_links.py --only stations first")
    st = json.loads(p.read_text(encoding="utf-8"))
    kd = next(s for s in st["stations"] if s["id"] == "KDSA")
    bits = K.unpack_bits(kd["bits_b64"], st["n"])
    idx = np.array([0, 1000, 20000, 43823])
    alt, _ = K.moon_altaz(E, KDSA, E.hours()[idx])
    assert np.array_equal(bits[idx], alt >= 10)


def test_danuri_state_vs_second_horizons_query(E):
    """Cached 5-min chunk rows vs an independent TLIST query at the same epochs (< 10 m)."""
    jd, x, _ = K.fetch_danuri()
    pick = np.array([1000, len(jd) // 2, len(jd) - 50])
    txt = K.horizons_vectors_tlist(jd[pick])
    jd2, x2 = K.parse_vectors(txt)
    assert np.allclose(jd2, jd[pick], atol=1e-6)
    err_km = np.linalg.norm(x2 - x[pick], axis=1)
    print("Danuri |dr| km", err_km)
    assert np.all(err_km < 0.01)


def test_danuri_moon_me_vs_horizons_topocentric(E):
    """Our MOON_ME conversion: Danuri az/el from a lunar surface site vs Horizons coord@301 (< 0.3 deg).

    Horizons' lunar body-fixed frame for surface sites may differ from MOON_ME (DE421) by ~arcminutes
    (PA vs ME, model version); at ~100 km range that is far below 0.3 deg.
    """
    jd, x, _ = K.fetch_danuri()
    r_me, t = K.danuri_me(E, jd, x)
    lat, lon = -89.0, 0.0
    fr = K.site_frame(lat, lon)
    pos = K.R_MOON_KM * fr[2]
    az, el = K.topo_azel(pos, fr, r_me)
    cand = np.where(el > 20)[0]
    pick = cand[[0, len(cand) // 2, -100]]
    times = [t[i].utc_strftime("%Y-%m-%d %H:%M:%S") for i in pick]
    hz = horizons_observer("-155", "coord@301", f"{lon},{lat},0", times)
    d_el = np.abs(el[pick] - hz[:, 1])
    print("Danuri el ours", el[pick], "Horizons", hz[:, 1])
    assert np.all(d_el < 0.3)


def test_pass_runs_helper():
    a, b = K.runs(np.array([0, 1, 1, 0, 1], bool))
    assert a.tolist() == [1, 4] and b.tolist() == [3, 5]


def test_earth_occultation_from_orbit():
    sc = np.array([[K.R_MOON_KM + 100, 0, 0], [-(K.R_MOON_KM + 100), 0, 0]])
    earth = np.array([[384400.0, 0, 0]] * 2)
    assert K.earth_visible_from_orbit(sc, earth).tolist() == [True, False]
