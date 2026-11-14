"""Card 3 (C2b): fetch non-polar lunar terrain from PDS Geosciences.

1. Global LOLA GDR grids LDEM_16 (1.9 km/px, 66 MB) and LDEM_64 (474 m/px, 1.06 GB),
   downloaded whole with resume (.part file + HTTP Range).
2. For every non-polar site (lat > -80; card 2 covers lat <= -80) a +-150 km window of
   SLDEM2015 512 ppd (59 m/px) float tiles, fetched with HTTP Range requests for only the
   needed row segments, cached in resumable chunks and saved as data/raw/sldem/<ID>.npz.

Only the Python standard library and numpy are needed. Run from the repository root:
    python pipeline/fetch_global.py                 # everything
    python pipeline/fetch_global.py --skip-ldem64   # small run (LDEM_16 + site windows)
    python pipeline/fetch_global.py --site APOLLO17 --skip-global

Conventions (docs/data_contract.md): MOON_ME (DE421), lon -180..180 east-positive,
heights in metres above R = 1737.4 km. PDS files use 0..360 E and kilometres; both are
converted here. Raw data lives under data/raw/ (git-ignored) and is never committed.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

R_KM = 1737.4
PDS = 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/'
LDEM_DIR = PDS + 'lola_gdr/cylindrical/float_img/'
SLDEM_DIR = PDS + 'sldem2015/tiles/float_img/'
LDEM = {16: 'ldem_16_float', 64: 'ldem_64_float'}
SLDEM_PPD = 512
SLDEM_LAT_LIMIT = 60.0          # SLDEM2015 covers 60 S .. 60 N only
POLAR_LAT = -80.0               # card 2 (fetch_polar.py) handles lat <= -80
UA = {'User-Agent': 'Mozilla/5.0 (compatible; dem-fetch/1.0)', 'Accept-Encoding': 'identity'}
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
CHUNK = 1 << 20

PLACEHOLDERS = [
    dict(id='TEST_EQ_0_0', lat=0.0, lon=0.0, mock=True,
         note='Synthetic test point used only when web/data/sites.json is missing'),
]


# ----------------------------------------------------------------------------- HTTP

def _open(url, headers=None, timeout=120):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def _retry(fn, tries=6, what=''):
    for k in range(tries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code not in (429, 500, 502, 503, 504):
                raise
            if k == tries - 1:
                raise
            wait = 2 ** k
            print(f'  retry {k + 1}/{tries - 1} in {wait}s ({what}): {e}', flush=True)
            time.sleep(wait)


def probe(url):
    """Return (size, validator) using a 1-byte Range request; require 206 support."""
    def go():
        with _open(url, {'Range': 'bytes=0-0'}, timeout=60) as r:
            m = re.fullmatch(r'bytes 0-0/(\d+)', r.headers.get('Content-Range', ''))
            if r.status != 206 or not m:
                raise RuntimeError(f'Server ignored Range request for {url}')
            r.read()
            return int(m[1]), r.headers.get('ETag') or r.headers.get('Last-Modified') or ''
    return _retry(go, what=url)


def get_text(url):
    def go():
        with _open(url, timeout=60) as r:
            return r.read().decode('latin-1')
    return _retry(go, what=url)


def download(url, dest):
    """Download a whole file with resume. Returns bytes fetched in this run."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    size, validator = probe(url)
    if dest.exists() and dest.stat().st_size == size:
        print(f'  have {dest.name} ({size:,} B)')
        return 0
    part = dest.with_name(dest.name + '.part')
    stamp = dest.with_name(dest.name + '.part.json')
    if part.exists():
        old = json.loads(stamp.read_text()) if stamp.exists() else {}
        if old.get('validator') != validator or old.get('size') != size or part.stat().st_size > size:
            print('  remote file changed or stale partial file -> restarting')
            part.unlink()
    stamp.write_text(json.dumps({'url': url, 'size': size, 'validator': validator}))
    fetched = 0
    t0 = time.time()
    while True:
        have = part.stat().st_size if part.exists() else 0
        if have >= size:
            break
        try:
            with _open(url, {'Range': f'bytes={have}-'}, timeout=120) as r:
                if r.status != 206 or not r.headers.get('Content-Range', '').startswith(f'bytes {have}-'):
                    raise RuntimeError('Range resume rejected by server')
                with open(part, 'ab') as f:
                    while chunk := r.read(CHUNK):
                        f.write(chunk)
                        fetched += len(chunk)
                        done = have + fetched
                        if fetched % (64 * CHUNK) < CHUNK:
                            rate = fetched / max(time.time() - t0, 1e-3) / 1e6
                            print(f'  {dest.name}: {done / size:6.1%} ({rate:.1f} MB/s)', flush=True)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            print(f'  connection dropped ({e}); resuming in 5 s', flush=True)
            time.sleep(5)
            have = 0  # recomputed from the .part size at loop start
    if part.stat().st_size != size:
        raise RuntimeError(f'{dest.name}: size {part.stat().st_size} != {size}')
    os.replace(part, dest)
    stamp.unlink(missing_ok=True)
    print(f'  done {dest.name}: fetched {fetched:,} B this run')
    return fetched


