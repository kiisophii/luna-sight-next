"""Independent verification of detail Z1 time statistics (web/data/detail/time_stats/).

Checker: Soyun Jeong, 2026-11-15. Producer: Jiyong Sung (PR #80).
No producer code is imported or run (pipeline/detail_time_stats.mjs, pipeline/verify_detail_author.py,
or any earlier Z1 check such as verification/task_z1_z4/verify.mjs). Definitions are taken from
web/js/core.js and docs/data_contract.md (sections 2, 3, 13.1, 19.1, "Z1") and re-implemented here.

Inputs read directly: web/data/sites.json, ephem.bin, ephem.json, horizon/<ID>.json, korea/stations.json.
Compared against: web/data/detail/time_stats/<ID>.json, metrics/<ID>.json, windows/<ID>.json.

Two separate evaluations of the hourly states are made and must agree bit for bit:
  * `scalar`: a literal per-hour loop with Python's math module (same statement order as core.js);
  * `vector`: NumPy arrays.
Run detection is an explicit state machine (not np.diff); station bits are decoded with explicit
shifts (`byte >> (k & 7) & 1`) and cross-checked against numpy.unpackbits(bitorder="little").

Usage (repo root):
  .venv/Scripts/python -X utf8 pipeline/verify_z1_independent_soyun.py run      # 3 selected sites (+ all 33 as a supplement)
  .venv/Scripts/python -X utf8 pipeline/verify_z1_independent_soyun.py report   # docs/z1_independent_soyun.md
"""
import base64
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web/data"
OUT_JSON = ROOT / "docs/z1_independent_soyun.json"
OUT_MD = ROOT / "docs/z1_independent_soyun.md"

R_KM = 1737.4              # core.js R_MOON_KM
OBS_M = 2.0                # core.js observerPos: R + (h0 + 2) / 1000
SUN_R_DEG = 0.2666         # core.js SUN_RADIUS_DEG
SUNLIT_FRACTION = 0.5      # core.js SUNLIT_FRACTION
N = 43824
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
STATION_IDS = ["KDSA", "DSN_GOLDSTONE", "DSN_MADRID", "DSN_CANBERRA"]

# Selection (see report): avoids PR #82's APOLLO17, CHANGE4, SHACKLETON_RIM.
SELECTED = {
    "ARTEMIS_MALAPERT": "South polar but Earth ALWAYS visible: no-Earth runs absent (mean_h null, longest_h 0) and station "
                        "counts limited only by the stations; dark run clipped at the END (365 h, not the longest 415 h) and "
                        "sunlit run clipped at the START (236 h). Pattern shared by 12 sites, none checked by PR #82.",
    "ARTEMIS_CABEUS_B": "South polar, intermittent Earth (12,988 h) and the smallest Sun+Earth total of all sites (4,671 h); "
                        "dark runs clipped at BOTH edges (two runs), no clipped sunlit run; 67 complete no-Earth runs; "
                        "KDSA / >=1 / >=2 counts all partial. Not checked by PR #82 or the integrator.",
    "CHANGE6": "Far side, Earth NEVER visible: one whole-period no-Earth run clipped at both ends (complete_count 0, "
               "complete_mean_h null) and all station counts 0; dark runs clipped at both edges. The only site with this "
               "pattern; PR #82's CHANGE4 differs (dark clipped at start, sunlight at end).",
}

RUN_FIELDS = ["count", "total_h", "mean_h", "longest_h", "complete_count", "complete_mean_h", "complete_longest_h", "clipped_runs"]


# ---------------------------------------------------------------- inputs
def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def file_hashes(p):
    b = Path(p).read_bytes()
    rec = {"path": str(Path(p).relative_to(ROOT)).replace("\\", "/"), "bytes": len(b), "sha256_raw": sha256_bytes(b)}
    if Path(p).suffix != ".bin":
        rec["sha256_lf"] = sha256_bytes(b.replace(b"\r\n", b"\n"))
    return rec


def load_ephem():
    meta = read_json(WEB / "ephem.json")
    assert meta["start"] == "2026-01-01T00:00:00Z" and meta["step_h"] == 1 and meta["n"] == N, meta
    assert meta["columns"] == ["sun_x", "sun_y", "sun_z", "earth_x", "earth_y", "earth_z"]
    e = np.fromfile(WEB / "ephem.bin", dtype="<f4")
    assert e.size == N * 6
    return e.astype(np.float64).reshape(N, 6)


