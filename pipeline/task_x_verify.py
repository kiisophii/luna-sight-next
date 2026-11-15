"""Independent developer control for Task X; CPU only, no producer imports.

Reader and PROJ/ECEF reference adapted from the standalone task_b_full_check.py
(Jiyong's AI-assisted independent implementation). This is developer verification
within the same AI-assisted team, NOT the taskboard's another-person sign-off.

Run: python pipeline/task_x_verify.py
Missing public site files are reported as pending; rerun resumes checked nodes.
All checkpoints and evidence are contained in docs/task_x_check.json.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS'):
    os.environ[_name] = '1'

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import time
import traceback

import numpy as np
from pyproj import Geod

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/task_x_check.json'
R = 1737400.0
GEOD = Geod(a=R, b=R)
SITE_IDS = ('APOLLO17', 'CHANGE4', 'CHANDRAYAAN3')
SEED = 20261115
KEYS = ('sun_frac', 'earth_frac', 'both_frac', 'longest_dark_h')
PARAMS = dict(min_km=.2, max_km=300., n_steps=4000, obs_height_m=2.)
WINDOW = dict(start='2026-01-01T00:00:00Z', step_h=1, n=43824)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(report):
    temporary = REPORT.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(REPORT)


_hashes = {}


def sha(path):
    path = Path(path)
    key = (str(path), path.stat().st_size, path.stat().st_mtime_ns)
    if key not in _hashes:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                digest.update(block)
        _hashes[key] = digest.hexdigest()
    return _hashes[key]


def identity(path):
    return dict(path=Path(path).relative_to(ROOT).as_posix(), sha256=sha(path), bytes=Path(path).stat().st_size)


def bilinear(array, row, col, wrap=False):
    """Interpolate four source pixels; outside a window remains missing."""
    ny, nx = array.shape
    valid = np.isfinite(row) & np.isfinite(col) & (row >= 0) & (row <= ny - 1)
    if not wrap:
        valid &= (col >= 0) & (col <= nx - 1)
    y = np.clip(np.floor(row).astype(np.int64), 0, ny - 2)
    x = np.floor(col).astype(np.int64)
    if not wrap:
        x = np.clip(x, 0, nx - 2)
    a, b = row - y, col - x
    value = ((1-a) * ((1-b)*array[y, x % nx] + b*array[y, (x+1) % nx])
             + a * ((1-b)*array[y+1, x % nx] + b*array[y+1, (x+1) % nx]))
    return np.where(valid, value, np.nan)


class Terrain:
    def __init__(self, site):
        self.sources, self.manifest = [], []
        if abs(site['lat']) < 60:
            path = ROOT / 'data/processed/task_x/raw/sldem' / (site['id'] + '.npz')
            with np.load(path, allow_pickle=False) as z:
                meta = json.loads(str(z['meta']))
                lat, lon, height = z['lat'], z['lon_unwrapped'], z['height_m']
                assert meta['radius_km'] >= 166
                assert (meta['site_lat'], meta['site_lon']) == (site['lat'], site['lon'])
                assert np.all(np.diff(lat) < 0) and np.all(np.diff(lon) > 0)
                assert height.shape == (len(lat), len(lon))
                self.sources.append(dict(kind='window', name='SLDEM2015', array=height,
                    lat0=float(lat[0]), lon0=float(lon[0]), mid=float((lon[0]+lon[-1])/2),
                    dlat=float((lat[0]-lat[-1])/(len(lat)-1)),
                    dlon=float((lon[-1]-lon[0])/(len(lon)-1)), gate_m=150000.))
            self.manifest.append(dict(**identity(path), metadata=meta, gate_m=150000.))
        for ppd in (64, 16):
            path = ROOT / 'data/processed/local250/raw/global' / f'ldem_{ppd}_float.img'
            label = path.with_suffix('.lbl')
            text = label.read_text(encoding='latin-1')
            def value(name):
                match = re.search(r'^\s*' + name + r'\s*=\s*([-+0-9.eE]+)', text, re.M)
                if not match:
                    raise ValueError(f'Missing PDS label value: {name}')
                return float(match[1])
            ny, nx = int(value('LINES')), int(value('LINE_SAMPLES'))
            assert 'PC_REAL' in text and value('SAMPLE_BITS') == 32
            assert value('OFFSET') == R/1000 and path.stat().st_size == ny*nx*4
            self.sources.append(dict(kind='global', name=f'LDEM_{ppd}',
                array=np.memmap(path, dtype='<f4', mode='r', shape=(ny, nx)),
                ppd=value('MAP_RESOLUTION'), lpo=value('LINE_PROJECTION_OFFSET'),
                spo=value('SAMPLE_PROJECTION_OFFSET'), clon=value('CENTER_LONGITUDE'),
                scale=value('SCALING_FACTOR')*1000, gate_m=300000.))
            self.manifest.append(dict(**identity(path), label=identity(label), gate_m=300000.))

    def sample(self, lat, lon, distance, counts=None):
        out = np.full(lat.shape, np.nan, dtype=np.float64)
        for source in self.sources:
            missing = np.isnan(out) & (distance <= source['gate_m'] + 1e-7)
            if not np.any(missing):
                continue
            if source['kind'] == 'window':
                lu = (lon-source['mid']+180) % 360 + source['mid']-180
                v = bilinear(source['array'], (source['lat0']-lat)/source['dlat'],
                             (lu-source['lon0'])/source['dlon'])
            else:
                row = np.clip(source['lpo']-lat*source['ppd'], 0, source['array'].shape[0]-1)
                col = source['spo']+((lon % 360)-source['clon'])*source['ppd']
                v = bilinear(source['array'], row, col, True)*source['scale']
            used = missing & np.isfinite(v)
            if counts is not None:
                counts[source['name']] = counts.get(source['name'], 0) + int(used.sum())
            out = np.where(missing, v, out)
        return out


def frame(lat, lon):
    la, lo = np.radians([lat, lon])
    up = np.array([np.cos(la)*np.cos(lo), np.cos(la)*np.sin(lo), np.sin(la)])
    east = np.array([-np.sin(lo), np.cos(lo), 0.])
    return up, east, np.cross(up, east)


def horizon(lat, lon, terrain):
    """PROJ great-circle positions, ECEF subtraction, all 720 x 4001 samples."""
    up, east, north = frame(lat, lon)
    ground = float(terrain.sample(np.array([lat]), np.array([lon]), np.array([0.]))[0])
    assert np.isfinite(ground)
    observer = up*(R+ground+2)
    distances = np.geomspace(200., 300000., 4001)
    mask, counts = [], {}
    for first in range(0, 720, 60):
        dd = np.broadcast_to(distances, (60, len(distances))).copy()
        az = np.broadcast_to(np.arange(first, first+60)[:, None]*.5, dd.shape).copy()
        lo, la, _ = GEOD.fwd(np.full(dd.shape, lon), np.full(dd.shape, lat), az, dd)
        heights = terrain.sample(la, lo, dd, counts)
        if not np.isfinite(heights).all():
            raise ValueError('Missing terrain in full ray march')
        la, lo = np.radians(la), np.radians(lo)
        ray = np.stack([np.cos(la)*np.cos(lo), np.cos(la)*np.sin(lo), np.sin(la)], axis=-1)
        ray = ray*(R+heights)[..., None]-observer
        angle = np.degrees(np.arctan2(ray@up, np.hypot(ray@east, ray@north)))
        mask.extend(angle.max(axis=1).tolist())
    assert sum(counts.values()) == 720*4001
    return ground, np.asarray(mask), counts


def metrics(lat, lon, ground, mask, ephem):
    """Independent hourly classification with explicit longest-dark accumulation."""
    up, east, north = frame(lat, lon)
    observer_km = up*(R+ground+2)/1000
    margins = []
    for offset in (0, 3):
        ray = ephem[:, offset:offset+3]-observer_km
        el = np.degrees(np.arctan2(ray@up, np.hypot(ray@east, ray@north)))
        az = np.degrees(np.arctan2(ray@east, ray@north)) % 360
        pos = az/.5
        low = np.floor(pos).astype(int) % 720
        weight = pos-np.floor(pos)
        line = mask[low]*(1-weight)+mask[(low+1) % 720]*weight
        margins.append(el-line)
    ns = ne = nb = run = longest = 0
    for sun_margin, earth_margin in zip(*margins):
        sun, earth = sun_margin >= 0, earth_margin > 0
        ns += int(sun)
        ne += int(earth)
        nb += int(sun and earth)
        run = 0 if sun else run+1
        longest = max(longest, run)
    n = len(ephem)
    return dict(sun_frac=ns/n, earth_frac=ne/n, both_frac=nb/n, longest_dark_h=longest)


def node(site, index):
    east, north = (index % 41-20)*250, (index//41-20)*250
    lon, lat, _ = GEOD.fwd(site['lon'], site['lat'], float(np.degrees(np.arctan2(east, north))),
                         float(np.hypot(east, north)))
    if east == north == 0:
        lat, lon = site['lat'], site['lon']
    return dict(index=index, e_m=east, n_m=north, lat=lat, lon=lon)


def resources():
    """One process, one logical CPU, one numerical thread; never use GPU."""
    if os.name != 'nt':
        if hasattr(os, 'sched_getaffinity'):
            available = os.sched_getaffinity(0)
            os.sched_setaffinity(0, {max(available)})
        return
    kernel = ctypes.windll.kernel32
    process = ctypes.c_void_p(-1)
    current, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process, ctypes.byref(current), ctypes.byref(system)):
        raise ctypes.WinError()
    chosen = 1 << (current.value.bit_length()-1)
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(process, chosen):
        raise ctypes.WinError()


def self_test():
    image = np.array([[0., 2.], [4., 6.]])
    assert bilinear(image, np.array([.5]), np.array([.5]))[0] == 3
    assert np.isnan(bilinear(image, np.array([2.]), np.array([0.]))[0])
    fixture = Terrain.__new__(Terrain)
    fixture.sources = [dict(kind='window', name='near', array=np.ones((2, 2))*7,
        lat0=1., lon0=-1., mid=0., dlat=2., dlon=2., gate_m=150000.),
        dict(kind='global', name='global', array=np.ones((2, 4))*3, ppd=1/90,
             lpo=.5, spo=-.5, clon=0., scale=1000., gate_m=300000.)]
    samples = fixture.sample(np.zeros(4), np.array([0., 0., 359.5, 40.]),
                             np.array([150000., 150000.01, 100., 100.]))
    assert np.array_equal(samples, [7., 3000., 7., 3000.])
    fixture.sources[0]['array'][0, 0] = np.nan
    assert fixture.sample(np.array([0.]), np.array([0.]), np.array([0.]))[0] == 3000.
    class Sphere:
        def sample(self, lat, lon, distance, counts=None):
            if counts is not None:
                counts['sphere'] = counts.get('sphere', 0)+lat.size
            return np.zeros(lat.shape)
    ground, mask, _ = horizon(20., 30., Sphere())
    dist = np.geomspace(200., 300000., 4001)
    expected = np.degrees(np.arctan2(R*np.cos(dist/R)-(R+2), R*np.sin(dist/R))).max()
    assert ground == 0 and np.max(np.abs(mask-expected)) < 1e-8
    up, east, north = frame(0., 0.)
    observer = up*(R+2)/1000
    sun = [up, -up, -up, up, -up]
    earth = [up, up, -up, up, up]
    ephem = np.array([np.r_[observer+s*1e6, observer+e*1e5] for s, e in zip(sun, earth)])
    assert metrics(0., 0., 0., np.zeros(720), ephem) == dict(
        sun_frac=.4, earth_frac=.8, both_frac=.4, longest_dark_h=2)
    # Exact equality distinguishes Sun >= horizon from Earth > horizon.
    tangent = np.array([np.r_[observer+north*1e6, observer+north*1e5]])
    assert metrics(0., 0., 0., np.zeros(720), tangent) == dict(
        sun_frac=1., earth_frac=0., both_frac=0., longest_dark_h=0)
    return dict(passed=True, checks=['bilinear interpolation and missing bounds',
        'observer-centred 150 km gate, longitude wrapping, window and NaN fallback',
        'full 720x4001 rays against analytic sphere curvature',
        'hourly fractions and clipped longest dark run', 'Sun/Earth equality boundary'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    resources()
    tests = self_test()
    if args.self_test:
        print(json.dumps(tests), flush=True)
        return 0
    started = time.time()
    prior = read(REPORT) if REPORT.exists() else {}
    rng = random.Random(SEED)
    selected = {sid: sorted(rng.sample(range(1681), 5)) for sid in SITE_IDS}
    code = identity(Path(__file__))
    ephmeta = read(ROOT/'web/data/ephem.json')
    assert all(ephmeta[k] == v for k, v in WINDOW.items())
    assert ephmeta['frame'] == 'MOON_ME_DE421' and ephmeta['units'] == 'km' and not ephmeta['mock']
    ephem = np.fromfile(ROOT/'web/data/ephem.bin', dtype='<f4').reshape(43824, 6).astype(float)
    assert np.isfinite(ephem).all()
    shared = dict(code=code, ephemeris=identity(ROOT/'web/data/ephem.bin'),
                  ephemeris_metadata=identity(ROOT/'web/data/ephem.json'), catalogue=identity(ROOT/'web/data/sites.json'))
    report = dict(complete=False, passed=False, checker='AI-assisted independent developer control',
        producer='Jiyong Sung / AI-assisted task_x GPU pipeline', human_independent_signoff=False,
        limitation='Does not satisfy taskboard requirement for another human team member sign-off.',
        method='Independent NumPy source readers; PROJ spherical destinations and ECEF subtraction; CPU full rays; independent hourly loop; no producer imports.',
        attribution='Reader and PROJ/ECEF reference adapted from standalone pipeline/task_b_full_check.py; no module import.',
        backend='CPU only', processes=1, logical_cpus=1, numerical_threads=1,
        criterion_fraction_pp=1., darkness_criterion='Report difference in hours; no specified threshold.',
        parameters=dict(**PARAMS, distances=4001, azimuths=720, az_step_deg=.5, early_stop=False,
                        sldem_gate_m=150000, mask_decimals=4, ground_decimals=2),
        window=WINDOW, seed=SEED, random_method='Python random.Random(seed); sample(range(1681),5), in SITE_IDS order',
        selected_nodes=selected, inputs=shared, self_tests=tests, sites=[], pending=[], failures=[])
    catalogue = {s['id']: s for s in read(ROOT/'web/data/sites.json')}
    old_sites = {s['id']: s for s in prior.get('sites', [])}
    for sid in SITE_IDS:
        path = ROOT/'web/data/local250'/f'{sid}.json'
        raw = ROOT/'data/processed/task_x/raw/sldem'/f'{sid}.npz'
        site = catalogue[sid]
        if not path.exists() or (abs(site['lat']) < 60 and not raw.exists()):
            report['pending'].append(sid)
            write(report)
            print('PENDING', sid, flush=True)
            continue
        item = dict(id=sid, complete=False, nodes=[])
        report['sites'].append(item)
        try:
            public = read(path)
            assert public['id'] == sid and public['complete'] and not public['mock']
            assert public['center'] == {k: site[k] for k in ('lat', 'lon')}
            assert public['params'] == PARAMS and public['window'] == WINDOW
            assert public['frame'] == 'MOON_ME_DE421' and public['radius_m'] == R
            grid = public['grid']
            assert all(grid[k] == v for k, v in dict(rows=41, cols=41, spacing_m=250, origin_e_m=-5000, origin_n_m=-5000).items())
            assert len(public['points']) == 1681
            terrain = Terrain(site)
            producer_inputs = {s['path']: s for s in public['provenance']['terrain_sources']}
            for source in terrain.manifest:
                assert producer_inputs[source['path']]['sha256'] == source['sha256']
                if 'label' in source:
                    assert producer_inputs[source['path']]['label_sha256'] == source['label']['sha256']
            for name in ('web/data/ephem.bin', 'web/data/ephem.json', 'web/data/sites.json'):
                assert public['provenance']['files_sha256'][name] == sha(ROOT/name)
            item['inputs'] = dict(**shared, public_output=identity(path), terrain_sources=terrain.manifest)
            fingerprint = hashlib.sha256(json.dumps(item['inputs'], sort_keys=True).encode()).hexdigest()
            old = {n['index']: n for n in old_sites.get(sid, {}).get('nodes', [])}
            for index in selected[sid]:
                begin = time.time()
                point = node(site, index)
                published = public['points'][index]
                assert all(published[k] == point[k] for k in ('index', 'e_m', 'n_m'))
                _, _, coord_error = GEOD.inv(point['lon'], point['lat'], published['lon'], published['lat'])
                assert abs(coord_error) < .001
                assert all(np.isfinite(published[k]) for k in (*KEYS, 'h0_m'))
                cached = old.get(index, {})
                reusable = (cached.get('fingerprint') == fingerprint and len(cached.get('mask', [])) == 720
                            and np.isfinite(cached.get('mask', [])).all())
                if reusable:
                    ground, mask, counts = cached['ground_m'], np.asarray(cached['mask']), cached['source_sample_counts']
                else:
                    ground, mask, counts = horizon(point['lat'], point['lon'], terrain)
                raw_metrics = metrics(point['lat'], point['lon'], ground, mask, ephem)
                stored_mask = np.asarray([round(float(v), 4) for v in mask])
                rounded_metrics = metrics(point['lat'], point['lon'], round(ground, 2), stored_mask, ephem)
                expected = {k: published[k] for k in KEYS}
                comparisons = {}
                for name, values in (('unrounded', raw_metrics), ('production_serialization', rounded_metrics)):
                    pp = {k: (values[k]-expected[k])*100 for k in KEYS[:3]}
                    comparisons[name] = dict(fraction_difference_pp=pp,
                        longest_dark_difference_h=values['longest_dark_h']-expected['longest_dark_h'],
                        within_1pp=all(abs(v) <= 1+1e-12 for v in pp.values()))
                    if not comparisons[name]['within_1pp']:
                        report['failures'].append(dict(id=sid, index=index, comparison=name, **comparisons[name]))
                row = dict(**point, fingerprint=fingerprint, coordinate_error_m=float(coord_error),
                    ground_m=ground, published_ground_m=published['h0_m'],
                    ground_difference_m=round(ground, 2)-published['h0_m'],
                    mask=mask.tolist(), source_sample_counts=counts, ray_samples=720*4001,
                    published=expected, unrounded=raw_metrics, production_serialization=rounded_metrics,
                    comparisons=comparisons, elapsed_s=time.time()-begin, resumed=bool(reusable))
                item['nodes'].append(row)
                write(report)
                print('CHECKED', sid, index, round(row['elapsed_s'], 2), 's', comparisons, flush=True)
            item['complete'] = True
            del terrain
        except Exception as exc:
            report['failures'].append(dict(id=sid, error=repr(exc), traceback=traceback.format_exc()))
            print('FAILED', sid, repr(exc), flush=True)
        write(report)
    rows = [n for s in report['sites'] for n in s['nodes']]
    report['n_nodes'] = len(rows)
    report['complete'] = len(rows) == 15 and not report['pending'] and all(s['complete'] for s in report['sites'])
    report['passed'] = report['complete'] and not report['failures']
    report['maximums'] = {name: dict(
        fraction_abs_diff_pp=max((abs(v) for n in rows for v in n['comparisons'][name]['fraction_difference_pp'].values()), default=None),
        longest_dark_abs_diff_h=max((abs(n['comparisons'][name]['longest_dark_difference_h']) for n in rows), default=None))
        for name in ('unrounded', 'production_serialization')}
    report['elapsed_s'] = time.time()-started
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    write(report)
    print(json.dumps({k: report[k] for k in ('complete', 'passed', 'n_nodes', 'pending', 'maximums')}), flush=True)
    return 0 if report['passed'] else (1 if report['failures'] else 2)


if __name__ == '__main__':
    try:
        status = main()
    except Exception as exc:
        try:
            failed = read(REPORT) if REPORT.exists() else {}
        except (OSError, ValueError):
            failed = {}
        failed.update(complete=False, passed=False, finished_utc=datetime.now(timezone.utc).isoformat())
        failed.setdefault('failures', []).append(dict(stage='setup or top-level', error=repr(exc),
            traceback=traceback.format_exc(), verifier_sha256=sha(Path(__file__))))
        write(failed)
        raise
    raise SystemExit(status)
