"""Card 23 (non-polar part): coordinate-uncertainty ranges around catalogue sites.

For every catalogue site with lat > -75 deg, an 11 x 11 node grid at 100 m spacing
(+-500 m east/north) is computed with the SAME horizon chain and parameters as the
production horizons (card 9, pipeline/run_horizons.py defaults) and the ACTUAL
web/js/core.js metrics (via pipeline/local_metrics.mjs), so the centre node reproduces
web/data/metrics/<ID>.json.

    python pipeline/coord_uncertainty.py                  # all non-polar sites
    python pipeline/coord_uncertainty.py --site APOLLO17  # one site (repeatable)
    python pipeline/coord_uncertainty.py --jobs 14

Chain (gates measured from EACH node, as card 9 measures them from the site):
  |lat| < 60 : SLDEM2015 59 m window to 150 km, LDEM_64 to 300 km, LDEM_16 to 300 km
  otherwise  : LDEM_64 to 300 km, LDEM_16 to 300 km (CHANDRAYAAN3, card 9 chain)
The SLDEM windows are fetched with radius 151 km (fetch_global.py --radius-km 151) so a
node up to 707 m off-centre still has 59 m terrain out to its own 150 km gate. The window
is a crop of the global 512 ppd grid, so its pixel values equal those of the 150 km window.

Resume: one checkpoint per node under data/processed/uncert/<ID>/<index>.json keyed by an
input fingerprint (terrain hashes, code/core/ephemeris hashes, params, site). No partial
public file is ever written. Output format: docs/data_contract.md section 18.
"""
import argparse
import concurrent.futures as cf
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as hz  # noqa: E402
from local_maps import CoreMetrics, METRICS, fingerprint, sha_file, valid_metrics  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LAT_MIN = -75.0                       # this part: lat > -75 (south-polar part done separately)
SLDEM_LAT = 60.0
SLDEM_GATE_KM = 150.0
PARAMS = dict(min_km=0.2, max_km=300.0, n_steps=4000, obs_height_m=2.0)   # = card 9 production
SPACING_M = 100
HALF_M = 500
N_SIDE = 2 * HALF_M // SPACING_M + 1  # 11
RADII_M = (100, 300, 500)
STATS = ('min', 'max', 'p10', 'median', 'p90')
WINDOW = dict(start='2026-01-01T00:00:00Z', step_h=1, n=43824)
CODE_FILES = ['web/js/core.js', 'web/data/ephem.bin', 'web/data/ephem.json', 'pipeline/horizon.py',
              'pipeline/coord_uncertainty.py', 'pipeline/local_metrics.mjs', 'pipeline/cache_metrics.mjs']


def grid_points(site):
    """Row-major, south->north rows, west->east columns; index = row*11 + col."""
    pts = []
    for n in range(-HALF_M, HALF_M + 1, SPACING_M):
        for e in range(-HALF_M, HALF_M + 1, SPACING_M):
            if e == n == 0:
                lat, lon = site['lat'], site['lon']
            else:
                la, lo = hz.destination(site['lat'], site['lon'], np.degrees(np.arctan2(e, n)), np.hypot(e, n))
                lat, lon = float(la), float(lo)
            pts.append(dict(index=len(pts), e_m=e, n_m=n, lat=lat, lon=lon))
    return pts


def terrain_inputs(site, raw):
    """[(kind, path, gate_km)] finest first, mirroring run_horizons.build_chain for lat > -80."""
    out = []
    if abs(site['lat']) < SLDEM_LAT:
        p = raw / 'sldem' / f"{site['id']}.npz"
        if not p.exists():
            raise FileNotFoundError(f'{p} (fetch_global.py --site {site["id"]} --skip-global --radius-km 151)')
        with np.load(p) as z:
            meta = json.loads(str(z['meta']))
        if meta.get('site_lat') != site['lat'] or meta.get('site_lon') != site['lon'] or meta.get('radius_km', 0) < 151:
            raise ValueError(f'{p}: window not centred on catalogue site or radius < 151 km')
        out.append(('sldem', p, SLDEM_GATE_KM))
    for ppd in (64, 16):
        p = raw / 'global' / f'ldem_{ppd}_float.img'
        if not (p.exists() and p.with_suffix('.lbl').exists()):
            raise FileNotFoundError(p)
        out.append(('global', p, PARAMS['max_km']))
    return out


def make_chain(inputs):
    chain = []
    for kind, p, gate in inputs:
        s = hz.LatLonWindowSampler(p) if kind == 'sldem' else hz.GlobalCylSampler(p)
        chain.append((s, gate))
    return chain


def resume_ok(path, key, index):
    try:
        r = json.loads(Path(path).read_text(encoding='utf-8'))
        return (r['input_key'] == key and r['index'] == index and valid_metrics(r['metrics'])
                and len(r['mask']) == 720 and np.isfinite(r['mask']).all() and r['n_missing'] == 0)
    except (OSError, ValueError, KeyError, TypeError):
        return False