def body_row(eph, i, c0):
    """core.js bodyVec(i, col0) for integer i: k = min(i, n-2), t = i - k (t = 1 at the last hour)."""
    k = min(i, N - 2)
    t = i - k
    a, b = eph[k], eph[min(k + 1, N - 1)]
    return (a[c0] + (b[c0] - a[c0]) * t, a[c0 + 1] + (b[c0 + 1] - a[c0 + 1]) * t, a[c0 + 2] + (b[c0 + 2] - a[c0 + 2]) * t)


def decode_station_bits(b64, n=N):
    raw = base64.b64decode(b64)
    assert len(raw) == (n + 7) // 8, (len(raw), n)
    explicit = np.array([(raw[k >> 3] >> (k & 7)) & 1 for k in range(n)], dtype=bool)
    unpacked = np.unpackbits(np.frombuffer(raw, np.uint8), bitorder="little")[:n].astype(bool)
    assert np.array_equal(explicit, unpacked)
    return explicit


# ---------------------------------------------------------------- hourly states
def frame(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    sl, cl, so, co = math.sin(la), math.cos(la), math.sin(lo), math.cos(lo)
    return (-so, co, 0.0), (-sl * co, -sl * so, cl), (cl * co, cl * so, sl)


def states_scalar(lat, lon, h0_m, mask, az_step, eph):
    east, north, up = frame(lat, lon)
    r = R_KM + (h0_m + OBS_M) / 1000
    o = (up[0] * r, up[1] * r, up[2] * r)
    m = [float(x) for x in mask]
    nb = len(m)

    def azel(v):
        e = v[0] * east[0] + v[1] * east[1] + v[2] * east[2]
        nn = v[0] * north[0] + v[1] * north[1] + v[2] * north[2]
        u = v[0] * up[0] + v[1] * up[1] + v[2] * up[2]
        az = math.atan2(e, nn) * (180 / math.pi)
        if az < 0:
            az += 360
        return az, math.atan2(u, math.hypot(e, nn)) * (180 / math.pi)

    def hz(az):
        x = ((az % 360) + 360) % 360 / az_step
        k = int(math.floor(x)) % nb
        t = x - math.floor(x)
        return m[k] + (m[(k + 1) % nb] - m[k]) * t

    sun = np.zeros(N, bool)
    earth = np.zeros(N, bool)
    sun_margin = np.zeros(N)
    earth_margin = np.zeros(N)
    for i in range(N):
        s = body_row(eph, i, 0)
        az, el = azel((s[0] - o[0], s[1] - o[1], s[2] - o[2]))
        y = (hz(az) - el) / SUN_R_DEG
        frac = 1.0 if y <= -1 else 0.0 if y >= 1 else (math.acos(y) - y * math.sqrt(1 - y * y)) / math.pi
        sun[i] = frac >= SUNLIT_FRACTION
        sun_margin[i] = frac - SUNLIT_FRACTION
        g = body_row(eph, i, 3)
        az, el = azel((g[0] - o[0], g[1] - o[1], g[2] - o[2]))
        h = hz(az)
        earth[i] = el > h
        earth_margin[i] = el - h
    return sun, earth, sun_margin, earth_margin


def states_vector(lat, lon, h0_m, mask, az_step, eph):
    east, north, up = (np.array(v) for v in frame(lat, lon))
    r = R_KM + (h0_m + OBS_M) / 1000
    o = up * r
    rows = eph.copy()
    rows[-1] = eph[-2] + (eph[-1] - eph[-2]) * 1.0
    m = np.asarray(mask, np.float64)
    m1 = np.roll(m, -1)

    def el_hz(v):
        e, nn, u = v @ east, v @ north, v @ up
        az = np.degrees(np.arctan2(e, nn))
        az = np.where(az < 0, az + 360, az)
        el = np.degrees(np.arctan2(u, np.hypot(e, nn)))
        x = np.mod(np.mod(az, 360) + 360, 360) / az_step
        fl = np.floor(x)
        k = fl.astype(np.int64) % m.size
        return el, m[k] + (m1[k] - m[k]) * (x - fl)

    el, h = el_hz(rows[:, 0:3] - o)
    y = (h - el) / SUN_R_DEG
    yc = np.clip(y, -1, 1)
    frac = np.where(y <= -1, 1.0, np.where(y >= 1, 0.0, (np.arccos(yc) - yc * np.sqrt(1 - yc * yc)) / np.pi))
    el2, h2 = el_hz(rows[:, 3:6] - o)
    return frac >= SUNLIT_FRACTION, el2 > h2


# ---------------------------------------------------------------- runs
def runs_of(flags):
    """Maximal runs of True as [start, end) with clipping flags, by an explicit state machine."""
    out, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flags)))
    n = len(flags)
    return [dict(start_i=a, end_i=b, duration_h=b - a, clipped_start=a == 0, clipped_end=b == n) for a, b in out]


