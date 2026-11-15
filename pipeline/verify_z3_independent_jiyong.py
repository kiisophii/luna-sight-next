"""Independent Z3 audit: no production numerical imports or cached hourly flags.

Run from the repository root: python pipeline/verify_z3_independent_jiyong.py
Shared inputs are the published ephemeris and horizon masks, not new physical truth.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numpy as np

ROW_COLUMNS = ['status', 'sun_h', 'earth_h', 'both_h', 'sun_frac', 'earth_frac',
               'both_frac', 'longest_dark_h', 'dark_left_censored', 'dark_right_censored']
DELTA_COLUMNS = ['status', 'target_day_index', 'delta_sun_h', 'delta_earth_h',
                 'delta_both_h', 'delta_longest_dark_h']
STAYS = (168, 336, 708)
SHIFTS = (-7, -3, -1, 1, 3, 7)
DAYS, HOURS = 1826, 43824
PR_HEAD = '3939a3b8323b3ddf74c4c62691f8d9318bd3c1f1'
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def mask_at(azimuth, mask, step):
    """Periodic linear interpolation, including the final-to-first interval."""
    values = np.asarray(mask, dtype=np.float64)
    return np.interp(np.mod(azimuth, 360), np.arange(len(values) + 1) * step,
                     np.r_[values, values[0]])


def hourly_flags(site, horizon, eph):
    """Own local basis and observer subtraction; input rows are exact hours."""
    lat, lon = np.deg2rad([site['lat'], site['lon']])
    up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    east = np.array([-np.sin(lon), np.cos(lon), 0])
    north = np.cross(up, east)
    observer = up * (1737.4 + (horizon['h0_m'] + 2) / 1000)
    margins = []
    for column in (0, 3):
        v = eph[:, column:column + 3] - observer
        e, n, u = v @ east, v @ north, v @ up
        az = np.mod(np.rad2deg(np.arctan2(e, n)), 360)
        elevation = np.rad2deg(np.arctan2(u, np.hypot(e, n)))
        margins.append(elevation - mask_at(az, horizon['mask'], horizon['az_step_deg']))
    # Evaluate the disk integral explicitly, retaining the exact >=0.5 rule.
    cut = np.clip(-margins[0] / 0.2666, -1, 1)
    sun_fraction = (np.arccos(cut) - cut * np.sqrt(1 - cut * cut)) / np.pi
    return sun_fraction >= 0.5, margins[1] > 0, {
        'min_sun_margin_deg': float(np.min(np.abs(margins[0]))),
        'min_earth_margin_deg': float(np.min(np.abs(margins[1]))),
    }


def base_row(sun, earth, start, hours):
    end = start + hours
    if start < 0 or end > len(sun):
        return ['out_of_range'] + [None] * 9
    s, e = sun[start:end], earth[start:end]
    counts = [int(s.sum()), int(e.sum()), int(np.count_nonzero(s & e))]
    # Consecutive lit indices delimit every dark run, including both edges.
    longest = int(np.max(np.diff(np.r_[-1, np.flatnonzero(s), hours]) - 1))
    left = bool(not s[0] and (start == 0 or not sun[start - 1]))
    right = bool(not s[-1] and (end == len(sun) or not sun[end]))
    return ['ok', *counts, *(v / hours for v in counts), longest, left, right]


def shift_row(base, target, target_day):
    b_ok = base[0] == 'ok'
    t_ok = target is not None and target[0] == 'ok'
    if b_ok and t_ok:
        return ['ok', target_day, *(target[k] - base[k] for k in (1, 2, 3, 7))]
    label = ('both_out_of_range' if not b_ok and not t_ok else
             'base_out_of_range' if not b_ok else 'target_out_of_range')
    return [label, target_day, None, None, None, None]


def row_differences(actual, expected, columns, hours, delta):
    differences = []
    if len(actual) != len(expected):
        return [{'field': 'row_length', 'actual': len(actual), 'expected': len(expected),
                 'abs_diff': None, 'unit': 'exact', 'exceeds_criterion': True}]
    for name, a, b in zip(columns, actual, expected):
        numeric = isinstance(b, (int, float)) and not isinstance(b, bool)
        type_ok = (type(a) is bool if isinstance(b, bool) else
                   type(a) in (int, float) if numeric else type(a) is type(b))
        if type_ok and a == b:
            continue
        diff, unit, fails = None, 'exact', True
        if numeric and type_ok and np.isfinite(a):
            diff = abs(a - b)
            if name.endswith('_frac'):
                diff, unit = diff * 100, 'pp'
                fails = diff > 0.1
            elif name in ('delta_sun_h', 'delta_earth_h', 'delta_both_h'):
                diff, unit = diff / hours * 100, 'pp'
                fails = diff > 0.1 or abs(a - b) > 1
            elif name.endswith('_h'):
                unit, fails = 'h', diff > 1
        differences.append({'field': name, 'actual': a, 'expected': b,
                            'abs_diff': diff, 'unit': unit, 'exceeds_criterion': bool(fails)})
    return differences


def verify_site(root, site, eph):
    started = time.perf_counter()
    sid = site['id']
    hp = root / f'web/data/horizon/{sid}.json'
    pp = root / f'web/data/detail/dates/{sid}.json'
    h, product = load(hp), load(pp)
    assert h['lat'] == site['lat'] and h['lon'] == site['lon']
    assert h['obs_height_m'] == 2 and len(h['mask']) == 720 and h['az_step_deg'] == .5
    assert not h.get('mock') and not h.get('flat') and np.isfinite(h['mask']).all()
    assert product['id'] == sid and product['n_landings'] == DAYS
    assert product['row_columns'] == ROW_COLUMNS and product['delta_columns'] == DELTA_COLUMNS
    assert product['first_landing'] == '2026-01-01' and product['last_landing'] == '2030-12-31'
    assert product['step_days'] == 1 and product['landing_time_utc'] == '00:00:00'
    assert [s['stay_h'] for s in product['stays']] == list(STAYS)
    sun, earth, margins = hourly_flags(site, h, eph)
    discrepancies, boundaries, stay_summary = [], [], []
    fraction_diffs, hour_diffs = [], []
    valid_bases = invalid_bases = valid_shifts = invalid_shifts = comparisons = 0

    def compare(actual, expected, columns, hours, day, shift=None):
        nonlocal comparisons
        comparisons += len(columns)
        for mismatch in row_differences(actual, expected, columns, hours, shift is not None):
            discrepancies.append({'site': sid, 'stay_h': hours, 'day_index': day,
                                  'landing_date': (EPOCH + timedelta(days=day)).date().isoformat(),
                                  'shift_days': shift, **mismatch})
        if actual[0] == expected[0] == 'ok':
            for k, name in enumerate(columns):
                if name.endswith('_frac'):
                    fraction_diffs.append(abs(actual[k] - expected[k]) * 100)
                elif name.endswith('_h'):
                    hour_diffs.append(abs(actual[k] - expected[k]))
                    if name in ('delta_sun_h', 'delta_earth_h', 'delta_both_h'):
                        fraction_diffs.append(abs(actual[k] - expected[k]) / hours * 100)

    for stay in product['stays']:
        hours = stay['stay_h']
        assert stay['stay_days'] * 24 == hours == stay['delta_fraction_denominator_h']
        assert len(stay['rows']) == DAYS
        assert [s['shift_days'] for s in stay['slips']] == list(SHIFTS)
        expected = [base_row(sun, earth, day * 24, hours) for day in range(DAYS)]
        valid = sum(r[0] == 'ok' for r in expected)
        valid_bases += valid
        invalid_bases += DAYS - valid
        stay_summary.append({'stay_h': hours, 'valid': valid, 'out_of_range': DAYS - valid})
        for day, (actual, reference) in enumerate(zip(stay['rows'], expected)):
            compare(actual, reference, ROW_COLUMNS, hours, day)
        leap = (datetime(2028, 2, 29, tzinfo=timezone.utc) - EPOCH).days
        for day in sorted({0, leap - 1, leap, leap + 1, valid - 1, valid, DAYS - 1}):
            boundaries.append({'site': sid, 'stay_h': hours, 'day_index': day,
                               'date': (EPOCH + timedelta(days=day)).date().isoformat(),
                               'expected': expected[day], 'actual': stay['rows'][day]})
        for shift in stay['slips']:
            offset = shift['shift_days']
            assert len(shift['rows']) == DAYS
            for day, actual in enumerate(shift['rows']):
                target = day + offset
                reference = shift_row(expected[day], expected[target] if 0 <= target < DAYS else None, target)
                valid_shifts += reference[0] == 'ok'
                invalid_shifts += reference[0] != 'ok'
                compare(actual, reference, DELTA_COLUMNS, hours, day, offset)
    fractions, durations = np.asarray(fraction_diffs), np.asarray(hour_diffs)
    summary = {'site': sid, 'lat': site['lat'], 'lon': site['lon'],
               'hourly_states': HOURS, 'valid_base_windows': valid_bases,
               'invalid_base_windows': invalid_bases, 'valid_shift_rows': valid_shifts,
               'invalid_shift_rows': invalid_shifts, 'scalar_comparisons': comparisons,
               'fraction_comparisons': len(fractions), 'hour_comparisons': len(durations),
               'max_abs_fraction_pp': float(fractions.max()),
               'median_abs_fraction_pp': float(np.median(fractions)),
               'max_abs_hours': float(durations.max()), 'median_abs_hours': float(np.median(durations)),
               'different_fields': len(discrepancies),
               'failing_fields': sum(x['exceeds_criterion'] for x in discrepancies),
               'seconds': time.perf_counter() - started}
    hashes = {'horizon': digest(hp.read_bytes()), 'product': digest(pp.read_bytes()),
              'horizon_lf': digest(hp.read_bytes().replace(b'\r\n', b'\n')),
              'product_lf': digest(pp.read_bytes().replace(b'\r\n', b'\n')),
              'independent_sun_flags': digest(sun.astype('u1').tobytes()),
              'independent_earth_flags': digest(earth.astype('u1').tobytes())}
    assert product['inputs']['horizon_sha256'] in (hashes['horizon'], hashes['horizon_lf'])
    return summary, discrepancies, boundaries, {'site': sid, 'hashes': hashes, 'threshold_margins': margins, 'stays': stay_summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    root = args.root.resolve()
    started = time.perf_counter()
    meta = load(root / 'web/data/ephem.json')
    assert meta['n'] == HOURS and meta['step_h'] == 1 and meta['start'] == '2026-01-01T00:00:00Z'
    assert meta['frame'] == 'MOON_ME_DE421' and meta['units'] == 'km' and not meta['mock']
    ep = root / 'web/data/ephem.bin'
    eph = np.fromfile(ep, dtype='<f4').reshape(HOURS, 6).astype(np.float64)
    assert np.isfinite(eph).all()
    sites = load(root / 'web/data/sites.json')
    assert len(sites) == 33 and len({s['id'] for s in sites}) == 33
    index = load(root / 'web/data/detail/dates/index.json')
    assert {s['id'] for s in index['sites']} == {s['id'] for s in sites}
    for record in index['sites']:
        raw = (root / 'web/data/detail/dates' / record['file']).read_bytes()
        assert record['sha256'] in (digest(raw), digest(raw.replace(b'\r\n', b'\n')))
    rows, discrepancies, boundaries, details = [], [], [], []
    # Thread parallelism is bounded; no process copies of the ephemeris or GPU use.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(lambda site: verify_site(root, site, eph), sites):
            row, mismatch, edge, detail = result
            rows.append(row); discrepancies.extend(mismatch); boundaries.extend(edge); details.append(detail)
            print(f"{row['site']}: max {row['max_abs_fraction_pp']:.12g} pp / {row['max_abs_hours']:.12g} h; "
                  f"{row['different_fields']} differing fields", flush=True)
    files = ['web/data/ephem.bin', 'web/data/ephem.json', 'web/data/sites.json', 'web/js/core.js',
             'web/data/horizon', 'web/data/detail/dates']
    changed = subprocess.check_output(['git', 'diff', '--name-only', PR_HEAD, 'HEAD', '--', *files], cwd=root, text=True).splitlines()
    summary = {
        'checked_utc': datetime.now(timezone.utc).isoformat(), 'checker': 'Jiyong Sung, AI-assisted',
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'producer_pr': 79, 'producer_head': PR_HEAD, 'pr_to_checked_main_input_changes': changed,
        'scope': 'All 33 sites, all daily starts, all 3 stays and all 6 signed shifts',
        'criteria': {'fraction_pp': 0.1, 'duration_h': 1, 'status_null_censor': 'exact'},
        'workers': args.workers, 'runtime_seconds': time.perf_counter() - started,
        'shared_input_hashes': {p: digest((root / p).read_bytes()) for p in files[:4]},
        'checker_sha256': digest(Path(__file__).read_bytes()),
        'totals': {k: sum(r[k] for r in rows) for k in (
            'hourly_states', 'valid_base_windows', 'invalid_base_windows', 'valid_shift_rows',
            'invalid_shift_rows', 'scalar_comparisons', 'fraction_comparisons', 'hour_comparisons',
            'different_fields', 'failing_fields')},
        'max_abs_fraction_pp': max(r['max_abs_fraction_pp'] for r in rows),
        'max_abs_hours': max(r['max_abs_hours'] for r in rows),
        'sites': rows, 'evidence': details, 'boundary_cases': boundaries,
        'limitations': ['Reuses production ephemeris and terrain masks; does not independently validate physical inputs.',
                        'Hourly cells and midnight arrivals only; not a sub-hour or arbitrary-date UI test.',
                        'No human numerical rerun claimed.'],
    }
    summary['pass'] = summary['totals']['failing_fields'] == 0
    out = root / 'docs/z3_independent_jiyong'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    with (out / 'sites.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (out / 'discrepancies.csv').open('w', encoding='utf-8', newline='') as handle:
        fields = ['site', 'stay_h', 'day_index', 'landing_date', 'shift_days', 'field', 'actual',
                  'expected', 'abs_diff', 'unit', 'exceeds_criterion']
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(discrepancies)
    print(json.dumps({k: summary[k] for k in ['pass', 'runtime_seconds', 'totals', 'max_abs_fraction_pp', 'max_abs_hours']}, indent=2))
    return 0 if summary['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
