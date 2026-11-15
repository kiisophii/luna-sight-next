"""Independent task P/Q recomputation. No production/repository module imports.

Definitions copied from core.js and data_contract.md; existing ephemeris/horizons
are inputs, not independently established physical truth. CPU only.
"""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
import base64
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
N = 43824


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n', encoding='utf-8')
    tmp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def js_round(value, places):
    scale = 10 ** places
    return math.floor(value * scale + 0.5) / scale


def utc_hour(hour):
    return (T0 + timedelta(hours=int(hour))).strftime('%Y-%m-%dT%H:%M:%SZ')


def months():
    result = []
    for year in range(2026, 2031):
        for month in range(1, 13):
            a = datetime(year, month, 1, tzinfo=timezone.utc)
            b = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
            result.append((a.strftime('%Y-%m'), int((a-T0).total_seconds()/3600), int((b-T0).total_seconds()/3600)))
    return result


def horizon_at(horizon, azimuth):
    mask = np.asarray(horizon['mask'], dtype=np.float64)
    x = ((azimuth % 360 + 360) % 360) / horizon['az_step_deg']
    floor = np.floor(x)
    k = floor.astype(np.int64) % len(mask)
    return mask[k] + (mask[(k+1) % len(mask)] - mask[k]) * (x-floor)


def disk_fraction(margin_deg):
    y = np.clip(-margin_deg / 0.2666, -1., 1.)
    return (np.arccos(y) - y * np.sqrt(1-y*y)) / np.pi


def hourly_states(site, horizon, ephem):
    lat, lon = np.deg2rad([site['lat'], site['lon']])
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    east = np.array([-so, co, 0.])
    north = np.array([-sl*co, -sl*so, cl])
    up = np.array([cl*co, cl*so, sl])
    observer = up * (1737.4 + (horizon['h0_m']+2.) / 1000.)
    def margin(offset):
        vec = ephem[:, offset:offset+3] - observer
        def dot(basis):
            return vec[:, 0]*basis[0] + vec[:, 1]*basis[1] + vec[:, 2]*basis[2]
        e, n, u = dot(east), dot(north), dot(up)
        az = np.rad2deg(np.arctan2(e, n)) % 360
        el = np.rad2deg(np.arctan2(u, np.hypot(e, n)))
        return el - horizon_at(horizon, az)
    return disk_fraction(margin(0)) >= .5, margin(3) > 0.


def runs(states):
    states = np.asarray(states, dtype=bool)
    if not len(states):
        return [], []
    edges = np.r_[0, np.flatnonzero(states[1:] != states[:-1])+1, len(states)]
    yes, no = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        (yes if states[a] else no).append((int(a), int(b)))
    return yes, no


def longest_dark(sun):
    return max((b-a for a, b in runs(sun)[1]), default=0)


def window_product(states):
    yes, no = runs(states)
    def interval(ab):
        a, b = ab
        return dict(start_utc=utc_hour(a), end_utc=utc_hour(b), duration_h=b-a,
                    clipped_start=a == 0, clipped_end=b == len(states))
    return dict(visible=list(map(interval, yes)),
                longest_gaps=list(map(interval, sorted(no, key=lambda ab: (ab[0]-ab[1], ab[0]))[:10])),
                visible_hours=int(np.count_nonzero(states)))


