"""Task E (2026-11-15): independent check of web/data/local250/ (16 south-polar 250 m grids, producer Jiyong Sung).

Checker: Soyun Jeong. No module of the producer is imported or run (local250.py, local_maps.py, horizon.py,
local250_gpu.*, fetch_polar.py, polar_prefetch.py, verify_card18_local.py, core.js adapters). Every step is
written here from docs/data_contract.md sections 0, 3, 6, 15 and 22 and from the GeoTIFF / PDS metadata:

  shared  250 m vs 1 km grid at the 121 identical (e, n) offsets per site (pure data comparison).
  dem     5 random 250 m nodes, brute force: DEM windows read again around each node from the NASA originals,
          pyproj (PROJ) for the stereographic projection, numpy bilinear, every one of the 720 x 8,001 samples
          (no early stop), and a literal hour-by-hour port of the core.js definitions.
  full    all 16 x 1,681 = 26,896 nodes: per-site DEM windows read from the same NASA originals, a numba kernel
          (closed-form stereographic, no early stop, all 720 x 8,001 samples) and a vectorised hourly loop.
          Resumable: one checkpoint file per finished site.
  report  summary JSON + Markdown tables from the three parts.

Originals: NASA PGDA LOLA polar GeoTIFFs (read over HTTP Range: tifffile IFD parse + own deflate/predictor-3 tile decoder) and LOLA LDEM_64 /
LDEM_16 float V3.1 PDS images (data/raw/global/, sizes and SHA-256 recorded). Ephemeris: web/data/ephem.bin
(the shared production input, 43,824 hourly rows; it was not produced by the producer of local250/).

Run from the repository root with the project .venv:
  python pipeline/verify_local250_independent.py shared
  python pipeline/verify_local250_independent.py dem
  python pipeline/verify_local250_independent.py full [--threads 14]
  python pipeline/verify_local250_independent.py report
Caches (DEM windows, per-site checkpoints) go to data/processed/verify_local250_independent/ (git-ignored).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/processed/verify_local250_independent"
OUT_JSON = ROOT / "docs/local250_independent_check.json"

# ---- definitions (docs/data_contract.md) ---------------------------------------------------------------
R_M = 1737400.0                      # section 0 reference sphere
R_KM = 1737.4
OBS_M = 2.0                          # section 0 observer height
N_AZ, AZ_STEP = 720, 0.5             # section 3 / 15: 720 azimuths, 0 = north, clockwise
MIN_KM, MAX_KM, N_STEPS = 0.005, 300.0, 8000   # section 15/22 params: 8,001 geometric samples 5 m .. 300 km
SUN_R_DEG = 0.2666                   # section 6: solar disc radius; sunlit = visible fraction >= 0.5
N_HOURS = 43824                      # section 2: 2026-01-01T00Z .. 2030-12-31T23Z hourly
PGDA = "https://pgda.gsfc.nasa.gov/data/"
# section 15: PGDA 5/10/20/60/80/240 m to 3/25/25/60/60/200 km measured from each node, then global LDEM to 300 km.
# File names: data/DATASETS.md (PGDA LOLA polar products).
POLAR = [
    (5, "LOLA_5mpp/87S/ldem_87s_5mpp.tif", 3.0),
    (10, "LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF", 25.0),
    (20, "LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF", 25.0),
    (60, "LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF", 60.0),
    (80, "LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF", 60.0),
    (240, "LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF", 200.0),
]
CRS = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +no_defs"
GRID250 = dict(rows=41, cols=41, spacing_m=250, origin_e_m=-5000, origin_n_m=-5000)
GRID1K = dict(rows=21, cols=21, spacing_m=1000, origin_e_m=-10000, origin_n_m=-10000)
METRICS = ["sun_frac", "earth_frac", "both_frac", "longest_dark_h"]
SEED = 2026111505                    # task E, 5 brute-force nodes
# Nodes used by the producer's own check (docs/local250.md) - not reused here.
PRODUCER_NODES = {("ARTEMIS_MOUTON_PLATEAU", 1084), ("IM1", 961), ("ARTEMIS_SLATER_PLAIN", 1003),
                  ("ARTEMIS_MOUTON", 298), ("ARTEMIS_SLATER_PLAIN", 554)}
NODE_HALF_KM = 5.0 * math.sqrt(2) + 0.01      # farthest node from the centre (corner)


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    tmp.replace(p)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 23), b""):
            h.update(b)
    return h.hexdigest()


def polar_ids():
    sites = read_json(ROOT / "web/data/sites.json")
    return [s for s in sites if s["lat"] <= -75.0]


# ---- geometry ------------------------------------------------------------------------------------------
def enu(lat, lon):
    """Local up / east / north unit vectors (MOON_ME), as in section 6 siteFrame."""
    la, lo = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    return up, east, north


def offset_to_latlon(lat, lon, e_m, n_m):
    """Section 15: offset (e, n) -> great circle with bearing atan2(e, n) and length hypot(e, n)."""
    if e_m == 0 and n_m == 0:
        return float(lat), float(lon)
    up, east, north = enu(lat, lon)
    b, t = math.atan2(e_m, n_m), math.hypot(e_m, n_m) / R_M
    p = up * math.cos(t) + (north * math.cos(b) + east * math.sin(b)) * math.sin(t)
    return math.degrees(math.asin(max(-1.0, min(1.0, p[2])))), math.degrees(math.atan2(p[1], p[0]))


def grid_nodes(site, g):
    out = []
    for r in range(g["rows"]):
        for c in range(g["cols"]):
            e, n = g["origin_e_m"] + c * g["spacing_m"], g["origin_n_m"] + r * g["spacing_m"]
            la, lo = offset_to_latlon(site["lat"], site["lon"], e, n)
            out.append(dict(index=r * g["cols"] + c, row=r, col=c, e_m=e, n_m=n, lat=la, lon=lo))
    return out


def distances_km():
    return np.exp(np.linspace(math.log(MIN_KM), math.log(MAX_KM), N_STEPS + 1))


# ---- originals -----------------------------------------------------------------------------------------
class Ldem:
    """LOLA LDEM_<ppd> float image (simple cylindrical). Conventions read from the PDS label here."""

    def __init__(self, ppd):
        self.img = ROOT / f"data/raw/global/ldem_{ppd}_float.img"
        lbl = self.img.with_suffix(".lbl").read_text(encoding="latin-1")
        kv = {}
        for line in lbl.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv.setdefault(k.strip(), v.split("<")[0].strip().strip('"'))
        self.nl, self.ns = int(kv["LINES"]), int(kv["LINE_SAMPLES"])
        self.ppd = float(kv["MAP_RESOLUTION"])
        self.lpo, self.spo = float(kv["LINE_PROJECTION_OFFSET"]), float(kv["SAMPLE_PROJECTION_OFFSET"])
        self.clon = float(kv["CENTER_LONGITUDE"])
        assert kv["SAMPLE_TYPE"] == "PC_REAL" and kv["SAMPLE_BITS"] == "32" and kv["UNIT"] == "KILOMETER"
        assert abs(float(kv["OFFSET"]) - R_KM) < 1e-9 and float(kv.get("SCALING_FACTOR", 1)) == 1.0
        assert "MISSING_CONSTANT" not in kv
        assert self.img.stat().st_size == self.nl * self.ns * 4
        # pixel (r, c) centre: lat = (lpo - r)/ppd, lon = clon + (c - spo)/ppd  (0..360 E)
        assert abs((self.lpo + 0.5) / self.ppd - 90.0) < 1e-9            # row 0 centre = 90 - 0.5/ppd
        assert abs(self.clon - self.spo / self.ppd - 0.5 / self.ppd) < 1e-9  # column 0 centre = 0.5/ppd E
        self.a = np.memmap(self.img, dtype="<f4", mode="r", shape=(self.nl, self.ns))
        self.res_m = math.radians(1 / self.ppd) * R_M

    def sample(self, lat, lon):
        """Bilinear between pixel centres; rows clamped at the poles, columns wrap (metres)."""
        r = np.clip(self.lpo - np.asarray(lat) * self.ppd, 0, self.nl - 1)
        c = self.spo + (np.mod(lon, 360.0) - self.clon) * self.ppd
        r0 = np.minimum(np.floor(r).astype(np.int64), self.nl - 2)
        fr = r - r0
        c0f = np.floor(c)
        fc = c - c0f
        c0 = c0f.astype(np.int64) % self.ns
        c1 = (c0 + 1) % self.ns
        a = self.a
        v = (1 - fr) * ((1 - fc) * a[r0, c0] + fc * a[r0, c1]) + fr * ((1 - fc) * a[r0 + 1, c0] + fc * a[r0 + 1, c1])
        return v * 1000.0


class HttpFile:
    """Minimal seekable read-only file over HTTP Range (1 MiB blocks kept in memory), enough for tifffile's IFD parse."""
    BLOCK = 1 << 20

    def __init__(self, url):
        import requests
        self.url, self.pos, self.blocks = url, 0, {}
        self.s = requests.Session()
        h = self.s.head(url, timeout=60, allow_redirects=True)
        h.raise_for_status()
        self.size = int(h.headers["Content-Length"])

    def _block(self, k):
        if k not in self.blocks:
            a, b = k * self.BLOCK, min(self.size, (k + 1) * self.BLOCK) - 1
            for t in range(6):
                try:
                    r = self.s.get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=120)
                    assert r.status_code == 206 and len(r.content) == b - a + 1
                    self.blocks[k] = r.content
                    break
                except Exception:  # noqa: BLE001
                    if t == 5:
                        raise
                    time.sleep(5 * (t + 1))
        return self.blocks[k]

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        out = bytearray()
        while len(out) < n:
            k, o = divmod(self.pos + len(out), self.BLOCK)
            out += self._block(k)[o:o + n - len(out)]
        self.pos += n
        return bytes(out)

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def tell(self):
        return self.pos

    def seekable(self):
        return True

    def readable(self):
        return True

    def close(self):
        self.s.close()


