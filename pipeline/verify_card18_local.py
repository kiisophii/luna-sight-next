"""Independent Card 18 check: PROJ/ECEF full rays and hourly NumPy metrics.

No production horizon, local-map, relay geometry, or core.js code is imported.
The independent Card 13 reader and geometry helpers are reused. This checks
numerical implementation on the same terrain, not physical DEM accuracy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np

from verify_card13_relay import DEM, GEOD, RADIUS, bilinear, body_angles, trace_mask

ROOT = Path(__file__).resolve().parents[1]
SITE_IDS = tuple(sorted(('SHACKLETON_RIM', 'ARTEMIS_HAWORTH', 'ARTEMIS_MALAPERT',
                         'CONNECTING_RIDGE', 'PEAK_NEAR_SHACKLETON', 'DE_GERLACHE_RIM1')))
GATES_KM = {5: 3, 10: 25, 20: 25, 60: 60, 80: 60, 240: 200}
SEED = 20261114
FRACTIONS = ('sun_frac', 'earth_frac', 'both_frac')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def select_points(seed=SEED, count=5):
    """Uniform sample without replacement over sorted IDs then row-major nodes."""
    return random.Random(seed).sample([(site, index) for site in SITE_IDS
                                       for index in range(441)], count)


class PointDEM(DEM):
    """Read centre-ID windows, but anchor source gates on the selected observer."""
    def __init__(self, center, point, raw):
        super().__init__(center, raw, 300.)
        self.lat, self.lon = point['lat'], point['lon']
        self.fine_missing = 0
        self.fine_checked = 0
        for source in self.sources:
            if source['kind'] == 'polar':
                resolution = int(Path(source['path']).parent.name)
                source['max_km'] = GATES_KM[resolution]
                source['resolution_m'] = resolution
            else:
                source['max_km'] = None

    def __call__(self, lat, lon):
        lat, lon = np.asarray(lat), np.asarray(lon)
        _, _, distance = GEOD.inv(np.full(lat.shape, self.lon), np.full(lat.shape, self.lat), lon, lat)
        near = distance <= 3000 + 1e-6
        self.fine_checked += int(near.sum())
        fine = next((s for s in self.sources if s.get('resolution_m') == 5), None)
        if fine is None:
            self.fine_missing += int(near.sum())
        elif near.any():
            x, y = fine['project'](lon[near], lat[near])
            values = bilinear(fine['array'], (fine['y0']-y)/fine['dy'], (x-fine['x0'])/fine['dx'])
            self.fine_missing += int((~np.isfinite(values)).sum())
        return super().__call__(lat, lon)


def horizon_at(mask, azimuth):
    position = np.asarray(azimuth, dtype=float) % 360 / .5
    lower = np.floor(position).astype(int)
    weight = position - lower
    return np.asarray(mask)[lower] * (1-weight) + np.asarray(mask)[(lower+1) % 720] * weight


def longest_dark_run(sunlit):
    padded = np.r_[False, ~np.asarray(sunlit, dtype=bool), False].astype(int)
    changes = np.diff(padded)
    lengths = np.flatnonzero(changes == -1) - np.flatnonzero(changes == 1)
    return int(lengths.max(initial=0))


def evaluate_metrics(lat, lon, ground, mask, ephem):
    sun_az, sun_el = body_angles(lat, lon, ground + 2, ephem[:, :3])
    earth_az, earth_el = body_angles(lat, lon, ground + 2, ephem[:, 3:])
    # Symmetric solar disk fraction >= 0.5 iff its centre is on/above the mask.
    sunlit = sun_el >= horizon_at(mask, sun_az)
    earth = earth_el > horizon_at(mask, earth_az)
    return dict(sun_frac=float(sunlit.mean()), earth_frac=float(earth.mean()),
                both_frac=float((sunlit & earth).mean()), longest_dark_h=longest_dark_run(sunlit))


def compare_metrics(independent, reported):
    result = {}
    for key in FRACTIONS:
        difference = 100 * (independent[key] - reported[key])
        result[key] = dict(independent=independent[key], reported=reported[key],
                           difference_pp=difference, absolute_difference_pp=abs(difference),
                           passed=bool(abs(difference) <= 1 + 1e-12))
    difference = independent['longest_dark_h'] - reported['longest_dark_h']
    result['longest_dark_h'] = dict(independent=independent['longest_dark_h'],
        reported=reported['longest_dark_h'], difference_h=difference,
        absolute_difference_h=abs(difference), criterion='reported only; no tolerance specified')
    result['passed'] = all(result[key]['passed'] for key in FRACTIONS)
    return result


def check_sources(terrain, manifest, repo_root):
    expected = {(repo_root / item['path']).resolve(): item for item in manifest}
    actual = {Path(source['path']).resolve() for source in terrain.sources}
    if len(expected) != len(manifest) or actual != set(expected):
        raise ValueError('terrain source set differs from public output provenance')
    verified = []
    for source in terrain.sources:
        path = Path(source['path']).resolve()
        item = expected[path]
        digest = sha256(path)
        if digest != item['sha256']:
            raise ValueError(f'terrain hash differs: {path}')
        if item['gate_km'] != source['max_km']:
            raise ValueError(f'terrain range gate differs: {path}')
        entry = dict(path=item['path'], sha256=digest, gate_km=source['max_km'])
        if source['kind'] == 'global':
            label_digest = sha256(path.with_suffix('.lbl'))
            if item.get('label_sha256', label_digest) != label_digest:
                raise ValueError(f'global label hash differs: {path}')
            entry['label_sha256'] = label_digest
        verified.append(entry)
    return verified


def load_ephemeris(web_data):
    meta = json.loads((web_data / 'ephem.json').read_text(encoding='utf-8'))
    required = dict(start='2026-01-01T00:00:00Z', n=43824, step_h=1,
                    frame='MOON_ME_DE421', units='km', mock=False)
    if any(meta.get(key) != value for key, value in required.items()):
        raise ValueError('ephemeris window/frame must be exact non-mock hourly 2026-2030')
    values = np.fromfile(web_data / 'ephem.bin', dtype='<f4')
    if values.size != 43824 * 6 or not np.isfinite(values).all():
        raise ValueError('ephemeris must contain exactly 43824 finite rows of six float32 values')
    return values.reshape(43824, 6).astype(float)


def load_maps(web_data):
    records = {}
    for site in SITE_IDS:
        path = web_data / 'local' / (site + '.json')
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('mock') is not False or record.get('complete') is not True or record.get('id') != site:
            raise ValueError(f'{site}: incomplete, mock, or wrong-ID local map')
        if (record.get('frame') != 'MOON_ME_DE421' or record.get('radius_m') != RADIUS
                or record.get('window') != dict(start='2026-01-01T00:00:00Z', n=43824, step_h=1)):
            raise ValueError(f'{site}: wrong frame, reference sphere, or ephemeris window')
        params = dict(min_km=.005, max_km=300, n_steps=8000, obs_height_m=2)
        if any(record.get('params', {}).get(key) != value for key, value in params.items()):
            raise ValueError(f'{site}: wrong horizon parameters')
        grid = record['grid']
        expected = dict(rows=21, cols=21, spacing_m=1000, origin_e_m=-10000, origin_n_m=-10000)
        if any(grid.get(key) != value for key, value in expected.items()) or len(record['points']) != 441:
            raise ValueError(f'{site}: expected 21x21 grid at 1 km spacing')
        for index, point in enumerate(record['points']):
            east, north = (index % 21 - 10)*1000, (index // 21 - 10)*1000
            if (point['index'], point['e_m'], point['n_m']) != (index, east, north):
                raise ValueError(f'{site}: grid points are not south-to-north row-major')
            longitude, latitude, _ = GEOD.fwd(record['center']['lon'], record['center']['lat'],
                float(np.degrees(np.arctan2(east, north))), float(np.hypot(east, north)))
            _, _, error = GEOD.inv(longitude, latitude, point['lon'], point['lat'])
            if not np.isfinite(error) or abs(error) > .001:
                raise ValueError(f'{site}/{index}: coordinate differs from geodesic grid by >1 mm')
            for key in (*FRACTIONS, 'longest_dark_h', 'h0_m'):
                if not np.isfinite(point[key]):
                    raise ValueError(f'{site}/{index}: non-finite {key}')
            if any(not 0 <= point[key] <= 1 for key in FRACTIONS):
                raise ValueError(f'{site}/{index}: fractions outside 0..1')
            if (point['both_frac'] > min(point['sun_frac'], point['earth_frac']) + 1e-12
                    or not 0 <= point['longest_dark_h'] <= 43824
                    or int(point['longest_dark_h']) != point['longest_dark_h']):
                raise ValueError(f'{site}/{index}: inconsistent metrics')
        records[site] = record
    return records


def check_output_inputs(record, repo_root):
    for path, expected in record['provenance']['files_sha256'].items():
        if sha256(repo_root/path) != expected:
            raise ValueError(f'production input hash differs from public map: {path}')


def verify_point(site, index, record, ephem, raw, repo_root):
    started = time.monotonic()
    point = record['points'][index]
    center = dict(id=site, **record['center'])
    terrain = PointDEM(center, point, raw)
    sources = check_sources(terrain, record['provenance']['terrain_sources'], repo_root)
    ground = float(terrain(np.array([point['lat']]), np.array([point['lon']]))[0])
    if not np.isfinite(ground):
        raise ValueError(f'{site}/{index}: missing ground terrain')
    mask = trace_mask(point['lat'], point['lon'], ground, 2., terrain,
                      np.arange(720)*.5, np.geomspace(5., 300000., 8001))
    metrics = evaluate_metrics(point['lat'], point['lon'], ground, mask, ephem)
    comparison = compare_metrics(metrics, point)
    return dict(id=site, index=index, e_m=point['e_m'], n_m=point['n_m'],
        lat=point['lat'], lon=point['lon'], independent_ground_m=ground,
        reported_ground_m=point['h0_m'], ground_difference_m=ground-point['h0_m'],
        independent_mask_sha256=hashlib.sha256(np.asarray(mask, dtype='<f8').tobytes()).hexdigest(),
        sources=sources, fine_5m_gate_samples=terrain.fine_checked,
        fine_5m_missing_samples_falling_back=terrain.fine_missing,
        final_missing_terrain_samples=0, comparison=comparison, passed=comparison['passed'],
        elapsed_s=round(time.monotonic()-started, 3))


def save_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=ROOT/'data/processed/card18/raw')
    parser.add_argument('--web-data', type=Path, default=ROOT/'web/data')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/card18_validation.json')
    args = parser.parse_args(argv)
    ephem = load_ephemeris(args.web_data)
    records = load_maps(args.web_data)
    for record in records.values():
        check_output_inputs(record, ROOT)
    selected = select_points()
    identity = dict(ephem_bin_sha256=sha256(args.web_data/'ephem.bin'),
        ephem_metadata_sha256=sha256(args.web_data/'ephem.json'),
        verifier_sha256=sha256(Path(__file__)),
        independent_helpers_sha256=sha256(Path(__file__).with_name('verify_card13_relay.py')),
        output_sha256={site: sha256(args.web_data/'local'/(site+'.json')) for site in SITE_IDS})
    report = dict(method='Independent Card 13 DEM reader, PROJ geodesics, ECEF brute-force rays, NumPy full-window metrics; no production geometry imports or early stop',
        criterion='Each sun_frac, earth_frac, both_frac difference <= 1 percentage point; dark-run difference reported without pass threshold',
        limitation='Same-source numerical implementation check, not DEM physical accuracy or a statistical bound on all grid nodes',
        seed=SEED, sampling='Python random.Random(seed).sample without replacement; sorted six IDs then row-major indices 0..440',
        population_n=2646, sample_n=5, selected=[dict(id=site, index=index) for site, index in selected],
        parameters=dict(radius_m=RADIUS, observer_height_m=2, azimuth_bins=720, azimuth_step_deg=.5,
            min_distance_m=5, max_distance_m=300000, distances_n=8001, distance_spacing='geomspace',
            range_gates_km=GATES_KM, global_range_gate=None, epochs=43824,
            start='2026-01-01T00:00:00Z', step_h=1),
        fallback_policy='Missing/out-of-source 5 m samples fall through to coarser DEM; final missing samples abort',
        quantization='Production h0 rounds to 0.01 m and mask to 0.0001 deg; independent metrics retain full precision',
        identity=identity, points=[], complete=False, passed=False,
        started_utc=datetime.now(timezone.utc).isoformat())
    # A completed point is reused only if source bytes and all output/code bytes agree.
    previous = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {}
    if previous.get('identity') == identity and previous.get('selected') == report['selected']:
        for entry in previous.get('points', []):
            if all(sha256(ROOT/item['path']) == item['sha256'] and
                   ('label_sha256' not in item or sha256((ROOT/item['path']).with_suffix('.lbl')) == item['label_sha256'])
                   for item in entry['sources']):
                report['points'].append(entry)
    save_report(args.output, report)
    for site, index in selected:
        if any(point['id'] == site and point['index'] == index for point in report['points']):
            continue
        print(f'{site}/{index}: independently tracing all 720 rays', flush=True)
        result = verify_point(site, index, records[site], ephem, args.raw, ROOT)
        report['points'].append(result)
        save_report(args.output, report)
        print(json.dumps(dict(id=site, index=index, passed=result['passed'],
                              comparison=result['comparison'], elapsed_s=result['elapsed_s'])), flush=True)
    report['complete'] = len(report['points']) == 5
    report['passed'] = report['complete'] and all(point['passed'] for point in report['points'])
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save_report(args.output, report)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
