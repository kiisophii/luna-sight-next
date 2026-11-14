"""Reference horizons for the polar custom-point validation (s4).

Picks 30 random south-polar test points (fixed seed, 10 per latitude band 75-80, 80-85, 85-90 deg S,
area-uniform inside each band), fetches the card-2 PGDA windows around each point with the card-8 radii
(pipeline/fetch_polar.py: 5 m 3 km, 10 m 25 km, 20 m 25 km, 60/80 m 60 km, 240 m 200 km; windows outside a
product's footprint are skipped, partial windows keep only original pixels) and computes the card-8 horizon
(pipeline/horizon.py, min 5 m, 8000 steps, then LOLA LDEM_64/16 to 300 km).

    python pipeline/custom_polar_reference.py points
    python pipeline/custom_polar_reference.py fetch      # resumable (block cache + per-window npz)
    python pipeline/custom_polar_reference.py compute    # writes data/processed/custom_polar/ref/<ID>.json

The test points are synthetic coordinates, not landing sites.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_polar as fp  # noqa: E402
import horizon as hz  # noqa: E402
import polar_prefetch  # noqa: E402

polar_prefetch.install(8)   # parallel Range requests (PGDA is slow per connection)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'processed' / 'custom_polar'
RAW = ROOT / 'data' / 'raw'
BANDS = [(-80.0, -75.0), (-85.0, -80.0), (-90.0, -85.0)]
SEED = 20261114
RES = [5, 10, 20, 60, 80, 240]


def make_points(n_per_band=10, seed=SEED):
    rng = np.random.default_rng(seed)
    pts = []
    for b, (lo, hi) in enumerate(BANDS):
        # area-uniform in latitude: sin(lat) uniform between the band edges
        s = rng.uniform(math.sin(math.radians(lo)), math.sin(math.radians(hi)), n_per_band)
        lat = np.degrees(np.arcsin(s))
        lon = rng.uniform(-180, 180, n_per_band)
        for k in range(n_per_band):
            pts.append(dict(id=f'RANDPOLAR_{b + 1}_{k + 1:02d}', lat=round(float(lat[k]), 5),
                            lon=round(float(lon[k]), 5), synthetic=True, band=f'{-hi:g}-{-lo:g}S'))
    return pts


POINTS = OUT / 'points.json'


def load_points():
    return json.loads(POINTS.read_text(encoding='utf-8'))


def fetch_all(points, only=None, res_list=None):
    root = RAW / 'polar'
    fails = []
    for p in points:
        if only and p['id'] not in only:
            continue
        for res in res_list or RES:
            try:
                fp.fetch(p, res, fp.SOURCES[res][1], root, allow_partial=True)
            except fp.SourceCoverageError as e:
                print(f'UNAVAILABLE {p["id"]} {res} m: {e}', flush=True)
            except Exception as e:  # noqa: BLE001 - report and continue, rerun resumes
                fails.append(f'{p["id"]} {res}: {e}')
                print(f'FAILED {p["id"]} {res} m: {e}', flush=True)
    if fails:
        raise SystemExit(f'{len(fails)} windows failed; rerun to resume')


def card8_chain(sid, max_km=300.0):
    chain = []
    for res in RES:
        f = RAW / 'polar' / str(res) / f'{sid}.npz'
        if f.exists():
            s = hz.PolarStereoSampler(f)
            chain.append((s, min(s.radius_km or max_km, max_km)))
    for ppd in (64, 16):
        img = RAW / 'global' / f'ldem_{ppd}_float.img'
        chain.append((hz.GlobalCylSampler(img), max_km))
    return chain


def compute_all(points, force=False):
    d = OUT / 'ref'
    d.mkdir(parents=True, exist_ok=True)
    for p in points:
        f = d / f'{p["id"]}.json'
        if f.exists() and not force:
            continue
        chain = card8_chain(p['id'])
        r = hz.compute_horizon(p['lat'], p['lon'], chain, min_km=0.005, max_km=300, n_steps=8000)
        if r['n_missing']:
            print(f'WARNING {p["id"]}: {r["n_missing"]} missing samples', flush=True)
        rec = hz.horizon_record(p, r)
        rec['synthetic_point'] = True
        hz.write_json_atomic(f, rec)
        print(f'{p["id"]} ({p["lat"]:.3f}, {p["lon"]:.3f}): h0 {r["h0_m"]:.1f} m, '
              f'sources {[s["name"] for s in r["dem_sources"]]}', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['points', 'fetch', 'compute'])
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--res', nargs='*', type=int)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--points', type=Path, help='other point list (e.g. a catalogue site without a card-8 horizon)')
    a = ap.parse_args()
    global POINTS
    if a.points:
        POINTS = a.points
    if a.mode == 'points':
        OUT.mkdir(parents=True, exist_ok=True)
        pts = make_points()
        (OUT / 'points.json').write_text(json.dumps(pts, indent=1), encoding='utf-8')
        for p in pts:
            print(p)
    elif a.mode == 'fetch':
        fetch_all(load_points(), a.only, a.res)
    else:
        compute_all(load_points(), a.force)


if __name__ == '__main__':
    main()
