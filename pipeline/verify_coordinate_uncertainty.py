"""Independent Card 23 audit: full ECEF rays and actual hourly ephemeris.

No production horizon, local_maps, coordinate_uncertainty, or core.js imports.
This checks numerical agreement on the same DEMs, not physical terrain accuracy.
"""
from __future__ import annotations

import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS'):
    os.environ[_name] = '1'

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np

from verify_card13_relay import DEM, GEOD, RADIUS, trace_mask
from verify_card18_local import compare_metrics, evaluate_metrics, load_ephemeris, save_report, sha256

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261114
SAMPLE_IDS = ('SHACKLETON_RIM', 'ARTEMIS_HAWORTH', 'IM2')
FRACTIONS = ('sun_frac', 'earth_frac', 'both_frac')
METRICS = (*FRACTIONS, 'longest_dark_h')
WINDOW = dict(start='2026-01-01T00:00:00Z', step_h=1, n=43824)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def select_points(seed=SEED, count_each=5):
    rng = random.Random(seed)
    return [(site, index) for site in SAMPLE_IDS for index in rng.sample(range(121), count_each)]


def linear_quantile(values, probability):
    """Explicit order-statistic interpolation, independent of production np.quantile."""
    ordered = sorted(values)
    position = (len(ordered)-1)*probability
    lower = int(position)
    weight = position-lower
    return ordered[lower] + weight*(ordered[min(lower+1, len(ordered)-1)]-ordered[lower])


def check_statistics(record):
    if set(record['ranges']) != {'100', '300', '500'}:
        raise ValueError('expected precisely the three circular radius summaries')
    for radius, count in ((100, 5), (300, 29), (500, 81)):
        points = [p for p in record['nodes'] if p['e_m']**2+p['n_m']**2 <= radius**2]
        summary = record['ranges'][str(radius)]
        if len(points) != count or summary.get('n_nodes') != count:
            raise ValueError(f'{radius} m summary has wrong circle membership/count')
        for metric in METRICS:
            values = [p[metric] for p in points]
            expected = dict(min=min(values), max=max(values), p10=linear_quantile(values, .1),
                            median=linear_quantile(values, .5), p90=linear_quantile(values, .9))
            if set(summary[metric]) != set(expected) or any(
                    not np.isfinite(summary[metric][key]) or
                    not np.isclose(summary[metric][key], value, rtol=1e-14, atol=1e-14)
                    for key, value in expected.items()):
                raise ValueError(f'{radius} m {metric}: incorrect spatial statistics')


def legacy_params(horizon):
    return dict(min_km=horizon['engine']['min_km'], max_km=horizon['engine']['max_km'],
                n_steps=horizon['engine']['n_steps'], obs_height_m=horizon['obs_height_m'],
                early_stop=horizon['engine']['early_stop'], hmax_m=horizon['engine']['hmax_m'])


def source_name(item):
    path = Path(item['path'])
    if path.suffix == '.img':
        return 'LDEM_'+path.stem.split('_')[1]
    if path.parent.name == 'sldem':
        return 'SLDEM2015'
    return 'PGDA_LOLA_'+path.parent.name+'M'


