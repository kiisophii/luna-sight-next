"""Render task P/Q evidence; refuse stale, incomplete, or failed check results."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def numerical_agreement(rows):
    mismatches = sum(r['unit'] != 'exact' and r['serialized_equal'] != 'True' for r in rows)
    if mismatches:
        return mismatches, f'All numerical differences satisfy the assigned tolerances; **{mismatches:,} numerical values differ from the production serialization**.'
    return 0, 'All compared numerical values equal the production serialization.'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(root):
    report = json.loads((root/'docs/task_pq_check.json').read_text(encoding='utf-8'))
    csv_path = root/report['comparison_file']
    if sha(csv_path) != report['comparison_sha256']:
        raise ValueError('Comparison CSV hash differs from completed run')
    changed = [p for p, value in report['source_hashes'].items() if not (root/p).is_file() or sha(root/p) != value]
    if changed:
        raise ValueError('Source hashes changed: '+', '.join(changed))
    if report['status'] != 'PASS' or not report['complete'] or len(report['sites']) != 33 or sum(s['months'] for s in report['sites']) != 1980:
        raise ValueError('Refusing PASS report for incomplete or failed recomputation')
    with csv_path.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != report['compared_values'] or any(r['pass'] != 'True' for r in rows):
        raise ValueError('Comparison row count/status differs from summary')
    numeric_mismatches, agreement = numerical_agreement(rows)
    actual_failures = sum(r['pass'] != 'True' for r in rows)
    failure_path = root/'docs/task_pq_failures.csv'
    with failure_path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(r for r in rows if r['pass'] != 'True')
    provenance_path = root/'docs/task_pq_provenance_differences.csv'
    with provenance_path.open('w', newline='', encoding='utf-8') as stream:
        fields = ['site', 'product', 'field', 'stored', 'checkout_sha256', 'lf_sha256', 'crlf_sha256', 'only_line_endings']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report['provenance_byte_differences'])
    # One row per month for convenient inspection, alongside every scalar in the full CSV.
    grouped = {}
    for r in rows:
        if r['product'] == 'Q' and len(r['field']) > 8 and r['field'][4] == '-' and r['field'][7] == '.':
            month, field = r['field'][:7], r['field'][8:]
            grouped.setdefault((r['site'], month), {})[field] = r
    if len(grouped) != 1980:
        raise ValueError('Full monthly comparison table does not contain 1,980 rows')
    month_path = root/'docs/task_pq_months.csv'
    with month_path.open('w', newline='', encoding='utf-8') as stream:
        fields = ['site', 'month', 'hours', 'sun_h', 'earth_h', 'both_h', 'longest_dark_h', 'fraction_max_abs_pp', 'latitude_max_abs_deg', 'duration_max_abs_h', 'serialized_mismatches', 'failures']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for (site, month), values in sorted(grouped.items()):
            row = dict(site=site, month=month)
            row.update({k: values['series.'+k]['expected'] for k in ('hours', 'sun_h', 'earth_h', 'both_h', 'longest_dark_h')})
            for key, unit in [('fraction_max_abs_pp', 'pp'), ('latitude_max_abs_deg', 'deg'), ('duration_max_abs_h', 'h')]:
                row[key] = max(abs(float(r['delta'])) for r in values.values() if r['unit'] == unit)
            row['serialized_mismatches'] = sum(r['serialized_equal'] != 'True' for r in values.values())
            row['failures'] = sum(r['pass'] != 'True' for r in values.values())
            writer.writerow(row)
    counts = {body: sum(s['counts'][body]['visible'] for s in report['sites']) for body in ('sun', 'earth')}
    gaps = sum(s['counts'][body]['longest_gaps'] for s in report['sites'] for body in ('sun', 'earth'))
    stat = report['statistics']
    lines = [
        '# Task P/Q — complete independent windows and monthly recomputation', '',
        f"**PASS.** Jiyong Sung independently recomputed all **33/33 sites**, **{counts['sun']:,} Sun + {counts['earth']:,} Earth visible intervals**, "
        f"**{gaps:,} published longest-gap records**, and **1,980/1,980 site-months**. {agreement} "
        'All counts, edges, durations, clipping flags and structural checks satisfy their criteria. No missing or extra intervals.', '',
        f"Input Git HEAD: `{report['input_git_head']}`. Run: `{report['generated_utc']}`; CPU checking/evidence time **{report['elapsed_seconds']:.3f} s**. "
        'Single process, NumPy FP64 with BLAS/OMP threads fixed to 1; no GPU. '
        f"{sum(s['resumed'] for s in report['sites'])}/33 sites resumed from content-hashed independent state caches.", '',
        '## Method and scope', '',
        'P producer: Minchul (card 15-B). Q producer: Sua (monthly seasons). Jiyong did not produce either product. '
        'The checker imports only Python standard-library modules and NumPy; it does not import or execute any production module. '
        'It copies the definitions from `web/js/core.js` and `docs/data_contract.md` into a separate implementation. '
        'Both producing scripts were read to identify the complete stored scope.', '',
        'The checker reads the little-endian float32 ephemeris, promotes to float64, subtracts the observer at 1737.4 km + terrain height + 2 m '
        'for both bodies, projects onto local east/north/up, and interpolates the cyclic 0.5-degree stored mask. '
        'Sunlit means the visible circular solar-disk fraction (radius 0.2666 degrees) is at least 0.5; Earth centre is strictly above the mask. '
        'Each site has 43,824 hourly samples from 2026-01-01 through 2030-12-31.', '',
        'P compares every maximal visible run, visible-hour total, and all published top-ten longest gaps, sorted by duration descending/start ascending. '
        'Intervals are half-open one-hour bins with domain clipping; the last bin ends 2031-01-01. '
        '**The 2-minute edge tolerance checks stored hourly-bin boundaries, not physical or sub-hour rise/set accuracy.** '
        'All complement runs are recomputed to select the published longest gaps.', '',
        'Q compares all 60 UTC calendar months per site, including leap February, hours/Sun/Earth/both counts and fractions, '
        'longest darkness cut at the month boundaries, all three 709-hour month-centred lunation fractions, '
        'the four subsolar/subearth latitude min/max series, and all five-year totals. '
        'Subbody latitude uses the Moon-centred vector. JavaScript rounding (floor(x * scale + 0.5), including negative latitude ties) '
        'is applied only to the separately recorded serialized expectation; thresholds use the unrounded independent value.', '',
        'This is full implementation agreement on the **existing ephemeris and stored horizons**. It does not validate the kernels or terrain '
        'against the real Moon, recompute horizons from DEMs, establish physical error bounds, or change the scope of other ledger products.', '',
        '## Measured differences', '',
        'Signed difference = stored minus independent unrounded value. Raw residuals below are the retained finite-decimal serialization differences. '
        'Every original and recomputed value is in the full CSV; no failure or small discrepancy is rounded away.', '',
        '| Product/value | Values | Raw max absolute | Raw median absolute | Raw signed min / max | Serialized max / median | Criterion |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    labels = {'P_min': ('P interval edges', 'min', 2), 'P_h': ('P durations/totals', 'h', 1),
              'Q_pp': ('Q monthly/lunation/total fractions', 'pp', .1), 'Q_deg': ('Q latitude extrema', 'deg', .05), 'Q_h': ('Q hour counts/durations', 'h', 1)}
    for key, (label, unit, limit) in labels.items():
        s = stat[key]
        lines.append(f"| {label} ({unit}) | {s['n']:,} | {s['max_abs']:.12g} | {s['median_abs']:.12g} | {s['min_signed']:.12g} / {s['max_signed']:.12g} | {s['serialized_max_abs']:.12g} / {s['serialized_median_abs']:.12g} | <= {limit} |")
    lines += ['', f"All **{report['compared_values']:,} comparison records** pass. Scientific/structural failures: **{actual_failures}**; serialized numerical mismatches: **{numeric_mismatches:,}**.", '',
              '## Provenance byte differences retained', '',
              f"There are **{len(report['provenance_byte_differences'])} raw source-hash differences**, recorded individually in "
              '[the provenance table](task_pq_provenance_differences.csv). P stored LF hashes for `core.js` and `build_windows.mjs`; '
              'this Windows checkout has CRLF. Converting only CRLF to LF reproduces each recorded source hash exactly. '
              'No code/content differences are waived. All ephemeris, metadata, site-object and horizon hashes match exactly. '
              'The full source manifest preserves the actual checkout bytes for every input and the checker itself; hashes are rechecked after computation. '
              'These byte differences are provenance notes, not numeric failures.', '',
              '## All-site table', '',
              '| Site | Sun intervals | Earth intervals | Longest gaps (Sun/Earth) | Months | Q raw fraction max (pp) | Q raw angle max (deg) | Duration/edge max | Status |',
              '|---|---:|---:|---:|---:|---:|---:|---|---|']
    for s in report['sites']:
        a = s['statistics']
        lines.append(f"| {s['id']} | {s['counts']['sun']['visible']} | {s['counts']['earth']['visible']} | "
                     f"{s['counts']['sun']['longest_gaps']}/{s['counts']['earth']['longest_gaps']} | {s['months']} | "
                     f"{a['Q_pp']['max_abs']:.12g} | {a['Q_deg']['max_abs']:.12g} | "
                     f"{max(a['P_h']['max_abs'],a['Q_h']['max_abs']):g} h / {a['P_min']['max_abs']:g} min | PASS |")
    lines += ['', '## Evidence and reproduction', '',
              '- [Run summary, every source hash, and mismatch lists](task_pq_check.json)',
              '- [Every scalar/structural comparison, including all intervals and min/max](task_pq_comparisons.csv)',
              '- [All 1,980 month rows](task_pq_months.csv)',
              '- [All threshold failures (header only when none)](task_pq_failures.csv)',
              '- [All raw source-hash differences](task_pq_provenance_differences.csv)', '',
              'From the repository root, using the NumPy environment:', '', '```powershell',
              '$py = "C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe"',
              '& $py -m unittest discover -s pipeline/tests -p test_task_pq.py',
              '& $py pipeline/task_pq_check.py',
              '& $py pipeline/task_pq_report.py', '```', '',
              'Use `--resume` on the checker to reuse independently generated hourly state caches. Cache fingerprints include the full '
              'ephemeris, site list, horizon and checker bytes; packed-state payload hashes are checked before reuse. '
              'The default command always recomputes every state. Runtime caches/progress markers need not be committed. '
              'The checker overwrites prior PASS state with RUNNING before opening inputs and exits nonzero on error/incompleteness. '
              'The report refuses changed source/evidence hashes, incomplete coverage or failed checks. Production files are unchanged.', '']
    target = root/'docs/task_pq_check.md'
    target.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(status='PASS', sites=33, months=len(grouped), intervals=counts, gaps=gaps, report=str(target))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        render(args.root.resolve())
    except Exception as exc:
        # Do not leave an earlier PASS narrative displayed as the latest result.
        (args.root/'docs/task_pq_check.md').write_text(f'# Task P/Q report unavailable\n\nERROR: {type(exc).__name__}: {exc}\n', encoding='utf-8')
        raise
