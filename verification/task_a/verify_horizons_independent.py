"""Independent task A: original DEM bytes -> all 33 x 720 rays -> hourly sunlight.

No imports from pipeline/ or web/js/. Only NumPy, tifffile and requests are used.
Run with --prepare-global first; --run resumes per-source and per-site checkpoints.
Raw files and checkpoints are not submitted as production data.
"""
import argparse
import concurrent.futures
import email.parser
import email.policy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import numpy as np
import requests
import tifffile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(os.environ.get('LLSN_VERIFICATION_ROOT', Path(__file__).resolve().parent)).resolve()
INPUT = ROOT/'input_commit.txt'
if not INPUT.exists(): INPUT = Path(__file__).with_name('input_commit.txt')
RAW = ROOT / 'data/raw/independent_a'
OUT = ROOT / 'data/processed/task_a'
R = 1737400.0
PDS = 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/'
POLAR = {
    5: 'LOLA_5mpp/87S/ldem_87s_5mpp.tif',
    10: 'LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF',
    20: 'LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF',
    60: 'LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF',
    80: 'LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF',
    240: 'LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.part')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


class SourceSession(requests.Session):
    def send(self, request, **kwargs):
        host = urlsplit(request.url).hostname
        if host not in {'pds-geosciences.wustl.edu','pgda.gsfc.nasa.gov'}:
            raise ValueError('Blocked non-source network destination: '+str(host))
        for attempt in range(3):
            response=super().send(request, **kwargs)
            if response.status_code!=403 or host!='pgda.gsfc.nasa.gov' or attempt==2:
                return response
            # The canonical public product was independently observed returning
            # 206; allow two bounded retries for transient provider responses.
            retry_after=response.headers.get('Retry-After')
            if retry_after and (not retry_after.isdigit() or int(retry_after)>10):
                return response
            delay=int(retry_after) if retry_after else 2*(attempt+1)
            response.close()
            time.sleep(delay)


def session():
    s = SourceSession()
    s.headers.update({'Accept-Encoding': 'identity'})
    s.mount('https://', HTTPAdapter(max_retries=Retry(total=5, backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504])))
    return s


HTTP = session()


def text(url):
    r = HTTP.get(url, timeout=(20, 120))
    r.raise_for_status()
    return r.content.decode('latin-1')


def download(url, target):
    """Sequential 8 MiB source ranges with validator-pinned resume."""
    target.parent.mkdir(parents=True, exist_ok=True)
    own = session()
    with own.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=(20, 120)) as r:
        r.raise_for_status()
        m = re.fullmatch(r'bytes 0-0/(\d+)', r.headers.get('Content-Range', ''))
        if r.status_code != 206 or not m:
            raise ValueError('Source does not honor ranges: ' + url)
        meta = {'url': url, 'size': int(m[1]), 'etag': r.headers.get('ETag'),
                'last_modified': r.headers.get('Last-Modified')}
    identity = target.with_suffix(target.suffix + '.source.json')
    if identity.exists() and json.loads(identity.read_text()) != meta:
        raise ValueError('Source identity changed; refusing old resume: ' + url)
    atomic(identity, meta)
    part = target.with_suffix(target.suffix + '.part')
    if target.exists():
        if target.stat().st_size != meta['size']:
            raise ValueError('Wrong completed download length')
        return
    size = part.stat().st_size if part.exists() else 0
    while size < meta['size']:
        end = min(meta['size'], size + 8 * 1024**2) - 1
        with own.get(url+f'?range={size}-{end}', headers={'Range': f'bytes={size}-{end}'}, stream=True,
                     timeout=(20, 180)) as r:
            r.raise_for_status()
            if r.status_code != 206 or r.headers.get('Content-Range') != f'bytes {size}-{end}/{meta["size"]}':
                raise ValueError('Invalid content range')
            if meta['etag'] and r.headers.get('ETag') != meta['etag']:
                raise ValueError('ETag changed during download')
            payload = r.content
        if len(payload) != end - size + 1:
            raise ValueError('Truncated download')
        with part.open('ab') as f:
            f.write(payload)
        size += len(payload)
        print(target.name, size, '/', meta['size'], flush=True)
    part.replace(target)


