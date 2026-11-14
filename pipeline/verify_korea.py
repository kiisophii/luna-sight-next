"""Card 16 - direct-to-Earth link windows via Yeoju KDSA and the NASA DSN, with independent checks.

Definition (same as the app, web/js/diff_data.js siteStationLink):
  link hour at site S and station G  =  Earth CENTRE above S's terrain horizon mask (topocentric, 2 m observer)
                                        AND apparent Moon centre >= 10 deg above G's ellipsoidal horizon.
Direct link only: no relay, no link budget, no antenna schedule/availability.

What it does
  1. Per-site table for all 33 sites, hourly 2026-01-01 .. 2030-12-31 (43,824 h), station bits from
     web/data/korea/stations.json (pipeline/korea_links.py): Earth-visible hours, hours covered by KDSA,
     by any DSN complex (Goldstone DSS-14, Madrid DSS-63, Canberra DSS-43), and KDSA-only hours
     ("Korea fills the gap": Earth visible, KDSA sees the Moon, no DSN complex does).
     Earth visibility here is our own implementation; it is cross-checked against the app's
     web/data/metrics/<ID>.json earth_frac (actual core.js).
  2. JPL Horizons (independent): hourly apparent airless Moon az/el for the 4 stations over the whole
     window (observer = station geodetic coordinates as cited in korea_links.py STATIONS).
       a. 100 random hours (seed 16): Horizons vs korea_links.moon_altaz (Skyfield) - criterion < 0.05 deg
       b. all 43,824 hours: station bits from Horizons (el >= 10) vs stations.json bits
  3. Brute force for 5 sites without korea_links.py: Earth visibility from the horizon file + ephem.bin,
     station bits from Horizons -> same counts as the table?
  4. 30-day KST schedule (from 2026-11-14 KST) for ARTEMIS_HAWORTH and APOLLO17: when KDSA has a direct
     link, at 1-minute resolution (Earth vector linearly interpolated between hourly ephemeris rows,
     KDSA rise/set from web/data/korea/windows_kdsa.json).

Outputs: docs/korea_links_check.json, docs/korea_links.md
  python pipeline/verify_korea.py [--offline]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import korea_links as KL  # noqa: E402  (stations + Skyfield, only for check 2a and coordinates)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
CACHE = ROOT / "data" / "raw" / "horizons_korea"
API = "https://ssd.jpl.nasa.gov/api/horizons.api"
N = 43824
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))
BRUTE_SITES = ["ARTEMIS_HAWORTH", "APOLLO17", "CHANGE4", "SHACKLETON_RIM", "IM1"]
SCHEDULE_SITES = ["ARTEMIS_HAWORTH", "APOLLO17"]
SCHEDULE_START_KST = datetime(2026, 11, 14, tzinfo=KST)
DSN = ["DSN_GOLDSTONE", "DSN_MADRID", "DSN_CANBERRA"]


def decode_bits(b64, n):
    import base64
    return np.unpackbits(np.frombuffer(base64.b64decode(b64), np.uint8), bitorder="little")[:n].astype(bool)


def earth_visible(vec, site, hz):
    """Earth centre above the terrain mask (topocentric, observer h0 + 2 m). Own implementation."""
    la, lo = math.radians(site["lat"]), math.radians(site["lon"])
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.cross(up, east)
    v = vec[:, 3:6] - (1737.4 + (hz["h0_m"] + 2.0) / 1000.0) * up
    e, n, u = v @ east, v @ north, v @ up
    az = np.degrees(np.arctan2(e, n)) % 360.0
    el = np.degrees(np.arctan2(u, np.hypot(e, n)))
    m = np.asarray(hz["mask"], float)
    x = az / hz["az_step_deg"]
    k = np.floor(x).astype(int) % m.size
    f = x - np.floor(x)
    return el > m[k] * (1 - f) + m[(k + 1) % m.size] * f


def horizons_station(st, offline):
    """Hourly apparent airless Moon az/el from the station, 2026-01-01T00Z .. 2030-12-31T23Z."""
    o = {"format": "json", "COMMAND": "'301'", "CENTER": "'coord@399'", "COORD_TYPE": "'GEODETIC'",
         "SITE_COORD": f"'{st['lon']:.8f},{st['lat']:.8f},{st['height_m'] / 1000:.6f}'",
         "START_TIME": "'2026-01-01 00:00'", "STOP_TIME": "'2030-12-31 23:00'", "STEP_SIZE": "'1 h'",
         "QUANTITIES": "'4'", "CSV_FORMAT": "'YES'", "EXTRA_PREC": "'YES'", "APPARENT": "'AIRLESS'",
         "CAL_FORMAT": "'JD'", "OBJ_DATA": "'NO'"}
    url = API + "?" + urllib.parse.urlencode(o)
    path = CACHE / (st["id"].lower() + "_" + hashlib.sha256(url.encode()).hexdigest()[:10] + ".json")
    if path.exists():
        item = json.loads(path.read_text(encoding="utf-8"))
    elif offline:
        raise FileNotFoundError(path)
    else:
        with urllib.request.urlopen(url, timeout=600) as r:
            item = {"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(), "response": json.load(r)}
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(item), encoding="utf-8")
    res = item["response"]["result"]
    if "$$SOE" not in res:
        raise ValueError(res[:400])
    rows = [l.split(",") for l in res.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()]
    jd = np.array([float(r[0]) for r in rows])
    az = np.array([float(r[3]) for r in rows])
    el = np.array([float(r[4]) for r in rows])
    hours = np.rint((jd - 2461041.5) * 24).astype(int)
    if hours.size != N or not np.array_equal(hours, np.arange(N)):
        raise ValueError(f"{st['id']}: Horizons returned {hours.size} rows, not the 43,824-hour grid")
    return az, el, {"url": url, "retrieved_utc": item["retrieved_utc"], "header_radii":
                    res.split("Center radii")[1].split("\n")[0].strip(": ").strip() if "Center radii" in res else ""}


def runs_kst(mask_min, t0):
    """Boolean per-minute array -> list of (start_dt, end_dt)."""
    out, start = [], None
    for k, b in enumerate(mask_min):
        if b and start is None:
            start = k
        if not b and start is not None:
            out.append((t0 + timedelta(minutes=start), t0 + timedelta(minutes=k)))
            start = None
    if start is not None:
        out.append((t0 + timedelta(minutes=start), t0 + timedelta(minutes=len(mask_min))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)

    vec = np.fromfile(DATA / "ephem.bin", dtype="<f4").reshape(-1, 6).astype(np.float64)
    assert vec.shape[0] == N
    sites = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))
    st_json = json.loads((DATA / "korea" / "stations.json").read_text(encoding="utf-8"))
    bits = {s["id"]: decode_bits(s["bits_b64"], N) for s in st_json["stations"]}
    dsn_any = bits["DSN_GOLDSTONE"] | bits["DSN_MADRID"] | bits["DSN_CANBERRA"]
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(), "window": "2026-01-01T00Z..2030-12-31T23Z",
              "hours": N, "definition": __doc__.split("Definition")[1].split("What it does")[0].strip()}

    # 1. per-site table
    table, earth_bits, app_diff = [], {}, 0.0
    for s in sites:
        hz = json.loads((DATA / "horizon" / f"{s['id']}.json").read_text(encoding="utf-8"))
        ev = earth_visible(vec, s, hz)
        earth_bits[s["id"]] = (ev, hz)
        app = json.loads((DATA / "metrics" / f"{s['id']}.json").read_text(encoding="utf-8"))["earth_frac"]
        app_diff = max(app_diff, abs(app - ev.mean()))
        e = int(ev.sum())
        kd, ds, ko = int((ev & bits["KDSA"]).sum()), int((ev & dsn_any).sum()), int((ev & bits["KDSA"] & ~dsn_any).sum())
        table.append({"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"], "earth_h": e,
                      "kdsa_h": kd, "dsn_h": ds, "kdsa_only_h": ko,
                      "kdsa_share": round(kd / e, 4) if e else None, "dsn_share": round(ds / e, 4) if e else None,
                      "kdsa_only_share": round(ko / e, 5) if e else None})
    report["sites"] = table
    report["earth_frac_vs_app_metrics_max_abs_diff"] = app_diff
    print(f"1) 33-site table done; Earth-visible share vs app metrics (core.js): max |diff| {app_diff:.2e}")

    # 2. Horizons
    rng = np.random.default_rng(16)
    sample = np.sort(rng.choice(N, 100, replace=False))
    E = KL.Ephem()
    hz_bits, h2a, h2b, meta = {}, [], [], []
    for st in KL.STATIONS:
        az_h, el_h, m = horizons_station(st, a.offline)
        meta.append(dict(station=st["id"], **m))
        hz_bits[st["id"]] = el_h >= 10.0
        alt, az = KL.moon_altaz(E, st, E.hours()[sample] if False else E.ts.utc(2026, 1, 1, sample))
        # great-circle angle between the two (az, el) directions
        a1, e1, a2, e2 = map(np.radians, (az_h[sample], el_h[sample], az, alt))
        cosd = np.sin(e1) * np.sin(e2) + np.cos(e1) * np.cos(e2) * np.cos(a1 - a2)
        ang = np.degrees(np.arccos(np.clip(cosd, -1, 1)))
        h2a.append({"station": st["id"], "n": 100, "max_deg": float(ang.max()), "mean_deg": float(ang.mean()),
                    "max_el_diff_deg": float(np.abs(e1 - e2).max() * 180 / math.pi)})
        mism = np.flatnonzero(hz_bits[st["id"]] != bits[st["id"]])
        h2b.append({"station": st["id"], "hours": N, "mismatched_hours": int(mism.size),
                    "max_abs_el_minus_10_at_mismatch_deg": float(np.abs(el_h[mism] - 10).max()) if mism.size else 0.0,
                    "frac_visible_horizons": round(float(hz_bits[st["id"]].mean()), 4),
                    "frac_visible_stations_json": round(float(bits[st["id"]].mean()), 4)})
        print(f"2) {st['id']}: 100 random hours max {ang.max():.5f} deg; bits mismatched {mism.size}/{N}", flush=True)
    report["horizons_random_100"] = h2a
    report["horizons_bits_all_hours"] = h2b
    report["horizons_queries"] = meta

    # 3. brute force 5 sites with Horizons station bits
    hdsn = hz_bits["DSN_GOLDSTONE"] | hz_bits["DSN_MADRID"] | hz_bits["DSN_CANBERRA"]
    brute = []
    for sid in BRUTE_SITES:
        ev, _ = earth_bits[sid]
        row = next(r for r in table if r["id"] == sid)
        b = {"id": sid, "earth_h": int(ev.sum()), "kdsa_h": int((ev & hz_bits["KDSA"]).sum()),
             "dsn_h": int((ev & hdsn).sum()), "kdsa_only_h": int((ev & hz_bits["KDSA"] & ~hdsn).sum())}
        b["diff_vs_table_h"] = {k: b[k] - row[k] for k in ("earth_h", "kdsa_h", "dsn_h", "kdsa_only_h")}
        brute.append(b)
        print(f"3) {sid}: brute {b}", flush=True)
    report["brute_force_5_sites"] = brute

    # 4. 30-day KST schedule at 1-minute resolution
    win = json.loads((DATA / "korea" / "windows_kdsa.json").read_text(encoding="utf-8"))["windows"]
    t0 = SCHEDULE_START_KST.astimezone(timezone.utc)
    mins = 30 * 1440
    tmin = np.arange(mins) / 60.0 + (t0 - T0).total_seconds() / 3600.0      # fractional hour index
    kd = np.zeros(mins, bool)
    for r, s_, _ in win:
        rs = datetime.fromisoformat(r.replace("Z", "+00:00")); ss = datetime.fromisoformat(s_.replace("Z", "+00:00"))
        i0 = max(0, math.ceil((rs - t0).total_seconds() / 60)); i1 = min(mins, math.floor((ss - t0).total_seconds() / 60))
        if i1 > i0:
            kd[i0:i1] = True
    i = np.floor(tmin).astype(int); f = (tmin - i)[:, None]
    vmin = vec[i] * (1 - f) + vec[np.minimum(i + 1, N - 1)] * f
    sched = {}
    for sid in SCHEDULE_SITES:
        s = next(x for x in sites if x["id"] == sid)
        ev = earth_visible(vmin, s, earth_bits[sid][1])
        link = runs_kst(ev & kd, t0)
        days = {}
        for a_, b_ in link:
            a_k, b_k = a_.astimezone(KST), b_.astimezone(KST)
            while a_k.date() < b_k.date():
                nxt = datetime.combine(a_k.date() + timedelta(days=1), datetime.min.time(), KST)
                days.setdefault(a_k.date().isoformat(), []).append([a_k.strftime("%H:%M"), "24:00"]); a_k = nxt
            if b_k > a_k:
                days.setdefault(a_k.date().isoformat(), []).append([a_k.strftime("%H:%M"), b_k.strftime("%H:%M")])
        sched[sid] = {"earth_visible_minutes": int(ev.sum()), "kdsa_link_minutes": int((ev & kd).sum()), "days_kst": days}
        print(f"4) {sid}: {len(link)} KDSA link windows in 30 days, {int((ev & kd).sum())} min", flush=True)
    report["schedule_30d_kst"] = {"start_kst": SCHEDULE_START_KST.isoformat(), "resolution": "1 min", "sites": sched}

    # verdicts
    v = {
        "horizons_az_el_lt_0.05deg": all(r["max_deg"] < 0.05 for r in h2a),
        "station_bits_match_except_threshold": all(r["max_abs_el_minus_10_at_mismatch_deg"] < 0.05 for r in h2b),
        "brute_force_matches_table": all(all(abs(x) <= 2 for x in b["diff_vs_table_h"].values()) for b in brute),
        "earth_visibility_equals_app": app_diff < 1e-12,
    }
    report["verdicts"] = v
    (ROOT / "docs" / "korea_links_check.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("verdicts:", v)
    return 0 if all(v.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
