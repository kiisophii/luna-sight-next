"""Whole-Moon average sunlight / Earth-visibility maps (phase 2, items C5/C6).

For every point of a global lat/lon grid (pixel centres, `--ppd` pixels per degree):
  1. horizon over N_AZ azimuths (default 360), marched outward to 300 km along great circles
     with exact spherical geometry (lunar curvature always included), observer 2 m above
     terrain. Near terrain (<= 150 km) from the near DEM (LDEM_64, 474 m), beyond that from
     the far DEM (LDEM_16, 1895 m). NaN in the near DEM falls through to the far DEM.
  2. metrics over the whole ephemeris file (web/data/ephem.bin = 2026-2030, contract section 2)
     at a 1-3 h step, straight from the mask (masks are never stored):
        sun   = mean visible fraction of the solar disk (radius 0.2666 deg, contract section 6)
        earth = fraction of time the Earth CENTRE is above the mask (topocentric, conservative)
        both  = fraction of time sunlit (sun fraction >= 0.5) AND Earth visible
Same definitions as web/js/core.js and pipeline/horizon.py (contract sections 0, 3, 6).

Commands (run from the repo root):
  python pipeline/global_maps.py run --ppd 8                     # 3.8 km map (resumable)
  python pipeline/global_maps.py run --ppd 8 --rows 700:708      # quick test band
  python pipeline/global_maps.py run --ppd 32 --all-cores        # 948 m map (hours)
  python pipeline/global_maps.py status --ppd 8
  python pipeline/global_maps.py export --ppd 8                  # -> web/data/gmaps/
  python pipeline/global_maps.py validate                        # vs PGDA AVGVISIB_75S_120M
  python pipeline/global_maps.py synth --dir <tmp>               # synthetic DEM + ephemeris
Resume: results go row by row into memmaps under data/processed/gmaps_ppd<P>/ with a per-row
done mask; rerunning the same command continues where it stopped. Changing any parameter
that affects the numbers is refused unless --restart is given.

Threads: by default 4 numba threads; --all-cores uses every core (CLAUDE.md rule).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as hz  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
R_M = hz.R_M                       # 1737.4 km reference sphere
OBS_HEIGHT_M = hz.OBS_HEIGHT_M     # 2 m
SUN_RADIUS_DEG = 0.2666            # contract section 6 (solar disk radius)
ENGINE_VERSION = 1
LAYERS = ("sun", "earth", "both")
DEFAULT_THREADS = 4

import numba  # noqa: E402
from numba import njit, prange  # noqa: E402

# fastmath without nnan/ninf: NaN tests must keep working
FM = {"nsz", "arcp", "contract", "afn", "reassoc"}


# =========================================================================== numba kernels
@njit(cache=True, fastmath=FM)
def _cyl(d, lpo, spo, clon, ppd, scale, lat, lon):
    """Bilinear height (m) from a global simple-cylindrical PDS grid; same maths as
    horizon.GlobalCylSampler.sample (lon wraps, lat clamps)."""
    nl = d.shape[0]
    ns = d.shape[1]
    r = lpo - lat * ppd
    if r < 0.0:
        r = 0.0
    elif r > nl - 1:
        r = nl - 1.0
    lonm = lon % 360.0
    c = spo + (lonm - clon) * ppd
    r0 = int(math.floor(r))
    if r0 > nl - 2:
        r0 = nl - 2
    fr = r - r0
    c0f = math.floor(c)
    fc = c - c0f
    c0 = int(c0f) % ns
    c1 = (c0 + 1) % ns
    v = ((1.0 - fr) * ((1.0 - fc) * d[r0, c0] + fc * d[r0, c1])
         + fr * ((1.0 - fc) * d[r0 + 1, c0] + fc * d[r0 + 1, c1]))
    return v * scale


@njit(cache=True, fastmath=FM)
def _disk_fraction(x):
    """Visible part of a disk whose centre is x radii above a straight horizon line."""
    if x >= 1.0:
        return 1.0
    if x <= -1.0:
        return 0.0
    return 0.5 + (x * math.sqrt(1.0 - x * x) + math.asin(x)) / math.pi


@njit(cache=True, fastmath=FM)
def _mask_at(mask, az):
    """Linear interpolation of the mask (rad) at azimuth az (rad, any range)."""
    naz = mask.shape[0]
    x = (az / (2.0 * math.pi)) * naz
    x = x % naz
    i0 = int(math.floor(x))
    f = x - i0
    if i0 >= naz:
        i0 = naz - 1
    i1 = (i0 + 1) % naz
    return mask[i0] * (1.0 - f) + mask[i1] * f


@njit(parallel=True, cache=True, fastmath=FM)
def _points_kernel(lat_deg, lon_deg, hbound,
                   d0, p0, d1, p1,
                   cos_t, sin_t, dem_idx, naz, obs_h,
                   sun_u, sun_d, earth_u, earth_d, sun_r,
                   out, masks_out, keep_masks):
    """For each point: horizon (naz azimuths) then metrics over the ephemeris.
    p0/p1 = (lpo, spo, clon, ppd, scale_m) of the near / far DEM.
    out[i] = (sun, earth, both, h0_m, mask_max_deg, n_missing_samples)."""
    n = lat_deg.shape[0]
    ns = cos_t.shape[0]
    nt = sun_u.shape[0]
    two_pi = 2.0 * math.pi
    for i in prange(n):
        la = math.radians(lat_deg[i])
        lo = math.radians(lon_deg[i])
        cla, sla, clo, slo = math.cos(la), math.sin(la), math.cos(lo), math.sin(lo)
        ux, uy, uz = cla * clo, cla * slo, sla              # up
        ex, ey, ez = -slo, clo, 0.0                          # east
        nx, ny, nz = -sla * clo, -sla * slo, cla             # north = up x east
        h0 = _cyl(d0, p0[0], p0[1], p0[2], p0[3], p0[4], lat_deg[i], lon_deg[i])
        if math.isnan(h0):
            h0 = _cyl(d1, p1[0], p1[1], p1[2], p1[3], p1[4], lat_deg[i], lon_deg[i])
        if math.isnan(h0):
            for q in range(6):
                out[i, q] = np.nan
            continue
        ro = R_M + h0 + obs_h
        rtop = R_M + hbound[i]
        if rtop < ro + 1.0:
            rtop = ro + 1.0          # keeps the early-stop bound monotone (see module doc of horizon.py)
        mask = np.empty(naz)
        n_miss = 0
        for a in range(naz):
            az = two_pi * a / naz
            ca, sa = math.cos(az), math.sin(az)
            dx, dy, dz = nx * ca + ex * sa, ny * ca + ey * sa, nz * ca + ez * sa
            best = -1e30
            for k in range(ns):
                ct, st = cos_t[k], sin_t[k]
                px, py, pz = ux * ct + dx * st, uy * ct + dy * st, uz * ct + dz * st
                if pz > 1.0:
                    pz = 1.0
                elif pz < -1.0:
                    pz = -1.0
                plat = math.degrees(math.asin(pz))
                plon = math.degrees(math.atan2(py, px))
                if dem_idx[k] == 0:
                    h = _cyl(d0, p0[0], p0[1], p0[2], p0[3], p0[4], plat, plon)
                    if math.isnan(h):
                        h = _cyl(d1, p1[0], p1[1], p1[2], p1[3], p1[4], plat, plon)
                else:
                    h = _cyl(d1, p1[0], p1[1], p1[2], p1[3], p1[4], plat, plon)
                if math.isnan(h):
                    n_miss += 1
                else:
                    rt = R_M + h
                    t = (rt * ct - ro) / (rt * st)      # tan(elevation), monotone in elevation
                    if t > best:
                        best = t
                # early stop: even the highest terrain within range cannot beat `best` further out
                if (k & 7) == 7 and k + 1 < ns:
                    tb = (rtop * cos_t[k + 1] - ro) / (rtop * sin_t[k + 1])
                    if tb < best:
                        break
            mask[a] = math.atan(best)
        mmin = mask.min()
        mmax = mask.max()
        if keep_masks:
            for a in range(naz):
                masks_out[i, a] = math.degrees(mask[a])
        # thresholds in sin(elevation) space for the quick accept / reject
        lo_s = mmin - sun_r
        hi_s = mmax + sun_r
        s_lo = math.sin(max(lo_s, -0.5 * math.pi))
        s_hi = math.sin(min(hi_s, 0.5 * math.pi)) if hi_s < 0.5 * math.pi else 2.0
        e_lo = math.sin(max(mmin, -0.5 * math.pi))
        e_hi = math.sin(mmax) if mmax < 0.5 * math.pi else 2.0
        acc_sun = 0.0
        n_earth = 0
        n_both = 0
        for t in range(nt):
            # Sun (topocentric; parallax negligible but free)
            D = sun_d[t]
            cu = sun_u[t, 0] * ux + sun_u[t, 1] * uy + sun_u[t, 2] * uz
            sel = (D * cu - ro) / math.sqrt(D * D - 2.0 * D * ro * cu + ro * ro)
            if sel <= s_lo:
                f = 0.0
            elif sel >= s_hi:
                f = 1.0
            else:
                ce = sun_u[t, 0] * ex + sun_u[t, 1] * ey + sun_u[t, 2] * ez
                cn = sun_u[t, 0] * nx + sun_u[t, 1] * ny + sun_u[t, 2] * nz
                m = _mask_at(mask, math.atan2(ce, cn))
                f = _disk_fraction((math.asin(sel) - m) / sun_r)
            acc_sun += f
            # Earth centre (topocentric parallax up to ~0.26 deg)
            D = earth_d[t]
            cu = earth_u[t, 0] * ux + earth_u[t, 1] * uy + earth_u[t, 2] * uz
            sel = (D * cu - ro) / math.sqrt(D * D - 2.0 * D * ro * cu + ro * ro)
            if sel <= e_lo:
                vis = False
            elif sel >= e_hi:
                vis = True
            else:
                ce = earth_u[t, 0] * ex + earth_u[t, 1] * ey + earth_u[t, 2] * ez
                cn = earth_u[t, 0] * nx + earth_u[t, 1] * ny + earth_u[t, 2] * nz
                vis = math.asin(sel) > _mask_at(mask, math.atan2(ce, cn))
            if vis:
                n_earth += 1
                if f >= 0.5:
                    n_both += 1
        out[i, 0] = acc_sun / nt
        out[i, 1] = n_earth / nt
        out[i, 2] = n_both / nt
        out[i, 3] = h0
        out[i, 4] = math.degrees(mmax)
        out[i, 5] = n_miss


# =========================================================================== inputs
class Dem:
    """Global cylindrical DEM (LDEM_*_float.img + .lbl) as arrays for the numba kernel."""

    def __init__(self, img, name=None):
        s = hz.GlobalCylSampler(img, name=name)
        self.path = Path(img)
        self.name = s.name
        if "SYNTHETIC" in self.path.with_suffix(".lbl").read_text(encoding="latin-1")[:400]:
            self.name = s.name = "SYNTH_" + s.name     # never mistaken for real LOLA data
        self.res_m = s.res_m
        self.ppd = s.ppd
        self.data = np.asarray(s.data)          # still memory-mapped, plain ndarray for numba
        self.params = np.array([s.lpo, s.spo, s.clon, s.ppd, s.km_scale], dtype=np.float64)
        self.sampler = s

    def signature(self):
        st = self.path.stat()
        return {"name": self.name, "file": self.path.name, "bytes": st.st_size,
                "res_m": round(self.res_m, 1)}


def load_dems(raw, near_name, far_name):
    raw = Path(raw)
    paths = {}
    for role, nm in (("near", near_name), ("far", far_name)):
        p = Path(nm) if (nm.endswith(".img") or os.sep in nm or "/" in nm) else raw / "global" / f"{nm.lower()}_float.img"
        if not p.exists() or not p.with_suffix(".lbl").exists():
            raise SystemExit(f"missing {role} DEM {p} (+ .lbl). Card 3: python pipeline/fetch_global.py "
                             f"(LDEM_64 = 1.06 GB, LDEM_16 = 66 MB); or pass --near/--far.")
        paths[role] = p
    near = Dem(paths["near"])
    far = near if paths["far"].resolve() == paths["near"].resolve() else Dem(paths["far"])
    return near, far


def load_ephem(path, step_h=2):
    """Contract section 2 file (ephem.bin + ephem.json) or the card-1 validation npz
    (key `vectors`, float[N][6]). Returns dict with unit vectors and distances in metres."""
    path = Path(path)
    if path.suffix == ".npz":
        with np.load(path, allow_pickle=False) as z:
            v = np.asarray(z["vectors"], dtype=np.float64)
            file_step = int(z["step_h"]) if "step_h" in z.files else 2
            meta = {"start": str(z["start"]) if "start" in z.files else "?", "step_h": file_step,
                    "n": int(v.shape[0]), "mock": False,
                    "stop_exclusive": str(z["stop_exclusive"]) if "stop_exclusive" in z.files else "?"}
    else:
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        v = np.fromfile(path, dtype="<f4").astype(np.float64)
        n = int(meta["n"])
        if v.size != n * 6:
            raise SystemExit(f"{path}: {v.size} floats, expected n*6 = {n * 6}")
        v = v.reshape(n, 6)
        file_step = int(meta.get("step_h", 1))
    if step_h % file_step:
        raise SystemExit(f"--step-h {step_h} is not a multiple of the file step {file_step} h")
    k = step_h // file_step
    v = v[::k]
    sun, earth = v[:, 0:3] * 1000.0, v[:, 3:6] * 1000.0
    sd = np.linalg.norm(sun, axis=1)
    ed = np.linalg.norm(earth, axis=1)
    h = hashlib.sha1(np.ascontiguousarray(v, dtype=np.float64).tobytes()).hexdigest()[:12]
    return {"sun_u": np.ascontiguousarray(sun / sd[:, None]), "sun_d": sd,
            "earth_u": np.ascontiguousarray(earth / ed[:, None]), "earth_d": ed,
            "step_h": step_h, "n_used": int(v.shape[0]), "file": path.name, "sha1_12": h,
            "start": meta.get("start"), "mock": bool(meta.get("mock", False)),
            "source": meta.get("source", "")}


def build_steps(near_res_m, far_res_m, near_km=150.0, max_km=300.0, frac=0.01, start_m=None):
    """Distances (m) along each azimuth: step = max(DEM pixel, frac * distance).
    Returns (dist_m, dem_idx) with dem_idx 0 = near DEM, 1 = far DEM."""
    s = float(start_m if start_m is not None else 0.5 * near_res_m)
    d, idx = [], []
    while s <= max_km * 1000.0 + 1e-6:
        near = s <= near_km * 1000.0
        d.append(s)
        idx.append(0 if near else 1)
        s += max(near_res_m if near else far_res_m, frac * s)
    return np.array(d), np.array(idx, dtype=np.int8)


def cell_max_bound(dems, max_km):
    """Upper bound (m) of terrain height within max_km of any point of each 1x1 deg cell
    (180 x 360, rows from 90N, cols from lon -180). Used only for the early stop."""
    cmax = np.full((180, 360), -np.inf)
    for dem in dems:
        p = int(round(dem.ppd))
        lpo, spo, clon = dem.params[:3]
        aligned = (abs(lpo - (90 * p - 0.5)) < 1e-6 and abs(clon - (spo + 0.5) / p) < 1e-6
                   and dem.data.shape == (180 * p, 360 * p))
        if not aligned:   # unknown layout: fall back to the global maximum
            cmax = np.maximum(cmax, float(np.nanmax(dem.data)) * dem.params[4])
            continue
        blk = np.empty((180, 360))
        for r in range(180):   # row by row keeps memory low for LDEM_64
            rows = np.asarray(dem.data[r * p:(r + 1) * p], dtype=np.float32)
            blk[r] = np.nanmax(rows.reshape(p, 360, p), axis=(0, 2)) * dem.params[4]
        # DEM column 0 starts at lon 0 E; our cells start at lon -180
        cmax = np.maximum(cmax, np.roll(blk, 180, axis=1))
    ang = math.degrees(max_km * 1000.0 / R_M) + 1.0         # + 1 cell margin (bilinear corners)
    nr = int(math.ceil(ang))
    out = np.empty_like(cmax)
    for i in range(180):
        k0, k1 = max(i - nr, 0), min(i + nr + 1, 180)
        rowmax = cmax[k0:k1].max(axis=0)
        latmax = max(abs(90 - k0), abs(90 - k1))            # extreme |lat| edge of the window
        if latmax >= 80:
            out[i] = rowmax.max()
            continue
        w = min(180, int(math.ceil(ang / math.cos(math.radians(latmax)))) + 1)
        acc = rowmax.copy()
        for s in range(1, w + 1):
            acc = np.maximum(acc, np.maximum(np.roll(rowmax, s), np.roll(rowmax, -s)))
        out[i] = acc
    return out


def bound_at(bound, lat, lon):
    r = np.clip(np.floor(90.0 - np.asarray(lat)).astype(int), 0, 179)
    c = np.clip(np.floor(np.asarray(lon) + 180.0).astype(int), 0, 359)
    return bound[r, c] + 1.0


# =========================================================================== engine
class Engine:
    def __init__(self, near, far, ephem, naz=360, near_km=150.0, max_km=300.0, step_frac=0.01,
                 obs_h=OBS_HEIGHT_M):
        self.near, self.far, self.ephem = near, far, ephem
        self.naz, self.near_km, self.max_km, self.step_frac = naz, near_km, max_km, step_frac
        self.obs_h = obs_h
        dist, idx = build_steps(near.res_m, far.res_m, near_km, max_km, step_frac)
        th = dist / R_M
        self.dist_m, self.dem_idx = dist, idx
        self.cos_t, self.sin_t = np.cos(th), np.sin(th)
        dems = [near] if far is near else [near, far]
        self.bound = cell_max_bound(dems, max_km)

    def signature(self):
        e = self.ephem
        return {"engine_version": ENGINE_VERSION, "naz": self.naz, "near_km": self.near_km,
                "max_km": self.max_km, "step_frac": self.step_frac, "n_steps": int(self.dist_m.size),
                "obs_height_m": self.obs_h, "sun_radius_deg": SUN_RADIUS_DEG,
                "near": self.near.signature(), "far": self.far.signature(),
                "ephem": {"file": e["file"], "step_h": e["step_h"], "n_used": e["n_used"],
                          "sha1_12": e["sha1_12"], "start": e["start"], "mock": e["mock"]}}

    def points(self, lat, lon, keep_masks=False):
        lat = np.ascontiguousarray(lat, dtype=np.float64).ravel()
        lon = np.ascontiguousarray(lon, dtype=np.float64).ravel()
        out = np.empty((lat.size, 6))
        masks = np.empty((lat.size if keep_masks else 1, self.naz))
        e = self.ephem
        _points_kernel(lat, lon, bound_at(self.bound, lat, lon),
                       self.near.data, self.near.params, self.far.data, self.far.params,
                       self.cos_t, self.sin_t, self.dem_idx, self.naz, self.obs_h,
                       e["sun_u"], e["sun_d"], e["earth_u"], e["earth_d"],
                       math.radians(SUN_RADIUS_DEG), out, masks, keep_masks)
        return (out, masks) if keep_masks else out


# =========================================================================== grid store (resumable)
def grid_axes(ppd):
    nlat, nlon = 180 * ppd, 360 * ppd
    lat = 90.0 - (np.arange(nlat) + 0.5) / ppd
    lon = -180.0 + (np.arange(nlon) + 0.5) / ppd
    return lat, lon


class Store:
    """data/processed/gmaps_ppd<P>/{sun,earth,both,h0,maskmax}.npy (float32 memmaps, NaN = not done)
    + done.npy (uint8 per row) + meta.json (parameter signature for safe resume)."""
    FIELDS = ("sun", "earth", "both", "h0", "maskmax")

    def __init__(self, folder, ppd, signature=None, restart=False, readonly=False):
        self.dir = Path(folder)
        self.ppd = ppd
        self.nlat, self.nlon = 180 * ppd, 360 * ppd
        meta_p = self.dir / "meta.json"
        mode = "r" if readonly else "r+"
        if readonly or (meta_p.exists() and not restart):
            if not meta_p.exists():
                raise SystemExit(f"no map in {self.dir} - run first")
            self.meta = json.loads(meta_p.read_text(encoding="utf-8"))
            if signature is not None and self.meta["signature"] != signature:
                diff = [k for k in signature if self.meta["signature"].get(k) != signature.get(k)]
                raise SystemExit(f"{self.dir} was made with different parameters ({', '.join(diff)}).\n"
                                 f"Use the same options to resume, or --restart to start over.")
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            for f in self.FIELDS:
                m = np.lib.format.open_memmap(self.dir / f"{f}.npy", mode="w+", dtype=np.float32,
                                              shape=(self.nlat, self.nlon))
                m[:] = np.nan
                m.flush()
                del m
            d = np.lib.format.open_memmap(self.dir / "done.npy", mode="w+", dtype=np.uint8, shape=(self.nlat,))
            d[:] = 0
            d.flush()
            del d
            self.meta = {"ppd": ppd, "nlat": self.nlat, "nlon": self.nlon, "signature": signature,
                         "created_utc": _now(), "grid": "pixel centres; lat 90 - (r+0.5)/ppd, "
                                                         "lon -180 + (c+0.5)/ppd (MOON_ME)"}
            _write_json(meta_p, self.meta)
        self.arr = {f: np.load(self.dir / f"{f}.npy", mmap_mode=mode) for f in self.FIELDS}
        self.done = np.load(self.dir / "done.npy", mmap_mode=mode)

    def write_rows(self, r0, r1, res):
        res = res.reshape(r1 - r0, self.nlon, 6)
        for q, f in enumerate(self.FIELDS):
            self.arr[f][r0:r1] = res[:, :, q]
            self.arr[f].flush()
        self.done[r0:r1] = 1           # only after the values are on disk
        self.done.flush()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def parse_rows(spec, nlat):
    if not spec:
        return 0, nlat
    a, b = spec.split(":")
    r0, r1 = int(a or 0), int(b or nlat)
    if not (0 <= r0 < r1 <= nlat):
        raise SystemExit(f"--rows {spec}: need 0 <= start < stop <= {nlat}")
    return r0, r1


def run_grid(engine, store, rows=None, band=None, log=print):
    """Compute all not-yet-done rows in [r0, r1) band by band. Returns rows computed."""
    r0, r1 = rows or (0, store.nlat)
    band = band or max(1, store.ppd)
    _, lon = grid_axes(store.ppd)
    lat_all, _ = grid_axes(store.ppd)
    todo = [r for r in range(r0, r1) if not store.done[r]]
    if not todo:
        log(f"rows {r0}:{r1} already done")
        return 0
    t_start, n_done = time.time(), 0
    i = 0
    while i < len(todo):
        a = todo[i]
        b = a
        while i < len(todo) and todo[i] == b and b - a < band:   # contiguous run, at most `band` rows
            b += 1
            i += 1
        la = np.repeat(lat_all[a:b], lon.size)
        lo = np.tile(lon, b - a)
        t0 = time.time()
        res = engine.points(la, lo)
        store.write_rows(a, b, res)
        n_done += b - a
        el = time.time() - t_start
        left = len(todo) - n_done
        log(f"rows {a}:{b} (lat {lat_all[a]:+.3f}..{lat_all[b - 1]:+.3f}) {time.time() - t0:.1f}s; "
            f"{n_done}/{len(todo)} rows, ETA {el / n_done * left / 60:.1f} min", flush=True)
    return n_done


# =========================================================================== export (web tiles)
COLORMAPS = {   # value 0..1 -> colour stops (Sun = yellow, Earth = blue; 'both' = violet)
    "sun":   [[0.0, "#0a0a14"], [0.25, "#4d3300"], [0.5, "#c78a00"], [0.75, "#ffd23f"], [1.0, "#fff7cc"]],
    "earth": [[0.0, "#0a0a14"], [0.25, "#0b2f5c"], [0.5, "#1f6fd1"], [0.75, "#3fa9ff"], [1.0, "#dff2ff"]],
    "both":  [[0.0, "#0a0a14"], [0.25, "#3b1d5c"], [0.5, "#7b4dff"], [0.75, "#b99bff"], [1.0, "#f1eaff"]],
}
NODATA_RGB = (40, 40, 40)
TILE = 512


def _hex(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def colorize(v, stops):
    xs = np.array([s[0] for s in stops])
    cs = np.array([_hex(s[1]) for s in stops], dtype=float)
    vv = np.clip(np.nan_to_num(v, nan=0.0), 0, 1)
    rgb = np.stack([np.interp(vv, xs, cs[:, k]) for k in range(3)], axis=-1)
    rgb[~np.isfinite(v)] = NODATA_RGB
    return np.round(rgb).astype(np.uint8)


def resample(a, w, h):
    """Resize a float grid (NaN = no data) to w x h with area averaging (down) / bilinear (up)."""
    from PIL import Image
    ok = np.isfinite(a)
    filt = Image.BOX if w <= a.shape[1] else Image.BILINEAR
    num = np.asarray(Image.fromarray(np.where(ok, a, 0).astype(np.float32), "F").resize((w, h), filt))
    den = np.asarray(Image.fromarray(ok.astype(np.float32), "F").resize((w, h), filt))
    out = np.full((h, w), np.nan, np.float32)
    good = den > 0.5
    out[good] = num[good] / den[good]
    return out


def export(store, out_dir, overview=(4096, 2048), quality=88, log=print):
    from PIL import Image
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    nlon = store.nlon
    zmax = max(2, int(round(math.log2(nlon / 1024.0))))
    levels = [{"z": z, "width": 1024 << z, "height": 512 << z, "nx": 2 << z, "ny": 1 << z}
              for z in range(zmax + 1)]
    done = np.asarray(store.done).astype(bool)
    sig = store.meta["signature"]
    layers = []
    for name in LAYERS:
        a = np.array(store.arr[name], dtype=np.float32)
        a[~done] = np.nan
        for L in levels:
            img = colorize(resample(a, L["width"], L["height"]), COLORMAPS[name])
            tdir = out_dir / "tiles" / name / str(L["z"])
            tdir.mkdir(parents=True, exist_ok=True)
            for ty in range(L["ny"]):
                for tx in range(L["nx"]):
                    Image.fromarray(img[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE]).save(
                        tdir / f"{tx}_{ty}.jpg", quality=quality, optimize=True)
        ov = resample(a, *overview)
        Image.fromarray(colorize(ov, COLORMAPS[name])).save(out_dir / f"{name}_overview.jpg",
                                                            quality=quality, optimize=True)
        q = np.where(np.isfinite(ov), np.round(np.clip(ov, 0, 1) * 250), 255).astype(np.uint8)
        Image.fromarray(q, "L").save(out_dir / f"{name}_values.png", optimize=True)
        fin = a[np.isfinite(a)]
        w = np.cos(np.radians(grid_axes(store.ppd)[0]))[:, None] * np.isfinite(a)
        layers.append({
            "id": name, "units": "fraction of time 0..1",
            "definition": {"sun": "mean visible fraction of the solar disk (radius 0.2666 deg)",
                           "earth": "fraction of time the Earth centre is above the horizon mask",
                           "both": "fraction of time sunlit (disk fraction >= 0.5) AND Earth visible"}[name],
            "colormap": COLORMAPS[name], "nodata_rgb": list(NODATA_RGB),
            "overview": f"{name}_overview.jpg", "values_png": f"{name}_values.png",
            "stats": {"min": float(fin.min()) if fin.size else None,
                      "max": float(fin.max()) if fin.size else None,
                      "area_mean": float(np.nansum(np.nan_to_num(a) * w) / max(w.sum(), 1e-12))},
        })
        log(f"{name}: {sum(L['nx'] * L['ny'] for L in levels)} tiles + overview")
    index = {
        "contract": "v1.2 proposal (docs/data_contract.md section 10)",
        "ppd": store.ppd, "grid_res_km": round(math.radians(1 / store.ppd) * R_M / 1000, 3),
        "projection": "equirectangular (plate carree), MOON_ME; image x: lon -180 (left edge) -> +180, "
                      "y: lat +90 (top edge) -> -90; pixel edges span the whole globe",
        "tiles": {"size": TILE, "url": "tiles/{layer}/{z}/{x}_{y}.jpg", "levels": levels,
                  "x0_y0": "north-west corner (lon -180, lat 90)"},
        "overview_size": list(overview),
        "values_png": "8-bit grey, same size as the overview: value = DN / 250, DN 255 = no data",
        "layers": layers,
        "rows_done": int(done.sum()), "rows_total": int(done.size),
        "window": "whole ephemeris file", "ephem": sig["ephem"],
        "dem_sources": [{"name": sig["near"]["name"], "res_m": sig["near"]["res_m"], "to_km": sig["near_km"]},
                        {"name": sig["far"]["name"], "res_m": sig["far"]["res_m"], "to_km": sig["max_km"]}],
        "params": {k: sig[k] for k in ("naz", "near_km", "max_km", "step_frac", "n_steps",
                                       "obs_height_m", "sun_radius_deg", "engine_version")},
        "computed_utc": store.meta.get("created_utc"), "exported_utc": _now(),
        "mock": bool(sig["ephem"]["mock"] or sig["near"]["name"].startswith("SYNTH")),
    }
    _write_json(out_dir / "index.json", index)
    return index


# =========================================================================== validation vs PGDA
PGDA_DN_SCALE = 0.00004    # PDS label SCALING_FACTOR of the AVGVISIB maps (DN 25000 = 1.0)


class PgdaMap:
    def __init__(self, path):
        import rasterio
        with rasterio.open(path) as d:
            raw = d.read(1)
            self.transform, self.crs = d.transform, d.crs
            scale = d.scales[0] if d.scales and d.scales[0] not in (None, 0) else 1.0
            offset = d.offsets[0] if d.offsets else 0.0
            nodata = d.nodata
        data = raw.astype(np.float64)
        if nodata is not None:
            data[raw == nodata] = np.nan
        if np.issubdtype(raw.dtype, np.integer) and abs(scale - 1.0) < 1e-12:
            scale, offset = PGDA_DN_SCALE, 0.0
        self.data = data * scale + offset
        if np.nanmax(self.data) > 1.0001:
            raise ValueError(f"{path}: values > 1 after scaling ({np.nanmax(self.data)})")
        self.name = Path(path).name
        self._check_projection()

    def _check_projection(self):
        """Our spherical south-polar stereographic formula must agree with the file's CRS."""
        try:
            from rasterio.crs import CRS
            from rasterio.warp import transform
        except Exception:  # noqa: BLE001
            return
        lats, lons = [-75.0, -80.0, -85.0, -89.0], [0.0, 90.0, -135.0, 45.0]
        x1, y1 = hz.polar_stereo_xy(lats, lons)
        x2, y2 = transform(CRS.from_proj4(f"+proj=longlat +R={R_M} +no_defs"), self.crs, lons, lats)
        err = float(np.max(np.hypot(x1 - np.array(x2), y1 - np.array(y2))))
        if err > 1.0:
            raise ValueError(f"{self.name}: projection mismatch {err:.1f} m (CRS {self.crs})")

    def sample(self, lat, lon):
        x, y = hz.polar_stereo_xy(lat, lon)
        inv = ~self.transform
        col = inv.a * x + inv.b * y + inv.c
        row = inv.d * x + inv.e * y + inv.f
        row, col = np.floor(row).astype(int), np.floor(col).astype(int)
        h, w = self.data.shape
        ok = (row >= 0) & (row < h) & (col >= 0) & (col < w)
        out = np.full(np.shape(lat), np.nan)
        out[ok] = self.data[row[ok], col[ok]]
        return out


