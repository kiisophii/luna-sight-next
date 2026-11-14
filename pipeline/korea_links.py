"""Korea links (differentiator B): ground stations, Danuri/KPLO passes, ShadowCam and sites of Korean interest.

Writes web/data/korea/*.json (format: docs/data_contract.md section 13, contract v1.2 proposal).

Usage:
    python pipeline/korea_links.py                 # everything (downloads are cached and resumable)
    python pipeline/korea_links.py --only stations # or: danuri, korea
    python -m pytest pipeline/test_korea_links.py -q

Inputs (cached under data/raw/, never committed):
  * NAIF generic kernels (de440s.bsp, moon_pa_de421_1900-2050.bpc, moon_080317.tf, pck00011.tpc)
  * Danuri (-155) Moon-centred ICRF vectors from the JPL Horizons API, 5-minute step, monthly chunks
  * web/data/sites.json (catalog) and web/data/horizon/<ID>.json (optional terrain masks)

Conventions follow the data contract: MOON_ME (DE421) frame, lon east-positive, azimuth 0 = north clockwise,
UTC hour index from 2026-01-01T00Z, R = 1737.4 km, observer 2 m above terrain, no refraction.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
KERNELS = RAW / "kernels"
DANURI_RAW = RAW / "danuri"
OUT = ROOT / "web" / "data" / "korea"
WEB_DATA = ROOT / "web" / "data"

NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
KERNEL_URLS = {
    "de440s.bsp": NAIF + "spk/planets/de440s.bsp",
    "moon_pa_de421_1900-2050.bpc": NAIF + "pck/moon_pa_de421_1900-2050.bpc",
    "moon_080317.tf": NAIF + "fk/satellites/moon_080317.tf",
    "pck00011.tpc": NAIF + "pck/pck00011.tpc",
    "kdsa01.tf": "https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf",
}
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"

R_MOON_KM = 1737.4
OBS_HEIGHT_M = 2.0
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
N_HOURS = 43824                      # 2026-01-01T00Z .. 2030-12-31T23Z
MIN_EL_STATION_DEG = 10.0
KST = timezone(timedelta(hours=9))

DSN_DOC = "https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf"
DSN_DOC_CITE = ("DSN Telecommunications Link Design Handbook 810-005, module 301 'Coverage and Geometry', "
                "Rev. P, Table 5 (geodetic coordinates, WGS 84)")


def dms(d, m, s, sign=1):
    return sign * (abs(d) + m / 60 + s / 3600)


# Station coordinates. KDSA: NAIF kdsa01.tf site definition (KARI). DSN: 810-005 module 301 Rev. P Table 5.
# Each DSN complex is represented by its 70 m antenna. Longitudes converted from 0..360 E to -180..180 E.
STATIONS = [
    {"id": "KDSA", "name": "Korea Deep Space Antenna (Yeoju), 35 m", "name_ko": "한국 심우주 안테나(여주), 35 m",
     "antenna": "KDSA01 (DSN code 32)", "country": "KR",
     "lat": 37.20723347, "lon": 127.62181206, "height_m": 145.359,
     "ellipsoid": "6378.1366 / 6356.7519 km (kdsa01.tf); ITRF93 per file, ITRF version unconfirmed in the file",
     "source": "NAIF kdsa01.tf (PINPOINT site definition by KARI, 2021-03-08)", "source_url": KERNEL_URLS["kdsa01.tf"],
     "terms": "PENDING: question to Seoul ops/SMEs on use of KDSA coordinates (owner: Dongju Kim)"},
    {"id": "DSN_GOLDSTONE", "name": "NASA DSN Goldstone (DSS-14, 70 m)", "name_ko": "NASA DSN 골드스톤(DSS-14, 70 m)",
     "antenna": "DSS 14", "country": "US",
     "lat": dms(35, 25, 33.24312), "lon": dms(243, 6, 37.66244) - 360, "height_m": 1001.390,
     "ellipsoid": "WGS 84", "source": DSN_DOC_CITE, "source_url": DSN_DOC, "terms": "NASA/JPL public document"},
    {"id": "DSN_MADRID", "name": "NASA DSN Madrid (DSS-63, 70 m)", "name_ko": "NASA DSN 마드리드(DSS-63, 70 m)",
     "antenna": "DSS 63", "country": "ES",
     "lat": dms(40, 25, 52.35510), "lon": dms(355, 45, 7.16924) - 360, "height_m": 864.816,
     "ellipsoid": "WGS 84", "source": DSN_DOC_CITE, "source_url": DSN_DOC, "terms": "NASA/JPL public document"},
    {"id": "DSN_CANBERRA", "name": "NASA DSN Canberra (DSS-43, 70 m)", "name_ko": "NASA DSN 캔버라(DSS-43, 70 m)",
     "antenna": "DSS 43", "country": "AU",
     "lat": dms(35, 24, 8.72724, -1), "lon": dms(148, 58, 52.56231), "height_m": 688.867,
     "ellipsoid": "WGS 84", "source": DSN_DOC_CITE, "source_url": DSN_DOC, "terms": "NASA/JPL public document"},
]

# Danuri trajectory span as reported by the Horizons -155 header (checked 2026-11-14):
# "Concatenated trajectory solutions 2022-Aug-04 23:19 .. 2027-Jun-03 08:36 TDB; tag-up data through
# 2026-11-10, prediction thereafter". We fetch the lunar-orbit part only.
DANURI_START = datetime(2023, 1, 1, tzinfo=timezone.utc)
DANURI_STOP = datetime(2027, 6, 3, 8, 0, tzinfo=timezone.utc)
DANURI_STEP_MIN = 5


# ----------------------------------------------------------------------------- utilities
def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def download(name):
    KERNELS.mkdir(parents=True, exist_ok=True)
    p = KERNELS / name
    if not p.exists() or p.stat().st_size < 1000:
        log("download", name)
        tmp = p.with_suffix(p.suffix + ".part")
        urllib.request.urlretrieve(KERNEL_URLS[name], tmp)
        tmp.replace(p)
    return p


def hour_index(dt):
    return (dt - T0).total_seconds() / 3600.0


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pack_bits(b):
    """bool array -> base64 of bytes; bit k of the series = byte k//8, bit (k%8) LSB-first."""
    return base64.b64encode(np.packbits(np.asarray(b, bool), bitorder="little").tobytes()).decode("ascii")


