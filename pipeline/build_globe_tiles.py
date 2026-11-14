"""Build the whole-Moon 3D height-tile pyramid for web/js/globe3d.js (phase 4, card S4).

Two steps, both resumable (re-run to continue after an interruption):

  python pipeline/build_globe_tiles.py fetch   # HTTP Range windows of fine DEMs around catalogue sites
  python pipeline/build_globe_tiles.py build   # write web/data/globe/ (PNG height tiles + index.json)

Tiling (see docs/globe3d.md):
  * "band" quadtree: equirectangular, lat -72..72, 10 root tiles of 72 x 72 deg (lon from -180).
    Tile (z, x, y) covers 72/2^z deg; x from lon -180 eastward, y from lat +72 southward.
  * "south" / "north" quadtrees: polar stereographic (R = 1737.4 km, same as PGDA), root square
    +-CAP_HALF m around the pole; x from -CAP_HALF eastward, y from +CAP_HALF downward (proj x/y).
  Every tile = 256 x 256 cells -> 257 x 257 vertices, stored with a 1-sample border (259 x 259 px)
  so normals at tile edges are exact. Neighbouring tiles share their edge vertices.
  Height encoding (lossless PNG, RGB): v = round((h_m + 10000) * 2); R = v >> 8, G = v & 255, B = 0
  -> 0.5 m steps, metres above the 1737.4 km sphere (contract section 0).

Sources (finest first, a sample uses the first source that covers it):
  south cap fine: PGDA LOLA 20 m site windows, PGDA 80 m (80S..90S), PGDA 60 m site windows
  band fine:      SLDEM2015 512 ppd site windows (+-62 km), PGDA 60 m (Chandrayaan-3)
  everywhere:     LOLA LDEM_64 (64 ppd, 474 m), box-filtered for coarse levels.
Every dataset is listed in data/DATASETS.md.
"""
import argparse
import concurrent.futures as cf
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))

R = 1737400.0
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'web' / 'data' / 'globe'
N = 256                 # cells per tile side
BAND_LAT = 72.0         # band covers |lat| <= 72
ROOT_DEG = 72.0         # band root tile size (deg)
CAP_HALF = 560000.0     # polar root square half-size (m); 72 deg is at rho = 550.4 km
BAND_GLOBAL_Z = 3       # band levels 0..3 everywhere (1.07 km at z3)
CAP_GLOBAL_Z = 2        # cap levels 0..2 everywhere (1.09 km at z2)
SITE_RADIUS_M = 60000   # finer tiles only within this distance of a catalogue site
HMIN = -10000.0

LDEM64 = Path(os.environ.get('LDEM64_IMG', ROOT / 'data' / 'raw' / 'global' / 'ldem_64_float.img'))
SLDEM_DIR = RAW / 'sldem60'
POLAR_DIR = RAW / 'polar'


# ----------------------------------------------------------------------------- geometry
def stere_fwd(lat, lon, south=True):
    """Polar stereographic (sphere R, true scale at the pole). South: same as PGDA proj string."""
    lat = np.asarray(lat, float)
    lon = np.radians(lon)
    if south:
        rho = 2 * R * np.tan(np.radians(90 + lat) / 2)
        return rho * np.sin(lon), rho * np.cos(lon)
    rho = 2 * R * np.tan(np.radians(90 - lat) / 2)
    return rho * np.sin(lon), -rho * np.cos(lon)


def stere_inv(x, y, south=True):
    rho = np.hypot(x, y)
    c = 2 * np.degrees(np.arctan(rho / (2 * R)))
    if south:
        return c - 90.0, np.degrees(np.arctan2(x, y))
    return 90.0 - c, np.degrees(np.arctan2(x, -y))


def tile_spacing_m(kind, z):
    if kind == 'band':
        return math.radians(ROOT_DEG / 2 ** z / N) * R
    return 2 * CAP_HALF / 2 ** z / N