def run_stats(flags):
    rs = runs_of(flags)
    durs = [r["duration_h"] for r in rs]
    comp = [r["duration_h"] for r in rs if not (r["clipped_start"] or r["clipped_end"])]
    return dict(count=len(rs), total_h=sum(durs), mean_h=(sum(durs) / len(durs)) if durs else None,
                longest_h=max(durs) if durs else 0, complete_count=len(comp),
                complete_mean_h=(sum(comp) / len(comp)) if comp else None,
                complete_longest_h=max(comp) if comp else 0,
                clipped_runs=[r for r in rs if r["clipped_start"] or r["clipped_end"]]), rs


def utc(i):
    return (START + timedelta(hours=int(i))).strftime("%Y-%m-%dT%H:%M:%SZ")


def windows_from(flags):
    vis = runs_of(flags)
    gaps = runs_of(~np.asarray(flags))
    top = sorted(gaps, key=lambda r: (-r["duration_h"], r["start_i"]))[:10]

    def rec(r):
        return dict(start_utc=utc(r["start_i"]), end_utc=utc(r["end_i"]), duration_h=r["duration_h"],
                    clipped_start=r["clipped_start"], clipped_end=r["clipped_end"])
    return dict(visible=[rec(r) for r in vis], longest_gaps=[rec(r) for r in top],
                visible_hours=int(sum(r["duration_h"] for r in vis)))


# ---------------------------------------------------------------- per-site
def compute_site(sid, site, eph, stations):
    hz = read_json(WEB / f"horizon/{sid}.json")
    assert hz["id"] == sid and hz["lat"] == site["lat"] and hz["lon"] == site["lon"], sid
    assert hz["obs_height_m"] == 2 and len(hz["mask"]) * hz["az_step_deg"] == 360 and not hz.get("mock")
    t0 = time.perf_counter()
    sun, earth, sm, em = states_scalar(site["lat"], site["lon"], hz["h0_m"], hz["mask"], hz["az_step_deg"], eph)
    t1 = time.perf_counter()
    vs, ve = states_vector(site["lat"], site["lon"], hz["h0_m"], hz["mask"], hz["az_step_deg"], eph)
    scalar_vs_vector = dict(sun_bits_differ=int((vs != sun).sum()), earth_bits_differ=int((ve != earth).sum()))
    both = sun & earth
    dark_s, _ = run_stats(~sun)
    noe_s, _ = run_stats(~earth)
    sun_s, _ = run_stats(sun)
    link = {k: earth & stations[k] for k in STATION_IDS}
    nlink = sum(link[k].astype(np.int64) for k in STATION_IDS)
    mine = dict(id=sid, lat=site["lat"], lon=site["lon"],
                window=dict(start_utc="2026-01-01T00:00:00Z", end_utc="2031-01-01T00:00:00Z", step_h=1, n=N),
                sunlit_h=int(sun.sum()), earth_visible_h=int(earth.sum()), both_h=int(both.sum()),
                dark_runs=dark_s, no_earth_runs=noe_s, sunlit_runs=sun_s,
                station_link_h=dict(kdsa_h=int(link["KDSA"].sum()), at_least_1_h=int((nlink >= 1).sum()),
                                    at_least_2_h=int((nlink >= 2).sum())))
    extra = dict(
        per_station_link_h={k: int(link[k].sum()) for k in STATION_IDS},
        per_station_available_h={k: int(stations[k].sum()) for k in STATION_IDS},
        link_hours_while_dark=int(((nlink >= 1) & ~sun).sum()),
        min_abs_sun_margin=float(np.min(np.abs(sm))), min_abs_earth_margin_deg=float(np.min(np.abs(em))),
        scalar_vs_vector=scalar_vs_vector, scalar_seconds=round(t1 - t0, 2),
        identities=dict(dark_plus_sun=dark_s["total_h"] + sun_s["total_h"] == N,
                        noearth_plus_earth=noe_s["total_h"] + mine["earth_visible_h"] == N,
                        kdsa_le_1=mine["station_link_h"]["kdsa_h"] <= mine["station_link_h"]["at_least_1_h"] <= mine["earth_visible_h"],
                        two_le_1=mine["station_link_h"]["at_least_2_h"] <= mine["station_link_h"]["at_least_1_h"]))
    return mine, extra, sun, earth, hz


def num_diff(a, b):
    if a is None or b is None:
        return None if (a is None and b is None) else "null-mismatch"
    return abs(float(a) - float(b))


