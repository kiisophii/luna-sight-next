"""Task M (2026-11-15, Dongju): independent FULL recomputation of web/data/metrics/ (33 sites).

Own loop, nothing imported from pipeline/ or web/js/. The definitions are copied from web/js/core.js
(read as text, re-written here in NumPy):
  * site frame from sites.json lat/lon (siteFrame), observer at R + (h0_m + 2 m) along up, h0_m from
    the site's web/data/horizon/<ID>.json (observerPos),
  * hourly rows of web/data/ephem.bin (float32 km, MOON_ME), all 43,824 hours (default window
    2026-01-01..2030-12-31, metrics(site) with i0 = 0, i1 = n - 1),
  * topocentric azimuth / elevation in degrees (azEl), mask linearly interpolated between
    az_step_deg bins with wrap (horizonAt),
  * sun visible fraction (acos(y) - y sqrt(1 - y^2)) / pi with y = (mask - el) / 0.2666 deg,
    sunlit = fraction >= 0.5; Earth visible = Earth-centre el > mask; both = sunlit AND Earth;
    longest_dark_h = longest run of consecutive not-sunlit hours.

    python pipeline/crosscheck_metrics_dongju.py   # -> docs/crosscheck_metrics_dongju.{json,md}
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
R_MOON_KM = 1737.4
SUN_RADIUS_DEG = 0.2666
TOL_PP, TOL_H = 0.1, 1


def site_metrics(site, hz, eph):
    la, lo = np.radians(site["lat"]), np.radians(site["lon"])
    east = np.array([-np.sin(lo), np.cos(lo), 0.0])
    north = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    obs = up * (R_MOON_KM + (hz["h0_m"] + 2) / 1000.0)
    mask = np.asarray(hz["mask"], float)
    step = float(hz["az_step_deg"])
    nb = mask.size

    def az_el(v):
        d = v - obs
        e, n, u = d @ east, d @ north, d @ up
        az = np.degrees(np.arctan2(e, n))
        az = np.where(az < 0, az + 360.0, az)
        return az, np.degrees(np.arctan2(u, np.hypot(e, n)))

    def horizon_at(az):
        x = np.mod(np.mod(az, 360.0) + 360.0, 360.0) / step
        k = np.floor(x).astype(int) % nb
        t = x - np.floor(x)
        return mask[k] + (mask[(k + 1) % nb] - mask[k]) * t

    saz, sel = az_el(eph[:, 0:3])
    y = (horizon_at(saz) - sel) / SUN_RADIUS_DEG
    frac = np.where(y <= -1, 1.0, np.where(y >= 1, 0.0,
                    (np.arccos(np.clip(y, -1, 1)) - y * np.sqrt(np.clip(1 - y * y, 0, None))) / np.pi))
    sunlit = frac >= 0.5
    eaz, eel = az_el(eph[:, 3:6])
    earth = eel > horizon_at(eaz)
    run = longest = 0
    for s in sunlit:
        run = 0 if s else run + 1
        if run > longest:
            longest = run
    n = sunlit.size
    # closest approach to a sunlit / Earth threshold (how close a rounding-level flip would be)
    return dict(sun_frac=sunlit.sum() / n, earth_frac=earth.sum() / n, both_frac=(sunlit & earth).sum() / n,
                longest_dark_h=int(longest), n=int(n),
                min_sun_margin=float(np.abs(frac - 0.5).min()),
                min_earth_margin_deg=float(np.abs(eel - horizon_at(eaz)).min()))


def main():
    sites = json.loads((WEB / "sites.json").read_text(encoding="utf-8"))
    meta = json.loads((WEB / "ephem.json").read_text(encoding="utf-8"))
    raw = (WEB / "ephem.bin").read_bytes()
    eph = np.frombuffer(raw, dtype="<f4").astype(np.float64).reshape(-1, 6)
    assert eph.shape[0] == meta["n"] == 43824
    rows, fails = [], []
    for s in sites:
        mp = WEB / "metrics" / f"{s['id']}.json"
        hp = WEB / "horizon" / f"{s['id']}.json"
        if not mp.exists():
            continue
        f = json.loads(mp.read_text(encoding="utf-8"))
        hz = json.loads(hp.read_text(encoding="utf-8"))
        m = site_metrics(s, hz, eph)
        r = dict(site=s["id"], lat=s["lat"], lon=s["lon"], horizon_lat=hz.get("lat"), horizon_lon=hz.get("lon"),
                 window=f["window"], hours=m["n"], longest_dark_mine=m["longest_dark_h"],
                 longest_dark_file=f["longest_dark_h"], min_sun_margin=m["min_sun_margin"],
                 min_earth_margin_deg=m["min_earth_margin_deg"],
                 horizon_sha256=hashlib.sha256(hp.read_bytes()).hexdigest()[:16])
        for k in ("sun_frac", "earth_frac", "both_frac"):
            r[f"{k}_mine"], r[f"{k}_file"] = m[k], f[k]
            r[f"{k}_diff_pp"] = 100 * (m[k] - f[k])
            r[f"{k}_hours_diff"] = int(round((m[k] - f[k]) * m["n"]))
        r["dark_diff_h"] = m["longest_dark_h"] - f["longest_dark_h"]
        r["pass"] = bool(all(abs(r[f"{k}_diff_pp"]) <= TOL_PP for k in ("sun_frac", "earth_frac", "both_frac"))
                         and abs(r["dark_diff_h"]) <= TOL_H)
        r["identical"] = bool(all(r[f"{k}_hours_diff"] == 0 for k in ("sun_frac", "earth_frac", "both_frac"))
                              and r["dark_diff_h"] == 0)
        rows.append(r)
        if not r["pass"]:
            fails.append(s["id"])
        print(f"{s['id']}: sun {r['sun_frac_diff_pp']:+.6f} earth {r['earth_frac_diff_pp']:+.6f} "
              f"both {r['both_frac_diff_pp']:+.6f} pp, dark {r['dark_diff_h']:+d} h {'PASS' if r['pass'] else 'FAIL'}")
    absmax = {k: max(abs(r[f"{k}_diff_pp"]) for r in rows) for k in ("sun_frac", "earth_frac", "both_frac")}
    med = {k: float(np.median([abs(r[f"{k}_diff_pp"]) for r in rows])) for k in ("sun_frac", "earth_frac", "both_frac")}
    summary = dict(sites=len(rows), fails=fails, identical=sum(r["identical"] for r in rows),
                   max_abs_diff_pp=absmax, median_abs_diff_pp=med,
                   max_dark_diff_h=max(abs(r["dark_diff_h"]) for r in rows),
                   coords_differ_from_horizon=[r["site"] for r in rows
                                               if (r["horizon_lat"], r["horizon_lon"]) != (r["lat"], r["lon"])],
                   criterion=dict(fraction_pp=TOL_PP, longest_dark_h=TOL_H),
                   ephem_sha256=hashlib.sha256(raw).hexdigest()[:16])
    doc = dict(task="M", checker="Dongju Kim", product="web/data/metrics/ (33 sites)", summary=summary, rows=rows)
    (ROOT / "docs" / "crosscheck_metrics_dongju.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    L = ["# Task M — independent full recomputation of `web/data/metrics/` (Dongju Kim, 2026-11-15)", "",
         "Own NumPy loop `pipeline/crosscheck_metrics_dongju.py` (no imports from `pipeline/` or `web/js/`; the formulas "
         "of `web/js/core.js` re-written: `siteFrame`, `observerPos`, `azEl`, `horizonAt`, `sunVisibleFraction`, "
         "`earthVisible`, `metrics`). Inputs: `web/data/ephem.bin` (all 43,824 hours, default window "
         "2026-01-01..2030-12-31), `web/data/horizon/<ID>.json` (mask, `az_step_deg`, `h0_m`), `web/data/sites.json` "
         "(lat/lon). Machine-readable: `docs/crosscheck_metrics_dongju.json`.", "",
         f"Criterion: ≤ {TOL_PP} %p per fraction, ≤ {TOL_H} h for the longest dark period.", "",
         "## Summary", "", "| Check | Result |", "|---|---|",
         f"| Sites | {summary['sites']} |",
         f"| Max \\|diff\\| sun / Earth / both | {absmax['sun_frac']:.6f} / {absmax['earth_frac']:.6f} / {absmax['both_frac']:.6f} %p |",
         f"| Median \\|diff\\| sun / Earth / both | {med['sun_frac']:.6f} / {med['earth_frac']:.6f} / {med['both_frac']:.6f} %p |",
         f"| Max \\|diff\\| longest dark | {summary['max_dark_diff_h']} h |",
         f"| Sites identical to the hour (all three counts and longest dark) | {summary['identical']}/{summary['sites']} |",
         f"| Sites failing the criterion | {len(fails)}{': ' + ', '.join(fails) if fails else ''} |",
         f"| Sites whose horizon file lat/lon differ from sites.json | {', '.join(summary['coords_differ_from_horizon']) or 'none'} |",
         "", "## All 33 sites", "",
         "Fractions in %. diff = mine − file in %p (hours in brackets). Margin columns: closest any hour came to the "
         "sunlit threshold (disk fraction − 0.5) and to the Earth threshold (deg), which shows how sensitive a count is.", "",
         "| Site | Sun mine / file (diff) | Earth mine / file (diff) | Both mine / file (diff) | Longest dark mine / file h | "
         "Min sun margin | Min Earth margin ° | Pass |",
         "|---|---|---|---|---|---:|---:|---|"]
    for r in rows:
        cell = lambda k: (f"{100 * r[k + '_mine']:.4f} / {100 * r[k + '_file']:.4f} "  # noqa: E731
                          f"({r[k + '_diff_pp']:+.6f}; {r[k + '_hours_diff']:+d} h)")
        L.append(f"| {r['site']} | {cell('sun_frac')} | {cell('earth_frac')} | {cell('both_frac')} | "
                 f"{r['longest_dark_mine']} / {r['longest_dark_file']} | {r['min_sun_margin']:.2e} | "
                 f"{r['min_earth_margin_deg']:.2e} | {'PASS' if r['pass'] else '**FAIL**'} |")
    L += ["", "## Scope", "",
          "- Recomputes the metrics from the published horizon masks; it does not re-derive the masks from the DEM "
          "(that is task A, horizon files).",
          "- Same hourly sampling and threshold rules as the app; no sub-hour refinement (the app's `metrics` has none either).",
          "", "Reproduce: `python pipeline/crosscheck_metrics_dongju.py` (about a second per site)."]
    (ROOT / "docs" / "crosscheck_metrics_dongju.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
