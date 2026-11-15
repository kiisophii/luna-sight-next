"""Separate Task Y author check; never imports the producer's numerical code.

Run from the repository root with the original small PGDA NPZ windows present.
This is Jiyong's author verification, NOT another team member's verification.
"""
import os

# Bound BLAS before importing NumPy; desktop simulations may run concurrently.
for _variable in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[_variable] = '1'

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import unittest

import numpy as np

RADIUS = 1737400.0
DEFAULT_SITES = ['SHACKLETON_RIM', 'ARTEMIS_MALAPERT', 'IM1']


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def project_site(lat, lon):
    """Analytic spherical south-polar stereographic forward projection."""
    rho = 2*RADIUS*np.tan((np.deg2rad(lat) + np.pi/2)/2)
    return rho*np.sin(np.deg2rad(lon)), rho*np.cos(np.deg2rad(lon))


def spherical_distances(x, y, site_lat, site_lon):
    """Invert stereographic coordinates; use haversine on the reference sphere."""
    lat = -np.pi/2 + 2*np.arctan(np.hypot(x, y)/(2*RADIUS))
    lon = np.arctan2(x, y)
    lat0, lon0 = np.deg2rad([site_lat, site_lon])
    hav = np.sin((lat-lat0)/2)**2 + np.cos(lat)*np.cos(lat0)*np.sin((lon-lon0)/2)**2
    return 2*RADIUS*np.arcsin(np.sqrt(np.clip(hav, 0, 1)))


def bilinear(z, x, y, query_x, query_y):
    """Bilinear interpolation in ascending or descending regular axes."""
    col = (np.asarray(query_x)-x[0])/(x[1]-x[0])
    row = (np.asarray(query_y)-y[0])/(y[1]-y[0])
    if np.any((col < 0) | (row < 0) | (col > len(x)-1) | (row > len(y)-1)):
        raise ValueError('Bilinear query outside original DEM')
    c = np.clip(np.floor(col).astype(int), 0, len(x)-2)
    r = np.clip(np.floor(row).astype(int), 0, len(y)-2)
    u, v = col-c, row-r
    result = ((1-v)*((1-u)*z[r, c]+u*z[r, c+1])
              + v*((1-u)*z[r+1, c]+u*z[r+1, c+1]))
    if not np.isfinite(result).all():
        raise ValueError('Invalid original DEM in bilinear query')
    return result


def fit_centres(z, x, y, centres, side, batch_size=1024):
    """Explicit least squares against each native neighbourhood's height vector.

    A shared design matrix has local metre coordinates (including y-axis sign).
    Each batch supplies many independent right-hand sides to numpy.linalg.lstsq.
    Residual RMS comes from explicit fitted heights, not summed moments.
    """
    half = side//2
    if side < 3 or side % 2 != 1:
        raise ValueError('An odd plane window of at least 3 samples is required')
    offsets = np.arange(-half, half+1)
    dc, dr = np.meshgrid(offsets, offsets)
    design = np.column_stack((dc.ravel()*(x[1]-x[0]),
                              dr.ravel()*(y[1]-y[0]), np.ones(side*side)))
    coeff = np.empty((len(centres), 3), dtype=float)
    rms = np.empty(len(centres), dtype=float)
    for start in range(0, len(centres), batch_size):
        chunk = centres[start:start+batch_size]
        rows, cols = chunk[:, 0, None]+dr.ravel(), chunk[:, 1, None]+dc.ravel()
        if np.any((rows < 0) | (rows >= len(y)) | (cols < 0) | (cols >= len(x))):
            raise ValueError('Required plane window extends outside original DEM')
        samples = z[rows, cols]
        if not np.isfinite(samples).all():
            raise ValueError('Invalid DEM in required plane window')
        origin = z[chunk[:, 0], chunk[:, 1]]
        centered = samples-origin[:, None]
        fitted, _, rank, _ = np.linalg.lstsq(design, centered.T, rcond=None)
        if rank != 3:
            raise ValueError('Rank-deficient plane design')
        residual = centered.T-design@fitted
        count = len(chunk)
        coeff[start:start+count] = fitted.T
        coeff[start:start+count, 2] += origin
        rms[start:start+count] = np.sqrt(np.mean(residual**2, axis=0))
    return coeff, rms