def compare_z1(mine, pub):
    rows = []

    def add(field, m, p, kind, crit):
        if kind == "list":
            ok = m == p
            rows.append(dict(field=field, mine=m, published=p, diff=0 if ok else "differs", criterion=crit, pass_=ok))
            return
        d = num_diff(m, p)
        if d == "null-mismatch":
            ok = False
        elif d is None:
            ok = True
        elif kind == "exact":
            ok = d == 0
        elif kind == "hours":
            ok = d <= 1
        else:
            ok = d <= 0.1
        rows.append(dict(field=field, mine=m, published=p, diff=d, criterion=crit, pass_=ok))

    add("lat", mine["lat"], pub["lat"], "exact", "exact")
    add("lon", mine["lon"], pub["lon"], "exact", "exact")
    add("window", mine["window"], pub["window"], "list", "exact")
    for f in ["sunlit_h", "earth_visible_h", "both_h"]:
        add(f, mine[f], pub[f], "hours", "<= 1 h (also exact reported)")
    for f, lab in [("sunlit_h", "sun_frac"), ("earth_visible_h", "earth_frac"), ("both_h", "both_frac")]:
        add(lab + " (pp)", mine[f] / N * 100, pub[f] / N * 100, "pp", "<= 0.1 pp")
    for g in ["dark_runs", "no_earth_runs", "sunlit_runs"]:
        for f in RUN_FIELDS:
            m, p = mine[g][f], pub[g][f]
            if f == "clipped_runs":
                add(f"{g}.{f}", m, p, "list", "exact (start_i, end_i, duration_h, flags)")
            elif f in ("count", "complete_count"):
                add(f"{g}.{f}", m, p, "exact", "exact (integer count)")
            else:
                add(f"{g}.{f}", m, p, "hours", "<= 1 h; null must match null")
    for f in ["kdsa_h", "at_least_1_h", "at_least_2_h"]:
        add(f"station_link_h.{f}", mine["station_link_h"][f], pub["station_link_h"][f], "exact", "exact (station-hour count)")
    return rows


def compare_metrics(sid, sun, earth, dark_longest):
    m = read_json(WEB / f"metrics/{sid}.json")
    mine = dict(sun_frac=int(sun.sum()) / N, earth_frac=int(earth.sum()) / N, both_frac=int((sun & earth).sum()) / N,
                longest_dark_h=dark_longest)
    return [dict(field=k, mine=mine[k], published=m[k], exact=mine[k] == m[k]) for k in mine]


def compare_windows(sid, sun, earth):
    w = read_json(WEB / f"windows/{sid}.json")
    out = []
    for body, flags in (("sun", sun), ("earth", earth)):
        mw = windows_from(flags)
        for f in ("visible", "longest_gaps", "visible_hours"):
            out.append(dict(field=f"{body}.{f}", n_mine=len(mw[f]) if isinstance(mw[f], list) else mw[f],
                            n_published=len(w[body][f]) if isinstance(w[body][f], list) else w[body][f],
                            exact=mw[f] == w[body][f]))
    return out, w