_ctx = None


def _init(inputs, key, site, work):
    global _ctx
    import atexit
    core = CoreMetrics(ROOT)
    atexit.register(core.close)
    _ctx = make_chain(inputs), core, key, site, Path(work)


def compute_node(pt):
    chain, core, key, site, work = _ctx
    t0 = time.monotonic()
    res = hz.compute_horizon(pt['lat'], pt['lon'], chain, min_km=PARAMS['min_km'], max_km=PARAMS['max_km'],
                             n_steps=PARAMS['n_steps'], obs_height_m=PARAMS['obs_height_m'])
    if res['n_missing']:
        raise ValueError(f"{site['id']} node {pt['index']}: {res['n_missing']} ray samples without DEM")
    node_site = dict(id=f"{site['id']}_U{pt['index']:03d}", lat=pt['lat'], lon=pt['lon'], mock=False)
    rec = hz.horizon_record(node_site, res)        # section-3 rounding, exactly as production
    m = core.metrics(node_site, rec)
    if not valid_metrics(m):
        raise ValueError(f'invalid core.js metrics {m}')
    out = dict(**pt, input_key=key, h0_m=rec['h0_m'], mask=rec['mask'], dem_sources=rec['dem_sources'],
               n_missing=res['n_missing'], metrics=m, elapsed_s=round(time.monotonic() - t0, 3))
    hz.write_json_atomic(work / f"{pt['index']:03d}.json", out)
    return pt['index'], out['elapsed_s']


def summarize(nodes, radius_m):
    sel = [p for p in nodes if p['e_m'] ** 2 + p['n_m'] ** 2 <= radius_m ** 2]
    row = dict(n_nodes=len(sel))
    for k in METRICS:
        v = np.array([p[k] for p in sel], float)
        q = np.percentile(v, [10, 50, 90])          # numpy default 'linear' interpolation
        st = dict(min=float(v.min()), max=float(v.max()), p10=float(q[0]), median=float(q[1]), p90=float(q[2]))
        if k == 'longest_dark_h':
            st['min'], st['max'] = int(v.min()), int(v.max())
        row[k] = st
    return row


def validate_record(obj, site=None, strict_params=True):
    """strict_params=False: format-only check (south-polar files use their own production params)."""
    nodes = obj['nodes']
    if len(nodes) != N_SIDE * N_SIDE or [p['index'] for p in nodes] != list(range(N_SIDE * N_SIDE)):
        raise ValueError('expected 121 ordered nodes')
    g = obj['grid']
    if (g['rows'], g['cols'], g['spacing_m'], g['origin_e_m'], g['origin_n_m']) != (N_SIDE, N_SIDE, SPACING_M, -HALF_M, -HALF_M):
        raise ValueError('grid geometry')
    if obj['window'] != WINDOW or obj['frame'] != 'MOON_ME_DE421' or obj['radius_m'] != hz.R_M:
        raise ValueError('window/frame/radius')
    if (strict_params and obj['params'] != PARAMS) or obj['mock'] or not obj['complete']:
        raise ValueError('params/mock/complete')
    centre = site or dict(lat=obj['center']['lat'], lon=obj['center']['lon'])
    for p, q in zip(nodes, grid_points(centre)):
        if (p['e_m'], p['n_m']) != (q['e_m'], q['n_m']) or abs(p['lat'] - q['lat']) > 1e-9 \
                or abs((p['lon'] - q['lon'] + 180) % 360 - 180) > 1e-9:
            raise ValueError(f"node {p['index']} geometry")
        if not valid_metrics(p):
            raise ValueError(f"node {p['index']} metrics")
    if sorted(obj['ranges']) != sorted(str(r) for r in RADII_M):
        raise ValueError('ranges keys')
    for r in RADII_M:
        exp = summarize(nodes, r)
        got = obj['ranges'][str(r)]
        if got['n_nodes'] != exp['n_nodes']:
            raise ValueError(f'ranges {r} n_nodes')
        for k in METRICS:
            for s in STATS:
                if abs(got[k][s] - exp[k][s]) > 1e-12:
                    raise ValueError(f'ranges {r} {k} {s}')
                if s in ('p10', 'median', 'p90') and not (got[k]['min'] <= got[k][s] <= got[k]['max']):
                    raise ValueError(f'ranges {r} {k} order')