def physical_slope(a, b, x, y, height):
    scale = 1+(np.hypot(x, y)/(2*RADIUS))**2
    return np.rad2deg(np.arctan(np.hypot(a, b)*scale*RADIUS/(RADIUS+height)))


def circle_summary(slope, distance, area, radius, thresholds):
    inside = distance <= radius
    values, weights = slope[inside], area[inside]
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('No valid slope sample or invalid slope in circle')
    return dict(n=int(len(values)), median_deg=float(np.median(values)),
                p95_deg=float(np.percentile(values, 95)), max_deg=float(np.max(values)),
                flat_fraction={str(t): float(weights[values <= t].sum()/weights.sum())
                               for t in thresholds}, sampled_area_m2=float(weights.sum()))


def independent_site(site, product, root):
    path = Path(product['source']['window_path'])
    if not path.is_absolute():
        path = root/path
    source_hash = sha256(path)
    if source_hash != product['source']['window_sha256']:
        raise ValueError(f'{site["id"]}: original DEM hash mismatch')
    with np.load(path, allow_pickle=False) as archive:
        z = np.asarray(archive['height_m'], dtype=float)
        x, y = np.asarray(archive['x_m'], dtype=float), np.asarray(archive['y_m'], dtype=float)
        metadata = json.loads(str(archive['metadata']))
    res = float(product['source']['resolution_m'])
    if (metadata['reference_radius_m'] != RADIUS or metadata['frame'] != 'MOON_ME_DE421'
            or metadata['pixel_registration'] != 'center' or metadata['units'] != 'm'
            or product['method']['reference_radius_m'] != RADIUS):
        raise ValueError('Original DEM or output has a different reference radius/frame/registration/unit')
    method = product['method']
    if (method['slope_window_cells'] != 3 or method['slope_center_span_projected_m'] != 2*res
            or method['slope_footprint_projected_m'] != 3*res
            or method['roughness_window_width_ground_m'] != 50):
        raise ValueError('Output native window descriptors differ from the specified method')
    if (z.shape != (len(y), len(x)) or not np.allclose(np.diff(x), res)
            or not np.allclose(np.abs(np.diff(y)), res)
            or metadata['resolution_m'] != res):
        raise ValueError('Source grid is inconsistent with native resolution')
    if metadata['site']['lat'] != site['lat'] or metadata['site']['lon'] != site['lon']:
        raise ValueError('Raw DEM metadata has a different site coordinate')
    xx, yy = np.meshgrid(x, y)
    distance_grid = spherical_distances(xx, yy, site['lat'], site['lon'])
    centres = np.argwhere(distance_grid <= 1000)
    coefficients, _ = fit_centres(z, x, y, centres, 3)
    rows, cols = centres.T
    cx, cy, ch = xx[rows, cols], yy[rows, cols], z[rows, cols]
    slope = physical_slope(coefficients[:, 0], coefficients[:, 1], cx, cy, ch)
    k = 1+(np.hypot(cx, cy)/(2*RADIUS))**2
    distance = distance_grid[rows, cols]
    area = res**2/k**2
    thresholds = product['thresholds_deg']
    circles = {str(radius): circle_summary(slope, distance, area, radius, thresholds)
               for radius in (100, 500, 1000)}
    sx, sy = project_site(site['lat'], site['lon'])
    # Exact-coordinate 3x3 samples: original DEM bilinear interpolation only.
    qx, qy = np.meshgrid(sx+np.arange(-1, 2)*res, sy+np.arange(-1, 2)*res)
    sample_z = bilinear(z, x, y, qx, qy)
    design = np.column_stack(((qx-sx).ravel(), (qy-sy).ravel(), np.ones(9)))
    fitted = np.linalg.lstsq(design, (sample_z-sample_z[1, 1]).ravel(), rcond=None)[0]
    landing = float(physical_slope(fitted[0], fitted[1], sx, sy, sample_z[1, 1]))
    site_scale = 1+(np.hypot(sx, sy)/(2*RADIUS))**2
    rough_side = 2*int(np.floor(25*site_scale/res))+1
    rough_centres = centres[distance <= 500]
    _, residual_rms = fit_centres(z, x, y, rough_centres, rough_side)
    roughness = dict(n=len(residual_rms), median_m=float(np.median(residual_rms)),
                     p95_m=float(np.percentile(residual_rms, 95)))
    span = (rough_side-1)*res/site_scale
    return dict(landing_slope_deg=landing, slope_by_radius_m=circles,
                roughness_within_500m=roughness, roughness_window_cells=rough_side,
                roughness_sample_center_span_ground_m=float(span),
                resolution_m=res, source_path=str(path), source_sha256=source_hash,
                source_radius_frame_registration_units_match=True,
                source_url=metadata['source_url'], source_metadata=metadata,
                grid_shape=list(z.shape), landing_height_m=float(sample_z[1, 1]))