def get_ranges(url, ranges, validator=None):
    """Fetch several byte ranges [(start, end_inclusive)] in one request.

    Handles single-part and multipart/byteranges answers, and servers that merge
    ranges. Returns a list of bytes objects in request order.
    """
    spec = 'bytes=' + ','.join(f'{a}-{b}' for a, b in ranges)

    def go():
        with _open(url, {'Range': spec}, timeout=180) as r:
            if r.status != 206:
                raise RuntimeError(f'Expected 206, got {r.status}')
            body = r.read()
            ctype = r.headers.get('Content-Type', '')
            if validator:
                got = r.headers.get('ETag') or r.headers.get('Last-Modified') or ''
                if got and got != validator:
                    raise RuntimeError(f'Remote file changed during fetch: {url}')
            if ctype.startswith('multipart/byteranges'):
                return parse_multipart(body, ctype)
            m = re.fullmatch(r'bytes (\d+)-(\d+)/\d+', r.headers.get('Content-Range', ''))
            if not m:
                raise RuntimeError('Missing Content-Range')
            return [(int(m[1]), body)]
    parts = _retry(go, what=f'{url} [{len(ranges)} ranges]')
    out = []
    for a, b in ranges:
        for start, data in parts:
            if start <= a and b < start + len(data):
                out.append(data[a - start:b - start + 1])
                break
        else:
            raise RuntimeError(f'Range {a}-{b} missing from server response')
    return out


def parse_multipart(body, ctype):
    m = re.search(r'boundary=("?)([^";]+)\1', ctype)
    if not m:
        raise RuntimeError('multipart response without boundary')
    sep = b'--' + m[2].encode()
    parts, pos = [], 0
    while True:
        i = body.find(sep, pos)
        if i < 0:
            break
        j = i + len(sep)
        if body[j:j + 2] == b'--':
            break
        h_end = body.find(b'\r\n\r\n', j)
        if h_end < 0:
            break
        headers = body[j:h_end].decode('latin-1')
        cr = re.search(r'Content-Range:\s*bytes (\d+)-(\d+)/\d+', headers, re.I)
        if not cr:
            raise RuntimeError('multipart part without Content-Range')
        a, b = int(cr[1]), int(cr[2])
        start = h_end + 4
        parts.append((a, body[start:start + b - a + 1]))
        pos = start + b - a + 1
    return parts


# ----------------------------------------------------------------------------- PDS labels

LABEL_KEYS = ['RECORD_BYTES', 'LINES', 'LINE_SAMPLES', 'SAMPLE_TYPE', 'SAMPLE_BITS', 'UNIT',
              'SCALING_FACTOR', 'OFFSET', 'MAP_PROJECTION_TYPE', 'MAP_RESOLUTION',
              'A_AXIS_RADIUS', 'POSITIVE_LONGITUDE_DIRECTION', 'CENTER_LONGITUDE',
              'MAXIMUM_LATITUDE', 'MINIMUM_LATITUDE', 'WESTERNMOST_LONGITUDE',
              'EASTERNMOST_LONGITUDE', 'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET',
              'COORDINATE_SYSTEM_NAME', 'PRODUCT_ID']