def random_points(n, seed, lat_min=-85.0, lat_max=-75.0):
    """Uniform on the sphere inside the latitude band."""
    rng = np.random.default_rng(seed)
    s = rng.uniform(math.sin(math.radians(lat_min)), math.sin(math.radians(lat_max)), n)
    return np.degrees(np.arcsin(s)), rng.uniform(-180.0, 180.0, n)


def compare(ours, truth):
    ok = np.isfinite(ours) & np.isfinite(truth)
    a, b = ours[ok], truth[ok]
    if a.size < 2:
        return {"n": int(a.size)}
    d = (a - b) * 100
    r = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else None
    return {"n": int(a.size), "mae_pp": round(float(np.abs(d).mean()), 3),
            "rmse_pp": round(float(np.sqrt((d ** 2).mean())), 3), "bias_pp": round(float(d.mean()), 3),
            "r": None if r is None else round(r, 4)}


def validate(engine, pgda_sun, pgda_earth, n=240, seed=42, lat_range=(-85.0, -75.0), log=print):
    lat, lon = random_points(n, seed, *lat_range)
    t0 = time.time()
    out = engine.points(lat, lon)
    log(f"computed {n} points in {time.time() - t0:.1f}s")
    ps = PgdaMap(pgda_sun).sample(lat, lon)
    pe = PgdaMap(pgda_earth).sample(lat, lon)
    res = {"sun": compare(out[:, 0], ps), "earth": compare(out[:, 1], pe),
           "points": [{"lat": round(float(a), 4), "lon": round(float(b), 4),
                       "ours_sun": round(float(c), 4), "pgda_sun": None if not np.isfinite(d) else round(float(d), 4),
                       "ours_earth": round(float(e), 4), "pgda_earth": None if not np.isfinite(f) else round(float(f), 4)}
                      for a, b, c, d, e, f in zip(lat, lon, out[:, 0], ps, out[:, 1], pe)]}
    return res


