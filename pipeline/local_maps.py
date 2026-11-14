"""Card 18: resumable local horizons and actual core.js metrics.

Expanded NPZ windows are storage envelopes. Range gates are centred on EACH
grid observer, not on the catalogue point. Shared read-only NPY rasters avoid
one expanded raster copy per worker. Raw windows/checkpoints stay ignored.
"""
import argparse
import atexit
import concurrent.futures as cf
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
import horizon as hz

ROOT = Path(__file__).resolve().parents[1]
IDS = ['SHACKLETON_RIM', 'ARTEMIS_HAWORTH', 'ARTEMIS_MALAPERT',
       'CONNECTING_RIDGE', 'PEAK_NEAR_SHACKLETON', 'DE_GERLACHE_RIM1']
GATES = {5: 3., 10: 25., 20: 25., 60: 60., 80: 60., 240: 200.}
PARAMS = dict(min_km=.005, max_km=300., n_steps=8000, obs_height_m=2.)
# Card 20 review: non-polar sites (lat > -75) use the card 9 horizon settings, so the grid centre equals
# web/data/horizon/<ID>.json and web/data/metrics/<ID>.json exactly (near field < 200 m not marched).
PARAMS_CARD9 = dict(min_km=.2, max_km=300., n_steps=4000, obs_height_m=2.)


def params_for(site):
    return PARAMS if site['lat'] <= -75.0 else PARAMS_CARD9
METRICS = ['sun_frac', 'earth_frac', 'both_frac', 'longest_dark_h']
POLAR_LAT = -75.0          # card 20: PGDA polar chain for lat <= -75
SLDEM_LAT = 60.0           # SLDEM2015 covers |lat| < 60
SLDEM_GATE_KM = 150.0      # same near-field gate as card 9


def catalogue_ids():
    """All catalogue sites, card 18 six first, then south-polar, then the rest (card 20 order)."""
    sites = json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
    rest = [s for s in sites if s['id'] not in IDS]
    return IDS + [s['id'] for s in rest if s['lat'] <= POLAR_LAT] + [s['id'] for s in rest if s['lat'] > POLAR_LAT]


def not_covered(raw, sid, resolution):
    """True when the source raster genuinely does not cover this site (recorded by the fetch step)."""
    for status_path in [raw.parent/f'download_{resolution}.json', *sorted(raw.parent.glob('fetch27_status*.json'))]:
        if not status_path.exists():
            continue
        status = json.loads(status_path.read_text(encoding='utf-8'))
        rows = status.get('rows', []) + list(status.get('polar', {}).values())
        if any(r.get('id') == sid and r.get('res_m', resolution) == resolution
               and r.get('status') == 'outside_source_coverage' for r in rows):
            return True
    return False


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def grid_points(site):
    result = []
    for n in range(-10000, 10001, 1000):
        for e in range(-10000, 10001, 1000):
            lat, lon = hz.destination(site['lat'], site['lon'], np.degrees(np.arctan2(e, n)), np.hypot(e, n))
            if e == n == 0:
                lat, lon = site['lat'], site['lon']
            result.append(dict(index=len(result), e_m=e, n_m=n, lat=float(lat), lon=float(lon)))
    return result


def prepare_sampler(path, shared, gate_km):
    path, shared = Path(path), Path(shared)
    digest = sha_file(path)
    shared.mkdir(parents=True, exist_ok=True)
    array_path, meta_path = shared/(digest+'.npy'), shared/(digest+'.json')
    if not (array_path.exists() and meta_path.exists()):
        sampler = hz.PolarStereoSampler(path)
        with array_path.with_suffix('.npy.tmp').open('wb') as stream:
            np.save(stream, sampler.h)
        array_path.with_suffix('.npy.tmp').replace(array_path)
        meta = {k: getattr(sampler, k) for k in ['x0', 'dx', 'y0', 'dy', 'res_m', 'name', 'radius_km', 'meta']}
        hz.write_json_atomic(meta_path, meta)
    return dict(path=str(path.resolve()), array_path=str(array_path.resolve()),
                meta_path=str(meta_path.resolve()), sha256=digest, gate_km=gate_km)