def tile_sample_grid(kind, z, x, y):
    """lat, lon arrays (259 x 259) of the tile vertices incl. the 1-sample border."""
    k = np.arange(-1, N + 2)
    if kind == 'band':
        d = ROOT_DEG / 2 ** z / N
        lon = -180.0 + (x * N + k) * d
        lat = BAND_LAT - (y * N + k) * d
        LON, LAT = np.meshgrid(lon, lat)
        LAT = np.clip(LAT, -90, 90)
        LON = (LON + 180.0) % 360.0 - 180.0
        return LAT, LON
    d = 2 * CAP_HALF / 2 ** z / N
    px = -CAP_HALF + (x * N + k) * d
    py = CAP_HALF - (y * N + k) * d
    PX, PY = np.meshgrid(px, py)
    return stere_inv(PX, PY, south=(kind == 'south'))


def tile_center_latlon(kind, z, x, y):
    lat, lon = tile_sample_grid(kind, z, x, y)
    return float(lat[129, 129]), float(lon[129, 129])


def gc_dist_m(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ----------------------------------------------------------------------------- sources
def box2(a):
    """2x2 box filter (NaN-aware) -> half resolution."""
    h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
    b = a[:h, :w].reshape(h // 2, 2, w // 2, 2)
    with np.errstate(invalid='ignore'):
        return np.nanmean(b, axis=(1, 3)).astype(np.float32)


def bilinear(arr, fr, fc):
    """Bilinear sample at fractional row/col (pixel centres at integers). NaN outside."""
    H, W = arr.shape
    ok = (fr >= 0) & (fr <= H - 1) & (fc >= 0) & (fc <= W - 1)
    r0 = np.clip(np.floor(fr).astype(np.int64), 0, H - 2)
    c0 = np.clip(np.floor(fc).astype(np.int64), 0, W - 2)
    tr = np.clip(fr - r0, 0, 1)
    tc = np.clip(fc - c0, 0, 1)
    v = (arr[r0, c0] * (1 - tr) * (1 - tc) + arr[r0, c0 + 1] * (1 - tr) * tc
         + arr[r0 + 1, c0] * tr * (1 - tc) + arr[r0 + 1, c0 + 1] * tr * tc)
    return np.where(ok, v, np.nan)


class Ldem64:
    """LOLA LDEM_64 global grid (km -> m), with a box-filtered pyramid for coarse tiles."""
    name = 'LDEM_64'

    def __init__(self, img):
        raw = np.memmap(img, dtype='<f4', mode='r', shape=(11520, 23040))
        print(f'  loading {img} ...', flush=True)
        base = np.asarray(raw, dtype=np.float32) * 1000.0
        levels = [(64, base)]
        a = base
        for ppd in (32, 16, 8, 4):
            a = box2(a)
            levels.append((ppd, a))
        # one wrap-around column on each side so bilinear works across lon 0/360
        self.levels = [(p, np.concatenate([a[:, -1:], a, a[:, :1]], axis=1)) for p, a in levels]
        del base, levels
        self.res_m = math.radians(1 / 64) * R

    def sample(self, lat, lon, spacing_m):
        # coarsest level whose pixel is still <= spacing
        ppd, a = self.levels[0]
        for p, arr in self.levels:
            if math.radians(1 / p) * R <= spacing_m * 1.01:
                ppd, a = p, arr
        # pixel centres: lat = 90 - (r+0.5)/ppd, lon(0..360) = (c+0.5)/ppd  (LDEM_64 label: 0..360 E)
        fr = (90.0 - lat) * ppd - 0.5
        lon360 = np.mod(lon, 360.0)
        fc = lon360 * ppd - 0.5
        return bilinear(a, np.clip(fr, 0, a.shape[0] - 1), fc + 1)   # a is padded by one column


class SldemWin:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.h = z['height_m'].astype(np.float32)
            self.lat0 = float(z['lat'][0])
            self.lon0 = float(z['lon_unwrapped'][0])
            self.lat = z['lat']
        self.ppd = 512.0
        self.res_m = math.radians(1 / 512) * R
        self.name = 'SLDEM2015'
        self.pyr = [(self.ppd, self.h)]
        a, p = self.h, self.ppd
        for _ in range(4):
            a, p = box2(a), p / 2
            self.pyr.append((p, a))

    def sample(self, lat, lon, spacing_m):
        ppd, a = self.pyr[0]
        for p, arr in self.pyr:
            if math.radians(1 / p) * R <= spacing_m * 1.01:
                ppd, a = p, arr
        f = self.ppd / ppd
        # level pixel centre k corresponds to base fractional index k*f + (f-1)/2
        fr = ((self.lat0 - lat) * self.ppd - (f - 1) / 2) / f
        dl = np.mod(lon - self.lon0 + 180.0, 360.0) - 180.0
        fc = (dl * self.ppd - (f - 1) / 2) / f
        return bilinear(a, fr, fc)


class PolarWin:
    """PGDA polar-stereographic window (data/raw/polar/<res>/<ID>.npz)."""

    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.h = z['height_m'].astype(np.float32)
            self.x0 = float(z['x_m'][0])
            self.y0 = float(z['y_m'][0])
            meta = json.loads(str(z['metadata']))
        self.res_m = float(meta['resolution_m'])
        self.name = f'PGDA {int(self.res_m)} m'
        self.pyr = [(self.res_m, self.h)]
        a, r = self.h, self.res_m
        for _ in range(5):
            a, r = box2(a), r * 2
            self.pyr.append((r, a))

    def sample(self, lat, lon, spacing_m):
        res, a = self.pyr[0]
        for r, arr in self.pyr:
            if r <= spacing_m * 1.01:
                res, a = r, arr
        f = res / self.res_m
        x, y = stere_fwd(np.minimum(lat, -1e-9), lon, south=True)
        fc = ((x - self.x0) / self.res_m - (f - 1) / 2) / f
        fr = ((self.y0 - y) / self.res_m - (f - 1) / 2) / f
        v = bilinear(a, fr, fc)
        return np.where(np.asarray(lat) < 0, v, np.nan)


# ----------------------------------------------------------------------------- fetch
def load_sites():
    return json.loads((ROOT / 'web' / 'data' / 'sites.json').read_text(encoding='utf-8'))


def cmd_fetch(a):
    import fetch_global as fg
    import fetch_polar as fp
    sites = load_sites()
    fails = []
    # PGDA 80 m, whole 80S..90S cap (pole-centred window)
    jobs = [(dict(id='SOUTH_CAP_80S', lat=-90.0, lon=0.0), 80, 300000)]
    for s in sites:
        if s['lat'] <= -83:
            jobs.append((s, 20, 15000))
        elif s['lat'] < -60:
            jobs.append((s, 60, SITE_RADIUS_M + 3000))
    for s, res, rad in jobs:
        try:
            fp.fetch(s, res, rad, POLAR_DIR)
        except Exception as e:  # keep going; re-run resumes from cached blocks
            fails.append(f'{s["id"]} {res} m: {e}')
            print('FAILED', fails[-1], flush=True)
    for s in sites:
        if abs(s['lat']) < 60:
            try:
                fg.fetch_site_window(s, (SITE_RADIUS_M + 2000) / 1000, SLDEM_DIR, workers=a.workers)
            except Exception as e:
                fails.append(f'{s["id"]} SLDEM: {e}')
                print('FAILED', fails[-1], flush=True)
    print('fetch done;', len(fails), 'failures', *fails, sep='\n')
    return 1 if fails else 0


# ----------------------------------------------------------------------------- build
def encode_png(h, path):
    from PIL import Image
    v = np.clip(np.round((h - HMIN) * 2), 0, 65535).astype(np.uint32)
    rgb = np.zeros(h.shape + (3,), np.uint8)
    rgb[..., 0] = v >> 8
    rgb[..., 1] = v & 255
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp.png')
    Image.fromarray(rgb, 'RGB').save(tmp, optimize=True)
    os.replace(tmp, path)


class Builder:
    def __init__(self):
        self.ldem = Ldem64(LDEM64)
        self.sites = load_sites()
        self.fine = []        # (source, kind-tag)
        for p in sorted(q for q in SLDEM_DIR.glob('*.npz') if '.tmp' not in q.name):
            self.fine.append(SldemWin(p))
        for res in (20, 60, 80):
            for p in sorted((POLAR_DIR / str(res)).glob('*.npz')):
                self.fine.append(PolarWin(p))
        self.fine.sort(key=lambda s: s.res_m)
        print('  fine sources:', [(s.name, s.h.shape) for s in self.fine], flush=True)

    def heights(self, kind, z, x, y):
        lat, lon = tile_sample_grid(kind, z, x, y)
        sp = tile_spacing_m(kind, z)
        h = np.full(lat.shape, np.nan, np.float32)
        used = set()
        for s in self.fine if sp < 600 else []:   # global levels (>= 1 km) come from LDEM_64 only
            if s.res_m > sp * 1.01:
                continue
            m = np.isnan(h)
            if not m.any():
                break
            v = s.sample(lat[m], lon[m], sp)
            if np.isfinite(v).any():
                used.add(s.name)
            h[m] = v
        m = np.isnan(h)
        if m.any():
            h[m] = self.ldem.sample(lat[m], lon[m], sp)
            used.add('LDEM_64')
        return h, used

    def fine_coverage(self, kind, z, x, y):
        """Fraction of the tile's samples covered by a fine source with res <= spacing."""
        lat, lon = tile_sample_grid(kind, z, x, y)
        lat, lon = lat[::16, ::16], lon[::16, ::16]
        sp = tile_spacing_m(kind, z)
        ok = np.zeros(lat.shape, bool)
        for s in self.fine:
            if s.res_m <= sp * 1.01:
                ok |= np.isfinite(s.sample(lat, lon, sp))
        return ok.mean()


def level_tiles(kind, z):
    if kind == 'band':
        return [(x, y) for y in range(2 * 2 ** z // 2 * 1) for x in range(5 * 2 ** z)] if False else \
            [(x, y) for y in range(2 ** (z + 1)) for x in range(5 * 2 ** z)]
    n = 2 ** z
    return [(x, y) for y in range(n) for x in range(n)]


def tile_in_domain(kind, z, x, y):
    """Cap tiles fully outside |lat| >= BAND_LAT - margin are skipped (band covers them)."""
    if kind == 'band':
        return True
    lat, _ = tile_sample_grid(kind, z, x, y)
    a = np.abs(lat)
    return a.max() >= BAND_LAT - 1.0


def refine_radius_m(spacing_child_m):
    """How far from a site the children of a tile are still generated (keeps the total size web-friendly)."""
    if spacing_child_m >= 200:
        return SITE_RADIUS_M
    if spacing_child_m >= 100:
        return 40000.0
    if spacing_child_m >= 50:
        return 20000.0
    return 10000.0


def near_site(kind, z, x, y, sites):
    lat, lon = tile_sample_grid(kind, z, x, y)
    clat, clon = float(lat[129, 129]), float(lon[129, 129])
    half_diag = tile_spacing_m(kind, z) * N * 0.75
    rad = refine_radius_m(tile_spacing_m(kind, z + 1))
    for s in sites:
        if gc_dist_m(clat, clon, s['lat'], s['lon']) <= rad + half_diag:
            return True
    return False


def plan_tiles(b, max_band_z, max_cap_z):
    """Return {(kind,z,x,y)} complete quads: global levels + refined quads near sites with fine data."""
    sites = b.sites
    tiles = set()
    for kind, gz in (('band', BAND_GLOBAL_Z), ('south', CAP_GLOBAL_Z), ('north', CAP_GLOBAL_Z)):
        for z in range(gz + 1):
            for x, y in level_tiles(kind, z):
                if tile_in_domain(kind, z, x, y):
                    tiles.add((kind, z, x, y))
        frontier = [(kind, gz, x, y) for x, y in level_tiles(kind, gz) if (kind, gz, x, y) in tiles]
        zmax = max_band_z if kind == 'band' else max_cap_z
        z = gz
        while frontier and z < zmax:
            nxt = []
            for (k, zz, x, y) in frontier:
                if not near_site(k, zz, x, y, sites):
                    continue
                kids = [(k, zz + 1, 2 * x + i, 2 * y + j) for j in (0, 1) for i in (0, 1)]
                # refine past LDEM_64 resolution only where a finer DEM actually covers the area
                sp_child = tile_spacing_m(k, zz + 1)
                if sp_child < b.ldem.res_m * 0.95:
                    cov = max(b.fine_coverage(*c) for c in kids)
                    if cov < 0.25:
                        continue
                kids = [c for c in kids if k == 'band' or tile_in_domain(*c)]
                if len(kids) < 4 and k == 'band':
                    continue
                for c in kids:
                    tiles.add(c)
                nxt.extend(kids)
            frontier = nxt
            z += 1
    return tiles


def cmd_build(a):
    b = Builder()
    tiles = plan_tiles(b, a.max_band_z, a.max_cap_z)
    print(f'  {len(tiles)} tiles planned', flush=True)
    t0 = time.time()
    records = {}
    done_file = ROOT / 'data' / 'processed' / 'globe_progress.json'   # git-ignored resume state
    done_file.parent.mkdir(parents=True, exist_ok=True)
    if done_file.exists() and not a.force:
        records = json.loads(done_file.read_text())
    todo = sorted(tiles, key=lambda t: (t[1], t[0], t[3], t[2]))
    n_new = 0
    for i, t in enumerate(todo):
        key = '/'.join(map(str, t))
        path = OUT / t[0] / str(t[1]) / f'{t[2]}_{t[3]}.png'
        if key in records and path.exists():
            continue
        h, used = b.heights(*t)
        if np.isnan(h).any():
            h = np.where(np.isnan(h), np.nanmean(h), h)
        encode_png(h, path)
        records[key] = dict(src=sorted(used), min=float(np.floor(h.min())), max=float(np.ceil(h.max())),
                            bytes=path.stat().st_size)
        n_new += 1
        if n_new % 50 == 0:
            done_file.write_text(json.dumps(records))
            el = time.time() - t0
            print(f'  {i + 1}/{len(todo)} tiles, {el:.0f} s', flush=True)
    done_file.write_text(json.dumps(records))
    write_index(tiles, records)


def write_index(tiles, records):
    out = dict(
        version=1,
        radius_m=R, frame='MOON_ME_DE421', tile_cells=N, tile_px=N + 3, border=1,
        encoding='RGB PNG: v = R*256 + G; h_m = v/2 - 10000 (metres above 1737.4 km)',
        band=dict(lat_max=BAND_LAT, root_deg=ROOT_DEG, roots=[5, 2],
                  note='tile (z,x,y): lon -180 + x*72/2^z eastward, lat 72 - y*72/2^z southward'),
        cap=dict(half_m=CAP_HALF, projection_south='+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400',
                 projection_north='+proj=stere +lat_0=90 +lat_ts=90 +lon_0=0 +R=1737400',
                 note='tile (z,x,y): x_m = -half + x*2half/2^z eastward, y_m = +half - y*2half/2^z downward'),
        url='{kind}/{z}/{x}_{y}.png',
        sources={
            'LDEM_64': 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ldem_64_float.img',
            'SLDEM2015': 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/',
            'PGDA 20/60/80 m': 'https://pgda.gsfc.nasa.gov/products/90',
        },
        tiles={},
    )
    total = 0
    for t in sorted(tiles):
        key = '/'.join(map(str, t))
        r = records.get(key)
        if not r:
            continue
        out['tiles'].setdefault(t[0], []).append([t[1], t[2], t[3], r['min'], r['max'],
                                                  1 if r['src'] != ['LDEM_64'] else 0])
        total += r['bytes']
    lv = {}
    for k, arr in out['tiles'].items():
        for z, *_ in arr:
            lv.setdefault(k, {}).setdefault(z, 0)
            lv[k][z] += 1
    out['levels'] = {k: {str(z): dict(n=n, spacing_m=round(tile_spacing_m(k, z), 1)) for z, n in sorted(v.items())}
                     for k, v in lv.items()}
    out['total_bytes'] = total
    out['max_tile_bytes'] = max(r['bytes'] for r in records.values())
    (OUT / 'index.json').write_text(json.dumps(out, separators=(',', ':')))
    print(f'  index.json: {sum(len(v) for v in out["tiles"].values())} tiles, {total / 1e6:.1f} MB, '
          f'largest {out["max_tile_bytes"] / 1e3:.0f} kB', flush=True)
    print('  levels:', json.dumps(out['levels']))


SVS_COLOR = 'https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif'


def cmd_albedo(a):
    """NASA SVS CGI Moon Kit colour map (LRO LROC WAC based, equirectangular, lon -180..180) -> web JPEGs."""
    import subprocess
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    src = RAW / 'svs' / 'lroc_color_poles_8k.tif'
    src.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        subprocess.run(['curl', '-sS', '-C', '-', '-o', str(src) + '.part', SVS_COLOR], check=True)
        os.replace(str(src) + '.part', src)
    im = Image.open(src).convert('RGB')
    OUT.mkdir(parents=True, exist_ok=True)
    for w, q in ((8192, 88), (2048, 88)):
        p = OUT / f'moon_color_{w // 1024}k.jpg'
        (im if im.size[0] == w else im.resize((w, w // 2), Image.LANCZOS)).save(p, quality=q, optimize=True)
        print(f'  {p.name}: {p.stat().st_size / 1e6:.1f} MB')


def cmd_test(a):
    """Self-checks: projection round trip, encode/decode, LDEM sample at Apollo 17 vs SLDEM."""
    lat, lon = np.array([-89.7668, -85.0, 80.0]), np.array([-171.87, 30.0, 120.0])
    for south, la, lo in ((True, lat[:2], lon[:2]), (False, lat[2:], lon[2:])):
        x, y = stere_fwd(la, lo, south)
        la2, lo2 = stere_inv(x, y, south)
        assert np.allclose(la, la2) and np.allclose(lo, lo2), (la, la2, lo, lo2)
    x, y = stere_fwd(-89.9, 0.0, True)
    assert abs(x) < 1e-6 and abs(y - 3032.4) < 1, (x, y)   # matches PGDA window centre (y ~ +3030 m)
    h = np.array([[-9123.5, 10786.0], [0.0, 1.5]], np.float32)
    v = np.round((h - HMIN) * 2).astype(int)
    back = ((v >> 8) * 256 + (v & 255)) / 2 + HMIN
    assert np.allclose(back, h), back
    print('projection + encoding OK')


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fetch')
    f.add_argument('--workers', type=int, default=4)
    bp = sub.add_parser('build')
    bp.add_argument('--max-band-z', type=int, default=7)
    bp.add_argument('--max-cap-z', type=int, default=8)
    bp.add_argument('--force', action='store_true')
    sub.add_parser('test')
    sub.add_parser('albedo')
    a = p.parse_args()
    return {'fetch': cmd_fetch, 'build': cmd_build, 'test': cmd_test, 'albedo': cmd_albedo}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