# =========================================================================== synthetic inputs
SYNODIC_H = 29.530589 * 24.0


def write_synthetic_dem(img_path, ppd, fn=None):
    """Global simple-cylindrical float32 grid in the LDEM PDS layout (km above 1737.4 km).
    fn(lat_deg, lon_deg) -> height in metres (default: flat sphere)."""
    img_path = Path(img_path)
    img_path.parent.mkdir(parents=True, exist_ok=True)
    nl, ns = 180 * ppd, 360 * ppd
    lat = 90.0 - (np.arange(nl) + 0.5) / ppd
    lon = (np.arange(ns) + 0.5) / ppd                     # 0..360 E, CENTER_LONGITUDE 180
    if fn is None:
        h = np.zeros((nl, ns), np.float32)
    else:
        h = np.empty((nl, ns), np.float32)
        lon_s = np.where(lon > 180, lon - 360, lon)
        for r in range(nl):
            h[r] = fn(np.full(ns, lat[r]), lon_s) / 1000.0
    h.astype("<f4").tofile(img_path)
    img_path.with_suffix(".lbl").write_text(
        "PDS_VERSION_ID = PDS3\n/* SYNTHETIC test DEM written by pipeline/global_maps.py */\n"
        f"    LINES                 = {nl}\n    LINE_SAMPLES          = {ns}\n"
        "    SAMPLE_TYPE           = PC_REAL\n    UNIT                  = KILOMETER\n"
        "    SCALING_FACTOR        = 1\n    OFFSET                = 1737.4\n"
        f" MAP_RESOLUTION               = {ppd} <pix/deg>\n CENTER_LONGITUDE             = 180 <deg>\n"
        " MAXIMUM_LATITUDE             = 90 <deg>\n"
        f" LINE_PROJECTION_OFFSET       = {90 * ppd - 0.5} <pix>\n"
        f" SAMPLE_PROJECTION_OFFSET     = {180 * ppd - 0.5} <pix>\nEND\n", encoding="latin-1")
    return img_path


