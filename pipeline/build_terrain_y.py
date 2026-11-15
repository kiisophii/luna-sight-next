"""Task Y: native PGDA terrain descriptors and unchanged coarse relay comparisons.

Run from the repository root with --workers 4. Downloads use the validated PGDA
Range reader and atomic block cache; only coverage errors select a coarser DEM.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

import fetch_polar as fp
from fetch_polar import RADIUS, SourceCoverageError

ROOT = Path(__file__).resolve().parents[1]
STATUS = 'author_checks_only_team_verification_pending'


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.part')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def projection_scale(x, y):
    return 1 + (np.asarray(x) ** 2 + np.asarray(y) ** 2) / (4 * RADIUS ** 2)


def area_weights(x, y, res):
    """Horizontal native-pixel area represented on the reference sphere."""
    return res ** 2 / projection_scale(x, y) ** 2


def geodesic_distance(x, y, site_x, site_y):
    """Stable exact great-circle separation via stereographic chord identity."""
    denominator = np.sqrt(projection_scale(x, y) * projection_scale(site_x, site_y))
    half_chord = np.hypot(np.asarray(x) - site_x, np.asarray(y) - site_y) / (2 * RADIUS * denominator)
    return 2 * RADIUS * np.arcsin(np.clip(half_chord, 0, 1))


def native_slopes(height, x, y, res):
    """3x3 least-squares plane; NaN for incomplete derivative neighborhoods."""
    height = np.asarray(height, dtype=np.float64)
    windows = sliding_window_view(height, (3, 3))
    # Subtracting the local centre keeps height offsets out of gradient sums.
    z = windows - height[1:-1, 1:-1, None, None]
    gx = (z[..., :, 2].sum(axis=-1) - z[..., :, 0].sum(axis=-1)) / (6 * res)
    gy = (z[..., 0, :].sum(axis=-1) - z[..., 2, :].sum(axis=-1)) / (6 * res)
    scale = projection_scale(np.asarray(x)[None, 1:-1], np.asarray(y)[1:-1, None])
    scale = scale * RADIUS / (RADIUS + height[1:-1, 1:-1])
    out = np.full(height.shape, np.nan)
    values = np.degrees(np.arctan(np.hypot(gx, gy) * scale))
    values[~np.isfinite(windows).all(axis=(-1, -2))] = np.nan
    out[1:-1, 1:-1] = values
    return out


def bilinear(height, x, y, sample_x, sample_y):
    res = float(x[1] - x[0])
    col = (np.asarray(sample_x) - x[0]) / res
    row = (y[0] - np.asarray(sample_y)) / res
    col, row = np.broadcast_arrays(col, row)
    c, r = np.floor(col).astype(int), np.floor(row).astype(int)
    if np.any(c < 0) or np.any(c + 1 >= len(x)) or np.any(r < 0) or np.any(r + 1 >= len(y)):
        raise SourceCoverageError('Exact-coordinate bilinear samples exceed native window')
    dx, dy = col - c, row - r
    return ((1-dx)*(1-dy)*height[r, c] + dx*(1-dy)*height[r, c+1]
            + (1-dx)*dy*height[r+1, c] + dx*dy*height[r+1, c+1])


def landing_slope(height, x, y, site_x, site_y, res):
    offsets = np.arange(-1, 2) * res
    h = bilinear(height, x, y, site_x + offsets[None, :], site_y - offsets[:, None])
    if not np.isfinite(h).all():
        raise SourceCoverageError('Exact-coordinate 3x3 fit intersects missing native data')
    z = h - h[1, 1]
    gx = (z[:, 2].sum() - z[:, 0].sum()) / (6 * res)
    gy = (z[0].sum() - z[2].sum()) / (6 * res)
    scale = projection_scale(site_x, site_y) * RADIUS / (RADIUS + h[1, 1])
    return float(np.degrees(np.arctan(np.hypot(gx, gy) * scale)))


def roughness_rms(height, res, window_cells):
    """Local planar RMS, in bounded row batches and centred heights for stability."""
    if window_cells < 3 or window_cells % 2 != 1:
        raise ValueError('Roughness needs an odd window of at least three cells')
    height = np.asarray(height, dtype=np.float64)
    n, half = window_cells, window_cells // 2
    out = np.full(height.shape, np.nan)
    windows = sliding_window_view(height, (n, n))
    dx = (np.arange(n) - half) * float(res)
    dy = -dx
    denominator = n * np.sum(dx ** 2)
    for start in range(0, windows.shape[0], 16):
        stop = min(start + 16, windows.shape[0])
        z = windows[start:stop] - height[start+half:stop+half, half:-half, None, None]
        z = z - z.mean(axis=(-1, -2), keepdims=True)
        gx = np.sum(z * dx[None, :], axis=(-1, -2)) / denominator
        gy = np.sum(z * dy[:, None], axis=(-1, -2)) / denominator
        residual = z - gx[..., None, None] * dx[None, :] - gy[..., None, None] * dy[:, None]
        out[start+half:stop+half, half:-half] = np.sqrt(np.mean(residual ** 2, axis=(-1, -2)))
    return out


def threshold_key(value):
    return format(value, 'g')


def summarize_slopes(slopes, weights, thresholds):
    slopes, weights = np.asarray(slopes), np.asarray(weights)
    area = float(weights.sum())
    if not slopes.size or not np.isfinite(slopes).all() or not np.isfinite(weights).all() or area <= 0:
        raise SourceCoverageError('Slope distribution lacks full valid positive-area support')
    return dict(n=int(slopes.size), median_deg=float(np.median(slopes)),
                p95_deg=float(np.percentile(slopes, 95)), max_deg=float(np.max(slopes)),
                flat_fraction={threshold_key(t): float(weights[slopes <= t].sum() / area)
                               for t in thresholds}, sampled_area_m2=area)


def describe_window(height, x, y, site, res, thresholds):
    """Return method, coordinate slope, radius distributions and 500m roughness."""
    height = np.asarray(height, dtype=np.float64)
    x, y = np.asarray(x), np.asarray(y)
    if height.shape != (len(y), len(x)) or not np.allclose(np.diff(x), res) or not np.allclose(np.diff(y), -res):
        raise ValueError('Expected the original north-up square-pixel grid')
    sx, sy = fp.project(site['lat'], site['lon'])
    k = float(projection_scale(sx, sy))
    # This guarantees all circle centres and their derivative support are stored.
    # The selected 1200m projected square is deliberately larger than this bound.
    padding = 1000 * (k + .001) + 2 * res
    if min(sx-x[0], x[-1]-sx, y[0]-sy, sy-y[-1]) < padding:
        raise SourceCoverageError('Native window does not enclose the 1km circle plus derivative padding')
    slopes = native_slopes(height, x, y, res)
    distance = geodesic_distance(x[None, :], y[:, None], sx, sy)
    area = area_weights(x[None, :], y[:, None], res)
    full = distance <= 1000
    if not np.isfinite(slopes[full]).all():
        raise SourceCoverageError('1km geodesic circle contains missing 3x3 derivative support')
    distributions = {str(radius): summarize_slopes(slopes[distance <= radius], area[distance <= radius], thresholds)
                     for radius in (100, 500, 1000)}
    cells = 2 * math.floor(25 * k / res) + 1
    rough = roughness_rms(height, res, cells)
    values = rough[distance <= 500]
    if not np.isfinite(values).all():
        raise SourceCoverageError('500m geodesic circle contains incomplete roughness windows')
    rough_summary = dict(n=int(values.size), median_m=float(np.median(values)), p95_m=float(np.percentile(values, 95)))
    method = dict(
        slope='Least-squares vertical DEM-height plane over 3x3 native-spaced samples; landing samples are bilinear and centred on the exact catalogue coordinate; distributions use native pixel centres.',
        slope_window_cells=3, slope_center_span_projected_m=2*res, slope_footprint_projected_m=3*res,
        reference_radius_m=RADIUS,
        slope_ground_scale='Projected gradient multiplied by stereographic k=1+(rho/(2R))^2 and R/(R+h), with local centre height h.',
        radius_rule='Great-circle distance on the reference sphere; include native sample centres at distance <= radius.',
        percentile_rule='Unweighted sample-centre percentiles; NumPy linear interpolation.',
        flat_fraction_rule='Sum res^2/k^2 for centres with slope <= threshold, divided by summed represented horizontal area on the reference sphere; no fractional boundary pixels.',
        roughness='RMS vertical DEM-height residual about a local least-squares plane, with heights centred before fitting. DEM-derived roughness, not boulder detection or raw laser-spot roughness.',
        roughness_window_width_ground_m=50, roughness_window_cells=cells,
        roughness_sample_center_span_ground_m=(cells-1)*res/k,
        roughness_window_rule='Include native centres within +/-25m along each projected axis converted to reference-sphere ground distance using site k, held constant for all windows; odd N=2*floor(25*k/res)+1.',
        roughness_site_projection_scale=k,
        thresholds_label='Reference comparisons only; not safe-landing criteria.')
    return method, landing_slope(height, x, y, sx, sy, res), distributions, rough_summary


def relay_comparison(path, root, site):
    relay = json.loads(Path(path).read_text(encoding='utf-8'))
    if relay.get('mock') is not False or relay['lat'] != site['lat'] or relay['lon'] != site['lon']:
        raise ValueError('Relay source is mock or has mismatched coordinates')
    if relay['params']['slope_box_m'] != 250:
        raise ValueError('Expected existing 250m relay box')
    columns = relay['candidates']
    if len({len(columns[key]) for key in ('e_m', 'n_m', 'slope_deg')}) != 1:
        raise ValueError('Relay candidate columns have unequal lengths')
    centres = [i for i, (east, north) in enumerate(zip(columns['e_m'], columns['n_m'])) if east == north == 0]
    if len(centres) != 1:
        raise ValueError('Expected exactly one relay candidate at e=n=0')
    index = centres[0]
    value = columns['slope_deg'][index]
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 90:
        raise ValueError('Missing or invalid relay centre slope')
    return dict(slope_deg=value, box_m=250, source_path=Path(path).relative_to(root).as_posix(),
                source_sha256=file_sha256(path), candidate_index=index, e_m=0, n_m=0,
                provenance=dict(description='Copied existing stored rounded 250m-box slope at relay centre; not recomputed.',
                                dem_sources=relay['dem_sources'], input_identity=relay.get('input_identity'))), relay['dem_sources']


def make_inputs(site, relay_hash, source_hash, parameters):
    inputs = dict(producer_sha256=file_sha256(__file__), sites_sha256=file_sha256(ROOT / 'web/data/sites.json'),
                  site_sha256=canonical_hash(site), relay_sha256=relay_hash, source_sha256=source_hash,
                  code_sha256={name: file_sha256(ROOT / 'pipeline' / name)
                               for name in ('fetch_polar.py', 'polar_prefetch.py')}, parameters=parameters)
    inputs['signature'] = canonical_hash(inputs)
    return inputs


def is_resumable(path, inputs):
    try:
        product = json.loads(Path(path).read_text(encoding='utf-8'))
        old = product['inputs']
        signature_fields = {key: value for key, value in old.items() if key != 'signature'}
        content = {key: value for key, value in product.items() if key != 'content_sha256'}
        return (product.get('mock') is False and product.get('schema_version') == 1
                and old == inputs and old['signature'] == canonical_hash(signature_fields)
                and product.get('content_sha256') == canonical_hash(content))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def acquire(site, raw_root, thresholds):
    unavailable = []
    for res in (5, 10, 20):
        try:
            # fetch refreshes source validators before reusing cached NPZ windows.
            try:
                # Storage margins may be clipped; describe_window still requires
                # every centre in the 1km circle and its derivative support.
                fp.fetch(site, res, 1200, raw_root, allow_partial=True)
            except ValueError as error:
                if str(error) == 'Window contains no valid elevations':
                    raise SourceCoverageError(str(error)) from error
                raise
            path = raw_root / str(res) / (site['id'] + '.npz')
            with np.load(path, allow_pickle=False) as data:
                h, x, y = data['height_m'], data['x_m'], data['y_m']
                metadata = json.loads(str(data['metadata']))
            result = describe_window(h, x, y, site, res, thresholds)
        except SourceCoverageError as error:
            unavailable.append(dict(resolution_m=res, url=fp.BASE + fp.SOURCES[res][0], reason=str(error)))
            print(f'{site["id"]} {res}m unavailable: {error}', flush=True)
            continue
        source = dict(dem_name=f'PGDA_LOLA_{res}M', resolution_m=res, url=metadata['source_url'],
                      window_path=path.relative_to(ROOT).as_posix(), window_sha256=file_sha256(path),
                      metadata=metadata, finer_unavailable=unavailable)
        return source, result
    raise SourceCoverageError(f'{site["id"]}: no complete original 5/10/20m source: {unavailable}')


def build_site(site, raw_root, output, thresholds):
    started = time.perf_counter()
    box, dem_sources = relay_comparison(ROOT / 'web/data/relay' / (site['id'] + '.json'), ROOT, site)
    parameters = dict(thresholds_deg=thresholds, thresholds_label='reference_only',
                      radii_m=[100, 500, 1000], roughness_radius_m=500, roughness_window_width_ground_m=50,
                      projected_storage_radius_m=1200, resolution_preference_m=[5, 10, 20])
    source, result = (dict(dem_sources=dem_sources, label='coarse (SLDEM2015 59 m / LDEM_64)'), (None,) * 4)
    kind = 'coarse_relay_comparison'
    if site['lat'] <= -75:
        source, result = acquire(site, raw_root, thresholds)
        kind = 'polar_detailed'
    source_hash = source.get('window_sha256', canonical_hash(source))
    # Coverage diagnostics and validators participate alongside actual raster bytes.
    parameters['source_metadata_sha256'] = canonical_hash(source)
    inputs = make_inputs(site, box['source_sha256'], source_hash, parameters)
    dest = output / (site['id'] + '.json')
    resumed = is_resumable(dest, inputs)
    if not resumed:
        method, landing, slopes, roughness = result
        product = dict(schema_version=1, id=site['id'], lat=site['lat'], lon=site['lon'], frame='MOON_ME_DE421',
                       kind=kind, mock=False, thresholds_deg=thresholds, thresholds_label='reference_only',
                       source=source, method=method, landing_slope_deg=landing, slope_by_radius_m=slopes,
                       roughness_within_500m=roughness, relay_box=box, inputs=inputs, verification_status=STATUS)
        product['content_sha256'] = canonical_hash(product)
        atomic_json(dest, product)
    elapsed = time.perf_counter() - started
    print(f'{site["id"]}: {"resumed" if resumed else "written"} {kind} in {elapsed:.2f}s', flush=True)
    return dict(id=site['id'], path=dest.name, kind=kind, dem_resolution_m=source.get('resolution_m')), dict(
        id=site['id'], seconds=elapsed, resumed=resumed, dem_resolution_m=source.get('resolution_m'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', help='Generate one catalogue site; index is written only for a full run')
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 7), help='Bounded parallel Range downloads (CPU remains serial)')
    parser.add_argument('--thresholds-deg', type=float, nargs='+', default=[8, 15])
    args = parser.parse_args()
    thresholds = sorted(set(args.thresholds_deg))
    if not thresholds or any(not math.isfinite(t) or not 0 < t < 90 for t in thresholds):
        parser.error('Reference thresholds must be finite degrees strictly between 0 and 90')
    import polar_prefetch
    polar_prefetch.install(args.workers)
    sites = json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8'))
    if args.site:
        sites = [site for site in sites if site['id'] == args.site]
    if not sites:
        parser.error('No matching catalogue site')
    raw_root, output = ROOT / 'data/processed/terrain_y/raw', ROOT / 'web/data/terrain'
    started = time.perf_counter()
    runtime = dict(started_utc=datetime.now(timezone.utc).isoformat(), workers=args.workers, cpu_workers=1, sites=[])
    entries = []
    for site in sites:
        entry, timing = build_site(site, raw_root, output, thresholds)
        entries.append(entry)
        runtime['sites'].append(timing)
        runtime['elapsed_seconds'] = time.perf_counter() - started
        atomic_json(ROOT / 'data/processed/terrain_y/run.json', runtime)
    if not args.site:
        atomic_json(output / 'index.json', dict(schema_version=1, mock=False, thresholds_deg=thresholds,
                                               thresholds_label='reference_only', sites=entries))
    print(f'Task Y: {len(entries)} site(s), {time.perf_counter()-started:.2f}s', flush=True)


if __name__ == '__main__':
    main()