def prepare_latlon_sampler(path, shared, gate_km):
    """SLDEM2015 window (card 3 cache) -> shared read-only NPY, like prepare_sampler."""
    path, shared = Path(path), Path(shared)
    digest = sha_file(path)
    shared.mkdir(parents=True, exist_ok=True)
    array_path, meta_path = shared/(digest+'.npy'), shared/(digest+'.json')
    if not (array_path.exists() and meta_path.exists()):
        sampler = hz.LatLonWindowSampler(path)
        with array_path.with_suffix('.npy.tmp').open('wb') as stream:
            np.save(stream, sampler.h)
        array_path.with_suffix('.npy.tmp').replace(array_path)
        meta = {k: getattr(sampler, k) for k in ['lat0', 'dlat', 'lon0', 'dlon', 'res_m', 'name', 'radius_km', 'meta']}
        meta['meta'] = dict(meta['meta'] or {}, res_m=sampler.res_m)
        hz.write_json_atomic(meta_path, meta)
    return dict(path=str(path.resolve()), array_path=str(array_path.resolve()),
                meta_path=str(meta_path.resolve()), sha256=digest, gate_km=gate_km, kind='latlon')


def load_sampler(descriptor):
    # Reuse the production sampler's sampling method with shared backing storage.
    if descriptor.get('kind') == 'latlon':
        sampler = hz.LatLonWindowSampler.__new__(hz.LatLonWindowSampler)
        sampler.__dict__.update(json.loads(Path(descriptor['meta_path']).read_text(encoding='utf-8')))
        sampler.path = Path(descriptor['path'])
        sampler.h = np.load(descriptor['array_path'], mmap_mode='r')
        return sampler
    sampler = hz.PolarStereoSampler.__new__(hz.PolarStereoSampler)
    sampler.__dict__.update(json.loads(Path(descriptor['meta_path']).read_text(encoding='utf-8')))
    sampler.path = Path(descriptor['path'])
    sampler.h = np.load(descriptor['array_path'], mmap_mode='r')
    return sampler


def validate_source_metadata(meta, site, gate):
    if any(meta.get('site',{}).get(k)!=site[k] for k in ['id','lat','lon']):
        raise ValueError('Terrain centre does not match catalogue')
    if meta.get('radius_m',0)<(gate+16)*1000 or meta.get('frame')!='MOON_ME_DE421':
        raise ValueError('Expected expanded terrain window and production frame')


class CoreMetrics:
    def __init__(self, root=ROOT):
        self.process = subprocess.Popen(['node', str(root/'pipeline/local_metrics.mjs')],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        first = self.process.stdout.readline()
        if not first:
            raise RuntimeError('core.js adapter failed: '+self.process.stderr.read())
        self.identity = json.loads(first)
        if not self.identity.get('ready'):
            raise RuntimeError('core.js adapter not ready')

    def metrics(self, site, horizon):
        self.process.stdin.write(json.dumps(dict(site=site, horizon=horizon))+'\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('core.js adapter stopped')
        value = json.loads(line)
        if 'error' in value:
            raise ValueError(value['error'])
        return value['metrics']

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=10)
        self.process.stdout.close()
        self.process.stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def valid_metrics(m):
    return (all(k in m and np.isfinite(m[k]) for k in METRICS)
            and all(0 <= m[k] <= 1 for k in METRICS[:3])
            and m['both_frac'] <= min(m['sun_frac'], m['earth_frac'])
            and isinstance(m['longest_dark_h'], int) and 0 <= m['longest_dark_h'] <= 43824)


def resume_valid(path, key, index):
    try:
        r = json.loads(Path(path).read_text(encoding='utf-8'))
        h = r['horizon']
        return (r['input_key'] == key and r['index'] == index and valid_metrics(r['metrics'])
                and len(h['mask']) == 720 and np.isfinite(h['mask']).all()
                and np.isfinite(h['h0_m']) and h['engine']['n_missing_samples'] == 0)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def validate_map(record):
    points = record['points']
    if len(points) != 441 or [p['index'] for p in points] != list(range(441)):
        raise ValueError('Expected 441 ordered complete points')
    if record['window'] != dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824):
        raise ValueError('Invalid production window')
    expected_grid=dict(rows=21,cols=21,spacing_m=1000,origin_e_m=-10000,origin_n_m=-10000)
    if any(record['grid'].get(k)!=v for k,v in expected_grid.items()):
        raise ValueError('Invalid grid geometry')
    if record['frame']!='MOON_ME_DE421' or record['radius_m']!=hz.R_M or record['params']!=params_for(record['center']):
        raise ValueError('Invalid frame or horizon parameters')
    for p,expected in zip(points,grid_points(record['center'])):
        if any(p[k]!=expected[k] for k in ['index','e_m','n_m']):
            raise ValueError('Invalid grid node order')
        if abs(p['lat']-expected['lat'])>1e-9 or abs((p['lon']-expected['lon']+180)%360-180)>1e-9:
            raise ValueError('Invalid grid point coordinates')
        if not valid_metrics(p) or not np.isfinite([p['lat'],p['lon'],p['h0_m']]).all():
            raise ValueError('Invalid point metrics or geometry')
        if not (-90 <= p['lat'] <= 90 and -180 <= p['lon'] <= 180):
            raise ValueError('Point outside coordinate domain')
    if not record['complete'] or record['mock']:
        raise ValueError('Incomplete/mock local map')


