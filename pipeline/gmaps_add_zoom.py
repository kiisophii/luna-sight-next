"""Add one finer tile level to an existing global-map export (card 14: z4 for the 948 m map).

`global_maps.py export` picks its finest level as zmax = max(2, round(log2(nlon / 1024))); for the
948 m grid (nlon = 11520) that is z3 = 8192 px wide (~1.33 km per pixel at the equator), coarser than
the grid itself. This script writes only the next level (z4 = 16384 x 8192 px, 32 x 16 tiles of
512 px per layer, ~0.67 km per pixel) with the exporter's own functions (global_maps.resample /
colorize / COLORMAPS / TILE, JPEG quality 88), and appends it to index.json. Existing tiles,
overviews, value PNGs and other exports are not touched; an existing level is never overwritten.

z4 is the 0.948 km grid upsampled bilinearly for display: it does NOT add terrain or ephemeris detail.

    python pipeline/gmaps_add_zoom.py add   --store data/processed/gmaps_ppd32_merged --web web/data/gmaps_ppd32 --z 4
    python pipeline/gmaps_add_zoom.py check --store data/processed/gmaps_ppd32_merged --web web/data/gmaps_ppd32 --z 4
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import global_maps as gm  # noqa: E402

QUALITY = 88                      # global_maps.export default


def level(z):
    return {"z": z, "width": 1024 << z, "height": 512 << z, "nx": 2 << z, "ny": 1 << z}


def load(store_dir, web_dir):
    st = gm.Store(store_dir, int(json.loads((Path(store_dir) / "meta.json").read_text())["ppd"]), readonly=True)
    idx = json.loads((Path(web_dir) / "index.json").read_text(encoding="utf-8"))
    done = np.asarray(st.done).astype(bool)
    if idx["ppd"] != st.ppd or idx["rows_done"] != int(done.sum()) or idx["rows_total"] != done.size:
        raise SystemExit("index.json does not belong to this store (ppd / rows differ)")
    if idx.get("mock"):
        raise SystemExit("export is mock")
    return st, idx, done


def layer_values(st, done, name, L):
    a = np.array(st.arr[name], dtype=np.float32)
    a[~done] = np.nan
    return gm.resample(a, L["width"], L["height"])          # exporter's resampler (bilinear when upsampling)


def cmd_add(a):
    from PIL import Image
    web = Path(a.web)
    st, idx, done = load(a.store, web)
    have = [L["z"] for L in idx["tiles"]["levels"]]
    if a.z in have:
        raise SystemExit(f"z{a.z} is already in index.json - nothing overwritten")
    if a.z != max(have) + 1:
        raise SystemExit(f"z{a.z} must follow the finest existing level z{max(have)}")
    L = level(a.z)
    t0 = time.time()
    written = 0
    for name in gm.LAYERS:
        tdir = web / "tiles" / name / str(a.z)
        if tdir.exists() and any(tdir.iterdir()):
            raise SystemExit(f"{tdir} exists and is not empty")
        tdir.mkdir(parents=True, exist_ok=True)
        v = layer_values(st, done, name, L)
        T = gm.TILE
        for ty in range(L["ny"]):                               # colour one tile row at a time (per-pixel, identical)
            img = gm.colorize(v[ty * T:(ty + 1) * T], gm.COLORMAPS[name])
            for tx in range(L["nx"]):
                Image.fromarray(img[:, tx * T:(tx + 1) * T]).save(tdir / f"{tx}_{ty}.jpg", quality=QUALITY, optimize=True)
                written += 1
        del v
        print(f"  {name}: {L['nx'] * L['ny']} tiles z{a.z} ({time.time() - t0:.0f} s)", flush=True)
    idx["tiles"]["levels"].append(L)
    idx.setdefault("added_levels", []).append({
        "z": a.z, "width": L["width"], "height": L["height"],
        "km_per_px_equator": round(2 * math.pi * gm.R_M / 1000 / L["width"], 3),
        "grid_res_km": idx["grid_res_km"],
        "method": "pipeline/gmaps_add_zoom.py: global_maps.resample (bilinear upsampling of the grid) + colorize, JPEG q88",
        "note": "display only: finer than the computed grid, no new terrain or ephemeris detail",
        "added_utc": gm._now()})
    gm._write_json(web / "index.json", idx)
    print(f"z{a.z}: {written} tiles in {time.time() - t0:.0f} s; index.json levels -> {[x['z'] for x in idx['tiles']['levels']]}")
    return 0


def decode(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)


def mosaic(web, name, L):
    T = gm.TILE
    out = np.empty((L["height"], L["width"], 3), np.int16)
    for ty in range(L["ny"]):
        for tx in range(L["nx"]):
            out[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T] = decode(web / "tiles" / name / str(L["z"]) / f"{tx}_{ty}.jpg")
    return out


def cmd_check(a):
    from PIL import Image
    web = Path(a.web)
    st, idx, done = load(a.store, web)
    L = level(a.z)
    rep = {"z": a.z, "level": L, "problems": []}
    P = rep["problems"]
    reg = [x for x in idx["tiles"]["levels"] if x["z"] == a.z]
    rep["index_registered"] = bool(reg) and reg[0] == L
    if not rep["index_registered"]:
        P.append("z level missing or wrong in index.json")
    Lc = [x for x in idx["tiles"]["levels"] if x["z"] == a.z - 1][0]
    T = gm.TILE
    rep["layers"] = {}
    for name in gm.LAYERS:
        d = {}
        files = [web / "tiles" / name / str(a.z) / f"{tx}_{ty}.jpg" for ty in range(L["ny"]) for tx in range(L["nx"])]
        missing = [f.name for f in files if not f.exists()]
        d["tiles_expected"], d["tiles_missing"] = len(files), len(missing)
        d["bytes"] = sum(f.stat().st_size for f in files if f.exists())
        if missing:
            P.append(f"{name}: {len(missing)} tiles missing")
            rep["layers"][name] = d
            continue
        sizes = {Image.open(f).size for f in files[:: max(1, len(files) // 16)]}
        d["tile_px"] = sorted(sizes)
        v = layer_values(st, done, name, L)                       # the values the tiles encode
        d["value_nan"] = int(np.isnan(v).sum())
        d["value_min"], d["value_max"] = float(np.nanmin(v)), float(np.nanmax(v))
        if d["value_nan"] or d["value_min"] < -1e-6 or d["value_max"] > 1 + 1e-6:
            P.append(f"{name}: values outside 0..1 or no-data inside the map")
        m = mosaic(web, name, L)
        ref = np.concatenate([gm.colorize(v[ty * T:(ty + 1) * T], gm.COLORMAPS[name]) for ty in range(L["ny"])]).astype(np.int16)
        err = np.abs(m - ref)
        d["jpeg_vs_colorized_rgb"] = {"mean_abs": round(float(err.mean()), 3), "p99_abs": float(np.percentile(err, 99)),
                                      "max_abs": int(err.max())}
        nod = np.all(np.abs(m - np.array(gm.NODATA_RGB)) <= 3, axis=-1)
        d["pixels_near_nodata_rgb"] = int(nod.sum())
        d["ref_pixels_nodata_rgb"] = int(np.all(ref == np.array(gm.NODATA_RGB), axis=-1).sum())
        # tile seams: step across a tile edge vs the step between neighbouring columns/rows inside tiles
        cs = np.arange(T, L["width"], T)
        rs = np.arange(T, L["height"], T)
        seam_c = np.abs(m[:, cs] - m[:, cs - 1]).mean()
        inner_c = np.abs(m[:, cs - 1] - m[:, cs - 2]).mean()
        seam_r = np.abs(m[rs] - m[rs - 1]).mean()
        inner_r = np.abs(m[rs - 1] - m[rs - 2]).mean()
        d["seam_step_rgb"] = {"across_tile_columns": round(float(seam_c), 3), "inside_columns": round(float(inner_c), 3),
                              "across_tile_rows": round(float(seam_r), 3), "inside_rows": round(float(inner_r), 3),
                              # same steps before JPEG (alignment) and in the existing coarser level (baseline)
                              "before_jpeg_across_columns": round(float(np.abs(ref[:, cs] - ref[:, cs - 1]).mean()), 3),
                              "before_jpeg_inside_columns": round(float(np.abs(ref[:, cs - 1] - ref[:, cs - 2]).mean()), 3)}
        # +-180 deg: first vs last column (neighbours on the sphere) in values and in the decoded image
        d["lon_wrap"] = {"value_mean_abs_first_vs_last_col": round(float(np.abs(v[:, 0] - v[:, -1]).mean()), 5),
                         "value_mean_abs_adjacent_cols": round(float(np.abs(v[:, 1] - v[:, 0]).mean()), 5),
                         "rgb_mean_abs_first_vs_last_col": round(float(np.abs(m[:, 0] - m[:, -1]).mean()), 3)}
        # poles: first / last image rows
        d["poles"] = {"top_row_value_range": [round(float(v[0].min()), 4), round(float(v[0].max()), 4)],
                      "bottom_row_value_range": [round(float(v[-1].min()), 4), round(float(v[-1].max()), 4)],
                      "top_bottom_rows_nan": int(np.isnan(v[0]).sum() + np.isnan(v[-1]).sum())}
        # consistency with the existing coarser level: z4 values box-averaged x2 vs z3 values; decoded images likewise
        vc = layer_values(st, done, name, Lc)
        v2 = v.reshape(Lc["height"], 2, Lc["width"], 2).mean(axis=(1, 3))
        mc = mosaic(web, name, Lc)
        m2 = m.reshape(Lc["height"], 2, Lc["width"], 2, 3).mean(axis=(1, 3))
        cs3, rs3 = np.arange(T, Lc["width"], T), np.arange(T, Lc["height"], T)
        d["seam_step_rgb"]["previous_level_across_columns"] = round(float(np.abs(mc[:, cs3] - mc[:, cs3 - 1]).mean()), 3)
        d["seam_step_rgb"]["previous_level_inside_columns"] = round(float(np.abs(mc[:, cs3 - 1] - mc[:, cs3 - 2]).mean()), 3)
        gg = np.array(st.arr[name], dtype=np.float32)
        d["lon_wrap"]["grid_first_vs_last_col"] = round(float(np.abs(gg[:, 0] - gg[:, -1]).mean()), 5)
        d["lon_wrap"]["grid_adjacent_cols"] = round(float(np.abs(gg[:, 1] - gg[:, 0]).mean()), 5)
        d["lon_wrap"]["previous_level_first_vs_last_col"] = round(float(np.abs(vc[:, 0] - vc[:, -1]).mean()), 5)
        d["lon_wrap"]["previous_level_adjacent_cols"] = round(float(np.abs(vc[:, 1] - vc[:, 0]).mean()), 5)
        del gg
        d["vs_previous_level"] = {"value_mean_abs": round(float(np.abs(v2 - vc).mean()), 5),
                                  "value_p99_abs": round(float(np.percentile(np.abs(v2 - vc), 99)), 5),
                                  "area_mean_this": round(float(v.mean()), 5), "area_mean_previous": round(float(vc.mean()), 5),
                                  "rgb_mean_abs_decoded": round(float(np.abs(m2 - mc).mean()), 3)}
        # against the computed grid: z4 sampled at grid cell centres vs the grid values
        g = np.array(st.arr[name], dtype=np.float32)
        rr = np.arange(0, st.nlat, 37)
        cc = np.arange(0, st.nlon, 41)
        yy = ((rr + 0.5) / st.nlat * L["height"]).astype(int)
        xx = ((cc + 0.5) / st.nlon * L["width"]).astype(int)
        gv = g[np.ix_(rr, cc)]
        tv = v[np.ix_(yy, xx)]
        d["vs_grid_at_cell_centres"] = {"n": int(gv.size), "value_mean_abs": round(float(np.abs(tv - gv).mean()), 5),
                                        "value_p99_abs": round(float(np.percentile(np.abs(tv - gv), 99)), 5)}
        rep["layers"][name] = d
        del v, m, ref, mc, vc
        print(f"  {name}: ok", flush=True)
    rep["bytes_total"] = sum(d.get("bytes", 0) for d in rep["layers"].values())
    rep["ok"] = not P
    out = Path(a.report)
    out.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1))
    return 0 if rep["ok"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("add", "check"):
        p = sub.add_parser(c)
        p.add_argument("--store", default=str(gm.ROOT / "data" / "processed" / "gmaps_ppd32_merged"))
        p.add_argument("--web", default=str(gm.ROOT / "web" / "data" / "gmaps_ppd32"))
        p.add_argument("--z", type=int, default=4)
        if c == "check":
            p.add_argument("--report", default=str(gm.ROOT / "docs" / "gmaps_ppd32_z4_check.json"))
    a = ap.parse_args(argv)
    return {"add": cmd_add, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
