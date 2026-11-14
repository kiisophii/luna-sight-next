"""Independent check of two terrain-tile products against the original NASA LOLA DEMs (Soyun Jeong).

  (5) 3D globe height tiles      web/data/globe/            (producer: Sua Kim, pipeline/build_globe_tiles.py)
  (6) custom-point terrain tiles web/data/hterrain/ (+ polar_s/)  (producer: Sua Kim, build_custom_terrain.py,
                                                                    build_polar_terrain.py)

Independence: nothing is imported from the production pipeline. Tile decoding, vertex coordinates,
block means, bilinear interpolation and the DEM readers are written here from the formats documented in the
index.json files, docs/globe3d.md and the PDS / GeoTIFF metadata. Only numpy, Pillow, gzip, pyproj (for the
stereographic projection, from the CRS string in the index / GeoTIFF), rasterio (to read the original PGDA
GeoTIFFs over HTTP) and requests (HTTP Range spot checks) are used.

Originals:
  LOLA LDEM_64 / LDEM_16 float (PDS Geosciences): local copies in data/raw/global/; every byte this script
    reads from them is also fetched from the PDS server by HTTP Range and compared (bit-identical required).
  PGDA LOLA south-polar DEMs LDEM_80S_20MPP_ADJ.TIF, LDEM_60S_60MPP_ADJ.TIF, LDEM_60S_240MPP_ADJ.TIF:
    read directly from https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/ (no local cache).

    python pipeline/verify_terrain_tiles.py            -> docs/terrain_tiles_verification.json (+ table on stdout)
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
SEED = 20261115
R_M = 1737400.0
PDS = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/"
PGDA = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/"
PGDA_FILE = {20: "LDEM_80S_20MPP_ADJ.TIF", 60: "LDEM_60S_60MPP_ADJ.TIF", 240: "LDEM_60S_240MPP_ADJ.TIF"}

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")


# =========================================================================== original LOLA cylindrical grids
class LolaCyl:
    """PDS LDEM_xx float image. Label checked here: rows north->south, col c centre lon = (c + 0.5)/ppd (0..360 E),
    row r centre lat = 90 - (r + 0.5)/ppd, value in km above 1737.4 km."""

    def __init__(self, name):
        self.name = name
        self.img = ROOT / "data" / "raw" / "global" / f"{name}.img"
        lbl = self.img.with_suffix(".lbl").read_text(encoding="latin-1")
        kv = {}
        for line in lbl.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv.setdefault(k.strip(), v.split("<")[0].strip().strip('"'))
        self.nl, self.ns = int(kv["LINES"]), int(kv["LINE_SAMPLES"])
        self.ppd = int(float(kv["MAP_RESOLUTION"]))
        assert kv["SAMPLE_TYPE"] == "PC_REAL" and kv["SAMPLE_BITS"] == "32" and kv["UNIT"] == "KILOMETER"
        assert float(kv["OFFSET"]) == 1737.4 and float(kv["SCALING_FACTOR"]) == 1 and float(kv["CENTER_LONGITUDE"]) == 180
        assert float(kv["LINE_PROJECTION_OFFSET"]) == self.nl / 2 - 0.5 and float(kv["SAMPLE_PROJECTION_OFFSET"]) == self.ns / 2 - 0.5
        assert "MISSING_CONSTANT" not in kv
        self.label = {k: kv[k] for k in ("PRODUCT_VERSION_ID", "LINES", "LINE_SAMPLES", "MAP_RESOLUTION", "UNIT",
                                         "OFFSET", "CENTER_LONGITUDE", "LINE_PROJECTION_OFFSET",
                                         "SAMPLE_PROJECTION_OFFSET", "COORDINATE_SYSTEM_NAME")}
        assert self.img.stat().st_size == self.nl * self.ns * 4
        self.a = np.memmap(self.img, dtype="<f4", mode="r", shape=(self.nl, self.ns))
        self.used = {}                     # row -> set(cols) actually read (for the PDS Range check)

    def px(self, r, c):
        """height (m) of base pixel (r, c); c wraps."""
        c = int(c) % self.ns
        self.used.setdefault(int(r), set()).add(c)
        return float(self.a[int(r), c]) * 1000.0

    def level_value(self, p, r, c):
        """value of pixel (r, c) of the level with p pixels/deg = mean of the k x k base pixels (k = ppd/p)."""
        k = self.ppd // p
        return float(np.mean([self.px(r * k + i, c * k + j) for i in range(k) for j in range(k)]))

    def bilinear(self, p, lat, lon):
        """bilinear between level pixel centres (lat = 90 - (r+.5)/p, lon360 = (c+.5)/p); rows clamped, cols wrap."""
        H, W = self.nl * p // self.ppd, self.ns * p // self.ppd
        fr = min(max((90.0 - lat) * p - 0.5, 0.0), H - 1.0)
        fc = (lon % 360.0) * p - 0.5
        r0 = min(int(math.floor(fr)), H - 2)
        c0 = int(math.floor(fc))
        tr, tc = fr - r0, fc - c0
        v = lambda r, c: self.level_value(p, r, c % W)  # noqa: E731
        return ((1 - tr) * ((1 - tc) * v(r0, c0) + tc * v(r0, c0 + 1))
                + tr * ((1 - tc) * v(r0 + 1, c0) + tc * v(r0 + 1, c0 + 1)))

    def range_check(self):
        """Fetch every used byte range from the PDS server and compare with the local file."""
        import requests
        url = PDS + self.img.name
        s = requests.Session()
        n_req = n_bytes = 0
        mism = 0
        with open(self.img, "rb") as f:
            for r, cols in sorted(self.used.items()):
                cs = sorted(cols)
                runs, a = [], cs[0]
                for prev, cur in zip(cs, cs[1:] + [None]):
                    if cur != prev + 1:
                        runs.append((a, prev))
                        a = cur
                for c0, c1 in runs:
                    off = (r * self.ns + c0) * 4
                    ln = (c1 - c0 + 1) * 4
                    for t in range(5):
                        try:
                            resp = s.get(url, headers={"Range": f"bytes={off}-{off + ln - 1}"}, timeout=60)
                            if resp.status_code == 206 and len(resp.content) == ln:
                                break
                        except requests.RequestException:
                            pass
                        time.sleep(2)
                    else:
                        raise RuntimeError(f"PDS range read failed {url} {off}")
                    f.seek(off)
                    mism += f.read(ln) != resp.content
                    n_req += 1
                    n_bytes += ln
        return {"url": url, "requests": n_req, "bytes": n_bytes, "mismatching_ranges": int(mism)}


# =========================================================================== original PGDA GeoTIFFs (remote)
class PgdaTif:
    def __init__(self, res):
        import rasterio
        self.res, self.file = res, PGDA_FILE[res]
        self.url = PGDA + self.file
        self.ds = rasterio.open("/vsicurl/" + self.url)
        t = self.ds.transform
        assert abs(t.a - res) < 1e-9 and abs(t.e + res) < 1e-9 and t.b == 0 and t.d == 0
        assert self.ds.tags().get("AREA_OR_POINT") == "Area"
        self.xul, self.yul = t.c, t.f                       # outer corner; pixel centre = corner + (c + 0.5) * res
        self.crs = self.ds.crs.to_proj4()
        self.meta = {"url": self.url, "width": self.ds.width, "height": self.ds.height, "dtype": self.ds.dtypes[0],
                     "nodata": str(self.ds.nodata), "transform": list(t[:6]), "area_or_point": "Area", "crs": self.crs}

    def read(self, r0, c0, h, w):
        import rasterio
        for t in range(5):
            try:
                a = self.ds.read(1, window=rasterio.windows.Window(c0, r0, w, h)).astype(np.float64)
                if not np.isfinite(a).all():
                    raise ValueError("no-data in window")
                return a
            except rasterio.errors.RasterioIOError:
                time.sleep(3)
        raise RuntimeError(f"read failed {self.url}")

    def frac_index(self, x, y):
        return (self.yul - self.res / 2 - y) / self.res, (x - (self.xul + self.res / 2)) / self.res   # (row, col)

    def bilinear(self, x, y):
        fr, fc = self.frac_index(x, y)
        r0, c0 = int(math.floor(fr)), int(math.floor(fc))
        a = self.read(r0, c0, 2, 2)
        tr, tc = fr - r0, fc - c0
        return float((1 - tr) * ((1 - tc) * a[0, 0] + tc * a[0, 1]) + tr * ((1 - tc) * a[1, 0] + tc * a[1, 1])), (r0, c0)

    def pixel(self, x, y):
        fr, fc = self.frac_index(x, y)
        r, c = round(fr), round(fc)
        if abs(fr - r) > 1e-6 or abs(fc - c) > 1e-6:
            raise ValueError(f"not on a source pixel centre: frac row {fr}, col {fc}")
        return float(self.read(r, c, 1, 1)[0, 0]), (r, c)


def proj(crs):
    from pyproj import CRS, Transformer
    ll = CRS.from_proj4(f"+proj=longlat +R={R_M} +no_defs")
    return (Transformer.from_crs(ll, CRS.from_proj4(crs), always_xy=True),
            Transformer.from_crs(CRS.from_proj4(crs), ll, always_xy=True))


# =========================================================================== (5) globe tiles
def decode_png(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.int64)
    return (a[..., 0] * 256 + a[..., 1]) / 2.0 - 10000.0


def level_ppd(spacing_m, base_ppd=64):
    """coarsest LDEM level (64/32/16/8/4 ppd) whose pixel is <= 1.01 x the tile spacing (docs: box-filtered)."""
    best = base_ppd
    for p in (64, 32, 16, 8, 4):
        if math.radians(1 / p) * R_M <= spacing_m * 1.01:
            best = p
    return best


def check_globe(rng, l64, pg20, out):
    idx = json.loads((WEB / "globe" / "index.json").read_text())
    N, half = idx["tile_cells"], idx["cap"]["half_m"]
    tiles = {k: [t for t in v] for k, v in idx["tiles"].items()}
    fwd_s, inv_s = proj(idx["cap"]["projection_south"])
    fwd_n, inv_n = proj(idx["cap"]["projection_north"])
    sites = [s for s in json.loads((WEB / "sites.json").read_text(encoding="utf-8")) if s["lat"] <= -83]
    rows = []

    def vertex(kind, z, x, y, bi, bj):
        k_r, k_c = bi - 1, bj - 1                       # bordered pixel -> vertex index (-1 .. 257)
        if kind == "band":
            d = idx["band"]["root_deg"] / 2 ** z / N
            lat = idx["band"]["lat_max"] - (y * N + k_r) * d
            lon = (-180.0 + (x * N + k_c) * d + 180.0) % 360.0 - 180.0
            return lat, lon, None, math.radians(d) * R_M
        d = 2 * half / 2 ** z / N
        px, py = -half + (x * N + k_c) * d, half - (y * N + k_r) * d
        lon, lat = (inv_s if kind == "south" else inv_n).transform(px, py)
        return lat, lon, (px, py), d

    def ldem_sample(kind, z, x, y, label):
        bi, bj = (int(v) for v in rng.integers(1, N + 2, 2))   # one of the 257 x 257 shared vertices
        lat, lon, _, sp = vertex(kind, z, x, y, bi, bj)
        p = level_ppd(sp)
        exp = l64.bilinear(p, lat, lon)
        native = l64.bilinear(64, lat, lon)
        h = float(decode_png(WEB / "globe" / kind / str(z) / f"{x}_{y}.png")[bi, bj])
        rows.append(dict(group=label, tile=f"{kind}/{z}/{x}_{y}", z=z, pixel=[bi, bj], lat=round(lat, 6), lon=round(lon, 6),
                         source=f"LOLA LDEM_64 ({p} ppd = {64 // p}x{64 // p} block mean of 64 ppd, bilinear)",
                         tile_spacing_m=round(sp, 1), expected_m=round(exp, 3), tile_m=h, abs_diff_m=round(abs(h - exp), 3),
                         info_native_64ppd_bilinear_m=round(native, 3), info_abs_diff_to_native_m=round(abs(h - native), 3)))

    # band (LDEM only at z <= 3) and north cap (LDEM only at z <= 2): three levels each
    for kind, zs, label in (("band", (1, 2, 3), "band global"), ("north", (0, 1, 2), "north cap global")):
        for z in zs:
            cand = [t for t in tiles[kind] if t[0] == z]
            t = cand[int(rng.integers(len(cand)))]
            ldem_sample(kind, z, t[1], t[2], label)

    # south high-resolution: z7 tiles (34 m spacing) from PGDA 20 m near the polar sites (z8 excluded: Soyun's own tiles)
    site_xy = [(s["id"], *fwd_s.transform(s["lon"], s["lat"])) for s in sites]
    z = 7
    d = 2 * half / 2 ** z / N
    z7 = [t for t in tiles["south"] if t[0] == z and t[5] == 1]
    order = rng.permutation(len(site_xy))
    picked = 0
    for si in order:
        if picked == 4:
            break
        sid, sx, sy = site_xy[si]
        near = [t for t in z7 if abs(-half + (t[1] + 0.5) * N * d - sx) < N * d and abs(half - (t[2] + 0.5) * N * d - sy) < N * d]
        if not near:
            continue
        t = near[int(rng.integers(len(near)))]
        for _ in range(500):
            bi, bj = (int(v) for v in rng.integers(1, N + 2, 2))
            lat, lon, (px, py), sp = vertex("south", z, t[1], t[2], bi, bj)
            if math.hypot(px - sx, py - sy) <= 9000:
                break
        else:
            continue
        exp, (r0, c0) = pg20.bilinear(px, py)
        h = float(decode_png(WEB / "globe" / "south" / str(z) / f"{t[1]}_{t[2]}.png")[bi, bj])
        nr, nc = (round(v) for v in pg20.frac_index(px, py))
        nearest = float(pg20.read(nr, nc, 1, 1)[0, 0])
        rows.append(dict(group="south z7 (PGDA 20 m)", tile=f"south/{z}/{t[1]}_{t[2]}", z=z, pixel=[bi, bj],
                         lat=round(lat, 6), lon=round(lon, 6), x_m=round(px, 2), y_m=round(py, 2),
                         near_site=sid, km_from_site=round(math.hypot(px - sx, py - sy) / 1000, 2),
                         source=f"PGDA {pg20.file} (20 m, bilinear between pixel centres; rows {r0}-{r0 + 1}, cols {c0}-{c0 + 1})",
                         tile_spacing_m=round(sp, 1), expected_m=round(exp, 3), tile_m=h, abs_diff_m=round(abs(h - exp), 3),
                         info_nearest_20m_pixel_m=round(nearest, 3), info_abs_diff_to_nearest_m=round(abs(h - nearest), 3)))
        picked += 1
    tol = 0.25 + 0.01
    for r in rows:
        r["result"] = "PASS" if r["abs_diff_m"] <= tol else "FAIL"
    out["globe"] = {"tolerance_m": tol, "tolerance_basis": "0.5 m PNG height step -> max rounding 0.25 m; + 0.01 m for "
                    "float32 source values and floating-point bilinear", "samples": rows}
    return rows


# =========================================================================== (6) custom-point terrain tiles
def decode_i16_rows(path, n):
    d = np.frombuffer(gzip.decompress(path.read_bytes()), dtype="<i2").astype(np.int64)
    assert d.size == n * n
    return np.cumsum(d.reshape(n, n), axis=1)               # each row delta-coded along the row


def decode_polar(path, n):
    b = gzip.decompress(path.read_bytes())
    base = int(np.frombuffer(b[:4], "<i4")[0])
    r = np.frombuffer(b[4:], "<i2").astype(np.int64)
    assert r.size == n * n
    return np.cumsum(np.cumsum(r.reshape(n, n), axis=0), axis=1) + base   # inverse of the planar predictor


def check_hterrain(rng, l64, l16, pgda, out):
    idx = json.loads((WEB / "hterrain" / "index.json").read_text())
    rows = []
    for grid, src, k_mean, n_rand, edge in (("near", l64, 2, 3, "wrap"), ("far", l16, 1, 2, "clamp")):
        g = idx["grids"][grid]
        n, ppd, tdeg = g["n"], g["ppd"], g["tile_deg"]
        nl, ns = 180 * ppd, 360 * ppd
        picks = [(int(rng.integers(g["ny"])), int(rng.integers(g["nx"])), int(rng.integers(n)), int(rng.integers(n)), "random")
                 for _ in range(n_rand)]
        if edge == "wrap":   # last column of the easternmost tile = global column 0 (lon wraps at +-180)
            picks.append((int(rng.integers(g["ny"])), g["nx"] - 1, int(rng.integers(n)), n - 1, "lon wrap (+180 -> -180)"))
        else:                # last row of the southernmost tile is clamped to the last global row
            picks.append((g["ny"] - 1, int(rng.integers(g["nx"])), n - 1, int(rng.integers(n)), "south-pole row clamp"))
        for ty, tx, i, j, why in picks:
            R_ = min(ty * (n - 1) + i, nl - 1)
            C_ = (tx * (n - 1) + j) % ns
            lat, lon = 90 - (R_ + 0.5) / ppd, -180 + (C_ + 0.5) / ppd
            # grid node -> original pixels: grid col C (lon -180 + (C+.5)/ppd) = file cols k*C + ns_file/2 (+0..k-1)
            fc0 = (k_mean * C_ + src.ns // 2) % src.ns
            exp = float(np.mean([src.px(k_mean * R_ + a, fc0 + b) for a in range(k_mean) for b in range(k_mean)]))
            tile = decode_i16_rows(WEB / "hterrain" / "tiles" / grid / f"{ty}_{tx}.i16.gz", n)
            h = float(tile[i, j])
            extra = {}
            if why.startswith("lon wrap"):
                other = decode_i16_rows(WEB / "hterrain" / "tiles" / grid / f"{ty}_0.i16.gz", n)
                extra["same_node_in_tile_0_column_0_m"] = float(other[i, 0])
            rows.append(dict(group=f"{grid} ({ppd} ppd)", tile=f"tiles/{grid}/{ty}_{tx}", sample=[i, j], case=why,
                             grid_node=[R_, C_], lat=round(lat, 6), lon=round(lon, 6),
                             source=f"LOLA {src.name.upper().replace('_FLOAT', '')}" + (f" (2x2 block mean of 64 ppd)" if k_mean == 2 else " (16 ppd as is)"),
                             expected_m=round(exp, 3), expected_rounded_m=float(np.rint(exp)), tile_m=h,
                             abs_diff_m=round(abs(h - exp), 3), **extra))
    tol_g = 0.5 + 0.01
    for r in rows:
        r["result"] = "PASS" if r["abs_diff_m"] <= tol_g and r["tile_m"] == r["expected_rounded_m"] and \
            r.get("same_node_in_tile_0_column_0_m", r["tile_m"]) == r["tile_m"] else "FAIL"
    # south-polar levels
    pidx = json.loads((WEB / "hterrain" / "polar_s" / "index.json").read_text())
    fwd, inv = proj(pidx["projection"])
    for lv in pidx["levels"]:
        name, res, q, n = lv["name"], lv["res_m"], lv["q_m"], lv["n"]
        tif = pgda[res]
        key = lv["tiles"][int(rng.integers(len(lv["tiles"])))]
        ty, tx = (int(v) for v in key.split("_"))
        i, j = (int(v) for v in rng.integers(0, n, 2))
        R_, C_ = ty * lv["tile_px"] + i, tx * lv["tile_px"] + j
        x, y = lv["x0_m"] + C_ * res, lv["y0_m"] - R_ * res
        lon, lat = inv.transform(x, y)
        exp, (sr, sc) = tif.pixel(x, y)
        aq = decode_polar(WEB / "hterrain" / "polar_s" / name / f"{key}.bin.gz", n)
        h = float(aq[i, j]) * q
        tol = q / 2 + 1e-3
        rows.append(dict(group=f"polar_s {name} ({res} m)", tile=f"polar_s/{name}/{key}", sample=[i, j], level_index=[R_, C_],
                         x_m=x, y_m=y, lat=round(lat, 6), lon=round(lon, 6),
                         source=f"PGDA {tif.file} pixel (row {sr}, col {sc})", q_m=q,
                         expected_m=round(exp, 4), expected_rounded_m=round(float(np.rint(exp / q) * q), 4), tile_m=h,
                         abs_diff_m=round(abs(h - exp), 4), tolerance_m=tol,
                         result="PASS" if abs(h - exp) <= tol else "FAIL"))
    out["hterrain"] = {"tolerance_global_m": tol_g, "tolerance_basis": "global tiles: heights rounded to 1 m -> max 0.5 m "
                       "(+0.01 m float); the decoded value must also equal round(expected). polar: q_m/2 (p20/p60 q 0.25 m "
                       "-> 0.125 m; p240 q 0.5 m -> 0.25 m) + 0.001 m", "samples": rows}
    return rows


def stats(rows):
    d = np.array([r["abs_diff_m"] for r in rows])
    return {"n": int(d.size), "max_abs_m": round(float(d.max()), 4), "mean_abs_m": round(float(d.mean()), 4),
            "pass": sum(r["result"] == "PASS" for r in rows), "fail": sum(r["result"] == "FAIL" for r in rows)}


def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    l64, l16 = LolaCyl("ldem_64_float"), LolaCyl("ldem_16_float")
    pgda = {res: PgdaTif(res) for res in (20, 60, 240)}
    out = {"what": "independent tile-vs-original-DEM check (Soyun Jeong), products by Sua Kim", "seed": SEED,
           "originals": {"LDEM_64": {"local": "data/raw/global/ldem_64_float.img", "pds_url": PDS + "ldem_64_float.img",
                                     "bytes": l64.img.stat().st_size, "label": l64.label},
                         "LDEM_16": {"local": "data/raw/global/ldem_16_float.img", "pds_url": PDS + "ldem_16_float.img",
                                     "bytes": l16.img.stat().st_size, "label": l16.label},
                         "PGDA": {r: t.meta for r, t in pgda.items()}}}
    g = check_globe(rng, l64, pgda[20], out)
    h = check_hterrain(rng, l64, l16, pgda, out)
    out["globe"]["stats"], out["hterrain"]["stats"] = stats(g), stats(h)
    out["pds_range_check"] = {"LDEM_64": l64.range_check(), "LDEM_16": l16.range_check()}
    ok_src = all(v["mismatching_ranges"] == 0 for v in out["pds_range_check"].values())
    out["result"] = {"globe": "PASS" if out["globe"]["stats"]["fail"] == 0 and ok_src else "FAIL",
                     "hterrain": "PASS" if out["hterrain"]["stats"]["fail"] == 0 and ok_src else "FAIL"}
    out["seconds"] = round(time.time() - t0, 1)
    dest = ROOT / "docs" / "terrain_tiles_verification.json"
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, rows in (("(5) globe", g), ("(6) hterrain", h)):
        print(f"\n{name}")
        for r in rows:
            print(f"  {r['result']:4} {r['tile']:26} lat {r['lat']:+10.5f} lon {r['lon']:+11.5f}  exp {r['expected_m']:10.3f}  "
                  f"tile {r['tile_m']:10.3f}  |d| {r['abs_diff_m']:.3f}  {r['source'][:60]}")
    print("\nstats", json.dumps({"globe": out["globe"]["stats"], "hterrain": out["hterrain"]["stats"]}))
    print("PDS range check", json.dumps(out["pds_range_check"]))
    print("RESULT", out["result"], "->", dest)
    return 0 if all(v == "PASS" for v in out["result"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