class Comparisons:
    def __init__(self, site):
        self.site, self.rows = site, []

    def exact(self, product, field, stored, expected):
        equal = type(stored) == type(expected) and stored == expected
        # JSON integer and floating-point numerical metadata are equivalent.
        if isinstance(stored, (int, float)) and not isinstance(stored, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
            equal = stored == expected
        self.rows.append(dict(site=self.site, product=product, field=field, stored=stored,
                              expected=expected, raw_expected=expected, unit='exact', limit=0,
                              delta=None, serialized_delta=None, serialized_equal=equal, **{'pass': equal}))

    def number(self, product, field, stored, expected, unit, limit, places=None):
        rounded = expected if places is None else js_round(expected, places)
        factor = 100. if unit == 'pp' else 1.
        valid = isinstance(stored, (int, float)) and not isinstance(stored, bool) and math.isfinite(stored)
        delta = (stored-expected)*factor if valid else None
        serial = (stored-rounded)*factor if valid else None
        self.rows.append(dict(site=self.site, product=product, field=field,
                              stored=stored if valid or stored is None else repr(stored),
                              expected=rounded, raw_expected=expected, unit=unit, limit=limit,
                              delta=delta, serialized_delta=serial, serialized_equal=valid and stored == rounded,
                              **{'pass': valid and abs(delta) <= limit}))


def compare_windows(check, body, actual, states):
    expected = window_product(states)
    check.exact('P', f'{body}.keys', sorted(actual), sorted(expected))
    check.number('P', f'{body}.visible_hours', actual.get('visible_hours'), expected['visible_hours'], 'h', 1.)
    for kind in ('visible', 'longest_gaps'):
        stored = actual.get(kind, [])
        wanted = expected[kind]
        check.exact('P', f'{body}.{kind}.count', len(stored), len(wanted))
        for k in range(max(len(stored), len(wanted))):
            prefix = f'{body}.{kind}[{k}]'
            if k >= len(stored) or k >= len(wanted):
                check.exact('P', prefix, stored[k] if k < len(stored) else None, wanted[k] if k < len(wanted) else None)
                continue
            s, w = stored[k], wanted[k]
            check.exact('P', prefix+'.keys', sorted(s), sorted(w))
            for key in ('start_utc', 'end_utc'):
                try:
                    actual_min = (datetime.fromisoformat(s[key].replace('Z', '+00:00'))-T0).total_seconds()/60
                except (KeyError, ValueError, TypeError):
                    actual_min = None
                wanted_min = (datetime.fromisoformat(w[key].replace('Z', '+00:00'))-T0).total_seconds()/60
                check.number('P', prefix+'.'+key, actual_min, wanted_min, 'min', 2.)
            check.number('P', prefix+'.duration_h', s.get('duration_h'), w['duration_h'], 'h', 1.)
            for key in ('clipped_start', 'clipped_end'):
                check.exact('P', prefix+'.'+key, s.get(key), w[key])
    return {key: len(expected[key]) for key in ('visible', 'longest_gaps')}


def compare_monthly(check, actual, sun, earth, ephem):
    calendar = months()
    for key, expected in dict(id=check.site, first_month='2026-01', last_month='2030-12', n_months=60,
                              step_h=1, months=[m for m, _, _ in calendar], mock=False).items():
        check.exact('Q', key, actual.get(key), expected)
    check.exact('Q', 'lunation.window_h', actual.get('lunation', {}).get('window_h'), 709)
    definitions = [('series', k, 'h', None) for k in ('hours', 'sun_h', 'earth_h', 'both_h', 'longest_dark_h')]
    definitions += [(section, k, 'pp', 4) for section in ('series', 'lunation') for k in ('sun_frac', 'earth_frac', 'both_frac')]
    definitions += [(section, k, 'deg', 3) for section in ('subsolar_lat_deg', 'subearth_lat_deg') for k in ('min', 'max')]
    for section, key, _, _ in definitions:
        check.exact('Q', f'{section}.{key}.count', len(actual.get(section, {}).get(key, [])), 60)
    # Body-centred direction, NOT the topocentric observer direction.
    latitudes = [np.rad2deg(np.arcsin(ephem[:, c+2] / np.hypot(np.hypot(ephem[:, c], ephem[:, c+1]), ephem[:, c+2]))) for c in (0, 3)]
    both = sun & earth
    monthly_dark = []
    for i, (month, a, b) in enumerate(calendar):
        center = a + (b-a)//2
        values = {'series': dict(hours=b-a, longest_dark_h=longest_dark(sun[a:b])), 'lunation': {}}
        monthly_dark.append(values['series']['longest_dark_h'])
        for key, state in zip(('sun', 'earth', 'both'), (sun, earth, both)):
            count = int(np.count_nonzero(state[a:b]))
            values['series'][key+'_h'] = count
            values['series'][key+'_frac'] = count/(b-a)
            values['lunation'][key+'_frac'] = int(np.count_nonzero(state[center-354:center+355]))/709
        for section, latitude in zip(('subsolar_lat_deg', 'subearth_lat_deg'), latitudes):
            values[section] = dict(min=float(latitude[a:b].min()), max=float(latitude[a:b].max()))
        for section, key, unit, places in definitions:
            stored = actual.get(section, {}).get(key, [])
            check.number('Q', f'{month}.{section}.{key}', stored[i] if i < len(stored) else None,
                         values[section][key], unit, {'h': 1., 'pp': .1, 'deg': .05}[unit], places)
    totals = dict(hours=len(sun), longest_dark_h_max_month=max(monthly_dark))
    totals.update({key+'_frac': int(np.count_nonzero(state))/len(state) for key, state in zip(('sun', 'earth', 'both'), (sun, earth, both))})
    for key, value in totals.items():
        check.number('Q', 'total.'+key, actual.get('total', {}).get(key), value, 'pp' if key.endswith('frac') else 'h', .1 if key.endswith('frac') else 1.)


def validate_inputs(sites, meta, ephem):
    if len(sites) != 33 or len({s['id'] for s in sites}) != 33:
        raise ValueError('Expected exactly 33 unique catalogue sites')
    expected = dict(start='2026-01-01T00:00:00Z', step_h=1, n=N, frame='MOON_ME_DE421', units='km', mock=False,
                    columns=['sun_x', 'sun_y', 'sun_z', 'earth_x', 'earth_y', 'earth_z'])
    if any(meta.get(k) != v for k, v in expected.items()) or ephem.shape != (N, 6) or not np.isfinite(ephem).all():
        raise ValueError('Invalid ephemeris metadata, dimensions or values')
    if any(s.get('mock', False) for s in sites):
        raise ValueError('Mock sites are not valid verification inputs')


def validate_horizon(site, h):
    if any(h.get(k) != site[k] for k in ('id', 'lat', 'lon')):
        raise ValueError('Horizon and catalogue coordinates differ')
    if h.get('mock') is not False or h.get('site_coords_mock') or h.get('flat') or h.get('obs_height_m') != 2:
        raise ValueError('Expected real terrain, real coordinates and 2 m observer')
    mask = np.asarray(h['mask'], dtype=float)
    if mask.shape != (720,) or h['az_step_deg'] != .5 or not np.isfinite(mask).all() or not math.isfinite(h['h0_m']):
        raise ValueError('Invalid horizon mask')
    if h.get('engine', {}).get('n_missing_samples', 0) != 0 or not h.get('dem_sources'):
        raise ValueError('Missing terrain samples or DEM provenance')


def source_site_hash(site):
    # JSON.stringify normalizes integral Numbers; catalogue has no exponent-scale values.
    def normal(value):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, dict):
            return {k: normal(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normal(v) for v in value]
        return value
    return hashlib.sha256(json.dumps(normal(site), ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def compare_source_hash(check, product, field, stored, path, byte_differences):
    raw = Path(path).read_bytes()
    raw_hash = hashlib.sha256(raw).hexdigest()
    lf_hash = hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
    crlf_hash = hashlib.sha256(raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest()
    accepted = stored in (raw_hash, lf_hash, crlf_hash)
    check.exact(product, field+'.matches_bytes_or_line_endings', accepted, True)
    if stored != raw_hash:
        byte_differences.append(dict(site=check.site, product=product, field=field, stored=stored,
                                     checkout_sha256=raw_hash, lf_sha256=lf_hash, crlf_sha256=crlf_hash,
                                     only_line_endings=accepted))


def statistics(rows):
    result = {}
    for product in ('P', 'Q'):
        for unit in ('pp', 'deg', 'min', 'h'):
            selected = [r for r in rows if r['product'] == product and r['unit'] == unit and r['delta'] is not None]
            if not selected:
                continue
            raw = np.array([r['delta'] for r in selected])
            serial = np.array([r['serialized_delta'] for r in selected])
            result[product+'_'+unit] = dict(n=len(selected), min_signed=float(raw.min()), max_signed=float(raw.max()),
                                          max_abs=float(np.abs(raw).max()), median_abs=float(np.median(np.abs(raw))),
                                          serialized_max_abs=float(np.abs(serial).max()),
                                          serialized_median_abs=float(np.median(np.abs(serial))))
    return result


def write_comparisons(path, rows):
    fields = ['site', 'product', 'field', 'stored', 'expected', 'raw_expected', 'unit', 'limit', 'delta', 'serialized_delta', 'serialized_equal', 'pass']
    tmp = path.with_suffix('.csv.tmp')
    with tmp.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(',', ':')) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    tmp.replace(path)


def cached_states(path, fingerprint, site, h, ephem, resume):
    if resume and path.exists():
        prior = read(path)
        packed = base64.b64decode(prior['packed'])
        if prior.get('fingerprint') == fingerprint and hashlib.sha256(packed).hexdigest() == prior.get('packed_sha256') and len(packed) == 2*((N+7)//8):
            unpacked = np.unpackbits(np.frombuffer(packed, dtype=np.uint8)).reshape(2, N).astype(bool)
            return unpacked[0], unpacked[1], True
    sun, earth = hourly_states(site, h, ephem)
    packed = np.packbits(np.stack([sun, earth])).tobytes()
    write(path, dict(fingerprint=fingerprint, packed=base64.b64encode(packed).decode(), packed_sha256=hashlib.sha256(packed).hexdigest()))
    return sun, earth, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    out = root/'docs/task_pq_check.json'
    started = time.perf_counter()
    report = dict(status='RUNNING', complete=False, checker='Jiyong Sung', generated_utc=datetime.now(timezone.utc).isoformat(),
                  source_hashes={}, sites=[], comparisons=[], errors=[], provenance_byte_differences=[], criteria=dict(fraction_pp=.1, angle_deg=.05, edge_min=2, duration_h=1),
                  scope='All stored P/Q values on existing ephemeris and horizons; implementation consistency, not physical lunar truth.',
                  runtime=dict(python=os.sys.version, numpy=np.__version__, cpu_processes=1, blas_threads=1, gpu=False))
    write(out, report)
    (root/'docs/task_pq_check.md').write_text('# Task P/Q verification running\n\nNo current PASS claim; generate the report after completion.\n', encoding='utf-8')
    try:
        paths = ['web/data/sites.json', 'web/data/ephem.json', 'web/data/ephem.bin', 'web/js/core.js',
                 'pipeline/build_windows.mjs', 'pipeline/seasons.mjs', 'docs/data_contract.md', 'pipeline/task_pq_check.py',
                 'pipeline/task_pq_report.py', 'pipeline/tests/test_task_pq.py', 'web/data/windows/index.json']
        sites = read(root/paths[0])
        meta = read(root/paths[1])
        ephem = np.fromfile(root/paths[2], dtype='<f4').astype(np.float64).reshape(-1, 6)
        validate_inputs(sites, meta, ephem)
        ids = sorted(s['id'] for s in sites)
        report['input_git_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        for category in ('horizon', 'windows', 'monthly'):
            names = sorted(p.stem for p in (root/'web/data'/category).glob('*.json') if p.stem != 'index')
            if names != ids:
                raise ValueError(f'{category}: site file coverage differs from 33-site catalogue')
            paths += [f'web/data/{category}/{site_id}.json' for site_id in ids]
        hashes = {p: sha(root/p) for p in paths}
        report['source_hashes'] = hashes
        index = read(root/'web/data/windows/index.json')
        global_check = Comparisons('__global__')
        for key, expected in dict(ids=ids, skipped={}, n=N, step_h=1, start_utc=utc_hour(0), end_utc=utc_hour(N), mock=False, format='site-windows-v1').items():
            global_check.exact('P', 'index.'+key, sorted(index.get(key, [])) if key == 'ids' else index.get(key), expected)
        report['comparisons'].extend(global_check.rows)
        for site in sites:
            site_id = site['id']
            h = read(root/f'web/data/horizon/{site_id}.json')
            validate_horizon(site, h)
            fingerprint = hashlib.sha256(json.dumps({p: hashes[p] for p in paths if p in ('web/data/sites.json', 'web/data/ephem.bin', 'web/data/ephem.json', 'pipeline/task_pq_check.py') or p == f'web/data/horizon/{site_id}.json'}, sort_keys=True).encode()).hexdigest()
            sun, earth, resumed = cached_states(root/f'data/processed/task_pq/cache/{site_id}.json', fingerprint, site, h, ephem, args.resume)
            check = Comparisons(site_id)
            window = read(root/f'web/data/windows/{site_id}.json')
            monthly = read(root/f'web/data/monthly/{site_id}.json')
            for key, expected in dict(id=site_id, format='site-windows-v1', lat=site['lat'], lon=site['lon'], h0_m=h['h0_m'], obs_height_m=2,
                                      start_utc=utc_hour(0), end_utc=utc_hour(N), step_h=1, n=N, mock=False).items():
                check.exact('P', key, window.get(key), expected)
            source_paths = dict(core_sha256='web/js/core.js', ephem_sha256='web/data/ephem.bin', ephem_meta_sha256='web/data/ephem.json',
                                horizon_sha256=f'web/data/horizon/{site_id}.json', producer_sha256='pipeline/build_windows.mjs')
            for key, path in source_paths.items():
                if key in ('core_sha256', 'producer_sha256'):
                    compare_source_hash(check, 'P', 'source.'+key, window.get('source', {}).get(key), root/path, report['provenance_byte_differences'])
                else:
                    check.exact('P', 'source.'+key, window.get('source', {}).get(key), hashes[path])
            check.exact('P', 'source.site_sha256', window.get('source', {}).get('site_sha256'), source_site_hash(site))
            for key in ('core_sha256', 'horizon_sha256'):
                check.exact('Q', key, monthly.get(key), hashes[source_paths[key]])
            counts = {body: compare_windows(check, body, window.get(body, {}), state) for body, state in (('sun', sun), ('earth', earth))}
            compare_monthly(check, monthly, sun, earth, ephem)
            result = dict(id=site_id, hours=N, months=60, resumed=resumed, counts=counts,
                          failures=sum(not r['pass'] for r in check.rows), serialized_mismatches=sum(not r['serialized_equal'] for r in check.rows),
                          compared_values=len(check.rows), statistics=statistics(check.rows))
            report['sites'].append(result)
            report['comparisons'].extend(check.rows)
            # Small progress marker; full evidence is finalized below.
            write(root/'data/processed/task_pq/progress.json', dict(completed_sites=report['sites'], status='RUNNING', elapsed_seconds=time.perf_counter()-started))
            print(f'{site_id}: P Sun {counts["sun"]["visible"]}, Earth {counts["earth"]["visible"]}; Q 60 months; failures {result["failures"]}', flush=True)
        changed = [p for p, old in hashes.items() if sha(root/p) != old]
        if changed:
            raise ValueError(f'Sources changed during verification: {changed}')
        report['complete'] = len(report['sites']) == 33
        report['failures'] = [r for r in report['comparisons'] if not r['pass']]
        report['serialized_mismatches'] = [r for r in report['comparisons'] if not r['serialized_equal']]
        report['status'] = 'PASS' if report['complete'] and not report['failures'] else 'FAIL'
    except Exception as exc:
        report['status'] = 'ERROR'
        report['errors'].append(f'{type(exc).__name__}: {exc}')
    rows = report.pop('comparisons')
    report['compared_values'] = len(rows)
    report['statistics'] = statistics(rows)
    report['comparison_file'] = 'docs/task_pq_comparisons.csv'
    write_comparisons(root/report['comparison_file'], rows)
    report['comparison_sha256'] = sha(root/report['comparison_file'])
    report['elapsed_seconds'] = time.perf_counter()-started
    write(out, report)
    if report['status'] != 'PASS':
        (root/'docs/task_pq_check.md').write_text('# Task P/Q report unavailable\n\n'+report['status']+': see task_pq_check.json for all failures/errors.\n', encoding='utf-8')
    write(root/'data/processed/task_pq/progress.json', {k: report[k] for k in ('status', 'complete', 'elapsed_seconds', 'errors')})
    print(json.dumps({k: report[k] for k in ('status', 'complete', 'elapsed_seconds', 'errors')}))
    return 0 if report['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