def unpack_bits(s, n):
    return np.unpackbits(np.frombuffer(base64.b64decode(s), np.uint8), bitorder="little")[:n].astype(bool)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log("wrote", path.relative_to(ROOT), f"{path.stat().st_size / 1024:.1f} KB")


class Ephem:
    """Skyfield objects: timescale, DE440s, MOON_ME_DE421 frame."""

    def __init__(self):
        from skyfield.api import Loader
        from skyfield.planetarylib import PlanetaryConstants
        for k in ("de440s.bsp", "moon_pa_de421_1900-2050.bpc", "moon_080317.tf", "pck00011.tpc"):
            download(k)
        ld = Loader(str(KERNELS), verbose=False)
        self.ts = ld.timescale(builtin=True)
        self.eph = ld("de440s.bsp")
        pc = PlanetaryConstants()
        pc.read_text(ld("moon_080317.tf"))
        pc.read_text(ld("pck00011.tpc"))
        pc.read_binary(ld("moon_pa_de421_1900-2050.bpc"))
        self.moon_me = pc.build_frame_named("MOON_ME_DE421")
        self.earth, self.moon = self.eph["earth"], self.eph["moon"]

    def hours(self, i0=0, n=N_HOURS):
        return self.ts.utc(2026, 1, 1, np.arange(i0, i0 + n))

    def rot_icrf_to_me(self, t):
        """(3,3,N) rotation matrices ICRF -> MOON_ME at times t."""
        return self.moon_me.rotation_at(t)

    def earth_in_me(self, t):
        """Moon centre -> Earth centre (geometric, km) in MOON_ME, shape (3, N)."""
        v = (self.earth - self.moon).at(t).position.km
        return np.einsum("ij...,j...->i...", self.rot_icrf_to_me(t), v)