def parse_label(text):
    """Parse the PDS3 keywords we need (first occurrence of each; units dropped)."""
    out = {}
    for line in text.splitlines():
        m = re.match(r'^\s*([A-Z_]+)\s*=\s*(.+?)\s*$', line)
        if not m or m[1] not in LABEL_KEYS or m[1] in out:
            continue
        v = re.sub(r'<[^>]*>', '', m[2]).strip().strip('"').strip("'").strip()
        try:
            out[m[1]] = float(v) if re.fullmatch(r'[-+]?\d+\.?\d*([eE][-+]?\d+)?', v) else v
        except ValueError:
            out[m[1]] = v
    return out


class Grid:
    """Simple-cylindrical PDS grid; pixel (row r, col s) centre at
    lat = (LINE_PROJECTION_OFFSET - r) / res, lon = CENTER_LONGITUDE + (s - SAMPLE_PROJECTION_OFFSET) / res
    (0-based r, s; lon 0..360 E). Verified against the label's edge latitudes/longitudes."""

    def __init__(self, label):
        L = label if isinstance(label, dict) else parse_label(label)
        self.L = L
        need = ['LINES', 'LINE_SAMPLES', 'MAP_RESOLUTION', 'LINE_PROJECTION_OFFSET',
                'SAMPLE_PROJECTION_OFFSET', 'CENTER_LONGITUDE', 'OFFSET']
        miss = [k for k in need if k not in L]
        if miss:
            raise ValueError(f'label lacks {miss}')
        checks = {
            'SAMPLE_TYPE': 'PC_REAL', 'UNIT': 'KILOMETER',
            'MAP_PROJECTION_TYPE': 'SIMPLE CYLINDRICAL', 'POSITIVE_LONGITUDE_DIRECTION': 'EAST',
        }
        for k, v in checks.items():
            if str(L.get(k, v)).upper() != v:
                raise ValueError(f'{k} = {L.get(k)!r}, expected {v!r}')
        if L.get('SAMPLE_BITS', 32) != 32 or L.get('SCALING_FACTOR', 1) != 1:
            raise ValueError('unexpected sample bits or scaling factor')
        if abs(L['OFFSET'] - R_KM) > 1e-9 or abs(L.get('A_AXIS_RADIUS', R_KM) - R_KM) > 1e-9:
            raise ValueError(f'reference radius {L["OFFSET"]} km != {R_KM} km')
        if 'COORDINATE_SYSTEM_NAME' in L and 'DE421' not in L['COORDINATE_SYSTEM_NAME'].upper():
            raise ValueError(f'frame {L["COORDINATE_SYSTEM_NAME"]} is not ME/PA DE421')
        self.lines, self.samples = int(L['LINES']), int(L['LINE_SAMPLES'])
        self.res = float(L['MAP_RESOLUTION'])
        self.lpo, self.spo = float(L['LINE_PROJECTION_OFFSET']), float(L['SAMPLE_PROJECTION_OFFSET'])
        self.clon = float(L['CENTER_LONGITUDE'])
        self.row_bytes = self.samples * 4
        if 'RECORD_BYTES' in L and int(L['RECORD_BYTES']) != self.row_bytes:
            raise ValueError('RECORD_BYTES does not match LINE_SAMPLES * 4')
        h = 0.5 / self.res
        edges = {
            'MAXIMUM_LATITUDE': self.row_lat(0) + h,
            'MINIMUM_LATITUDE': self.row_lat(self.lines - 1) - h,
            'WESTERNMOST_LONGITUDE': self.col_lon(0) - h,
            'EASTERNMOST_LONGITUDE': self.col_lon(self.samples - 1) + h,
        }
        for k, v in edges.items():
            if k in L and abs(float(L[k]) - v) > 1e-6:
                raise ValueError(f'half-pixel check failed: {k} label {L[k]} vs grid {v}')
        self.north = self.row_lat(0) + h
        self.south = self.row_lat(self.lines - 1) - h
        self.west = self.col_lon(0) - h
        self.east = self.col_lon(self.samples - 1) + h

    def row_lat(self, r):
        return (self.lpo - np.asarray(r, dtype=float)) / self.res

    def col_lon(self, s):
        return self.clon + (np.asarray(s, dtype=float) - self.spo) / self.res

    def lat_to_row(self, lat):
        return self.lpo - np.asarray(lat, dtype=float) * self.res

    def lon_to_col(self, lon):
        return self.spo + (np.mod(np.asarray(lon, dtype=float), 360.0) - self.clon) * self.res


