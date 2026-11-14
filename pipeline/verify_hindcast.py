"""Card 21 verification: recompute 3 rows of web/data/hindcast.json independently, without
pipeline/ephem.py / Skyfield / pipeline/hindcast.py - using JPL Horizons observer tables directly.

  * APOLLO11, APOLLO17: Sun elevation at the landing time from Horizons (observer = catalogue point,
    height h0 + 2 m above the 1737.4 km sphere, apparent, airless) vs our stored value.
  * CHANDRAYAAN3: Sun az/el from Horizons every minute for +-2 h around our sunset, own disc-fraction
    code with the horizon file -> first minute below 50 % vs our stored sunset.

    python pipeline/verify_hindcast.py   -> docs/hindcast_check.json
"""
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
API = "https://ssd.jpl.nasa.gov/api/horizons.api"


def horizons(lat, lon, h_km, start, stop, step):
    o = {"format": "json", "COMMAND": "'10'", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
         "SITE_COORD": f"'{lon},{lat},{h_km}'", "START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'",
         "STEP_SIZE": f"'{step}'", "QUANTITIES": "'4'", "CSV_FORMAT": "'YES'", "EXTRA_PREC": "'YES'",
         "APPARENT": "'AIRLESS'", "CAL_FORMAT": "'JD'", "TIME_TYPE": "'UT'", "OBJ_DATA": "'NO'"}
    with urllib.request.urlopen(API + "?" + urllib.parse.urlencode(o), timeout=300) as r:
        txt = json.load(r)["result"]
    rows = [l.split(",") for l in txt.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()]
    return np.array([[float(x[0]), float(x[3]), float(x[4])] for x in rows])


def main():
    hc = json.loads((DATA / "hindcast.json").read_text(encoding="utf-8"))
    sites = {s["id"]: s for s in json.loads((DATA / "sites.json").read_text(encoding="utf-8"))}
    out = []
    for sid in ("APOLLO11", "APOLLO17"):
        row = next(r for r in hc["apollo_sun_elevation"] if r["id"] == sid)
        t = datetime.fromisoformat(row["landing_utc"].replace("Z", "+00:00"))
        s = sites[sid]
        tab = horizons(s["lat"], s["lon"], (row["h0_m"] + 2) / 1000, t.strftime("%Y-%m-%d %H:%M:%S"),
                       (t + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"), "1m")
        el = float(tab[0, 2])
        d = el - row["ours_sun_el_deg_catalogue_point"]
        out.append(dict(id=sid, check="Sun elevation at landing", horizons_deg=round(el, 4),
                        ours_deg=row["ours_sun_el_deg_catalogue_point"], difference_deg=round(d, 4), passed=abs(d) < 0.01))
        print(sid, "Horizons", round(el, 4), "ours", row["ours_sun_el_deg_catalogue_point"], "diff", round(d, 4))
    row = next(r for r in hc["robotic_sunset"] if r["id"] == "CHANDRAYAAN3")
    s = sites["CHANDRAYAAN3"]
    hz = json.loads((DATA / "horizon" / "CHANDRAYAAN3.json").read_text(encoding="utf-8"))
    ts = datetime.fromisoformat(row["ours_first_sunset_utc"].replace("Z", "+00:00"))
    tab = horizons(s["lat"], s["lon"], (hz["h0_m"] + 2) / 1000, (ts - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
                   (ts + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"), "1m")
    m = np.asarray(hz["mask"], float)
    x = (tab[:, 1] % 360) / hz["az_step_deg"]
    k = np.floor(x).astype(int) % m.size
    f = x - np.floor(x)
    line = m[k] + (m[(k + 1) % m.size] - m[k]) * f
    y = np.clip((line - tab[:, 2]) / 0.2666, -1, 1)
    frac = (np.arccos(y) - y * np.sqrt(1 - y * y)) / math.pi
    first = int(np.argmax(frac < 0.5))
    jd = tab[first, 0]
    t_ind = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jd - 2440587.5)
    d_min = (t_ind - ts).total_seconds() / 60
    out.append(dict(id="CHANDRAYAAN3", check="first sunset after landing (core.js rule)", horizons_based_utc=t_ind.strftime("%Y-%m-%dT%H:%MZ"),
                    ours_utc=row["ours_first_sunset_utc"], difference_min=round(d_min, 1), passed=abs(d_min) <= 2))
    print("CHANDRAYAAN3 sunset Horizons-based", t_ind.strftime("%Y-%m-%d %H:%M"), "ours", row["ours_first_sunset_utc"], "diff min", round(d_min, 1))
    p = ROOT / "docs" / "hindcast_check.json"
    p.write_text(json.dumps(dict(method=__doc__.strip().split("\n\n")[0], rows=out, passed=all(r["passed"] for r in out),
                                 generated_utc=datetime.now(timezone.utc).isoformat()), indent=1), encoding="utf-8")
    print("ALL PASS" if all(r["passed"] for r in out) else "FAIL")


if __name__ == "__main__":
    main()