# ----------------------------------------------------------------------------- 1. ground stations
def station_topos(st):
    from skyfield.api import wgs84
    return wgs84.latlon(st["lat"], st["lon"], elevation_m=st["height_m"])


def moon_altaz(E, st, t):
    """Apparent Moon-centre (alt, az) in degrees from a station, no refraction."""
    obs = E.earth + station_topos(st)
    alt, az, _ = obs.at(t).observe(E.moon).apparent().altaz()
    return alt.degrees, az.degrees


def station_windows(E, st, start, stop):
    """Exact (1-s) Moon >= 10 deg windows between datetimes; returns [(rise_dt, set_dt, max_el)]."""
    from skyfield.searchlib import find_discrete, find_maxima
    obs = E.earth + station_topos(st)

    def above(t):
        return obs.at(t).observe(E.moon).apparent().altaz()[0].degrees >= MIN_EL_STATION_DEG
    above.step_days = 1 / 48

    def elev(t):
        return obs.at(t).observe(E.moon).apparent().altaz()[0].degrees
    elev.step_days = 1 / 24

    t0, t1 = E.ts.from_datetime(start), E.ts.from_datetime(stop)
    tt, val = find_discrete(t0, t1, above, epsilon=1 / 86400)
    edges = [(ti.utc_datetime(), bool(v)) for ti, v in zip(tt, val)]
    out, cur = [], (start if above(t0) else None)
    for dt, v in edges:
        if v:
            cur = dt
        elif cur is not None:
            out.append([cur, dt]); cur = None
    if cur is not None:
        out.append([cur, stop])
    tm, vm = find_maxima(t0, t1, elev, epsilon=1 / 86400)
    mx = [(ti.utc_datetime(), v) for ti, v in zip(tm, vm)]
    res = []
    for a, b in out:
        peaks = [v for d, v in mx if a <= d <= b]
        res.append((a, b, round(float(max(peaks)) if peaks else float("nan"), 2)))
    return res


def build_stations(E):
    t = E.hours()
    bits, rows = {}, []
    end = T0 + timedelta(hours=N_HOURS)
    for st in STATIONS:
        log("station", st["id"])
        alt, _ = moon_altaz(E, st, t)
        b = alt >= MIN_EL_STATION_DEG
        bits[st["id"]] = b
        win = station_windows(E, st, T0, end)
        rows.append((st, b, win))
    dsn_any = bits["DSN_GOLDSTONE"] | bits["DSN_MADRID"] | bits["DSN_CANBERRA"]
    kdsa = bits["KDSA"]
    stations = []
    for st, b, win in rows:
        d = {k: st[k] for k in ("id", "name", "name_ko", "antenna", "country", "lat", "lon", "height_m", "ellipsoid",
                                "source", "source_url", "terms")}
        d["lat"], d["lon"] = round(d["lat"], 8), round(d["lon"], 8)
        d["frac_visible"] = round(float(b.mean()), 4)
        d["bits_b64"] = pack_bits(b)
        stations.append(d)
        write_json(OUT / f"windows_{st['id'].lower()}.json", {
            "station": st["id"], "min_el_deg": MIN_EL_STATION_DEG, "time": "UTC",
            "columns": ["rise_utc", "set_utc", "max_el_deg"],
            "windows": [[iso(a), iso(b_), m] for a, b_, m in win],
            "source": "Skyfield + NAIF de440s.bsp; apparent Moon centre, no refraction"})
        if st["id"] == "KDSA":
            write_json(OUT / "kdsa_daily_kst.json", kst_daily(win))
    write_json(OUT / "stations.json", {
        "start": iso(T0), "step_h": 1, "n": N_HOURS, "min_el_deg": MIN_EL_STATION_DEG,
        "bit_order": "LSB-first: hour k is bit (k % 8) of byte k // 8 of base64-decoded bits_b64",
        "definition": "true = apparent Moon centre >= 10 deg above the station's ellipsoidal horizon at the hour mark "
                      "(no refraction, no local terrain mask)",
        "stations": stations,
        "summary": {
            "frac_any_dsn": round(float(dsn_any.mean()), 4),
            "frac_any_dsn_or_kdsa": round(float((dsn_any | kdsa).mean()), 4),
            "frac_kdsa_only": round(float((kdsa & ~dsn_any).mean()), 4),
            "frac_kdsa_and_no_dsn_of_kdsa_hours": round(float((kdsa & ~dsn_any).sum() / max(kdsa.sum(), 1)), 4),
            "note": "kdsa_only = hours when KDSA sees the Moon but none of the three DSN 70 m antennas does",
        },
        "ephemeris": "NAIF de440s.bsp via Skyfield (builtin timescale / delta-T)", "mock": False})
    return bits