_TIFF = {}


def tiff_meta(url):
    """Header of a PGDA GeoTIFF: size, tiles, georeferencing, compression (parsed with tifffile from HTTP ranges)."""
    if url not in _TIFF:
        import tifffile
        f = HttpFile(url)
        with tifffile.TiffFile(f) as t:
            pg = t.pages[0]
            sx, sy, _ = pg.tags[33550].value                       # ModelPixelScale
            i, j, _, x, y, _ = pg.tags[33922].value                # ModelTiepoint
            geo = pg.geotiff_tags or {}
            nod = pg.tags.get(42113)
            _TIFF[url] = dict(width=pg.imagewidth, height=pg.imagelength, th=pg.tilelength, tw=pg.tilewidth,
                              offsets=np.array(pg.dataoffsets, np.int64), counts=np.array(pg.databytecounts, np.int64),
                              res=float(sx), sy=float(sy), left=float(x - i * sx), top=float(y + j * sy),
                              raster_type=geo.get("GTRasterTypeGeoKey"), compression=int(pg.compression),
                              predictor=int(pg.predictor), dtype=str(pg.dtype), bits=pg.bitspersample,
                              nodata=None if nod is None else str(nod.value).strip(chr(0)),
                              crs={k: geo.get(k) for k in ("ProjCoordTransGeoKey", "ProjNatOriginLatGeoKey",
                                                            "ProjStraightVertPoleLongGeoKey", "ProjScaleAtNatOriginGeoKey",
                                                            "GeogSemiMajorAxisGeoKey", "GeogSemiMinorAxisGeoKey",
                                                            "ProjFalseEastingGeoKey", "ProjFalseNorthingGeoKey")},
                              size=f.size)
        f.close()
    return _TIFF[url]


