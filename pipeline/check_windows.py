"""Validate proposed contract section 18: windows, gaps and input identity.

Called by check_contract.py; no optional scientific packages are required.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2031, 1, 1, tzinfo=timezone.utc)
N = 43824


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def stringify_site_hashes(sites_file):
    """Use Node itself: Python's JSON formatting is not JSON.stringify."""
    node = os.environ.get('LLSN_NODE') or shutil.which('node')
    if not node:
        raise ValueError('Node is required to verify exact JSON.stringify(site) hashes')
    script = """
const fs = require('node:fs');
const crypto = require('node:crypto');
const sites = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
const hashes = Object.fromEntries(sites.map(site => [site.id,
  crypto.createHash('sha256').update(JSON.stringify(site), 'utf8').digest('hex')]));
process.stdout.write(JSON.stringify(hashes));
"""
    try:
        result = subprocess.run([node, '--input-type=commonjs', '-e', script, str(sites_file)],
                                capture_output=True, text=True, encoding='utf-8',
                                check=True, timeout=30)
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise ValueError('Cannot verify JSON.stringify(site) hashes: ' + str(error)) from error


def hour(text):
    if not isinstance(text, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:00:00Z', text):
        raise ValueError('UTC hour string required')
    value = (datetime.fromisoformat(text.replace('Z', '+00:00')) - START).total_seconds() / 3600
    if value != int(value) or not 0 <= value <= N:
        raise ValueError('UTC edge outside hourly window')
    return int(value)


def interval(a, b):
    from datetime import timedelta
    return dict(start_utc=(START + timedelta(hours=a)).isoformat().replace('+00:00', 'Z'),
                end_utc=(START + timedelta(hours=b)).isoformat().replace('+00:00', 'Z'),
                duration_h=b-a, clipped_start=a == 0, clipped_end=b == N)


def validate_document(doc, site, horizon):
    if doc.get('format') != 'site-windows-v1' or doc.get('mock') is not False:
        raise ValueError('real site-windows-v1 required')
    for k in ('id', 'lat', 'lon'):
        if doc.get(k) != site[k]:
            raise ValueError(f'{k} differs from catalogue')
    if doc.get('h0_m') != horizon['h0_m'] or doc.get('obs_height_m') != 2:
        raise ValueError('observer geometry differs from real horizon')
    if hour(doc['start_utc']) != 0 or hour(doc['end_utc']) != N or doc.get('n') != N or doc.get('step_h') != 1:
        raise ValueError('wrong five-year window')
    for body in ('sun', 'earth'):
        group = doc[body]
        ranges = []
        for row in group['visible']:
            a, b = hour(row['start_utc']), hour(row['end_utc'])
            if a >= b or (ranges and a <= ranges[-1][1]):
                raise ValueError(f'{body}: intervals must be maximal, ordered and disjoint')
            if row != interval(a, b):
                raise ValueError(f'{body}: duration or clipping flags incorrect')
            ranges.append((a, b))
        count = sum(b-a for a, b in ranges)
        if type(group['visible_hours']) is not int or group['visible_hours'] != count:
            raise ValueError(f'{body}: wrong visible-hours count')
        gaps, at = [], 0
        for a, b in ranges:
            if a > at:
                gaps.append(interval(at, a))
            at = b
        if at < N:
            gaps.append(interval(at, N))
        gaps.sort(key=lambda x: (-x['duration_h'], x['start_utc']))
        if group['longest_gaps'] != gaps[:10]:
            raise ValueError(f'{body}: longest gaps differ from complement, sorting or clipping')
    hashes = doc['source']
    for key in ('core_sha256', 'ephem_sha256', 'ephem_meta_sha256', 'site_sha256', 'horizon_sha256', 'producer_sha256'):
        if not isinstance(hashes.get(key), str) or not re.fullmatch('[0-9a-f]{64}', hashes[key]):
            raise ValueError('invalid provenance hash: ' + key)


def check_windows(data, sites, err, warn):
    folder = data / 'windows'
    if not folder.exists():
        return
    files = sorted(p for p in folder.glob('*.json') if p.name != 'index.json')
    try:
        site_hashes = stringify_site_hashes(data / 'sites.json')
        producer_hash = digest(Path(__file__).with_name('build_windows.mjs'))
    except (OSError, ValueError) as error:
        err('windows provenance', str(error))
        return
    for file in files:
        where = f'windows/{file.name}'
        try:
            doc = json.loads(file.read_text(encoding='utf-8'))
            if file.stem != doc['id'] or doc['id'] not in sites:
                raise ValueError('ID/file/catalogue mismatch')
            hfile = data / 'horizon' / (doc['id'] + '.json')
            horizon = json.loads(hfile.read_text(encoding='utf-8'))
            if horizon.get('mock') is not False or horizon.get('flat') or horizon.get('site_coords_mock'):
                raise ValueError('real terrain required')
            if (horizon.get('lat'), horizon.get('lon')) != (doc['lat'], doc['lon']):
                raise ValueError('horizon coordinate mismatch')
            validate_document(doc, sites[doc['id']], horizon)
            if doc['source']['site_sha256'] != site_hashes[doc['id']]:
                raise ValueError('input changed: site_sha256 (exact JSON.stringify(site))')
            if doc['source']['producer_sha256'] != producer_hash:
                raise ValueError('input changed: producer_sha256 (actual build_windows.mjs bytes)')
            for key, file_path in [('horizon_sha256', hfile), ('ephem_sha256', data / 'ephem.bin'),
                                   ('ephem_meta_sha256', data / 'ephem.json'),
                                   ('core_sha256', data.parent / 'js/core.js')]:
                if doc['source'][key] != digest(file_path):
                    raise ValueError('input changed: ' + key)
        except (KeyError, TypeError, ValueError, OSError) as error:
            err(where, str(error))
    try:
        idx = json.loads((folder / 'index.json').read_text(encoding='utf-8'))
        if idx['format'] != 'site-windows-v1' or idx['mock'] is not False or idx['n'] != N or idx['step_h'] != 1:
            raise ValueError('invalid index format/time/mock')
        if hour(idx['start_utc']) != 0 or hour(idx['end_utc']) != N:
            raise ValueError('index time range mismatch')
        if len(idx['ids']) != len(set(idx['ids'])) or set(idx['ids']) != {p.stem for p in files}:
            raise ValueError('index IDs differ from actual window files')
        if set(idx['ids']) & set(idx['skipped']) or set(idx['ids']) | set(idx['skipped']) != set(sites):
            raise ValueError('index must account for every catalogue site exactly once')
        if idx['skipped']:
            warn('windows/index.json', 'skipped sites: ' + ', '.join(sorted(idx['skipped'])))
    except (KeyError, TypeError, ValueError, OSError) as error:
        err('windows/index.json', str(error))
    print(f'windows: {len(files)} site files')
