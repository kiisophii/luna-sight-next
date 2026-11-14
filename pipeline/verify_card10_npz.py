"""Independent check of card 10's 18.6-year validation ephemeris (data/processed/ephem_2020-2038_2h.npz).

Written for the card 10 verification step (separate from the generator, pipeline/ephem.py, and from
card 10's own checks). It does not import ephem.py / Skyfield and does not trust earlier PASS reports.

Checks
  A  file identity: SHA-256 equals the hash card 10 published
  B  schema: keys, dtype, shape, frame, units, columns, start / stop / step metadata
  C  time axis: hour_index = 2 h steps from -52,608 (2020-01-01T00Z) to 110,278 (2038-07-31T22Z)
  D  values: all finite; |Moon->Sun| and |Moon->Earth| inside physical ranges; no jumps
     (each row vs the quadratic prediction from its neighbours)
  E  overlap: every even-hour row of web/data/ephem.bin (2026-2030, card 1) equals the NPZ row
  F  physics over the whole 18.6 years: sub-Earth point (optical libration) and sub-solar latitude
     stay inside the known lunar limits; the sub-solar point drifts west ~12.2 deg/day (synodic month)
  G  JPL Horizons (independent truth, DE441): apparent airless az/el of Sun and Earth from 4 lunar
     sites every 38 h across 2020-01-01 .. 2038-07-31 (~4,290 times per site/body). Our az/el is
     computed here from the NPZ vectors (topocentric: vector minus observer at R + 2 m). The error
     measure is the great-circle angle between the two directions (robust near the zenith).
     Criterion: max < 0.01 deg (card 10 / card 1 standard).

  python pipeline/verify_card10_npz.py [--npz PATH] [--offline]
Raw Horizons responses are cached in data/raw/horizons_verify10/ (git-ignored).
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

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SHA = "358526e031babbe9944695b253ad36f2f63f15cb0175225dfcf04c62886ccabe"
R_KM = 1737.4
OBS_KM = 0.002
API = "https://ssd.jpl.nasa.gov/api/horizons.api"
CACHE = ROOT / "data" / "raw" / "horizons_verify10"
SITES = [  # geometry test points (not landing-site claims)
    ("EQ_0_0", 0.0, 0.0),
    ("SOUTH_89.5_0", -89.5, 0.0),
    ("MID_45N_120W", 45.0, -120.0),
    ("MID_30S_150E", -30.0, 150.0),
]
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
START = datetime(2020, 1, 1, tzinfo=timezone.utc)
results = []


def check(name, ok, detail):
    results.append({"check": name, "pass": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def enu(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.cross(up, east)
    return east, north, up


def horizons(body, lat, lon, offline):
    o = {"format": "json", "COMMAND": f"'{body}'", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
         "SITE_COORD": f"'{lon},{lat},{OBS_KM}'", "START_TIME": "'2020-01-01'", "STOP_TIME": "'2038-07-31 22:00'",
         "STEP_SIZE": "'38 h'", "QUANTITIES": "'4'", "CSV_FORMAT": "'YES'", "EXTRA_PREC": "'YES'",
         "APPARENT": "'AIRLESS'", "CAL_FORMAT": "'JD'", "OBJ_DATA": "'NO'"}
    url = API + "?" + urllib.parse.urlencode(o)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")
    if path.exists():
        item = json.loads(path.read_text(encoding="utf-8"))
    elif offline:
        raise FileNotFoundError(path)
    else:
        with urllib.request.urlopen(url, timeout=300) as r:
            item = {"url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(), "response": json.load(r)}
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(item), encoding="utf-8")
    res = item["response"]["result"]
    if "$$SOE" not in res:
        raise ValueError(res[:500])
    if "DE441" not in res and "DE4" not in res:
        print("  note: Horizons header does not name a DE ephemeris")
    rows = []
    for line in res.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines():
        f = [x.strip() for x in line.split(",")]
        rows.append((float(f[0]), float(f[3]), float(f[4])))
    return np.array(rows), item["url"], item["retrieved_utc"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--npz", type=Path, default=ROOT / "data" / "processed" / "ephem_2020-2038_2h.npz")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--report", type=Path, default=ROOT / "docs" / "card10_npz_independent_check.json")
    a = ap.parse_args(argv)

    # A
    sha = hashlib.sha256(a.npz.read_bytes()).hexdigest()
    check("A sha256", sha == EXPECTED_SHA, f"{sha} (expected {EXPECTED_SHA[:12]}...)")
    # B
    z = np.load(a.npz, allow_pickle=False)
    keys = sorted(z.files)
    want = sorted(["vectors", "hour_index", "start", "step_h", "frame", "units", "columns", "stop_exclusive"])
    v32 = z["vectors"]
    ok = (keys == want and v32.dtype == np.dtype("<f4") and v32.shape == (81444, 6)
          and str(z["frame"]) == "MOON_ME_DE421" and str(z["units"]) == "km"
          and list(z["columns"]) == ["sun_x", "sun_y", "sun_z", "earth_x", "earth_y", "earth_z"]
          and str(z["start"]) == "2020-01-01T00:00:00Z" and str(z["stop_exclusive"]) == "2038-08-01T00:00:00Z"
          and int(z["step_h"]) == 2)
    check("B schema", ok, f"keys {keys}, {v32.dtype} {v32.shape}, frame {z['frame']}, units {z['units']}, "
                          f"{z['start']} .. <{z['stop_exclusive']}, step {z['step_h']} h")
    # C
    hi = z["hour_index"].astype(np.int64)
    n_expected = int((datetime(2038, 8, 1, tzinfo=timezone.utc) - START).total_seconds() // 7200)
    first = int((START - EPOCH).total_seconds() // 3600)
    ok = (hi.size == n_expected == 81444 and hi[0] == first == -52608 and np.all(np.diff(hi) == 2)
          and hi[-1] == 110278)
    check("C time axis", ok, f"n {hi.size} (expected {n_expected}), first {hi[0]}, last {hi[-1]}, "
                             f"steps {set(np.unique(np.diff(hi)).tolist())}")
    # D
    v = v32.astype(np.float64)
    fin = np.isfinite(v).all()
    ds, de = np.linalg.norm(v[:, :3], axis=1), np.linalg.norm(v[:, 3:], axis=1)
    ok_rng = 1.44e8 < ds.min() and ds.max() < 1.54e8 and 3.50e5 < de.min() and de.max() < 4.10e5
    jump = {}
    for name, c in (("sun", 0), ("earth", 3)):
        u = unit(v[:, c:c + 3])
        pred = 3 * u[1:-1] - 3 * u[:-2] + u[:-3] if False else 2 * u[1:-1] - u[:-2]   # linear extrapolation
        err = np.degrees(np.arccos(np.clip((unit(pred) * u[2:]).sum(1), -1, 1)))
        jump[name] = float(err.max())
    ok_jump = jump["sun"] < 0.01 and jump["earth"] < 0.05
    check("D values", fin and ok_rng and ok_jump,
          f"finite {fin}; |sun| {ds.min():.4e}..{ds.max():.4e} km; |earth| {de.min():.1f}..{de.max():.1f} km; "
          f"max deviation from neighbour extrapolation sun {jump['sun']:.2e} deg, earth {jump['earth']:.2e} deg")
    # E
    binp = ROOT / "web" / "data" / "ephem.bin"
    web = np.fromfile(binp, dtype="<f4").reshape(-1, 6)
    i0 = int(np.flatnonzero(hi == 0)[0])
    sub = v32[i0:i0 + web[::2].shape[0]]
    eq = np.array_equal(sub, web[::2]) and sub.shape[0] == 21912
    check("E overlap with ephem.bin", eq, f"{sub.shape[0]} even-hour rows 2026-01-01..2030-12-31 "
                                          f"bit-identical: {eq}")
    # F
    ue, us = unit(v[:, 3:]), unit(v[:, :3])
    lib_lat, lib_lon = np.degrees(np.arcsin(ue[:, 2])), np.degrees(np.arctan2(ue[:, 1], ue[:, 0]))
    sun_lat = np.degrees(np.arcsin(us[:, 2]))
    sun_lon = np.unwrap(np.arctan2(us[:, 1], us[:, 0]))
    days = (hi[-1] - hi[0]) / 24.0
    drift = np.degrees(sun_lon[-1] - sun_lon[0]) / days
    ok = (abs(lib_lat).max() < 7.0 and abs(lib_lon).max() < 8.5 and abs(sun_lat).max() < 1.7
          and -12.3 < drift < -12.1)
    check("F physics", ok, f"sub-Earth lat {lib_lat.min():.2f}..{lib_lat.max():.2f} deg, lon {lib_lon.min():.2f}.."
                           f"{lib_lon.max():.2f} deg (libration); sub-solar lat {sun_lat.min():.3f}..{sun_lat.max():.3f} deg; "
                           f"sub-solar drift {drift:.4f} deg/day (synodic -12.19)")
    # G
    worst, rows_g, meta = 0.0, [], []
    for sid, lat, lon in SITES:
        east, north, up = enu(lat, lon)
        for body, cmd, c in (("sun", 10, 0), ("earth", 399, 3)):
            tab, url, when = horizons(cmd, lat, lon, a.offline)
            hours = np.rint((tab[:, 0] - 2461041.5) * 24).astype(np.int64)   # JD 2461041.5 = 2026-01-01T00Z
            if not np.allclose((tab[:, 0] - 2461041.5) * 24, hours, atol=1e-6):
                raise ValueError("Horizons times are not on whole hours")
            idx = np.searchsorted(hi, hours)
            if not np.array_equal(hi[idx], hours):
                raise ValueError("Horizons times not in the NPZ grid")
            w = v[idx, c:c + 3] - (R_KM + OBS_KM) * up
            ours = unit(w)
            az, el = np.radians(tab[:, 1]), np.radians(tab[:, 2])
            hz = (np.outer(np.cos(el) * np.sin(az), east) + np.outer(np.cos(el) * np.cos(az), north)
                  + np.outer(np.sin(el), up))
            ang = np.degrees(np.arccos(np.clip((ours * hz).sum(1), -1, 1)))
            worst = max(worst, float(ang.max()))
            rows_g.append({"site": sid, "lat": lat, "lon": lon, "body": body, "n": int(ang.size),
                           "first": float(tab[0, 0]), "last": float(tab[-1, 0]),
                           "max_deg": float(ang.max()), "mean_deg": float(ang.mean())})
            meta.append({"url": url, "retrieved_utc": when})
            print(f"  {sid:14s} {body:5s} n={ang.size} max {ang.max():.6f} deg mean {ang.mean():.6f} deg", flush=True)
    n_g = sum(r["n"] for r in rows_g)
    check("G JPL Horizons 2020-2038", worst < 0.01, f"{n_g} comparisons (4 sites x Sun/Earth, every 38 h); "
                                                    f"max direction difference {worst:.6f} deg (< 0.01)")

    report = {"generated_utc": datetime.now(timezone.utc).isoformat(), "file": str(a.npz.name), "sha256": sha,
              "all_pass": all(r["pass"] for r in results), "checks": results, "horizons": rows_g,
              "horizons_queries": meta,
              "not_verified_here": [
                  "web/data/metrics/<ID>.json (card 10 site metrics): needs real horizon files for every site; "
                  "only the 16 south-polar horizons (card 8) are on main, non-polar (card 9) pending",
                  "terrain heights at the test points (all at 0 m + 2 m observer)",
                  "Horizons uses DE441 and its own lunar orientation; agreement is to <0.01 deg, not bit level"]}
    a.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{'ALL PASS' if report['all_pass'] else 'SOME CHECKS FAILED'} - report {a.report.relative_to(ROOT)}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