def kst_daily(win):
    """Per KST calendar date: windows that overlap that date, as KST 'HH:MM' strings (minute-rounded)."""
    days = {}
    for a, b, m in win:
        ak, bk = a.astimezone(KST), b.astimezone(KST)
        d = ak.date()
        while d <= bk.date():
            day0 = datetime(d.year, d.month, d.day, tzinfo=KST)
            s, e = max(ak, day0), min(bk, day0 + timedelta(days=1))
            if e > s:
                days.setdefault(d.isoformat(), []).append(
                    [s.strftime("%H:%M"), "24:00" if e == day0 + timedelta(days=1) else e.strftime("%H:%M"), m])
            d += timedelta(days=1)
    return {"station": "KDSA", "tz": "KST (UTC+9)", "min_el_deg": MIN_EL_STATION_DEG,
            "columns": ["from_kst", "to_kst", "max_el_deg_of_whole_window"],
            "note": "Times when the Moon is >= 10 deg above Yeoju. 'Tonight' = today's evening + next day's early hours.",
            "days": days}


# ----------------------------------------------------------------------------- 2. Danuri
def horizons_vectors(start, stop, step, target="-155", center="500@301"):
    q = {"format": "text", "COMMAND": f"'{target}'", "MAKE_EPHEM": "YES", "EPHEM_TYPE": "VECTORS",
         "CENTER": f"'{center}'", "START_TIME": f"'{start}'", "STOP_TIME": f"'{stop}'", "STEP_SIZE": f"'{step}'",
         "REF_SYSTEM": "ICRF", "REF_PLANE": "FRAME", "VEC_TABLE": "1", "VEC_CORR": "NONE", "OUT_UNITS": "KM-S",
         "CSV_FORMAT": "YES", "TIME_TYPE": "TDB"}
    return _horizons(q)


def horizons_vectors_tlist(jd_tdb, target="-155", center="500@301"):
    q = {"format": "text", "COMMAND": f"'{target}'", "MAKE_EPHEM": "YES", "EPHEM_TYPE": "VECTORS",
         "CENTER": f"'{center}'", "TLIST": " ".join(f"'{j:.9f}'" for j in jd_tdb), "TLIST_TYPE": "JD",
         "REF_SYSTEM": "ICRF", "REF_PLANE": "FRAME", "VEC_TABLE": "1", "VEC_CORR": "NONE", "OUT_UNITS": "KM-S",
         "CSV_FORMAT": "YES", "TIME_TYPE": "TDB"}
    return _horizons(q)


def _horizons(q, tries=4):
    url = HORIZONS_API + "?" + urllib.parse.urlencode(q)
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                txt = r.read().decode("utf-8", "replace")
            if "$$SOE" not in txt:
                raise RuntimeError("Horizons: no $$SOE\n" + txt[-1500:])
            return txt
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                raise
            log("horizons retry", k + 1, e)
            time.sleep(5 * (k + 1))