def compare_site(site, product, independent):
    degree_differences = {'landing': abs(independent['landing_slope_deg']-product['landing_slope_deg'])}
    flat_differences = {}
    counts_equal = True
    area_differences = {}
    for radius, actual in independent['slope_by_radius_m'].items():
        saved = product['slope_by_radius_m'][radius]
        counts_equal &= actual['n'] == saved['n']
        for metric in ('median_deg', 'p95_deg', 'max_deg'):
            degree_differences[f'{radius}.{metric}'] = abs(actual[metric]-saved[metric])
        for threshold, fraction in actual['flat_fraction'].items():
            flat_differences[f'{radius}.{threshold}'] = abs(fraction-saved['flat_fraction'][threshold])*100
        area_differences[radius] = abs(actual['sampled_area_m2']-saved['sampled_area_m2'])
    rough_actual, rough_saved = independent['roughness_within_500m'], product['roughness_within_500m']
    counts_equal &= rough_actual['n'] == rough_saved['n']
    rough_delta = {key: abs(rough_actual[key]-rough_saved[key]) for key in ('median_m', 'p95_m')}
    method = product['method']
    window_equal = method['roughness_window_cells'] == independent['roughness_window_cells']
    span_delta = abs(method['roughness_sample_center_span_ground_m']
                     - independent['roughness_sample_center_span_ground_m'])
    max_deg, max_pp = max(degree_differences.values()), max(flat_differences.values())
    return dict(id=site['id'], independent=independent,
                producer={key: product[key] for key in ('landing_slope_deg', 'slope_by_radius_m', 'roughness_within_500m')},
                slope_abs_difference_deg=degree_differences, flat_abs_difference_pp=flat_differences,
                max_slope_abs_difference_deg=max_deg, max_flat_abs_difference_pp=max_pp,
                roughness_abs_difference_m=rough_delta, roughness_tolerance=None,
                roughness_note='Actual differences reported; no formal roughness tolerance was specified.',
                counts_equal=bool(counts_equal), roughness_window_cells_equal=window_equal,
                roughness_sample_center_span_abs_difference_m=span_delta,
                sampled_area_abs_difference_m2=area_differences,
                passed=bool(max_deg <= 0.5 and max_pp <= 1 and counts_equal and window_equal and span_delta < 1e-6))


def check_all_relay_centres(root, sites):
    checks = []
    for site in sites:
        product_path = root/'web/data/terrain'/f'{site["id"]}.json'
        product = read_json(product_path)
        relay_path = root/'web/data/relay'/f'{site["id"]}.json'
        relay = read_json(relay_path)
        candidates = relay['candidates']
        indices = [i for i, (east, north) in enumerate(zip(candidates['e_m'], candidates['n_m']))
                   if east == 0 and north == 0]
        if len(indices) != 1:
            raise ValueError(f'{site["id"]}: expected exactly one relay centre')
        index = indices[0]
        slope = candidates['slope_deg'][index]
        box = product['relay_box']
        detailed_keys = ('method', 'landing_slope_deg', 'slope_by_radius_m', 'roughness_within_500m')
        coarse = site['lat'] > -75
        tests = dict(id_equal=product['id'] == site['id'],
                     coordinates_equal=(product['lat'], product['lon']) == (site['lat'], site['lon']),
                     centre_index_equal=box['candidate_index'] == index,
                     centre_offsets_zero=box['e_m'] == box['n_m'] == 0,
                     slope_exact_equal=box['slope_deg'] == slope,
                     stored_one_decimal=abs(slope*10-round(slope*10)) < 1e-9,
                     source_sha256_equal=box['source_sha256'] == sha256(relay_path),
                     input_relay_sha256_equal=product['inputs']['relay_sha256'] == sha256(relay_path),
                     input_producer_sha256_equal=product['inputs']['producer_sha256'] == sha256(root/'pipeline/build_terrain_y.py'),
                     input_sites_sha256_equal=product['inputs']['sites_sha256'] == sha256(root/'web/data/sites.json'),
                     source_path_equal=(root/box['source_path']).resolve() == relay_path.resolve(),
                     box_m_equal=box['box_m'] == relay['params']['slope_box_m'] == 250,
                     kind_equal=product['kind'] == ('coarse_relay_comparison' if coarse else 'polar_detailed'),
                     nonpolar_details_null=not coarse or all(product[key] is None for key in detailed_keys),
                     human_verification_pending=product['verification_status'] == 'author_checks_only_team_verification_pending')
        checks.append(dict(id=site['id'], candidate_index=index, stored_slope_deg=slope,
                           relay_sha256=sha256(relay_path), product_sha256=sha256(product_path),
                           tests=tests, passed=all(tests.values())))
    return checks