_context = None


def init_worker(descriptors, globals_, key, site, work):
    global _context
    chain = [(load_sampler(d), d['gate_km']) for d in descriptors]
    chain += [(hz.GlobalCylSampler(p), 300.) for p in globals_]
    core = CoreMetrics()
    atexit.register(core.close)
    _context = chain, core, key, site, Path(work)


def compute_point(point):
    chain, core, key, site, work = _context
    begin = time.monotonic()
    local_site = dict(id=f"{site['id']}_LOCAL_{point['index']:03d}",lat=point['lat'],lon=point['lon'],mock=False)
    result = hz.compute_horizon(point['lat'], point['lon'], chain, **params_for(site))
    if result['n_missing']:
        raise ValueError(f"{local_site['id']}: missing ray samples")
    horizon = hz.horizon_record(local_site, result)
    metrics = core.metrics(local_site, horizon)
    if not valid_metrics(metrics):
        raise ValueError('Invalid core.js result')
    ground_resolution = None
    for sampler, _ in chain:
        if np.isfinite(sampler.sample(np.array([point['lat']]), np.array([point['lon']])))[0]:
            ground_resolution = float(sampler.res_m)
            break
    record = dict(**point, input_key=key, horizon=horizon, metrics=metrics,
                  ground_resolution_m=ground_resolution, elapsed_s=time.monotonic()-begin)
    hz.write_json_atomic(work/f"{point['index']:03d}.json", record)
    return point['index'], record['elapsed_s']


