"""Card 21 - hindcast real missions with our ephemeris pipeline, horizon files and core.js definitions.

  python pipeline/hindcast.py            -> web/data/hindcast.json, docs/hindcast_check.json
  python pipeline/hindcast.py --offline  (reuse cached Horizons responses)

(1) Ephemeris check: data/processed/ephem_2019-2025_1h.npz (pipeline/hindcast_ephem.py = card 1 pipeline)
    vs JPL Horizons at 50 random hours (2 lunar test sites, Sun and Earth), criterion < 0.01 deg.
(2a) Apollo 11-17: topocentric Sun elevation at the published landing time (observer at R + h0 + 2 m,
    h0 from web/data/horizon/<ID>.json) vs the Apollo Lunar Surface Journal table (computed by Fjeld & Scotti,
    spot-checked with Horizons). Evaluated at our catalogue point and at the ALSJ table point.
(2b) Chandrayaan-3, SLIM, IM-1, Chang'e 3, Chang'e 4: first local sunset after landing with the core.js rule
    (sunlit = >= 50 % of the solar disc above the real terrain mask) at 1-minute steps, vs the publicly reported
    sleep / dormancy / power-down / last-contact time. END OF OPERATIONS IS AN APPROXIMATE PROXY for sunset:
    operators may power down before sunset (battery, thermal, schedule) or the report gives only a date.

Ephemeris for (2a)/(2b) comes straight from the card 1 engine (pipeline/ephem.py Ephemeris.vectors) at the
needed instants, which covers 1969-1972 and 2013 as well (DE440s 1849-2150, MOON_ME DE421 1900-2050).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ephem as E  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
CACHE = ROOT / "data" / "raw" / "horizons_hindcast"
NPZ = ROOT / "data" / "processed" / "ephem_2019-2025_1h.npz"
R_KM = 1737.4
SUN_R = 0.2666
UTC = timezone.utc
ALSJ_URL = "https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html"
ALSJ_NOTE = ("Apollo Lunar Surface Journal (NASA History; linked from https://www.nasa.gov/history/alsj-and-afj/), "
             "table 'Sun and Earth: Altitudes and Azimuths at the Apollo Landing Sites', computed by Paul Fjeld and "
             "Jim Scotti (Scotti values), spot-checked with JPL Horizons; revised 7 May 2025")

# Published landing times and Sun altitudes, transcribed from the ALSJ table (Scotti values).
APOLLO = [
    dict(id="APOLLO11", mission="Apollo 11", landing="1969-07-20T20:17:39Z", alsj_lon=23.4333, alsj_lat=0.6875, reported_sun_el=10.65),
    dict(id="APOLLO12", mission="Apollo 12", landing="1969-11-19T06:54:36Z", alsj_lon=-23.3856, alsj_lat=-3.1975, reported_sun_el=5.19),
    dict(id="APOLLO14", mission="Apollo 14", landing="1971-02-05T09:18:13Z", alsj_lon=-17.4653, alsj_lat=-3.6733, reported_sun_el=10.36),
    dict(id="APOLLO15", mission="Apollo 15", landing="1971-07-30T22:16:29Z", alsj_lon=3.6528, alsj_lat=26.1008, reported_sun_el=12.05),
    dict(id="APOLLO16", mission="Apollo 16", landing="1972-04-21T02:23:35Z", alsj_lon=15.5144, alsj_lat=-8.9914, reported_sun_el=14.76),
    dict(id="APOLLO17", mission="Apollo 17", landing="1972-12-11T19:54:58Z", alsj_lon=30.7658, alsj_lat=20.1653, reported_sun_el=13.33),
]

# Robotic landers: landing and end-of-operations proxy, each with the exact public wording found.
ROBOTIC = [
    dict(id="CHANDRAYAAN3", mission="Chandrayaan-3 (Vikram)", landing="2023-08-23T12:32:00Z",
         landing_source="ISRO (landing 23 Aug 2023 18:03-18:04 IST; date confirmed in the ISRO post quoted below)",
         reported="2023-09-04T02:30:00Z", reported_precision="time (around 08:00 IST)",
         reported_event="lander set into sleep mode (operator decision before local sunset; rover slept 2 Sep)",
         source_url="https://www.businesstoday.in/latest/trends/story/chandrayaan-3-update-vikram-lander-set-into-sleep-mode-at-8-am-payloads-are-now-switched-off-says-isro-396766-2023-09-04",
         source_quote="ISRO post embedded on the page: 'Vikram Lander is set into sleep mode around 08:00 Hrs. IST today' (4 Sep 2023)",
         source_kind="agency statement (ISRO post), via news page"),
    dict(id="SLIM", mission="SLIM (JAXA)", landing="2024-01-19T15:20:00Z",
         landing_source="JAXA DARTS mission page: 'landed on the moon on 2024-01-19 15:20' / 'January 20 at 00:20 JST'",
         reported="2024-02-01", reported_precision="date only",
         reported_event="sunset and hibernation after the first lunar day",
         source_url="https://cosmiclog.com/2024/02/01/japans-moon-lander-sleeps-again-after-sending-science/",
         source_quote="'Sunset came on Feb. 1, and once again, SLIM went into hibernation.' (quotes a JAXA X post; no agency page found)",
         source_kind="secondary (news) - no JAXA page with the date was found"),
    dict(id="IM1", mission="IM-1 Odysseus (Intuitive Machines / NASA CLPS)", landing="2024-02-22T23:23:00Z",
         landing_source="NASA: 'touched down Feb. 22 near Malapert A' (time 23:23 UTC as reported for the touchdown)",
         reported="2024-02-29", reported_precision="date only",
         reported_event="lander powered down (instruments ceased operations seven days after landing)",
         source_url="https://www.nasa.gov/centers-and-facilities/marshall/nasa-lights-beacon-on-moon-with-autonomous-navigation-system-test/",
         source_quote="NASA Marshall: '...before it officially powered down on Feb. 29.'",
         source_kind="NASA"),
    dict(id="CHANGE3", mission="Chang'e 3 (lander + Yutu)", landing="2013-12-14T13:11:00Z",
         landing_source="Chang'e 3 landed 14 Dec 2013 (phys.org / Spaceflight Now); 13:11 UTC as reported for touchdown",
         reported="2013-12-25T21:23:00Z", reported_precision="time (rover); lander same day",
         reported_event="rover hibernation (lander also entered sleep mode the same Wednesday)",
         source_url="https://spaceflightnow.com/china/change3/131227hibernation",
         source_quote="'Chinese state media reported the rover went into hibernation at 2123 GMT (4:23 p.m. EST) Wednesday.' (article of 27 Dec 2013)",
         source_kind="secondary (news) citing Chinese state media"),
    dict(id="CHANGE4", mission="Chang'e 4 (lander + Yutu-2)", landing="2019-01-03T02:26:00Z",
         landing_source="Spaceflight Now: 'The spacecraft landed at 0226 GMT on Jan. 3'",
         reported=None, reported_precision=None,
         reported_event="first lunar-night dormancy",
         source_url=None, source_quote="no public source found with the date/time of the FIRST lunar-night dormancy "
                                       "(Spaceflight Now only says it 'will begin in mid-January')",
         source_kind="no public source"),
]


def parse_t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def frame(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    return east, north, up


def az_el(vec3, lat, lon, h0_m):
    east, north, up = frame(lat, lon)
    v = np.atleast_2d(vec3) - (R_KM + (h0_m + 2.0) / 1000.0) * up
    e, n, u = v @ east, v @ north, v @ up
    return np.degrees(np.arctan2(e, n)) % 360.0, np.degrees(np.arctan2(u, np.hypot(e, n)))


def mask_at(hz, az):
    m = np.asarray(hz["mask"], float)
    x = (np.asarray(az) % 360.0) / hz["az_step_deg"]
    k = np.floor(x).astype(int) % m.size
    f = x - np.floor(x)
    return m[k] + (m[(k + 1) % m.size] - m[k]) * f


def sunlit(vecs, site, hz):
    """core.js sunlit: visible solar-disc fraction (flat mask line) >= 0.5."""
    az, el = az_el(vecs[:, :3], site["lat"], site["lon"], hz["h0_m"])
    y = np.clip((mask_at(hz, az) - el) / SUN_R, -1, 1)
    frac = (np.arccos(y) - y * np.sqrt(1 - y * y)) / np.pi
    return frac >= 0.5


def horizons_check(eng, offline, n=50, seed=21):
    z = np.load(NPZ)
    vec, hours = z["vectors"].astype(float), z["hour_index"]
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    rng = random.Random(seed)
    pick = sorted(rng.sample(range(len(hours)), n))
    rows, worst = [], 0.0
    for name, lat, lon in (("EQ_0_0", 0.0, 0.0), ("SOUTH_85S_30E", -85.0, 30.0)):
        for body, cmd, col in (("sun", 10, 0), ("earth", 399, 3)):
            times = [t0 + timedelta(hours=int(hours[k])) for k in pick]
            jd = [2440587.5 + t.timestamp() / 86400.0 for t in times]
            o = {"format": "json", "COMMAND": f"'{cmd}'", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
                 "SITE_COORD": f"'{lon},{lat},0.002'", "TLIST": "'" + " ".join(f"{j:.6f}" for j in jd) + "'",
                 "TLIST_TYPE": "'JD'", "TIME_TYPE": "'UT'", "QUANTITIES": "'4'", "CSV_FORMAT": "'YES'",
                 "EXTRA_PREC": "'YES'", "APPARENT": "'AIRLESS'", "CAL_FORMAT": "'JD'", "OBJ_DATA": "'NO'"}
            url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(o)
            path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")
            if path.exists():
                res = json.loads(path.read_text(encoding="utf-8"))
            elif offline:
                raise FileNotFoundError(path)
            else:
                with urllib.request.urlopen(url, timeout=300) as r:
                    res = json.load(r)
                CACHE.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(res), encoding="utf-8")
            txt = res["result"]
            tab = np.array([[float(x) for x in (l.split(",")[0], l.split(",")[3], l.split(",")[4])]
                            for l in txt.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()])
            az, el = az_el(vec[pick, col:col + 3], lat, lon, 0.0)
            a1, e1, a2, e2 = map(np.radians, (tab[:, 1], tab[:, 2], az, el))
            ang = np.degrees(np.arccos(np.clip(np.sin(e1) * np.sin(e2) + np.cos(e1) * np.cos(e2) * np.cos(a1 - a2), -1, 1)))
            worst = max(worst, float(ang.max()))
            rows.append(dict(site=name, body=body, n=len(pick), max_deg=float(ang.max()), mean_deg=float(ang.mean())))
            print(f"  Horizons {name} {body}: max {ang.max():.6f} deg", flush=True)
    return dict(file=NPZ.name, rows=int(len(hours)), first=str(z["start"]), stop_exclusive=str(z["stop_exclusive"]),
                seed=seed, sample_hours=n, checks=rows, max_deg=worst, passed=worst < 0.01)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    eng = E.Ephemeris(ROOT / "data/raw/kernels")
    sites = {s["id"]: s for s in json.loads((DATA / "sites.json").read_text(encoding="utf-8"))}
    hz = {i: json.loads((DATA / "horizon" / f"{i}.json").read_text(encoding="utf-8"))
          for i in [r["id"] for r in APOLLO + ROBOTIC]}

    print("1) ephemeris 2019-2025 vs Horizons", flush=True)
    eph_check = horizons_check(eng, a.offline)

    print("2a) Apollo Sun elevation at landing", flush=True)
    apollo = []
    for r in APOLLO:
        t = parse_t(r["landing"])
        v = eng.vectors([t])
        s, h = sites[r["id"]], hz[r["id"]]
        _, el_cat = az_el(v[:, :3], s["lat"], s["lon"], h["h0_m"])
        _, el_alsj = az_el(v[:, :3], r["alsj_lat"], r["alsj_lon"], 0.0)
        az_c, _ = az_el(v[:, :3], s["lat"], s["lon"], h["h0_m"])
        apollo.append(dict(id=r["id"], mission=r["mission"], landing_utc=r["landing"],
                           reported_sun_el_deg=r["reported_sun_el"], reported_source=ALSJ_URL,
                           ours_sun_el_deg_catalogue_point=round(float(el_cat[0]), 3),
                           ours_sun_el_deg_alsj_point=round(float(el_alsj[0]), 3),
                           difference_deg_catalogue=round(float(el_cat[0]) - r["reported_sun_el"], 3),
                           difference_deg_alsj_point=round(float(el_alsj[0]) - r["reported_sun_el"], 3),
                           terrain_mask_at_sun_az_deg=round(float(mask_at(h, az_c)[0]), 3),
                           catalogue_point=[s["lat"], s["lon"]], alsj_point=[r["alsj_lat"], r["alsj_lon"]],
                           h0_m=h["h0_m"]))
        print(f"  {r['mission']}: ours {el_cat[0]:.2f} (ALSJ point {el_alsj[0]:.2f}) vs reported {r['reported_sun_el']}", flush=True)

    print("2b) first local sunset after landing (core.js rule, 1-min steps)", flush=True)
    robotic = []
    for r in ROBOTIC:
        t0 = parse_t(r["landing"])
        s, h = sites[r["id"]], hz[r["id"]]
        minutes = 30 * 1440
        # vectors every 10 min, then linear interpolation to 1 min (Sun moves ~0.005 deg/min in the Moon frame)
        coarse_t = [t0 + timedelta(minutes=10 * k) for k in range(minutes // 10 + 1)]
        cv = eng.vectors(coarse_t)
        tm = np.arange(minutes) / 10.0
        k = np.floor(tm).astype(int)
        f = (tm - k)[:, None]
        vm = cv[k] * (1 - f) + cv[np.minimum(k + 1, len(cv) - 1)] * f
        lit = sunlit(vm, s, h)
        state0 = bool(lit[0])
        idx = int(np.argmax(~lit)) if state0 and (~lit).any() else None
        sunset = t0 + timedelta(minutes=idx) if idx is not None else None
        row = dict(id=r["id"], mission=r["mission"], landing_utc=r["landing"], landing_source=r["landing_source"],
                   sunlit_at_landing=state0, ours_first_sunset_utc=sunset.strftime("%Y-%m-%dT%H:%MZ") if sunset else None,
                   reported_event=r["reported_event"], reported_utc=r["reported"], reported_precision=r["reported_precision"],
                   source_url=r["source_url"], source_quote=r["source_quote"], source_kind=r["source_kind"],
                   proxy_note="End of operations is an approximate proxy for local sunset, not an exact measurement.")
        if sunset and r["reported"]:
            if r["reported_precision"] == "date only":
                rep_day = datetime.fromisoformat(r["reported"]).date()
                row["difference_days"] = (sunset.date() - rep_day).days
                row["difference_text"] = f"our sunset {sunset:%Y-%m-%d %H:%M} UTC vs reported date {rep_day}: {row['difference_days']:+d} day(s)"
            else:
                d = (sunset - parse_t(r["reported"])).total_seconds() / 3600.0
                row["difference_hours"] = round(d, 1)
                row["difference_text"] = f"our sunset minus reported event: {d:+.1f} h"
        else:
            row["difference_text"] = "not compared (no public source)" if not r["reported"] else "no sunset in 30 days"
        robotic.append(row)
        print(f"  {r['mission']}: sunlit at landing {state0}, our sunset {row['ours_first_sunset_utc']} | {row['difference_text']}", flush=True)

    out = dict(contract="docs/data_contract.md section 19 (proposal)", generated_utc=datetime.now(UTC).isoformat(),
               definitions=dict(sun_elevation="topocentric apparent Sun centre elevation, observer R + h0 + 2 m, no refraction",
                                sunset="first minute after landing when < 50 % of the solar disc is above the real terrain mask (core.js sunlit rule)",
                                ephemeris="card 1 pipeline (NAIF DE440s + MOON_ME DE421 via Skyfield)"),
               ephemeris_check=eph_check, apollo_sun_elevation=apollo, robotic_sunset=robotic,
               alsj_note=ALSJ_NOTE, mock=False)
    (DATA / "hindcast.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote web/data/hindcast.json")


if __name__ == "__main__":
    main()