def label(txt):
    out = {}
    for line in txt.splitlines():
        m = re.match(r'^\s*([A-Z_]+)\s*=\s*(.*?)\s*$', line)
        if m and m[1] not in out:
            v = m[2].split('<')[0].strip().strip('"')
            try:
                v = float(v)
            except ValueError:
                pass
            out[m[1]] = v
    return out


def bilinear(a, y, x, wrap=False):
    y, x = np.asarray(y, float), np.asarray(x, float)
    valid = np.isfinite(y) & np.isfinite(x) & (y >= 0) & (y <= a.shape[0] - 1)
    if not wrap:
        valid &= (x >= 0) & (x <= a.shape[1] - 1)
    result = np.full(y.shape, np.nan)
    yy, xx = y[valid], x[valid]
    iy = np.clip(np.floor(yy).astype('int64'), 0, a.shape[0] - 2)
    ix = np.floor(xx).astype('int64')
    if not wrap:
        ix = np.clip(ix, 0, a.shape[1] - 2)
    dy, dx = yy - iy, xx - ix
    j0, j1 = ix % a.shape[1], (ix + 1) % a.shape[1]
    top = a[iy, j0] + dx * (a[iy, j1].astype(float) - a[iy, j0])
    bottom = a[iy + 1, j0] + dx * (a[iy + 1, j1].astype(float) - a[iy + 1, j0])
    result[valid] = top + dy * (bottom - top)
    return result


class Global:
    def __init__(self, ppd):
        self.path = RAW / f'ldem_{ppd}_float.img'
        self.meta = label(self.path.with_suffix('.lbl').read_text(encoding='latin-1'))
        l = self.meta
        assert l['OFFSET'] == 1737.4 and l['UNIT'] == 'KILOMETER'
        assert l['SAMPLE_TYPE'] == 'PC_REAL' and l['SAMPLE_BITS'] == 32
        self.ppd = l['MAP_RESOLUTION']
        self.h = np.memmap(self.path, '<f4', mode='r', shape=(int(l['LINES']), int(l['LINE_SAMPLES']))) if self.path.exists() else None
        self.site, self.regional = None, None

    def __call__(self, lat, lon):
        l = self.meta
        row = np.clip(l['LINE_PROJECTION_OFFSET'] - lat * self.ppd, 0, int(l['LINES']) - 1)
        col = l['SAMPLE_PROJECTION_OFFSET'] + (lon % 360 - l['CENTER_LONGITUDE']) * self.ppd
        if self.h is None:
            if self.regional is None:
                self.regional = regional_global(self.site, self.ppd, l)
            a, m = self.regional
            c = (col - m['c0']) % int(l['LINE_SAMPLES'])
            return bilinear(a, row - m['r0'], c, m['full_longitude']) * 1000 * l.get('SCALING_FACTOR',1)
        return bilinear(self.h, row, col, True) * (1000 * l.get('SCALING_FACTOR', 1))


