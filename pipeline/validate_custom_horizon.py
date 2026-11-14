"""Validate the browser (custom-site) horizon.

A. Implementation check: browser JS (web/js/hterrain.js, run in Node by check_custom_horizon.mjs) vs the Python
   engine pipeline/horizon.py run on the SAME web tiles (web/data/hterrain/). Should agree to ~1e-3 deg.
B. Resolution error: browser horizon vs the catalogue pipeline horizons (cards 8/9, web/data/horizon/<ID>.json,
   finer DEMs: PGDA 5-240 m / SLDEM2015) -> RMS of the mask difference (deg) and the change in sunlight / Earth
   visibility fractions over the whole ephemeris window (2026-2030, 2 h step, same definitions as core.js).
C. (optional) browser vs Python with the full-resolution LDEM_64 (474 m) + LDEM_16 chain: effect of the 2x2 block
   mean alone.

  node pipeline/check_custom_horizon.mjs data/processed/custom_horizon/browser.json ID ...
  python pipeline/validate_custom_horizon.py --browser data/processed/custom_horizon/browser.json \
      --pipeline-dir web/data/horizon [--ldem64 .../ldem_64_float.img --ldem16 .../ldem_16_float.img --full IDS]
Writes docs/custom_horizon_validation.json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"


class WebTileSampler:
    """Python twin of hterrain.js sampleGrid: bilinear inside one (n x n) tile, same pixel-centre convention."""

    def __init__(self, tile_dir: Path, grid: dict, name: str):
        self.dir, self.g, self.name, self.res_m = tile_dir, grid, name, grid["res_m"]
        self.cache: dict[tuple[int, int], np.ndarray] = {}

    def tile(self, ty, tx):
        k = (ty, tx)
        if k not in self.cache:
            n = self.g["n"]
            d = np.frombuffer(gzip.decompress((self.dir / f"{ty}_{tx}.i16.gz").read_bytes()), "<i2")
            self.cache[k] = np.cumsum(d.reshape(n, n).astype(np.int64), axis=1).astype(np.float64)
        return self.cache[k]

    def sample(self, lat, lon):
        shape = np.shape(lat)
        lat = np.asarray(lat, float).ravel()
        lon = np.asarray(lon, float).ravel()
        P, tp = self.g["ppd"], self.g["n"] - 1
        Hh, W = 180 * P, 360 * P
        r = np.clip((90 - lat) * P - 0.5, 0, Hh - 1)
        r0 = np.minimum(np.floor(r), Hh - 2).astype(np.int64)
        fr = r - r0
        c = (lon + 180) * P - 0.5
        c0f = np.floor(c)
        fc = c - c0f
        c0 = np.mod(c0f.astype(np.int64), W)
        ty, tx = r0 // tp, c0 // tp
        lr, lc = r0 - ty * tp, c0 - tx * tp
        out = np.empty(lat.size)
        key = ty * 1000 + tx
        for k in np.unique(key):
            m = key == k
            t = self.tile(int(k // 1000), int(k % 1000))
            a, b, u, v = lr[m], lc[m], fr[m], fc[m]
            out[m] = (1 - u) * ((1 - v) * t[a, b] + v * t[a, b + 1]) + u * ((1 - v) * t[a + 1, b] + v * t[a + 1, b + 1])
        return out.reshape(shape)


def rms(a, b):
    d = np.asarray(a, float) - np.asarray(b, float)
    return float(np.sqrt(np.mean(d * d))), float(np.max(np.abs(d))), float(np.mean(d))


# ------------------------------------------------------------- metrics (same definitions as web/js/core.js)
def load_ephem(step_h=2):
    e = np.fromfile(WEB / "ephem.bin", dtype="<f4").reshape(-1, 6).astype(np.float64)
    return e[::step_h]


def fractions(lat, lon, h0_m, mask, eph):
    la, lo = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.cross(up, east)
    obs = up * (H.R_M + h0_m + 2.0) / 1000.0
    mask = np.asarray(mask, float)
    nb = mask.size
    step = 360.0 / nb

    def azel(v):
        v = v - obs
        e, n, u = v @ east, v @ north, v @ up
        return np.degrees(np.arctan2(e, n)) % 360.0, np.degrees(np.arctan2(u, np.hypot(e, n)))

    def hz(az):
        x = az / step
        k = np.floor(x).astype(int) % nb
        t = x - np.floor(x)
        return mask[k] + (mask[(k + 1) % nb] - mask[k]) * t

    saz, sel = azel(eph[:, :3])
    eaz, eel = azel(eph[:, 3:])
    y = np.clip((hz(saz) - sel) / 0.2666, -1, 1)
    frac = (np.arccos(y) - y * np.sqrt(1 - y * y)) / np.pi
    sun = frac >= 0.5
    earth = eel > hz(eaz)
    return float(sun.mean()), float(earth.mean()), float((sun & earth).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", required=True, type=Path)
    ap.add_argument("--pipeline-dir", type=Path, default=WEB / "horizon")
    ap.add_argument("--ldem64", type=Path)
    ap.add_argument("--ldem16", type=Path)
    ap.add_argument("--full", default="", help="comma-separated IDs for check C")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "custom_horizon_validation.json")
    a = ap.parse_args()

    idx = json.loads((WEB / "hterrain" / "index.json").read_text(encoding="utf-8"))
    near = WebTileSampler(WEB / "hterrain" / "tiles" / "near", idx["grids"]["near"], "near")
    far = WebTileSampler(WEB / "hterrain" / "tiles" / "far", idx["grids"]["far"], "far")
    chain = [(near, idx["grids"]["near"]["to_km"]), (far, idx["grids"]["far"]["to_km"])]
    browser = {s["id"]: s for s in json.loads(a.browser.read_text(encoding="utf-8"))["sites"]}
    eph = load_ephem(2)
    report = {"tiles": {k: {kk: v[kk] for kk in ("ppd", "res_m", "to_km", "source")} for k, v in idx["grids"].items()},
              "ephem_window": "2026-01-01..2030-12-31, 2 h step",
              "A_js_vs_python_same_tiles": [], "B_browser_vs_catalogue": [], "C_browser_vs_full_ldem64": []}

    for sid, b in browser.items():
        r = H.compute_horizon(b["lat"], b["lon"], chain)
        e_rms, e_max, _ = rms(b["mask"], r["mask"])
        report["A_js_vs_python_same_tiles"].append({"id": sid, "rms_deg": float(f"{e_rms:.3g}"), "max_abs_deg": float(f"{e_max:.3g}"),
                                                    "h0_js": round(b["h0_m"], 3), "h0_py": round(r["h0_m"], 3)})
        print(f"A {sid:24s} JS vs Python same tiles: RMS {e_rms:.2e} deg, max {e_max:.2e} deg")

    for sid, b in browser.items():
        f = a.pipeline_dir / f"{sid}.json"
        if not f.exists():
            continue
        p = json.loads(f.read_text(encoding="utf-8"))
        if p.get("mock") or p.get("site_coords_mock"):
            continue
        e_rms, e_max, e_bias = rms(b["mask"], p["mask"])
        fb = fractions(b["lat"], b["lon"], b["h0_m"], b["mask"], eph)
        fp = fractions(p["lat"], p["lon"], p["h0_m"], p["mask"], eph)
        row = {"id": sid, "rms_deg": round(e_rms, 3), "max_abs_deg": round(e_max, 3), "bias_deg": round(e_bias, 3),
               "h0_browser_m": round(b["h0_m"], 1), "h0_catalogue_m": p["h0_m"],
               "catalogue_dems": [d["name"] for d in p["dem_sources"]],
               "sun_pp": round(100 * (fb[0] - fp[0]), 2), "earth_pp": round(100 * (fb[1] - fp[1]), 2),
               "both_pp": round(100 * (fb[2] - fp[2]), 2),
               "catalogue_sun_pct": round(100 * fp[0], 1), "catalogue_earth_pct": round(100 * fp[1], 1)}
        report["B_browser_vs_catalogue"].append(row)
        print(f"B {sid:24s} browser vs catalogue: RMS {e_rms:.2f} deg (max {e_max:.2f}, bias {e_bias:+.2f}); "
              f"sun {row['sun_pp']:+.1f} pp, earth {row['earth_pp']:+.1f} pp, both {row['both_pp']:+.1f} pp")

    if a.full and a.ldem64 and a.ldem16:
        c64, c16 = H.GlobalCylSampler(a.ldem64), H.GlobalCylSampler(a.ldem16)
        for sid in a.full.split(","):
            b = browser[sid]
            r = H.compute_horizon(b["lat"], b["lon"], [(c64, 150.0), (c16, 300.0)])
            e_rms, e_max, e_bias = rms(b["mask"], r["mask"])
            fb = fractions(b["lat"], b["lon"], b["h0_m"], b["mask"], eph)
            fp = fractions(b["lat"], b["lon"], r["h0_m"], r["mask"], eph)
            report["C_browser_vs_full_ldem64"].append({"id": sid, "rms_deg": round(e_rms, 3), "max_abs_deg": round(e_max, 3),
                                                       "sun_pp": round(100 * (fb[0] - fp[0]), 2),
                                                       "earth_pp": round(100 * (fb[1] - fp[1]), 2)})
            print(f"C {sid:24s} browser (948 m) vs full LDEM_64 (474 m): RMS {e_rms:.3f} deg (max {e_max:.2f}); "
                  f"sun {100 * (fb[0] - fp[0]):+.2f} pp, earth {100 * (fb[1] - fp[1]):+.2f} pp")

    B = report["B_browser_vs_catalogue"]
    if B:
        allr = np.array([r["rms_deg"] for r in B])
        report["B_summary"] = {"n_sites": len(B), "rms_deg_median": round(float(np.median(allr)), 3),
                               "rms_deg_max": round(float(allr.max()), 3),
                               "abs_sun_pp_median": round(float(np.median([abs(r["sun_pp"]) for r in B])), 2),
                               "abs_sun_pp_max": round(float(max(abs(r["sun_pp"]) for r in B)), 2),
                               "abs_earth_pp_median": round(float(np.median([abs(r["earth_pp"]) for r in B])), 2),
                               "abs_earth_pp_max": round(float(max(abs(r["earth_pp"]) for r in B)), 2)}
        print("B summary", report["B_summary"])
    a.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote", a.out)
    # small summary the app shows next to the custom-site resolution label (numbers from this run only)
    A = report["A_js_vs_python_same_tiles"]
    C = report["C_browser_vs_full_ldem64"]
    summary = {"source": "pipeline/validate_custom_horizon.py -> docs/custom_horizon_validation.json",
               "impl_rms_deg_max": max(r["rms_deg"] for r in A) if A else None,
               "catalogue": report.get("B_summary"),
               "catalogue_dems": "PGDA LOLA 5-240 m (card 8, south polar sites)" if B else None,
               "full_ldem64_rms_deg_max": max(r["rms_deg"] for r in C) if C else None,
               "full_ldem64_ids": [r["id"] for r in C]}
    (WEB / "hterrain" / "validation.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
