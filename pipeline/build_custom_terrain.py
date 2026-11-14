"""Browser height tiles for user-defined (custom) sites  ->  web/data/hterrain/

Two global grids, both MOON_ME simple cylindrical, heights in metres above R = 1737.4 km:
  near : LOLA LDEM_64 block-averaged 2x2 to 32 pixels/degree (pixel ~948 m), used to 150 km
  far  : LOLA LDEM_16 as is, 16 pixels/degree (pixel ~1895 m), used 150-300 km
Pixel centres: lat = 90 - (r + 0.5)/P, lon = -180 + (c + 0.5)/P   (P = pixels/degree, lon east-positive).

Each grid is cut into T x T degree tiles. A tile file holds (T*P + 1) x (T*P + 1) int16 samples:
rows r0 .. r0+T*P and columns c0 .. c0+T*P (one shared row/column with the next tile so the browser can
interpolate bilinearly inside a single tile; the last row is clamped at the south pole, columns wrap in longitude).
Encoding per tile (little-endian): int16 heights rounded to 1 m, then each row delta-coded along the row
(first value absolute), then gzip.  File: tiles/<grid>/<ty>_<tx>.i16.gz  (ty from the north, tx from lon -180).

Usage:
  python pipeline/build_custom_terrain.py --ldem64 <ldem_64_float.img> --ldem16 <ldem_16_float.img> [--out web/data/hterrain]
Resumable: existing tiles are skipped (delete a tile to rebuild it).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np

R_M = 1737400.0
GRIDS = {  # name: (ppd, tile_deg, used_to_km, source)
    "near": (32, 15, 150, "LDEM_64"),
    "far": (16, 30, 300, "LDEM_16"),
}


def read_ldem(img: Path) -> tuple[np.ndarray, int]:
    """Return (heights m float32 rows north->south, cols from lon -180), ppd. Checks the label."""
    lbl = img.with_suffix(".lbl").read_text(encoding="latin-1")
    def key(k):
        for line in lbl.splitlines():
            if line.strip().startswith(k) and "=" in line:
                return float(line.split("=", 1)[1].split("<")[0].strip().strip('"'))
        raise KeyError(k)
    nl, ns, ppd = int(key("LINES")), int(key("LINE_SAMPLES")), int(key("MAP_RESOLUTION"))
    assert key("OFFSET") == 1737.4 and key("CENTER_LONGITUDE") == 180
    assert abs(key("LINE_PROJECTION_OFFSET") - (nl / 2 - 0.5)) < 1e-6
    assert abs(key("SAMPLE_PROJECTION_OFFSET") - (ns / 2 - 0.5)) < 1e-6
    # col c centre lon = 180 + (c - (ns/2 - 0.5))/ppd = (c + 0.5)/ppd  (0..360 E)  -> roll by half to start at -180
    a = np.fromfile(img, dtype="<f4").reshape(nl, ns)
    a = np.roll(a, ns // 2, axis=1) * 1000.0        # km -> m; new col c centre lon = -180 + (c+0.5)/ppd
    return a.astype(np.float32), ppd


def block_mean(a: np.ndarray, f: int) -> np.ndarray:
    nl, ns = a.shape
    return a.reshape(nl // f, f, ns // f, f).mean(axis=(1, 3), dtype=np.float64).astype(np.float32)


def encode_tile(t: np.ndarray) -> bytes:
    q = np.rint(t).astype(np.int32)
    assert q.min() > -32768 and q.max() < 32768
    d = q.copy()
    d[:, 1:] = q[:, 1:] - q[:, :-1]
    assert d.min() > -32768 and d.max() < 32768
    return gzip.compress(d.astype("<i2").tobytes(), compresslevel=9, mtime=0)


def decode_tile(raw: bytes, n: int) -> np.ndarray:
    d = np.frombuffer(gzip.decompress(raw), dtype="<i2").reshape(n, n).astype(np.int32)
    return np.cumsum(d, axis=1).astype(np.float32)


def cut(grid: np.ndarray, ppd: int, tile_deg: int, outdir: Path) -> dict:
    nl, ns = grid.shape
    tp = tile_deg * ppd
    ny, nx = nl // tp, ns // tp
    outdir.mkdir(parents=True, exist_ok=True)
    total = 0
    for ty in range(ny):
        rows = np.minimum(np.arange(ty * tp, ty * tp + tp + 1), nl - 1)
        for tx in range(nx):
            f = outdir / f"{ty}_{tx}.i16.gz"
            if not f.exists():
                cols = np.arange(tx * tp, tx * tp + tp + 1) % ns
                tmp = f.with_suffix(".tmp")
                tmp.write_bytes(encode_tile(grid[np.ix_(rows, cols)]))
                tmp.replace(f)
            total += f.stat().st_size
    return {"nx": nx, "ny": ny, "n": tp + 1, "bytes": total}


def overview(far: np.ndarray, out: Path, width: int = 1024):
    """Grey shaded-relief picture of the whole Moon (equirectangular, lon -180 left, lat +90 top) for the
    click-to-pick mini map. Display only: no numbers are read from it."""
    from PIL import Image
    f = far.shape[1] // width
    a = block_mean(far, f).astype(np.float64)
    res = math.radians(f / 16) * R_M
    lat = np.radians(90 - (np.arange(a.shape[0]) + 0.5) * f / 16)[:, None]
    gy, gx = np.gradient(a, res)
    gx = gx / np.maximum(np.cos(lat), 0.05)
    az, alt = math.radians(315), math.radians(35)
    slope = np.arctan(np.hypot(gx, gy) * 3)
    aspect = np.arctan2(-gx, gy)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    hn = (a - a.min()) / (a.max() - a.min())
    v = np.clip(40 + 150 * np.clip(shade, 0, 1) + 50 * hn, 0, 255).astype(np.uint8)
    Image.fromarray(v, "L").save(out, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ldem64", required=True, type=Path)
    ap.add_argument("--ldem16", required=True, type=Path)
    ap.add_argument("--out", default=Path("web/data/hterrain"), type=Path)
    a = ap.parse_args()
    index = {"version": 1, "frame": "MOON_ME", "units": "m above R=1737.4 km", "radius_m": R_M,
             "pixel_centres": "lat = 90 - (r+0.5)/ppd, lon = -180 + (c+0.5)/ppd",
             "encoding": "gzip(int16 LE, each row delta-coded along the row, first value absolute), (n x n) samples, "
                         "tile (ty,tx) = global rows ty*(n-1).., cols tx*(n-1).. (wrapping), last row clamped",
             "url": "tiles/{grid}/{ty}_{tx}.i16.gz", "overview": "overview.png", "grids": {}, "mock": False,
             "sources": [{"name": "LOLA LDEM_64 (block mean 2x2 -> 32 ppd)",
                          "url": "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ldem_64_float.img"},
                         {"name": "LOLA LDEM_16",
                          "url": "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ldem_16_float.img"}]}
    for name, (ppd, tdeg, to_km, src) in GRIDS.items():
        img = a.ldem64 if src == "LDEM_64" else a.ldem16
        g, p0 = read_ldem(img)
        if p0 != ppd:
            g = block_mean(g, p0 // ppd)
        info = cut(g, ppd, tdeg, a.out / "tiles" / name)
        res_m = math.radians(1 / ppd) * R_M
        index["grids"][name] = {"ppd": ppd, "tile_deg": tdeg, "res_m": round(res_m, 1), "to_km": to_km,
                                "source": src, **info}
        print(name, info, f"{info['bytes'] / 1e6:.1f} MB")
        if name == "far":
            overview(g, a.out / "overview.png")
        del g
    (a.out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