def lon180(lon):
    return (np.asarray(lon, dtype=float) + 180.0) % 360.0 - 180.0


class LdemFile:
    """Memory-mapped LDEM float image with bilinear sampling (heights in metres)."""

    def __init__(self, img, lbl):
        self.grid = Grid(Path(lbl).read_text(encoding='latin-1'))
        g = self.grid
        self.data = np.memmap(img, dtype='<f4', mode='r', shape=(g.lines, g.samples))

    def sample(self, lat, lon):
        g = self.grid
        r = np.clip(g.lat_to_row(lat), 0, g.lines - 1)
        c = g.lon_to_col(lon)
        r0 = np.clip(np.floor(r).astype(int), 0, g.lines - 2)
        fr = r - r0
        c0 = np.floor(c).astype(int)
        fc = c - c0
        c0m, c1m = c0 % g.samples, (c0 + 1) % g.samples   # longitude wraps
        d = self.data
        v = ((1 - fr) * ((1 - fc) * d[r0, c0m] + fc * d[r0, c1m])
             + fr * ((1 - fc) * d[r0 + 1, c0m] + fc * d[r0 + 1, c1m]))
        return v.astype(float) * 1000.0


# ----------------------------------------------------------------------------- sites

def load_sites(path, only=None):
    path = Path(path)
    if path.exists():
        sites = json.loads(path.read_text(encoding='utf-8'))
        src = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    else:
        print(f'WARNING: {path} not found; using synthetic placeholder points')
        sites, src = PLACEHOLDERS, 'placeholder'
    out = [s for s in sites if s['lat'] > POLAR_LAT and (only is None or s['id'] in only)]
    if only and len(out) != len(set(only)):
        missing = set(only) - {s['id'] for s in out}
        raise SystemExit(f'Unknown or polar site id(s): {sorted(missing)}')
    return out, src


def cap_extent(lat, radius_km):
    """Half-widths (deg) in lat and lon of a spherical cap of radius_km around lat."""
    a = radius_km / R_KM
    dlat = math.degrees(a)
    s = math.sin(a) / max(math.cos(math.radians(lat)), 1e-12)
    dlon = 180.0 if s >= 1 else math.degrees(math.asin(s))
    return dlat, dlon


# ----------------------------------------------------------------------------- SLDEM windows

TILE_RE = re.compile(r'sldem2015_512_(\d+)([ns])_(\d+)([ns])_(\d{3})_(\d{3})_float\.img', re.I)


def list_tiles(cache_dir):
    """Discover the 512 ppd float tiles from the PDS directory listing (cached)."""
    cache = Path(cache_dir) / 'tiles_index.json'
    if cache.exists():
        return json.loads(cache.read_text())
    html = get_text(SLDEM_DIR)
    tiles = []
    for name in sorted({m.group(0).lower() for m in TILE_RE.finditer(html)}):
        m = TILE_RE.fullmatch(name)
        la = [int(m[1]) * (1 if m[2] == 'n' else -1), int(m[3]) * (1 if m[4] == 'n' else -1)]
        tiles.append(dict(name=name[:-4], south=min(la), north=max(la),
                          west=int(m[5]), east=int(m[6])))
    if len(tiles) != 32:
        raise RuntimeError(f'expected 32 SLDEM2015 512 ppd tiles, found {len(tiles)}')
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(tiles, indent=1))
    return tiles


def tile_grid(tile, cache_dir):
    lbl = Path(cache_dir) / 'labels' / (tile['name'] + '.lbl')
    if not lbl.exists():
        lbl.parent.mkdir(parents=True, exist_ok=True)
        lbl.write_text(get_text(SLDEM_DIR + tile['name'] + '.lbl'), encoding='latin-1')
    g = Grid(lbl.read_text(encoding='latin-1'))
    if g.res != SLDEM_PPD:
        raise ValueError(f'{tile["name"]}: resolution {g.res} != {SLDEM_PPD}')
    if (round(g.south), round(g.north), round(g.west), round(g.east)) != \
            (tile['south'], tile['north'], tile['west'], tile['east']):
        raise ValueError(f'{tile["name"]}: label extent disagrees with file name')
    return g