def run_fixtures():
    tests = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_verify_terrain_y.py')
    result = unittest.TextTestRunner(verbosity=1).run(tests)
    if not result.wasSuccessful():
        raise RuntimeError('Independent analytic fixtures failed')
    return dict(tests_run=result.testsRun, passed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--sites', nargs='+', default=DEFAULT_SITES)
    parser.add_argument('--report', type=Path, default=Path('data/processed/terrain_y/verification.json'))
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    fixtures = run_fixtures()
    if args.self_test:
        return 0
    root = args.root.resolve()
    sites_path = root/'web/data/sites.json'
    sites = read_json(sites_path)
    site_map = {site['id']: site for site in sites}
    report = dict(schema_version=1, verification_status='author_checks_only_team_verification_pending',
                  verifier_member='Jiyong', human_other_member_verification=False,
                  method='Independent original-DEM bilinear samples and batched explicit numpy.linalg.lstsq planes; analytic spherical stereographic inversion and haversine; explicit residual RMS.',
                  thresholds=dict(slope_max_abs_difference_deg=0.5, flat_max_abs_difference_pp=1),
                  generated_utc=datetime.now(timezone.utc).isoformat(), fixtures=fixtures,
                  hashes=dict(verifier_sha256=sha256(__file__),
                              verifier_test_sha256=sha256(Path(__file__).with_name('test_verify_terrain_y.py')),
                              producer_sha256=sha256(root/'pipeline/build_terrain_y.py'),
                              sites_sha256=sha256(sites_path)), sites=[],
                  limitations=['Same original PGDA rasters; checks the implementation, not the true physical terrain or source vertical accuracy.',
                               'Three detailed sites checked numerically; all catalogue relay centres checked exactly.',
                               'Another human team member verification remains pending.'])
    for site_id in args.sites:
        site = site_map[site_id]
        product_path = root/'web/data/terrain'/f'{site_id}.json'
        product = read_json(product_path)
        calculated = independent_site(site, product, root)
        checked = compare_site(site, product, calculated)
        checked['product_sha256'] = sha256(product_path)
        report['sites'].append(checked)
        print(f'{site_id}: {calculated["resolution_m"]:g} m, slope max {checked["max_slope_abs_difference_deg"]:.12g} deg, flat max {checked["max_flat_abs_difference_pp"]:.12g} pp', flush=True)
    report['relay_centres'] = check_all_relay_centres(root, sites)
    report['max_slope_abs_difference_deg'] = max(item['max_slope_abs_difference_deg'] for item in report['sites'])
    report['max_flat_abs_difference_pp'] = max(item['max_flat_abs_difference_pp'] for item in report['sites'])
    report['max_roughness_abs_difference_m'] = max(max(item['roughness_abs_difference_m'].values()) for item in report['sites'])
    report['passed'] = all(item['passed'] for item in report['sites']+report['relay_centres'])
    report['elapsed_seconds'] = time.perf_counter()-started
    report_path = args.report if args.report.is_absolute() else root/args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(report_path)
    print(f'{"PASS" if report["passed"] else "FAIL"}: {len(report["relay_centres"])} relay centres; {report_path}', flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