def parse_vectors(txt):
    body = txt.split("$$SOE")[1].split("$$EOE")[0]
    jd, xyz = [], []
    for line in body.strip().splitlines():
        p = [s.strip() for s in line.split(",")]
        jd.append(float(p[0])); xyz.append([float(p[2]), float(p[3]), float(p[4])])
    return np.array(jd), np.array(xyz)


def month_chunks(a, b):
    cur = a
    while cur < b:
        nxt = datetime(cur.year + (cur.month == 12), cur.month % 12 + 1, 1, tzinfo=timezone.utc)
        yield cur, min(nxt, b)
        cur = nxt


def fetch_danuri():
    """Monthly chunk files (resumable cache). Chunk = [start, next start) with the last row dropped (overlap)."""
    DANURI_RAW.mkdir(parents=True, exist_ok=True)

    def one(ab):
        a, b = ab
        p = DANURI_RAW / f"danuri_{a:%Y%m}.txt"
        if p.exists() and "$$EOE" in p.read_text(encoding="utf-8", errors="replace"):
            return p
        txt = horizons_vectors(a.strftime("%Y-%m-%d %H:%M"), b.strftime("%Y-%m-%d %H:%M"), f"{DANURI_STEP_MIN}m")
        p.write_text(txt, encoding="utf-8")
        log("danuri chunk", p.name)
        return p

    with ThreadPoolExecutor(4) as ex:
        paths = list(ex.map(one, list(month_chunks(DANURI_START, DANURI_STOP))))
    jds, xs = [], []
    for p in paths:
        jd, x = parse_vectors(p.read_text(encoding="utf-8"))
        jds.append(jd[:-1] if p != paths[-1] else jd); xs.append(x[:-1] if p != paths[-1] else x)
    jd, x = np.concatenate(jds), np.concatenate(xs)
    header = paths[-1].read_text(encoding="utf-8").split("$$SOE")[0]
    return jd, x, header


def danuri_me(E, jd_tdb, r_icrf):
    """Rotate Moon-centred ICRF positions (N,3) into MOON_ME; returns (N,3) and the time object."""
    t = E.ts.tdb_jd(jd_tdb)
    out = np.empty_like(r_icrf)
    B = 20000
    for k in range(0, len(jd_tdb), B):
        sl = slice(k, k + B)
        R = E.rot_icrf_to_me(t[sl])
        out[sl] = np.einsum("ijn,nj->ni", R, r_icrf[sl])
    return out, t


