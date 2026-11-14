"""Fetch PGDA lunar DEM windows without downloading whole source TIFFs.

Run from the repository root. See docs/polar.md for cache format and verification.
"""
import argparse
import hashlib
import io
import json
import math
import re
from pathlib import Path

import numpy as np
import requests
import tifffile
from pyproj import Proj
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RADIUS = 1737400.0
PROJ = f'+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R={RADIUS} +units=m'
POLAR = Proj(PROJ)
BASE = 'https://pgda.gsfc.nasa.gov/data/'
SOURCES = {
    5: ('LOLA_5mpp/87S/ldem_87s_5mpp.tif', 3000),
    10: ('LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF', 25000),
    20: ('LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF', 25000),
    60: ('LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF', 60000),
    80: ('LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF', 60000),
    240: ('LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF', 200000),
}
PLACEHOLDERS = [dict(id=f'TEST_POLAR_{i+1}', lat=lat, lon=lon,
                     coord_quality='estimated', note='Synthetic test point; not a landing site')
                for i, (lat, lon) in enumerate([(-89.5, 0), (-89.5, 90), (-89, -90)])]


class RangeFile(io.RawIOBase):
    """Seekable, single-writer HTTP reader; complete blocks survive interruption.

    Cache identity includes URL, remote size and validators. Partial block writes
    never become valid blocks. Range-ignoring servers are rejected before body read.
    """
    block_size = 1048576

    def __init__(self, url, cache):
        super().__init__()
        self.url, self.pos, self.bytes_fetched = url, 0, 0
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
        self.session.headers['Accept-Encoding'] = 'identity'
        with self.session.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=60) as r:
            r.raise_for_status()
            match = re.fullmatch(r'bytes 0-0/(\d+)', r.headers.get('Content-Range', ''))
            if r.status_code != 206 or not match:
                raise ValueError('Range metadata probe rejected')
            self.size = int(match[1])
            self.etag = r.headers.get('ETag')
            self.modified = r.headers.get('Last-Modified')
        if not (self.etag or self.modified):
            raise ValueError('Source has no validator; persistent cache would be unsafe')
        identity = json.dumps([url, self.size, self.etag, self.modified, self.block_size])
        self.cache = Path(cache) / hashlib.sha256(identity.encode()).hexdigest()[:24]
        self.cache.mkdir(parents=True, exist_ok=True)
        (self.cache / 'source.json').write_text(identity, encoding='utf-8')

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        pos = offset + (0 if whence == 0 else self.pos if whence == 1 else self.size)
        if whence not in (0, 1, 2) or pos < 0:
            raise ValueError('Invalid seek')
        self.pos = pos
        return pos

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.size, self.pos + size)
        chunks = []
        while self.pos < end:
            start = self.pos // self.block_size * self.block_size
            stop = min(start + self.block_size, self.size)
            path = self.cache / str(start)
            if not path.exists() or path.stat().st_size != stop-start:
                headers = {'Range': f'bytes={start}-{stop-1}'}
                with self.session.get(self.url, headers=headers, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    if r.status_code != 206 or r.headers.get('Content-Range') != f'bytes {start}-{stop-1}/{self.size}':
                        raise ValueError('Invalid Range response or changed source')
                    if r.headers.get('ETag') != self.etag or r.headers.get('Last-Modified') != self.modified:
                        raise ValueError('Source validator changed during Range download')
                    data = r.raw.read(stop-start+1)
                    self.bytes_fetched += len(data)
                    if len(data) != stop-start:
                        raise ValueError('Truncated or oversized Range response')
                partial = path.with_suffix('.part')
                partial.write_bytes(data)
                partial.replace(path)
            data = path.read_bytes()
            n = min(end, stop)-self.pos
            chunks.append(data[self.pos-start:self.pos-start+n])
            self.pos += n
        return b''.join(chunks)

    def close(self):
        if hasattr(self, 'session'):
            self.session.close()
        super().close()


def project(lat, lon):
    if not (-90 <= lat < 0 and -180 <= lon <= 180):
        raise ValueError('Expected southern latitude and east longitude in [-180,180]')
    return POLAR(lon, lat)


def grid(page):
    """Return first pixel CENTER x/y and pixel spacing, respecting RasterType."""
    sx, sy, _ = page.tags[33550].value
    i, j, _, x, y, _ = page.tags[33922].value
    if sx != sy or sx <= 0 or 34264 in page.tags:
        raise ValueError('Only north-up square-pixel grids supported')
    point = (page.geotiff_tags or {}).get('GTRasterTypeGeoKey', 1) == 2
    shift = 0 if point else 0.5
    return x + (shift-i)*sx, y - (shift-j)*sy, sx


def validate_crs(tags):
    expected = dict(GeogSemiMajorAxisGeoKey=RADIUS, GeogSemiMinorAxisGeoKey=RADIUS,
                    ProjCoordTransGeoKey=15, ProjLinearUnitsGeoKey=9001,
                    GeogAngularUnitsGeoKey=9102, ProjNatOriginLatGeoKey=-90,
                    ProjFalseEastingGeoKey=0, ProjFalseNorthingGeoKey=0,
                    ProjScaleAtNatOriginGeoKey=1, ProjStraightVertPoleLongGeoKey=0)
    if not tags or any(k not in tags or not math.isclose(float(tags[k]), v, abs_tol=1e-8)
                       for k, v in expected.items()):
        raise ValueError('Source CRS is not the expected lunar south-polar stereographic grid')


def read_window(page, stream, bounds):
    """Decode only full-resolution tiles/strips intersecting [r0:r1,c0:c1]."""
    r0, r1, c0, c1 = bounds
    if page.samplesperpixel != 1 or not (0 <= r0 < r1 <= page.imagelength and 0 <= c0 < c1 <= page.imagewidth):
        raise ValueError('Invalid DEM window')
    th = page.tilelength if page.is_tiled else page.rowsperstrip
    tw = page.tilewidth if page.is_tiled else page.imagewidth
    cols = math.ceil(page.imagewidth/tw)
    out = np.full((r1-r0, c1-c0), np.nan, dtype='<f4')
    for tr in range(r0//th, (r1-1)//th+1):
        for tc in range(c0//tw, (c1-1)//tw+1):
            idx = tr*cols+tc
            stream.seek(page.dataoffsets[idx])
            tile, _, _ = page.decode(stream.read(page.databytecounts[idx]), idx)
            if tile is None:
                continue
            tile = tile[0, :, :, 0]
            a, b = max(r0,tr*th), min(r1,tr*th+tile.shape[0])
            c, d = max(c0,tc*tw), min(c1,tc*tw+tile.shape[1])
            out[a-r0:b-r0,c-c0:d-c0] = tile[a-tr*th:b-tr*th,c-tc*tw:d-tc*tw]
    nodata = page.tags.get(42113)
    if nodata:
        out[out == float(nodata.value.rstrip('\x00'))] = np.nan
    return out


class SourceCoverageError(ValueError):
    """Requested coordinates are outside this DEM's footprint."""


def clip_window(bounds, shape, *, allow_partial=False):
    """Keep only available source pixels when explicitly requested; never extrapolate."""
    r0, r1, c0, c1 = bounds
    nr, nc = shape
    clipped = max(0, r0), min(nr, r1), max(0, c0), min(nc, c1)
    if clipped[0] >= clipped[1] or clipped[2] >= clipped[3]:
        raise SourceCoverageError('Requested window has no source coverage')
    if clipped != tuple(bounds) and not allow_partial:
        raise SourceCoverageError('Requested window exceeds source coverage')
    return clipped


def fetch(site, res, radius, root, *, allow_partial=False):
    url = BASE + SOURCES[res][0]
    dest = root / str(res) / (site['id'] + '.npz')
    x, y = project(site['lat'], site['lon'])
    with RangeFile(url, root / '_blocks') as stream, tifffile.TiffFile(stream) as tif:
        page = tif.pages[0]
        validate_crs(page.geotiff_tags)
        x0, y0, step = grid(page)
        if not math.isclose(step, res):
            raise ValueError(f'Unexpected pixel size: {step}')
        # Half-pixel outer edges enclosing the entire requested projected square.
        c0 = math.floor((x-radius-(x0-step/2))/step)
        c1 = math.ceil((x+radius-(x0-step/2))/step)
        r0 = math.floor(((y0+step/2)-(y+radius))/step)
        r1 = math.ceil(((y0+step/2)-(y-radius))/step)
        requested_bounds = [r0, r1, c0, c1]
        r0, r1, c0, c1 = clip_window(requested_bounds, (page.imagelength, page.imagewidth),
                                    allow_partial=allow_partial)
        meta = dict(site=site, source_url=url, source_size_bytes=stream.size,
                    etag=stream.etag, last_modified=stream.modified,
                    resolution_m=res, radius_m=radius, frame='MOON_ME_DE421',
                    reference_radius_m=RADIUS, projection=PROJ, bounds=[r0,r1,c0,c1],
                    pixel_registration='center', units='m',
                    source_geotiff=str(page.geotiff_tags))
        if requested_bounds != [r0, r1, c0, c1]:
            meta.update(requested_bounds=requested_bounds, coverage_clipped=True)
        if dest.exists():
            with np.load(dest, allow_pickle=False) as old:
                if json.loads(str(old['metadata'])) == meta:
                    print(f'{site["id"]} {res}m: cached; fetched {stream.bytes_fetched} bytes', flush=True)
                    return
        heights = read_window(page, stream, (r0,r1,c0,c1))
        if not np.isfinite(heights).any():
            raise ValueError('Window contains no valid elevations')
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_suffix('.part')
        with temporary.open('wb') as f:
            np.savez_compressed(f, height_m=heights,
                                x_m=x0+np.arange(c0,c1)*step,
                                y_m=y0-np.arange(r0,r1)*step,
                                metadata=json.dumps(meta, sort_keys=True))
        temporary.replace(dest)
        print(f'{site["id"]} {res}m: {heights.shape}; fetched {stream.bytes_fetched} / {stream.size} bytes', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sites', type=Path, default=Path('web/data/sites.json'))
    p.add_argument('--site', help='Only this site ID')
    p.add_argument('--res', type=int, nargs='+', choices=list(SOURCES), default=list(SOURCES))
    p.add_argument('--radius-m', type=float, help='Override radii for a small smoke test')
    p.add_argument('--output', type=Path, default=Path('data/raw/polar'))
    p.add_argument('--clip-coverage', action='store_true',
                   help='Keep available original pixels for partially covered windows; no extrapolation')
    p.add_argument('--skip-unavailable', action='store_true',
                   help='Report out-of-coverage sources as unavailable; transport/data errors still fail')
    args = p.parse_args()
    if args.radius_m is not None and (not math.isfinite(args.radius_m) or args.radius_m <= 0):
        p.error('radius must be positive and finite')
    if args.sites.exists():
        sites = json.loads(args.sites.read_text(encoding='utf-8'))
    elif args.sites == Path('web/data/sites.json'):
        sites = PLACEHOLDERS
        print('sites.json absent: using three SYNTHETIC test points, not landing sites', flush=True)
    else:
        p.error(f'sites file missing: {args.sites}')
    ids = [s['id'] for s in sites]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Z][A-Z0-9_]*', s) for s in ids):
        p.error('Site IDs must be unique UPPER_SNAKE identifiers')
    sites = [s for s in sites if s['lat'] <= -80 and (args.site is None or s['id'] == args.site)]
    if not sites:
        p.error('No matching south-polar sites (latitude <= -80)')
    if any(s.get('mock') for s in sites):
        print('WARNING: selected sites include MOCK coordinates; terrain is real but site identity is unverified', flush=True)
    failures = []
    for site in sites:
        for res in args.res:
            try:
                fetch(site, res, args.radius_m or SOURCES[res][1], args.output,
                      allow_partial=args.clip_coverage)
            except SourceCoverageError as e:
                if args.skip_unavailable:
                    print(f'UNAVAILABLE {site["id"]} {res}m: {e}', flush=True)
                else:
                    failures.append(str(e))
                    print(f'FAILED {site["id"]} {res}m: {e}', flush=True)
            except (ValueError, requests.RequestException) as e:
                failures.append(str(e))
                print(f'FAILED {site["id"]} {res}m: {e}', flush=True)
    if failures:
        raise SystemExit(f'{len(failures)} windows failed; completed blocks are retained. Rerun to resume.')


if __name__ == '__main__':
    main()
