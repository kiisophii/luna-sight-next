"""Card 14: why do the PGDA numbers differ (VALIDATION row 11 vs card 14)? Factor-by-factor test.

Same 400 points (verify_card9.random_points, seed 42, 75-85 S), same PGDA product and reader
(verify_card9.Pgda: AVGVISIB_75S_120M, nearest 120 m pixel). Three groups, never mixed:

  A  stored maps, no recomputation: 948 m (ppd 32, merged) and 3.8 km (ppd 8) stores,
     nearest = the cell containing the point, bilinear = between the 4 nearest cell centres.
     Both stores average 2026-2030; the 948 m store uses a 3 h step, the 3.8 km store a 2 h step.
  B  point recomputation with the production engine (global_maps.Engine, LDEM_64/16, 360 az),
     only at the 400 evaluation points (or at their cell centres). Each run changes one thing.
     The engine's horizon masks are also fed to verify_card9.fractions(), so Earth "centre" and
     Earth "any part of the disc" come from the same horizon.
  C  card 9 independent code (verify_card9.py, 720 az, own marching), per-point cache
     data/processed/verify_card9_pgda_points.jsonl; 5 points recomputed fresh as a cache check.

    python pipeline/analyze_card14_pgda.py      -> docs/card14_pgda_analysis.json
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import global_maps as gm  # noqa: E402
import verify_card9 as v9  # noqa: E402

ROOT = gm.ROOT
PROC = ROOT / "data" / "processed"
STORE32 = PROC / "gmaps_ppd32_merged"
STORE8 = PROC / "gmaps_ppd8"
EPH_BIN = ROOT / "web" / "data" / "ephem.bin"
EPH_186 = PROC / "ephem_2020-2038_2h.npz"
GPU_FIRST_ROW = 3455        # Jiyong's manifest: rows 3103-3454 CPU, 3455-5759 CUDA FP64


def stats(ours, truth, lo=None, hi=None):
    a, b = np.asarray(ours, float), np.asarray(truth, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    d = (a - b) * 100
    s = {"n": int(ok.sum()), "mae_pp": round(float(np.abs(d).mean()), 3),
         "rmse_pp": round(float(np.sqrt((d ** 2).mean())), 3), "bias_pp": round(float(d.mean()), 3),
         "max_abs_pp": round(float(np.abs(d).max()), 3), "r": round(float(np.corrcoef(a, b)[0, 1]), 4)}
    if lo is not None:
        lo_, hi_ = np.asarray(lo)[ok], np.asarray(hi)[ok]
        s["inside_pgda_3x3_pct"] = round(float(((a >= lo_) & (a <= hi_)).mean() * 100), 1)
    return s


def diff(a, b):
    d = (np.asarray(a, float) - np.asarray(b, float)) * 100
    return {"mae_pp": round(float(np.abs(d).mean()), 4), "max_abs_pp": round(float(np.abs(d).max()), 4),
            "bias_pp": round(float(d.mean()), 4)}


def store(folder):
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    ppd = int(meta["ppd"])
    arr = {f: np.load(folder / f"{f}.npy", mmap_mode="r") for f in ("sun", "earth", "both", "h0", "maskmax")}
    return ppd, meta["signature"], arr


def cell_index(lat, lon, ppd):
    r = np.clip(np.floor((90.0 - lat) * ppd).astype(int), 0, 180 * ppd - 1)
    c = np.clip(np.floor((lon + 180.0) * ppd).astype(int), 0, 360 * ppd - 1)
    return r, c


def cell_centre(r, c, ppd):
    return 90.0 - (r + 0.5) / ppd, -180.0 + (c + 0.5) / ppd


def bilinear(a, lat, lon, ppd):
    """Interpolate between the 4 nearest cell centres (longitude wraps)."""
    nlat, nlon = 180 * ppd, 360 * ppd
    y = (90.0 - lat) * ppd - 0.5
    x = (lon + 180.0) * ppd - 0.5
    r0 = np.clip(np.floor(y).astype(int), 0, nlat - 2)
    c0 = np.floor(x).astype(int)
    fy, fx = np.clip(y - r0, 0, 1), x - c0
    c0w, c1w = c0 % nlon, (c0 + 1) % nlon
    v = lambda r, c: np.asarray(a[r, c], float)  # noqa: E731
    return ((1 - fy) * ((1 - fx) * v(r0, c0w) + fx * v(r0, c1w)) + fy * ((1 - fx) * v(r0 + 1, c0w) + fx * v(r0 + 1, c1w)))


def dist_km(lat1, lon1, lat2, lon2):
    p1, p2, dl = np.radians(lat1), np.radians(lat2), np.radians(lon2 - lon1)
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * gm.R_M * np.arcsin(np.sqrt(np.clip(h, 0, 1))) / 1000


def raw_vectors(path, step_h):
    """Ephemeris rows (km, MOON_ME: Sun xyz, Earth xyz) at step_h, as global_maps.load_ephem selects them."""
    path = Path(path)
    if path.suffix == ".npz":
        with np.load(path) as z:
            v = np.asarray(z["vectors"], np.float64)
            file_step = int(z["step_h"]) if "step_h" in z.files else 2
    else:
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        v = np.fromfile(path, dtype="<f4").astype(np.float64).reshape(int(meta["n"]), 6)
        file_step = int(meta.get("step_h", 1))
    return v[:: step_h // file_step]


class Runner:
    def __init__(self):
        self.near, self.far = gm.load_dems(ROOT / "data" / "raw", "LDEM_64", "LDEM_16")
        self.l16 = self.far

    def run(self, lat, lon, eph_path, step_h, near=None, label=""):
        near = near or self.near
        eph = gm.load_ephem(eph_path, step_h)
        eng = gm.Engine(near, self.far, eph, naz=360, near_km=150.0, max_km=300.0, step_frac=0.01)
        t0 = time.time()
        out, masks = eng.points(lat, lon, keep_masks=True)
        vec = raw_vectors(eph_path, step_h)
        az = np.arange(eng.naz) * 360.0 / eng.naz
        fr = [v9.fractions(float(lat[k]), float(lon[k]), float(out[k, 3]), az, masks[k], vec) for k in range(lat.size)]
        res = {"sun": out[:, 0], "earth_ctr": out[:, 1], "both": out[:, 2], "h0": out[:, 3], "maskmax": out[:, 4],
               "sun_mean_v9": np.array([f["sun_mean"] for f in fr]),
               "earth_ctr_v9": np.array([f["earth_ctr"] for f in fr]),
               "earth_any_v9": np.array([f["earth_any"] for f in fr]),
               "sig": eng.signature(), "seconds": round(time.time() - t0, 1), "label": label}
        print(f"  {label}: {lat.size} points, {res['seconds']} s, ephem {eph['n_used']} x {step_h} h", flush=True)
        return res


def main():
    t_start = time.time()
    lat, lon = v9.random_points(400, 42)
    raw = ROOT / "data" / "raw" / "pgda"
    pg_s, pg_e = v9.Pgda(raw / "AVGVISIB_75S_120M_201608.TIF"), v9.Pgda(raw / "AVGVISIB_75S_120M_201608_EARTH.TIF")
    ps, ps_lo, ps_hi = pg_s.sample(lat, lon)
    pe, pe_lo, pe_hi = pg_e.sample(lat, lon)
    vs = lambda x: stats(x, ps, ps_lo, ps_hi)  # noqa: E731
    ve = lambda x: stats(x, pe, pe_lo, pe_hi)  # noqa: E731
    rep = {"what": "card 14 PGDA discrepancy analysis (VALIDATION row 11 vs card 14 map numbers)",
           "points": {"n": 400, "seed": 42, "lat_range": [-85, -75], "sampling": "uniform by area (verify_card9.random_points)"},
           "pgda": {"files": ["AVGVISIB_75S_120M_201608.TIF", "AVGVISIB_75S_120M_201608_EARTH.TIF"],
                    "reader": "verify_card9.Pgda, nearest 120 m pixel (floor), 3x3 range for 'inside'",
                    "definition": "hourly, 18.6 years (dates not stated); Sun = finite disc; Earth = any part of the disc"}}

    # ------------------------------------------------------------------ A: stored maps
    p32, sig32, a32 = store(STORE32)
    p8, sig8, a8 = store(STORE8)
    r32, c32 = cell_index(lat, lon, p32)
    r8, c8 = cell_index(lat, lon, p8)
    clat32, clon32 = cell_centre(r32, c32, p32)
    clat8, clon8 = cell_centre(r8, c8, p8)
    d32, d8 = dist_km(lat, lon, clat32, clon32), dist_km(lat, lon, clat8, clon8)
    A = {}
    for key, ppd, arr, r, c, sig in (("948m", p32, a32, r32, c32, sig32), ("3.8km", p8, a8, r8, c8, sig8)):
        near = {f: np.asarray(arr[f][r, c], float) for f in ("sun", "earth")}
        bil = {f: bilinear(arr[f], lat, lon, ppd) for f in ("sun", "earth")}
        A[key] = {"store": str((STORE32 if key == "948m" else STORE8).relative_to(ROOT)),
                  "ephem": {k: sig["ephem"][k] for k in ("start", "step_h", "n_used", "sha1_12")},
                  "nearest": {"sun_mean": vs(near["sun"]), "earth_centre": ve(near["earth"])},
                  "bilinear": {"sun_mean": vs(bil["sun"]), "earth_centre": ve(bil["earth"])}}
        A[key]["_near"] = near
    A["948m"]["point_to_cell_centre_km"] = {"mean": round(float(d32.mean()), 3), "max": round(float(d32.max()), 3)}
    A["3.8km"]["point_to_cell_centre_km"] = {"mean": round(float(d8.mean()), 3), "max": round(float(d8.max()), 3)}
    A["rows_of_the_400_cells_948m"] = {"min": int(r32.min()), "max": int(r32.max()),
                                       "all_in_gpu_rows_3455_5759": bool((r32 >= GPU_FIRST_ROW).all())}

    # ------------------------------------------------------------------ B: point recomputation
    R = Runner()
    B = {}
    runs = [("B1_points_2026-2030_3h", lat, lon, EPH_BIN, 3, None),
            ("B2_points_2026-2030_2h", lat, lon, EPH_BIN, 2, None),
            ("B3_points_2020-2038_2h", lat, lon, EPH_186, 2, None),
            ("B4_948m_cell_centres_2026-2030_3h", clat32, clon32, EPH_BIN, 3, None),
            ("B5_3.8km_cell_centres_2026-2030_2h", clat8, clon8, EPH_BIN, 2, None),
            ("B6_points_2026-2030_3h_near_LDEM_16", lat, lon, EPH_BIN, 3, R.l16)]
    res = {}
    for name, la, lo, ep, st, near in runs:
        res[name] = x = R.run(la, lo, ep, st, near, name)
        B[name] = {"ephem": {k: x["sig"]["ephem"][k] for k in ("file", "start", "step_h", "n_used", "sha1_12")},
                   "near_dem": x["sig"]["near"]["name"], "seconds": x["seconds"],
                   "sun_mean": vs(x["sun"]), "earth_centre": ve(x["earth_ctr"]), "earth_any_disc": ve(x["earth_any_v9"]),
                   "engine_vs_v9_fractions_same_mask": {"sun": diff(x["sun"], x["sun_mean_v9"]),
                                                        "earth_ctr": diff(x["earth_ctr"], x["earth_ctr_v9"])}}

    # ------------------------------------------------------------------ factor effects (pp, |difference| between two runs)
    b = res
    F = {
        "1_period_5y_vs_18.6y (B2 vs B3, both 2 h, exact points)": {
            "sun": diff(b["B2_points_2026-2030_2h"]["sun"], b["B3_points_2020-2038_2h"]["sun"]),
            "earth_centre": diff(b["B2_points_2026-2030_2h"]["earth_ctr"], b["B3_points_2020-2038_2h"]["earth_ctr"]),
            "pgda_mae_change_sun_pp": round(B["B2_points_2026-2030_2h"]["sun_mean"]["mae_pp"] - B["B3_points_2020-2038_2h"]["sun_mean"]["mae_pp"], 3)},
        "2_step_3h_vs_2h (B1 vs B2, 2026-2030, exact points)": {
            "sun": diff(b["B1_points_2026-2030_3h"]["sun"], b["B2_points_2026-2030_2h"]["sun"]),
            "earth_centre": diff(b["B1_points_2026-2030_3h"]["earth_ctr"], b["B2_points_2026-2030_2h"]["earth_ctr"])},
        "3a_948m_cell_centre_vs_point (B4 vs B1, 3 h)": {
            "sun": diff(b["B4_948m_cell_centres_2026-2030_3h"]["sun"], b["B1_points_2026-2030_3h"]["sun"]),
            "earth_centre": diff(b["B4_948m_cell_centres_2026-2030_3h"]["earth_ctr"], b["B1_points_2026-2030_3h"]["earth_ctr"]),
            "distance_km": A["948m"]["point_to_cell_centre_km"]},
        "3b_3.8km_cell_centre_vs_point (B5 vs B2, 2 h)": {
            "sun": diff(b["B5_3.8km_cell_centres_2026-2030_2h"]["sun"], b["B2_points_2026-2030_2h"]["sun"]),
            "earth_centre": diff(b["B5_3.8km_cell_centres_2026-2030_2h"]["earth_ctr"], b["B2_points_2026-2030_2h"]["earth_ctr"]),
            "distance_km": A["3.8km"]["point_to_cell_centre_km"]},
        "4_near_terrain_LDEM_16_vs_LDEM_64 (B6 vs B1)": {
            "sun": diff(b["B6_points_2026-2030_3h_near_LDEM_16"]["sun"], b["B1_points_2026-2030_3h"]["sun"]),
            "earth_centre": diff(b["B6_points_2026-2030_3h_near_LDEM_16"]["earth_ctr"], b["B1_points_2026-2030_3h"]["earth_ctr"]),
            "note": "only a coarser-terrain sensitivity; no DEM finer than 474 m covers the 400 points here"},
        "5_earth_any_disc_vs_centre (same masks)": {
            k: diff(b[k]["earth_any_v9"], b[k]["earth_ctr_v9"]) for k in ("B1_points_2026-2030_3h", "B3_points_2020-2038_2h")},
    }
    # error vs terrain roughness: |ours - PGDA| against the PGDA 3x3 spread and our mask height
    e1 = np.abs(b["B1_points_2026-2030_3h"]["sun"] - ps)
    F["4b_sun_error_correlations (B1)"] = {
        "with_pgda_3x3_spread": round(float(np.corrcoef(e1, ps_hi - ps_lo)[0, 1]), 3),
        "with_maskmax": round(float(np.corrcoef(e1, b["B1_points_2026-2030_3h"]["maskmax"])[0, 1]), 3)}

    # ------------------------------------------------------------------ 6: CPU (this laptop) vs CUDA (stored 948 m cells)
    b4 = res["B4_948m_cell_centres_2026-2030_3h"]
    cpu_gpu = {}
    for f_store, f_run in (("sun", "sun"), ("earth", "earth_ctr"), ("both", "both"), ("h0", "h0"), ("maskmax", "maskmax")):
        gpu = np.asarray(a32[f_store][r32, c32], np.float32)
        cpu = b4[f_run].astype(np.float32)
        dd = np.abs(cpu.astype(float) - gpu.astype(float))
        cpu_gpu[f_store] = {"max_abs": float(dd.max()), "n_identical_float32": int((dd == 0).sum()), "n": int(dd.size)}
    b5 = res["B5_3.8km_cell_centres_2026-2030_2h"]
    st8 = {f: float(np.abs(b5[g].astype(np.float32).astype(float) - np.asarray(a8[f][r8, c8], np.float32).astype(float)).max())
           for f, g in (("sun", "sun"), ("earth", "earth_ctr"), ("h0", "h0"))}
    F["6_cpu_vs_cuda_on_the_400_cells"] = {
        "what": "stored 948 m values at the 400 cells (all in CUDA rows) vs this laptop's CPU engine at the same cell centres",
        "fields": cpu_gpu, "store_3.8km_vs_recompute_max_abs": st8}

    # ------------------------------------------------------------------ C: card 9 independent code (row 11 'independent' and 'Earth any')
    cache = [json.loads(x) for x in (PROC / "verify_card9_pgda_points.jsonl").read_text(encoding="utf-8").splitlines()]
    cache = {d["k"]: d for d in cache if d.get("seed") == 42 and d.get("n_total") == 400}
    rows = [cache[k] for k in range(400)]
    g = lambda key: np.array([r[key] for r in rows])  # noqa: E731
    assert np.allclose(g("lat"), lat) and np.allclose(g("lon"), lon)
    C = {"code": "pipeline/verify_card9.py (720 az, 200 m / 500 m steps, own DEM reader), ephem 2020-2038 2 h",
         "sun_mean": stats(g("sun_mean"), ps, ps_lo, ps_hi), "earth_any_disc": stats(g("earth_any"), pe, pe_lo, pe_hi),
         "earth_centre": stats(g("earth_ctr"), pe, pe_lo, pe_hi)}
    # fresh recomputation of 5 cached points (cache check)
    eph186 = np.load(EPH_186)["vectors"].astype(np.float64)
    l64, l16 = v9.ldem(64), v9.ldem(16)
    az720 = np.arange(720) * 0.5
    fresh = []
    for k in (0, 99, 199, 299, 399):
        h0 = float(l64.sample(lat[k], lon[k]))
        mask, _, _ = v9.brute_mask(lat[k], lon[k], az720, lambda la, lo, d: np.where(d <= 150e3, l64.sample(la, lo), l16.sample(la, lo)),
                                   h0, 150e3, d_near=200.0, d_far=500.0, d_min=200.0)
        fr = v9.fractions(lat[k], lon[k], h0, az720, mask, eph186)
        fresh.append(max(abs(fr[x] - cache[k][x]) for x in ("sun_mean", "earth_any", "earth_ctr")))
    C["fresh_recompute_5_points_max_abs_vs_cache"] = round(float(max(fresh)), 6)
    C["engine_B3_vs_independent_sun"] = diff(res["B3_points_2020-2038_2h"]["sun"], g("sun_mean"))

    # ------------------------------------------------------------------ side-by-side table (stored maps, same 2026-2030 window)
    for k in ("948m", "3.8km"):
        A[k].pop("_near")
    rep.update(A_stored_maps=A, B_point_recompute=B, C_card9_independent=C, factors=F,
               row11_sources={
                   "engine Sun MAE 2.19 pp, r 0.938": "global_maps.py validate --n 400 = engine at the exact points, "
                                                      "ephem 2020-2038 2 h, Earth centre -> reproduced by B3",
                   "independent Sun MAE 2.12 pp, r 0.940": "verify_card9.py sun_mean -> C.sun_mean",
                   "Earth (any) MAE 1.73 pp, r 0.989": "verify_card9.py earth_any (720 az, 2020-2038 2 h) -> C.earth_any_disc",
                   "note": "none of these values is read from a stored map"},
               seconds=round(time.time() - t_start, 1))
    out = ROOT / "docs" / "card14_pgda_analysis.json"
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print("->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