def check_record(record, site, baseline, baseline_hash, horizon):
    sid = site['id']
    if (horizon.get('mock') is not False or horizon.get('id') != sid
            or horizon.get('lat') != site['lat'] or horizon.get('lon') != site['lon']
            or horizon.get('obs_height_m') != 2 or horizon.get('az_step_deg') != .5):
        raise ValueError(f'{sid}: wrong legacy horizon identity/observer geometry')
    if record.get('id') != sid or record.get('complete') is not True or record.get('mock') is not False:
        raise ValueError(f'{sid}: wrong ID, mock, or incomplete output')
    center = dict(lat=site['lat'], lon=site['lon'])
    if (record.get('center') != center or record.get('frame') != 'MOON_ME_DE421'
            or record.get('radius_m') != RADIUS or record.get('window') != WINDOW
            or record.get('params') != legacy_params(horizon)):
        raise ValueError(f'{sid}: wrong catalogue centre/frame/sphere/window/parameters')
    grid = dict(rows=11, cols=11, spacing_m=100, origin_e_m=-500, origin_n_m=-500)
    if any(record.get('grid',{}).get(k)!=value for k,value in grid.items()) or not record['grid'].get('order') or len(record['nodes']) != 121:
        raise ValueError(f'{sid}: expected complete 11x11 grid at 100 m spacing')
    max_geometry_error = 0.
    for index, point in enumerate(record['nodes']):
        east, north = (index % 11-5)*100, (index//11-5)*100
        if (point['index'], point['e_m'], point['n_m']) != (index, east, north):
            raise ValueError(f'{sid}/{index}: wrong row-major grid order/offsets')
        if not (-90 <= point['lat'] <= 90 and -180 <= point['lon'] <= 180):
            raise ValueError(f'{sid}/{index}: invalid latitude/longitude')
        lon, lat, _ = GEOD.fwd(site['lon'], site['lat'],
            float(np.degrees(np.arctan2(east, north))), float(np.hypot(east, north)))
        _, _, error = GEOD.inv(lon, lat, point['lon'], point['lat'])
        if not np.isfinite(error) or abs(error) > .001:
            raise ValueError(f'{sid}/{index}: coordinate differs from independent geodesic by >1 mm')
        max_geometry_error = max(max_geometry_error, abs(error))
        if any(not np.isfinite(point[k]) for k in (*METRICS, 'h0_m', 'ground_resolution_m')):
            raise ValueError(f'{sid}/{index}: non-finite metric/height/resolution')
        if (any(not 0 <= point[k] <= 1 for k in FRACTIONS)
                or point['both_frac'] > min(point['sun_frac'], point['earth_frac'])
                or not 0 <= point['longest_dark_h'] <= WINDOW['n']
                or int(point['longest_dark_h']) != point['longest_dark_h']
                or point['ground_resolution_m'] <= 0 or not point['dem_sources']):
            raise ValueError(f'{sid}/{index}: invalid metric/resolution/DEM sources')
        if any(abs(point[k]*WINDOW['n']-round(point[k]*WINDOW['n'])) > 1e-8 for k in FRACTIONS):
            raise ValueError(f'{sid}/{index}: fractions are not exact hourly counts')
    center_point = record['nodes'][60]
    if any(center_point[k] != center[k] for k in center):
        raise ValueError(f'{sid}: centre node coordinates must exactly equal catalogue')
    check_statistics(record)
    provenance = record['provenance']
    if provenance['center'] != site or provenance['params'] != legacy_params(horizon):
        raise ValueError(f'{sid}: provenance centre/parameters differ')
    legacy_chain = [(entry[0], entry[1]) for entry in horizon['engine']['chain']]
    declared_chain = [(source_name(item), item['gate_km']) for item in provenance['terrain_sources']]
    if legacy_chain != declared_chain:
        raise ValueError(f'{sid}: terrain source order/gates differ from unchanged legacy horizon')
    payload = {k: v for k, v in provenance.items() if k != 'input_key'}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if provenance['input_key'] != digest:
        raise ValueError(f'{sid}: provenance fingerprint differs')
    differences = {key: center_point[key]-baseline[key] for key in METRICS}
    matches = all(value == 0 for value in differences.values())
    claimed = record['center_check']
    claim_matches = (claimed.get('matches') == matches and claimed.get('differences') == differences
                     and claimed.get('metrics_sha256') == baseline_hash)
    return dict(id=sid, schema_passed=True, maximum_coordinate_error_m=max_geometry_error,
                center_exact_match=matches, center_differences=differences,
                center_claim_matches=claim_matches, metrics_sha256=baseline_hash,
                passed=matches and claim_matches)


class ProvenanceDEM(DEM):
    """Independent readers, source order and observer-centred gates from provenance."""
    def __init__(self, center, point, raw, manifest, repo_root, hash_file=sha256):
        super().__init__(center, raw, 300.)
        self.lat, self.lon = point['lat'], point['lon']
        available = {Path(s['path']).resolve(): s for s in self.sources}
        declared = [(repo_root/item['path']).resolve() for item in manifest]
        if len(set(declared)) != len(declared) or set(declared) != set(available):
            raise ValueError('terrain source set differs from output provenance; legacy global64 must be retained')
        self.sources = [available[path] for path in declared]
        self.verified_sources = []
        for source, item in zip(self.sources, manifest):
            path = Path(source['path'])
            if hash_file(path) != item['sha256']:
                raise ValueError(f'terrain hash differs: {path}')
            gate = item['gate_km']
            if gate is not None and (not np.isfinite(gate) or not 0 < gate <= 300):
                raise ValueError(f'invalid terrain range gate: {path}')
            if gate is None and source['kind'] != 'global':
                raise ValueError(f'unbounded non-global terrain range gate: {path}')
            if not np.isfinite(item['resolution_m']) or item['resolution_m'] <= 0:
                raise ValueError(f'invalid terrain resolution: {path}')
            source['max_km'] = gate
            if source['kind'] == 'global' and hash_file(path.with_suffix('.lbl')) != item['label_sha256']:
                raise ValueError(f'global terrain label hash differs: {path}')
            self.verified_sources.append(dict(item))


def verify_point(site, index, record, ephem, terrain):
    started = time.monotonic()
    point = record['nodes'][index]
    terrain.lat, terrain.lon = point['lat'], point['lon']
    ground = float(terrain(np.array([point['lat']]), np.array([point['lon']]))[0])
    if not np.isfinite(ground):
        raise ValueError(f'{site}/{index}: missing observer ground')
    params = record['params']
    distances = np.geomspace(params['min_km']*1000, params['max_km']*1000, params['n_steps']+1)
    mask = trace_mask(point['lat'], point['lon'], ground, 2., terrain, np.arange(720)*.5, distances)
    full = evaluate_metrics(point['lat'], point['lon'], ground, mask, ephem)
    # Mirror only the documented record serialization, not production geometry.
    rounded_ground = round(ground, 2)
    rounded_mask = np.array([round(float(value), 4) for value in mask])
    rounded = evaluate_metrics(point['lat'], point['lon'], rounded_ground, rounded_mask, ephem)
    comparison = compare_metrics(rounded, point)
    ground_difference = ground-point['h0_m']
    ground_pass = abs(ground_difference) <= .005001
    return dict(id=site, index=index, e_m=point['e_m'], n_m=point['n_m'],
        lat=point['lat'], lon=point['lon'], independent_ground_m=ground,
        reported_ground_m=point['h0_m'], ground_difference_m=ground_difference,
        ground_rounding_passed=ground_pass,
        independent_mask_sha256=hashlib.sha256(np.asarray(mask, dtype='<f8').tobytes()).hexdigest(),
        rounded_mask_sha256=hashlib.sha256(np.asarray(rounded_mask, dtype='<f8').tobytes()).hexdigest(),
        comparison=comparison, unrounded_comparison=compare_metrics(full, point),
        rounding_effect={key: rounded[key]-full[key] for key in METRICS},
        sources=terrain.verified_sources, final_missing_terrain_samples=0,
        rays=720, samples_per_ray=len(distances), min_distance_m=float(distances[0]), epochs=43824,
        passed=bool(comparison['passed'] and ground_pass), elapsed_s=round(time.monotonic()-started, 3))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=ROOT/'data/raw')
    parser.add_argument('--web-data', type=Path, default=ROOT/'web/data')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/coordinate_uncertainty_check.json')
    parser.add_argument('--log', type=Path, default=ROOT/'docs/coordinate_uncertainty_verification.log')
    args = parser.parse_args(argv)
    args.log.parent.mkdir(parents=True, exist_ok=True)

    def log(message):
        line = f'{datetime.now(timezone.utc).isoformat()} {message}'
        print(line, flush=True)
        with args.log.open('a', encoding='utf-8') as output:
            output.write(line+'\n')

    hashes = {}
    def hash_file(path):
        path = Path(path).resolve()
        if path not in hashes:
            hashes[path] = sha256(path)
        return hashes[path]

    ephem = load_ephemeris(args.web_data)
    sites = [s for s in read(args.web_data/'sites.json') if s['lat']<=-75]
    if len({s['id'] for s in sites}) != len(sites):
        raise ValueError('duplicate catalogue IDs')
    paths = list((args.web_data/'uncertainty').glob('*.json'))
    if not {s['id'] for s in sites} <= {p.stem for p in paths}:
        raise ValueError('uncertainty outputs must include all 16 polar IDs')
    records, checks = {}, []
    for site in sites:
        sid = site['id']
        record = read(args.web_data/'uncertainty'/f'{sid}.json')
        baseline_path = args.web_data/'metrics'/f'{sid}.json'
        horizon = read(args.web_data/'horizon'/f'{sid}.json')
        checks.append(check_record(record, site, read(baseline_path), hash_file(baseline_path), horizon))
        if (record['provenance']['baseline_metrics_sha256'] != hash_file(baseline_path)
                or record['provenance']['baseline_horizon_sha256'] != hash_file(args.web_data/'horizon'/f'{sid}.json')):
            raise ValueError(f'{sid}: unchanged legacy horizon/metrics hashes differ from provenance')
        for path, expected in record['provenance']['files_sha256'].items():
            if hash_file(ROOT/path) != expected:
                raise ValueError(f'{sid}: production input hash differs: {path}')
        for source in record['provenance']['terrain_sources']:
            path = ROOT/source['path']
            if hash_file(path) != source['sha256']:
                raise ValueError(f'{sid}: terrain hash differs: {path}')
            if path.suffix == '.img' and hash_file(path.with_suffix('.lbl')) != source['label_sha256']:
                raise ValueError(f'{sid}: global label hash differs: {path}')
        records[sid] = record
    selected = [dict(id=sid, index=index) for sid, index in select_points()]
    identity = dict(catalogue_sha256=hash_file(args.web_data/'sites.json'),
        ephem_bin_sha256=hash_file(args.web_data/'ephem.bin'),
        ephem_metadata_sha256=hash_file(args.web_data/'ephem.json'),
        verifier_sha256=hash_file(__file__),
        helpers_sha256={name: hash_file(Path(__file__).with_name(name))
                        for name in ('verify_card13_relay.py', 'verify_card18_local.py')},
        output_sha256={s['id']: hash_file(args.web_data/'uncertainty'/f"{s['id']}.json") for s in sites},
        baseline_sha256={entry['id']: entry['metrics_sha256'] for entry in checks},
        legacy_horizon_sha256={s['id']: hash_file(args.web_data/'horizon'/f"{s['id']}.json") for s in sites})
    previous = read(args.output) if args.output.exists() else {}
    report = dict(method='Independent PROJ geodesics, DEM readers, ECEF brute-force rays and NumPy full-window Sun/Earth metrics; no production imports or early stop',
        criterion='Rounded-record independent sun/earth/both differences <=1 percentage point; all catalogue centres exact in all four metrics; ground within 0.005001 m rounding envelope. Longest dark-run difference reported, no invented tolerance.',
        limitation='Same-source numerical verification, not terrain ground truth or a statistical bound for every node.',
        seed=SEED, sampling='random.Random(seed), five nodes without replacement separately per site in SAMPLE_IDS order',
        sample_sites=list(SAMPLE_IDS), selected=selected, sample_n=15,
        parameters=dict(radius_m=RADIUS, observer_height_m=2, azimuth_bins=720,
            azimuth_step_deg=.5, per_site={sid: r['params'] for sid, r in records.items()},
            distance_spacing='geomspace(min_km*1000,max_km*1000,n_steps+1)', early_stop=False, **WINDOW),
        quantization='Primary comparison rounds independent mask to 4 decimal degrees and ground to 2 decimal metres using Python round. Full-precision comparison and rounding-induced metric changes are also retained.',
        source_policy='Use exact provenance source order/gates centred on each observer and verify against unchanged legacy horizon metadata. Retain LDEM_64 before LDEM_16 at all sites. Reject any source-set difference; verify terrain and global-label SHA256.',
        identity=identity, catalogue_checks=checks, points=[], complete=False, passed=False,
        started_utc=datetime.now(timezone.utc).isoformat())
    if previous.get('identity') == identity and previous.get('selected') == selected:
        report['points'] = [p for p in previous.get('points', [])
                            if dict(id=p['id'], index=p['index']) in selected]
        if len({(p['id'], p['index']) for p in report['points']}) != len(report['points']):
            raise ValueError('duplicate completed verification checkpoints')
    save_report(args.output, report)
    log(f'Catalogue schema/statistics checked: {len(checks)} sites; exact centres: {sum(c["passed"] for c in checks)}/{len(checks)}; resumed nodes: {len(report["points"])}')
    for sid in SAMPLE_IDS:
        record = records[sid]
        terrain = None
        for selected_point in [p for p in selected if p['id'] == sid]:
            index = selected_point['index']
            if any(p['id'] == sid and p['index'] == index for p in report['points']):
                continue
            if terrain is None:
                terrain = ProvenanceDEM(record['provenance']['center'], record['nodes'][index],
                    args.raw, record['provenance']['terrain_sources'], ROOT, hash_file)
            log(f'{sid}/{index}: tracing all 720 x {record["params"]["n_steps"]+1} samples')
            result = verify_point(sid, index, record, ephem, terrain)
            report['points'].append(result)
            save_report(args.output, report)
            pp = {k: result['comparison'][k]['difference_pp'] for k in FRACTIONS}
            log(f'{sid}/{index}: passed={result["passed"]}; differences_pp={pp}; dark_difference_h={result["comparison"]["longest_dark_h"]["difference_h"]}; elapsed_s={result["elapsed_s"]}')
        del terrain
    report['complete'] = len(report['points']) == 15
    report['passed'] = report['complete'] and all(c['passed'] for c in checks) and all(p['passed'] for p in report['points'])
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save_report(args.output, report)
    log(f'Finished: complete={report["complete"]}; passed={report["passed"]}; report={args.output}')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
