"""Independent check of web/data/monthly/<ID>.json (pipeline/seasons.mjs, which runs web/js/core.js).

Re-implements the geometry in numpy WITHOUT core.js (contract section 0 / AGENTS.md definitions):
site frame from lat/lon, observer = R + h0 + 2 m along local up, topocentric az/el of Sun and Earth from
web/data/ephem.bin (hourly rows, no interpolation needed), horizon mask linear in azimuth (0.5 deg bins),
sunlit = visible solar-disc fraction (radius 0.2666 deg, flat mask line) >= 0.5, Earth visible = centre above mask.

  python pipeline/verify_seasons.py   -> docs/seasons_check.json, exit 1 on any mismatch

Checks
 1. 3 sites (SHACKLETON_RIM, ARTEMIS_HAWORTH, APOLLO17) x 6 random months (seed 20261114): sun/earth/both hour counts are identical,
    fractions equal the file to 4 decimals (half-up rounding as in JS) and longest dark is identical (calendar month and the 709 h lunation window); also all 60 months.
 2. Subsolar / sub-Earth latitude range of those months equals the file to 0.001 deg.
 3. All 33 sites: hour-weighted 60-month mean == web/data/metrics/<ID>.json (5-year window) to 1e-9, and the
    longest monthly dark run <= the 5-year longest_dark_h.
"""
import calendar
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
R_KM, SUN_R = 1737.4, 0.2666
SITES = ["SHACKLETON_RIM", "ARTEMIS_HAWORTH", "APOLLO17"]
LUN_HALF = 354


def r4(x):
    """Half-up rounding to 4 decimals, same as JavaScript Math.round(x * 1e4) / 1e4 (Python round() is half-even)."""
    return float(np.floor(x * 1e4 + 0.5) / 1e4)


def month_table():
    out, i0 = [], 0
    for y in range(2026, 2031):
        for m in range(1, 13):
            n = calendar.monthrange(y, m)[1] * 24
            out.append((f"{y}-{m:02d}", i0, i0 + n - 1))
            i0 += n
    return out


def flags(site, hz, eph):
    la, lo = np.radians(site["lat"]), np.radians(site["lon"])
    east = np.array([-np.sin(lo), np.cos(lo), 0.0])
    north = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    obs = up * (R_KM + (hz["h0_m"] + 2) / 1000.0)
    mask = np.asarray(hz["mask"], float)
    nb, step = len(mask), hz["az_step_deg"]

    def azel(v):
        v = v - obs
        e, n, u = v @ east, v @ north, v @ up
        az = np.degrees(np.arctan2(e, n)) % 360.0
        return az, np.degrees(np.arctan2(u, np.hypot(e, n)))

    def hmask(az):
        x = az / step
        k = np.floor(x).astype(int) % nb
        t = x - np.floor(x)
        return mask[k] + (mask[(k + 1) % nb] - mask[k]) * t

    saz, sel = azel(eph[:, 0:3])
    y = (hmask(saz) - sel) / SUN_R
    yc = np.clip(y, -1, 1)
    frac = np.where(y <= -1, 1.0, np.where(y >= 1, 0.0, (np.arccos(yc) - yc * np.sqrt(1 - yc * yc)) / np.pi))
    eaz, eel = azel(eph[:, 3:6])
    return frac >= 0.5, eel > hmask(eaz)


def stats(sun, earth, a, b):
    s, e = sun[a:b + 1], earth[a:b + 1]
    run = longest = 0
    for v in s:
        run = 0 if v else run + 1
        longest = max(longest, run)
    n = len(s)
    return {"sun_frac": s.sum() / n, "earth_frac": e.sum() / n, "both_frac": (s & e).sum() / n, "longest_dark_h": longest}


def sublat(v):
    return np.degrees(np.arcsin(v[:, 2] / np.linalg.norm(v, axis=1)))