def window_plan(lat, lon, radius_km, ppd=SLDEM_PPD):
    """Global pixel index ranges of the window on a ppd grid anchored at 90 N / 0 E.

    Row g centre: lat = 90 - (g + 0.5)/ppd. Column k centre: lon = (k + 0.5)/ppd, k may be
    negative or >= 360*ppd (unwrapped) so a window crossing 0/360 stays contiguous.
    """
    dlat, dlon = cap_extent(lat, radius_km)
    north = min(lat + dlat, SLDEM_LAT_LIMIT)
    south = max(lat - dlat, -SLDEM_LAT_LIMIT)
    lon360 = lon % 360.0
    g0 = int(math.floor((90.0 - north) * ppd))
    g1 = int(math.ceil((90.0 - south) * ppd))          # exclusive
    k0 = int(math.floor((lon360 - dlon) * ppd))
    k1 = int(math.ceil((lon360 + dlon) * ppd))         # exclusive
    clipped = (lat + dlat > SLDEM_LAT_LIMIT) or (lat - dlat < -SLDEM_LAT_LIMIT)
    return g0, g1, k0, k1, clipped


def tile_pieces(plan, tiles, grids, ppd=SLDEM_PPD):
    """Split the window into (tile, tile rows, tile cols, window rows, window cols) pieces."""
    g0, g1, k0, k1, _ = plan
    full = 360 * ppd
    pieces = []
    for t in tiles:
        grid = grids.get(t['name'])
        tg0 = int(round((90.0 - t['north']) * ppd))
        tk0 = int(round(t['west'] * ppd))
        if grid is not None:   # anchor check from the label itself
            assert abs((90.0 - float(grid.row_lat(0))) * ppd - 0.5 - tg0) < 1e-6
            assert abs(float(grid.col_lon(0)) * ppd - 0.5 - tk0) < 1e-6
        nrow = (t['north'] - t['south']) * ppd
        ncol = (t['east'] - t['west']) * ppd
        ra, rb = max(g0, tg0), min(g1, tg0 + nrow)
        if ra >= rb:
            continue
        for shift in (-full, 0, full):
            ca, cb = max(k0, tk0 + shift), min(k1, tk0 + shift + ncol)
            if ca < cb:
                pieces.append(dict(tile=t['name'],
                                   rows=(ra - tg0, rb - tg0), cols=(ca - tk0 - shift, cb - tk0 - shift),
                                   wrows=(ra - g0, rb - g0), wcols=(ca - k0, cb - k0)))
    return pieces


def fetch_piece_rows(url, row_bytes, r0, r1, c0, c1, validator, batch=128):
    """Return float32 array (r1-r0, c1-c0) in km for tile rows r0..r1, cols c0..c1."""
    if c0 == 0 and c1 * 4 == row_bytes:
        raw = get_ranges(url, [(r0 * row_bytes, r1 * row_bytes - 1)], validator)[0]
        return np.frombuffer(raw, dtype='<f4').reshape(r1 - r0, -1)
    out = np.empty((r1 - r0, c1 - c0), dtype='<f4')
    for b0 in range(r0, r1, batch):
        b1 = min(b0 + batch, r1)
        rng = [(r * row_bytes + c0 * 4, r * row_bytes + c1 * 4 - 1) for r in range(b0, b1)]
        for i, chunk in enumerate(get_ranges(url, rng, validator)):
            out[b0 - r0 + i] = np.frombuffer(chunk, dtype='<f4')
    return out