def run(all_sites=True):
    sites = {s["id"]: s for s in read_json(WEB / "sites.json")}
    st = read_json(WEB / "korea/stations.json")
    assert st["start"] == "2026-01-01T00:00:00Z" and st["n"] == N and st["step_h"] == 1 and st["min_el_deg"] == 10
    assert [s["id"] for s in st["stations"]] == STATION_IDS
    stations = {s["id"]: decode_station_bits(s["bits_b64"]) for s in st["stations"]}
    eph = load_ephem()
    ids = list(SELECTED) + ([s for s in sites if s not in SELECTED] if all_sites else [])
    res = dict(checker="Soyun Jeong", date="2026-11-15", producer="Jiyong Sung (PR #80)", n_hours=N,
               selected=SELECTED, inputs={}, sites={})
    for p in [WEB / "sites.json", WEB / "ephem.bin", WEB / "ephem.json", WEB / "korea/stations.json", ROOT / "web/js/core.js"]:
        res["inputs"][p.name] = file_hashes(p)
    res["station_available_h"] = {k: int(v.sum()) for k, v in stations.items()}
    res["station_frac_visible_published"] = {s["id"]: s["frac_visible"] for s in st["stations"]}
    for sid in ids:
        mine, extra, sun, earth, hz = compute_site(sid, sites[sid], eph, stations)
        pub = read_json(WEB / f"detail/time_stats/{sid}.json")
        z1 = compare_z1(mine, pub)
        met = compare_metrics(sid, sun, earth, mine["dark_runs"]["longest_h"])
        win, w = compare_windows(sid, sun, earth)
        # windows <-> Z1 overlaps defined on the same quantity
        overlap = dict(
            sun_visible_hours=w["sun"]["visible_hours"] == pub["sunlit_h"],
            earth_visible_hours=w["earth"]["visible_hours"] == pub["earth_visible_h"],
            sun_interval_count=len(w["sun"]["visible"]) == pub["sunlit_runs"]["count"],
            sun_longest=max([x["duration_h"] for x in w["sun"]["visible"]], default=0) == pub["sunlit_runs"]["longest_h"],
            dark_longest=max([x["duration_h"] for x in w["sun"]["longest_gaps"]], default=0) == pub["dark_runs"]["longest_h"],
            noearth_longest=max([x["duration_h"] for x in w["earth"]["longest_gaps"]], default=0) == pub["no_earth_runs"]["longest_h"],
            metrics_longest_dark=read_json(WEB / f"metrics/{sid}.json")["longest_dark_h"] == pub["dark_runs"]["longest_h"])
        src = pub["source"]
        hz_rec = file_hashes(WEB / f"horizon/{sid}.json")
        hashes = dict(horizon=hz_rec, published_horizon_sha256=src["horizon_sha256"],
                      horizon_matches=src["horizon_sha256"] in (hz_rec["sha256_raw"], hz_rec.get("sha256_lf")),
                      ephem_matches=src["ephem_sha256"] == res["inputs"]["ephem.bin"]["sha256_raw"],
                      ephem_meta_matches=src["ephem_meta_sha256"] in (res["inputs"]["ephem.json"]["sha256_raw"], res["inputs"]["ephem.json"]["sha256_lf"]),
                      sites_matches=src["sites_sha256"] in (res["inputs"]["sites.json"]["sha256_raw"], res["inputs"]["sites.json"]["sha256_lf"]),
                      stations_matches=src["stations_sha256"] in (res["inputs"]["stations.json"]["sha256_raw"], res["inputs"]["stations.json"]["sha256_lf"]),
                      core_matches=src["core_sha256"] in (res["inputs"]["core.js"]["sha256_raw"], res["inputs"]["core.js"]["sha256_lf"]),
                      time_stats=file_hashes(WEB / f"detail/time_stats/{sid}.json"),
                      metrics=file_hashes(WEB / f"metrics/{sid}.json"), windows=file_hashes(WEB / f"windows/{sid}.json"))
        res["sites"][sid] = dict(selected=sid in SELECTED, h0_m=hz["h0_m"], mine=mine, extra=extra, z1=z1,
                                 z1_all_pass=all(r["pass_"] for r in z1),
                                 z1_all_exact=all(r["diff"] in (0, None) for r in z1),
                                 metrics=met, metrics_exact=all(r["exact"] for r in met),
                                 windows=win, windows_exact=all(r["exact"] for r in win),
                                 windows_z1_overlap=overlap, overlap_exact=all(overlap.values()), hashes=hashes)
        s = res["sites"][sid]
        print(f"{sid:26s} Z1 pass={s['z1_all_pass']} exact={s['z1_all_exact']} metrics={s['metrics_exact']} "
              f"windows={s['windows_exact']} overlap={s['overlap_exact']} sv={extra['scalar_vs_vector']} "
              f"margins sun {extra['min_abs_sun_margin']:.2e} earth {extra['min_abs_earth_margin_deg']:.2e} ({extra['scalar_seconds']} s)",
              flush=True)
    OUT_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return res


# ---------------------------------------------------------------- report
def fmt(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, float):
        return f"{v:.10g}"
    if isinstance(v, list):
        if not v:
            return "[]"
        return "; ".join(f"[{r['start_i']},{r['end_i']}) {r['duration_h']} h {'S' if r['clipped_start'] else ''}{'E' if r['clipped_end'] else ''}" for r in v)
    if isinstance(v, dict):
        return ", ".join(f"{k}={v[k]}" for k in v)
    return str(v)