def main():
    meta = json.loads((DATA / "ephem.json").read_text())
    eph = np.fromfile(DATA / "ephem.bin", dtype="<f4").astype(np.float64).reshape(meta["n"], 6)
    sites = {s["id"]: s for s in json.loads((DATA / "sites.json").read_text(encoding="utf-8"))}
    M = month_table()
    assert M[-1][2] == meta["n"] - 1
    rng = random.Random(20261114)
    pick = sorted(rng.sample(range(60), 6))
    ssl, sel = sublat(eph[:, 0:3]), sublat(eph[:, 3:6])
    report = {"random_months": [M[k][0] for k in pick], "sites": {}, "average_check": {}, "fail": []}

    for sid in SITES:
        hz = json.loads((DATA / "horizon" / f"{sid}.json").read_text())
        rec = json.loads((DATA / "monthly" / f"{sid}.json").read_text())
        sun, earth = flags(sites[sid], hz, eph)
        rows, worst = [], 0.0
        for k, (lab, a, b) in enumerate(M):
            mine = stats(sun, earth, a, b)
            c = a + (b - a + 1) // 2
            lun = stats(sun, earth, c - LUN_HALF, c + LUN_HALF)
            for f in ("sun_frac", "earth_frac", "both_frac"):
                d1 = abs(r4(mine[f]) - rec["series"][f][k])
                d2 = abs(r4(lun[f]) - rec["lunation"][f][k])
                hours = b - a + 1
                if round(mine[f] * hours) != rec["series"][f.replace("_frac", "_h")][k]:
                    report["fail"].append(f"{sid} {lab} {f}: hour count differs")
                worst = max(worst, d1, d2)
                if d1 > 1e-9 or d2 > 1e-9:
                    report["fail"].append(f"{sid} {lab} {f}: py {mine[f]:.6f}/{lun[f]:.6f} file {rec['series'][f][k]}/{rec['lunation'][f][k]}")
            if mine["longest_dark_h"] != rec["series"]["longest_dark_h"][k]:
                report["fail"].append(f"{sid} {lab} longest_dark_h py {mine['longest_dark_h']} file {rec['series']['longest_dark_h'][k]}")
            lat_ok = (abs(ssl[a:b + 1].min() - rec["subsolar_lat_deg"]["min"][k]) <= 1e-3 and abs(ssl[a:b + 1].max() - rec["subsolar_lat_deg"]["max"][k]) <= 1e-3
                      and abs(sel[a:b + 1].min() - rec["subearth_lat_deg"]["min"][k]) <= 1e-3 and abs(sel[a:b + 1].max() - rec["subearth_lat_deg"]["max"][k]) <= 1e-3)
            if not lat_ok:
                report["fail"].append(f"{sid} {lab} sub-solar/sub-Earth latitude range")
            if k in pick:
                rows.append({"month": lab, "python": {f: r4(v) for f, v in mine.items()},
                             "file": {f: rec["series"][f][k] for f in mine},
                             "python_lunation_sun": r4(lun["sun_frac"]), "file_lunation_sun": rec["lunation"]["sun_frac"][k],
                             "subsolar_lat_deg": [round(ssl[a:b + 1].min(), 3), round(ssl[a:b + 1].max(), 3)]})
        report["sites"][sid] = {"random_month_rows": rows, "all_60_months_max_abs_diff_4dp": worst}

    for sid in sites:
        rec = json.loads((DATA / "monthly" / f"{sid}.json").read_text())
        five = json.loads((DATA / "metrics" / f"{sid}.json").read_text())
        s = rec["series"]
        N = sum(s["hours"])
        diff = {f: abs(sum(s[f.replace("_frac", "_h")]) / N - five[f]) for f in ("sun_frac", "earth_frac", "both_frac")}
        ok = N == meta["n"] and max(diff.values()) <= 1e-9 and max(s["longest_dark_h"]) <= five["longest_dark_h"]
        report["average_check"][sid] = {"max_abs_diff": max(diff.values()), "longest_month": max(s["longest_dark_h"]),
                                        "longest_5yr": five["longest_dark_h"], "ok": ok}
        if not ok:
            report["fail"].append(f"{sid}: 60-month mean differs from metrics/{sid}.json {diff}")

    report["pass"] = not report["fail"]
    (ROOT / "docs" / "seasons_check.json").write_text(json.dumps(report, indent=2) + "\n")
    print("random months:", report["random_months"])
    for sid in SITES:
        print(sid, "max |diff| over 60 months (4 dp):", report["sites"][sid]["all_60_months_max_abs_diff_4dp"])
    print("33-site average check ok:", sum(v["ok"] for v in report["average_check"].values()), "/", len(sites))
    print("PASS" if report["pass"] else "FAIL", *report["fail"][:20], sep="\n")
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
