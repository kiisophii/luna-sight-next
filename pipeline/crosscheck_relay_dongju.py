"""Task N (2026-11-15, Dongju): independent FULL recomputation of web/data/relay/ (33 sites).

Own code only: nothing is imported from pipeline/ or web/js/. Definitions are taken from
docs/data_contract.md section 12 / 12.1 and CLAUDE.md, and terrain is read directly from the
original NASA rasters (PGDA LOLA south-polar GeoTIFFs, SLDEM2015 512 ppd tiles, LOLA LDEM_64).

For every site, for every published tower (the four `best` towers and every `networks[].towers`
entry) this script recomputes, at hourly steps over the 43,824-hour window of web/data/ephem.bin:
  * lander direct Earth visibility (lander antenna 2 m, own 720-bin horizon),
  * tower ground height, tower <-> lander (or parent tower) line of sight with lunar curvature,
    minimum clearance and first-Fresnel clearance ratio (S 2.2 GHz, Ka 26 GHz),
  * tower-top Earth visibility (Earth centre above the tower-top horizon mask),
  * tower-top sunlit fraction (>= half the solar disk) and longest dark run,
  * single-tower link fraction  = direct OR (link AND tower sees Earth),
  * network link fractions by number of towers, longest gap and the hourly timeline codes.

Terrain chain (input definition, as recorded in each relay file's dem_sources/input_identity):
finest source first; a sample at great-circle distance d from the LANDER uses source k if
d <= gate_k and the source has data there (NaN falls through). PGDA windows are the squares of
half-width gate_k around the lander in polar-stereographic metres; SLDEM2015 is the 150 km cap;
LDEM_64 / LDEM_16 are global. Bilinear interpolation between pixel centres.

It also checks all 5,025 candidates x 4 heights of every site (`candidates`: ground, slope,
LOS and Fresnel at 1 m, 5 m and the producer's documented block sampling; `candidates-earth`:
tower-top Earth visibility -> tower_earth_pm / lander_link_pm).

    python pipeline/crosscheck_relay_dongju.py fetch             # DEM windows (resumable)
    python pipeline/crosscheck_relay_dongju.py run [--site ID]   # per-site results (resumable)
    python pipeline/crosscheck_relay_dongju.py candidates        # candidate LOS/ground/slope
    python pipeline/crosscheck_relay_dongju.py candidates-earth  # candidate tower Earth (slow)
    python pipeline/crosscheck_relay_dongju.py report            # docs/crosscheck_relay_dongju.{json,md}
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
WORK = Path(os.environ.get("RELAY_XCHECK_WORK", ROOT / "data" / "processed" / "crosscheck_relay_dongju"))
DEM = WORK / "dem"
OUT_SITES = WORK / "sites"

R = 1737400.0                  # m, reference sphere (contract section 0)
C_LIGHT = 299_792_458.0
SUN_RADIUS_DEG = 0.2666        # contract section 6
LANDER_ANT = 2.0
N_AZ, AZ_STEP = 720, 0.5
DIST_M = np.geomspace(5.0, 300_000.0, 8001)   # params min_km 0.005, max_km 300, n_steps 8000

PGDA = "https://pgda.gsfc.nasa.gov/data/"
PGDA_FILES = {"PGDA_LOLA_5M": ("LOLA_5mpp/87S/ldem_87s_5mpp.tif", 5.0),
              "PGDA_LOLA_10M": ("LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF", 10.0),
              "PGDA_LOLA_20M": ("LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF", 20.0),
              "PGDA_LOLA_60M": ("LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF", 60.0),
              "PGDA_LOLA_80M": ("LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF", 80.0),
              "PGDA_LOLA_240M": ("LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF", 240.0)}
PDS = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/"
SLDEM_DIR = PDS + "sldem2015/tiles/float_img/"
LDEM_DIR = PDS + "lola_gdr/cylindrical/float_img/"
SLDEM_PPD = 512


# ============================================================ HTTP helpers
def http_get(url, rng=None, timeout=180):
    for attempt in range(6):
        try:
            hdr = {"Range": rng} if rng else {}
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout) as r:
                return r.read(), dict(r.headers)
        except Exception:  # noqa: BLE001
            if attempt == 5:
                raise
            time.sleep(3 * (attempt + 1))


def http_ranges(url, ranges):
    """Fetch several byte ranges in one request (multipart/byteranges). Returns list of bytes."""
    if len(ranges) == 1:
        a, b = ranges[0]
        d, _ = http_get(url, f"bytes={a}-{b}")
        assert len(d) == b - a + 1
        return [d]
    spec = "bytes=" + ",".join(f"{a}-{b}" for a, b in ranges)
    body, hdr = http_get(url, spec)
    ctype = next(v for k, v in hdr.items() if k.lower() == "content-type")
    m = re.search(r'boundary="?([^";]+)"?', ctype)
    if not m:
        raise IOError("server did not return multipart/byteranges")
    sep = b"--" + m.group(1).encode()
    got = {}
    for part in body.split(sep)[1:]:
        if part.startswith(b"--"):
            break
        head, _, data = part.partition(b"\r\n\r\n")
        cr = re.search(rb"Content-Range:\s*bytes\s+(\d+)-(\d+)/", head, re.I)
        a, b = int(cr.group(1)), int(cr.group(2))
        got[(a, b)] = data[: b - a + 1]
    return [got[(a, b)] for a, b in ranges]


class HttpFile:
    """Minimal seekable reader for tifffile (header/IFD only; tiles are fetched separately)."""

    def __init__(self, url, block=1 << 18):
        self.url, self.block, self.pos, self.cache = url, block, 0, {}
        _, h = http_get(url, "bytes=0-0")
        cr = next(v for k, v in h.items() if k.lower() == "content-range")
        self.size = int(cr.split("/")[-1])

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        n = self.size - self.pos if n is None or n < 0 else min(n, self.size - self.pos)
        out = bytearray()
        while len(out) < n:
            k = (self.pos + len(out)) // self.block
            if k not in self.cache:
                a = k * self.block
                self.cache[k] = http_ranges(self.url, [(a, min(self.size, a + self.block) - 1)])[0]
            o = self.pos + len(out) - k * self.block
            out += self.cache[k][o:o + n - len(out)]
        self.pos += n
        return bytes(out)

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)

    def seekable(self):
        return True

    def readable(self):
        return True

    def close(self):
        pass


# ============================================================ geometry (own)
def frame(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    return up, east, north


def walk(lat, lon, az_deg, dist_m):
    """Great-circle destination from (lat, lon) along azimuth az for distance dist (broadcast)."""
    up, east, north = frame(lat, lon)
    a = np.radians(az_deg)
    t = np.asarray(dist_m, float) / R
    ct, st = np.cos(t), np.sin(t)
    d = [north[i] * np.cos(a) + east[i] * np.sin(a) for i in range(3)]
    p = [up[i] * ct + d[i] * st for i in range(3)]
    return np.degrees(np.arcsin(np.clip(p[2], -1, 1))), np.degrees(np.arctan2(p[1], p[0]))


def gc_km(lat0, lon0, lat, lon):
    p0, p = np.radians(lat0), np.radians(lat)
    dl = np.radians(np.asarray(lon) - lon0)
    a = np.sin((p - p0) / 2) ** 2 + math.cos(p0) * np.cos(p) * np.sin(dl / 2) ** 2
    return 2 * R / 1000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def bearing_angle(lat_a, lon_a, lat_b, lon_b):
    """Azimuth at A towards B (deg) and central angle (rad)."""
    up, east, north = frame(lat_a, lon_a)
    ub, _, _ = frame(lat_b, lon_b)
    c = float(ub @ up)
    t = ub - c * up
    return math.degrees(math.atan2(t @ east, t @ north)) % 360.0, math.atan2(np.linalg.norm(t), c)


def ps_south(lat, lon):
    """Spherical south polar stereographic, k0 = 1, R = 1737.4 km (PGDA rasters)."""
    rho = 2 * R * np.tan(np.pi / 4 + np.radians(lat) / 2)
    lo = np.radians(lon)
    return rho * np.sin(lo), rho * np.cos(lo)


def bilinear(img, r, c):
    nr, nc = img.shape
    out = np.full(r.shape, np.nan)
    ok = (r >= 0) & (r <= nr - 1) & (c >= 0) & (c <= nc - 1)
    if ok.any():
        rr, cc = r[ok], c[ok]
        r0 = np.minimum(np.floor(rr).astype(np.int64), nr - 2)
        c0 = np.minimum(np.floor(cc).astype(np.int64), nc - 2)
        fr, fc = rr - r0, cc - c0
        out[ok] = ((1 - fr) * ((1 - fc) * img[r0, c0] + fc * img[r0, c0 + 1])
                   + fr * ((1 - fc) * img[r0 + 1, c0] + fc * img[r0 + 1, c0 + 1]))
    return out


# ============================================================ terrain sources
class PolarWindow:
    def __init__(self, path):
        z = np.load(path)
        self.h = z["h"].astype(np.float64)
        self.xc0, self.yc0, self.res = float(z["xc0"]), float(z["yc0"]), float(z["res"])

    def sample(self, lat, lon):
        x, y = ps_south(lat, lon)
        return bilinear(self.h, (self.yc0 - y) / self.res, (x - self.xc0) / self.res)


class LatLonWindow:
    def __init__(self, path):
        z = np.load(path)
        self.h = z["h"].astype(np.float64)
        self.g0, self.k0, self.ppd = int(z["g0"]), int(z["k0"]), float(z["ppd"])
        self.lonmid = (self.k0 + 0.5 + (self.h.shape[1] - 1) / 2) / self.ppd

    def sample(self, lat, lon):
        lon = (np.asarray(lon) - self.lonmid + 180.0) % 360.0 + self.lonmid - 180.0
        r = (90.0 - lat) * self.ppd - 0.5 - self.g0
        c = lon * self.ppd - 0.5 - self.k0
        return bilinear(self.h, r, c)


class GlobalGrid:
    def __init__(self, img, ppd, nl, ns):
        self.d = np.memmap(img, dtype="<f4", mode="r", shape=(nl, ns))
        self.ppd, self.nl, self.ns = ppd, nl, ns
        self.lpo, self.spo = nl / 2 - 0.5, ns / 2 - 0.5   # label: centre lon 180, max lat 90

    def sample(self, lat, lon):
        r = np.clip(self.lpo - np.asarray(lat) * self.ppd, 0, self.nl - 1)
        c = self.spo + (np.mod(lon, 360.0) - 180.0) * self.ppd
        r0 = np.minimum(np.floor(r).astype(np.int64), self.nl - 2)
        c0f = np.floor(c)
        fr, fc = r - r0, c - c0f
        c0 = c0f.astype(np.int64) % self.ns
        c1 = (c0 + 1) % self.ns
        d = self.d
        v = ((1 - fr) * ((1 - fc) * d[r0, c0] + fc * d[r0, c1])
             + fr * ((1 - fc) * d[r0 + 1, c0] + fc * d[r0 + 1, c1]))
        return v.astype(np.float64) * 1000.0


class Terrain:
    """Anchored chain: source choice by distance from the lander (contract 12.1)."""

    def __init__(self, lat0, lon0, sources):
        self.lat0, self.lon0, self.sources = lat0, lon0, sources   # [(name, gate_km, sampler)]

    def height(self, lat, lon):
        lat, lon = np.asarray(lat, float), np.asarray(lon, float)
        shp = lat.shape
        lat, lon = lat.ravel(), lon.ravel()
        dk = gc_km(self.lat0, self.lon0, lat, lon)
        h = np.full(lat.shape, np.nan)
        for _, gate, s in self.sources:
            need = np.isnan(h) & (dk <= gate)
            if need.any():
                h[need] = s.sample(lat[need], lon[need])
        return h.reshape(shp)


def site_terrain(rec):
    gates = {d["name"]: (math.inf if d["name"].startswith("LDEM_") else float(d["radius_km"]))
             for d in rec["input_identity"]["dem"]}
    src = []
    for d in rec["dem_sources"]:
        n = d["name"]
        if n.startswith("PGDA_"):
            s = PolarWindow(DEM / rec["id"] / f"{n}.npz")
        elif n == "SLDEM2015":
            s = LatLonWindow(DEM / rec["id"] / "SLDEM2015.npz")
        elif n == "LDEM_64":
            s = GlobalGrid(DEM / "ldem_64_float.img", 64, 11520, 23040)
        elif n == "LDEM_16":
            s = GlobalGrid(DEM / "ldem_16_float.img", 16, 2880, 5760)
        else:
            raise ValueError(n)
        src.append((n, gates[n], s))
    return Terrain(rec["lat"], rec["lon"], src)


# ============================================================ fetch (original rasters)
def fetch_pgda_window(sid, lat, lon, name, gate_km, out):
    import tifffile
    path, res = PGDA_FILES[name]
    url = PGDA + path
    if out.exists():
        return f"{sid} {name}: cached"
    tiles_dir = DEM / "_pgda_tiles" / Path(path).stem
    tiles_dir.mkdir(parents=True, exist_ok=True)
    f = HttpFile(url)
    with tifffile.TiffFile(f) as t:
        p = t.pages[0]
        g = p.geotiff_tags
        X0, Y0 = g["ModelTiepoint"][3], g["ModelTiepoint"][4]
        assert abs(g["ModelPixelScale"][0] - res) < 1e-9 and g["GTRasterTypeGeoKey"] == 1
        assert g["ProjNatOriginLatGeoKey"] == -90.0 and g["GeogSemiMajorAxisGeoKey"] == R
        H, W, tw, tl = p.imagelength, p.imagewidth, p.tilewidth, p.tilelength
        offs, cnts, decode = p.dataoffsets, p.databytecounts, p.decode
        ntx = -(-W // tw)
        x, y = ps_south(lat, lon)
        rad = gate_km * 1000.0
        c0, c1 = math.floor((x - rad - X0) / res), math.ceil((x + rad - X0) / res)
        r0, r1 = math.floor((Y0 - (y + rad)) / res), math.ceil((Y0 - (y - rad)) / res)
        c0, c1, r0, r1 = max(c0, 0), min(c1, W), max(r0, 0), min(r1, H)
        arr = np.full((r1 - r0, c1 - c0), np.nan, np.float32)
        need = [(ty, tx) for ty in range(r0 // tl, (r1 - 1) // tl + 1) for tx in range(c0 // tw, (c1 - 1) // tw + 1)]

        def get(tt):
            ty, tx = tt
            i = ty * ntx + tx
            cp = tiles_dir / f"{i}.bin"
            if cp.exists():
                return tt, cp.read_bytes(), i
            if cnts[i] == 0:
                return tt, b"", i
            d = http_ranges(url, [(offs[i], offs[i] + cnts[i] - 1)])[0]
            cp.with_suffix(".tmp").write_bytes(d)
            cp.with_suffix(".tmp").replace(cp)
            return tt, d, i

        with cf.ThreadPoolExecutor(8) as ex:
            for (ty, tx), d, i in ex.map(get, need):
                if not d:
                    continue
                a = decode(d, i)[0].reshape(tl, tw)
                ya, xa = ty * tl, tx * tw
                rs, re_ = max(r0, ya), min(r1, ya + tl)
                cs, ce = max(c0, xa), min(c1, xa + tw)
                arr[rs - r0:re_ - r0, cs - c0:ce - c0] = a[rs - ya:re_ - ya, cs - xa:ce - xa]
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out.with_suffix(".tmp.npz"), h=arr, xc0=X0 + (c0 + 0.5) * res,
                        yc0=Y0 - (r0 + 0.5) * res, res=res, url=url, bounds=[r0, r1, c0, c1],
                        size=f.size)
    out.with_suffix(".tmp.npz").replace(out)
    return f"{sid} {name}: {arr.shape}, finite {np.isfinite(arr).mean():.3f}"


def sldem_tiles():
    html = http_get(SLDEM_DIR)[0].decode("latin-1")
    out = []
    for nm in sorted(set(re.findall(r"sldem2015_512_(\d+)([ns])_(\d+)([ns])_(\d{3})_(\d{3})_float\.img", html))):
        a = int(nm[0]) * (1 if nm[1] == "n" else -1)
        b = int(nm[2]) * (1 if nm[3] == "n" else -1)
        out.append(dict(name=f"sldem2015_512_{nm[0]}{nm[1]}_{nm[2]}{nm[3]}_{nm[4]}_{nm[5]}_float.img",
                        south=min(a, b), north=max(a, b), west=int(nm[4]), east=int(nm[5])))
    assert len(out) == 32, len(out)
    return out


def fetch_sldem_window(sid, lat, lon, gate_km, out, tiles):
    if out.exists():
        return f"{sid} SLDEM2015: cached"
    ppd = SLDEM_PPD
    a = gate_km * 1000.0 / R
    dlat = math.degrees(a)
    dlon = math.degrees(math.asin(min(1.0, math.sin(a) / math.cos(math.radians(lat)))))
    pad = 3 / ppd
    g0 = math.floor((90.0 - min(lat + dlat + pad, 60.0)) * ppd)
    g1 = math.ceil((90.0 - max(lat - dlat - pad, -60.0)) * ppd)
    lon360 = lon % 360.0
    k0 = math.floor((lon360 - dlon - pad) * ppd)
    k1 = math.ceil((lon360 + dlon + pad) * ppd)
    arr = np.full((g1 - g0, k1 - k0), np.nan, np.float32)
    full = 360 * ppd
    for t in tiles:
        tg0, tk0 = round((90.0 - t["north"]) * ppd), t["west"] * ppd
        nrow, ncol = (t["north"] - t["south"]) * ppd, (t["east"] - t["west"]) * ppd
        ra, rb = max(g0, tg0), min(g1, tg0 + nrow)
        if ra >= rb:
            continue
        for sh in (-full, 0, full):
            ca, cb = max(k0, tk0 + sh), min(k1, tk0 + sh + ncol)
            if ca >= cb:
                continue
            url = SLDEM_DIR + t["name"]
            rowb = ncol * 4
            lc0, lc1 = ca - tk0 - sh, cb - tk0 - sh
            for b0 in range(ra, rb, 128):
                b1 = min(b0 + 128, rb)
                rngs = [((r - tg0) * rowb + lc0 * 4, (r - tg0) * rowb + lc1 * 4 - 1) for r in range(b0, b1)]
                for j, d in enumerate(http_ranges(url, rngs)):
                    arr[b0 - g0 + j, ca - k0:cb - k0] = np.frombuffer(d, "<f4")
    arr = arr * 1000.0    # km -> m above 1737.4 km (label OFFSET 1737.4, UNIT KILOMETER, SCALING 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out.with_suffix(".tmp.npz"), h=arr.astype(np.float32), g0=g0, k0=k0, ppd=ppd)
    out.with_suffix(".tmp.npz").replace(out)
    return f"{sid} SLDEM2015: {arr.shape}, finite {np.isfinite(arr).mean():.4f}"


def relay_records(only=None):
    idx = json.loads((WEB / "relay" / "index.json").read_text(encoding="utf-8"))
    for sid in idx["ids"]:
        if only and sid not in only:
            continue
        yield json.loads((WEB / "relay" / f"{sid}.json").read_text(encoding="utf-8"))


def cmd_fetch(a):
    DEM.mkdir(parents=True, exist_ok=True)
    for nm, ppd in (("ldem_64_float", 64), ("ldem_16_float", 16)):
        img = DEM / f"{nm}.img"
        if not img.exists():
            raise SystemExit(f"download {LDEM_DIR}{nm}.img (+.lbl) to {img} first (curl -C -)")
    tiles = None
    jobs = []
    for rec in relay_records(a.site):
        gates = {d["name"]: d["radius_km"] for d in rec["input_identity"]["dem"]}
        for d in rec["dem_sources"]:
            n = d["name"]
            if n.startswith("PGDA_"):
                jobs.append(("pgda", rec["id"], rec["lat"], rec["lon"], n, gates[n]))
            elif n == "SLDEM2015":
                jobs.append(("sldem", rec["id"], rec["lat"], rec["lon"], n, gates[n]))
    for j in jobs:
        kind, sid, lat, lon, n, gate = j
        out = DEM / sid / f"{n}.npz"
        t0 = time.time()
        if kind == "pgda":
            msg = fetch_pgda_window(sid, lat, lon, n, gate, out)
        else:
            tiles = tiles or sldem_tiles()
            msg = fetch_sldem_window(sid, lat, lon, gate, out, tiles)
        print(f"{msg} ({time.time() - t0:.0f} s)", flush=True)


# ============================================================ computations
def ephem():
    meta = json.loads((WEB / "ephem.json").read_text(encoding="utf-8"))
    a = np.fromfile(WEB / "ephem.bin", dtype="<f4").reshape(-1, 6).astype(np.float64)
    assert a.shape[0] == meta["n"] == 43824 and meta["frame"] == "MOON_ME_DE421"
    return a[:, :3], a[:, 3:]


def horizon(ter, lat, lon, ground, heights, chunk=48):
    """(len(heights), 720) horizon elevation (deg) by brute-force march, no early stop."""
    az = np.arange(N_AZ) * AZ_STEP
    th = DIST_M / R
    ro = R + ground + np.asarray(heights, float)
    best = np.full((ro.size, N_AZ), -np.inf)
    for i0 in range(0, N_AZ, chunk):
        a = az[i0:i0 + chunk]
        la, lo = walk(lat, lon, a[:, None], DIST_M[None, :])
        h = ter.height(la, lo)
        if not np.isfinite(h).all():
            raise ValueError(f"missing terrain on horizon rays at ({lat}, {lon})")
        rt = R + h
        x, yv = rt * np.sin(th), rt * np.cos(th)
        for j, r_o in enumerate(ro):
            best[j, i0:i0 + chunk] = np.arctan2(yv - r_o, x).max(axis=1)
    return np.degrees(best)


def topo(lat, lon, top_m, body):
    up, east, north = frame(lat, lon)
    v = body - up * (R + top_m) / 1000.0
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return np.degrees(np.arctan2(v @ east, v @ north)) % 360.0, np.degrees(np.arcsin(np.clip(v @ up, -1, 1)))


def mask_at(mask, az):
    x = (az % 360.0) / AZ_STEP
    k = np.floor(x).astype(int) % N_AZ
    t = x - np.floor(x)
    return mask[k] + (mask[(k + 1) % N_AZ] - mask[k]) * t


def longest(b):
    best = run = 0
    for v in np.asarray(b, bool).tolist():
        run = run + 1 if v else 0
        best = max(best, run)
    return best


def path_clearance(ter, A, B, step_m):
    """A, B = (lat, lon, top_m above R). Min clearance (m) and min clearance/F1 per band over
    interior samples; None if same position (vertical connection, no interior path)."""
    az, th = bearing_angle(A[0], A[1], B[0], B[1])
    D_s = th * R
    if D_s < 1e-6:
        return None
    n = max(int(math.ceil(D_s / step_m)), 1)
    if n < 2:
        return dict(min_clear_m=math.inf, fresnel={"S": math.inf, "Ka": math.inf}, n=0)
    phi = th * np.arange(1, n) / n
    la, lo = walk(A[0], A[1], az, phi * R)
    h = ter.height(la, lo)
    if not np.isfinite(h).all():
        raise ValueError("missing terrain on link path")
    rA, rB, rt = R + A[2], R + B[2], R + h
    bx, by = rB * math.sin(th), rB * math.cos(th) - rA
    D = math.hypot(bx, by)
    ux, uy = bx / D, by / D
    tx, ty = rt * np.sin(phi), rt * np.cos(phi) - rA
    clear = -(ux * ty - uy * tx)          # >0: terrain below the straight antenna-antenna line
    d1 = ux * tx + uy * ty
    fr = {}
    for band, ghz in (("S", 2.2), ("Ka", 26.0)):
        lam = C_LIGHT / (ghz * 1e9)
        F = np.sqrt(lam * np.maximum(d1, 1e-6) * np.maximum(D - d1, 1e-6) / D)
        fr[band] = float((clear / F).min())
    return dict(min_clear_m=float(clear.min()), fresnel=fr, n=int(n - 1))


def tower_latlon(rec, e, n):
    d = math.hypot(e, n)
    if d == 0:
        return rec["lat"], rec["lon"]
    la, lo = walk(rec["lat"], rec["lon"], math.degrees(math.atan2(e, n)), d)
    return float(la), float(lo)


def run_site(rec, sun, earth):
    t0 = time.time()
    sid = rec["id"]
    ter = site_terrain(rec)
    lat0, lon0 = rec["lat"], rec["lon"]
    h0 = float(ter.height(np.array([lat0]), np.array([lon0]))[0])
    heights = [float(h) for h in rec["params"]["heights_m"]]
    # lander
    lm = horizon(ter, lat0, lon0, h0, [LANDER_ANT])[0]
    az, el = topo(lat0, lon0, h0 + LANDER_ANT, earth)
    direct = el > mask_at(lm, az)
    out = dict(id=sid, h0_m=h0, h0_file=rec["h0_m"],
               lander=dict(earth_frac=float(direct.mean()), longest_no_earth_h=longest(~direct),
                           file=rec["lander"]), towers={}, best=[], networks=[])
    # every published tower position (best + networks)
    pos = {}
    for b in rec["best"]:
        pos.setdefault((b["e_m"], b["n_m"]), set()).add(b["height_m"])
    for net in rec["networks"]:
        for t in net["towers"]:
            pos.setdefault((t["e_m"], t["n_m"]), set()).add(net["height_m"])
    vis = {}
    for (e, n), hs in sorted(pos.items()):
        la, lo = tower_latlon(rec, e, n)
        g = float(ter.height(np.array([la]), np.array([lo]))[0])
        hs = sorted(hs)
        masks = horizon(ter, la, lo, g, hs)
        for j, H in enumerate(hs):
            aze, ele = topo(la, lo, g + H, earth)
            v = ele > mask_at(masks[j], aze)
            azs, els = topo(la, lo, g + H, sun)
            lit = els >= mask_at(masks[j], azs)            # >= half the disk visible
            vis[(e, n, H)] = v
            out["towers"][f"{e:g},{n:g},{H:g}"] = dict(
                e_m=e, n_m=n, height_m=H, lat=la, lon=lo, ground_m=g,
                tower_earth_frac=float(v.mean()), sun_frac=float(lit.mean()),
                longest_dark_h=longest(~lit))
    lander_pt = (lat0, lon0, h0 + LANDER_ANT)

    def top(e, n, H):
        t = out["towers"][f"{e:g},{n:g},{H:g}"]
        return (t["lat"], t["lon"], t["ground_m"] + H)

    def link(A, B):
        p1 = path_clearance(ter, A, B, 1.0)
        p5 = path_clearance(ter, A, B, 5.0)
        if p1 is None:
            return dict(same_position=True, link=True, min_clear_m=1e6, fresnel={"S": 999.0, "Ka": 999.0},
                        step5=None)
        return dict(same_position=False, link=bool(p1["min_clear_m"] > 0), min_clear_m=p1["min_clear_m"],
                    fresnel=p1["fresnel"], n_samples=p1["n"],
                    step5=dict(link=bool(p5["min_clear_m"] > 0), min_clear_m=p5["min_clear_m"],
                               fresnel=p5["fresnel"]))

    for b in rec["best"]:
        H = b["height_m"]
        lk = link(lander_pt, top(b["e_m"], b["n_m"], H))
        v = vis[(b["e_m"], b["n_m"], H)]
        lf = (direct | (v & lk["link"])).mean()
        t = out["towers"][f"{b['e_m']:g},{b['n_m']:g},{H:g}"]
        out["best"].append(dict(height_m=H, idx=b["idx"], e_m=b["e_m"], n_m=b["n_m"], lat=t["lat"], lon=t["lon"],
                                ground_m=t["ground_m"], link=lk, tower_earth_frac=t["tower_earth_frac"],
                                link_frac=float(lf), sun_frac=t["sun_frac"], longest_dark_h=t["longest_dark_h"],
                                file=b))
    for net in rec["networks"]:
        H = net["height_m"]
        covered = direct.copy()
        fr = [float(direct.mean())]
        reach_ok = []
        hops = []
        for k, t in enumerate(net["towers"]):
            par = t["parent"]
            A = lander_pt if par == "LANDER" else top(net["towers"][par]["e_m"], net["towers"][par]["n_m"], H)
            lk = link(A, top(t["e_m"], t["n_m"], H))
            ok = lk["link"] and (par == "LANDER" or reach_ok[par])
            reach_ok.append(ok)
            hops.append(dict(parent=par, hop=lk, reachable=ok, file_parent_link=t.get("parent_link")))
            if ok:
                covered = covered | vis[(t["e_m"], t["n_m"], H)]
            fr.append(float(covered.mean()))
        codes = np.where(direct, 1, np.where(covered, 2, 0))
        fcodes = np.zeros(direct.size, np.int8)
        for s, L, c in net["timeline"]["segments"]:
            fcodes[s:s + L] = c
        out["networks"].append(dict(height_m=H, link_frac_by_n=fr, file_link_frac_by_n=net["link_frac_by_n"],
                                    longest_gap_h=longest(codes == 0), file_longest_gap_h=net["longest_gap_h"],
                                    timeline_hours_differing=int((codes != fcodes).sum()), hops=hops))
    # internal consistency of the published candidate arrays at each best index
    cons = []
    ph = rec["candidates"]["per_height"]
    for b in rec["best"]:
        p = ph[f"{b['height_m']:g}"]
        i = b["idx"]
        cons.append(dict(height_m=b["height_m"],
                         e_n=[rec["candidates"]["e_m"][i], rec["candidates"]["n_m"][i]] == [b["e_m"], b["n_m"]],
                         link=p["link"][i] == int(b["link_to_lander"]),
                         tower_earth_pm=p["tower_earth_pm"][i] == round(b["tower_earth_frac"] * 1000),
                         lander_link_pm=p["lander_link_pm"][i] == round(b["link_frac"] * 1000)))
    out["candidate_consistency"] = cons
    out["seconds"] = round(time.time() - t0, 1)
    return out


def max_overestimate(clear, ref, open_only=False):
    """Largest (clear - ref) over paths where both are finite: how much a coarser sampling
    overstates the minimum clearance found with 1 m steps (m). open_only: only paths that are
    clear with 1 m steps (the ones where the overstatement could matter for a margin)."""
    ok = np.isfinite(clear) & np.isfinite(ref)
    if open_only:
        ok &= ref > 0
    return round(float((clear[ok] - ref[ok]).max()), 3) if ok.any() else 0.0


def run_candidates(rec):
    """All 5,025 candidates: ground, 250 m plane-fit slope, lander <-> tower-top LOS and Fresnel
    for the 4 heights (terrain profile shared). Tower Earth visibility of every candidate is
    recomputed separately by run_candidates_earth."""
    t0 = time.time()
    ter = site_terrain(rec)
    lat0, lon0 = rec["lat"], rec["lon"]
    h0 = float(ter.height(np.array([lat0]), np.array([lon0]))[0])
    c = rec["candidates"]
    E, N = np.asarray(c["e_m"], float), np.asarray(c["n_m"], float)
    H = np.asarray(rec["params"]["heights_m"], float)
    d = np.hypot(E, N)
    az = np.degrees(np.arctan2(E, N))
    la, lo = walk(lat0, lon0, az, d)
    ground = ter.height(la, lo)
    # slope: least-squares plane over a 5 x 5 grid spanning 250 m (offsets in the lander's local E/N)
    g = np.linspace(-125.0, 125.0, 5)
    de, dn = [x.ravel() for x in np.meshgrid(g, g)]
    EE, NN = E[:, None] + de[None, :], N[:, None] + dn[None, :]
    sla, slo = walk(lat0, lon0, np.degrees(np.arctan2(EE, NN)), np.hypot(EE, NN))
    z = ter.height(sla, slo)
    A = np.stack([de, dn, np.ones_like(de)], axis=1)
    coef, *_ = np.linalg.lstsq(A, z.T, rcond=None)
    slope = np.degrees(np.arctan(np.hypot(coef[0], coef[1])))
    rA = R + h0 + LANDER_ANT
    out = {s: dict(link=np.zeros((N.size, H.size), bool), clear=np.full((N.size, H.size), np.inf),
                   fS=np.full((N.size, H.size), np.inf), fKa=np.full((N.size, H.size), np.inf))
           for s in ("1m", "5m", "blk")}
    lam = {"S": C_LIGHT / 2.2e9, "Ka": C_LIGHT / 26.0e9}
    # "blk" = the sampling the producer documents (relay_tower.link_profiles docstring/params):
    # paths sorted by length, blocks of 256, every path in a block gets ceil(longest/5 m) intervals.
    # Used only to explain sample-position differences; 1 m is the reference.
    th_all = np.array([bearing_angle(lat0, lon0, float(la[i]), float(lo[i]))[1] for i in range(N.size)])
    dist_all = th_all * R
    order = np.argsort(dist_all)
    order = order[dist_all[order] > 1e-6]
    n_blk = np.zeros(N.size, int)
    for i0 in range(0, order.size, 256):
        idx = order[i0:i0 + 256]
        n_blk[idx] = int(math.ceil(dist_all[idx].max() / 5.0))
    for i in range(N.size):
        if d[i] < 1e-6:
            for s in out:
                out[s]["link"][i] = True
            continue
        a_i, th = bearing_angle(lat0, lon0, float(la[i]), float(lo[i]))
        n1 = int(math.ceil(th * R / 1.0))
        phi = th * np.arange(1, n1) / n1
        pla, plo = walk(lat0, lon0, a_i, phi * R)
        rt = R + ter.height(pla, plo)
        if not np.isfinite(rt).all():
            raise ValueError(f"missing terrain on candidate path {i}")
        n5 = int(math.ceil(th * R / 5.0))
        for tag, step_n in (("1m", n1), ("5m", n5), ("blk", int(n_blk[i]))):
            if tag in ("5m", "blk"):
                if step_n < 2:
                    out[tag]["link"][i] = True
                    continue
                ph5 = th * np.arange(1, step_n) / step_n
                p5la, p5lo = walk(lat0, lon0, a_i, ph5 * R)
                rt_, ph_ = R + ter.height(p5la, p5lo), ph5
            else:
                if n1 < 2:
                    out["1m"]["link"][i] = True
                    continue
                rt_, ph_ = rt, phi
            tx, ty = rt_ * np.sin(ph_), rt_ * np.cos(ph_) - rA
            for j, h in enumerate(H):
                rB = R + ground[i] + h
                bx, by = rB * math.sin(th), rB * math.cos(th) - rA
                D = math.hypot(bx, by)
                ux, uy = bx / D, by / D
                clear = -(ux * ty - uy * tx)
                d1 = ux * tx + uy * ty
                o = out[tag]
                o["clear"][i, j] = clear.min()
                o["link"][i, j] = clear.min() > 0
                for band, key in (("S", "fS"), ("Ka", "fKa")):
                    F = np.sqrt(lam[band] * np.maximum(d1, 1e-6) * np.maximum(D - d1, 1e-6) / D)
                    o[key][i, j] = (clear / F).min()

    def q(a):
        a = np.where(np.isfinite(a), np.round(a * 100), 999)
        return np.clip(a, -999, 999).astype(int)

    res = dict(id=rec["id"], n=int(N.size), seconds=None)
    gf = np.asarray([np.nan if v is None else v for v in c["ground_m"]], float)
    res["ground_max_abs_diff_m"] = float(np.nanmax(np.abs(np.round(ground, 1) - gf)))
    res["slope_max_abs_diff_deg"] = float(np.max(np.abs(np.round(slope, 1) - np.asarray(c["slope_deg"], float))))
    res["slope_buildable_disagree"] = int(((np.round(slope, 1) <= rec["params"]["max_slope_deg"])
                                           != (np.asarray(c["slope_deg"]) <= rec["params"]["max_slope_deg"])).sum())
    per = {}
    for j, h in enumerate(H):
        p = c["per_height"][f"{h:g}"]
        fl = np.asarray(p["link"], bool)
        row = {}
        for tag in ("1m", "5m", "blk"):
            o = out[tag]
            dis = np.flatnonzero(o["link"][:, j] != fl)
            row[tag] = dict(link_disagree=int(dis.size), disagree_idx=dis.tolist()[:50],
                            disagree_min_clear_m=[round(float(o["clear"][k, j]), 3) for k in dis[:50]],
                            fresnel_S_pc_max_abs_diff=int(np.max(np.abs(q(o["fS"][:, j]) - np.asarray(p["fresnel_S_pc"])))),
                            fresnel_Ka_pc_max_abs_diff=int(np.max(np.abs(q(o["fKa"][:, j]) - np.asarray(p["fresnel_Ka_pc"])))),
                            fresnel_S_pc_n_diff_gt1=int((np.abs(q(o["fS"][:, j]) - np.asarray(p["fresnel_S_pc"])) > 1).sum()),
                            fresnel_Ka_pc_n_diff_gt1=int((np.abs(q(o["fKa"][:, j]) - np.asarray(p["fresnel_Ka_pc"])) > 1).sum()),
                            min_clear_vs_1m_max_drop_m=max_overestimate(o["clear"][:, j], out["1m"]["clear"][:, j]),
                            min_clear_vs_1m_max_drop_open_m=max_overestimate(o["clear"][:, j], out["1m"]["clear"][:, j],
                                                                             open_only=True))
        row["n_link_file"] = int(fl.sum())
        per[f"{h:g}"] = row
    res["per_height"] = per
    res["seconds"] = round(time.time() - t0, 1)
    return res


HMAX_M = 10_800.0   # above the highest lunar terrain (+10.79 km): exact bound for stopping a ray


def horizon_bins(ter, lat, lon, ground, heights, bins, block=500):
    """Horizon (deg) only for 0.5-deg bins `bins`, all heights; rays stop once even a 10.8 km
    peak at the next distance could not exceed the current maximum (exact, not an approximation)."""
    az = np.asarray(bins) * AZ_STEP
    ro = R + ground + np.asarray(heights, float)
    th_all = DIST_M / R
    best = np.full((ro.size, az.size), -np.inf)
    active = np.ones(az.size, bool)
    for i0 in range(0, DIST_M.size, block):
        idx = np.flatnonzero(active)
        if idx.size == 0:
            break
        s = DIST_M[i0:i0 + block]
        th = th_all[i0:i0 + block]
        la, lo = walk(lat, lon, az[idx][:, None], s[None, :])
        h = ter.height(la, lo)
        if not np.isfinite(h).all():
            raise ValueError("missing terrain on candidate horizon")
        rt = R + h
        x, yv = rt * np.sin(th), rt * np.cos(th)
        for j, r_o in enumerate(ro):
            best[j, idx] = np.maximum(best[j, idx], np.arctan2(yv - r_o, x).max(axis=1))
        if i0 + block < DIST_M.size:
            tn = th_all[i0 + block]
            bound = np.arctan2((R + HMAX_M) * math.cos(tn) - ro, (R + HMAX_M) * math.sin(tn))
            done = np.all(best[:, idx] > bound[:, None], axis=0)
            active[idx[done]] = False
    return np.degrees(best)


def run_candidates_earth(rec, earth):
    """Every candidate x height: tower-top Earth visibility (hourly) -> tower_earth_pm and
    lander_link_pm, compared with the published per-mille arrays."""
    t0 = time.time()
    ter = site_terrain(rec)
    lat0, lon0 = rec["lat"], rec["lon"]
    h0 = float(ter.height(np.array([lat0]), np.array([lon0]))[0])
    laz, lel = topo(lat0, lon0, h0 + LANDER_ANT, earth)
    direct = lel > mask_at(horizon(ter, lat0, lon0, h0, [LANDER_ANT])[0], laz)
    c = rec["candidates"]
    E, N = np.asarray(c["e_m"], float), np.asarray(c["n_m"], float)
    H = np.asarray(rec["params"]["heights_m"], float)
    d = np.hypot(E, N)
    la, lo = walk(lat0, lon0, np.degrees(np.arctan2(E, N)), d)
    ground = ter.height(la, lo)
    te = np.zeros((N.size, H.size), int)
    ll_file_link = np.zeros((N.size, H.size), int)
    for i in range(N.size):
        if not np.isfinite(ground[i]):
            continue
        azs, els = [], []
        for Hh in H:
            a_, e_ = topo(float(la[i]), float(lo[i]), ground[i] + Hh, earth)
            azs.append(a_)
            els.append(e_)
        k = np.floor(np.concatenate(azs) / AZ_STEP).astype(int) % N_AZ
        bins = np.unique(np.concatenate([k, (k + 1) % N_AZ]))
        m = horizon_bins(ter, float(la[i]), float(lo[i]), float(ground[i]), H, bins)
        full = np.full((H.size, N_AZ), np.nan)
        full[:, bins] = m
        for j in range(H.size):
            v = els[j] > mask_at(full[j], azs[j])
            te[i, j] = int(v.sum())
            fl = bool(c["per_height"][f"{H[j]:g}"]["link"][i])
            ll_file_link[i, j] = int((direct | (v & fl)).sum()) if fl else int(direct.sum())
    n = direct.size
    res = dict(id=rec["id"], n=int(N.size), direct_hours=int(direct.sum()), per_height={})
    for j, h in enumerate(H):
        p = c["per_height"][f"{h:g}"]
        te_pm = np.round(te[:, j] / n * 1000).astype(int)
        ll_pm = np.round(ll_file_link[:, j] / n * 1000).astype(int)
        dte = te_pm - np.asarray(p["tower_earth_pm"])
        dll = ll_pm - np.asarray(p["lander_link_pm"])
        valid = np.isfinite(ground)
        res["per_height"][f"{h:g}"] = dict(
            tower_earth_pm_max_abs_diff=int(np.abs(dte[valid]).max()),
            tower_earth_pm_n_diff=int((dte[valid] != 0).sum()),
            tower_earth_pm_n_diff_gt1=int((np.abs(dte[valid]) > 1).sum()),
            lander_link_pm_max_abs_diff=int(np.abs(dll[valid]).max()),
            lander_link_pm_n_diff=int((dll[valid] != 0).sum()),
            lander_link_pm_n_diff_gt1=int((np.abs(dll[valid]) > 1).sum()),
            tower_earth_frac_max_abs_diff_pp=float(np.abs(te[valid, j] / n * 100 - np.asarray(p["tower_earth_pm"])[valid] / 10).max()))
    res["seconds"] = round(time.time() - t0, 1)
    return res


def cmd_candidates_earth(a):
    sun, earth = ephem()
    OUT_SITES.mkdir(parents=True, exist_ok=True)
    for rec in relay_records(a.site):
        dst = OUT_SITES / f"{rec['id']}.candidates_earth.json"
        if dst.exists() and not a.force:
            continue
        lock = dst.with_suffix(".lock")     # lets several workers share one site list
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL))
        except FileExistsError:
            continue
        try:
            r = run_candidates_earth(rec, earth)
            dst.with_suffix(".tmp").write_text(json.dumps(r, indent=1), encoding="utf-8")
            dst.with_suffix(".tmp").replace(dst)
        finally:
            lock.unlink(missing_ok=True)
        print(f"{rec['id']}: {r['seconds']} s; " + "; ".join(
            f"{h} m tower_earth_pm diff max {v['tower_earth_pm_max_abs_diff']} (n {v['tower_earth_pm_n_diff']}), "
            f"lander_link_pm diff max {v['lander_link_pm_max_abs_diff']} (n {v['lander_link_pm_n_diff']})"
            for h, v in r["per_height"].items()), flush=True)


def cmd_candidates(a):
    OUT_SITES.mkdir(parents=True, exist_ok=True)
    for rec in relay_records(a.site):
        dst = OUT_SITES / f"{rec['id']}.candidates.json"
        if dst.exists() and not a.force:
            continue
        r = run_candidates(rec)
        dst.with_suffix(".tmp").write_text(json.dumps(r, indent=1), encoding="utf-8")
        dst.with_suffix(".tmp").replace(dst)
        print(f"{rec['id']}: {r['seconds']} s; ground {r['ground_max_abs_diff_m']:.2f} m; slope {r['slope_max_abs_diff_deg']:.1f} deg; "
              + "; ".join(f"{h} m LOS disagree 1m/5m/blk {v['1m']['link_disagree']}/{v['5m']['link_disagree']}/{v['blk']['link_disagree']}"
                          f" FresS max blk {v['blk']['fresnel_S_pc_max_abs_diff']}" for h, v in r["per_height"].items()),
              flush=True)


def cmd_run(a):
    sun, earth = ephem()
    OUT_SITES.mkdir(parents=True, exist_ok=True)
    for rec in relay_records(a.site):
        dst = OUT_SITES / f"{rec['id']}.json"
        if dst.exists() and not a.force:
            print(f"{rec['id']}: done (resume)", flush=True)
            continue
        r = run_site(rec, sun, earth)
        r["relay_sha256"] = hashlib.sha256((WEB / "relay" / f"{rec['id']}.json").read_bytes()).hexdigest()
        dst.with_suffix(".tmp").write_text(json.dumps(r, indent=1, default=float), encoding="utf-8")
        dst.with_suffix(".tmp").replace(dst)
        b = r["best"]
        print(f"{rec['id']}: {r['seconds']} s; direct {r['lander']['earth_frac']:.4f} vs {rec['lander']['earth_frac']}; "
              + "; ".join(f"{x['height_m']:g} m link {x['link_frac']:.4f} vs {x['file']['link_frac']}" for x in b),
              flush=True)


# ============================================================ report
def cmd_report(a):
    rows, nets, fails = [], [], []
    tol_pp = 1.0
    for rec in relay_records():
        r = json.loads((OUT_SITES / f"{rec['id']}.json").read_text(encoding="utf-8"))
        d_dir = 100 * (r["lander"]["earth_frac"] - rec["lander"]["earth_frac"])
        for b in r["best"]:
            f = b["file"]
            lk = b["link"]
            row = dict(site=rec["id"], height_m=b["height_m"], dist_m=f["dist_m"],
                       direct_pp=100 * r["lander"]["earth_frac"], direct_file_pp=100 * rec["lander"]["earth_frac"],
                       direct_diff_pp=d_dir,
                       los_mine=lk["link"], los_file=f["link_to_lander"], same_position=lk["same_position"],
                       min_clear_mine=lk["min_clear_m"], min_clear_file=f["min_clear_m"],
                       fresnel_S_mine=lk["fresnel"]["S"], fresnel_S_file=f["fresnel"]["S"],
                       fresnel_Ka_mine=lk["fresnel"]["Ka"], fresnel_Ka_file=f["fresnel"]["Ka"],
                       fresnel_S_step5=(lk["step5"] or {}).get("fresnel", {}).get("S"),
                       tower_earth_mine=100 * b["tower_earth_frac"], tower_earth_file=100 * f["tower_earth_frac"],
                       link_mine=100 * b["link_frac"], link_file=100 * f["link_frac"],
                       sun_mine=100 * b["sun_frac"], sun_file=100 * f["sun_frac"],
                       dark_mine=b["longest_dark_h"], dark_file=f["longest_dark_h"],
                       ground_mine=b["ground_m"], ground_file=f["ground_m"])
            row["tower_earth_diff_pp"] = row["tower_earth_mine"] - row["tower_earth_file"]
            row["link_diff_pp"] = row["link_mine"] - row["link_file"]
            row["sun_diff_pp"] = row["sun_mine"] - row["sun_file"]
            row["exact_4dp"] = dict(
                direct=round(r["lander"]["earth_frac"], 4) == rec["lander"]["earth_frac"],
                tower_earth=round(b["tower_earth_frac"], 4) == f["tower_earth_frac"],
                link=round(b["link_frac"], 4) == f["link_frac"], sun=round(b["sun_frac"], 4) == f["sun_frac"],
                dark=b["longest_dark_h"] == f["longest_dark_h"])
            row["pass"] = bool(row["los_mine"] == row["los_file"] and abs(row["tower_earth_diff_pp"]) <= tol_pp
                               and abs(row["link_diff_pp"]) <= tol_pp and abs(d_dir) <= tol_pp)
            rows.append(row)
            if not row["pass"]:
                fails.append(f"{rec['id']} best {b['height_m']:g} m")
        for n in r["networks"]:
            mine, fil = n["link_frac_by_n"], n["file_link_frac_by_n"]
            diffs = [100 * (x - y) for x, y in zip(mine, fil)]
            hop_ok = all(h["hop"]["link"] for h in n["hops"])
            nr = dict(site=rec["id"], height_m=n["height_m"], n_towers=len(n["hops"]),
                      mine=[round(100 * x, 3) for x in mine], file=[round(100 * x, 2) for x in fil],
                      max_abs_diff_pp=max(abs(x) for x in diffs), hops_all_los=hop_ok,
                      parents=[h["parent"] for h in n["hops"]],
                      gap_mine=n["longest_gap_h"], gap_file=n["file_longest_gap_h"],
                      timeline_hours_differing=n["timeline_hours_differing"])
            nr["exact_4dp"] = [round(x, 4) for x in mine] == list(fil) and n["longest_gap_h"] == n["file_longest_gap_h"]
            nr["pass"] = bool(hop_ok and nr["max_abs_diff_pp"] <= tol_pp and len(mine) == len(fil))
            nets.append(nr)
            if not nr["pass"]:
                fails.append(f"{rec['id']} network {n['height_m']:g} m")
    # height_curve rows are derived values: check them against my recomputed best / network / direct
    hc_rows = []
    for rec in relay_records():
        r = json.loads((OUT_SITES / f"{rec['id']}.json").read_text(encoding="utf-8"))
        for hc in rec["height_curve"]:
            b = next(x for x in r["best"] if x["height_m"] == hc["height_m"])
            n = next(x for x in r["networks"] if x["height_m"] == hc["height_m"])
            single, net = 100 * b["link_frac"], 100 * n["link_frac_by_n"][-1]
            gain = single - 100 * r["lander"]["earth_frac"]
            d = dict(site=rec["id"], height_m=hc["height_m"],
                     single_diff_pp=single - 100 * hc["single_link_frac"],
                     network_diff_pp=net - 100 * hc["network_link_frac"],
                     gain_diff_pp=gain - hc["single_gain_pp"])
            d["pass"] = all(abs(d[k]) <= tol_pp for k in ("single_diff_pp", "network_diff_pp", "gain_diff_pp"))
            hc_rows.append(d)
            if not d["pass"]:
                fails.append(f"{rec['id']} height_curve {hc['height_m']:g} m")
    tower_rows = [r for r in rows if not r["same_position"]]
    cands = []
    for rec in relay_records():
        cl = OUT_SITES / f"{rec['id']}.candidates.json"
        ce = OUT_SITES / f"{rec['id']}.candidates_earth.json"
        if not cl.exists():
            continue
        a_ = json.loads(cl.read_text(encoding="utf-8"))
        e_ = json.loads(ce.read_text(encoding="utf-8")) if ce.exists() else None
        for h, v in a_["per_height"].items():
            row = dict(site=rec["id"], height_m=float(h), n=a_["n"], ground_max_abs_diff_m=a_["ground_max_abs_diff_m"],
                       slope_max_abs_diff_deg=a_["slope_max_abs_diff_deg"],
                       slope_buildable_disagree=a_["slope_buildable_disagree"], n_link_file=v["n_link_file"],
                       los_disagree_1m=v["1m"]["link_disagree"], los_disagree_5m=v["5m"]["link_disagree"],
                       los_disagree_1m_min_clear_m=v["1m"]["disagree_min_clear_m"],
                       los_disagree_5m_min_clear_m=v["5m"]["disagree_min_clear_m"],
                       fresnel_S_pc_max_abs_diff_5m=v["5m"]["fresnel_S_pc_max_abs_diff"],
                       fresnel_Ka_pc_max_abs_diff_5m=v["5m"]["fresnel_Ka_pc_max_abs_diff"],
                       fresnel_S_pc_max_abs_diff_1m=v["1m"]["fresnel_S_pc_max_abs_diff"],
                       fresnel_Ka_pc_max_abs_diff_1m=v["1m"]["fresnel_Ka_pc_max_abs_diff"],
                       fresnel_S_pc_n_diff_gt1_1m=v["1m"]["fresnel_S_pc_n_diff_gt1"],
                       los_disagree_blk=v["blk"]["link_disagree"],
                       los_disagree_blk_min_clear_m=v["blk"]["disagree_min_clear_m"],
                       fresnel_S_pc_max_abs_diff_blk=v["blk"]["fresnel_S_pc_max_abs_diff"],
                       fresnel_Ka_pc_max_abs_diff_blk=v["blk"]["fresnel_Ka_pc_max_abs_diff"],
                       fresnel_S_pc_n_diff_gt1_blk=v["blk"]["fresnel_S_pc_n_diff_gt1"],
                       fresnel_Ka_pc_n_diff_gt1_blk=v["blk"]["fresnel_Ka_pc_n_diff_gt1"],
                       clear_overestimate_vs_1m_m_blk=v["blk"]["min_clear_vs_1m_max_drop_m"],
                       clear_overestimate_open_vs_1m_m_blk=v["blk"]["min_clear_vs_1m_max_drop_open_m"])
            if e_:
                row.update({k: e_["per_height"][h][k] for k in e_["per_height"][h]})
            cands.append(row)
    if cands:
        summary_c = dict(
            rows=len(cands), sites=len({c["site"] for c in cands}),
            candidates=sum(c["n"] for c in cands if c["height_m"] == 5.0),
            ground_max_abs_diff_m=max(c["ground_max_abs_diff_m"] for c in cands),
            slope_max_abs_diff_deg=max(c["slope_max_abs_diff_deg"] for c in cands),
            slope_buildable_disagree=sum(c["slope_buildable_disagree"] for c in cands if c["height_m"] == 5.0),
            los_pairs=sum(c["n"] for c in cands),
            los_disagree_1m=sum(c["los_disagree_1m"] for c in cands),
            los_disagree_5m=sum(c["los_disagree_5m"] for c in cands),
            los_disagree_max_abs_clear_m=max([abs(x) for c in cands for x in
                                              c["los_disagree_1m_min_clear_m"] + c["los_disagree_5m_min_clear_m"]
                                              + c["los_disagree_blk_min_clear_m"]] or [0]),
            earth_sites=len({c["site"] for c in cands if "tower_earth_pm_max_abs_diff" in c}),
            los_disagree_blk=sum(c["los_disagree_blk"] for c in cands),
            fresnel_S_pc_max_abs_diff_1m=max(c["fresnel_S_pc_max_abs_diff_1m"] for c in cands),
            fresnel_Ka_pc_max_abs_diff_1m=max(c["fresnel_Ka_pc_max_abs_diff_1m"] for c in cands),
            fresnel_S_pc_n_diff_gt1_1m=sum(c["fresnel_S_pc_n_diff_gt1_1m"] for c in cands),
            fresnel_S_pc_max_abs_diff_blk=max(c["fresnel_S_pc_max_abs_diff_blk"] for c in cands),
            fresnel_Ka_pc_max_abs_diff_blk=max(c["fresnel_Ka_pc_max_abs_diff_blk"] for c in cands),
            fresnel_S_pc_n_diff_gt1_blk=sum(c["fresnel_S_pc_n_diff_gt1_blk"] for c in cands),
            fresnel_Ka_pc_n_diff_gt1_blk=sum(c["fresnel_Ka_pc_n_diff_gt1_blk"] for c in cands),
            clear_overestimate_vs_1m_m_blk=max(c["clear_overestimate_vs_1m_m_blk"] for c in cands),
            clear_overestimate_open_vs_1m_m_blk=max(c["clear_overestimate_open_vs_1m_m_blk"] for c in cands))
        ce_rows = [c for c in cands if "tower_earth_pm_max_abs_diff" in c]
        if ce_rows:
            summary_c.update(
                tower_earth_pm_max_abs_diff=max(c["tower_earth_pm_max_abs_diff"] for c in ce_rows),
                tower_earth_pm_n_diff=sum(c["tower_earth_pm_n_diff"] for c in ce_rows),
                tower_earth_frac_max_abs_diff_pp=max(c["tower_earth_frac_max_abs_diff_pp"] for c in ce_rows),
                lander_link_pm_max_abs_diff=max(c["lander_link_pm_max_abs_diff"] for c in ce_rows),
                lander_link_pm_n_diff=sum(c["lander_link_pm_n_diff"] for c in ce_rows),
                pairs=sum(c["n"] for c in ce_rows))
    else:
        summary_c = None

    def mx(key, rs=rows):
        return max(abs(r[key]) for r in rs) if rs else 0.0

    summary = dict(
        sites=len({r["site"] for r in rows}), best_rows=len(rows), network_rows=len(nets),
        criterion_pp=tol_pp, fails=fails,
        max_abs_diff_pp=dict(direct=mx("direct_diff_pp"), tower_earth=mx("tower_earth_diff_pp"),
                             link=mx("link_diff_pp"), sun=mx("sun_diff_pp"),
                             network=max(n["max_abs_diff_pp"] for n in nets)),
        los_agreement=f"{sum(r['los_mine'] == r['los_file'] for r in rows)}/{len(rows)}",
        hop_los_all_true=f"{sum(n['hops_all_los'] for n in nets)}/{len(nets)}",
        max_abs_fresnel_S_diff=max((abs(r["fresnel_S_mine"] - r["fresnel_S_file"]) for r in tower_rows), default=0),
        max_abs_fresnel_Ka_diff=max((abs(r["fresnel_Ka_mine"] - r["fresnel_Ka_file"]) for r in tower_rows), default=0),
        max_abs_ground_diff_m=max(abs(r["ground_mine"] - r["ground_file"]) for r in rows),
        max_dark_diff_h=max(abs(r["dark_mine"] - r["dark_file"]) for r in rows),
        max_gap_diff_h=max(abs(n["gap_mine"] - n["gap_file"]) for n in nets),
        max_timeline_hours_differing=max(n["timeline_hours_differing"] for n in nets),
        exact_after_4dp_rounding={k: f"{sum(r['exact_4dp'][k] for r in rows)}/{len(rows)}"
                                  for k in ("direct", "tower_earth", "link", "sun", "dark")},
        network_exact_after_4dp_rounding=f"{sum(n['exact_4dp'] for n in nets)}/{len(nets)}",
        height_curve=dict(rows=len(hc_rows), passing=sum(h["pass"] for h in hc_rows),
                          max_abs_diff_pp=max(max(abs(h[k]) for k in ("single_diff_pp", "network_diff_pp", "gain_diff_pp"))
                                              for h in hc_rows)))
    summary["candidates"] = summary_c
    doc = dict(task="N", checker="Dongju Kim", product="web/data/relay/ (33 sites)", summary=summary,
               best=rows, networks=nets, height_curve=hc_rows, candidates=cands)
    (ROOT / "docs" / "crosscheck_relay_dongju.json").write_text(json.dumps(doc, indent=1, default=float),
                                                               encoding="utf-8")
    write_markdown(doc)
    print(json.dumps(summary, indent=1, default=float))


def write_markdown(doc):
    s = doc["summary"]
    f2 = lambda x: f"{x:.2f}"  # noqa: E731
    f4 = lambda x: f"{x:+.4f}"  # noqa: E731
    L = ["# Task N — independent full recomputation of `web/data/relay/` (Dongju Kim, 2026-11-15)", "",
         "Own code: `pipeline/crosscheck_relay_dongju.py` (no imports from `pipeline/` or `web/js/`). "
         "Terrain read directly from the original NASA rasters (PGDA LOLA polar GeoTIFFs over HTTP Range, "
         "SLDEM2015 512 ppd tiles, LOLA LDEM_64/16 float). Ephemeris `web/data/ephem.bin` (43,824 hourly rows). "
         "Full machine-readable table: `docs/crosscheck_relay_dongju.json`.", "",
         "## What was recomputed (all 33 sites, every published tower)", "",
         "- Lander direct Earth visibility, hourly, own 720-bin horizon (2 m antenna).",
         "- For each of the 4 `best` towers and every `networks[].towers` entry: tower position from (e_m, n_m), ground height, "
         "tower-top 720-bin horizon (5 m to 300 km, 8,001 log distances, curvature, no early stop), hourly Earth-centre visibility, "
         "sunlit fraction (>= half disk) and longest dark run.",
         "- Tower <-> lander (or parent tower) line of sight with curvature at **1 m** interior steps (also 5 m), minimum clearance, "
         "first-Fresnel clearance ratio for S 2.2 GHz and Ka 26 GHz.",
         "- Single-tower link fraction = direct OR (link AND tower sees Earth); network fractions by number of towers, longest gap, "
         "and the hourly timeline codes compared hour by hour with the published segments.", "",
         f"Criterion: <= {s['criterion_pp']:g} %p for every fraction; LOS yes/no must agree.", "",
         "## Summary", "",
         "| Check | Result |", "|---|---|",
         f"| Sites | {s['sites']} |",
         f"| Best-tower rows (site x height) | {s['best_rows']} |",
         f"| Network rows (site x height) | {s['network_rows']} |",
         f"| Max \\|diff\\| direct Earth | {s['max_abs_diff_pp']['direct']:.4f} %p |",
         f"| Max \\|diff\\| tower Earth visibility | {s['max_abs_diff_pp']['tower_earth']:.4f} %p |",
         f"| Max \\|diff\\| single-tower link fraction | {s['max_abs_diff_pp']['link']:.4f} %p |",
         f"| Max \\|diff\\| network link fractions (all n) | {s['max_abs_diff_pp']['network']:.4f} %p |",
         f"| Max \\|diff\\| tower sunlit fraction | {s['max_abs_diff_pp']['sun']:.4f} %p |",
         f"| Tower -> lander LOS agreement | {s['los_agreement']} |",
         f"| Network hops all clear (my LOS) | {s['hop_los_all_true']} |",
         f"| Max \\|diff\\| Fresnel ratio S / Ka (towers away from the lander) | {s['max_abs_fresnel_S_diff']:.3f} / {s['max_abs_fresnel_Ka_diff']:.3f} |",
         f"| Max \\|diff\\| tower ground height | {s['max_abs_ground_diff_m']:.2f} m (file rounded to 0.1 m) |",
         f"| Max \\|diff\\| longest dark / longest network gap | {s['max_dark_diff_h']} h / {s['max_gap_diff_h']} h |",
         f"| Max hours with a different timeline code (of 43,824) | {s['max_timeline_hours_differing']} |",
         "| Identical to the file after rounding mine to its 4 decimals (direct / tower Earth / link / sun / longest dark) | "
         + " / ".join(s["exact_after_4dp_rounding"][k] for k in ("direct", "tower_earth", "link", "sun", "dark")) + " |",
         f"| Network `link_frac_by_n` + longest gap identical after 4-decimal rounding | {s['network_exact_after_4dp_rounding']} |",
         f"| `height_curve` rows (single, network, gain) within criterion / max \\|diff\\| | "
         f"{s['height_curve']['passing']}/{s['height_curve']['rows']} / {s['height_curve']['max_abs_diff_pp']:.4f} %p |",
         f"| Rows failing the criterion | {len(s['fails'])}{': ' + ', '.join(s['fails']) if s['fails'] else ''} |", "",
         "## Best single tower, all 33 sites x 4 heights", "",
         "Fractions in %. `mine - file` in %p. LOS: mine/file. Fresnel = min clearance / F1 (mine vs file; 999 = same position, no path).", "",
         "| Site | H m | Dist m | Direct % (diff) | LOS | Tower Earth mine / file (diff) | Link mine / file (diff) | Fresnel S mine / file | Ka mine / file | Sun mine / file | Pass |",
         "|---|---:|---:|---|---|---|---|---|---|---|---|"]
    for r in doc["best"]:
        L.append(f"| {r['site']} | {r['height_m']:g} | {r['dist_m']:.0f} | {f2(r['direct_pp'])} ({f4(r['direct_diff_pp'])}) | "
                 f"{'Y' if r['los_mine'] else 'N'}/{'Y' if r['los_file'] else 'N'} | "
                 f"{f2(r['tower_earth_mine'])} / {f2(r['tower_earth_file'])} ({f4(r['tower_earth_diff_pp'])}) | "
                 f"{f2(r['link_mine'])} / {f2(r['link_file'])} ({f4(r['link_diff_pp'])}) | "
                 f"{min(r['fresnel_S_mine'], 999):.2f} / {r['fresnel_S_file']:.2f} | {min(r['fresnel_Ka_mine'], 999):.2f} / {r['fresnel_Ka_file']:.2f} | "
                 f"{f2(r['sun_mine'])} / {f2(r['sun_file'])} | {'PASS' if r['pass'] else '**FAIL**'} |")
    L += ["", "## Networks (greedy 1-3 towers), all sites x 4 heights", "",
          "`link_frac_by_n` in % (index 0 = direct only). Hops = my LOS for each tower's published parent.", "",
          "| Site | H m | Towers | Parents | Mine % | File % | Max \\|diff\\| %p | Hops clear | Longest gap mine / file h | Timeline hours differing | Pass |",
          "|---|---:|---:|---|---|---|---:|---|---|---:|---|"]
    for n in doc["networks"]:
        L.append(f"| {n['site']} | {n['height_m']:g} | {n['n_towers']} | {', '.join(str(p) for p in n['parents']) or '-'} | "
                 f"{', '.join(f'{x:.2f}' for x in n['mine'])} | {', '.join(f'{x:.2f}' for x in n['file'])} | "
                 f"{n['max_abs_diff_pp']:.4f} | {'yes' if n['hops_all_los'] else '**no**'} | {n['gap_mine']} / {n['gap_file']} | "
                 f"{n['timeline_hours_differing']} | {'PASS' if n['pass'] else '**FAIL**'} |")
    c = s.get("candidates")
    if c:
        L += ["", "## All 5,025 candidates per site (`candidates.per_height`)", "",
              "Every candidate position x 4 heights: ground height, 250 m plane-fit slope, lander <-> tower-top LOS "
              "(1 m and 5 m interior steps), Fresnel per-cent clearance, and (where run) tower-top Earth visibility "
              "`tower_earth_pm` and `lander_link_pm` (per mille).", "",
              "| Check | Result |", "|---|---|",
              f"| Sites / candidate positions | {c['sites']} / {c['candidates']:,} |",
              f"| Max \\|diff\\| ground height | {c['ground_max_abs_diff_m']:.2f} m |",
              f"| Max \\|diff\\| slope / buildable flag disagreements | {c['slope_max_abs_diff_deg']:.1f} deg / {c['slope_buildable_disagree']} |",
              f"| LOS pairs (candidate x height) | {c['los_pairs']:,} |",
              f"| LOS yes/no disagreements, 1 m steps / 5 m steps | {c['los_disagree_1m']} / {c['los_disagree_5m']} "
              f"({100 * c['los_disagree_1m'] / c['los_pairs']:.3f} % / {100 * c['los_disagree_5m'] / c['los_pairs']:.3f} %) |",
              f"| Largest \\|min clearance\\| among the disagreements | {c['los_disagree_max_abs_clear_m']:.3f} m |",
              f"| Fresnel S / Ka per-cent, 1 m steps vs file: max \\|diff\\| (entries > 1 pc, S) | "
              f"{c['fresnel_S_pc_max_abs_diff_1m']} / {c['fresnel_Ka_pc_max_abs_diff_1m']} ({c['fresnel_S_pc_n_diff_gt1_1m']:,}) |",
              f"| Same, with the producer's block sampling re-implemented: LOS disagreements / Fresnel S, Ka max \\|diff\\| "
              f"(entries > 1 pc S, Ka) | {c['los_disagree_blk']} / {c['fresnel_S_pc_max_abs_diff_blk']}, {c['fresnel_Ka_pc_max_abs_diff_blk']} "
              f"({c['fresnel_S_pc_n_diff_gt1_blk']}, {c['fresnel_Ka_pc_n_diff_gt1_blk']}) |",
              f"| Largest amount the producer's sampling overstates the minimum clearance vs 1 m steps: all paths / "
              f"paths that are clear at 1 m | {c['clear_overestimate_vs_1m_m_blk']:.2f} m / "
              f"{c['clear_overestimate_open_vs_1m_m_blk']:.2f} m |"]
        if "pairs" in c:
            L += [f"| Sites with tower Earth recomputed / pairs | {c['earth_sites']} / {c['pairs']:,} |",
                  f"| `tower_earth_pm` max \\|diff\\| / entries differing | {c['tower_earth_pm_max_abs_diff']} per mille / {c['tower_earth_pm_n_diff']} |",
                  f"| Tower Earth fraction max \\|diff\\| (unrounded mine vs file) | {c['tower_earth_frac_max_abs_diff_pp']:.4f} %p |",
                  f"| `lander_link_pm` max \\|diff\\| / entries differing (using the file's LOS bit) | {c['lander_link_pm_max_abs_diff']} per mille / {c['lander_link_pm_n_diff']} |"]
        L += ["", "**Why the candidate LOS and Fresnel values differ, and what it means.** Every LOS disagreement is a grazing "
              f"path: my minimum clearance is within {c['los_disagree_max_abs_clear_m']:.2f} m of zero, so the yes/no depends on "
              "where the path is sampled. The producer (`relay_tower.link_profiles`) sorts the paths by length, groups them in "
              "blocks of 256, and gives every path in a block ceil(longest/5 m) intervals, so sample positions are not at fixed "
              "distances. When I re-implement that sampling in my own code (column `blk`), the LOS bits and the Fresnel values "
              "come back almost exactly; the few remaining entries are paths whose block membership depends on how equal "
              "distances are ordered. So the file is computed as documented, and the differences are sample positions, not "
              "terrain or geometry. Finding for the producer: samples about 5 m apart can step over a short terrain feature, so "
              "the published minimum clearance (and Fresnel per-cent) can be slightly optimistic. Example CHANGE5: the "
              "largest Fresnel differences sit 15–25 m from the lander, where the first Fresnel radius is only about 1.6 m. "
              "The largest differences overall (APOLLO16: Fresnel up to 92 / 230 pc, clearance up to 5.8 m) are paths already "
              "blocked by 10–200 m where they cross a steep ridge 6–7 km out, so both values say blocked. On paths that are "
              "open at 1 m steps the published minimum clearance is optimistic by at most the second number in the table "
              "above (IM1). The app uses the plain LOS rule (`link_rule: los`), so none of this changes a published link "
              "fraction; it only matters if someone applies the 0.6 F1 Fresnel rule to these arrays.", "",
              "| Site | H m | File LOS yes | LOS disagree 1 m / 5 m / blk | Max \\|clear\\| m | Fresnel S / Ka max \\|diff\\| 1 m (pc) | "
              "Same, blk | tower_earth_pm max \\|diff\\| (n) | lander_link_pm max \\|diff\\| (n) |",
              "|---|---:|---:|---|---:|---|---|---|---|"]
        for r in doc["candidates"]:
            cl = [abs(x) for x in r["los_disagree_1m_min_clear_m"] + r["los_disagree_5m_min_clear_m"]
                  + r["los_disagree_blk_min_clear_m"]]
            te = (f"{r['tower_earth_pm_max_abs_diff']} ({r['tower_earth_pm_n_diff']})"
                  if "tower_earth_pm_max_abs_diff" in r else "not run")
            ll = (f"{r['lander_link_pm_max_abs_diff']} ({r['lander_link_pm_n_diff']})"
                  if "lander_link_pm_max_abs_diff" in r else "not run")
            L.append(f"| {r['site']} | {r['height_m']:g} | {r['n_link_file']} | "
                     f"{r['los_disagree_1m']} / {r['los_disagree_5m']} / {r['los_disagree_blk']} | "
                     f"{max(cl, default=0):.3f} | {r['fresnel_S_pc_max_abs_diff_1m']} / {r['fresnel_Ka_pc_max_abs_diff_1m']} | "
                     f"{r['fresnel_S_pc_max_abs_diff_blk']} / {r['fresnel_Ka_pc_max_abs_diff_blk']} | {te} | {ll} |")
    L += ["", "## Scope and limits", "",
          "- Recomputed: every value the app shows for the relay (direct, best tower per height, networks, timelines) and "
          "the per-candidate arrays listed above, plus the derived `height_curve`. Not re-run: the greedy search itself "
          "(I checked the towers it chose, not that no other choice is better; the contract calls it a heuristic) and the "
          "`link_budget` block, which is a stated assumption set, not a terrain result. No published file has a `coverage` "
          "map (`params.coverage_side_km = 0`). Each best-tower entry matches its own candidate-array entry "
          "(`candidate_consistency` in the JSON).",
          "- Same terrain chain as the producer (input definition from each file's `dem_sources` / `input_identity`): source gates "
          "measured from the lander, PGDA windows = squares of half-width = gate. Terrain was read from the NASA originals, not from "
          "the producer's caches.",
          "- LOS sampled every 1 m (production at most 5 m). For the published best towers and network hops the Fresnel "
          "differences are small (table above). For the candidate arrays the producer's sample positions matter; see the "
          "candidate section.",
          "- Geometry only: no RF budget, no Earth-station scheduling, no tower power model.", "",
          "Reproduce (order matters; each step resumes per site, `--site ID` limits it):", "",
          "```",
          "python pipeline/crosscheck_relay_dongju.py fetch             # DEM windows from NASA servers (~3 GB, not committed)",
          "python pipeline/crosscheck_relay_dongju.py run               # lander, best towers, networks, timelines (~4 min)",
          "python pipeline/crosscheck_relay_dongju.py candidates        # 5,025 candidates: ground, slope, LOS, Fresnel (~6 min)",
          "python pipeline/crosscheck_relay_dongju.py candidates-earth  # 5,025 candidates: tower Earth (~6 min per site)",
          "python pipeline/crosscheck_relay_dongju.py report            # writes docs/crosscheck_relay_dongju.{json,md}",
          "```", "",
          "Work folder: `data/processed/crosscheck_relay_dongju/` (or `RELAY_XCHECK_WORK`)."]
    (ROOT / "docs" / "crosscheck_relay_dongju.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("fetch", "run", "candidates", "candidates-earth", "report"):
        s = sub.add_parser(c)
        s.add_argument("--site", action="append")
        s.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    {"fetch": cmd_fetch, "run": cmd_run, "candidates": cmd_candidates, "candidates-earth": cmd_candidates_earth,
     "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