def run_site(site, raw, work, out, jobs):
    t0 = time.monotonic()
    inputs = terrain_inputs(site, raw)
    terrain = []
    for kind, p, gate in inputs:
        row = dict(name='SLDEM2015' if kind == 'sldem' else p.stem.upper().replace('_FLOAT', ''),
                   path=p.relative_to(ROOT).as_posix(), sha256=sha_file(p), gate_km=gate)
        if kind == 'global':
            row['label_sha256'] = sha_file(p.with_suffix('.lbl'))
            row['resolution_m'] = round(hz.GlobalCylSampler(p).res_m, 1)
        else:
            with np.load(p) as z:
                meta = json.loads(str(z['meta']))
            row['resolution_m'] = round(hz.LatLonWindowSampler(p).res_m, 1)
            row['storage_radius_km'] = meta['radius_km']
        terrain.append(row)
    prov = dict(terrain_sources=terrain, files_sha256={f: sha_file(ROOT / f) for f in CODE_FILES},
                center={k: site[k] for k in ('id', 'lat', 'lon')}, params=PARAMS)
    key = fingerprint(prov)
    prov['input_key'] = key
    wdir = work / site['id']
    wdir.mkdir(parents=True, exist_ok=True)
    pts = grid_points(site)
    todo = [p for p in pts if not resume_ok(wdir / f"{p['index']:03d}.json", key, p['index'])]
    print(f"{site['id']}: {len(pts) - len(todo)}/121 cached, {len(todo)} to compute, {jobs} workers", flush=True)
    if todo:
        with cf.ProcessPoolExecutor(min(jobs, len(todo)), initializer=_init,
                                    initargs=(inputs, key, site, str(wdir))) as ex:
            futs = [ex.submit(compute_node, p) for p in todo]
            for c, f in enumerate(cf.as_completed(futs), 1):
                i, s = f.result()
                if c % 30 == 0 or c == len(todo):
                    print(f"{site['id']}: +{c}/{len(todo)} (node {i} {s:.1f}s)", flush=True)
    if not all(resume_ok(wdir / f"{p['index']:03d}.json", key, p['index']) for p in pts):
        raise RuntimeError(f"{site['id']}: incomplete checkpoints, no export")
    nodes, srcs = [], {}
    for p in pts:
        r = json.loads((wdir / f"{p['index']:03d}.json").read_text(encoding='utf-8'))
        nodes.append(dict(**p, h0_m=r['h0_m'], **r['metrics']))
        for d in r['dem_sources']:
            srcs.setdefault(d['name'], dict(name=d['name'], res_m=d['res_m'], to_km_min=d['to_km'], to_km_max=d['to_km']))
            srcs[d['name']]['to_km_min'] = min(srcs[d['name']]['to_km_min'], d['to_km'])
            srcs[d['name']]['to_km_max'] = max(srcs[d['name']]['to_km_max'], d['to_km'])
    obj = dict(
        id=site['id'], center=dict(lat=site['lat'], lon=site['lon']),
        grid=dict(rows=N_SIDE, cols=N_SIDE, spacing_m=SPACING_M, origin_e_m=-HALF_M, origin_n_m=-HALF_M,
                  order='row-major, rows south to north, columns west to east; index = row*11 + col; '
                        'node (e,n) placed at geodesic bearing atan2(e,n), distance hypot(e,n)'),
        radius_rule='a radius r uses the nodes with hypot(e_m, n_m) <= r (100 m: 5, 300 m: 29, 500 m: 81 nodes)',
        quantiles='numpy.percentile, linear interpolation',
        window=WINDOW, params=PARAMS, frame='MOON_ME_DE421', radius_m=hz.R_M,
        ranges={str(r): summarize(nodes, r) for r in RADII_M},
        nodes=nodes, dem_sources=list(srcs.values()), provenance=prov,
        part='non-polar (lat > -75), pipeline/coord_uncertainty.py', complete=True, mock=False)
    validate_record(obj, site)
    hz.write_json_atomic(out / f"{site['id']}.json", obj)
    el = time.monotonic() - t0
    print(f"{site['id']}: COMPLETE {el:.1f}s", flush=True)
    return dict(id=site['id'], computed=len(todo), resumed=121 - len(todo), elapsed_s=round(el, 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--site', action='append')
    ap.add_argument('--raw', type=Path, default=ROOT / 'data' / 'raw')
    ap.add_argument('--work', type=Path, default=ROOT / 'data' / 'processed' / 'uncert')
    ap.add_argument('--out', type=Path, default=ROOT / 'web' / 'data' / 'uncertainty')
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 3) - 2))
    a = ap.parse_args(argv)
    sites = [s for s in json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8')) if s['lat'] > LAT_MIN]
    if a.site:
        sites = [s for s in sites if s['id'] in a.site]
        if len(sites) != len(set(a.site)):
            ap.error('unknown or polar site id')
    start = time.time()
    runs = []
    for s in sites:
        runs.append(run_site(s, a.raw.resolve(), a.work.resolve(), a.out.resolve(), a.jobs))
        hz.write_json_atomic(a.work / 'last_run.json', dict(start_epoch=start, end_epoch=time.time(), jobs=a.jobs, runs=runs))
    print(f'done {len(runs)} site(s) in {time.time() - start:.0f} s')


if __name__ == '__main__':
    main()
