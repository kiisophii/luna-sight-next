"""Validate the south-polar browser path for custom points (s4).

Reference = the card-8 horizon chain run by pipeline/horizon.py (PGDA 5/10/20/60/80/240 m windows where the
products cover the point, then LOLA LDEM_64/16 to 300 km, min 5 m, 8000 steps):
  * 16 catalogue south-polar sites: web/data/horizon/<ID>.json (card 8 production masks)
  * 30 random test points (pipeline/custom_polar_reference.py): data/processed/custom_polar/ref/<ID>.json

Compared for every point (RMS / max of the 720-azimuth mask difference, sun / Earth / both fractions over
2026-2030 at a 2 h step, same definitions as web/js/core.js):
  before = browser global path (948 m LDEM_64 tiles)       node pipeline/check_custom_horizon.mjs --no-polar ...
  after  = browser polar path (web/data/hterrain/polar_s)   node pipeline/check_custom_horizon.mjs ...
Plus an implementation check: the browser JS polar path vs this file's Python twin (same tiles, horizon.py engine).

  python pipeline/validate_custom_polar.py --before b.json --after a.json
Writes docs/custom_polar_validation.json and the "polar" block of web/data/hterrain/validation.json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as H  # noqa: E402
import validate_custom_horizon as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
TARGET_RMS_MEDIAN = 0.2     # deg, requested by the integrator (accuracy-first task, 2026-11-14)
TARGET_SUN_PP = 2.0         # |delta sun| per point, percentage points
BANDS = [("75-80S", -80.0, -75.0), ("80-85S", -85.0, -80.0), ("85-90S", -90.0, -85.0)]


class WebPolarSampler:
    """Python twin of hterrain.js samplePolar (same tiles, same pixel convention, same no-data rule)."""

    def __init__(self, level: dict, root: Path):
        self.lv, self.root, self.name, self.res_m = level, root, level["name"], level["res_m"]
        self.present = set(level["tiles"])
        self.cache: dict[str, np.ndarray] = {}

    def tile(self, key):
        if key not in self.cache:
            n, q = self.lv["n"], self.lv["q_m"]
            b = gzip.decompress((self.root / self.lv["url"].replace("polar_s/", "").replace("{ty}_{tx}", key)).read_bytes())
            base = int(np.frombuffer(b[:4], "<i4")[0])
            r = np.frombuffer(b[4:], "<i2").reshape(n, n).astype(np.int64)
            self.cache[key] = (np.cumsum(np.cumsum(r, axis=0), axis=1) + base) * q
        return self.cache[key]

    def sample(self, lat, lon):
        shape = np.shape(lat)
        x, y = H.polar_stereo_xy(np.ravel(lat), np.ravel(lon), south=True)
        d, T, N = self.lv["res_m"], self.lv["tile_px"], self.lv["nt"] * self.lv["tile_px"]
        c = (x - self.lv["x0_m"]) / d
        r = (self.lv["y0_m"] - y) / d
        out = np.full(c.size, np.nan)
        ok = (r >= 0) & (c >= 0) & (r <= N) & (c <= N)
        r0 = np.minimum(np.floor(np.where(ok, r, 0)), N - 1).astype(np.int64)
        c0 = np.minimum(np.floor(np.where(ok, c, 0)), N - 1).astype(np.int64)
        ty, tx = r0 // T, c0 // T
        for k in set(zip(ty[ok].tolist(), tx[ok].tolist())):
            key = f"{k[0]}_{k[1]}"
            if key not in self.present:
                continue
            m = ok & (ty == k[0]) & (tx == k[1])
            t = self.tile(key)
            a, b = r0[m] - k[0] * T, c0[m] - k[1] * T
            u, v = r[m] - r0[m], c[m] - c0[m]
            out[m] = (1 - u) * ((1 - v) * t[a, b] + v * t[a, b + 1]) + u * ((1 - v) * t[a + 1, b] + v * t[a + 1, b + 1])
        return out.reshape(shape)


def level_text(lv, pidx):
    """Short level description for the app; sparse near-field patches (task F) say where they exist."""
    if lv.get("patch_radius_m"):
        return f'{lv["res_m"]:g} m to {lv["to_km"]:g} km (only within {lv["patch_radius_m"] / 1000:g} km of the 16 south-polar catalogue sites)'
    return f'{lv["res_m"]:g} m to {lv["to_km"]:g} km (points ≥ {-lv.get("lat_edge_deg", pidx["lat_edge_deg"]):g}°S)'


def band_of(lat):
    for name, lo, hi in BANDS:
        if lo <= lat <= hi:
            return name
    return None


def compare(b, ref, eph):
    e_rms, e_max, e_bias = V.rms(b["mask"], ref["mask"])
    fb = V.fractions(b["lat"], b["lon"], b["h0_m"], b["mask"], eph)
    fr = V.fractions(ref["lat"], ref["lon"], ref["h0_m"], ref["mask"], eph)
    return dict(rms_deg=round(e_rms, 3), max_abs_deg=round(e_max, 3), bias_deg=round(e_bias, 3),
                h0_diff_m=round(b["h0_m"] - ref["h0_m"], 1),
                sun_pp=round(100 * (fb[0] - fr[0]), 2), earth_pp=round(100 * (fb[1] - fr[1]), 2),
                both_pp=round(100 * (fb[2] - fr[2]), 2))


def summary(rows, key):
    if not rows:
        return None
    r = np.array([x[key]["rms_deg"] for x in rows])
    s = np.array([abs(x[key]["sun_pp"]) for x in rows])
    e = np.array([abs(x[key]["earth_pp"]) for x in rows])
    return dict(n=len(rows), rms_deg_median=round(float(np.median(r)), 3), rms_deg_max=round(float(r.max()), 3),
                max_abs_deg_max=round(float(max(x[key]["max_abs_deg"] for x in rows)), 3),
                abs_sun_pp_median=round(float(np.median(s)), 2), abs_sun_pp_max=round(float(s.max()), 2),
                abs_earth_pp_median=round(float(np.median(e)), 2), abs_earth_pp_max=round(float(e.max()), 2),
                n_sun_over_target=int((s > TARGET_SUN_PP).sum()),
                meets_target=bool(np.median(r) <= TARGET_RMS_MEDIAN and s.max() <= TARGET_SUN_PP))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--impl-n", type=int, default=6, help="points for the JS-vs-Python implementation check")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "custom_polar_validation.json")
    a = ap.parse_args()
    eph = V.load_ephem(2)
    before = {s["id"]: s for s in json.loads(a.before.read_text(encoding="utf-8"))["sites"]}
    after = {s["id"]: s for s in json.loads(a.after.read_text(encoding="utf-8"))["sites"]}
    pidx = json.loads((WEB / "hterrain" / "polar_s" / "index.json").read_text(encoding="utf-8"))
    rows = []
    for sid, b in after.items():
        if sid.startswith("RANDPOLAR_"):
            f, group = ROOT / "data" / "processed" / "custom_polar" / "ref" / f"{sid}.json", "random"
        else:
            f, group = WEB / "horizon" / f"{sid}.json", "catalogue"
            if not f.exists():   # e.g. SHACKLETON_RIM after the card-15 coordinate fix: same card-8 chain, run here
                f = ROOT / "data" / "processed" / "custom_polar" / "ref" / f"{sid}.json"
        if not f.exists():
            print("no reference for", sid)
            continue
        ref = json.loads(f.read_text(encoding="utf-8"))
        row = dict(id=sid, group=group, lat=b["lat"], lon=b["lon"], band=band_of(b["lat"]),
                   ref_dems=[d["name"] for d in ref["dem_sources"]],
                   browser_dems=[f'{d["name"]} to {d["to_km"]} km' for d in b["dem_sources"]],
                   after=compare(b, ref, eph))
        if sid in before:
            row["before"] = compare(before[sid], ref, eph)
        rows.append(row)
        bf = row.get("before", {})
        print(f'{sid:26s} {b["lat"]:7.2f} before RMS {bf.get("rms_deg", float("nan")):.3f} sun {bf.get("sun_pp", float("nan")):+6.2f} | '
              f'after RMS {row["after"]["rms_deg"]:.3f} (max {row["after"]["max_abs_deg"]:.2f}) sun {row["after"]["sun_pp"]:+6.2f} '
              f'earth {row["after"]["earth_pp"]:+6.2f}', flush=True)

    # implementation check: JS polar path vs Python twin on the same tiles
    near_idx = json.loads((WEB / "hterrain" / "index.json").read_text(encoding="utf-8"))
    near = V.WebTileSampler(WEB / "hterrain" / "tiles" / "near", near_idx["grids"]["near"], "near")
    far = V.WebTileSampler(WEB / "hterrain" / "tiles" / "far", near_idx["grids"]["far"], "far")
    impl = []
    for b in list(after.values())[: a.impl_n]:
        lvls = [lv for lv in pidx["levels"] if b["lat"] <= lv.get("lat_edge_deg", pidx["lat_edge_deg"])]
        chain = [(WebPolarSampler(lv, WEB / "hterrain" / "polar_s"), lv["to_km"]) for lv in lvls]
        chain += [(near, near_idx["grids"]["near"]["to_km"]), (far, near_idx["grids"]["far"]["to_km"])]
        p = b["params"]
        r = H.compute_horizon(b["lat"], b["lon"], chain, min_km=p["minKm"], max_km=p["maxKm"], n_steps=p["nSteps"])
        e_rms, e_max, _ = V.rms(b["mask"], r["mask"])
        impl.append(dict(id=b["id"], rms_deg=float(f"{e_rms:.3g}"), max_abs_deg=float(f"{e_max:.3g}"),
                         h0_js=round(b["h0_m"], 3), h0_py=round(r["h0_m"], 3)))
        print(f'impl {b["id"]:24s} JS vs Python: RMS {e_rms:.2e}, max {e_max:.2e} deg', flush=True)

    groups = {}
    for key in ("before", "after"):
        g = {"catalogue_16": summary([r for r in rows if r["group"] == "catalogue" and key in r], key),
             "random_30": summary([r for r in rows if r["group"] == "random" and key in r], key)}
        for name, _, _ in BANDS:
            g[f"random_{name}"] = summary([r for r in rows if r["group"] == "random" and r["band"] == name and key in r], key)
            g[f"all_{name}"] = summary([r for r in rows if r["band"] == name and key in r], key)
        groups[key] = g
    report = dict(target=dict(rms_deg_median=TARGET_RMS_MEDIAN, abs_sun_pp_per_point=TARGET_SUN_PP),
                  reference="card-8 chain via pipeline/horizon.py (PGDA 5/10/20/60/80/240 m + LDEM_64/16), min 5 m, 8000 steps",
                  ephem_window="2026-01-01..2030-12-31, 2 h step",
                  polar_levels=[{k: lv[k] for k in ("name", "source", "res_m", "q_m", "to_km", "lat_edge_deg", "bytes")}
                                for lv in pidx["levels"]],
                  implementation_js_vs_python=impl, summary=groups, points=rows)
    a.out.write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(groups["after"], indent=1))
    print("wrote", a.out)

    # small block the app reads for the accuracy label / badge (numbers from this run only)
    vf = WEB / "hterrain" / "validation.json"
    v = json.loads(vf.read_text(encoding="utf-8"))
    v["polar"] = dict(source="pipeline/validate_custom_polar.py -> docs/custom_polar_validation.json",
                      target=report["target"], lat_edge_deg=pidx["lat_edge_deg"],
                      levels=[level_text(lv, pidx) for lv in pidx["levels"]],
                      bands={name: groups["after"][f"all_{name}"] for name, _, _ in BANDS},
                      bands_before={name: groups["before"][f"all_{name}"] for name, _, _ in BANDS},
                      impl_rms_deg_max=max((r["rms_deg"] for r in impl), default=None))
    vf.write_text(json.dumps(v, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