def site_frame(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.cross(up, east)
    return east, north, up


def load_mask(site_id):
    p = WEB_DATA / "horizon" / f"{site_id}.json"
    if not p.exists():
        return None
    h = json.loads(p.read_text(encoding="utf-8"))
    return h


def mask_at(h, az):
    if h is None:
        return np.zeros_like(az)
    m = np.asarray(h["mask"], float)
    step = h["az_step_deg"]
    x = (az % 360) / step
    k = np.floor(x).astype(int) % len(m)
    f = x - np.floor(x)
    return m[k] * (1 - f) + m[(k + 1) % len(m)] * f


def topo_azel(pos_site, frame, targets):
    """targets (N,3) km in MOON_ME -> az, el (deg) from pos_site."""
    e, n, u = frame
    d = targets - pos_site
    r = np.linalg.norm(d, axis=1)
    el = np.degrees(np.arcsin(np.clip(d @ u / r, -1, 1)))
    az = np.degrees(np.arctan2(d @ e, d @ n)) % 360
    return az, el


def site_position(site, h):
    h0 = (h or {}).get("h0_m")
    if h0 is None:
        h0 = site.get("elev_m") or 0.0
    rad = R_MOON_KM + (h0 + OBS_HEIGHT_M) / 1000.0
    _, _, u = site_frame(site["lat"], site["lon"])
    return rad * u, h0


def runs(mask):
    """Start/stop indices (stop exclusive) of True runs."""
    m = np.concatenate([[False], mask, [False]]).astype(np.int8)
    d = np.diff(m)
    return np.where(d == 1)[0], np.where(d == -1)[0]


def earth_visible_from_orbit(sc, earth):
    """Earth centre not occulted by the lunar sphere as seen from spacecraft positions (N,3)."""
    d = earth - sc
    dn = d / np.linalg.norm(d, axis=1)[:, None]
    tca = -(sc * dn).sum(1)                           # distance along ray to closest approach to Moon centre
    closest = np.linalg.norm(sc + np.clip(tca, 0, None)[:, None] * dn, axis=1)
    return (tca <= 0) | (closest > R_MOON_KM)


def build_danuri(E, sites):
    jd, r_icrf, header = fetch_danuri()
    log("danuri rows", len(jd))
    r_me, t = danuri_me(E, jd, r_icrf)
    DATA_PROC = ROOT / "data" / "processed"; DATA_PROC.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DATA_PROC / "danuri_moon_me_5min.npz", jd_tdb=jd, r_me_km=r_me)
    utc = t.utc_datetime()
    hidx = np.array([hour_index(d) for d in utc])
    alt = np.linalg.norm(r_me, axis=1) - R_MOON_KM

    w = hidx >= 0                                     # contract window part (2026-01-01 ..)
    hw, rw, tw = hidx[w], r_me[w], t[w]
    earth = np.empty_like(rw)
    for k in range(0, len(hw), 20000):
        earth[k:k + 20000] = E.earth_in_me(tw[k:k + 20000]).T
    sc_sees_earth = earth_visible_from_orbit(rw, earth)
    dt_h = DANURI_STEP_MIN / 60

    out_sites = []
    for s in sites:
        h = load_mask(s["id"])
        pos, h0 = site_position(s, h)
        fr = site_frame(s["lat"], s["lon"])
        az, el = topo_azel(pos, fr, rw)
        above = el - mask_at(h, az)
        vis = above > 0
        vis_flat = el > 0
        eaz, eel = topo_azel(pos, fr, earth)
        direct = eel > mask_at(h, eaz)
        a, b = runs(vis)
        starts, durs, maxel = [], [], []
        for i0, i1 in zip(a, b):
            # refine edges by linear interpolation of (el - mask) between samples
            ts_ = hw[i0] - (dt_h * above[i0] / (above[i0] - above[i0 - 1]) if i0 > 0 else 0)
            te_ = hw[i1 - 1] + (dt_h * above[i1 - 1] / (above[i1 - 1] - above[i1]) if i1 < len(hw) else 0)
            starts.append(round(float(ts_), 4)); durs.append(int(round((te_ - ts_) * 3600)))
            maxel.append(round(float(el[i0:i1].max()), 1))
        no_direct = ~direct
        relay = no_direct & vis & sc_sees_earth
        gaps_a, gaps_b = runs(no_direct & ~relay)
        longest_gap_h = float(((gaps_b - gaps_a).max() if len(gaps_a) else 0) * dt_h)
        out_sites.append({
            "id": s["id"], "lat": s["lat"], "lon": s["lon"], "h0_m": h0,
            "mask": "terrain" if h else "flat",
            "mask_mock": bool(h.get("mock", False)) if h else None,
            "site_coords_mock": bool(s.get("mock", False)),
            "passes": {"start_i": starts, "dur_s": durs, "max_el_deg": maxel},
            "n_passes": len(starts),
            "visible_frac": round(float(vis.mean()), 4),
            "visible_frac_flat": round(float(vis_flat.mean()), 4),
            "direct_earth_frac": round(float(direct.mean()), 4),
            "no_direct_hours": round(float(no_direct.sum() * dt_h), 1),
            "relay_covered_hours": round(float(relay.sum() * dt_h), 1),
            "relay_upper_bound": round(float(relay.sum() / max(no_direct.sum(), 1)), 4),
            "longest_uncovered_gap_h": round(longest_gap_h, 2),
            "median_pass_min": round(float(np.median(durs) / 60), 1) if durs else 0,
        })
        log("danuri site", s["id"], out_sites[-1]["n_passes"], "passes, relay UB", out_sites[-1]["relay_upper_bound"])

    # small track sample for the 3D view: first 24 h of the window at 5 min
    k0 = np.argmax(w)
    trk = r_me[k0:k0 + 289]
    span_note = [ln.strip() for ln in header.splitlines() if "Tag-up" in ln or "Concatenated" in ln]
    write_json(OUT / "danuri.json", {
        "target": "Danuri / KPLO (Horizons -155)", "frame": "MOON_ME_DE421",
        "source": "JPL Horizons API vectors, CENTER=500@301, ICRF, geometric, 5-min step; rotated to MOON_ME with "
                  "NAIF moon_pa_de421_1900-2050.bpc + moon_080317.tf via Skyfield",
        "source_url": HORIZONS_API, "horizons_span_note": span_note,
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "fetched_span": [iso(DANURI_START), iso(utc[-1])],
        "window": [iso(utc[np.argmax(w)]), iso(utc[-1])], "step_min": DANURI_STEP_MIN,
        "prediction_after": "2026-11-10 (Horizons header: tag-up data through Nov 10, prediction thereafter)",
        "orbit": {"alt_km_min": round(float(alt.min()), 1), "alt_km_max": round(float(alt.max()), 1),
                  "alt_km_min_window": round(float(alt[w].min()), 1), "alt_km_max_window": round(float(alt[w].max()), 1)},
        "definitions": {
            "pass": "Danuri centre above the site's horizon mask (terrain mask if web/data/horizon/<ID>.json exists, "
                    "else flat 0 deg), observer 2 m above terrain; edges linearly interpolated between 5-min samples",
            "start_i": "UTC hour index from 2026-01-01T00Z (fractional)",
            "relay_upper_bound": "share of the site's no-direct-Earth time (Earth centre below the mask) during "
                                 "which Danuri is above the site's mask AND Earth's centre is not blocked by the lunar "
                                 "sphere as seen from Danuri",
        },
        "caveat": "Danuri carries no lander relay payload. relay_upper_bound is a GEOMETRIC upper bound only "
                  "(no link budget, scheduling, pointing or payload). It shows what an orbiter like Danuri could "
                  "cover, not a service that exists.",
        "track_sample": {"start": iso(utc[k0]), "step_min": DANURI_STEP_MIN,
                         "xyz_km": np.round(trk, 1).tolist()},
        "sites": out_sites, "mock": False})