def write_synthetic_ephem(bin_path, n_hours=2 * 709, sub_earth=(0.0, 0.0)):
    """Toy ephemeris in the contract-2 layout: Sun circles the lunar equator once per synodic
    month (sub-solar longitude decreasing, i.e. the Sun rises in the east), 1 AU away; Earth is
    fixed above `sub_earth` at 384,400 km. NOT an ephemeris - tests only (mock = true)."""
    t = np.arange(n_hours, dtype=np.float64)
    ls = -2 * np.pi * t / SYNODIC_H
    sun = 1.496e8 * np.stack([np.cos(ls), np.sin(ls), np.zeros_like(ls)], axis=1)
    la, lo = np.radians(sub_earth[0]), np.radians(sub_earth[1])
    e = 384400.0 * np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    v = np.hstack([sun, np.tile(e, (n_hours, 1))]).astype("<f4")
    bin_path = Path(bin_path)
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    v.tofile(bin_path)
    _write_json(bin_path.with_suffix(".json"), {
        "start": "2026-01-01T00:00:00Z", "step_h": 1, "n": n_hours, "frame": "MOON_ME_DE421",
        "units": "km", "columns": ["sun_x", "sun_y", "sun_z", "earth_x", "earth_y", "earth_z"],
        "source": "SYNTHETIC toy model from pipeline/global_maps.py (not an ephemeris)", "mock": True})
    return bin_path