class RemoteTIFF(io.RawIOBase):
    """Seekable original byte blocks; tifffile only decodes selected source segments."""
    block = 1024**2

    def __init__(self, url):
        super().__init__()
        self.url, self.position = url, 0
        self.http = session()
        with self.http.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=(20, 120)) as r:
            r.raise_for_status()
            m = re.fullmatch(r'bytes 0-0/(\d+)', r.headers.get('Content-Range', ''))
            if r.status_code != 206 or not m:
                raise ValueError('No range support: ' + url)
            self.length = int(m[1])
            self.etag = r.headers.get('ETag')
            meta = {'url': url, 'size': self.length, 'etag': self.etag,
                    'modified': r.headers.get('Last-Modified')}
        self.folder = RAW / 'tiff_bytes' / digest(json.dumps(meta, sort_keys=True).encode())[:24]
        atomic(self.folder / 'source.json', meta)
        self.last = (-1, b'')

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (0 if whence == 0 else self.position if whence == 1 else self.length)
        if self.position < 0:
            raise ValueError('negative seek')
        return self.position

    def read(self, n=-1):
        stop = self.length if n < 0 else min(self.length, self.position + n)
        parts = []
        while self.position < stop:
            k = self.position // self.block
            begin, end = k * self.block, min((k + 1) * self.block, self.length) - 1
            p = self.folder / f'{k}.bin'
            if self.last[0] == k:
                b = self.last[1]
            elif p.exists():
                b = p.read_bytes()
            else:
                with self.http.get(self.url, headers={'Range': f'bytes={begin}-{end}'},
                         stream=True, timeout=(20, 180)) as r:
                    r.raise_for_status()
                    if r.status_code != 206 or r.headers.get('Content-Range') != f'bytes {begin}-{end}/{self.length}':
                        raise ValueError('TIFF invalid source byte range')
                    if self.etag and r.headers.get('ETag') != self.etag:
                        raise ValueError('TIFF source changed')
                    b = r.content
                if len(b) != end - begin + 1:
                    raise ValueError('TIFF truncated range')
                tmp = p.with_suffix('.part')
                tmp.write_bytes(b)
                tmp.replace(p)
            if len(b) != end - begin + 1:
                raise ValueError('Bad cached source block')
            self.last = (k, b)
            hi = min(stop, end + 1)
            parts.append(b[self.position - begin:hi - begin])
            self.position = hi
        return b''.join(parts)


def stereographic(lat, lon):
    la, lo = np.deg2rad(lat), np.deg2rad(lon)
    rho = 2 * R * np.tan((np.pi / 2 + la) / 2)
    return rho * np.sin(lo), rho * np.cos(lo)


class Window:
    def __init__(self, p, polar=False):
        self.z = np.load(p, allow_pickle=False)
        self.h = self.z['height']
        self.meta = json.loads(str(self.z['meta']))
        self.polar = polar

    def __call__(self, lat, lon):
        m = self.meta
        if self.polar:
            x, y = stereographic(lat, lon)
            return bilinear(self.h, (m['y0'] - y) / m['step'], (x - m['x0']) / m['step'])
        lon = (lon - m['lon0'] + 180) % 360 + m['lon0'] - 180
        return bilinear(self.h, (m['lat0'] - lat) * 512, (lon - m['lon0']) * 512)