# ----------------------------------------------------------------------------- 3/4. korea.json
SHADOWCAM_PDS = "https://pds.shadowcam.asu.edu/"   # redirects to pds.shadowcam.im-ldi.com
SHADOWCAM_PRODUCTS = [
    # (target, IAU feature URL or note, PDS directory, product stem)
    ("Shackleton crater (PSR interior)", "https://planetarynames.wr.usgs.gov/Feature/5450",
     "derived/cmosaic/shackleton01/", "shadowcam_cmosaic_shackleton01_p896s1350_summer_11am"),
    ("Spudis crater", "https://planetarynames.wr.usgs.gov/Feature/16007",
     "derived/umosaic/spudis01/", "shadowcam_umosaic_spudis01_p889s3107_summer_02pm"),
    ("Shackleton-de Gerlache ridge (ShadowCam name, not IAU)", None,
     "derived/umosaic/shackletondegerlacheridge01/",
     "shadowcam_umosaic_shackletondegerlacheridge01_p884s0447_summer_09am"),
]


def _tag(xml, name):
    import re
    m = re.search(rf"<{name}[^>]*>([^<]+)</{name}>", xml)
    return m.group(1).strip() if m else None


def ps_xy_to_latlon(x, y, R=1737400.0):
    """South polar stereographic (origin -90, central meridian 0, sphere R) -> planetocentric lat, lon (deg)."""
    rho = math.hypot(x, y)
    lat = -90 + math.degrees(2 * math.atan(rho / (2 * R)))
    lon = math.degrees(math.atan2(x, y))      # south pole aspect: x = rho sin(lon), y = rho cos(lon)
    return round(lat, 5), round(lon, 5)