def synth(folder, near_ppd=16, far_ppd=4):
    """Flat synthetic LDEM_64/LDEM_16 stand-ins + toy ephemeris under <folder>."""
    folder = Path(folder)
    write_synthetic_dem(folder / "raw" / "global" / "ldem_64_float.img", near_ppd)
    write_synthetic_dem(folder / "raw" / "global" / "ldem_16_float.img", far_ppd)
    write_synthetic_ephem(folder / "ephem.bin")
    return folder


# =========================================================================== CLI
def _engine_from_args(a, ephem_path=None):
    numba.set_num_threads(os.cpu_count() if a.all_cores else min(a.threads, os.cpu_count()))
    near, far = load_dems(a.raw, a.near, a.far)
    eph = load_ephem(ephem_path or a.ephem, a.step_h)
    if eph["mock"]:
        print(f"NOTE: ephemeris {eph['file']} is mock ({eph['source']}) - numbers are not real")
    print(f"near {near.name} ({near.res_m:.0f} m, to {a.near_km:g} km), far {far.name} "
          f"({far.res_m:.0f} m, to {a.max_km:g} km); ephem {eph['n_used']} samples @ {eph['step_h']} h; "
          f"{numba.get_num_threads()} threads")
    return Engine(near, far, eph, naz=a.naz, near_km=a.near_km, max_km=a.max_km, step_frac=a.step_frac)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, ephem_default):
        p.add_argument("--raw", default=str(ROOT / "data" / "raw"), help="folder with global/ldem_*_float.img")
        p.add_argument("--near", default="LDEM_64", help="near DEM: LDEM_64 / LDEM_16 or a .img path")
        p.add_argument("--far", default="LDEM_16", help="far DEM: LDEM_16 or a .img path")
        p.add_argument("--ephem", default=str(ephem_default))
        p.add_argument("--step-h", type=int, default=2, help="ephemeris step used (1-3 h)")
        p.add_argument("--naz", type=int, default=360)
        p.add_argument("--near-km", type=float, default=150.0)
        p.add_argument("--max-km", type=float, default=300.0)
        p.add_argument("--step-frac", type=float, default=0.01, help="march step = max(DEM px, frac*dist)")
        p.add_argument("--threads", type=int, default=DEFAULT_THREADS)
        p.add_argument("--all-cores", action="store_true", help="use every CPU core")

    p = sub.add_parser("run", help="compute (or resume) a global map")
    common(p, ROOT / "web" / "data" / "ephem.bin")
    p.add_argument("--ppd", type=int, default=8)
    p.add_argument("--rows", default=None, help="START:STOP row range (row 0 = 90N), e.g. 700:708")
    p.add_argument("--band", type=int, default=None, help="rows per parallel band (default ppd)")
    p.add_argument("--out", default=None, help="default data/processed/gmaps_ppd<P>")
    p.add_argument("--restart", action="store_true", help="discard an existing map with other parameters")

    p = sub.add_parser("status")
    p.add_argument("--ppd", type=int, default=8)
    p.add_argument("--out", default=None)

    p = sub.add_parser("export", help="colour JPEG tiles + overview + index.json")
    p.add_argument("--ppd", type=int, default=8)
    p.add_argument("--out", default=None, help="map folder (default data/processed/gmaps_ppd<P>)")
    p.add_argument("--web", default=str(ROOT / "web" / "data" / "gmaps"))

    p = sub.add_parser("validate", help="compare with PGDA AVGVISIB_75S_120M in 75-85 S")
    common(p, ROOT / "data" / "processed" / "ephem_2020-2038_2h.npz")
    p.add_argument("--pgda-dir", default=str(ROOT / "data" / "raw" / "pgda"))
    p.add_argument("--pgda-sun", default="AVGVISIB_75S_120M_201608.TIF")
    p.add_argument("--pgda-earth", default="AVGVISIB_75S_120M_201608_EARTH.TIF")
    p.add_argument("--n", type=int, default=240)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--lat-range", default="-85:-75")
    p.add_argument("--report", default=str(ROOT / "data" / "processed" / "gmaps_validation.json"))

    p = sub.add_parser("synth", help="write synthetic flat DEMs + toy ephemeris for smoke tests")
    p.add_argument("--dir", required=True)

    a = ap.parse_args(argv)
    if a.cmd == "synth":
        f = synth(a.dir)
        print(f"synthetic inputs in {f}:\n  --raw {f / 'raw'} --ephem {f / 'ephem.bin'}")
        return 0
    if a.cmd in ("status", "export"):
        st = Store(a.out or ROOT / "data" / "processed" / f"gmaps_ppd{a.ppd}", a.ppd, readonly=True)
        nd = int(np.asarray(st.done).sum())
        print(f"{st.dir}: {nd}/{st.nlat} rows done ({100 * nd / st.nlat:.1f} %); "
              f"ephem mock={st.meta['signature']['ephem']['mock']}")
        if a.cmd == "export":
            idx = export(st, a.web)
            print(f"wrote {a.web}/index.json (mock={idx['mock']})")
        return 0
    if a.cmd == "run":
        eng = _engine_from_args(a)
        folder = Path(a.out or ROOT / "data" / "processed" / f"gmaps_ppd{a.ppd}")
        st = Store(folder, a.ppd, signature=eng.signature(), restart=a.restart)
        rows = parse_rows(a.rows, st.nlat)
        print(f"grid {st.nlat} x {st.nlon} ({math.radians(1 / a.ppd) * R_M / 1000:.2f} km), "
              f"rows {rows[0]}:{rows[1]}, {eng.dist_m.size} march steps/azimuth -> {folder}")
        run_grid(eng, st, rows, a.band)
        nd = int(np.asarray(st.done).sum())
        print(f"done: {nd}/{st.nlat} rows")
        return 0
    if a.cmd == "validate":
        eng = _engine_from_args(a)
        lo_, hi_ = (float(x) for x in a.lat_range.split(":"))
        pdir = Path(a.pgda_dir)
        res = validate(eng, pdir / a.pgda_sun, pdir / a.pgda_earth, a.n, a.seed, (lo_, hi_))
        res = {"what": "global-map engine vs PGDA average visibility (Mazarico et al. 2011, Icarus 211, 1066-1081)",
               "pgda_files": [a.pgda_sun, a.pgda_earth], "lat_range": [lo_, hi_], "n_points": a.n,
               "seed": a.seed, "signature": eng.signature(), "computed_utc": _now(),
               "note": "PGDA 'EARTH' definition (centre vs disk) unverified; ours = Earth centre above mask",
               **res}
        _write_json(a.report, res)
        print(f"SUN   {res['sun']}\nEARTH {res['earth']}\nreport -> {a.report}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
