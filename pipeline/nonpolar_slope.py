"""Lander-scale slope for a non-polar catalogue site from SLDEM2015 512 ppd (contest-time computation).

Fills web/data/terrain/<ID>.json fields landing_slope_deg / slope_by_radius_m for a site with |lat| < 60
using the same definitions as the south-polar product (pipeline/build_terrain_y.py, contract section 23):

* landing slope: least-squares plane over 3x3 samples spaced one native pixel apart, bilinear, centred on
  the exact catalogue coordinate;
* distributions: the same 3x3 plane at every native pixel centre within 100/500/1000 m great-circle
  distance; flat fractions area-weighted on the reference sphere; thresholds 8/15 deg are reference only.

SLDEM2015 is simple cylindrical (lat/lon), not polar stereographic, so the ground spacing of one pixel is
(R+h)*dphi north-south and (R+h)*cos(phi)*dlambda east-west (h = local centre height, R = 1737.4 km),
which is the same R/(R+h) convention as the polar product. Roughness is NOT computed: the polar rule uses
a 50 m window, narrower than one 59 m SLDEM2015 pixel, so it is undefined here (stored as null).

Data: one contiguous HTTP Range request (full tile rows) from the public PDS tile, cropped and cached at
data/raw/terrain_nonpolar/<ID>_SLDEM2015.npz (not committed). Re-running reuses the cache.

Usage:  python pipeline/nonpolar_slope.py --site APOLLO17
"""
import argparse
import hashlib
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RADIUS = 1737400.0
PPD = 512
TILE_DIR = 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/'
TILES_N = [(-60, -30), (-30, 0), (0, 30), (30, 60)]
THRESHOLDS = [8, 15]
RADII = (100, 500, 1000)
HALF_ROWS = 60          # +-60 rows (~3.55 km) around the site; 1 km circle + 3x3 support needs ~19
HALF_COLS = 64
STATUS = 'author_checks_only_team_verification_pending'


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tile_for(lat, lon360):
    for south, north in TILES_N:
        if south <= lat < north:
            west = int(lon360 // 45) * 45
            ns = lambda v: f'{abs(v):02d}{"n" if v >= 0 else "s"}'
            return dict(name=f'sldem2015_512_{ns(south)}_{ns(north)}_{west:03d}_{west + 45:03d}_float.img',
                        south=south, north=north, west=west)
    raise SystemExit('SLDEM2015 covers 60 S..60 N only')


def fetch_window(site, out):
    """Download full rows g0..g1 of the tile by one Range request; crop columns; cache as npz."""
    lat, lon360 = site['lat'], site['lon'] % 360.0
    t = tile_for(lat, lon360)
    ncol = 45 * PPD
    rowb = ncol * 4
    # Tile pixel centres (label): lat = (15359.5 - r)/512 + south, lon = west + (c + 0.5)/512.
    rc = (t['north'] - lat) * PPD - 0.5
    cc = (lon360 - t['west']) * PPD - 0.5
    r0, r1 = int(math.floor(rc)) - HALF_ROWS, int(math.floor(rc)) + HALF_ROWS + 2
    c0, c1 = int(math.floor(cc)) - HALF_COLS, int(math.floor(cc)) + HALF_COLS + 2
    if r0 < 0 or r1 > 30 * PPD or c0 < 0 or c1 > ncol:
        raise SystemExit('Window crosses a tile edge; extend the fetcher before using this site')
    url = TILE_DIR + t['name']
    req = urllib.request.Request(url, headers={'Range': f'bytes={r0 * rowb}-{r1 * rowb - 1}'})
    with urllib.request.urlopen(req, timeout=300) as resp:
        if resp.status != 206:
            raise SystemExit(f'Expected HTTP 206 partial content, got {resp.status}')
        data = resp.read()
        meta = dict(etag=resp.headers.get('ETag'), last_modified=resp.headers.get('Last-Modified'),
                    content_range=resp.headers.get('Content-Range'))
    if len(data) != (r1 - r0) * rowb:
        raise SystemExit(f'Short read: {len(data)} bytes')
    rows = np.frombuffer(data, '<f4').reshape(r1 - r0, ncol)
    km = rows[:, c0:c1].astype(np.float32)          # height above 1737.4 km in km (label UNIT KILOMETER)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp.npz')
    np.savez_compressed(tmp, height_km=km, row0=r0, col0=c0, tile=t['name'], url=url,
                        tile_south=t['south'], tile_north=t['north'], tile_west=t['west'],
                        meta=json.dumps(meta), download_sha256=hashlib.sha256(data).hexdigest())
    tmp.replace(out)


def load_window(path):
    z = np.load(path, allow_pickle=False)
    h = z['height_km'].astype(np.float64) * 1000.0
    r0, c0, north, west = int(z['row0']), int(z['col0']), int(z['tile_north']), int(z['tile_west'])
    lat = north - (r0 + np.arange(h.shape[0]) + 0.5) / PPD          # north-up rows
    lon = west + (c0 + np.arange(h.shape[1]) + 0.5) / PPD
    return h, lat, lon, z


def native_slopes(h, lat):
    """3x3 least-squares plane at every interior pixel; NaN on the border."""
    d = math.radians(1.0 / PPD)
    z = np.lib.stride_tricks.sliding_window_view(h, (3, 3)) - h[1:-1, 1:-1, None, None]
    hc = h[1:-1, 1:-1]
    dy = (RADIUS + hc) * d
    dx = (RADIUS + hc) * d * np.cos(np.radians(lat[1:-1]))[:, None]
    gx = (z[..., :, 2].sum(-1) - z[..., :, 0].sum(-1)) / (6 * dx)
    gy = (z[..., 0, :].sum(-1) - z[..., 2, :].sum(-1)) / (6 * dy)
    out = np.full(h.shape, np.nan)
    out[1:-1, 1:-1] = np.degrees(np.arctan(np.hypot(gx, gy)))
    return out


def bilinear(h, lat, lon, qlat, qlon):
    row = (lat[0] - np.asarray(qlat)) * PPD
    col = (np.asarray(qlon) - lon[0]) * PPD
    row, col = np.broadcast_arrays(row, col)
    r, c = np.floor(row).astype(int), np.floor(col).astype(int)
    fr, fc = row - r, col - c
    return ((1 - fc) * (1 - fr) * h[r, c] + fc * (1 - fr) * h[r, c + 1]
            + (1 - fc) * fr * h[r + 1, c] + fc * fr * h[r + 1, c + 1])


def landing_slope(h, lat, lon, slat, slon):
    step = 1.0 / PPD
    off = np.arange(-1, 2) * step
    s = bilinear(h, lat, lon, slat - off[:, None], slon + off[None, :])   # rows north->south, cols west->east
    if not np.isfinite(s).all():
        raise SystemExit('Missing data in the landing 3x3')
    z = s - s[1, 1]
    d = math.radians(step) * (RADIUS + s[1, 1])
    gx = (z[:, 2].sum() - z[:, 0].sum()) / (6 * d * math.cos(math.radians(slat)))
    gy = (z[0].sum() - z[2].sum()) / (6 * d)
    return float(np.degrees(np.arctan(math.hypot(gx, gy)))), s


def great_circle(lat, lon, slat, slon):
    p1, p2 = np.radians(lat), math.radians(slat)
    dl = np.radians(lon - slon)
    a = np.sin((p1 - p2) / 2) ** 2 + np.cos(p1) * math.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * RADIUS * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def summarize(slopes, weights):
    area = float(weights.sum())
    if not slopes.size or not np.isfinite(slopes).all():
        raise SystemExit('Slope distribution has missing support')
    return dict(n=int(slopes.size), median_deg=float(np.median(slopes)),
                p95_deg=float(np.percentile(slopes, 95)), max_deg=float(np.max(slopes)),
                flat_fraction={format(t, 'g'): float(weights[slopes <= t].sum() / area) for t in THRESHOLDS},
                sampled_area_m2=area)


def compute(site, window):
    h, lat, lon, z = load_window(window)
    if not np.isfinite(h).all():
        raise SystemExit('Window has missing values')
    slat, slon = site['lat'], site['lon'] % 360.0
    landing, samples = landing_slope(h, lat, lon, slat, slon)
    slopes = native_slopes(h, lat)
    dist = great_circle(lat[:, None], lon[None, :], slat, slon)
    d = math.radians(1.0 / PPD)
    area = (RADIUS * d) ** 2 * np.cos(np.radians(lat))[:, None] * np.ones_like(h)
    if not np.isfinite(slopes[dist <= 1000]).all():
        raise SystemExit('1 km circle touches the window border')
    dists = {str(r): summarize(slopes[dist <= r], area[dist <= r]) for r in RADII}
    return landing, dists, samples, z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True)
    a = ap.parse_args()
    sites = json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8'))
    sites = sites['sites'] if isinstance(sites, dict) else sites
    site = next(s for s in sites if s['id'] == a.site)
    if abs(site['lat']) >= 60:
        raise SystemExit('Non-polar sites only')
    window = ROOT / 'data/raw/terrain_nonpolar' / f'{site["id"]}_SLDEM2015.npz'
    if not window.exists():
        fetch_window(site, window)
    landing, dists, samples, z = compute(site, window)
    dest = ROOT / 'web/data/terrain' / f'{site["id"]}.json'
    product = json.loads(dest.read_text(encoding='utf-8'))
    if product['lat'] != site['lat'] or product['lon'] != site['lon']:
        raise SystemExit('Terrain file coordinates differ from sites.json')
    res_ns = RADIUS * math.radians(1.0 / PPD)
    product['kind'] = 'nonpolar_detailed'
    product['source'] = dict(
        dem_name='SLDEM2015', resolution_m=round(res_ns, 1),
        resolution_note='512 px/deg; 59.2 m north-south, 59.2*cos(lat) m east-west on the 1737.4 km sphere.',
        url=str(z['url']), tile=str(z['tile']),
        window_path=window.relative_to(ROOT).as_posix(), window_sha256=file_sha256(window),
        download_sha256=str(z['download_sha256']),
        window_rows_cols=[int(z['row0']), int(z['col0']), *map(int, z['height_km'].shape)],
        http=json.loads(str(z['meta'])),
        label_url=str(z['url'])[:-4] + '.lbl',
        citation='Barker et al. 2016, Icarus 273, 346-355, doi:10.1016/j.icarus.2015.07.039',
        coarse_dem_sources=product['source'].get('dem_sources'),
        label='SLDEM2015 59 m (lander-scale 3x3 plane)')
    product['method'] = dict(
        slope='Least-squares vertical DEM-height plane over 3x3 native-spaced samples (1/512 deg apart); landing samples are bilinear and centred on the exact catalogue coordinate; distributions use native pixel centres.',
        slope_window_cells=3, slope_center_span_projected_m=round(2 * res_ns, 1),
        slope_footprint_projected_m=round(3 * res_ns, 1), reference_radius_m=RADIUS,
        slope_ground_scale='Simple cylindrical grid: pixel ground spacing (R+h)*dphi north-south and (R+h)*cos(phi)*dlambda east-west, with local centre height h.',
        radius_rule='Great-circle distance on the reference sphere; include native sample centres at distance <= radius.',
        percentile_rule='Unweighted sample-centre percentiles; NumPy linear interpolation.',
        flat_fraction_rule='Sum R^2*dphi*dlambda*cos(phi) for centres with slope <= threshold, divided by the summed area; no fractional boundary pixels.',
        roughness='Not computed: the 50 m roughness window used for the polar sites is narrower than one 59 m SLDEM2015 pixel.',
        thresholds_label='Reference comparisons only; not safe-landing criteria.',
        producer='pipeline/nonpolar_slope.py')
    product['landing_slope_deg'] = landing
    product['slope_by_radius_m'] = dists
    product['roughness_within_500m'] = None
    product['inputs'] = dict(producer_sha256=file_sha256(__file__),
                             sites_sha256=file_sha256(ROOT / 'web/data/sites.json'),
                             site_sha256=canonical_hash(site), relay_sha256=product['relay_box']['source_sha256'],
                             source_sha256=file_sha256(window),
                             parameters=dict(thresholds_deg=THRESHOLDS, radii_m=list(RADII), ppd=PPD,
                                             window_half_rows=HALF_ROWS, window_half_cols=HALF_COLS),
                             previous_kind='coarse_relay_comparison')
    product['inputs']['signature'] = canonical_hash(product['inputs'])
    product['verification_status'] = STATUS
    product.pop('content_sha256', None)
    product['content_sha256'] = canonical_hash(product)
    dest.write_bytes((json.dumps(product, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))   # LF on Windows
    idx_path = ROOT / 'web/data/terrain/index.json'
    idx = json.loads(idx_path.read_text(encoding='utf-8'))
    for row in idx['sites']:
        if row['id'] == site['id']:
            row['kind'] = 'nonpolar_detailed'
            row['dem_resolution_m'] = round(res_ns, 1)
    idx_path.write_bytes((json.dumps(idx, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
    print(f'{site["id"]}: landing slope {landing:.3f} deg; centre h {samples[1, 1]:.1f} m')
    for r, q in dists.items():
        print(f'  r<={r} m: n={q["n"]} median {q["median_deg"]:.2f} p95 {q["p95_deg"]:.2f} max {q["max_deg"]:.2f} '
              f'flat8 {q["flat_fraction"]["8"]:.3f} flat15 {q["flat_fraction"]["15"]:.3f}')


if __name__ == '__main__':
    sys.exit(main())
