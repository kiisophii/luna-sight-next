"""Card 14: the stored 948 m (ppd 32) and 3.8 km (ppd 8) maps vs NASA PGDA AVGVISIB_75S_120M at 400 points.

Same 400 points as the card 9 check (pipeline/verify_card9.py: seed 42, uniform by area in 75-85 S)
and the same PGDA reader (tifffile + GeoTIFF tie point). Here nothing is recomputed: the values
are read from the map stores (nearest grid cell = the cell that contains the point).

Known differences of definition (so the numbers are a consistency check, not an error budget):
  * time window: our maps average 2026-2030 (5 years, contract ephemeris); PGDA averages 18.6 years;
  * Earth: our map counts the Earth CENTRE above the mask; PGDA counts any part of the Earth disc;
  * terrain: our near terrain is LDEM_64 (474 m); PGDA uses finer polar terrain (not stated).

    python pipeline/validate_card14_pgda.py [--n 400 --seed 42]
    -> docs/card14_pgda.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_card9 as v9  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STORES = {"ppd32_948m": ROOT / "data" / "processed" / "gmaps_ppd32_merged",
          "ppd8_3.8km": ROOT / "data" / "processed" / "gmaps_ppd8"}


def sample_store(folder, lat, lon):
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    ppd = int(meta["ppd"])
    done = np.load(folder / "done.npy", mmap_mode="r")
    r = np.clip(np.floor((90.0 - lat) * ppd).astype(int), 0, 180 * ppd - 1)
    c = np.clip(np.floor((lon + 180.0) * ppd).astype(int), 0, 360 * ppd - 1)
    if not np.asarray(done)[r].all():
        raise SystemExit(f"{folder}: some sampled rows are not done")
    out = {f: np.asarray(np.load(folder / f"{f}.npy", mmap_mode="r")[r, c], dtype=np.float64)
           for f in ("sun", "earth", "both", "h0", "maskmax")}
    return out, meta["signature"], ppd


def stats(ours, truth, lo=None, hi=None):
    a, b = np.asarray(ours), np.asarray(truth)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    d = (a - b) * 100
    s = {"n": int(ok.sum()), "mae_pp": round(float(np.abs(d).mean()), 3),
         "rmse_pp": round(float(np.sqrt((d ** 2).mean())), 3), "bias_pp": round(float(d.mean()), 3),
         "max_abs_pp": round(float(np.abs(d).max()), 3), "r": round(float(np.corrcoef(a, b)[0, 1]), 4)}
    if lo is not None:
        l, h = np.asarray(lo)[ok], np.asarray(hi)[ok]
        s["inside_pgda_3x3_range_pct"] = round(float(((a >= l) & (a <= h)).mean() * 100), 1)
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(ROOT / "docs" / "card14_pgda.json"))
    a = ap.parse_args(argv)
    raw = ROOT / "data" / "raw" / "pgda"
    pg_s = v9.Pgda(raw / "AVGVISIB_75S_120M_201608.TIF")
    pg_e = v9.Pgda(raw / "AVGVISIB_75S_120M_201608_EARTH.TIF")
    lat, lon = v9.random_points(a.n, a.seed)
    ps, ps_lo, ps_hi = pg_s.sample(lat, lon)
    pe, pe_lo, pe_hi = pg_e.sample(lat, lon)
    rep = {"what": "card 14: stored global maps vs PGDA AVGVISIB_75S_120M (no recomputation)",
           "points": {"n": a.n, "seed": a.seed, "lat_range": [-85, -75], "sampling": "uniform by area (same as card 9)",
                      "map_sampling": "grid cell containing the point (row = floor((90 - lat) * ppd))"},
           "pgda": {"files": ["AVGVISIB_75S_120M_201608.TIF", "AVGVISIB_75S_120M_201608_EARTH.TIF"],
                    "source": "https://pgda.gsfc.nasa.gov/products/69",
                    "definition": "18.6-year averages; Earth = any part of the disc visible"},
           "maps": {}}
    vals = {}
    for key, folder in STORES.items():
        m, sig, ppd = sample_store(folder, lat, lon)
        vals[key] = m
        err = np.abs(m["sun"] - ps) * 100
        rep["maps"][key] = {
            "store": str(folder.relative_to(ROOT)), "ppd": ppd,
            "ephem": {k: sig["ephem"][k] for k in ("step_h", "n_used", "sha1_12", "start", "mock")},
            "dems": [sig["near"]["name"], sig["far"]["name"]],
            "sun_vs_pgda_sun": stats(m["sun"], ps, ps_lo, ps_hi),
            "earth_centre_vs_pgda_earth": stats(m["earth"], pe, pe_lo, pe_hi),
            "corr_sun_error_vs_pgda_3x3_spread": round(float(np.corrcoef(err, (ps_hi - ps_lo) * 100)[0, 1]), 3),
            "corr_sun_error_vs_maskmax": round(float(np.corrcoef(err, m["maskmax"])[0, 1]), 3),
        }
    a32, a8 = vals["ppd32_948m"], vals["ppd8_3.8km"]
    rep["ppd32_vs_ppd8_same_points"] = {f: stats(a32[f], a8[f]) for f in ("sun", "earth", "both")}
    worst = np.argsort(-np.abs(a32["sun"] - ps))[:10]
    rep["largest_sun_errors_ppd32"] = [
        {"lat": round(float(lat[k]), 4), "lon": round(float(lon[k]), 4), "ours": round(float(a32["sun"][k]), 4),
         "pgda": round(float(ps[k]), 4), "pgda_3x3": [round(float(ps_lo[k]), 4), round(float(ps_hi[k]), 4)],
         "maskmax_deg": round(float(a32["maskmax"][k]), 2), "h0_m": round(float(a32["h0"][k]), 1)} for k in worst]
    c9 = ROOT / "docs" / "card9_verification.json"
    if c9.exists():
        c = json.loads(c9.read_text(encoding="utf-8"))   # same 400 points, recomputed over 2020-2038
        rep["card9_same_points_2020_2038_for_context"] = {
            "independent_code": {k: v for k, v in c.get("pgda_independent", {}).items() if k.endswith("pgda_sun")
                                 or k.endswith("pgda_earth")},
            "global_maps_engine": c.get("pgda_engine_global_maps_validate")}
    Path(a.out).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    for key, m in rep["maps"].items():
        print(key, "sun", m["sun_vs_pgda_sun"], "\n   earth", m["earth_centre_vs_pgda_earth"])
    print("948 m vs 3.8 km:", rep["ppd32_vs_ppd8_same_points"])
    print("->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
