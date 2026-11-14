"""Card 14 add-on (docs only): 1 h vs 10 min time-step sensitivity of the site metrics, 2026-2030.

Nothing in production is changed: web/data/ephem.bin, web/data/metrics/, core.js and the engines are
only read. The 10-minute ephemeris is regenerated with card 1's own `pipeline/ephem.py`
`Ephemeris.vectors()` (same NAIF kernels, MOON_ME_DE421, Skyfield observe().apparent()) and stored
under data/processed/ (git-ignored).

    python pipeline/timestep_sensitivity.py ephem   # 10-min ephemeris 2026-01-01T00Z .. 2031-01-01T00Z (excl.), resumable
    python pipeline/timestep_sensitivity.py run     # metrics + sunset/Earthset comparison -> docs/timestep_sensitivity.json

The metric definitions are a line-by-line Python port of web/js/core.js (sunVisibleFraction, sunlit,
earthVisible, horizonAt, metrics, untilFlip). Methods compared:
  H1   production: hourly ephemeris rows (float32, as ephem.bin), hourly samples (core.js metrics)
  T10  reference: 10-min ephemeris, 10-min samples
  I10  hourly ephemeris linearly interpolated (core.js bodyVec) to the 10-min samples
       -> T10 vs I10 = ephemeris interpolation error; I10 vs H1 = hourly sampling (discretisation) error
Sunset / Earthset (50 random times x 6 sites):
  M1   core.js untilSunset / untilEarthset exactly (hourly scan + 7 bisections, hourly ephemeris)
  M2   hourly ephemeris, 10-min scan + 30 bisections        (M1 - M2 = transition-estimate error)
  M3   10-min ephemeris, 10-min scan + 30 bisections        (M2 - M3 = hourly-ephemeris interpolation error)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ephem as card1  # noqa: E402  (card 1 pipeline, unchanged)

ROOT = card1.ROOT
SITES = ["SHACKLETON_RIM", "ARTEMIS_HAWORTH", "ARTEMIS_MALAPERT", "APOLLO17", "CHANGE4", "SLIM"]
STEP_MIN = 10
K = 60 // STEP_MIN                      # 6 samples per hour
N_HOURS = 43824                         # 2026-01-01T00Z .. 2031-01-01T00Z exclusive
N10 = N_HOURS * K                       # 262,944
OUT10 = ROOT / "data" / "processed" / "ephem_2026-2030_10min_f64.npy"
STATE10 = OUT10.with_suffix(".state.json")
SUN_R = 0.2666
R_MOON_KM = 1737.4
SEED, N_TIMES = 20260101, 50


# =========================================================================== 10-minute ephemeris
def cmd_ephem(a):
    eng = card1.Ephemeris()
    man = eng.manifest()
    key = {"start": card1.EPOCH.isoformat(), "step_min": STEP_MIN, "n": N10, "kernels": man["kernels"]}
    st = json.loads(STATE10.read_text()) if STATE10.exists() else {}
    ok = st.get("key") == key and OUT10.exists()
    done = st.get("done", 0) if ok else 0
    arr = np.lib.format.open_memmap(OUT10, mode="r+" if ok else "w+", dtype="<f8", shape=(N10, 6))
    for i in range(done, N10, 8192):
        j = min(i + 8192, N10)
        v = eng.vectors([card1.EPOCH + timedelta(minutes=STEP_MIN * k) for k in range(i, j)])
        if not np.all(np.isfinite(v)):
            raise ValueError(f"non-finite rows {i}:{j}")
        arr[i:j] = v
        arr.flush()
        STATE10.write_text(json.dumps({"key": key, "done": j}))
        if (j // 8192) % 8 == 0 or j == N10:
            print(f"  {j}/{N10}", flush=True)
    print(f"10-min ephemeris -> {OUT10} ({OUT10.stat().st_size / 1e6:.1f} MB)")
    return 0


# =========================================================================== core.js port
class Site:
    def __init__(self, site, hz):
        la, lo = math.radians(site["lat"]), math.radians(site["lon"])
        sl, cl, so, co = math.sin(la), math.cos(la), math.sin(lo), math.cos(lo)
        self.east = np.array([-so, co, 0.0])
        self.north = np.array([-sl * co, -sl * so, cl])
        self.up = np.array([cl * co, cl * so, sl])
        self.obs = self.up * (R_MOON_KM + (hz["h0_m"] + 2) / 1000)
        self.mask = np.asarray(hz["mask"], np.float64)
        self.step = float(hz["az_step_deg"])
        self.id = site["id"]

    def _azel(self, v):
        e, n, u = v @ self.east, v @ self.north, v @ self.up
        az = np.degrees(np.arctan2(e, n))
        az = np.where(az < 0, az + 360, az)
        return az, np.degrees(np.arctan2(u, np.hypot(e, n)))

    def horizon_at(self, az):
        nb = self.mask.size
        x = (((az % 360) + 360) % 360) / self.step
        k = np.floor(x).astype(int) % nb
        t = x - np.floor(x)
        return self.mask[k] + (self.mask[(k + 1) % nb] - self.mask[k]) * t

    def sun_fraction(self, vec):
        az, el = self._azel(vec[..., 0:3] - self.obs)
        y = (self.horizon_at(az) - el) / SUN_R
        yc = np.clip(y, -1, 1)
        f = (np.arccos(yc) - yc * np.sqrt(1 - yc * yc)) / np.pi
        return np.where(y <= -1, 1.0, np.where(y >= 1, 0.0, f))

    def earth_margin(self, vec):
        az, el = self._azel(vec[..., 3:6] - self.obs)
        return el - self.horizon_at(az)


def metrics_from(site, vec, dt_h):
    """core.js metrics() over the given samples; longest run converted to hours with dt_h."""
    sun = site.sun_fraction(vec) >= 0.5
    earth = site.earth_margin(vec) > 0
    dark = ~sun
    # longest run of consecutive True in `dark`
    d = np.diff(np.concatenate([[0], dark.astype(np.int8), [0]]))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    longest = int((ends - starts).max()) if starts.size else 0
    n = sun.size
    return {"n": n, "n_sun": int(sun.sum()), "n_earth": int(earth.sum()), "n_both": int((sun & earth).sum()),
            "sun_frac": float(sun.mean()), "earth_frac": float(earth.mean()), "both_frac": float((sun & earth).mean()),
            "longest_dark_samples": longest, "longest_dark_h": longest * dt_h}


class Ephem:
    """Rows at a fixed step; vec(x) = linear interpolation at fractional row index (core.js bodyVec, clamped)."""

    def __init__(self, rows, step_h):
        self.rows, self.step_h, self.n = np.asarray(rows, np.float64), step_h, len(rows)

    def at_hour(self, t_h):
        x = min(max(t_h / self.step_h, 0.0), self.n - 1)
        k = min(int(math.floor(x)), max(self.n - 2, 0))
        f = x - k
        a, b = self.rows[k], self.rows[min(k + 1, self.n - 1)]
        return a + (b - a) * f


def until_flip_core(site, eph, i, margin, n_hours, hourly_vis=None):
    """core.js untilFlip with the hourly ephemeris: hourly scan from floor(i)+1, 7 bisections, midpoint.
    hourly_vis (optional) = precomputed `margin > 0` at whole hours t = 0..n-1 (same values as the scalar path)."""
    now = margin(site, eph.at_hour(i)) > 0
    a = i
    t = math.floor(i) + 1
    if hourly_vis is not None:                  # jump straight to the first whole hour whose state differs
        flip = np.flatnonzero(hourly_vis[t:n_hours] != now)
        if not flip.size:
            return None
        t = t + int(flip[0])
        a = i if t == math.floor(i) + 1 else t - 1
    while t <= n_hours - 1:
        if (margin(site, eph.at_hour(t)) > 0) != now:
            b = t
            for _ in range(7):
                c = (a + b) / 2
                if (margin(site, eph.at_hour(c)) > 0) == now:
                    a = c
                else:
                    b = c
            return (a + b) / 2 - i
        a = t
        t += 1
    return None


def until_flip_fine(site, eph, i, margin, grid_margin, grid_dt_h, last_h, iters=30):
    """Scan the precomputed margin on a fine grid (10 min) after i, then bisect with interpolation."""
    now = margin(site, eph.at_hour(i)) > 0
    j0 = int(math.floor(i / grid_dt_h)) + 1
    jmax = int(round(last_h / grid_dt_h))
    vis = grid_margin[j0:jmax + 1] > 0
    flip = np.flatnonzero(vis != now)
    if not flip.size:
        return None
    j = j0 + int(flip[0])
    a, b = max(i, (j - 1) * grid_dt_h), j * grid_dt_h
    for _ in range(iters):
        c = (a + b) / 2
        if (margin(site, eph.at_hour(c)) > 0) == now:
            a = c
        else:
            b = c
    return (a + b) / 2 - i


sun_margin = lambda s, v: float(s.sun_fraction(v)) - 0.5   # noqa: E731  core.js sunMargin
earth_margin = lambda s, v: float(s.earth_margin(v))       # noqa: E731


def until(kind, site, eph, i, finder):
    m = sun_margin if kind == "sun" else earth_margin
    if not m(site, eph.at_hour(i)) > 0:
        return 0.0                          # core.js: 0 if not visible now
    return finder(m)


def summ(x):
    x = np.asarray([v for v in x if v is not None], float)
    if not x.size:
        return {"n": 0}
    a = np.abs(x)
    return {"n": int(x.size), "max_abs": round(float(a.max()), 4), "mean_abs": round(float(a.mean()), 4),
            "p95_abs": round(float(np.percentile(a, 95)), 4), "mean_signed": round(float(x.mean()), 4)}


def cmd_run(a):
    st = json.loads(STATE10.read_text()) if STATE10.exists() else {}
    if st.get("done") != N10:
        raise SystemExit("10-min ephemeris incomplete - run `ephem` first")
    e10 = np.load(OUT10, mmap_mode="r")
    prod = np.fromfile(ROOT / "web" / "data" / "ephem.bin", dtype="<f4").reshape(-1, 6)
    meta = json.loads((ROOT / "web" / "data" / "ephem.json").read_text())
    assert prod.shape[0] == N_HOURS == meta["n"] and meta["step_h"] == 1 and not meta["mock"]
    rep = {"what": "1 h vs 10 min time-step sensitivity, 2026-01-01T00Z .. 2031-01-01T00Z (exclusive), docs only",
           "sites": SITES, "definitions": "Python port of web/js/core.js (sunlit = disc fraction >= 0.5, radius 0.2666 deg; "
                                          "Earth centre above the 720-bin mask; observer 2 m; longest dark = consecutive not-sunlit samples)"}

    # ---- A: input consistency at the whole hours
    at_h = np.asarray(e10[::K], np.float64)
    d32 = np.abs(at_h.astype(np.float32).astype(np.float64) - prod.astype(np.float64))
    d64 = np.abs(at_h - prod.astype(np.float64))
    rep["ephemeris"] = {
        "production": {"file": "web/data/ephem.bin", "rows": N_HOURS, "step_h": 1, "dtype": "float32",
                       "sha256": hashlib.sha256((ROOT / "web/data/ephem.bin").read_bytes()).hexdigest(),
                       "source": meta.get("source")},
        "ten_min": {"file": str(OUT10.relative_to(ROOT)), "rows": N10, "step_min": STEP_MIN, "dtype": "float64",
                    "generator": "pipeline/ephem.py Ephemeris.vectors() (card 1, unchanged)",
                    "kernels": st["key"]["kernels"]},
        "same_hours_check": {"rows": N_HOURS,
                             "max_abs_km_after_float32_rounding": float(d32.max()),
                             "rows_bit_identical_after_float32": int((d32.max(axis=1) == 0).sum()),
                             "max_abs_km_float64_vs_float32_file": float(d64.max()),
                             "max_rel_float64_vs_float32_file": float((d64 / np.abs(prod)).max())}}
    # 1-h interpolation error of the ephemeris itself (between hours), as core.js would use it
    hp = prod.astype(np.float64)
    fr = (np.arange(N10) % K) / K
    k0 = np.minimum(np.arange(N10) // K, N_HOURS - 1)
    k1 = np.minimum(k0 + 1, N_HOURS - 1)
    interp10 = hp[k0] + (hp[k1] - hp[k0]) * fr[:, None]            # core.js bodyVec (clamped after the last hour)
    rep["ephemeris"]["hourly_linear_interpolation_error"] = {}
    for body, sl in (("sun", slice(0, 3)), ("earth", slice(3, 6))):
        ref = np.asarray(e10[:, sl], np.float64)
        dv = interp10[:, sl] - ref
        ang = np.degrees(np.arcsin(np.clip(np.linalg.norm(np.cross(interp10[:, sl], ref), axis=1) /
                                           (np.linalg.norm(interp10[:, sl], axis=1) * np.linalg.norm(ref, axis=1)), 0, 1)))
        inner = np.arange(N10) < (N_HOURS - 1) * K + 1                   # exclude the clamped last hour
        rep["ephemeris"]["hourly_linear_interpolation_error"][body] = {
            "max_km": round(float(np.linalg.norm(dv, axis=1)[inner].max()), 3),
            "max_direction_arcsec": round(float(ang[inner].max() * 3600), 4)}

    sites = {s["id"]: s for s in json.loads((ROOT / "web/data/sites.json").read_text(encoding="utf-8"))}
    eph1 = Ephem(prod, 1.0)
    eph10 = Ephem(np.asarray(e10), 1.0 / K)
    rng = np.random.default_rng(SEED)
    times = np.sort(np.round(rng.uniform(0, N_HOURS - 1, N_TIMES) * 60) / 60)   # whole minutes, hours since T0
    rep["sunset_times"] = {"seed": SEED, "n": N_TIMES, "rule": "uniform in [0, 43823) h, rounded to the minute",
                           "hours": [round(float(t), 4) for t in times]}
    rep["metrics"], rep["sunset_earthset"] = {}, {}
    all_d = {"sun_pp": [], "earth_pp": [], "both_pp": [], "dark_h": []}
    for sid in SITES:
        hz = json.loads((ROOT / f"web/data/horizon/{sid}.json").read_text(encoding="utf-8"))
        cache = json.loads((ROOT / f"web/data/metrics/{sid}.json").read_text(encoding="utf-8"))
        s = Site(sites[sid], hz)
        h1 = metrics_from(s, hp, 1.0)
        t10 = metrics_from(s, np.asarray(e10), 1.0 / K)
        i10 = metrics_from(s, interp10, 1.0 / K)
        cache_ok = {k: {"cache": cache[k], "port": h1[k], "abs_diff": abs(cache[k] - h1[k]),
                        "cache_times_n": cache[k] * N_HOURS if k != "longest_dark_h" else None}
                    for k in ("sun_frac", "earth_frac", "both_frac", "longest_dark_h")}
        exact = all(v["abs_diff"] == 0 for v in cache_ok.values())
        close = all(v["abs_diff"] <= 1e-12 for v in cache_ok.values())
        dd = {"sun_frac_pp": (t10["sun_frac"] - h1["sun_frac"]) * 100,
              "earth_frac_pp": (t10["earth_frac"] - h1["earth_frac"]) * 100,
              "both_frac_pp": (t10["both_frac"] - h1["both_frac"]) * 100,
              "longest_dark_h": t10["longest_dark_h"] - h1["longest_dark_h"],
              "interp_only_sun_pp": (t10["sun_frac"] - i10["sun_frac"]) * 100,
              "interp_only_earth_pp": (t10["earth_frac"] - i10["earth_frac"]) * 100,
              "interp_only_dark_h": t10["longest_dark_h"] - i10["longest_dark_h"],
              "sampling_only_sun_pp": (i10["sun_frac"] - h1["sun_frac"]) * 100,
              "sampling_only_earth_pp": (i10["earth_frac"] - h1["earth_frac"]) * 100,
              "sampling_only_dark_h": i10["longest_dark_h"] - h1["longest_dark_h"]}
        all_d["sun_pp"].append(dd["sun_frac_pp"]); all_d["earth_pp"].append(dd["earth_frac_pp"])
        all_d["both_pp"].append(dd["both_frac_pp"]); all_d["dark_h"].append(dd["longest_dark_h"])
        rep["metrics"][sid] = {"lat": sites[sid]["lat"], "lon": sites[sid]["lon"], "h0_m": hz["h0_m"],
                               "H1_hourly": h1, "T10_10min": t10, "I10_interpolated_10min": i10,
                               "differences_T10_minus_H1": {k: round(v, 6) for k, v in dd.items()},
                               "metrics_cache_check": {"exact": exact, "within_1e-12": close, "fields": cache_ok}}
        # ---- sunset / Earthset
        grid1 = {"sun": s.sun_fraction(interp10) - 0.5, "earth": s.earth_margin(interp10)}
        hv = {k: grid1[k][::K] > 0 for k in grid1}         # whole hours = hourly rows exactly
        hv["sun"][-1] = sun_margin(s, eph1.at_hour(N_HOURS - 1)) > 0
        hv["earth"][-1] = earth_margin(s, eph1.at_hour(N_HOURS - 1)) > 0
        grid10 = {"sun": s.sun_fraction(np.asarray(e10)) - 0.5, "earth": s.earth_margin(np.asarray(e10))}
        last_h = N_HOURS - 1
        rows = []
        for t in times:
            r = {"t_h": round(float(t), 4)}
            for kind in ("sun", "earth"):
                m1 = until(kind, s, eph1, t, lambda m: until_flip_core(s, eph1, t, m, N_HOURS, hv[kind]))
                m2 = until(kind, s, eph1, t, lambda m: until_flip_fine(s, eph1, t, m, grid1[kind], 1 / K, last_h))
                m3 = until(kind, s, eph10, t, lambda m: until_flip_fine(s, eph10, t, m, grid10[kind], 1 / K, last_h))
                r[kind] = {"M1_core_h": m1, "M2_h": m2, "M3_ref_h": m3}
            rows.append(r)
        out = {}
        for kind in ("sun", "earth"):
            cls = {"both_zero": 0, "both_null": 0, "both_number": 0, "state_or_null_mismatch": 0}
            d13, d12, d23 = [], [], []
            for r in rows:
                m1, m2, m3 = r[kind]["M1_core_h"], r[kind]["M2_h"], r[kind]["M3_ref_h"]
                if m1 == 0 and m3 == 0:
                    cls["both_zero"] += 1
                elif m1 is None and m3 is None:
                    cls["both_null"] += 1
                elif m1 not in (None, 0) and m3 not in (None, 0):
                    cls["both_number"] += 1
                    d13.append((m1 - m3) * 60)
                    d12.append((m1 - m2) * 60)
                    d23.append((m2 - m3) * 60)
                else:
                    cls["state_or_null_mismatch"] += 1
            out[kind] = {"classes": cls, "M1_minus_M3_min": summ(d13), "M1_minus_M2_min": summ(d12),
                         "M2_minus_M3_min": summ(d23)}
        out["rows"] = rows
        rep["sunset_earthset"][sid] = out
        print(f"{sid}: cache exact={exact} | dSun {dd['sun_frac_pp']:+.4f} pp dEarth {dd['earth_frac_pp']:+.4f} pp "
              f"dDark {dd['longest_dark_h']:+.3f} h | sunset |M1-M3| max {out['sun']['M1_minus_M3_min'].get('max_abs')} min",
              flush=True)
    # ---- overall
    pool = lambda kind, key: [x for sid in SITES for x in  # noqa: E731
                              [(r[kind]["M1_core_h"], r[kind]["M2_h"], r[kind]["M3_ref_h"]) for r in rep["sunset_earthset"][sid]["rows"]]
                              if x[0] not in (None, 0) and x[2] not in (None, 0)]
    overall = {"metrics": {k: summ(v) for k, v in all_d.items()}}
    for kind in ("sun", "earth"):
        p = pool(kind, None)
        overall[f"until_{'sunset' if kind == 'sun' else 'earthset'}_min"] = {
            "M1_minus_M3": summ([(a - c) * 60 for a, b, c in p]), "M1_minus_M2": summ([(a - b) * 60 for a, b, c in p]),
            "M2_minus_M3": summ([(b - c) * 60 for a, b, c in p]),
            "classes": {k: sum(rep["sunset_earthset"][sid][kind]["classes"][k] for sid in SITES)
                        for k in ("both_zero", "both_null", "both_number", "state_or_null_mismatch")}}
    rep["overall"] = overall
    dest = ROOT / "docs" / "timestep_sensitivity.json"
    dest.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(overall, indent=1))
    print("->", dest)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ephem")
    sub.add_parser("run")
    a = ap.parse_args(argv)
    return {"ephem": cmd_ephem, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
