"""Independent Task V Earth-definition comparison; no producer numerical imports.

The 240 random-point masks are reconstructed with the original sampling definition.
The named-point masks are shared inputs, not independently validated terrain.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_key] = "1"

import numpy as np
import rasterio
from numba import njit
from rasterio.windows import Window
import requests
import tifffile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/processed/task_v"
RADIUS_M = 1737400.0
EARTH_KM = 6371.0
SOURCE = "https://pgda.gsfc.nasa.gov/data/"
DEMS = {60: SOURCE + "LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF",
        240: SOURCE + "LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF"}
TRUTH = {60: SOURCE + "MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF",
         120: SOURCE + "MoonIllumination/AVGVISIB_75S_120M_201608_EARTH.TIF"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1 << 20), b""):
            h.update(data)
    return h.hexdigest()


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def xy(lat, lon):
    rho = 2 * RADIUS_M * np.tan(np.deg2rad(90 + np.asarray(lat)) / 2)
    angle = np.deg2rad(lon)
    return rho * np.sin(angle), rho * np.cos(angle)


class SourceRanges(io.RawIOBase):
    """Read original TIFF bytes, reusing immutable validated acquisition blocks.

    No producer code is imported. Existing 1 MiB blocks are read-only. Newly
    requested blocks live only in memory to avoid duplicate on-disk raw caches.
    """
    def __init__(self, url, headers):
        self.url, self.pos = url, 0
        self.size = int(headers["Content-Length"])
        self.etag, self.modified = headers.get("ETag"), headers.get("Last-Modified")
        self.session = requests.Session()
        self.blocks, self.directories = {}, []
        for root in (ROOT / "data/processed/local250/raw/polar/_blocks",
                     Path("C:/Users/jy02s/Documents/lunar-card8-jiyong/data/raw/polar/_blocks")):
            if root.exists():
                for meta_path in root.glob("*/source.json"):
                    record = json.loads(meta_path.read_text(encoding="utf-8"))
                    if record[:4] == [url, self.size, self.etag, self.modified] and len(record) == 5 and record[4] == 1048576:
                        self.directories.append(meta_path.parent)
        self.cached_bytes = self.network_bytes = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset + (0 if whence == 0 else self.pos if whence == 1 else self.size)
        return self.pos

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.pos + size, self.size)
        pieces = []
        while self.pos < end:
            offset = self.pos // 1048576 * 1048576
            stop = min(offset + 1048576, self.size)
            if offset not in self.blocks:
                content = None
                for folder in self.directories:
                    path = folder / str(offset)
                    if path.exists() and path.stat().st_size == stop - offset:
                        content = path.read_bytes()
                        self.cached_bytes += len(content)
                        break
                if content is None:
                    for attempt in range(4):
                        try:
                            response = self.session.get(self.url, headers={"Range": f"bytes={offset}-{stop-1}"}, timeout=30)
                            response.raise_for_status()
                            if response.status_code != 206 or response.headers.get("Content-Range") != f"bytes {offset}-{stop-1}/{self.size}":
                                raise ValueError("Unexpected DEM range response")
                            content = response.content
                            if len(content) != stop - offset or response.headers.get("ETag") != self.etag:
                                raise ValueError("Changed or incomplete DEM source")
                            break
                        except requests.RequestException:
                            if attempt == 3:
                                raise
                    self.network_bytes += len(content)
                    if self.network_bytes % (20 * 1048576) == 0:
                        print(f"DEM ranges: network {self.network_bytes/1e6:.1f} MB, reused {self.cached_bytes/1e6:.1f} MB", flush=True)
                self.blocks[offset] = content
                if len(self.blocks) > 32:
                    del self.blocks[next(iter(self.blocks))]
            take = min(end, stop) - self.pos
            pieces.append(self.blocks[offset][self.pos - offset:self.pos - offset + take])
            self.pos += take
        return b"".join(pieces)


def fetch_dem(res, radius):
    """Read only a pole-centred source window; store full-resolution decoded pixels."""
    path = CACHE / f"dem{res}.npy"
    meta_path = CACHE / f"dem{res}.json"
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if digest(path) != meta["sha256"]:
            raise ValueError("DEM cache hash mismatch")
        return np.load(path, mmap_mode="r"), meta
    CACHE.mkdir(parents=True, exist_ok=True)
    response = requests.head(DEMS[res], timeout=60)
    response.raise_for_status()
    stream = SourceRanges(DEMS[res], response.headers)
    with tifffile.TiffFile(stream) as tif:
            page = tif.pages[0]
            sx, sy, _ = page.tags[33550].value
            _, _, _, left, top, _ = page.tags[33922].value
            tags = page.geotiff_tags
            if sx != res or sy != res or tags["GTRasterTypeGeoKey"] != 1:
                raise ValueError("Unexpected DEM spacing")
            if tags["GeogSemiMajorAxisGeoKey"] != RADIUS_M or tags["ProjNatOriginLatGeoKey"] != -90:
                raise ValueError("Unexpected DEM projection")
            # One-pixel halo beyond the requested square. The original windows had
            # more than 7 km spare coverage for every required 60 m sample.
            r0, c0 = math.floor((top-radius)/res), math.floor((-radius-left)/res)
            r1, c1 = math.floor((top+radius)/res), math.floor((radius-left)/res)
            r0, c0, r1, c1 = r0 - 1, c0 - 1, r1 + 2, c1 + 2
            data = np.full((r1-r0, c1-c0), np.nan, dtype="<f4")
            th, tw = page.tilelength, page.tilewidth
            nc = math.ceil(page.imagewidth/tw)
            for tr in range(r0//th, (r1-1)//th+1):
                for tc in range(c0//tw, (c1-1)//tw+1):
                    idx = tr*nc+tc
                    stream.seek(page.dataoffsets[idx])
                    decoded, _, _ = page.decode(stream.read(page.databytecounts[idx]), idx)
                    tile = decoded[0, :, :, 0]
                    a,b,c,d = max(r0,tr*th), min(r1,(tr+1)*th), max(c0,tc*tw), min(c1,(tc+1)*tw)
                    data[a-r0:b-r0,c-c0:d-c0] = tile[a-tr*th:b-tr*th,c-tc*tw:d-tc*tw]
            nodata = page.tags.get(42113)
            if nodata:
                data[data == float(nodata.value.rstrip("\x00"))] = np.nan
            x0, y0 = left+(c0+.5)*res, top-(r0+.5)*res
            meta = dict(url=DEMS[res], etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                        source_bytes=int(response.headers["Content-Length"]),
                        bounds_rc=[r0, r1, c0, c1], x0=float(x0), y0=float(y0),
                        resolution_m=res, shape=list(data.shape), crs=str(tags),
                        reused_block_bytes=stream.cached_bytes, network_bytes=stream.network_bytes,
                        units="m above 1737.4 km sphere")
    np.save(path, data)
    meta["sha256"] = digest(path)
    save_json(meta_path, meta)
    print(f"DEM {res}: {data.nbytes / 1e6:.1f} MB", flush=True)
    return np.load(path, mmap_mode="r"), meta


def fetch_truth(res):
    path = CACHE / Path(TRUTH[res]).name
    if not path.exists():
        session = requests.Session()
        head = session.head(TRUTH[res], timeout=60)
        head.raise_for_status()
        total = int(head.headers["Content-Length"])
        temp = path.with_suffix(".part")
        offset = temp.stat().st_size if temp.exists() else 0
        with temp.open("ab") as out:
            while offset < total:
                end = min(offset + (1 << 20), total) - 1
                for attempt in range(4):
                    try:
                        response = session.get(TRUTH[res], headers={"Range": f"bytes={offset}-{end}"}, timeout=60)
                        response.raise_for_status()
                        if response.status_code != 206 or response.headers.get("Content-Range") != f"bytes {offset}-{end}/{total}":
                            raise ValueError("Unexpected range response")
                        if len(response.content) != end - offset + 1 or response.headers.get("ETag") != head.headers.get("ETag"):
                            raise ValueError("Truncated or changed source")
                        break
                    except requests.RequestException:
                        if attempt == 3:
                            raise
                out.write(response.content)
                out.flush()
                offset = end + 1
        temp.replace(path)
        save_json(path.with_suffix(".source.json"), dict(
            url=TRUTH[res], etag=head.headers.get("ETag"),
            last_modified=head.headers.get("Last-Modified"), sha256=digest(path)))
        print(f"Truth {res}: {total / 1e6:.1f} MB", flush=True)
    return path


# This audit is used both as a script and via dynamic imports in tests. Numba's
# disk cache pickles that module identity, which can become '<dynamic>' and fail
# to reload in another process. Compile per process; the scientific DEM/mask
# checkpoints below remain resumable and are independently hashed.
@njit(cache=False)
def interpolate_dem(grid, x0, y0, step, x, y):
    col, row = (x - x0) / step, (y0 - y) / step
    if row < 0 or col < 0 or row > grid.shape[0] - 1 or col > grid.shape[1] - 1:
        return np.nan
    ir = min(int(math.floor(row)), grid.shape[0] - 2)
    ic = min(int(math.floor(col)), grid.shape[1] - 2)
    fy, fx = row - ir, col - ic
    return ((1 - fy) * ((1 - fx) * grid[ir, ic] + fx * grid[ir, ic + 1])
            + fy * ((1 - fx) * grid[ir + 1, ic] + fx * grid[ir + 1, ic + 1]))


@njit(cache=False)
def reconstruct_mask(lat, lon, near, nx0, ny0, far, fx0, fy0, distances):
    """Independent Cartesian great-circle march, same discrete definition.

    Stereographic coordinates are computed directly from the unit vector,
    eliminating the producer's intermediate latitude/longitude conversion.
    No early stop is used, so every requested sample is examined.
    """
    la, lo = math.radians(lat), math.radians(lon)
    ux, uy, uz = math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)
    ex, ey = -math.sin(lo), math.cos(lo)
    nx, ny, nz = -math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)
    x, y = 2 * RADIUS_M * uy / (1 - uz), 2 * RADIUS_M * ux / (1 - uz)
    ground = interpolate_dem(near, nx0, ny0, 60., x, y)
    if not math.isfinite(ground):
        ground = interpolate_dem(far, fx0, fy0, 240., x, y)
    if not math.isfinite(ground):
        raise ValueError("Missing observer terrain")
    mask = np.empty(720)
    missing = 0
    for az in range(720):
        a = math.radians(az / 2)
        dx, dy, dz = nx * math.cos(a) + ex * math.sin(a), ny * math.cos(a) + ey * math.sin(a), nz * math.cos(a)
        maximum = -math.inf
        for distance in distances:
            theta = distance / RADIUS_M
            ct, st = math.cos(theta), math.sin(theta)
            px, py, pz = ux * ct + dx * st, uy * ct + dy * st, uz * ct + dz * st
            x, y = 2 * RADIUS_M * py / (1 - pz), 2 * RADIUS_M * px / (1 - pz)
            h = np.nan
            if distance <= 60000:
                h = interpolate_dem(near, nx0, ny0, 60., x, y)
            if not math.isfinite(h):
                h = interpolate_dem(far, fx0, fy0, 240., x, y)
            if not math.isfinite(h):
                missing += 1
                continue
            angle = math.atan2((RADIUS_M + h) * ct - (RADIUS_M + ground + 2), (RADIUS_M + h) * st)
            maximum = max(maximum, angle)
        mask[az] = math.degrees(maximum)
    if missing or not np.all(np.isfinite(mask)):
        raise ValueError("Missing ray terrain")
    return mask, ground


def horizon_at(mask, azimuth):
    mask = np.asarray(mask, dtype=np.float64)
    if mask.shape != (720,) or not np.all(np.isfinite(mask)):
        raise ValueError("Expected finite 720-bin mask")
    coord = np.mod(azimuth, 360) * 2
    index = np.floor(coord).astype(np.int64)
    weight = coord - index
    return mask[index] + weight * (mask[(index + 1) % 720] - mask[index])


def earth_fractions(earth, lat, lon, ground, mask, height=2):
    earth = np.asarray(earth, dtype=np.float64)
    if earth.ndim != 2 or earth.shape[1] != 3 or not np.all(np.isfinite(earth)) or not len(earth):
        raise ValueError("Expected nonempty finite Earth xyz array")
    la, lo = np.deg2rad([lat, lon])
    sl, cl, sp, cp = np.sin(lo), np.cos(lo), np.sin(la), np.cos(la)
    up = np.array([cp * cl, cp * sl, sp])
    topo = earth - (1737.4 + (ground + height) / 1000) * up
    # Explicit scalar components avoid depending on producer basis helpers.
    e = -sl * topo[:, 0] + cl * topo[:, 1]
    n = -sp * cl * topo[:, 0] - sp * sl * topo[:, 1] + cp * topo[:, 2]
    u = cp * cl * topo[:, 0] + cp * sl * topo[:, 1] + sp * topo[:, 2]
    az = np.rad2deg(np.arctan2(e, n)) % 360
    elevation = np.rad2deg(np.arctan2(u, np.hypot(e, n)))
    distance = np.sqrt(np.sum(topo * topo, axis=1))
    if np.any(distance <= EARTH_KM):
        raise ValueError("Observer cannot be inside Earth")
    radius = np.rad2deg(np.arcsin(EARTH_KM / distance))
    clearance = elevation - horizon_at(mask, az)
    centre = clearance > 0
    limb = clearance + radius > 0
    return dict(centre_count=int(centre.sum()), any_part_count=int(limb.sum()), n=len(earth),
                centre=float(centre.mean()), any_part=float(limb.mean()),
                definition_increase_pp=float((limb.astype(int) - centre).mean() * 100),
                angular_radius_min_deg=float(radius.min()), angular_radius_max_deg=float(radius.max()))


def read_truth(dataset, lat, lon, half_m):
    x, y = xy(lat, lon)
    row, col = dataset.index(float(x), float(y))
    if not 0 <= row < dataset.height or not 0 <= col < dataset.width:
        return None
    dn = dataset.read(1, window=Window(col, row, 1, 1))[0, 0]
    if dataset.nodata is not None and dn == dataset.nodata:
        raise ValueError("No-data PGDA pixel")
    scale = dataset.scales[0]
    if np.issubdtype(np.dtype(dataset.dtypes[0]), np.integer) and scale == 1:
        scale = 0.00004
    offset = dataset.offsets[0]
    # Match original window convention, including Python ties-to-even for 300/120.
    k = max(1, round(half_m / dataset.transform.a))
    r0, c0 = max(0, row - k), max(0, col - k)
    window = dataset.read(1, window=Window(c0, r0, min(dataset.width, col + k + 1) - c0,
                                          min(dataset.height, row + k + 1) - r0))
    values = window.astype(np.float64) * scale + offset
    value = float(dn * scale + offset)
    if not 0 <= value <= 1 or not np.all(np.isfinite(values)):
        raise ValueError("Invalid scaled PGDA values")
    return dict(value=value, minimum=float(values.min()), maximum=float(values.max()),
                row=int(row), col=int(col), raw_dn=int(dn), scale=float(scale), offset=float(offset), half_px=k)


def statistics(ours, truth, lo=None, hi=None):
    ours, truth = np.asarray(ours), np.asarray(truth)
    if ours.shape != truth.shape or not ours.size or not np.all(np.isfinite(ours + truth)):
        raise ValueError("Statistics need equal finite nonempty inputs")
    difference = 100 * (ours - truth)
    correlation = (float(np.corrcoef(ours, truth)[0, 1])
                   if np.std(ours) > 0 and np.std(truth) > 0 else None)
    result = dict(n=len(ours), mae_pp=float(np.mean(np.abs(difference))),
                  rmse_pp=float(np.sqrt(np.mean(difference ** 2))), bias_pp=float(difference.mean()),
                  r=correlation, median_abs_pp=float(np.median(np.abs(difference))),
                  max_abs_pp=float(np.max(np.abs(difference))))
    if lo is not None:
        result["within_pgda_neighborhood_pct"] = float(np.mean((ours >= lo) & (ours <= hi)) * 100)
    return result


def summarize(rows):
    truth = np.array([r["pgda"]["value"] for r in rows])
    lo, hi = (np.array([r["pgda"][key] for r in rows]) for key in ("minimum", "maximum"))
    centre, limb = (np.array([r[key] for r in rows]) for key in ("centre", "any_part"))
    a, b = statistics(centre, truth, lo, hi), statistics(limb, truth, lo, hi)
    baseline = dict(centre=statistics(np.round(centre, 5), np.round(truth, 5), np.round(lo, 5), np.round(hi, 5)),
                    any_part=statistics(np.round(limb, 5), np.round(truth, 5), np.round(lo, 5), np.round(hi, 5)))
    delta = (limb - centre) * 100
    improved = np.abs(limb - truth) < np.abs(centre - truth) - 1e-12
    worsened = np.abs(limb - truth) > np.abs(centre - truth) + 1e-12
    return dict(centre=a, any_part=b, rounded_like_original=baseline,
                mae_reduction_pp=a["mae_pp"] - b["mae_pp"],
                mae_reduction_pct=(a["mae_pp"] - b["mae_pp"]) / a["mae_pp"] * 100,
                definition_increase_mean_pp=float(delta.mean()), definition_increase_median_pp=float(np.median(delta)),
                definition_increase_max_pp=float(delta.max()), improved_points=int(improved.sum()),
                worsened_points=int(worsened.sum()), unchanged_points=int((~(improved | worsened)).sum()),
                negative_centre_residuals=int(np.sum(centre < truth)),
                negative_any_part_residuals=int(np.sum(limb < truth)),
                residual_above_0_1pp=[r["id"] for r in rows if abs(r["any_part"] - r["pgda"]["value"]) * 100 > .1],
                reproduction_above_0_1pp=[r["id"] for r in rows if abs(r["stored_any_delta_pp"]) > .1])


def run(args):
    CACHE.mkdir(parents=True, exist_ok=True)
    original_path = ROOT / "web/data/validation.json"
    original = json.loads(original_path.read_text(encoding="utf-8"))
    with np.load(args.ephem) as z:
        if str(z["start"]) != "2020-01-01T00:00:00Z" or int(z["step_h"]) != 2:
            raise ValueError("Wrong ephemeris interval")
        vector = z["vectors"]
        if vector.shape != (81444, 6):
            raise ValueError("Wrong full 18.6-year ephemeris shape")
        earth = vector[:, 3:].astype(np.float64)
        ephem_meta = {key: str(z[key]) for key in z.files if key != "vectors"}
    if original["n_points"] != 240 or len(original["points"]) != 240:
        raise ValueError("Expected all 240 validation points")
    inputs = {str(original_path): digest(original_path), str(args.ephem): digest(args.ephem),
              str(Path(__file__)): digest(__file__)}
    rasters = {res: fetch_truth(res) for res in TRUTH}
    inputs.update({str(path): digest(path) for path in rasters.values()})
    datasets = {res: rasterio.open(path) for res, path in rasters.items()}
    near, nmeta = fetch_dem(60, 220000)
    far, fmeta = fetch_dem(240, 520000)
    inputs.update({str(CACHE / f"dem{res}.npy"): meta["sha256"] for res, meta in ((60, nmeta), (240, fmeta))})
    distances = np.geomspace(.2, 300, 4001) * 1000
    cache_key = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    rows = []
    start = time.monotonic()
    for i, point in enumerate(original["points"]):
        key = f"P{i:03d}"
        mask_path = CACHE / "masks" / f"{key}.npz"
        mask_path.parent.mkdir(exist_ok=True)
        reuse = False
        if mask_path.exists():
            with np.load(mask_path) as z:
                reuse = str(z["cache_key"]) == cache_key
                if reuse:
                    mask, ground = z["mask"], float(z["ground"])
        if not reuse:
            mask, ground = reconstruct_mask(point["lat"], point["lon"], near, nmeta["x0"], nmeta["y0"],
                                            far, fmeta["x0"], fmeta["y0"], distances)
            np.savez(mask_path, mask=mask, ground=ground, lat=point["lat"], lon=point["lon"], cache_key=cache_key)
        result = earth_fractions(earth, point["lat"], point["lon"], ground, mask)
        pgda = read_truth(datasets[60], point["lat"], point["lon"], 60)
        rows.append(dict(id=key, lat=point["lat"], lon=point["lon"], h0_m=ground, mask_sha256=digest(mask_path),
                         pgda=pgda, stored_any=point["ours_earth"],
                         stored_any_delta_pp=100 * (result["any_part"] - point["ours_earth"]),
                         stored_pgda_delta_pp=100 * (pgda["value"] - point["pgda_earth"]), **result))
        if i % 10 == 0 or i == 239:
            print(f"{key}: {i + 1}/240, elapsed {time.monotonic() - start:.1f}s", flush=True)
            save_json(CACHE / "progress.json", dict(completed=i + 1, total=240, rows=rows))
    sites_path = ROOT / "web/data/sites.json"
    sites = {site["id"]: site for site in json.loads(sites_path.read_text(encoding="utf-8"))}
    inputs[str(sites_path)] = digest(sites_path)
    named = []
    for point in original["named"]:
        key = point["id"]
        site = sites[key]
        path = ROOT / "web/data/horizon" / (key + ".json")
        h = json.loads(path.read_text(encoding="utf-8"))
        if h["lat"] != site["lat"] or h["lon"] != site["lon"] or h["mock"]:
            raise ValueError("Named horizon coordinates/mock mismatch")
        inputs[str(path)] = digest(path)
        result = earth_fractions(earth, site["lat"], site["lon"], h["h0_m"], h["mask"], h["obs_height_m"])
        res = 60
        pgda = read_truth(datasets[60], site["lat"], site["lon"], 300)
        if pgda is None:
            res, pgda = 120, read_truth(datasets[120], site["lat"], site["lon"], 300)
        if pgda is None:
            raise ValueError("Named point outside PGDA")
        named.append(dict(id=key, lat=site["lat"], lon=site["lon"], h0_m=h["h0_m"], mask_sha256=digest(path),
                          pgda_resolution_m=res, pgda=pgda, stored_any=point["ours_earth"],
                          stored_any_delta_pp=100 * (result["any_part"] - point["ours_earth"]),
                          stored_pgda_delta_pp=100 * (pgda["value"] - point["pgda_earth"]), **result))
    result = dict(task="V", author="Jiyong Sung", complete=True, random_count=len(rows), named_count=len(named),
                  source_product="https://pgda.gsfc.nasa.gov/products/69", ephemeris=ephem_meta,
                  n_epochs=81444, interval="[2020-01-01T00:00Z, 2038-08-01T00:00Z)", step_h=2,
                  definition="Centre: elevation>mask; any-part approximation: elevation+asin(6371/topocentric_distance)>mask at centre azimuth",
                  mask_method="Independent 720-azimuth 4001-distance march, 0.2–300km; 60m to60km then240m; 2m observer; exact spherical curvature; no early stop",
                  random_summary=summarize(rows), named_summary=summarize(named),
                  original_alt_definitions=original["alt_definitions"],
                  input_sha256=inputs, dem_metadata=[nmeta, fmeta], rows=rows, named=named,
                  limits=["Original P*.npz masks unavailable: reconstructed same source/sampling and compare stored any-part fractions.",
                          "Any-part is vertical upper limb at centre azimuth, not a search over the whole disk against azimuth-varying terrain.",
                          "PGDA exact 18.6-year start/end dates and observer height not established; our 2h sampling differs from PGDA hourly.",
                          "Named masks authored by Jiyong: independent metric loop only; not independent validation of named terrain.",
                          "Reusing ephemeris validates metric integration, not an independent ephemeris generation.",
                          "Residual attribution to terrain, dates, observer height or discretisation has not been isolated."])
    save_json(ROOT / "docs/task_v_earth_definition.json", result)
    for ds in datasets.values():
        ds.close()
    print(json.dumps(result["random_summary"], indent=2), flush=True)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ephem", type=Path, required=True)
    run(ap.parse_args())