def fetch_site_window(site, radius_km, out_dir, workers=4, chunk_rows=256, sites_src=''):
    out_dir = Path(out_dir)
    dest = out_dir / f'{site["id"]}.npz'
    plan = window_plan(site['lat'], site['lon'], radius_km)
    g0, g1, k0, k1, clipped = plan
    if abs(site['lat']) >= SLDEM_LAT_LIMIT:
        print(f'  {site["id"]}: |lat| >= 60 -> outside SLDEM2015; use LDEM_64 in phase 2')
        return dict(id=site['id'], status='outside_sldem', fallback='LDEM_64')
    if dest.exists():
        with np.load(dest) as z:
            meta = json.loads(str(z['meta']))
        same = (meta.get('radius_km') == radius_km and meta.get('site_lat') == site['lat']
                and meta.get('site_lon') == site['lon'])
        if same:
            print(f'  have {dest.name}')
            return dict(id=site['id'], status='cached', path=dest.relative_to(ROOT).as_posix())
    tiles = list_tiles(out_dir)
    cand = tile_pieces(plan, tiles, {})
    grids = {p['tile']: tile_grid(next(t for t in tiles if t['name'] == p['tile']), out_dir)
             for p in cand}
    pieces = tile_pieces(plan, tiles, grids)
    validators = {}
    for name in grids:
        size, validators[name] = probe(SLDEM_DIR + name + '.img')
        if size != grids[name].lines * grids[name].row_bytes:
            raise RuntimeError(f'{name}: remote size {size} does not match label')

    parts_dir = out_dir / '_parts' / site['id']
    parts_dir.mkdir(parents=True, exist_ok=True)
    stamp = parts_dir / 'source.json'
    ident = {'validators': validators, 'plan': plan[:4]}
    if stamp.exists() and json.loads(stamp.read_text()) != json.loads(json.dumps(ident)):
        for f in parts_dir.glob('*.npy'):
            f.unlink()
    stamp.write_text(json.dumps(ident))

    jobs = []
    for p in pieces:
        for r in range(p['rows'][0], p['rows'][1], chunk_rows):
            jobs.append((p, r, min(r + chunk_rows, p['rows'][1])))
    fetched = [0]

    def job(j):
        p, ra, rb = j
        f = parts_dir / f'{p["tile"]}_r{ra}-{rb}_c{p["cols"][0]}-{p["cols"][1]}.npy'
        if f.exists():
            return
        g = grids[p['tile']]
        arr = fetch_piece_rows(SLDEM_DIR + p['tile'] + '.img', g.row_bytes, ra, rb,
                               p['cols'][0], p['cols'][1], validators[p['tile']])
        tmp = f.with_name(f.stem + '.tmp.npy')
        np.save(tmp, arr)
        os.replace(tmp, f)
        fetched[0] += arr.nbytes

    print(f'  {site["id"]}: {len(pieces)} tile piece(s), {len(jobs)} chunk(s), '
          f'{(g1 - g0)} x {(k1 - k0)} px')
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for n, _ in enumerate(ex.map(job, jobs), 1):
            if n % 5 == 0 or n == len(jobs):
                print(f'    {n}/{len(jobs)} chunks, {fetched[0] / 1e6:.0f} MB, '
                      f'{time.time() - t0:.0f} s', flush=True)

    h = np.full((g1 - g0, k1 - k0), np.nan, dtype=np.float32)
    for p, ra, rb in jobs:
        f = parts_dir / f'{p["tile"]}_r{ra}-{rb}_c{p["cols"][0]}-{p["cols"][1]}.npy'
        wr = p['wrows'][0] + (ra - p['rows'][0])
        h[wr:wr + rb - ra, p['wcols'][0]:p['wcols'][1]] = np.load(f) * 1000.0
    if np.isnan(h).any() or not np.isfinite(h).all():
        raise RuntimeError(f'{site["id"]}: window has {np.isnan(h).sum()} unfilled/invalid pixels')
    if not (-11000 < h.min() and h.max() < 11000):
        raise RuntimeError(f'{site["id"]}: heights out of lunar range {h.min()}..{h.max()} m')

    lat = 90.0 - (np.arange(g0, g1) + 0.5) / SLDEM_PPD
    lon_unwrapped = (np.arange(k0, k1) + 0.5) / SLDEM_PPD
    meta = dict(
        id=site['id'], site_lat=site['lat'], site_lon=site['lon'], radius_km=radius_km,
        dataset='SLDEM2015 512 ppd float (LOLA + SELENE TC)', res_ppd=SLDEM_PPD,
        res_m=round(2 * math.pi * R_KM * 1000 / 360 / SLDEM_PPD, 2),
        tiles=[SLDEM_DIR + n + '.img' for n in grids], validators=validators,
        units='m above 1737.4 km sphere', frame='MOON_ME_DE421',
        grid='pixel centres; rows north->south; lon_unwrapped monotonic (deg E, may exceed 0..360); '
             'lon = same in -180..180',
        clipped_at_60deg=clipped, sites_source=sites_src, site_is_mock=bool(site.get('mock')),
        bytes_fetched_this_run=fetched[0],
        created_utc=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        data_is_real='heights are real NASA PDS SLDEM2015 data; site coordinates may be mock')
    tmp = dest.with_name(dest.stem + '.tmp.npz')
    np.savez_compressed(tmp, height_m=h, lat=lat, lon=lon180(lon_unwrapped),
                        lon_unwrapped=lon_unwrapped, meta=json.dumps(meta))
    os.replace(tmp, dest)
    print(f'  saved {dest.relative_to(ROOT)}: {h.shape}, {h.min():.0f}..{h.max():.0f} m, '
          f'fetched {fetched[0] / 1e6:.1f} MB this run')
    return dict(id=site['id'], status='ok', path=dest.relative_to(ROOT).as_posix(),
                shape=list(h.shape), clipped_at_60deg=clipped, bytes=fetched[0])