def run_site(site, raw, work, out, jobs, limit=None):
    begin = time.monotonic()
    descriptors, terrain = [], []
    if site['lat'] <= POLAR_LAT:
        for resolution, gate in GATES.items():
            path = raw/'polar'/str(resolution)/(site['id']+'.npz')
            if not path.exists():
                if not_covered(raw, site['id'], resolution):
                    continue
                raise ValueError(f'Missing expanded terrain: {path}')
            d = prepare_sampler(path, work/'shared', gate)
            validate_source_metadata(json.loads(Path(d['meta_path']).read_text(encoding='utf-8'))['meta'],site,gate)
            descriptors.append(d)
            terrain.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=d['sha256'],resolution_m=resolution,gate_km=gate))
    elif abs(site['lat']) < SLDEM_LAT:
        path = raw/'sldem'/(site['id']+'.npz')
        if not path.exists():
            raise ValueError(f'Missing expanded SLDEM window: {path}')
        d = prepare_latlon_sampler(path, work/'shared', SLDEM_GATE_KM)
        meta = json.loads(Path(d['meta_path']).read_text(encoding='utf-8'))['meta']
        if abs(meta.get('site_lat', 1e9)-site['lat'])>1e-9 or abs(meta.get('site_lon', 1e9)-site['lon'])>1e-9                 or float(meta.get('radius_km', 0)) < SLDEM_GATE_KM+16:
            raise ValueError('SLDEM window centre/radius does not match catalogue')
        descriptors.append(d)
        terrain.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=d['sha256'],resolution_m=round(float(meta.get('res_m', 59.2)),1),gate_km=SLDEM_GATE_KM))
    # else (e.g. CHANDRAYAAN3, 69 S): global LDEM chain only, as card 9
    globals_ = []
    for ppd in (64,16):
        path = raw/'global'/f'ldem_{ppd}_float.img'
        if path.exists():
            globals_.append(str(path))
            sampler = hz.GlobalCylSampler(path)
            terrain.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha_file(path),
                label_sha256=sha_file(path.with_suffix('.lbl')),resolution_m=sampler.res_m,gate_km=None))
    if not globals_:
        raise ValueError('Global far-field DEM required')
    inputs = {p:sha_file(ROOT/p) for p in ['web/js/core.js','web/data/ephem.bin','web/data/ephem.json',
        'pipeline/horizon.py','pipeline/local_maps.py','pipeline/local_metrics.mjs','pipeline/cache_metrics.mjs']}
    provenance = dict(terrain_sources=terrain,files_sha256=inputs,center=site,params=params_for(site))
    key = fingerprint(provenance)
    provenance['input_key'] = key
    point_dir = work/site['id']; point_dir.mkdir(parents=True,exist_ok=True)
    points = grid_points(site)
    todo = [p for p in points if not resume_valid(point_dir/f"{p['index']:03d}.json", key, p['index'])]
    print(f"{site['id']}: {441-len(todo)}/441 cached, {len(todo)} to compute, {jobs} workers",flush=True)
    if limit is not None:
        todo = todo[:limit]
    if todo:
        with cf.ProcessPoolExecutor(jobs, initializer=init_worker,
                initargs=(descriptors, globals_, key, site, str(point_dir))) as executor:
            futures = [executor.submit(compute_point,p) for p in todo]
            for count,future in enumerate(cf.as_completed(futures),1):
                index,seconds = future.result()
                if count%20==0 or count==len(todo):
                    print(f"{site['id']}: +{count}/{len(todo)}, last point {index} {seconds:.2f}s",flush=True)
    complete = all(resume_valid(point_dir/f"{p['index']:03d}.json",key,p['index']) for p in points)
    if not complete:
        print(f"{site['id']}: partial checkpoints only; no public export",flush=True)
        return dict(id=site['id'],complete=False,elapsed_s=time.monotonic()-begin)
    public = []
    for p in points:
        r=json.loads((point_dir/f"{p['index']:03d}.json").read_text(encoding='utf-8'))
        public.append(dict(**p,**r['metrics'],h0_m=r['horizon']['h0_m'],
            ground_resolution_m=r['ground_resolution_m'],dem_sources=r['horizon']['dem_sources']))
    obj=dict(id=site['id'],center={k:site[k] for k in ['lat','lon']},
        grid=dict(rows=21,cols=21,spacing_m=1000,origin_e_m=-10000,origin_n_m=-10000,
                  order='row-major, south to north and west to east; nodes, not cell averages'),
        window=dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824),params=params_for(site),
        frame='MOON_ME_DE421',radius_m=hz.R_M,provenance=provenance,points=public,complete=True,mock=False)
    validate_map(obj)
    hz.write_json_atomic(out/(site['id']+'.json'),obj)
    elapsed=time.monotonic()-begin
    print(f"{site['id']}: COMPLETE {elapsed:.1f}s",flush=True)
    return dict(id=site['id'],complete=True,elapsed_s=elapsed,computed=len(todo),resumed=441-len(todo))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',action='append')
    parser.add_argument('--raw',type=Path,default=ROOT/'data/processed/card18/raw')
    parser.add_argument('--work',type=Path,default=ROOT/'data/processed/card18/checkpoints')
    parser.add_argument('--out',type=Path,default=ROOT/'web/data/local')
    parser.add_argument('--jobs',type=int,default=os.cpu_count())
    parser.add_argument('--limit',type=int,help='Benchmark only this many missing points per site; never export partial data')
    args=parser.parse_args()
    if args.jobs<1 or (args.limit is not None and args.limit<1):parser.error('positive jobs/limit required')
    sites=json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
    started=time.time();runs=[]
    for sid in args.site or catalogue_ids():
        runs.append(run_site(next(s for s in sites if s['id']==sid),args.raw.resolve(),args.work.resolve(),args.out.resolve(),args.jobs,args.limit))
        hz.write_json_atomic(args.work/'last_run.json',dict(start_epoch=started,end_epoch=time.time(),jobs=args.jobs,runs=runs))


if __name__=='__main__':
    main()