def polar_window(site, res, radius_km):
    p = RAW / 'polar_windows' / str(res) / (site['id'] + '.npz')
    if p.exists():
        return Window(p, True)
    url = 'https://pgda.gsfc.nasa.gov/data/' + POLAR[res]
    stream = RemoteTIFF(url)
    with tifffile.TiffFile(stream) as tf:
        page = tf.pages[0]
        sx, sy, _ = page.tags['ModelPixelScaleTag'].value
        ix, iy, _, x, y, _ = page.tags['ModelTiepointTag'].value
        g = page.geotiff_tags
        assert sx == sy == res and g['ProjNatOriginLatGeoKey'] == -90
        assert g['GeogSemiMajorAxisGeoKey'] == g['GeogSemiMinorAxisGeoKey'] == R
        shift = 0 if g.get('GTRasterTypeGeoKey', 1) == 2 else 0.5
        x0, y0 = x + (shift - ix) * sx, y - (shift - iy) * sy
        cx, cy = stereographic(site['lat'], site['lon'])
        rad = radius_km * 1000
        # Exactly the source-pixel outer edges enclosing the published cache square.
        c0 = max(0, math.floor((cx - rad - x0 + sx / 2) / sx))
        c1 = min(page.imagewidth, math.ceil((cx + rad - x0 + sx / 2) / sx))
        r0 = max(0, math.floor((y0 + sy / 2 - cy - rad) / sy))
        r1 = min(page.imagelength, math.ceil((y0 + sy / 2 - cy + rad) / sy))
        if r0 >= r1 or c0 >= c1:
            return None
        h = np.full((r1 - r0, c1 - c0), np.nan, dtype=np.float32)
        th = page.tilelength if page.is_tiled else page.rowsperstrip
        tw = page.tilewidth if page.is_tiled else page.imagewidth
        ncols = math.ceil(page.imagewidth / tw)
        for rr in range(r0 // th, (r1 - 1) // th + 1):
            for cc in range(c0 // tw, (c1 - 1) // tw + 1):
                k = rr * ncols + cc
                stream.seek(page.dataoffsets[k])
                decoded = page.decode(stream.read(page.databytecounts[k]), k)[0]
                if decoded is None:
                    continue
                tile = decoded.reshape(decoded.shape[1:3])
                ya, yb = max(r0, rr * th), min(r1, rr * th + tile.shape[0])
                xa, xb = max(c0, cc * tw), min(c1, cc * tw + tile.shape[1])
                h[ya - r0:yb - r0, xa - c0:xb - c0] = tile[ya - rr * th:yb - rr * th, xa - cc * tw:xb - cc * tw]
        nd = page.tags.get('GDAL_NODATA')
        if nd:
            h[h == float(str(nd.value).strip('\x00'))] = np.nan
        meta = dict(url=url, byte_identity=str(stream.folder), bounds=[r0, r1, c0, c1],
                    x0=x0 + c0 * sx, y0=y0 - r0 * sy, step=res,
                    reference_radius_m=R, units='m', registration='source pixel centres',
                    source_geokeys=str(g), source_window_sha256=digest(h.tobytes()))
    save_window(p, h, meta)
    print(site['id'], 'original polar', res, h.shape, flush=True)
    return Window(p, True)


def save_window(p, h, meta):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.part')
    with tmp.open('wb') as f:
        np.savez_compressed(f, height=h, meta=json.dumps(meta, sort_keys=True))
    tmp.replace(p)


def ranges(url, spans):
    """Strict PDS multipart range reader; persist decoded row batches as source bytes."""
    signature = digest((url + str(spans)).encode())
    p = RAW / 'pds_batches' / (signature + '.bin')
    sizes = [b - a + 1 for a, b in spans]
    if p.exists():
        b = p.read_bytes()
        if len(b) != sum(sizes): raise ValueError('bad cached row batch')
        return np.split(np.frombuffer(b, dtype='u1'), np.cumsum(sizes)[:-1])
    # Servers may coalesce contiguous byte ranges; do that explicitly before parsing.
    joined = []
    for a,b in spans:
        if joined and joined[-1][1] + 1 == a: joined[-1] = (joined[-1][0],b)
        else: joined.append((a,b))
    headers = {'Range': 'bytes=' + ','.join(f'{a}-{b}' for a, b in joined)}
    range_url=url+'?range='+digest(headers['Range'].encode())[:20]
    with HTTP.get(range_url, headers=headers, stream=True, timeout=(20, 180)) as r:
        r.raise_for_status()
        if r.status_code != 206:
            raise ValueError('PDS rejected multiple ranges: ' + url)
        ct = r.headers.get('Content-Type', '')
        body = r.content
        if ct.lower().startswith('multipart/'):
            # This PDS server emits an unquoted boundary containing angle brackets.
            # Quote that parameter for the standards-compliant MIME parser.
            boundary_match = re.search(r'boundary=([^;]+)',ct,re.I)
            if not boundary_match: raise ValueError('Missing PDS MIME boundary')
            boundary=boundary_match[1].strip().strip('"')
            ct='multipart/byteranges; boundary="'+boundary+'"'
            parts = {}
            for segment in body.split(b'--'+boundary.encode('ascii')):
                if segment.startswith(b'--'): continue  # MIME closing delimiter, not a data part.
                headers, separator, payload=segment.partition(b'\r\n\r\n')
                if not separator: continue
                m=re.search(rb'Content-Range:\s*bytes (\d+)-(\d+)/(\d+)',headers,re.I)
                if not m:
                    atomic(RAW/'multipart_header_diagnostic.json',dict(header=repr(headers[:500]),prefix=repr(segment[:500]),boundary=boundary))
                    raise ValueError('malformed multipart header; diagnostic saved')
                lo,hi=int(m[1]),int(m[2])
                size=hi-lo+1
                if len(payload)<size: raise ValueError('truncated original byte part')
                parts[(lo,hi)]=payload[:size]
            chunks=[]
            for a,b in joined:
                containing=[(lo,hi,payload) for (lo,hi),payload in parts.items() if lo<=a<=b<=hi]
                if len(containing)!=1:
                    raise ValueError(f'Wrong original ranges: requested {(a,b)}, received {list(parts)[:3]}')
                lo,hi,payload=containing[0]
                chunks.append(payload[a-lo:b-lo+1])
        else:
            if len(joined) != 1: raise ValueError('server omitted multipart boundaries')
            chunks = [body]
    if [len(c) for c in chunks] != [b-a+1 for a,b in joined]: raise ValueError('PDS row length mismatch')
    payload=b''.join(chunks)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.part')
    tmp.write_bytes(payload); tmp.replace(p)
    return np.split(np.frombuffer(payload,dtype='u1'),np.cumsum(sizes)[:-1])


def regional_global(site, ppd, grid):
    """Fetch original source pixels covering the entire 300 km spherical cap."""
    p=RAW/'global_windows'/str(int(ppd))/(site['id']+'.npz')
    if p.exists():
        with np.load(p,allow_pickle=False) as z:
            return z['height'],json.loads(str(z['meta']))
    la,lo=site['lat'],site['lon']%360
    arc=300000/R
    dla=math.degrees(arc)
    ns,nl=int(grid['LINE_SAMPLES']),int(grid['LINES'])
    r0=max(0,math.floor(grid['LINE_PROJECTION_OFFSET']-(la+dla)*ppd)-2)
    r1=min(nl,math.ceil(grid['LINE_PROJECTION_OFFSET']-(la-dla)*ppd)+3)
    full=abs(la)+dla>=90
    if full:
        c0,c1=0,ns
    else:
        dlo=math.degrees(math.asin(math.sin(arc)/math.cos(math.radians(la))))
        c0=math.floor(grid['SAMPLE_PROJECTION_OFFSET']+(lo-dlo-grid['CENTER_LONGITUDE'])*ppd)-2
        c1=math.ceil(grid['SAMPLE_PROJECTION_OFFSET']+(lo+dlo-grid['CENTER_LONGITUDE'])*ppd)+3
    h=np.empty((r1-r0,c1-c0),dtype='<f4')
    url=PDS+f'lola_gdr/cylindrical/float_img/ldem_{int(ppd)}_float.img'
    for ca in range(c0,c1):
        if ca==c0 or ca%ns==0:
            cb=min(c1,ca+ns-ca%ns)
            for start in range(r0,r1,16):
                yy=list(range(start,min(start+16,r1)))
                spans=[(4*(row*ns+ca%ns),4*(row*ns+ca%ns+cb-ca)-1) for row in yy]
                blocks=ranges(url,spans)
                for row,b in zip(yy,blocks): h[row-r0,ca-c0:cb-c0]=np.frombuffer(b,'<f4')
    meta=dict(url=url,r0=r0,c0=c0,full_longitude=full,ppd=ppd,units='km',
              source_window_sha256=digest(h.tobytes()),original_grid=grid)
    save_window(p,h,meta)
    print(site['id'],'original LDEM',ppd,h.shape,flush=True)
    return h,meta


def sldem_window(site):
    p = RAW / 'sldem_windows' / (site['id'] + '.npz')
    if p.exists(): return Window(p)
    folder = PDS + 'sldem2015/tiles/float_img/'
    listing = RAW / 'sldem_listing.html'
    if not listing.exists(): listing.write_text(text(folder), encoding='latin-1')
    pattern = r'sldem2015_512_(\d+)([ns])_(\d+)([ns])_(\d{3})_(\d{3})_float\.img'
    matches = {m[0]: m for m in re.finditer(pattern, listing.read_text(encoding='latin-1'), re.I)}
    if len(matches) != 32: raise ValueError('Expected 32 original SLDEM tiles')
    lat, lon = site['lat'], site['lon'] % 360
    arc = 150000 / R
    dla = math.degrees(arc)
    dlo = math.degrees(math.asin(math.sin(arc) / math.cos(math.radians(lat))))
    north, south = min(60, lat + dla + 2 / 512), max(-60, lat - dla - 2 / 512)
    ra, rb = math.floor((90 - north) * 512), math.ceil((90 - south) * 512)
    ca, cb = math.floor((lon - dlo - 2 / 512) * 512), math.ceil((lon + dlo + 2 / 512) * 512)
    h = np.full((rb - ra, cb - ca), np.nan, dtype=np.float32)
    sources = []
    for name, match in matches.items():
        a, b = [float(match[i]) * (1 if match[i + 1].lower() == 'n' else -1) for i in (1, 3)]
        top, bottom = max(a, b), min(a, b)
        west, east = float(match[5]), float(match[6])
        tile_r = round((90 - top) * 512)
        rows, cols = round((top - bottom) * 512), round((east - west) * 512)
        ya, yb = max(ra, tile_r), min(rb, tile_r + rows)
        if ya >= yb: continue
        for turn in (-1, 0, 1):
            tile_c = round((west + 360 * turn) * 512)
            xa, xb = max(ca, tile_c), min(cb, tile_c + cols)
            if xa >= xb: continue
            lbl = text(folder + name[:-4] + '.lbl')
            grid = label(lbl)
            assert grid['MAP_RESOLUTION'] == 512 and grid['LINE_SAMPLES'] == cols
            assert grid['LINES'] == rows and grid['OFFSET'] == 1737.4
            assert grid['UNIT'] == 'KILOMETER' and grid['SAMPLE_TYPE'] == 'PC_REAL'
            assert abs((grid['LINE_PROJECTION_OFFSET'] - 0) / 512 - (top - 0.5 / 512)) < 1e-7
            for y in range(ya, yb, 64):
                yy = list(range(y, min(yb, y + 64)))
                spans = [(4 * ((v - tile_r) * cols + xa - tile_c),
                          4 * ((v - tile_r) * cols + xb - tile_c) - 1) for v in yy]
                blocks = ranges(folder + name, spans)
                for v, raw in zip(yy, blocks):
                    h[v - ra, xa - ca:xb - ca] = np.frombuffer(raw, '<f4') * 1000
            sources.append({'url': folder + name, 'label_sha256': digest(lbl.encode('latin-1'))})
    if not np.isfinite(h).all(): raise ValueError('Original SLDEM window has uncovered pixels')
    meta = dict(lat0=90 - (ra + 0.5) / 512, lon0=(ca + 0.5) / 512,
                sources=sources, reference_radius_m=R, units='m',
                source_window_sha256=digest(h.tobytes()))
    save_window(p, h, meta)
    print(site['id'], 'original SLDEM', h.shape, flush=True)
    return Window(p)


def distances(minimum):
    """Uniform brute-force segments tied to native DEM scales, never early-stop."""
    if minimum < 0.1:
        segments = [(minimum * 1000, 3000, 2.5), (3000, 25000, 5),
                    (25000, 60000, 15), (60000, 200000, 60), (200000, 300000, 120)]
    else:
        segments = [(minimum * 1000, 3000, 2.5), (3000, 150000, 10), (150000, 300000, 60)]
    return np.unique(np.concatenate([np.arange(a, b, step) for a, b, step in segments] + [np.array([300000.])]))


def destinations(lat, lon, bearings, metres):
    phi, lam = math.radians(lat), math.radians(lon)
    az, delta = np.deg2rad(bearings)[:, None], metres[None, :] / R
    s = np.sin(phi) * np.cos(delta) + np.cos(phi) * np.sin(delta) * np.cos(az)
    p = np.arcsin(np.clip(s, -1, 1))
    l = lam + np.arctan2(np.sin(az) * np.sin(delta) * np.cos(phi), np.cos(delta) - np.sin(phi) * np.sin(p))
    return np.rad2deg(p), (np.rad2deg(l) + 180) % 360 - 180


def sunlight(site, horizon, h0):
    e = np.fromfile(ROOT / 'web/data/ephem.bin', '<f4').reshape(-1, 6).astype(float)
    assert e.shape == (43824, 6)
    la, lo = np.deg2rad([site['lat'], site['lon']])
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    east = np.array([-np.sin(lo), np.cos(lo), 0])
    north = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    # Own topocentric projection; centre above mask is equivalent to >= half solar disk.
    v = e[:, :3] - up * ((R + h0 + 2) / 1000)
    z, x, y = v @ up, v @ east, v @ north
    az = np.rad2deg(np.arctan2(x, y)) % 360
    el = np.rad2deg(np.arctan2(z, np.hypot(x, y)))
    ix = az / 0.5
    k = np.floor(ix).astype(int) % 720
    mask = horizon[k] + (ix - np.floor(ix)) * (horizon[(k + 1) % 720] - horizon[k])
    return int(np.count_nonzero(el >= mask)) / e.shape[0]


def run_site(site, globals_):
    sid = site['id']
    refpath = ROOT / 'web/data/horizon' / (sid + '.json')
    refbytes = refpath.read_bytes()
    reference = json.loads(refbytes)
    out = OUT / (sid + '.json')
    signature = digest(refbytes + Path(__file__).read_bytes() + INPUT.read_bytes())
    if out.exists() and json.loads(out.read_text())['signature'] == signature:
        print(sid, 'REUSED independent completed result', flush=True)
        return
    started = time.time()
    for sampler in globals_.values():
        sampler.site, sampler.regional = site, None
    chain = []
    for name, limit, *_ in reference['engine']['chain']:
        if name.startswith('PGDA_LOLA_'):
            res = int(name.split('_')[-1][:-1])
            sampler = polar_window(site, res, limit)
            if sampler is not None: chain.append((name, float(limit) * 1000, sampler))
        elif name == 'SLDEM2015': chain.append((name, float(limit) * 1000, sldem_window(site)))
        else: chain.append((name, float(limit) * 1000, globals_[int(name.split('_')[-1])]))

    def sample(lat, lon, dist):
        h = np.full(lat.shape, np.nan)
        for name, limit, sampler in chain:
            need = ~np.isfinite(h) & (dist <= limit)
            if need.any(): h[need] = sampler(lat[need], lon[need])
        return h

    h0 = sample(np.array([site['lat']]), np.array([site['lon']]), np.array([0.]))[0]
    if not np.isfinite(h0): raise ValueError(sid + ' no original terrain at observer')
    ds = distances(reference['engine']['min_km'])
    theta = ds / R
    observer = R + h0 + 2
    progress_path = OUT / (sid + '.progress.json')
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    result = progress.get('mask_deg', []) if progress.get('signature') == signature else []
    worst_distance = progress.get('peak_distance_m', []) if progress.get('signature') == signature else []
    assert len(result) % 12 == 0 and len(result) == len(worst_distance)
    for begin in range(len(result), 720, 12):
        az = np.arange(begin, begin + 12) * 0.5
        lat, lon = destinations(site['lat'], site['lon'], az, ds)
        terrain = sample(lat, lon, np.broadcast_to(ds, lat.shape))
        if not np.isfinite(terrain).all(): raise ValueError(sid + ' missing original DEM samples')
        # Cancellation-resistant radial difference: rt*cos(theta)-ro.
        vertical = (terrain - h0 - 2) - (R + terrain) * 2 * np.sin(theta / 2)**2
        horizontal = (R + terrain) * np.sin(theta)
        angles = np.rad2deg(np.arctan2(vertical, horizontal))
        maxima = angles.argmax(axis=1)
        result.extend(angles[np.arange(12), maxima].tolist())
        worst_distance.extend(ds[maxima].tolist())
        atomic(progress_path, dict(signature=signature, mask_deg=result,
                                   peak_distance_m=worst_distance))
        if begin % 120 == 0: print(sid, 'rays', begin + 12, '/720', flush=True)
    mask = np.asarray(result)
    stored = np.asarray(reference['mask'])
    delta = mask - stored
    metricpath = ROOT / 'web/data/metrics' / (sid + '.json')
    metric = json.loads(metricpath.read_text())
    my_sun = sunlight(site, mask, h0)
    stored_mask_sun = sunlight(site, stored, reference['h0_m'])
    seed = int.from_bytes(hashlib.sha256(('20261115A:' + sid).encode()).digest()[:8], 'big')
    selected = sorted(np.random.default_rng(seed).choice(720, 10, replace=False).tolist())
    record = dict(id=sid, input_commit=INPUT.read_text().strip(),
                  checker='Minchul Kim', signature=signature, stored_sha256=digest(refbytes),
                  own_h0_m=float(h0), stored_h0_m=reference['h0_m'], observer_height_m=2,
                  near_min_m=reference['engine']['min_km']*1000, max_range_m=300000,
                  distances_per_ray=len(ds), rays=720, early_stop=False,
                  mask_deg=result, stored_mask_deg=stored.tolist(), difference_deg=delta.tolist(),
                  peak_distance_m=worst_distance, random_indices=selected,
                  max_abs_deg=float(abs(delta).max()), median_abs_deg=float(np.median(abs(delta))),
                  failures_deg=[int(x) for x in np.flatnonzero(abs(delta)>0.05)],
                  own_sun_frac=my_sun, stored_sun_frac=metric['sun_frac'],
                  stored_mask_sun_frac=stored_mask_sun, sun_difference_pp=100*(my_sun-metric['sun_frac']),
                  elapsed_s=time.time()-started,
                  sources=[dict(name=n, limit_m=l, metadata=getattr(s,'meta',{})) for n,l,s in chain])
    atomic(out, record)
    print('DONE', sid, 'max deg', record['max_abs_deg'], 'Sun pp', record['sun_difference_pp'],
          'seconds', round(record['elapsed_s'],1), flush=True)


def prepare_global(ppd):
    folder = PDS + 'lola_gdr/cylindrical/float_img/'
    stem = f'ldem_{ppd}_float'
    RAW.mkdir(parents=True, exist_ok=True)
    lbl = RAW / (stem + '.lbl')
    if not lbl.exists(): lbl.write_text(text(folder + stem + '.lbl'), encoding='latin-1')
    download(folder + stem + '.img', RAW / (stem + '.img'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare-global', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--prepare-sites', action='store_true')
    ap.add_argument('--site', action='append')
    args = ap.parse_args()
    if args.prepare_global:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(prepare_global, [64, 16]))
    if args.prepare_sites:
        sites = json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
        if args.site: sites = [s for s in sites if s['id'] in args.site]
        for s in sites:
            ref = json.loads((ROOT/'web/data/horizon'/(s['id']+'.json')).read_text())
            for name, limit, *_ in ref['engine']['chain']:
                if name.startswith('PGDA_LOLA_'):
                    polar_window(s, int(name.split('_')[-1][:-1]), limit)
                elif name == 'SLDEM2015':
                    sldem_window(s)
    if args.run:
        if (OUT/'errors.json').exists():
            atomic(OUT/'previous_run_errors.json',json.loads((OUT/'errors.json').read_text()))
        atomic(OUT/'errors.json',[])
        RAW.mkdir(parents=True,exist_ok=True)
        for ppd in (64,16):
            f=RAW/f'ldem_{ppd}_float.lbl'
            if not f.exists(): f.write_text(text(PDS+f'lola_gdr/cylindrical/float_img/ldem_{ppd}_float.lbl'),encoding='latin-1')
        sites = json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
        if args.site: sites = [s for s in sites if s['id'] in args.site]
        glob = {ppd: Global(ppd) for ppd in (64,16)}
        failed = []
        for s in sites:
            try: run_site(s, glob)
            except Exception as error:
                failed.append(dict(id=s['id'], error=repr(error)))
                atomic(OUT/'errors.json', failed)
                print('ERROR', s['id'], repr(error), flush=True)
        if failed: raise SystemExit(2)


if __name__ == '__main__':
    main()
