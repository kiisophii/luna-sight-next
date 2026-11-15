"""Task O (2026-11-15, Dongju): independent FULL recomputation of web/data/gmaps_ppd32/
(948 m whole-Moon map) for every cell between 75 deg S and 90 deg S.

Own code only: nothing is imported from pipeline/ or web/js/. Definitions are taken from
docs/data_contract.md sections 6, 10 and 21 and from web/js/core.js:
  * grid: ppd 32, cell centre lat = 90 - (r + 0.5)/32, lon = -180 + (c + 0.5)/32 (rows 5280..5759),
  * terrain: LOLA LDEM_64 (near, to 150 km) and LDEM_16 (far, to 300 km), bilinear between pixel
    centres, read with my own PDS-label reader; heights above R = 1737.4 km,
  * horizon: 360 azimuths (1 deg), distances s0 = half a LDEM_64 pixel, then
    s += max(pixel of the DEM in use, 0.01 s) up to 300 km (contract: step_frac 0.01, n_steps 283),
    exact spherical geometry, observer 2 m above the cell-centre terrain,
  * time: web/data/ephem.bin every 3rd hourly row (3 h step, 14,608 samples, contract section 21),
  * sun = mean visible fraction of the solar disk (radius 0.2666 deg, mask locally flat, core.js
    formula), earth = Earth centre above the mask, both = disk fraction >= 0.5 AND Earth visible;
    topocentric azimuth and elevation as in core.js; mask linearly interpolated between bins.

Ray early stop uses an exact bound: the highest LDEM_64/LDEM_16 height south of 65 deg S (every
ray from a cell south of 75 deg S stays south of 65 deg S within 300 km), so it never changes a
result.

    python pipeline/crosscheck_gmaps_polar_dongju.py run [--rows 5280:5760] [--threads N]
    python pipeline/crosscheck_gmaps_polar_dongju.py compare   # vs the published *_values.png
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from numba import njit, prange, set_num_threads

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
WORK = Path(os.environ.get("GMAPS_XCHECK_WORK", ROOT / "data" / "processed" / "crosscheck_gmaps_polar_dongju"))
RAW = Path(os.environ.get("LDEM_DIR", ROOT / "data" / "raw" / "global"))

R = 1737400.0
OBS_H = 2.0
SUN_R = math.radians(0.2666)
PPD = 32
NLAT, NLON = 180 * PPD, 360 * PPD
ROW0, ROW1 = 5280, 5760          # 75 S .. 90 S (row 5280 centre = -75.015625)
NAZ = 360
NEAR_KM, MAX_KM, FRAC = 150.0, 300.0, 0.01
EPH_STEP = 3
FIELDS = ("sun", "earth", "both", "h0", "maskmax")


# ============================================================ DEM (own PDS reader)
def read_label(lbl):
    t = Path(lbl).read_text(encoding="latin-1")

    def num(key):
        m = re.search(rf"^\s*{key}\s*=\s*([-+0-9.eE]+)", t, re.M)
        if not m:
            raise ValueError(f"{key} missing in {lbl}")
        return float(m.group(1))
    lab = dict(lines=int(num("LINES")), samples=int(num("LINE_SAMPLES")), ppd=num("MAP_RESOLUTION"),
               lpo=num("LINE_PROJECTION_OFFSET"), spo=num("SAMPLE_PROJECTION_OFFSET"),
               clon=num("CENTER_LONGITUDE"), scale=num("SCALING_FACTOR"))
    if "KILOMETER" not in t:
        raise ValueError("expected heights in km")
    # Pixel-centre convention used below: row r centre = 90 - (r + 0.5)/ppd, column c centre = (c + 0.5)/ppd E.
    # Check that the label says the same thing (PDS: line = LPO - lat*ppd, sample = SPO + (lon - clon)*ppd, 0-based).
    p = lab["ppd"]
    assert abs(lab["lpo"] - (90 * p - 0.5)) < 1e-9 and abs(lab["spo"] + (0.5 / p - lab["clon"]) * p) < 1e-9, lab
    assert lab["lines"] == 180 * p and lab["samples"] == 360 * p
    return lab


def load_dem(name):
    img = RAW / f"{name}_float.img"
    lab = read_label(img.with_suffix(".lbl"))
    d = np.fromfile(img, dtype="<f4").reshape(lab["lines"], lab["samples"])
    return d, lab


@njit(cache=True)
def dem_h(d, ppd, lat, lon):
    """Bilinear height (km) between pixel centres; rows clamp at the poles, columns wrap."""
    nl, ns = d.shape
    y = (90.0 - lat) * ppd - 0.5
    if y < 0.0:
        y = 0.0
    if y > nl - 1.0:
        y = nl - 1.0
    r0 = int(math.floor(y))
    if r0 > nl - 2:
        r0 = nl - 2
    fy = y - r0
    x = ((lon % 360.0) * ppd) - 0.5
    c0f = math.floor(x)
    fx = x - c0f
    c0 = int(c0f) % ns
    c1 = (c0 + 1) % ns
    return ((1.0 - fy) * ((1.0 - fx) * d[r0, c0] + fx * d[r0, c1])
            + fy * ((1.0 - fx) * d[r0 + 1, c0] + fx * d[r0 + 1, c1]))


def steps(near_res, far_res):
    s, out, which = 0.5 * near_res, [], []
    while s <= MAX_KM * 1000.0 + 1e-6:
        near = s <= NEAR_KM * 1000.0
        out.append(s)
        which.append(0 if near else 1)
        s += max(near_res if near else far_res, FRAC * s)
    return np.array(out), np.array(which, np.int8)


# ============================================================ kernel
@njit(parallel=True, cache=True)
def cells(lat, lon, dn, pn, df, pf, th, which, rtop, su, sd, eu, ed, out):
    cth, sth = np.cos(th), np.sin(th)
    n = lat.size
    nt = sd.size
    ns = th.size
    two_pi = 2.0 * math.pi
    for i in prange(n):
        la, lo = math.radians(lat[i]), math.radians(lon[i])
        sl, cl, so, co = math.sin(la), math.cos(la), math.sin(lo), math.cos(lo)
        up = (cl * co, cl * so, sl)
        ea = (-so, co, 0.0)
        no = (-sl * co, -sl * so, cl)
        h0 = dem_h(dn, pn, lat[i], lon[i]) * 1000.0
        ro = R + h0 + OBS_H
        rt_b = max(rtop, ro + 1.0)      # keeps the stop bound decreasing with distance
        mask = np.empty(NAZ)
        for a in range(NAZ):
            az = two_pi * a / NAZ
            ca, sa = math.cos(az), math.sin(az)
            dx, dy, dz = no[0] * ca + ea[0] * sa, no[1] * ca + ea[1] * sa, no[2] * ca + ea[2] * sa
            best = -1e300
            for k in range(ns):
                ct, st = cth[k], sth[k]
                # exact stop: even a peak of height rtop here or further out cannot beat best
                if (rt_b * ct - ro) / (rt_b * st) < best:
                    break
                px, py, pz = up[0] * ct + dx * st, up[1] * ct + dy * st, up[2] * ct + dz * st
                plat = math.degrees(math.asin(min(1.0, max(-1.0, pz))))
                plon = math.degrees(math.atan2(py, px))
                if which[k] == 0:
                    h = dem_h(dn, pn, plat, plon)
                else:
                    h = dem_h(df, pf, plat, plon)
                rt = R + h * 1000.0
                t = (rt * ct - ro) / (rt * st)
                if t > best:
                    best = t
            mask[a] = math.atan(best)
        mmin, mmax = mask.min(), mask.max()
        ox, oy, oz = up[0] * ro, up[1] * ro, up[2] * ro
        acc = 0.0
        ne = 0
        nb = 0
        for t in range(nt):
            # Sun, topocentric (core.js sunAzEl)
            vx, vy, vz = su[t, 0] * sd[t] - ox, su[t, 1] * sd[t] - oy, su[t, 2] * sd[t] - oz
            vu = vx * up[0] + vy * up[1] + vz * up[2]
            vn = math.sqrt(vx * vx + vy * vy + vz * vz)
            el = math.asin(vu / vn)
            if el - SUN_R >= mmax:
                f = 1.0
            elif el + SUN_R <= mmin:
                f = 0.0
            else:
                ve = vx * ea[0] + vy * ea[1] + vz * ea[2]
                vno = vx * no[0] + vy * no[1] + vz * no[2]
                x = (math.atan2(ve, vno) % two_pi) / two_pi * NAZ
                k0 = int(math.floor(x)) % NAZ
                fr = x - math.floor(x)
                m = mask[k0] + (mask[(k0 + 1) % NAZ] - mask[k0]) * fr
                y = (m - el) / SUN_R
                if y <= -1.0:
                    f = 1.0
                elif y >= 1.0:
                    f = 0.0
                else:
                    f = (math.acos(y) - y * math.sqrt(1.0 - y * y)) / math.pi
            acc += f
            # Earth centre, topocentric (core.js earthAzEl / earthVisible)
            vx, vy, vz = eu[t, 0] * ed[t] - ox, eu[t, 1] * ed[t] - oy, eu[t, 2] * ed[t] - oz
            vu = vx * up[0] + vy * up[1] + vz * up[2]
            vn = math.sqrt(vx * vx + vy * vy + vz * vz)
            el = math.asin(vu / vn)
            if el > mmax:
                vis = True
            elif el <= mmin:
                vis = False
            else:
                ve = vx * ea[0] + vy * ea[1] + vz * ea[2]
                vno = vx * no[0] + vy * no[1] + vz * no[2]
                x = (math.atan2(ve, vno) % two_pi) / two_pi * NAZ
                k0 = int(math.floor(x)) % NAZ
                fr = x - math.floor(x)
                m = mask[k0] + (mask[(k0 + 1) % NAZ] - mask[k0]) * fr
                vis = el > m
            if vis:
                ne += 1
                if f >= 0.5:
                    nb += 1
        out[i, 0] = acc / nt
        out[i, 1] = ne / nt
        out[i, 2] = nb / nt
        out[i, 3] = h0
        out[i, 4] = math.degrees(mmax)


# ============================================================ run (resumable per row)
def store():
    WORK.mkdir(parents=True, exist_ok=True)
    arrs = {}
    for f in FIELDS:
        p = WORK / f"{f}.npy"
        if not p.exists():
            np.lib.format.open_memmap(p, mode="w+", dtype=np.float64, shape=(ROW1 - ROW0, NLON))[:] = np.nan
        arrs[f] = np.lib.format.open_memmap(p, mode="r+")
    done = WORK / "done.npy"
    if not done.exists():
        np.save(done, np.zeros(ROW1 - ROW0, np.uint8))
    return arrs, done


def inputs():
    dn, ln = load_dem("ldem_64")
    df, lf = load_dem("ldem_16")
    res_n = 2 * math.pi * R / (360 * ln["ppd"])
    res_f = 2 * math.pi * R / (360 * lf["ppd"])
    dist, which = steps(res_n, res_f)
    # exact terrain bound south of 65 S (rows of both DEMs whose centre is <= -65 + one pixel)
    hb = max(float(dn[int((90 + 65) * ln["ppd"]) - 1:].max()), float(df[int((90 + 65) * lf["ppd"]) - 1:].max()))
    rtop = R + hb * 1000.0 + 1.0
    v = np.fromfile(WEB / "ephem.bin", dtype="<f4").astype(np.float64).reshape(-1, 6)[::EPH_STEP] * 1000.0
    sd, ed = np.linalg.norm(v[:, :3], axis=1), np.linalg.norm(v[:, 3:], axis=1)
    return dict(dn=dn, pn=ln["ppd"], df=df, pf=lf["ppd"], th=dist / R, which=which, rtop=rtop, hb_km=hb,
                su=np.ascontiguousarray(v[:, :3] / sd[:, None]), sd=sd,
                eu=np.ascontiguousarray(v[:, 3:] / ed[:, None]), ed=ed, n_steps=int(dist.size),
                res_m=(res_n, res_f))


def cmd_run(a):
    if a.threads:
        set_num_threads(a.threads)
    inp = inputs()
    print(f"steps {inp['n_steps']}, terrain bound {inp['hb_km']:.3f} km, ephem samples {inp['sd'].size}, "
          f"res {inp['res_m'][0]:.1f}/{inp['res_m'][1]:.1f} m", flush=True)
    arrs, done_p = store()
    lon = -180.0 + (np.arange(NLON) + 0.5) / PPD
    r0, r1 = (int(x) for x in a.rows.split(":"))
    order = list(range(r0, r1))
    if a.reverse:
        order.reverse()
    for r in order:
        done = np.load(done_p)
        if done[r - ROW0]:
            continue
        t0 = time.time()
        lat = np.full(NLON, 90.0 - (r + 0.5) / PPD)
        out = np.empty((NLON, 5))
        cells(lat, lon, inp["dn"], inp["pn"], inp["df"], inp["pf"], inp["th"], inp["which"], inp["rtop"],
              inp["su"], inp["sd"], inp["eu"], inp["ed"], out)
        for j, f in enumerate(FIELDS):
            arrs[f][r - ROW0] = out[:, j]
            arrs[f].flush()
        done = np.load(done_p)          # another worker may have finished rows meanwhile
        done[r - ROW0] = 1
        np.save(done_p, done)
        print(f"row {r} lat {lat[0]:.4f}: {time.time() - t0:.1f} s, sun mean {out[:, 0].mean():.4f}", flush=True)


def cmd_bench(a):
    if a.threads:
        set_num_threads(a.threads)
    inp = inputs()
    print("steps", inp["n_steps"], "bound km", inp["hb_km"])
    lon = -180.0 + (np.arange(NLON) + 0.5) / PPD
    for r in (5280, 5520, 5759):
        idx = np.arange(0, NLON, NLON // a.n)
        lat = np.full(idx.size, 90.0 - (r + 0.5) / PPD)
        out = np.empty((idx.size, 5))
        t0 = time.time()
        cells(lat, lon[idx], inp["dn"], inp["pn"], inp["df"], inp["pf"], inp["th"], inp["which"], inp["rtop"],
              inp["su"], inp["sd"], inp["eu"], inp["ed"], out)
        dt = time.time() - t0
        print(f"row {r}: {idx.size} cells {dt:.2f} s -> {dt / idx.size * 1e3:.2f} ms/cell; sample {out[:3, :3]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("run")
    s.add_argument("--rows", default=f"{ROW0}:{ROW1}")
    s.add_argument("--threads", type=int)
    s.add_argument("--reverse", action="store_true")
    s = sub.add_parser("bench")
    s.add_argument("--n", type=int, default=256)
    s.add_argument("--threads", type=int)
    sub.add_parser("compare")
    a = ap.parse_args(argv)
    {"run": cmd_run, "bench": cmd_bench, "compare": lambda a: cmd_compare(a)}[a.cmd](a)


def box_resample(a, w, h):
    """Area mean to w x h with NaN = no data (PIL BOX on value*valid and on valid, ratio where valid > 0.5),
    the resampling rule stated in docs/data_contract.md section 21."""
    from PIL import Image
    ok = np.isfinite(a)
    num = np.asarray(Image.fromarray(np.where(ok, a, 0).astype(np.float32), "F").resize((w, h), Image.BOX))
    den = np.asarray(Image.fromarray(ok.astype(np.float32), "F").resize((w, h), Image.BOX))
    out = np.full((h, w), np.nan, np.float32)
    good = den > 0.5
    out[good] = num[good] / den[good]
    return out


def cmd_compare(a):
    import csv
    from PIL import Image
    done = np.load(WORK / "done.npy")
    if not done.all():
        raise SystemExit(f"run not finished: {int(done.sum())}/{done.size} rows")
    grid = {f: np.load(WORK / f"{f}.npy", mmap_mode="r") for f in FIELDS}
    W, H = 4096, 2048
    scale = NLAT / H
    p0 = int(math.ceil(ROW0 / scale))            # first PNG row whose whole footprint is south of 75 S
    res = dict(task="O", checker="Dongju Kim", product="web/data/gmaps_ppd32/ south of 75 S",
               cells=int(grid["sun"].size), rows=[ROW0, ROW1], png_rows=[p0, H], layers={})
    diff_rows = []
    for f in ("sun", "earth", "both"):
        full = np.full((NLAT, NLON), np.nan, np.float32)
        full[ROW0:ROW1] = grid[f]
        ov = box_resample(full, W, H)
        mine = np.round(np.clip(ov, 0, 1) * 250).astype(int)[p0:]
        ref = np.asarray(Image.open(WEB / "gmaps_ppd32" / f"{f}_values.png")).astype(int)[p0:]
        d = mine - ref
        un = ov[p0:] * 250.0
        ys, xs = np.nonzero(d)
        for y, x in zip(ys, xs):
            diff_rows.append(dict(layer=f, png_row=int(y + p0), png_col=int(x),
                                  lat_top=90 - (y + p0) * 180 / H, lon_left=-180 + x * 360 / W,
                                  dn_mine=int(mine[y, x]), dn_file=int(ref[y, x]), value_mine_x250=float(un[y, x]),
                                  frac_part=float(un[y, x] - math.floor(un[y, x]))))
        v = np.asarray(grid[f], np.float64)
        okp = np.isfinite(un) & (ref != 255)
        dpp = (ov[p0:] * 100.0 - ref * 0.4)[okp]           # my unrounded pixel value - published DN, in pp
        res["layers"][f + "_unrounded_vs_dn"] = dict(
            pixels=int(okp.sum()), max_abs_pp=float(np.abs(dpp).max()), median_abs_pp=float(np.median(np.abs(dpp))),
            within_0p1_pp=int((np.abs(dpp) <= 0.1).sum()), within_0p2_pp=int((np.abs(dpp) <= 0.2 + 1e-9).sum()))
        res["layers"][f] = dict(
            png_pixels=int(d.size), identical=int((d == 0).sum()), differing=int((d != 0).sum()),
            max_abs_dn=int(np.abs(d).max()), max_abs_pp=float(np.abs(d).max() * 0.4),
            median_abs_pp=float(np.median(np.abs(d)) * 0.4),
            mean_dn_diff=float(d.mean()), no_data_mine=int((ref == 255).sum()),
            grid_min=float(np.nanmin(v)), grid_max=float(np.nanmax(v)), grid_mean=float(np.nanmean(v)),
            grid_nan=int(np.isnan(v).sum()))
        print(f, res["layers"][f], flush=True)
    # stored float values published for individual cells (docs/gpu_cpu_300_cells.csv)
    cells = []
    for r in csv.DictReader(open(ROOT / "docs" / "gpu_cpu_300_cells.csv", encoding="utf-8")):
        row, col = int(r["row"]), int(r["col"])
        if ROW0 <= row < ROW1:
            cells.append(dict(row=row, col=col, lat=float(r["lat"]), lon=float(r["lon"]), backend=r["backend"],
                              **{f"{f}_diff_pp": 100 * (float(grid[f][row - ROW0, col]) - float(r[f"{f}_stored_fraction"]))
                                 for f in ("sun", "earth", "both")}))
    uniq = {(c["row"], c["col"]): c for c in cells}
    res["stored_cells"] = dict(n=len(uniq), max_abs_pp={f: max((abs(c[f"{f}_diff_pp"]) for c in uniq.values()), default=None)
                                                        for f in ("sun", "earth", "both")})
    res["stored_cells"]["cells"] = sorted(uniq.values(), key=lambda c: (c["row"], c["col"]))
    res["differing_pixels"] = diff_rows
    res["ephem_sha256"] = __import__("hashlib").sha256((WEB / "ephem.bin").read_bytes()).hexdigest()[:16]
    (ROOT / "docs" / "crosscheck_gmaps_polar_dongju.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    write_md(res)
    print(json.dumps({k: v for k, v in res.items() if k not in ("differing_pixels", "stored_cells")}, indent=1))
    print("stored cells", res["stored_cells"]["n"], res["stored_cells"]["max_abs_pp"])


def write_md(res):
    lay, sc = res["layers"], res["stored_cells"]
    p0 = res["png_rows"][0]
    L = ["# Task O — independent full recomputation of `web/data/gmaps_ppd32/` south of 75° S (Dongju Kim, 2026-11-15)", "",
         "Own code `pipeline/crosscheck_gmaps_polar_dongju.py` (no imports from `pipeline/` or `web/js/`): own PDS-label "
         "reader for LOLA LDEM_64 (to 150 km) and LDEM_16 (to 300 km), own 360-azimuth horizon march (exact spherical "
         "geometry, 2 m observer, contract steps), own loop over every 3rd row of `web/data/ephem.bin` "
         "(14,608 samples), `core.js` definitions (disk fraction, Earth centre, both = fraction ≥ 0.5 AND Earth). "
         "Machine-readable: `docs/crosscheck_gmaps_polar_dongju.json`.", "",
         f"**Coverage:** every cell of the 948 m grid between 75° S and 90° S: rows {res['rows'][0]}–{res['rows'][1] - 1} "
         f"× 11,520 columns = **{res['cells']:,} cells**, all computed (no sampling).", "",
         "## What could be compared", "",
         "The repository publishes this product only as 8-bit overview PNGs (`*_values.png`, 4096 × 2048, value = DN / 250, "
         "built with an area mean (PIL BOX on value × valid and on valid) and `round(clip × 250)`). One DN is **0.4 %p**, so "
         "the requested criterion of 0.1 %p **cannot be tested against the published file**: the file's own rounding "
         "is ± 0.2 %p. The producer's float grid is not in the repository. I therefore report:", "",
         f"1. **DN equality**: my {res['cells']:,} cells resampled with the same rule and rounded, compared with every "
         f"PNG pixel whose footprint lies fully south of 75° S (PNG rows {p0}–2047, "
         f"{lay['sun']['png_pixels']:,} pixels per layer). Any DN difference is listed below as a failing pixel.",
         "2. **Unrounded difference**: my area mean before rounding minus the published DN / 250, in %p (max, median); "
         "this can be at most 0.2 %p if the DN agrees.",
         f"3. **Float values at single cells**: the stored float fractions in `docs/gpu_cpu_300_cells.csv` for the "
         f"{sc['n']} cells that lie in the band; the only place the 0.1 %p criterion can be applied directly.", "",
         "## Result per metric", "",
         "| Metric | PNG pixels compared | DN identical | DN differing | Max \\|DN diff\\| (%p) | Median \\|DN diff\\| (%p) | "
         "Unrounded − file: max / median (%p) | Stored-float cells: max \\|diff\\| (%p) |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for f in ("sun", "earth", "both"):
        a, u = lay[f], lay[f + "_unrounded_vs_dn"]
        L.append(f"| {f} | {a['png_pixels']:,} | {a['identical']:,} | {a['differing']:,} | {a['max_abs_pp']:.1f} | "
                 f"{a['median_abs_pp']:.1f} | {u['max_abs_pp']:.4f} / {u['median_abs_pp']:.4f} | "
                 f"{sc['max_abs_pp'][f]:.2e} |")
    nd = len(res["differing_pixels"])
    L += ["", f"Grid summary (my cells): " + "; ".join(
        f"{f} min {lay[f]['grid_min']:.4f}, max {lay[f]['grid_max']:.4f}, mean {lay[f]['grid_mean']:.4f}, NaN {lay[f]['grid_nan']}"
        for f in ("sun", "earth", "both")) + ".", "",
        f"## Every failing PNG pixel ({nd})", ""]
    if nd:
        L += ["`frac` = fractional part of my unrounded value × 250: a value near 0.5 means my mean sits on a rounding "
              "boundary, so a difference far below 0.1 %p in the cells can flip the DN.", "",
              "| Layer | PNG row, col | Lat (top edge) | Lon (left edge) | DN mine | DN file | Mine × 250 | frac |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
        for d in res["differing_pixels"]:
            L.append(f"| {d['layer']} | {d['png_row']}, {d['png_col']} | {d['lat_top']:.5f} | {d['lon_left']:.5f} | "
                     f"{d['dn_mine']} | {d['dn_file']} | {d['value_mine_x250']:.4f} | {d['frac_part']:.4f} |")
    else:
        L.append("None: every compared pixel has the same DN in all three layers.")
    L += ["", "## Stored-float cells", "",
          "| Row | Col | Lat | Lon | Backend | Sun diff %p | Earth diff %p | Both diff %p |", "|---:|---:|---:|---:|---|---:|---:|---:|"]
    for c in sc["cells"]:
        L.append(f"| {c['row']} | {c['col']} | {c['lat']:.5f} | {c['lon']:.5f} | {c['backend']} | {c['sun_diff_pp']:+.2e} | "
                 f"{c['earth_diff_pp']:+.2e} | {c['both_diff_pp']:+.2e} |")
    L += ["", "## Scope and limits", "",
          "- Same inputs as the producer (LOLA LDEM_64/16, `ephem.bin`, contract definitions): this checks that the published "
          "map follows from them, not the physical accuracy of the DEM (that is the PGDA validation).",
          "- The PNG comparison tests the published 8-bit product exactly; it cannot show differences smaller than the "
          "file's own rounding. The 0.1 %p test on floats covers only the cells with published floats.",
          "- PNG rows whose footprint straddles 75° S (row 1877) are excluded because cells north of 75° S were not recomputed.", "",
          "Reproduce (about 2.5 h on 4 cores, resumable per row):", "",
          "    LDEM_DIR=<dir with LDEM_64.IMG/LBL, LDEM_16.IMG/LBL> GMAPS_XCHECK_WORK=<scratch> \\",
          "      python pipeline/crosscheck_gmaps_polar_dongju.py run",
          "    python pipeline/crosscheck_gmaps_polar_dongju.py compare   # -> docs/crosscheck_gmaps_polar_dongju.{json,md}"]
    (ROOT / "docs" / "crosscheck_gmaps_polar_dongju.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