def read_window(res, path, cx, cy, half_m):
    """Window of a PGDA original around projected (cx, cy), decoded tile by tile with own_tile().
    Returns dict, or None when the file does not cover it. Pixel centres: x = left + (c + 0.5) res,
    y = top - (r + 0.5) res (pixel-is-area)."""
    from concurrent.futures import ThreadPoolExecutor
    url = PGDA + path
    m = tiff_meta(url)
    assert abs(m["res"] - res) < 1e-9 and abs(m["sy"] - res) < 1e-9
    assert m["raster_type"] in (1, None) or str(m["raster_type"]).endswith("PixelIsArea") or int(m["raster_type"]) == 1
    assert m["compression"] == 8 and m["predictor"] == 3 and m["dtype"] == "float32"   # deflate, float predictor
    c = m["crs"]
    assert int(c["ProjCoordTransGeoKey"]) == 15 and c["ProjNatOriginLatGeoKey"] == -90 and c["ProjStraightVertPoleLongGeoKey"] == 0
    assert c["ProjScaleAtNatOriginGeoKey"] == 1 and c["GeogSemiMajorAxisGeoKey"] == R_M == c["GeogSemiMinorAxisGeoKey"]
    c0 = max(0, math.floor((cx - half_m - m["left"]) / res - 0.5))
    c1 = min(m["width"], math.ceil((cx + half_m - m["left"]) / res - 0.5) + 1)
    r0 = max(0, math.floor((m["top"] - (cy + half_m)) / res - 0.5))
    r1 = min(m["height"], math.ceil((m["top"] - (cy - half_m)) / res - 0.5) + 1)
    if c0 >= c1 or r0 >= r1:
        return None
    th, tw = m["th"], m["tw"]
    ncol = -(-m["width"] // tw)
    out = np.full((r1 - r0, c1 - c0), np.nan, np.float32)
    jobs = [(ty, tx) for ty in range(r0 // th, (r1 - 1) // th + 1) for tx in range(c0 // tw, (c1 - 1) // tw + 1)]

    def one(job):
        ty, tx = job
        k = ty * ncol + tx
        return job, own_tile(url, int(m["offsets"][k]), int(m["counts"][k]), th, tw)

    with ThreadPoolExecutor(8) as ex:
        for (ty, tx), full in ex.map(one, jobs):
            ya, yb = max(r0, ty * th), min(r1, (ty + 1) * th)
            xa, xb = max(c0, tx * tw), min(c1, (tx + 1) * tw)
            out[ya - r0:yb - r0, xa - c0:xb - c0] = full[ya - ty * th:yb - ty * th, xa - tx * tw:xb - tx * tw]
    if m["nodata"] not in (None, "", "nan", "NaN"):
        out[out == np.float32(float(m["nodata"]))] = np.nan
    if not np.isfinite(out).any():
        return None
    return dict(a=out, x0=m["left"] + (c0 + 0.5) * res, y0=m["top"] - (r0 + 0.5) * res, res=float(res),
                bounds=[r0, r1, c0, c1], shape=[m["height"], m["width"]], crs=c, reader="own tifffile-IFD + zlib")


def own_tile(url, offset, nbytes, th, tw):
    """Decode one deflate + floating-point-predictor (TIFF predictor 3) float32 tile fetched by HTTP Range.
    Predictor 3: each row stores the 4 byte planes (most significant first), byte-wise horizontally differenced."""
    import zlib
    import requests
    for k in range(6):
        try:
            b = requests.get(url, headers={"Range": f"bytes={offset}-{offset + nbytes - 1}"}, timeout=120).content
            assert len(b) == nbytes
            raw = np.frombuffer(zlib.decompress(b), np.uint8).reshape(th, 4 * tw)
            break
        except Exception:  # noqa: BLE001
            if k == 5:
                raise
            time.sleep(5 * (k + 1))
    und = np.cumsum(raw, axis=1, dtype=np.uint64).astype(np.uint8)     # undo byte differencing (mod 256)
    planes = und.reshape(th, 4, tw).transpose(0, 2, 1)                 # (row, sample, byte MSB..LSB)
    return np.ascontiguousarray(planes).view(">f4").reshape(th, tw).astype(np.float32)


def source_headers():
    import requests
    out = {}
    for res, path, gate in POLAR:
        h = requests.head(PGDA + path, timeout=60, allow_redirects=True).headers
        out[res] = dict(url=PGDA + path, content_length=int(h.get("Content-Length", -1)),
                        last_modified=h.get("Last-Modified"), etag=h.get("ETag"), gate_km=gate)
    return out


def proj_fwd():
    from pyproj import Transformer
    return Transformer.from_crs("+proj=longlat +R=1737400 +no_defs", CRS, always_xy=True)


# ---- metrics: literal port of core.js (section 6) ------------------------------------------------------
def load_ephem():
    e = np.fromfile(ROOT / "web/data/ephem.bin", dtype="<f4")
    meta = read_json(ROOT / "web/data/ephem.json")
    assert meta["n"] == N_HOURS and e.size == N_HOURS * 6 and meta["start"] == "2026-01-01T00:00:00Z"
    return e.astype(np.float64).reshape(N_HOURS, 6)


def core_metrics_literal(lat, lon, h0_m, mask, eph):
    """Hour-by-hour, scalar, exactly the core.js statements (bodyVec at integer hours, last hour t = 1)."""
    la, lo = math.radians(lat), math.radians(lon)
    sl, cl, so, co = math.sin(la), math.cos(la), math.sin(lo), math.cos(lo)
    east, north, up = (-so, co, 0.0), (-sl * co, -sl * so, cl), (cl * co, cl * so, sl)
    r = R_KM + (h0_m + 2) / 1000
    o = (up[0] * r, up[1] * r, up[2] * r)
    m = [float(v) for v in mask]
    n = N_HOURS
    ns = ne = nb = run = longest = 0

    def body(i, c0):
        k = min(i, n - 2)
        t = i - k
        a, b = eph[k], eph[min(k + 1, n - 1)]
        return [a[c0 + j] + (b[c0 + j] - a[c0 + j]) * t for j in range(3)]

    def azel(v):
        e = v[0] * east[0] + v[1] * east[1] + v[2] * east[2]
        nn = v[0] * north[0] + v[1] * north[1] + v[2] * north[2]
        u = v[0] * up[0] + v[1] * up[1] + v[2] * up[2]
        az = math.degrees(math.atan2(e, nn))
        if az < 0:
            az += 360
        return az, math.degrees(math.atan2(u, math.hypot(e, nn)))

    def hz_at(az):
        x = ((az % 360) + 360) % 360 / AZ_STEP
        k = int(math.floor(x)) % N_AZ
        t = x - math.floor(x)
        return m[k] + (m[(k + 1) % N_AZ] - m[k]) * t

    for i in range(n):
        s = body(i, 0)
        az, el = azel([s[0] - o[0], s[1] - o[1], s[2] - o[2]])
        y = (hz_at(az) - el) / SUN_R_DEG
        frac = 1.0 if y <= -1 else 0.0 if y >= 1 else (math.acos(y) - y * math.sqrt(1 - y * y)) / math.pi
        sun = frac >= 0.5
        g = body(i, 3)
        az, el = azel([g[0] - o[0], g[1] - o[1], g[2] - o[2]])
        earth = el > hz_at(az)
        ns += sun
        ne += earth
        nb += sun and earth
        run = 0 if sun else run + 1
        longest = max(longest, run)
    return dict(sun_frac=ns / n, earth_frac=ne / n, both_frac=nb / n, longest_dark_h=longest)


def body_rows(eph):
    """core.js bodyVec at integer hours: row i, except the last hour = a + (b - a) * 1 from rows n-2, n-1."""
    rows = eph.copy()
    a, b = eph[-2], eph[-1]
    rows[-1] = a + (b - a) * 1.0
    return rows


def core_metrics_vec(lat, lon, h0_m, mask, rows):
    """Vectorised version of the same definitions (used for the full run)."""
    la, lo = math.radians(lat), math.radians(lon)
    sl, cl, so, co = math.sin(la), math.cos(la), math.sin(lo), math.cos(lo)
    east, north, up = np.array([-so, co, 0.0]), np.array([-sl * co, -sl * so, cl]), np.array([cl * co, cl * so, sl])
    r = R_KM + (h0_m + 2) / 1000
    o = up * r
    m = np.asarray(mask, np.float64)
    m1 = np.roll(m, -1)

    def visible(v):
        e, nn, u = v @ east, v @ north, v @ up
        az = np.degrees(np.arctan2(e, nn))
        az = np.where(az < 0, az + 360, az)
        el = np.degrees(np.arctan2(u, np.hypot(e, nn)))
        x = np.mod(np.mod(az, 360) + 360, 360) / AZ_STEP
        fl = np.floor(x)
        k = fl.astype(np.int64) % N_AZ
        return el, m[k] + (m1[k] - m[k]) * (x - fl)

    el, hm = visible(rows[:, 0:3] - o)
    y = (hm - el) / SUN_R_DEG
    yc = np.clip(y, -1, 1)
    frac = np.where(y <= -1, 1.0, np.where(y >= 1, 0.0, (np.arccos(yc) - yc * np.sqrt(1 - yc * yc)) / np.pi))
    sun = frac >= 0.5
    el, hm = visible(rows[:, 3:6] - o)
    earth = el > hm
    dark = ~sun
    longest = 0
    if dark.any():
        d = np.diff(np.concatenate([[0], dark.view(np.int8), [0]]))
        longest = int((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).max())
    n = N_HOURS
    return dict(sun_frac=int(sun.sum()) / n, earth_frac=int(earth.sum()) / n,
                both_frac=int((sun & earth).sum()) / n, longest_dark_h=longest)


def stored_rounding(h0_m, mask_deg):
    """Section 15/3 storage the production metrics use: h0 to 0.01 m, mask to 0.0001 deg."""
    return round(float(h0_m), 2), [round(float(v), 4) for v in mask_deg]


# ---- part 1: shared nodes ------------------------------------------------------------------------------
def run_shared():
    rows, mism = [], []
    for s in polar_ids():
        a = read_json(ROOT / f"web/data/local250/{s['id']}.json")
        b = read_json(ROOT / f"web/data/local/{s['id']}.json")
        assert {k: a["grid"][k] for k in GRID250} == GRID250 and {k: b["grid"][k] for k in GRID1K} == GRID1K
        assert len(a["points"]) == 1681 and len(b["points"]) == 441
        assert a["center"]["lat"] == b["center"]["lat"] == s["lat"] and a["center"]["lon"] == b["center"]["lon"] == s["lon"]
        pa = {(p["e_m"], p["n_m"]): p for p in a["points"]}
        pb = {(p["e_m"], p["n_m"]): p for p in b["points"]}
        keys = sorted(set(pa) & set(pb))
        d = {k: [] for k in METRICS}
        pos = []
        nm = 0
        for key in keys:
            p, q = pa[key], pb[key]
            pos.append(max(abs(p["lat"] - q["lat"]), abs(p["lon"] - q["lon"])))
            bad = False
            for k in METRICS:
                diff = abs(p[k] - q[k]) * (1 if k == "longest_dark_h" else 100)
                d[k].append(diff)
                bad |= p[k] != q[k]
            if bad or p["h0_m"] != q["h0_m"]:
                nm += 1
                mism.append(dict(site=s["id"], e_m=key[0], n_m=key[1], **{f"{k}_250": p[k] for k in METRICS},
                                 **{f"{k}_1km": q[k] for k in METRICS}, h0_250=p["h0_m"], h0_1km=q["h0_m"]))
        fr = np.concatenate([d["sun_frac"], d["earth_frac"], d["both_frac"]])
        rows.append(dict(site=s["id"], shared=len(keys), max_pos_diff_deg=max(pos),
                         **{f"median_{k}_pp": float(np.median(d[k])) for k in METRICS[:3]},
                         **{f"max_{k}_pp": float(np.max(d[k])) for k in METRICS[:3]},
                         median_fraction_pp=float(np.median(fr)), max_fraction_pp=float(fr.max()),
                         max_dark_h=float(max(d["longest_dark_h"])), mismatches=nm,
                         h0_equal=all(pa[k]["h0_m"] == pb[k]["h0_m"] for k in keys)))
        print(f"{s['id']:26s} shared {len(keys)}  max {fr.max():.6f} pp  dark {max(d['longest_dark_h'])} h  mismatches {nm}")
    tot = sum(r["shared"] for r in rows)
    out = dict(sites=rows, total_shared=tot, total_mismatches=sum(r["mismatches"] for r in rows), mismatches=mism,
               rule="identical (e_m, n_m) offsets; lat/lon of both files also compared")
    write_json(CACHE / "shared.json", out)
    print("total shared", tot, "mismatching nodes", out["total_mismatches"])
    return out


# ---- part 2: brute force at 5 nodes (numpy + pyproj, no early stop) ------------------------------------
def pick_nodes():
    sites = sorted(s["id"] for s in polar_ids())
    rng = np.random.default_rng(SEED)
    chosen = rng.choice(len(sites), 5, replace=False)
    out = []
    for i in chosen:
        cand = [j for j in range(1681) if (j // 41 % 4 or j % 41 % 4) and (sites[i], j) not in PRODUCER_NODES]
        out.append((sites[i], int(rng.choice(cand))))
    return out


def brute_horizon(lat, lon, wins, ldems, fwd):
    """Every one of the 720 x 8,001 samples. wins: list of (res, gate, window or None) finest first."""
    s_km = distances_km()
    up, east, north = enu(lat, lon)

    def chain(la, lo, d_km, used):
        x, y = fwd.transform(lo, la)
        h = np.full(la.shape, np.nan)
        for res, gate, w in wins:
            need = np.isnan(h) & (d_km <= gate)
            if w is None or not need.any():
                continue
            r = (w["y0"] - y[need]) / w["res"]
            c = (x[need] - w["x0"]) / w["res"]
            v = bilinear(w["a"], r, c)
            h[need] = v
            ok = np.isfinite(v)
            if ok.any():
                used[res] = max(used.get(res, 0.0), float(d_km[need][ok].max()))
        for name, ld in ldems:
            need = np.isnan(h) & (d_km <= MAX_KM)
            if need.any():
                v = ld.sample(la[need], lo[need])
                h[need] = v
                ok = np.isfinite(v)
                if ok.any():
                    used[name] = max(used.get(name, 0.0), float(d_km[need][ok].max()))
        return h

    gres = {}
    h0 = float(chain(np.array([lat]), np.array([lon]), np.array([0.0]), gres)[0])
    ground = next(iter(gres))
    ro = R_M + h0 + OBS_M
    used = {}
    mask = np.empty(N_AZ)
    th = s_km * 1000.0 / R_M
    ct, st = np.cos(th), np.sin(th)
    for k0 in range(0, N_AZ, 24):
        az = np.radians(np.arange(k0, k0 + 24) * AZ_STEP)[:, None]
        d = north[:, None, None] * np.cos(az)[None] + east[:, None, None] * np.sin(az)[None]
        p = up[:, None, None] * ct[None, None, :] + d * st[None, None, :]
        la = np.degrees(np.arcsin(np.clip(p[2], -1, 1)))
        lo = np.degrees(np.arctan2(p[1], p[0]))
        dk = np.broadcast_to(s_km, la.shape)
        h = chain(la.ravel(), lo.ravel(), dk.ravel(), used).reshape(la.shape)
        assert np.isfinite(h).all(), "missing terrain sample"
        rt = R_M + h
        el = np.arctan2(rt * ct - ro, rt * st)
        mask[k0:k0 + 24] = np.degrees(el.max(axis=1))
    return mask, h0, ground, used


def bilinear(a, r, c):
    nr, nc = a.shape
    out = np.full(np.shape(r), np.nan)
    ok = (r >= 0) & (r <= nr - 1) & (c >= 0) & (c <= nc - 1)
    rr, cc = r[ok], c[ok]
    r0 = np.minimum(np.floor(rr).astype(np.int64), nr - 2)
    c0 = np.minimum(np.floor(cc).astype(np.int64), nc - 2)
    fr, fc = rr - r0, cc - c0
    out[ok] = ((1 - fr) * ((1 - fc) * a[r0, c0] + fc * a[r0, c0 + 1])
               + fr * ((1 - fc) * a[r0 + 1, c0] + fc * a[r0 + 1, c0 + 1]))
    return out


def run_dem():
    fwd = proj_fwd()
    ldems = [("LDEM_64", Ldem(64)), ("LDEM_16", Ldem(16))]
    eph = load_ephem()
    sites = {s["id"]: s for s in polar_ids()}
    res_out = []
    for sid, idx in pick_nodes():
        t0 = time.time()
        s = sites[sid]
        stored = read_json(ROOT / f"web/data/local250/{sid}.json")["points"][idx]
        r, c = divmod(idx, 41)
        e, n = -5000 + 250 * c, -5000 + 250 * r
        lat, lon = offset_to_latlon(s["lat"], s["lon"], e, n)
        x, y = fwd.transform(lon, lat)
        wins = []
        for res, path, gate in POLAR:
            wins.append((res, gate, read_window(res, path, x, y, gate * 1000 * 1.01 + 2 * res + 500)))
        mask, h0, ground, used = brute_horizon(lat, lon, wins, ldems, fwd)
        h0r, maskr = stored_rounding(h0, mask)
        m_round = core_metrics_literal(lat, lon, h0r, maskr, eph)
        m_raw = core_metrics_literal(lat, lon, h0, mask, eph)
        names = {5: "PGDA_LOLA_5M", 10: "PGDA_LOLA_10M", 20: "PGDA_LOLA_20M", 60: "PGDA_LOLA_60M",
                 80: "PGDA_LOLA_80M", 240: "PGDA_LOLA_240M"}
        src = [dict(name=names.get(k, k), to_km=round(min(v, MAX_KM), 2)) for k, v in used.items()]
        row = dict(site=sid, index=idx, row=r, col=c, e_m=e, n_m=n, lat=lat, lon=lon,
                   pos_diff_deg=max(abs(lat - stored["lat"]), abs(lon - stored["lon"])),
                   h0_m=h0, h0_stored=stored["h0_m"], ground_resolution_m=float(ground) if not isinstance(ground, str) else ground,
                   ground_stored=stored["ground_resolution_m"], sources=src, sources_stored=stored["dem_sources"],
                   windows={str(res): (None if w is None else dict(bounds=w["bounds"], shape=w["shape"])) for res, _, w in wins},
                   stored={k: stored[k] for k in METRICS}, mine=m_round, mine_unrounded_mask=m_raw,
                   mask_min=float(mask.min()), mask_max=float(mask.max()), mask=[round(float(v), 6) for v in mask])
        for tag, m in (("diff", m_round), ("diff_unrounded", m_raw)):
            row[tag] = {k: abs(m[k] - stored[k]) * (1 if k == "longest_dark_h" else 100) for k in METRICS}
        row["max_fraction_pp"] = max(row["diff"][k] for k in METRICS[:3])
        row["pass"] = row["max_fraction_pp"] <= 1.0
        row["seconds"] = round(time.time() - t0, 1)
        res_out.append(row)
        print(f"{sid} #{idx} ({e},{n}) h0 {h0:.2f}/{stored['h0_m']}  sun {m_round['sun_frac']:.6f}/{stored['sun_frac']:.6f} "
              f"earth {m_round['earth_frac']:.6f}/{stored['earth_frac']:.6f} both {m_round['both_frac']:.6f}/{stored['both_frac']:.6f} "
              f"dark {m_round['longest_dark_h']}/{stored['longest_dark_h']}  {row['seconds']} s", flush=True)
    out = dict(seed=SEED, nodes=res_out, max_fraction_pp=max(r["max_fraction_pp"] for r in res_out),
               max_dark_h=max(r["diff"]["longest_dark_h"] for r in res_out), all_pass=all(r["pass"] for r in res_out))
    write_json(CACHE / "dem5.json", out)
    return out


# ---- part 3: all nodes (numba) -------------------------------------------------------------------------
def build_kernel():
    """numba kernels (compiled on first use)."""
    import numba as nb

    @nb.njit(cache=False, inline="always")
    def bil(a, r, c):
        nr, nc = a.shape
        if not (r >= 0.0 and r <= nr - 1 and c >= 0.0 and c <= nc - 1):
            return np.nan
        r0 = min(int(math.floor(r)), nr - 2)
        c0 = min(int(math.floor(c)), nc - 2)
        fr, fc = r - r0, c - c0
        return ((1 - fr) * ((1 - fc) * a[r0, c0] + fc * a[r0, c0 + 1])
                + fr * ((1 - fc) * a[r0 + 1, c0] + fc * a[r0 + 1, c0 + 1]))

    @nb.njit(cache=False, inline="always")
    def ldem(a, lpo, spo, clon, ppd, px, py, pz):
        nl, ns = a.shape
        lat = math.degrees(math.asin(max(-1.0, min(1.0, pz))))
        lon = math.degrees(math.atan2(py, px)) % 360.0
        r = min(max(lpo - lat * ppd, 0.0), nl - 1.0)
        c = spo + (lon - clon) * ppd
        r0 = min(int(math.floor(r)), nl - 2)
        fr = r - r0
        c0f = math.floor(c)
        fc = c - c0f
        c0 = int(c0f) % ns
        c1 = (c0 + 1) % ns
        return 1000.0 * ((1 - fr) * ((1 - fc) * a[r0, c0] + fc * a[r0, c1])
                         + fr * ((1 - fc) * a[r0 + 1, c0] + fc * a[r0 + 1, c1]))

    @nb.njit(cache=False)
    def height(px, py, pz, d_km, a0, a1, a2, a3, a4, a5, geo, l64, g64, l16, g16, used):
        # closed-form spherical south-polar stereographic (k0 = 1 at the pole): x = 2R py/(1-pz), y = 2R px/(1-pz)
        den = 1.0 - pz
        x = 2.0 * R_M * py / den
        y = 2.0 * R_M * px / den
        for q in range(6):
            if d_km > geo[q, 3]:
                continue
            a = a0 if q == 0 else a1 if q == 1 else a2 if q == 2 else a3 if q == 3 else a4 if q == 4 else a5
            h = bil(a, (geo[q, 1] - y) / geo[q, 2], (x - geo[q, 0]) / geo[q, 2])
            if h == h:
                if d_km > used[q]:
                    used[q] = d_km
                return h, q
        h = ldem(l64, g64[0], g64[1], g64[2], g64[3], px, py, pz)
        if h == h:
            if d_km > used[6]:
                used[6] = d_km
            return h, 6
        h = ldem(l16, g16[0], g16[1], g16[2], g16[3], px, py, pz)
        if h == h and d_km > used[7]:
            used[7] = d_km
        return h, 7

    @nb.njit(parallel=True, cache=False)
    def horizons(ups, easts, norths, s_km, a0, a1, a2, a3, a4, a5, geo, l64, g64, l16, g16):
        nn = ups.shape[0]
        ns = s_km.shape[0]
        h0 = np.empty(nn)
        ground = np.empty(nn, np.int64)
        for i in range(nn):
            u0 = np.zeros(8)
            h0[i], ground[i] = height(ups[i, 0], ups[i, 1], ups[i, 2], 0.0, a0, a1, a2, a3, a4, a5, geo, l64, g64, l16, g16, u0)
        th = s_km * 1000.0 / R_M
        ct, st = np.cos(th), np.sin(th)
        mask = np.empty((nn, N_AZ))
        used = np.full((nn, N_AZ, 8), -1.0)
        missing = np.zeros(nn * N_AZ, np.int64)
        for t in nb.prange(nn * N_AZ):
            i, k = t // N_AZ, t % N_AZ
            az = math.radians(k * AZ_STEP)
            ca, sa = math.cos(az), math.sin(az)
            dx = norths[i, 0] * ca + easts[i, 0] * sa
            dy = norths[i, 1] * ca + easts[i, 1] * sa
            dz = norths[i, 2] * ca + easts[i, 2] * sa
            ro = R_M + h0[i] + OBS_M
            best = -np.inf
            u = used[i, k]
            for j in range(ns):
                px = ups[i, 0] * ct[j] + dx * st[j]
                py = ups[i, 1] * ct[j] + dy * st[j]
                pz = ups[i, 2] * ct[j] + dz * st[j]
                h, q = height(px, py, pz, s_km[j], a0, a1, a2, a3, a4, a5, geo, l64, g64, l16, g16, u)
                if h != h:
                    missing[t] += 1
                    continue
                rt = R_M + h
                el = math.atan2(rt * ct[j] - ro, rt * st[j])
                if el > best:
                    best = el
            mask[i, k] = math.degrees(best)
        return mask, h0, ground, used, missing

    return horizons


def site_windows(site):
    """Per-site windows from the originals, cached as .npy (+ .json) in CACHE/dem/."""
    fwd = proj_fwd()
    cx, cy = fwd.transform(site["lon"], site["lat"])
    out = []
    for res, path, gate in POLAR:
        base = CACHE / "dem" / f"{site['id']}_{res}"
        meta_p = base.with_suffix(".json")
        if meta_p.exists():
            meta = read_json(meta_p)
            a = np.load(base.with_suffix(".npy")) if meta["covered"] else None
        else:
            half = (NODE_HALF_KM + gate) * 1000 * 1.01 + 2 * res + 500
            t0 = time.time()
            w = read_window(res, path, cx, cy, half)
            meta = dict(covered=w is not None, res=res, gate_km=gate, url=PGDA + path, half_m=half)
            a = None
            if w is not None:
                a = w.pop("a")
                np.save(base.with_suffix(".npy"), a)
                meta.update({k: v for k, v in w.items()}, finite_frac=float(np.isfinite(a).mean()),
                            sha256=hashlib.sha256(a.tobytes()).hexdigest())
            meta["seconds"] = round(time.time() - t0, 1)
            write_json(meta_p, meta)
            print(f"  {site['id']} {res} m: {'none' if a is None else a.shape} {meta['seconds']} s", flush=True)
        out.append((res, gate, a, meta))
    return out


def run_full(threads):
    import numba as nb
    nb.set_num_threads(threads)
    (CACHE / "dem").mkdir(parents=True, exist_ok=True)
    (CACHE / "sites").mkdir(parents=True, exist_ok=True)
    kern = build_kernel()
    l64, l16 = Ldem(64), Ldem(16)
    g64 = np.array([l64.lpo, l64.spo, l64.clon, l64.ppd])
    g16 = np.array([l16.lpo, l16.spo, l16.clon, l16.ppd])
    rows = body_rows(load_ephem())
    s_km = distances_km()
    empty = np.full((2, 2), np.nan, np.float32)
    for s in polar_ids():
        done = CACHE / "sites" / f"{s['id']}.npz"
        if done.exists():
            print(f"{s['id']}: checkpoint present, skipped", flush=True)
            continue
        t0 = time.time()
        wins = site_windows(s)
        geo = np.zeros((6, 4))
        arrs = []
        for q, (res, gate, a, meta) in enumerate(wins):
            if a is None:
                geo[q] = [0, 0, 1, -1.0]          # absent source: gate -1 km, never used
                arrs.append(empty)
            else:
                geo[q] = [meta["x0"], meta["y0"], res, gate]
                arrs.append(np.ascontiguousarray(a))
        nodes = grid_nodes(s, GRID250)
        fr = [enu(p["lat"], p["lon"]) for p in nodes]
        ups = np.array([f[0] for f in fr]); easts = np.array([f[1] for f in fr]); norths = np.array([f[2] for f in fr])
        t1 = time.time()
        mask, h0, ground, used, missing = kern(ups, easts, norths, s_km, *arrs, geo, np.asarray(l64.a), g64,
                                              np.asarray(l16.a), g16)
        t2 = time.time()
        assert missing.sum() == 0, f"{s['id']}: {missing.sum()} samples without terrain"
        met_r, met_u = [], []
        for i, p in enumerate(nodes):
            h0r, mr = stored_rounding(h0[i], mask[i])
            met_r.append(core_metrics_vec(p["lat"], p["lon"], h0r, mr, rows))
            met_u.append(core_metrics_vec(p["lat"], p["lon"], h0[i], mask[i], rows))
        t3 = time.time()
        np.savez(done.with_suffix(".tmp.npz"), mask=mask.astype(np.float64), h0=h0, ground=ground,
                 used=used.max(axis=1), lat=np.array([p["lat"] for p in nodes]), lon=np.array([p["lon"] for p in nodes]),
                 metrics=np.array([[m[k] for k in METRICS] for m in met_r]),
                 metrics_unrounded=np.array([[m[k] for k in METRICS] for m in met_u]),
                 timing=np.array([t1 - t0, t2 - t1, t3 - t2]))
        done.with_suffix(".tmp.npz").replace(done)
        print(f"{s['id']}: windows {t1 - t0:.0f} s, horizons {t2 - t1:.0f} s, metrics {t3 - t2:.0f} s", flush=True)


# ---- part 4: report ------------------------------------------------------------------------------------
GROUND = {0: 5.0, 1: 10.0, 2: 20.0, 3: 60.0, 4: 80.0, 5: 240.0}
SRC_NAMES = ["PGDA_LOLA_5M", "PGDA_LOLA_10M", "PGDA_LOLA_20M", "PGDA_LOLA_60M", "PGDA_LOLA_80M", "PGDA_LOLA_240M",
             "LDEM_64", "LDEM_16"]


def run_report():
    shared = read_json(CACHE / "shared.json")
    dem = read_json(CACHE / "dem5.json") if (CACHE / "dem5.json").exists() else None
    l64r, l16r = Ldem(64).res_m, Ldem(16).res_m
    full_sites, all_d, all_du, all_dark, fails = [], [], [], [], []
    done_nodes = 0
    for s in polar_ids():
        p = CACHE / "sites" / f"{s['id']}.npz"
        if not p.exists():
            full_sites.append(dict(site=s["id"], recomputed=0, status="NOT RUN"))
            continue
        z = np.load(p)
        st = read_json(ROOT / f"web/data/local250/{s['id']}.json")["points"]
        sv = np.array([[q[k] for k in METRICS] for q in st], float)
        d = np.abs(z["metrics"] - sv)
        du = np.abs(z["metrics_unrounded"] - sv)
        dfr = d[:, :3] * 100
        node_max = dfr.max(axis=1)
        pos = max(max(abs(q["lat"] - a), abs(q["lon"] - b)) for q, a, b in zip(st, z["lat"], z["lon"]))
        h0d = np.abs(np.round(z["h0"], 2) - np.array([q["h0_m"] for q in st]))
        gr = [GROUND.get(int(g), l64r if g == 6 else l16r) for g in z["ground"]]
        gr_eq = sum(abs(a - q["ground_resolution_m"]) < 1e-6 for a, q in zip(gr, st))
        src_eq = 0
        for i, q in enumerate(st):
            mine = [(SRC_NAMES[k], round(min(float(v), MAX_KM), 2)) for k, v in enumerate(z["used"][i]) if v >= 0]
            theirs = [(x["name"], x["to_km"]) for x in q["dem_sources"]]
            # production stops marching an azimuth early (exact bound), so its to_km can be shorter than ours;
            # count nodes whose stored source names are all among the sources our full march used
            src_eq += {n for n, _ in theirs} <= {n for n, _ in mine}
        bad = np.flatnonzero(node_max > 1.0)
        for i in bad:
            fails.append(dict(site=s["id"], index=int(i), diff_pp=[float(x) for x in dfr[i]], dark_h=float(d[i, 3])))
        unr_nodes = int((du.max(axis=1) > 0).sum())
        unr_dark = float(du[:, 3].max())
        done_nodes += len(st)
        all_d.append(dfr.ravel()); all_du.append((du[:, :3] * 100).ravel()); all_dark.append(d[:, 3])
        full_sites.append(dict(site=s["id"], recomputed=len(st), pass_nodes=int((node_max <= 1.0).sum()),
                               fail_nodes=int(bad.size), median_pp=float(np.median(dfr)), max_pp=float(dfr.max()),
                               max_pp_unrounded=float((du[:, :3] * 100).max()), nodes_differ_unrounded=unr_nodes,
                               max_dark_h_unrounded=unr_dark,
                               exact_all4=int((d.max(axis=1) == 0).sum()), max_dark_h=float(d[:, 3].max()),
                               nodes_dark_differs=int((d[:, 3] > 0).sum()), max_pos_diff_deg=pos,
                               max_h0_diff_m=float(h0d.max()), ground_equal=int(gr_eq), sources_subset=int(src_eq),
                               timing_s=[round(float(t), 1) for t in z["timing"]]))
    full = dict(sites=full_sites, recomputed=done_nodes, of=16 * 1681, fail_nodes=len(fails), fails=fails[:200])
    if all_d:
        a, au, dk = np.concatenate(all_d), np.concatenate(all_du), np.concatenate(all_dark)
        full.update(max_pp=float(a.max()), median_pp=float(np.median(a)), max_pp_unrounded=float(au.max()),
                    median_pp_unrounded=float(np.median(au)), max_dark_h=float(dk.max()), median_dark_h=float(np.median(dk)),
                    nodes_dark_differs=int((dk > 0).sum()),
                    nodes_differ_unrounded=sum(r.get("nodes_differ_unrounded", 0) for r in full_sites),
                    max_dark_h_unrounded=max(r.get("max_dark_h_unrounded", 0) for r in full_sites))
    dem_cross = None
    if dem:
        dem_cross = []
        for r in dem["nodes"]:
            p = CACHE / "sites" / f"{r['site']}.npz"
            if p.exists():
                z = np.load(p)
                dem_cross.append(dict(site=r["site"], index=r["index"],
                                      max_mask_diff_deg=float(np.max(np.abs(z["mask"][r["index"]] - np.array(r["mask"])))),
                                      h0_diff_m=float(abs(z["h0"][r["index"]] - r["h0_m"]))))
    dem_gdal = None
    gp = CACHE / "dem5_gdal_reader.json"
    if gp.exists() and dem:
        g = read_json(gp)
        dem_gdal = dict(note="first run of the same brute force with GDAL /vsicurl/ windows instead of the own TIFF reader",
                        max_fraction_pp=g["max_fraction_pp"], max_dark_h=g["max_dark_h"],
                        identical_metrics=all(a["mine"] == b["mine"] and a["mine_unrounded_mask"] == b["mine_unrounded_mask"]
                                              for a, b in zip(g["nodes"], dem["nodes"])),
                        max_mask_diff_deg=max(float(np.max(np.abs(np.array(a["mask"]) - np.array(b["mask"]))))
                                              for a, b in zip(g["nodes"], dem["nodes"])))
    rr = read_json(CACHE / "rereader.json") if (CACHE / "rereader.json").exists() else None
    out = dict(task="E", product="web/data/local250/", producer="Jiyong Sung", checker="Soyun Jeong",
               criterion_fraction_pp=1.0, shared=shared, dem=dem, dem_gdal_reader=dem_gdal, gdal_windows_reread=rr, full=full, full_vs_bruteforce=dem_cross,
               inputs=inputs_record(), script="pipeline/verify_local250_independent.py")
    write_json(OUT_JSON, out)
    print(json.dumps(dict(shared_total=shared["total_shared"], shared_mismatch=shared["total_mismatches"],
                          dem_max=dem and dem["max_fraction_pp"], full_done=done_nodes,
                          full_max=full.get("max_pp"), full_fail=len(fails), cross=dem_cross), indent=1))


def run_rereader():
    """Windows cached by the first (GDAL /vsicurl/) reader are read again with the own TIFF reader and compared."""
    fwd = proj_fwd()
    rows = []
    for s in polar_ids():
        cx, cy = fwd.transform(s["lon"], s["lat"])
        for res, path, gate in POLAR:
            meta = read_json(CACHE / "dem" / f"{s['id']}_{res}.json")
            if not meta["covered"] or meta.get("reader"):
                continue
            w = read_window(res, path, cx, cy, meta["half_m"])
            a = np.load(CACHE / "dem" / f"{s['id']}_{res}.npy")
            same = (w is not None and w["bounds"] == meta["bounds"] and w["x0"] == meta["x0"] and w["y0"] == meta["y0"]
                    and np.array_equal(w["a"], a, equal_nan=True))
            rows.append(dict(site=s["id"], res=res, shape=list(a.shape), identical=bool(same)))
            print(s["id"], res, a.shape, "identical" if same else "DIFFERENT", flush=True)
    write_json(CACHE / "rereader.json", dict(windows=rows, all_identical=all(r["identical"] for r in rows)))


def run_tables():
    """Markdown tables for docs/local250_independent_check.md, printed from the JSON."""
    d = read_json(OUT_JSON)
    f = lambda x: f"{x:.6f}"  # noqa: E731
    print(r"| Site | Shared nodes | Median \|Δ\| (pp) | Max \|Δ\| (pp) | Max darkness Δ (h) | Mismatching nodes |")
    print("|---|---:|---:|---:|---:|---:|")
    for r in d["shared"]["sites"]:
        print(f"| {r['site']} | {r['shared']} | {f(r['median_fraction_pp'])} | {f(r['max_fraction_pp'])} | {r['max_dark_h']:.0f} | {r['mismatches']} |")
    print()
    print(r"| Site | Node (row, col) | e, n (m) | Lat, lon | Stored sun / earth / both / dark | Recomputed | \|Δ\| (pp, pp, pp, h) | Unrounded-mask \|Δ\| | Result |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in d["dem"]["nodes"]:
        st, mi, df, du = r["stored"], r["mine"], r["diff"], r["diff_unrounded"]
        q = lambda m: f"{m['sun_frac']:.6f} / {m['earth_frac']:.6f} / {m['both_frac']:.6f} / {m['longest_dark_h']}"  # noqa: E731
        dd = lambda m: f"{m['sun_frac']:.6f}, {m['earth_frac']:.6f}, {m['both_frac']:.6f}, {m['longest_dark_h']:.0f}"  # noqa: E731
        print(f"| {r['site']} | {r['index']} ({r['row']}, {r['col']}) | {r['e_m']}, {r['n_m']} | {r['lat']:.6f}, {r['lon']:.6f} | "
              f"{q(st)} | {q(mi)} | {dd(df)} | {dd(du)} | {'PASS' if r['pass'] else 'FAIL'} |")
    print()
    print(r"| Site | Nodes recomputed | PASS / FAIL | All 4 exact | Median \|Δ\| (pp) | Max \|Δ\| (pp) | Max \|Δ\| unrounded mask (pp) | Max darkness Δ (h) | h0 max Δ (m) | Ground res. equal |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in d["full"]["sites"]:
        if not r["recomputed"]:
            print(f"| {r['site']} | 0 | NOT RUN | | | | | | | |")
            continue
        print(f"| {r['site']} | {r['recomputed']} | {r['pass_nodes']} / {r['fail_nodes']} | {r['exact_all4']} | {f(r['median_pp'])} | "
              f"{f(r['max_pp'])} | {f(r['max_pp_unrounded'])} | {r['max_dark_h']:.0f} | {r['max_h0_diff_m']:.2f} | {r['ground_equal']} |")


def inputs_record():
    rec = dict(ldem={}, pgda=None, ephem_bin_sha256=sha256(ROOT / "web/data/ephem.bin"))
    for ppd in (64, 16):
        p = ROOT / f"data/raw/global/ldem_{ppd}_float.img"
        rec["ldem"][ppd] = dict(path=p.relative_to(ROOT).as_posix(), size=p.stat().st_size, sha256=sha256(p),
                                label_sha256=sha256(p.with_suffix(".lbl")))
    hp = CACHE / "pgda_headers.json"
    if not hp.exists():
        try:
            write_json(hp, source_headers())
        except Exception as e:  # noqa: BLE001
            print("HEAD failed:", e)
    if hp.exists():
        rec["pgda"] = read_json(hp)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["shared", "dem", "full", "report", "tables", "rereader"])
    ap.add_argument("--threads", type=int, default=14)
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    {"shared": run_shared, "dem": run_dem, "full": lambda: run_full(a.threads), "report": run_report, "tables": run_tables, "rereader": run_rereader}[a.part]()


if __name__ == "__main__":
    sys.exit(main())
