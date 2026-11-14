"""Card 11 - run the PGDA validation: our 18.6-year Sun / Earth fractions vs PGDA.

Pipeline
  1. Points: the 240 random points (85-90 S, seed 42) and the named south-polar sites from
     data/processed/validation_points.csv / validation_named.csv (pipeline/validate.py, card 5).
  2. Horizons: pipeline/horizon.py (720 azimuths, curvature, observer 2 m) with a polar DEM chain
     taken from two PGDA LOLA windows centred on the pole (fetched with pipeline/fetch_polar.py):
        LDEM_60S_60MPP_ADJ  60 m,  window radius 220 km  -> used within NEAR_KM of the point
        LDEM_60S_240MPP_ADJ 240 m, window radius 520 km  -> used out to 300 km
     60 m near field = the same resolution PGDA used for AVGVISIB_85S_060M (LDEM_85S_060M).
     Masks are cached per point in data/processed/val_horizons/ (resume after interruption).
  3. Ephemeris: data/processed/ephem_2020-2038_2h.npz (card 1/10 generator pipeline/ephem.py,
     2020-01-01 .. 2038-07-31T22Z, 2 h step = one 18.6-year nodal cycle).
  4. Fractions per point (topocentric, observer 2 m above terrain, mask linearly interpolated):
        sun_mean   mean visible fraction of the solar disc (radius 0.2666 deg)  <- PRIMARY (app/global maps)
        sun_any    share of steps with any part of the disc visible             (PGDA label wording)
        sun_half   share of steps with >= 50 % of the disc visible ("sunlit")
        earth_ctr  share of steps with the Earth CENTRE above the mask          (app definition, stricter)
        earth_any  share of steps with any part of the Earth disc visible       <- PRIMARY here: same as PGDA
  5. validate.compare() -> web/data/validation.json (contract v1.1) with the primary definitions
     (Sun: mean disc fraction like the app; Earth: any part of the disc like PGDA, because the
     app's Earth-centre rule is stricter by design and would show a definition gap, not an error);
     the alternative definitions are added under "alt_definitions" so the team can see which one
     PGDA matches best.

Usage
  python pipeline/validate_ours.py                 # everything (resumes)
  python pipeline/validate_ours.py --workers 4     # horizons in 4 processes (default 1)
  python pipeline/validate_ours.py --limit 5       # quick test on the first 5 points (no JSON)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as hz  # noqa: E402
import validate as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEM_DIR = ROOT / "data" / "raw" / "polar_validation"
DEM_ID = "VALIDATION_POLE"
NEAR_KM = 60.0
MAX_KM = 300.0
CACHE = ROOT / "data" / "processed" / "val_horizons"
EPHEM = ROOT / "data" / "processed" / "ephem_2020-2038_2h.npz"
R_KM = hz.R_M / 1000.0
SUN_RADIUS_DEG = 0.2666           # contract section 6
EARTH_RADIUS_KM = 6371.0          # mean Earth radius (IAU), for the 'any part' Earth variant

_CHAIN = None


def chain():
    global _CHAIN
    if _CHAIN is None:
        near = hz.PolarStereoSampler(DEM_DIR / "60" / f"{DEM_ID}.npz", name="PGDA_LOLA_60M")
        far = hz.PolarStereoSampler(DEM_DIR / "240" / f"{DEM_ID}.npz", name="PGDA_LOLA_240M")
        _CHAIN = [(near, NEAR_KM), (far, MAX_KM)]
    return _CHAIN


def horizon_for(key, lat, lon):
    """Cached horizon (mask deg[720], h0_m, missing share)."""
    path = CACHE / f"{key}.npz"
    if path.exists():
        with np.load(path) as z:
            if float(z["lat"]) == lat and float(z["lon"]) == lon:
                return key, z["mask"].copy(), float(z["h0_m"]), float(z["missing"]), "cached"
    t0 = time.time()
    res = hz.compute_horizon(lat, lon, chain(), max_km=MAX_KM)
    miss = res["n_missing"] / max(res["n_samples"], 1)
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez(tmp, mask=res["mask"], h0_m=res["h0_m"], lat=lat, lon=lon, missing=miss,
             sources=json.dumps(res["dem_sources"]))
    tmp.replace(path)
    return key, res["mask"], res["h0_m"], miss, f"{time.time() - t0:.1f} s"


def load_ephem():
    with np.load(EPHEM) as z:
        v = z["vectors"].astype(np.float64)
        if str(z["start"]) != "2020-01-01T00:00:00Z" or int(z["step_h"]) != 2:
            raise ValueError("unexpected validation ephemeris window")
    return v


def mask_at(mask_deg, az_deg):
    x = (np.asarray(az_deg) / 0.5) % 720.0
    i0 = np.floor(x).astype(int) % 720
    f = x - np.floor(x)
    return mask_deg[i0] * (1 - f) + mask_deg[(i0 + 1) % 720] * f


def disk_fraction(x):
    """Visible part of a disc whose centre is x radii above a straight horizon line."""
    x = np.clip(x, -1.0, 1.0)
    return 0.5 + (x * np.sqrt(1.0 - x * x) + np.arcsin(x)) / np.pi


def fractions(vectors, lat, lon, h0_m, mask_deg, obs_height_m=hz.OBS_HEIGHT_M):
    la, lo = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.cross(up, east)
    r_o = R_KM + (h0_m + obs_height_m) / 1000.0
    out = {}
    for body, col in (("sun", 0), ("earth", 3)):
        v = vectors[:, col:col + 3] - r_o * up
        e, n, u = v @ east, v @ north, v @ up
        az = np.degrees(np.arctan2(e, n)) % 360.0
        el = np.degrees(np.arctan2(u, np.hypot(e, n)))
        d = el - mask_at(mask_deg, az)
        if body == "sun":
            fr = disk_fraction(d / SUN_RADIUS_DEG)
            out["sun_mean"] = float(fr.mean())
            out["sun_any"] = float((d > -SUN_RADIUS_DEG).mean())
            out["sun_half"] = float((fr >= 0.5).mean())
        else:
            rad = np.degrees(np.arcsin(EARTH_RADIUS_KM / np.linalg.norm(v, axis=1)))
            out["earth_ctr"] = float((d > 0).mean())
            out["earth_any"] = float((d > -rad).mean())
    return out


def stats(ours, pgda, lo, hi):
    """Same numbers compare() writes: ours rounded to 5 decimals exactly as stored in the JSON
    points, so alt_definitions and the main sun/earth blocks agree (and check_contract can
    recompute them from the points)."""
    return V._stats([round(float(x), 5) for x in ours], pgda, lo, hi)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="only the first N points (test; no JSON)")
    ap.add_argument("--named-horizons", type=Path, default=None,
                    help="folder with card 8 site horizons (<ID>.json, contract section 3); named sites then use "
                         "these masks instead of the pole-centred windows, and both are compared")
    ap.add_argument("--no-json", action="store_true", help="do not write web/data/validation.json (preview)")
    a = ap.parse_args(argv)

    pts = V.read_csv(V.PROCESSED / "validation_points.csv")
    named = V.read_csv(V.PROCESSED / "validation_named.csv")
    if a.limit:
        pts, named = pts[:a.limit], []
    jobs = [(f"P{int(p['k']):03d}", p["lat"], p["lon"]) for p in pts]
    jobs += [(f"N_{n['id']}", n["lat"], n["lon"]) for n in named]
    print(f"{len(pts)} points + {len(named)} named sites; DEM chain 60 m <= {NEAR_KM:g} km, "
          f"240 m <= {MAX_KM:g} km; {a.workers} worker(s)", flush=True)

    hor = {}
    t0 = time.time()
    if a.workers > 1:
        with cf.ProcessPoolExecutor(a.workers) as ex:
            futs = [ex.submit(horizon_for, *j) for j in jobs]
            for k, f in enumerate(cf.as_completed(futs), 1):
                key, m, h0, miss, msg = f.result()
                hor[key] = (m, h0, miss)
                if k % 20 == 0 or k == len(jobs):
                    print(f"  horizons {k}/{len(jobs)} ({time.time() - t0:.0f} s)", flush=True)
    else:
        for k, j in enumerate(jobs, 1):
            key, m, h0, miss, msg = horizon_for(*j)
            hor[key] = (m, h0, miss)
            print(f"  {k}/{len(jobs)} {key}: h0 {h0:.0f} m, mask {m.min():.2f}..{m.max():.2f} deg, "
                  f"missing {miss:.2%}, {msg}", flush=True)

    vec = load_ephem()
    print(f"ephemeris: {vec.shape[0]} steps (2 h) 2020-01-01 .. 2038-07-31", flush=True)
    card8 = {}
    if a.named_horizons:
        for n in named:
            p = a.named_horizons / f"{n['id']}.json"
            if not p.exists():
                print(f"  card 8 horizon missing for {n['id']} - keeping the pole-window horizon", flush=True)
                continue
            h = json.loads(p.read_text(encoding="utf-8"))
            if abs(h["lat"] - n["lat"]) > 1e-4 or abs(h["lon"] - n["lon"]) > 1e-4 or len(h["mask"]) != 720:
                raise ValueError(f"{p}: coordinates or mask size differ from validation_named.csv")
            card8[n["id"]] = h
    rows = []
    for (key, lat, lon) in jobs:
        m, h0, miss = hor[key]
        rows.append(dict(key=key, lat=lat, lon=lon, h0_m=h0, missing=miss,
                         **fractions(vec, lat, lon, h0, m)))
    by = {r["key"]: r for r in rows}
    named_cmp = []
    for n in named:
        if n["id"] not in card8:
            continue
        h = card8[n["id"]]
        f8 = fractions(vec, n["lat"], n["lon"], float(h["h0_m"]), np.asarray(h["mask"], float))
        w = by[f"N_{n['id']}"]
        named_cmp.append({"id": n["id"], "pgda_sun": n["pgda_sun"], "pole_sun": w["sun_mean"], "card8_sun": f8["sun_mean"],
                          "pgda_earth": n["pgda_earth"], "pole_earth": w["earth_any"], "card8_earth": f8["earth_any"],
                          "card8_earth_ctr": f8["earth_ctr"],
                          "card8_sources": "+".join(f"{d['name']}<={d['to_km']:g}km" for d in h["dem_sources"])})
        # named sites in the JSON use card 8's finer per-site horizons from now on
        w.update({k: f8[k] for k in f8}, h0_m=float(h["h0_m"]), key=w["key"])
    if named_cmp:
        print(f"  named sites: card 8 site horizons vs pole-centred 60/240 m windows (n = {len(named_cmp)})")
        print(f"  {'id':26s} {'PGDA sun':>8s} {'pole':>6s} {'card8':>6s} | {'PGDA earth':>10s} {'pole':>6s} {'card8':>6s}")
        for c in named_cmp:
            print(f"  {c['id']:26s} {c['pgda_sun']:8.3f} {c['pole_sun']:6.3f} {c['card8_sun']:6.3f} | "
                  f"{c['pgda_earth']:10.3f} {c['pole_earth']:6.3f} {c['card8_earth']:6.3f}")
        for body in ("sun", "earth"):
            for src in ("pole", "card8"):
                d = np.array([c[f"{src}_{body}"] - c[f"pgda_{body}"] for c in named_cmp]) * 100
                print(f"  {body:5s} {src:5s}: MAE {np.abs(d).mean():.2f} pp, bias {d.mean():+.2f} pp")
        cmp_csv = V.PROCESSED / "validation_named_card8.csv"
        with open(cmp_csv, "w", encoding="utf-8") as f:
            f.write(",".join(named_cmp[0].keys()) + "\n")
            for c in named_cmp:
                f.write(",".join(f"{v:.5f}" if isinstance(v, float) else str(v) for v in c.values()) + "\n")
        print(f"  wrote {cmp_csv.relative_to(ROOT)}", flush=True)

    # per-point table for checking by hand
    out_csv = V.PROCESSED / "validation_ours.csv"
    keys = list(rows[0].keys())
    with open(out_csv, "w", encoding="utf-8") as f:
        f.write(",".join(keys) + "\n")
        for r in rows:
            f.write(",".join(f"{r[k]:.6f}" if isinstance(r[k], float) else str(r[k]) for k in keys) + "\n")
    print(f"  wrote {out_csv.relative_to(ROOT)}", flush=True)

    pr = [by[f"P{int(p['k']):03d}"] for p in pts]
    alt = {}
    for name, col, body in (("sun_mean_disc_fraction", "sun_mean", "sun"), ("sun_any_part", "sun_any", "sun"),
                            ("sun_half_disc", "sun_half", "sun"), ("earth_centre", "earth_ctr", "earth"),
                            ("earth_any_part", "earth_any", "earth")):
        alt[name] = stats([r[col] for r in pr], [p[f"pgda_{body}"] for p in pts],
                          [p[f"pgda_{body}_min60"] for p in pts], [p[f"pgda_{body}_max60"] for p in pts])
        print(f"  {name:24s} {alt[name]}", flush=True)
    if a.limit or a.no_json:
        print("(test/preview run: validation.json not written)")
        return 0

    ours = {"points": [{"ours_sun": r["sun_mean"], "ours_earth": r["earth_any"]} for r in pr],
            "named": {n["id"]: {"ours_sun": by[f"N_{n['id']}"]["sun_mean"],
                                "ours_earth": by[f"N_{n['id']}"]["earth_any"]} for n in named}}
    out = V.WEB_DATA / "validation.json"
    res = V.compare(ours, out=out, mock=False)
    res["definitions"] = {
        "ours_sun": "mean visible fraction of the solar disc (radius 0.2666 deg), 2 m observer",
        "ours_earth": "share of 2-h steps with any part of the Earth disc above the horizon mask (topocentric; same as PGDA). The app uses the stricter Earth-centre rule - see alt_definitions.earth_centre",
        "pgda": "PGDA AVGVISIB maps (Mazarico et al. 2011), 18.6-year hourly averages, LDEM 60 m",
        "horizon": f"pipeline/horizon.py, PGDA LOLA 60 m <= {NEAR_KM:g} km then 240 m <= {MAX_KM:g} km, curvature",
        "ephemeris": "data/processed/ephem_2020-2038_2h.npz (pipeline/ephem.py, NAIF DE440s + MOON_ME DE421)",
    }
    res["alt_definitions"] = alt
    res["max_missing_dem_share"] = round(max(r["missing"] for r in rows), 5)
    if card8:
        res["definitions"]["named_horizon"] = ("named sites: card 8 per-site horizons (web/data/horizon/<ID>.json, "
                                               "5-240 m PGDA LOLA + LDEM chain); random points: pole-centred 60/240 m windows")
        res["named_pole_window_vs_card8"] = named_cmp
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)} (with definitions + alt_definitions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
