"""South-polar browser height tiles for user-defined (custom) points  ->  web/data/hterrain/polar_s/

Why: the global browser grid (web/data/hterrain/, LDEM_64 at ~948 m) smooths polar peaks and rims too much
(docs/VALIDATION.md row 14: median RMS 0.96 deg against the card-8 polar horizons). Near the poles the Sun is
only 1-2 deg above the horizon, so the near field must come from the PGDA polar products.

Source: NASA PGDA LOLA south-polar DEMs (https://pgda.gsfc.nasa.gov/products/90), the same files and the same
projection card 2 / card 8 use (pipeline/fetch_polar.py): spherical polar stereographic, lat_0 = -90, k0 = 1,
R = 1737.4 km, heights in metres above R, pixel centres x = X0 + c*d, y = Y0 - r*d.
Read with HTTP range requests (fetch_polar.RangeFile, resumable block cache in data/raw/polar/_blocks).

Each LEVEL is a square window of the source grid centred on the pole, cut into tiles of T x T pixels stored as
(T+1) x (T+1) samples (one shared row/column with the next tile, so bilinear interpolation stays inside one tile).
Only tiles that intersect the disc of radius `radius_km` around the pole are written; the list is in the index.
Encoding per tile (little-endian): int32 base, then (T+1)^2 int16 residuals of the heights quantised to `q_m`
(planar predictor: res[r,c] = a[r,c] - a[r,c-1] - a[r-1,c] + a[r-1,c-1]; first row/column 1-D deltas;
res[0,0] = a[0,0] - base = 0), then gzip.  Decoding is exact (checked for every tile when it is written).

    python pipeline/build_polar_terrain.py [--levels p60,p240] [--out web/data/hterrain/polar_s]
Resumable: existing tiles are skipped.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_polar as fp  # noqa: E402
import polar_prefetch  # noqa: E402

polar_prefetch.install(8)   # parallel Range requests (PGDA is slow per connection)

ROOT = Path(__file__).resolve().parents[1]
R_M = 1737400.0
# name: source resolution (PGDA product), block-mean factor, pixel used to (km from the point),
#       disc radius around the pole that the tiles cover (km), quantisation (m), tile pixels
LEVELS = {
    "p20": dict(src=20, factor=1, to_km=None, radius_km=None, q_m=0.25, tile=512),
    "p60": dict(src=60, factor=1, to_km=None, radius_km=None, q_m=0.25, tile=512),
    "p120": dict(src=60, factor=2, to_km=None, radius_km=None, q_m=0.25, tile=512),
    "p240": dict(src=240, factor=1, to_km=None, radius_km=None, q_m=0.5, tile=512),
}


def rho_km(lat_deg):
    """Polar-stereographic radius (km) of a south latitude (k0 = 1 at the pole)."""
    return 2 * R_M * math.tan(math.pi / 4 + math.radians(lat_deg) / 2) / 1000.0


def encode(a_q: np.ndarray) -> bytes:
    """a_q: int64 quantised heights (n x n). -> gzip(int32 base + int16 planar residuals)."""
    base = int(a_q[0, 0])
    a = a_q - base
    r = np.empty_like(a)
    r[0, 0] = 0
    r[0, 1:] = a[0, 1:] - a[0, :-1]
    r[1:, 0] = a[1:, 0] - a[:-1, 0]
    r[1:, 1:] = a[1:, 1:] - a[1:, :-1] - a[:-1, 1:] + a[:-1, :-1]
    if r.min() < -32768 or r.max() > 32767:
        raise ValueError(f"residual out of int16 range ({r.min()}, {r.max()})")
    return gzip.compress(np.int32(base).astype("<i4").tobytes() + r.astype("<i2").tobytes(), compresslevel=9, mtime=0)


def decode(raw: bytes, n: int) -> np.ndarray:
    """Exact inverse of encode (returns quantised integer heights)."""
    b = gzip.decompress(raw)
    base = int(np.frombuffer(b[:4], "<i4")[0])
    r = np.frombuffer(b[4:], "<i2").reshape(n, n).astype(np.int64)
    return np.cumsum(np.cumsum(r, axis=0), axis=1) + base


def build_level(name, cfg, out: Path):
    url = fp.BASE + fp.SOURCES[cfg["src"]][0]
    f, T, q = cfg["factor"], cfg["tile"], cfg["q_m"]
    n = T + 1
    d_out = cfg["src"] * f
    with fp.RangeFile(url, ROOT / "data" / "raw" / "polar" / "_blocks") as stream, tifffile.TiffFile(stream) as tif:
        page = tif.pages[0]
        fp.validate_crs(page.geotiff_tags)
        x0, y0, step = fp.grid(page)
        if not math.isclose(step, cfg["src"]):
            raise ValueError(f"unexpected pixel size {step}")
        H, W = page.imagelength, page.imagewidth
        # output pixel (r, c) = mean of source rows r*f .. r*f+f-1 (and cols) starting at source (R0, C0)
        Rm = cfg["radius_km"] * 1000.0
        half_src = math.ceil(Rm / step) + 2 * f
        cpx, cpy = (0.0 - x0) / step, (y0 - 0.0) / step         # source pixel coords of the pole
        C0 = int(math.floor(cpx)) - half_src
        R0 = int(math.floor(cpy)) - half_src
        C0 -= C0 % f if f > 1 else 0
        R0 -= R0 % f if f > 1 else 0
        n_out = math.ceil(2 * half_src / f) + 1
        nt = math.ceil((n_out - 1) / T)
        X0 = x0 + (C0 + (f - 1) / 2) * step                       # first output pixel centre
        Y0 = y0 - (R0 + (f - 1) / 2) * step
        if C0 < 0 or R0 < 0 or C0 + (nt * T + 1) * f > W or R0 + (nt * T + 1) * f > H:
            raise ValueError("level window exceeds the source grid")
        tdir = out / name
        tdir.mkdir(parents=True, exist_ok=True)
        present, total = [], 0
        for ty in range(nt):
            # download every source block this tile row needs with many parallel Range requests first
            todo = [tx for tx in range(nt)
                    if math.hypot(max(X0 + tx * T * d_out, 0, -(X0 + (tx + 1) * T * d_out)),
                                  max(Y0 - (ty + 1) * T * d_out, 0, -(Y0 - ty * T * d_out))) <= Rm
                    and not (tdir / f"{ty}_{tx}.bin.gz").exists()]
            if todo:
                r0 = R0 + ty * T * f
                polar_prefetch.prefetch(page, stream, (r0, r0 + n * f, C0 + min(todo) * T * f, C0 + (max(todo) * T + n) * f),
                                        workers=24)
            for tx in range(nt):
                # tile extent in projected metres -> skip tiles that do not touch the disc
                xa, xb = X0 + tx * T * d_out, X0 + (tx + 1) * T * d_out
                ya, yb = Y0 - (ty + 1) * T * d_out, Y0 - ty * T * d_out
                dx = max(xa - 0, 0, 0 - xb)
                dy = max(ya - 0, 0, 0 - yb)
                if math.hypot(dx, dy) > Rm:
                    continue
                key = f"{ty}_{tx}"
                present.append(key)
                fpath = tdir / f"{key}.bin.gz"
                if fpath.exists():
                    total += fpath.stat().st_size
                    continue
                r0, c0 = R0 + ty * T * f, C0 + tx * T * f
                src = fp.read_window(page, stream, (r0, r0 + n * f, c0, c0 + n * f)).astype(np.float64)
                if not np.isfinite(src).all():
                    raise ValueError(f"{name} {key}: no-data pixels inside the level window")
                h = src.reshape(n, f, n, f).mean(axis=(1, 3)) if f > 1 else src
                a_q = np.rint(h / q).astype(np.int64)
                raw = encode(a_q)
                if not np.array_equal(decode(raw, n), a_q):
                    raise AssertionError(f"{name} {key}: decode mismatch")
                tmp = fpath.with_suffix(".part")
                tmp.write_bytes(raw)
                tmp.replace(fpath)
                total += len(raw)
                print(f"{name} {key}: {len(raw) / 1e6:.2f} MB (total {total / 1e6:.1f} MB)", flush=True)
    return dict(name=name, source=f"PGDA {Path(fp.SOURCES[cfg['src']][0]).name}" + (f" block mean {f}x{f}" if f > 1 else ""),
                source_url=url, res_m=d_out, q_m=q, to_km=cfg["to_km"], radius_km=cfg["radius_km"],
                covers_points_poleward_of_deg=cfg.get("lat_edge"),
                x0_m=X0, y0_m=Y0, tile_px=T, n=n, nt=nt, tiles=present, bytes=total,
                url=f"polar_s/{name}/{{ty}}_{{tx}}.bin.gz")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--levels", default="p60,p240", help="comma list, finest first")
    ap.add_argument("--lat-edge", type=float, default=-75.0, help="custom points poleward of this use the polar path")
    ap.add_argument("--to-km", required=True, help="comma list of use-to distances (km), one per level")
    ap.add_argument("--level-edges", default="", help="comma list: a level is used only for points poleward of "
                                                       "this latitude (default: --lat-edge for every level)")
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "data" / "hterrain" / "polar_s")
    a = ap.parse_args()
    names = a.levels.split(",")
    tos = [float(v) for v in a.to_km.split(",")]
    edges = [float(v) for v in a.level_edges.split(",")] if a.level_edges else [a.lat_edge] * len(names)
    levels = []
    for name, to, edge in zip(names, tos, edges):
        cfg = dict(LEVELS[name])
        cfg["to_km"] = to
        cfg["lat_edge"] = edge
        cfg["radius_km"] = rho_km(edge) + to + 1.0      # every sample a point can need, +1 km margin
        levels.append(build_level(name, cfg, a.out))
    for lv in levels:
        lv["lat_edge_deg"] = lv.pop("covers_points_poleward_of_deg")
    idx = dict(version=1, pole="south", lat_edge_deg=a.lat_edge, frame="MOON_ME (PGDA DE421 frame)",
               projection=fp.PROJ, units="m above R=1737.4 km",
               pixel_centres="x = x0_m + c*res_m, y = y0_m - r*res_m (global level pixel indices)",
               encoding="gzip(int32 LE base + (n x n) int16 LE residuals of round(h/q_m) - base; planar predictor "
                        "res[r,c]=a[r,c]-a[r,c-1]-a[r-1,c]+a[r-1,c-1], first row/col 1-D deltas, res[0,0]=0); "
                        "tile (ty,tx) = level rows ty*tile_px .. ty*tile_px+tile_px, cols likewise",
               levels=levels, mock=False,
               sources=[dict(name="NASA PGDA LOLA south-polar DEMs", url="https://pgda.gsfc.nasa.gov/products/90")])
    (a.out / "index.json").write_text(json.dumps(idx, indent=1), encoding="utf-8")
    print("total", round(sum(lv["bytes"] for lv in levels) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