def sample_window(npz, lat, lon):
    """Bilinear height (m) from a saved SLDEM window."""
    with np.load(npz) as z:
        h, la, lu = z['height_m'], z['lat'], z['lon_unwrapped']
    res = 1.0 / (la[0] - la[1])
    r = (la[0] - np.asarray(lat, float)) * res
    lon = np.asarray(lon, float) % 360.0
    lon = np.where(lon < lu[0] - 180, lon + 360, np.where(lon > lu[0] + 180, lon - 360, lon))
    c = (lon - lu[0]) * res
    if np.any(r < 0) or np.any(r > h.shape[0] - 1) or np.any(c < 0) or np.any(c > h.shape[1] - 1):
        raise ValueError('point outside the window')
    r0 = np.minimum(np.floor(r).astype(int), h.shape[0] - 2)
    c0 = np.minimum(np.floor(c).astype(int), h.shape[1] - 2)
    fr, fc = r - r0, c - c0
    return ((1 - fr) * ((1 - fc) * h[r0, c0] + fc * h[r0, c0 + 1])
            + fr * ((1 - fc) * h[r0 + 1, c0] + fc * h[r0 + 1, c0 + 1])).astype(float)


# ----------------------------------------------------------------------------- main

def fetch_global_grids(ppds, out_dir):
    total = 0
    for ppd in ppds:
        base = LDEM[ppd]
        for ext in ('.lbl', '.img'):
            total += download(LDEM_DIR + base + ext, Path(out_dir) / (base + ext))
        g = Grid((Path(out_dir) / (base + '.lbl')).read_text(encoding='latin-1'))
        size = (Path(out_dir) / (base + '.img')).stat().st_size
        if size != g.lines * g.row_bytes:
            raise RuntimeError(f'{base}.img size {size} != label {g.lines * g.row_bytes}')
        print(f'  {base}: {g.lines} x {g.samples}, {g.res:g} ppd, label checks OK')
    return total


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--sites', default=str(ROOT / 'web' / 'data' / 'sites.json'))
    p.add_argument('--site', action='append', help='only this site id (repeatable)')
    p.add_argument('--radius-km', type=float, default=150.0)
    p.add_argument('--workers', type=int, default=4, help='parallel HTTP requests')
    p.add_argument('--skip-global', action='store_true', help='do not download LDEM_16/64')
    p.add_argument('--skip-ldem64', action='store_true', help='download LDEM_16 only')
    p.add_argument('--skip-sites', action='store_true', help='do not fetch SLDEM windows')
    a = p.parse_args(argv)

    report = dict(created_utc=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    if not a.skip_global:
        ppds = [16] if a.skip_ldem64 else [16, 64]
        print(f'Global LOLA grids {ppds} ppd -> data/raw/global/')
        report['global_bytes'] = fetch_global_grids(ppds, RAW / 'global')
    if not a.skip_sites:
        sites, src = load_sites(a.sites, a.site)
        print(f'SLDEM2015 windows (+-{a.radius_km:g} km) for {len(sites)} non-polar site(s) from {src}')
        report['sites'] = [fetch_site_window(s, a.radius_km, RAW / 'sldem', a.workers, sites_src=src)
                           for s in sites]
    man = RAW / 'global_manifest.json'
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps(report, indent=1))
    print(f'Manifest: {man.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