def report():
    res = read_json(OUT_JSON)
    sel = [k for k, v in res["sites"].items() if v["selected"]]
    allz = [r for s in res["sites"].values() for r in s["z1"]]
    selz = [r for k in sel for r in res["sites"][k]["z1"]]

    def stats(rows, pred):
        d = [r["diff"] for r in rows if pred(r["field"]) and isinstance(r["diff"], (int, float))]
        return (max(d), float(np.median(d)), len(d)) if d else (None, None, 0)
    L = []
    L.append("# Z1 time statistics — independent three-site verification (Soyun Jeong)\n")
    L.append("Producer: Jiyong Sung (PR #80). Checker: Soyun Jeong, 2026-11-15. Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.")
    L.append("Script: `pipeline/verify_z1_independent_soyun.py` (own code; no producer or earlier-checker module imported or run). Full results: `docs/z1_independent_soyun.json`. **No production file was changed.**\n")
    L.append("## Summary\n")
    nsel_fail = sum(not r["pass_"] for r in selz)
    nsel_nonexact = sum(r["diff"] not in (0, None) for r in selz)
    fpp = stats(selz, lambda f: f.endswith("(pp)"))
    fh = stats(selz, lambda f: not f.endswith("(pp)") and f not in ("lat", "lon", "window") and "count" not in f and "clipped" not in f and "station" not in f)
    L.append("| Item | Result |\n|---|---|")
    L.append(f"| Sites (formal scope) | {', '.join(sel)} |")
    L.append(f"| Hourly cells per site | {res['n_hours']:,} (2026-01-01T00Z – 2030-12-31T23Z, each cell [i, i+1)); {len(sel) * res['n_hours']:,} for the three sites |")
    L.append(f"| Z1 fields compared (3 sites) | {len(selz)} ({len(selz) // len(sel)} per site) |")
    L.append(f"| Fields failing the criterion | **{nsel_fail}** |")
    L.append(f"| Fields not exactly equal | **{nsel_nonexact}** |")
    L.append(f"| Max / median fraction difference | {fpp[0]} / {fpp[1]} pp over {fpp[2]} values (criterion ≤ 0.1 pp) |")
    L.append(f"| Max / median duration difference | {fh[0]} / {fh[1]} h over {fh[2]} values (criterion ≤ 1 h) |")
    L.append("| Counts, station hours, clipping metadata | " + ("all exact" if all(r["pass_"] for r in selz if "count" in r["field"] or "clipped" in r["field"] or "station" in r["field"]) else "**discrepancies, see tables**") + " |")
    L.append("| metrics/ cross-check (sun/earth/both frac, longest dark) | " + ", ".join(f"{k}: {'exact' if res['sites'][k]['metrics_exact'] else 'DIFFERS'}" for k in sel) + " |")
    L.append("| windows/ cross-check (visible intervals, top-10 gaps, visible hours, clipping) | " + ", ".join(f"{k}: {'exact' if res['sites'][k]['windows_exact'] else 'DIFFERS'}" for k in sel) + " |")
    n_all = len(res["sites"])
    L.append(f"| Supplement: all {n_all} sites | Z1 fields exact at {sum(s['z1_all_exact'] for s in res['sites'].values())}/{n_all}; "
             f"metrics exact {sum(s['metrics_exact'] for s in res['sites'].values())}/{n_all}; windows exact {sum(s['windows_exact'] for s in res['sites'].values())}/{n_all}; "
             f"failing fields {sum(not r['pass_'] for r in allz)} of {len(allz)} |")
    L.append("")
    L.append("## Site selection\n")
    L.append("PR #82 (Minchul) checked APOLLO17, CHANGE4 and SHACKLETON_RIM; the integrator sampled CHANGE6 and ARTEMIS_HAWORTH. "
             "The task suggested APOLLO11, ARTEMIS_HAWORTH and CHANGE6 and allowed a stronger edge-case selection. Grouping the 33 published files by which run groups are clipped at which edge gives five patterns:\n")
    L.append("| Clipping pattern (dark / no-Earth / sunlit) | Sites | Covered by PR #82 | This check |\n|---|---|---|---|")
    L.append("| none / none / start + end (two runs) | 17 (incl. APOLLO11) | APOLLO17, SHACKLETON_RIM | — |")
    L.append("| end / none / start | 12 (incl. HAWORTH, MALAPERT) | — | ARTEMIS_MALAPERT |")
    L.append("| start + end (two runs) / none / none | 2 (CABEUS_B, IM3_REINER_GAMMA) | — | ARTEMIS_CABEUS_B |")
    L.append("| start + end / whole period / none | 1 (CHANGE6) | — | CHANGE6 |")
    L.append("| start / whole period / end | 1 (CHANGE4) | CHANGE4 | — |\n")
    L.append("APOLLO11 was replaced because it has the same pattern and the same Earth-always case as PR #82's APOLLO17. ARTEMIS_HAWORTH was replaced by ARTEMIS_MALAPERT, which has Haworth's clipping pattern *and* is a polar site where Earth is always visible "
             "(null no-Earth mean), and whose end-clipped dark run (365 h) is shorter than its longest complete dark run (415 h), testing that clipped and complete maxima are kept apart. "
             "CHANGE6 was kept although the integrator sampled it, because it is the only site of its pattern. With PR #82, all five patterns are now independently checked.\n")
    L.append("| Site | Why |\n|---|---|")
    for k in sel:
        L.append(f"| {k} | {res['selected'][k]} |")
    L.append("")
    L.append("Together they cover: Earth always / intermittent / never visible; no-Earth runs absent, 67 complete runs, and one whole-period run clipped at both ends; "
             "a clipped sunlit start with a clipped dark end, dark runs clipped at both edges, and no clipped sunlit run; station counts limited only by station availability, partial, and zero.\n")
    L.append("## Method\n")
    L.append("- **Inputs read directly**, hashes below: `sites.json` (lat, lon), `ephem.bin` float32 → float64 and `ephem.json` (start, step, n, columns), `horizon/<ID>.json` (`h0_m`, 720-bin mask, 0.5° step, observer 2 m), `korea/stations.json` (four 10° station bit arrays).")
    L.append("- **Geometry (core.js definitions, own code).** Local frame east/north/up from lat, lon; observer at (R + (h0 + 2 m)/1000) km along up, R = 1737.4 km; Sun and Earth vectors minus observer (topocentric); "
             "azimuth atan2(E, N) in 0–360°, elevation atan2(U, √(E²+N²)); mask linearly interpolated between 0.5° bins with wrap. Ephemeris row at integer hour i is row i; the last hour uses rows n−2, n−1 with t = 1, as `bodyVec`.")
    L.append("- **Sunlit**: visible fraction of a 0.2666° disc above the locally flat mask line, (acos y − y√(1−y²))/π with y = (mask − el)/0.2666, sunlit when ≥ 0.5. **Earth visible**: Earth-centre elevation strictly above the mask. **Both** = sunlit AND Earth visible. Hour i represents [i, i+1).")
    L.append("- **Two evaluations** of every hourly state: a literal per-hour scalar loop (Python `math`) and a NumPy version. They must agree bit for bit; the smallest distance of any hour from either threshold is reported, to show no hour is near a tie where libm rounding could flip it.")
    L.append("- **Runs**: an explicit state machine finds maximal runs of dark (not sunlit), no-Earth and sunlit hours as [start, end). A run is clipped at the start if it begins at hour 0 and at the end if it ends at 43,824. "
             "`count`, `total_h`, `mean_h`, `longest_h` use all observed runs; `complete_*` exclude every clipped run; means are null with no runs and `longest_h` is 0. A clipped run's length is only the observed part; nothing is extrapolated.")
    L.append("- **Stations**: base64-decoded bytes, hour k = bit (k mod 8) of byte ⌊k/8⌋ (LSB first), decoded with explicit shifts and cross-checked against `numpy.unpackbits(bitorder='little')`. A link hour = Earth visible AND station bit (Moon ≥ 10° at the station); sunlight is **not** required. "
             "Counted: KDSA linked, ≥ 1 of 4 stations, ≥ 2 of 4. This is geometric line of sight to an available station, not guaranteed radio communication.")
    L.append("- **Criteria**: fractions ≤ 0.1 pp; durations ≤ 1 h; integer run counts, station-hour counts and the clipped-run lists exact. Every difference is reported unrounded.")
    L.append("- **Cross-checks**: `metrics/<ID>.json` (sun_frac, earth_frac, both_frac, longest_dark_h) and `windows/<ID>.json` (every Sun/Earth visible interval with UTC edges and clipping flags, top-10 gaps sorted by duration then start, visible hours) are rebuilt from my own hourly states and compared for exact equality.\n")
    for k in sel:
        s = res["sites"][k]
        L.append(f"## {k}\n")
        L.append(f"h0 = {s['h0_m']} m. Scalar vs NumPy state bits differing: Sun {s['extra']['scalar_vs_vector']['sun_bits_differ']}, Earth {s['extra']['scalar_vs_vector']['earth_bits_differ']}. "
                 f"Closest hour to a threshold: Sun visible fraction {s['extra']['min_abs_sun_margin']:.3g} from 0.5; Earth centre {s['extra']['min_abs_earth_margin_deg']:.3g}° from the mask.\n")
        L.append("| Field | Mine | Published | |Δ| | Criterion | Result |\n|---|---|---|---|---|---|")
        for r in s["z1"]:
            L.append(f"| `{r['field']}` | {fmt(r['mine'])} | {fmt(r['published'])} | {fmt(r['diff'])} | {r['criterion']} | {'PASS' if r['pass_'] else '**FAIL**'} |")
        L.append("")
        e = s["extra"]
        L.append(f"Per-station link hours (mine): " + ", ".join(f"{a} {b:,}" for a, b in e["per_station_link_h"].items()) +
                 f". Link hours (≥ 1 station) while the site is dark: {e['link_hours_while_dark']:,} — counted, as sunlight is not required.\n")
        L.append("Cross-checks:\n")
        L.append("| Product | Field | Mine | Published | Exact |\n|---|---|---|---|---|")
        for r in s["metrics"]:
            L.append(f"| metrics | `{r['field']}` | {fmt(r['mine'])} | {fmt(r['published'])} | {'yes' if r['exact'] else '**no**'} |")
        for r in s["windows"]:
            L.append(f"| windows | `{r['field']}` | {r['n_mine']} | {r['n_published']} | {'yes' if r['exact'] else '**no**'} |")
        L.append("")
        L.append("Same-quantity overlap between the published products (windows/metrics vs Z1): " +
                 ", ".join(f"{a} {'=' if b else '≠'}" for a, b in s["windows_z1_overlap"].items()) + ".\n")
    L.append("## Clipped runs (three sites)\n")
    L.append("| Site | Group | Clipped runs (mine) | Published | complete_count mine / pub | complete_mean_h mine / pub |\n|---|---|---|---|---|---|")
    for k in sel:
        m = res["sites"][k]["mine"]
        pub = {r["field"]: r["published"] for r in res["sites"][k]["z1"]}
        for g in ["dark_runs", "no_earth_runs", "sunlit_runs"]:
            L.append(f"| {k} | {g} | {fmt(m[g]['clipped_runs'])} | {fmt(pub[g + '.clipped_runs'])} | {m[g]['complete_count']} / {pub[g + '.complete_count']} | {fmt(m[g]['complete_mean_h'])} / {fmt(pub[g + '.complete_mean_h'])} |")
    L.append("\nS = clipped at the period start (hour 0), E = clipped at the end (exclusive hour 43,824). Clipped durations are observed parts only.\n")
    L.append(f"## Supplement: all {n_all} sites with the same code\n")
    L.append("Not part of the three-site requirement; recorded because the same code runs in seconds.\n")
    L.append("| Site | Z1 fields | Not exact | Failing | metrics | windows | Scalar≠NumPy bits | Min Sun margin | Min Earth margin (°) |\n|---|---|---|---|---|---|---|---|---|")
    for k, s in res["sites"].items():
        L.append(f"| {k}{' (selected)' if s['selected'] else ''} | {len(s['z1'])} | {sum(r['diff'] not in (0, None) for r in s['z1'])} | {sum(not r['pass_'] for r in s['z1'])} | "
                 f"{'exact' if s['metrics_exact'] else 'DIFFERS'} | {'exact' if s['windows_exact'] else 'DIFFERS'} | "
                 f"{s['extra']['scalar_vs_vector']['sun_bits_differ'] + s['extra']['scalar_vs_vector']['earth_bits_differ']} | {s['extra']['min_abs_sun_margin']:.2g} | {s['extra']['min_abs_earth_margin_deg']:.2g} |")
    L.append("")
    L.append("## Input hashes\n")
    L.append("| File | Bytes | SHA-256 (raw bytes) | SHA-256 (CRLF→LF) |\n|---|---|---|---|")
    for v in res["inputs"].values():
        L.append(f"| `{v['path']}` | {v['bytes']:,} | `{v['sha256_raw']}` | `{v.get('sha256_lf', '—')}` |")
    for k in sel:
        h = res["sites"][k]["hashes"]
        for key in ("horizon", "time_stats", "metrics", "windows"):
            v = h[key]
            L.append(f"| `{v['path']}` | {v['bytes']:,} | `{v['sha256_raw']}` | `{v.get('sha256_lf', '—')}` |")
    L.append("")
    L.append("Source hashes recorded inside each published Z1 file vs the current inputs (match on raw or LF-normalised bytes): " +
             "; ".join(f"{k}: " + ", ".join(f"{a.replace('_matches', '')} {'✓' if res['sites'][k]['hashes'][a] else '✗'}" for a in
                                          ("horizon_matches", "ephem_matches", "ephem_meta_matches", "sites_matches", "stations_matches", "core_matches")) for k in sel) + ".\n")
    L.append("## Limits\n")
    L.append("- The ephemeris, horizons and station bit arrays are taken as given inputs; they were not regenerated here (they have their own ledger rows: ephem, horizon task A, korea task C).")
    L.append("- core.js runs in JavaScript (V8); this check uses Python/NumPy double precision. The reported threshold margins show how far the closest hour is from a tie; at that distance a 1-ulp libm difference cannot flip a state.")
    L.append("- Station 'link' is geometric: Earth visible from the site AND Moon ≥ 10° at the station. It does not model antenna scheduling, link budget or terrain at the station.")
    L.append("- Clipped runs are censored at 2026-01-01T00Z and 2031-01-01T00Z; their physical durations are unknown and are not inferred.")
    L.append("- Formal scope is three sites; the 33-site supplement uses the same code and is not a second independent implementation.")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote", OUT_MD)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run(all_sites="--selected-only" not in sys.argv)
    elif cmd == "report":
        report()
    else:
        sys.exit(__doc__)