def shadowcam_meta():
    """Read each product's 20 m PDS4 label: georeferencing for map/3D overlays (no image download)."""
    out = []
    for target, iau, d, stem in SHADOWCAM_PRODUCTS:
        base = SHADOWCAM_PDS + d + stem
        cache = RAW / "shadowcam" / f"{stem}_20m.xml"
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(base + "_20m.xml", cache)
        x = cache.read_text(encoding="utf-8")
        import re
        elems = [int(v) for v in re.findall(r"<elements>(\d+)</elements>", x)]
        lines, samples = elems[0], elems[1]
        ulx, uly = float(_tag(x, "cart:upperleft_corner_x")), float(_tag(x, "cart:upperleft_corner_y"))
        px = float(_tag(x, "cart:pixel_resolution_x"))
        corners = {k: ps_xy_to_latlon(ulx + sx * px, uly - sy * px) for k, (sx, sy) in
                   {"ul": (0, 0), "ur": (samples, 0), "lr": (samples, lines), "ll": (0, lines)}.items()}
        cx, cy = ulx + samples * px / 2, uly - lines * px / 2
        out.append({
            "target": target, "iau_feature_url": iau, "product_id": stem + "_20m",
            "title": _tag(x, "title"),
            "label_url": base + "_20m.xml", "data_url": base + "_20m.cub",
            "browse_cog_url": base + "_20m_cog.tif", "full_res_label_url": base + ".xml",
            "readme_url": base + "_readme.txt",
            "size_bytes_20m_cub": int(_tag(x, "file_size")),
            "start_utc": _tag(x, "start_date_time"), "stop_utc": _tag(x, "stop_date_time"),
            "lines": lines, "samples": samples, "pixel_m": px,
            "projection": {"name": _tag(x, "cart:map_projection_name"),
                           "latitude_of_projection_origin": float(_tag(x, "cart:latitude_of_projection_origin")),
                           "longitude_of_central_meridian": float(_tag(x, "cart:longitude_of_central_meridian")),
                           "radius_m": float(_tag(x, "cart:a_axis_radius")),
                           "upperleft_x_m": ulx, "upperleft_y_m": uly},
            "bounds_deg": {k: float(_tag(x, f"cart:{k}_bounding_coordinate")) for k in ("west", "east", "north", "south")},
            "center_latlon": ps_xy_to_latlon(cx, cy), "corners_latlon": corners,
        })
        log("shadowcam", stem, lines, "x", samples)
    return out


def build_korea():
    """Sites of Korean interest + ShadowCam product metadata (links only, no image files)."""
    src = json.loads((ROOT / "pipeline" / "korea_sources.json").read_text(encoding="utf-8"))
    src["shadowcam"]["products"] = shadowcam_meta()
    write_json(OUT / "korea.json", src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["stations", "danuri", "korea"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.only in (None, "korea"):
        build_korea()
    if a.only in (None, "stations", "danuri"):
        E = Ephem()
        if a.only in (None, "stations"):
            build_stations(E)
        if a.only in (None, "danuri"):
            sites = json.loads((WEB_DATA / "sites.json").read_text(encoding="utf-8"))
            kj = OUT / "korea.json"
            if kj.exists():
                ids = {s["id"] for s in sites}
                sites += [s for s in json.loads(kj.read_text(encoding="utf-8"))["sites_of_korean_interest"]
                          if s["id"] not in ids]
            build_danuri(E, sites)


if __name__ == "__main__":
    sys.exit(main())
