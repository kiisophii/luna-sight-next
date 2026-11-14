"""Multi-resolution horizon engine (phase 2).

For one site, march outward along great circles in 720 azimuths (0.5 deg, 0 = north,
clockwise) from ~0.2 km to 300 km with a geometric step, sample terrain heights through a
chain of DEM samplers (finest first), and keep the maximum elevation angle per azimuth.
Exact spherical geometry (R = 1737.4 km) is used, so lunar curvature is always included.
The observer stands 2 m above the terrain at the site.

Output format: docs/data_contract.md section 3 (web/data/horizon/<ID>.json).

Sampler interface (tiny on purpose):
    sampler.name   -> str   (e.g. "PGDA_LOLA_5M", "SLDEM2015", "LDEM_16")
    sampler.res_m  -> float (pixel size in metres)
    sampler.sample(lat_deg, lon_deg) -> float64 array of heights in metres above
        R = 1737.4 km, NaN where the sampler has no data.
A chain is a list [(sampler, max_km), ...], finest first. For a point at distance s,
the first sampler with s <= max_km that returns a finite value wins; NaN falls through
to the next (coarser) sampler.

Geometry (observer O at radius r_o along unit vector u; terrain point at angular distance
theta along direction d(az), radius r_t):
    elevation = atan2(r_t*cos(theta) - r_o, r_t*sin(theta))
Early stop: once even a peak at the highest lunar height (+10.8 km) could not beat the
current maximum at the next distance, the azimuth is finished (that bound only decreases
with distance).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

R_M = 1737400.0                 # reference sphere, contract section 0
OBS_HEIGHT_M = 2.0              # observer above terrain, contract section 0
HMAX_M = 10800.0                # max lunar height above R (~ +10.79 km), early-stop bound
N_AZ = 720
AZ_STEP_DEG = 360.0 / N_AZ
ENGINE_VERSION = 1

try:  # optional speed-up for the bilinear kernel
    from numba import njit as _njit
except Exception:  # noqa: BLE001
    _njit = None


# ------------------------------------------------------------------ bilinear kernels
def _bilinear_np(img, r, c):
    """Bilinear interpolation at fractional pixel-centre coords; NaN outside or near NaN."""
    nr, nc = img.shape
    out = np.full(r.shape, np.nan)
    ok = (r >= 0) & (r <= nr - 1) & (c >= 0) & (c <= nc - 1)
    if not ok.any():
        return out
    rr, cc = r[ok], c[ok]
    r0 = np.minimum(np.floor(rr).astype(np.int64), nr - 2) if nr > 1 else np.zeros(rr.shape, np.int64)
    c0 = np.minimum(np.floor(cc).astype(np.int64), nc - 2) if nc > 1 else np.zeros(cc.shape, np.int64)
    fr, fc = rr - r0, cc - c0
    r1 = np.minimum(r0 + 1, nr - 1)
    c1 = np.minimum(c0 + 1, nc - 1)
    v = ((1 - fr) * ((1 - fc) * img[r0, c0] + fc * img[r0, c1])
         + fr * ((1 - fc) * img[r1, c0] + fc * img[r1, c1]))
    out[ok] = v
    return out


if _njit is not None:
    @_njit(cache=True, fastmath=False)
    def _bilinear_nb(img, r, c):  # pragma: no cover - same maths as _bilinear_np
        nr, nc = img.shape
        out = np.empty(r.shape[0])
        for k in range(r.shape[0]):
            rr, cc = r[k], c[k]
            if not (rr >= 0 and rr <= nr - 1 and cc >= 0 and cc <= nc - 1):
                out[k] = np.nan
                continue
            r0 = min(int(math.floor(rr)), max(nr - 2, 0))
            c0 = min(int(math.floor(cc)), max(nc - 2, 0))
            r1 = min(r0 + 1, nr - 1)
            c1 = min(c0 + 1, nc - 1)
            fr, fc = rr - r0, cc - c0
            out[k] = ((1 - fr) * ((1 - fc) * img[r0, c0] + fc * img[r0, c1])
                      + fr * ((1 - fc) * img[r1, c0] + fc * img[r1, c1]))
        return out

    def bilinear(img, r, c):
        r = np.ascontiguousarray(r, dtype=np.float64).ravel()
        c = np.ascontiguousarray(c, dtype=np.float64).ravel()
        return _bilinear_nb(img, r, c)
else:
    def bilinear(img, r, c):
        return _bilinear_np(img, np.asarray(r, float).ravel(), np.asarray(c, float).ravel())


# ------------------------------------------------------------------ samplers
class FunctionSampler:
    """Wrap any f(lat_deg, lon_deg) -> heights (m). Used by tests and synthetic terrain."""

    def __init__(self, fn, name="SYNTHETIC", res_m=1.0):
        self.fn, self.name, self.res_m = fn, name, float(res_m)

    def sample(self, lat, lon):
        return np.asarray(self.fn(np.asarray(lat, float), np.asarray(lon, float)), float)


def polar_stereo_xy(lat, lon, south=True):
    """Spherical polar stereographic, true scale at the pole (k0 = 1), R = 1737.4 km.
    Matches PROJ '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400' (card 2 caches)."""
    lat = np.radians(np.asarray(lat, float))
    lon = np.radians(np.asarray(lon, float))
    if south:
        rho = 2 * R_M * np.tan(np.pi / 4 + lat / 2)
        return rho * np.sin(lon), rho * np.cos(lon)
    rho = 2 * R_M * np.tan(np.pi / 4 - lat / 2)
    return rho * np.sin(lon), -rho * np.cos(lon)


class PolarStereoSampler:
    """Card 2 cache: data/raw/polar/<res>/<ID>.npz with height_m (rows north->south, NaN = no
    data), x_m ascending, y_m descending (pixel centres, metres), metadata JSON string."""

    def __init__(self, path, name=None, res_m=None):
        self.path = Path(path)
        with np.load(self.path, allow_pickle=False) as z:
            self.h = np.ascontiguousarray(z["height_m"], dtype=np.float64)
            x, y = z["x_m"].astype(float), z["y_m"].astype(float)
            meta = json.loads(str(z["metadata"])) if "metadata" in z.files else {}
        if not (x.size == self.h.shape[1] and y.size == self.h.shape[0]):
            raise ValueError(f"{path}: x_m/y_m sizes do not match height_m")
        self.x0, self.dx = x[0], (x[-1] - x[0]) / max(x.size - 1, 1)
        self.y0, self.dy = y[0], (y[0] - y[-1]) / max(y.size - 1, 1)
        if self.dx <= 0 or self.dy <= 0:
            raise ValueError(f"{path}: expected x ascending and y descending")
        proj = meta.get("projection", "")
        if proj and ("lat_0=-90" not in proj or "R=1737400" not in proj.replace(".0", "")):
            raise ValueError(f"{path}: unexpected projection {proj!r}")
        self.res_m = float(res_m or meta.get("resolution_m") or self.dx)
        self.name = name or f"PGDA_LOLA_{self.res_m:g}M"
        self.radius_km = float(meta.get("radius_m", 0)) / 1000.0 or None
        self.meta = meta

    def sample(self, lat, lon):
        x, y = polar_stereo_xy(lat, lon, south=True)
        c = (x - self.x0) / self.dx
        r = (self.y0 - y) / self.dy
        return bilinear(self.h, r, c).reshape(np.shape(lat))


class LatLonWindowSampler:
    """Card 3 cache: data/raw/sldem/<ID>.npz with height_m (rows north->south), lat (pixel
    centres, descending), lon_unwrapped (pixel centres, ascending deg E, may exceed 0..360)."""

    def __init__(self, path, name="SLDEM2015", res_m=None):
        self.path = Path(path)
        with np.load(self.path, allow_pickle=False) as z:
            self.h = np.ascontiguousarray(z["height_m"], dtype=np.float64)
            la = z["lat"].astype(float)
            lu = z["lon_unwrapped"].astype(float) if "lon_unwrapped" in z.files else np.unwrap(
                np.radians(z["lon"].astype(float))) * 180 / np.pi
            meta = json.loads(str(z["meta"])) if "meta" in z.files else {}
        self.lat0, self.dlat = la[0], (la[0] - la[-1]) / max(la.size - 1, 1)
        self.lon0, self.dlon = lu[0], (lu[-1] - lu[0]) / max(lu.size - 1, 1)
        if self.dlat <= 0 or self.dlon <= 0:
            raise ValueError(f"{path}: expected lat descending and lon ascending")
        self.name = name
        self.res_m = float(res_m or math.radians(self.dlat) * R_M)
        self.radius_km = meta.get("radius_km")
        self.meta = meta

    def sample(self, lat, lon):
        lat = np.asarray(lat, float)
        lon = np.asarray(lon, float)
        mid = self.lon0 + 0.5 * self.dlon * (self.h.shape[1] - 1)   # window centre
        lon = (lon - mid + 180.0) % 360.0 + mid - 180.0             # nearest copy of lon
        r =(self.lat0 - lat) / self.dlat
        c = (lon - self.lon0) / self.dlon
        return bilinear(self.h, r, c).reshape(lat.shape)


def _parse_pds_label(text):
    keys = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k in keys or not k.replace("_", "").isalpha() or not k.isupper():
            continue
        v = v.split("<")[0].strip().strip('"').strip()
        try:
            keys[k] = float(v)
        except ValueError:
            keys[k] = v
    return keys


class GlobalCylSampler:
    """Global simple-cylindrical PDS float grid (LOLA LDEM_16 / LDEM_64 *_float.img + .lbl).
    Pixel (r, c) centre: lat = (LINE_PROJECTION_OFFSET - r)/res,
    lon = CENTER_LONGITUDE + (c - SAMPLE_PROJECTION_OFFSET)/res (0-based r, c, lon 0..360 E).
    Values are km relative to OFFSET (= 1737.4 km) -> converted to metres. Longitude wraps."""

    def __init__(self, img, lbl=None, name=None):
        img = Path(img)
        lbl = Path(lbl) if lbl else img.with_suffix(".lbl")
        L = _parse_pds_label(lbl.read_text(encoding="latin-1"))
        self.nl, self.ns = int(L["LINES"]), int(L["LINE_SAMPLES"])
        self.ppd = float(L["MAP_RESOLUTION"])
        self.lpo, self.spo = float(L["LINE_PROJECTION_OFFSET"]), float(L["SAMPLE_PROJECTION_OFFSET"])
        self.clon = float(L.get("CENTER_LONGITUDE", 180.0))
        offset_km = float(L.get("OFFSET", 1737.4))
        scale = float(L.get("SCALING_FACTOR", 1.0))
        unit = str(L.get("UNIT", "KILOMETER")).upper()
        if abs(offset_km - R_M / 1000) > 1e-6:
            raise ValueError(f"{lbl}: OFFSET {offset_km} km != 1737.4 km")
        if "KILOMETER" not in unit:
            raise ValueError(f"{lbl}: UNIT {unit} (expected KILOMETER)")
        if "MAXIMUM_LATITUDE" in L and abs((self.lpo + 0.5) / self.ppd - L["MAXIMUM_LATITUDE"]) > 1e-6:
            raise ValueError(f"{lbl}: pixel-centre convention check failed")
        self.data = np.memmap(img, dtype="<f4", mode="r", shape=(self.nl, self.ns))
        self.km_scale = 1000.0 * scale
        self.res_m = math.radians(1.0 / self.ppd) * R_M
        self.name = name or f"LDEM_{self.ppd:g}"

    def sample(self, lat, lon):
        shape = np.shape(lat)
        lat = np.asarray(lat, float).ravel()
        lon = np.asarray(lon, float).ravel()
        r = np.clip(self.lpo - lat * self.ppd, 0, self.nl - 1)
        c = self.spo + (np.mod(lon, 360.0) - self.clon) * self.ppd
        r0 = np.minimum(np.floor(r).astype(np.int64), self.nl - 2)
        fr = r - r0
        c0f = np.floor(c)
        fc = c - c0f
        c0 = c0f.astype(np.int64) % self.ns
        c1 = (c0 + 1) % self.ns
        d = self.data
        v = ((1 - fr) * ((1 - fc) * d[r0, c0] + fc * d[r0, c1])
             + fr * ((1 - fc) * d[r0 + 1, c0] + fc * d[r0 + 1, c1]))
        return (v.astype(np.float64) * self.km_scale).reshape(shape)


# ------------------------------------------------------------------ geometry
def site_frame(lat_deg, lon_deg):
    """Unit vectors (up, east, north) in MOON_ME for a site."""
    la, lo = math.radians(lat_deg), math.radians(lon_deg)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.cross(up, east)
    return up, east, north


def destination(lat_deg, lon_deg, az_deg, dist_m):
    """Great-circle destination(s): broadcast az (na,1) against dist (1,ns). Returns lat, lon deg."""
    up, east, north = site_frame(lat_deg, lon_deg)
    az = np.radians(np.asarray(az_deg, float))
    th = np.asarray(dist_m, float) / R_M
    ca, sa = np.cos(az), np.sin(az)
    ct, st = np.cos(th), np.sin(th)
    p = [up[i] * ct + (north[i] * ca + east[i] * sa) * st for i in range(3)]
    lat = np.degrees(np.arcsin(np.clip(p[2], -1, 1)))
    lon = np.degrees(np.arctan2(p[1], p[0]))
    return lat, lon


def sample_chain(chain, lat, lon, dist_km, used=None):
    """Heights (m) from the first sampler (finest first) that covers each point."""
    h = np.full(np.shape(lat), np.nan)
    for k, (sampler, max_km) in enumerate(chain):
        need = np.isnan(h) & (dist_km <= max_km)
        if not need.any():
            continue
        v = sampler.sample(lat[need], lon[need])
        h[need] = v
        if used is not None:
            got = np.isfinite(v)
            if got.any():
                used[k] = max(used.get(k, 0.0), float(dist_km[need][got].max()))
    return h


def distances_km(min_km=0.2, max_km=300.0, n_steps=4000):
    """Geometric distance grid (ratio exp(ln(max/min)/n_steps); ~0.18 % per step for defaults)."""
    return np.geomspace(min_km, max_km, n_steps + 1)


def compute_horizon(lat, lon, chain, *, h0_m=None, obs_height_m=OBS_HEIGHT_M,
                    min_km=0.2, max_km=300.0, n_steps=4000, block=128, early_stop=True,
                    hmax_m=HMAX_M):
    """Return dict with mask (720 deg), h0_m, used samplers, stats. `chain` = [(sampler, max_km)]."""
    if h0_m is None:
        h0 = sample_chain(chain, np.array([lat]), np.array([lon]), np.array([0.0]))[0]
        if not np.isfinite(h0):
            raise ValueError(f"no DEM covers the site itself ({lat}, {lon})")
        h0_m = float(h0)
    r_o = R_M + h0_m + obs_height_m
    az = np.arange(N_AZ) * AZ_STEP_DEG
    s_km = distances_km(min_km, max_km, n_steps)
    best = np.full(N_AZ, -np.inf)
    active = np.ones(N_AZ, bool)
    used, n_missing, n_samples = {}, 0, 0
    r_top = R_M + hmax_m
    for i0 in range(0, s_km.size, block):
        idx = np.flatnonzero(active)
        if idx.size == 0:
            break
        s = s_km[i0:i0 + block]
        la, lo = destination(lat, lon, az[idx][:, None], s[None, :] * 1000.0)
        dk = np.broadcast_to(s[None, :], la.shape)
        h = sample_chain(chain, la.ravel(), lo.ravel(), dk.ravel(), used).reshape(la.shape)
        th = s / (R_M / 1000.0)
        rt = R_M + h
        el = np.arctan2(rt * np.cos(th) - r_o, rt * np.sin(th))
        miss = ~np.isfinite(el)
        n_missing += int(miss.sum())
        n_samples += el.size
        el = np.where(miss, -np.inf, el)
        best[idx] = np.maximum(best[idx], el.max(axis=1))
        if early_stop and i0 + block < s_km.size:
            th_next = s_km[i0 + block] / (R_M / 1000.0)
            bound = math.atan2(r_top * math.cos(th_next) - r_o, r_top * math.sin(th_next))
            active[idx[best[idx] > bound]] = False
    if not np.all(np.isfinite(best)):
        bad = np.flatnonzero(~np.isfinite(best))
        raise ValueError(f"{bad.size} azimuths had no terrain samples (first az {az[bad[0]]} deg)")
    sources = [{"name": chain[k][0].name, "res_m": round(float(chain[k][0].res_m), 1),
                "to_km": round(min(used[k], max_km), 2)} for k in sorted(used)]
    return {"mask": np.degrees(best), "h0_m": h0_m, "dem_sources": sources,
            "n_missing": n_missing, "n_samples": n_samples,
            "params": {"min_km": min_km, "max_km": max_km, "n_steps": n_steps,
                       "early_stop": early_stop, "hmax_m": hmax_m, "engine_version": ENGINE_VERSION}}


def horizon_record(site, result):
    """Contract section 3 JSON object (plus a few QA extras the app ignores)."""
    return {
        "id": site["id"], "lat": site["lat"], "lon": site["lon"],
        "h0_m": round(float(result["h0_m"]), 2), "obs_height_m": 2,
        "az_step_deg": AZ_STEP_DEG,
        "mask": [round(float(v), 4) for v in result["mask"]],
        "max_range_km": result["params"]["max_km"],
        "dem_sources": result["dem_sources"],
        "engine": dict(result["params"], n_missing_samples=result["n_missing"],
                       n_samples=result["n_samples"]),
        # The horizon is a real computation from real DEMs for these coordinates, so it is not
        # mock data; if the site coordinates themselves are placeholders we say so separately.
        "site_coords_mock": bool(site.get("mock", False)),
        "mock": False,
    }


def write_json_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
