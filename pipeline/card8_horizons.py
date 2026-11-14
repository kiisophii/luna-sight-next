"""Card 8: resumable real-site polar horizons and explicit near-field sensitivity.

python pipeline/card8_horizons.py compute
python pipeline/card8_horizons.py sensitivity
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as hz
import run_horizons as runner

ROOT = Path(__file__).resolve().parents[1]
SENSITIVITY_SITES = ['SHACKLETON_RIM', 'CONNECTING_RIDGE', 'ARTEMIS_DE_GERLACHE_RIM2']


class OuterOnlySampler:
    """Preserve an original source only beyond the changed near field."""
    def __init__(self, sampler, site, near_km):
        self.sampler, self.site, self.near_km = sampler, site, near_km
        self.name, self.res_m = sampler.name, sampler.res_m

    def sample(self, lat, lon):
        la, lo = np.radians(lat), np.radians(lon)
        la0, lo0 = np.radians([self.site['lat'], self.site['lon']])
        a = np.sin((la-la0)/2)**2 + np.cos(la0)*np.cos(la)*np.sin((lo-lo0)/2)**2
        distance_km = 2*hz.R_M/1000*np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        values = self.sampler.sample(lat, lon)
        return np.where(distance_km > self.near_km + 1e-9, values, np.nan)


def sensitivity_chain(site, chain, resolution, near_km=3):
    coarse = next((s for s, radius in chain if s.res_m == resolution and radius >= near_km), None)
    if coarse is None:
        raise ValueError(f'{site["id"]}: no {resolution} m near-field source')
    return [(coarse, near_km)] + [(OuterOnlySampler(s, site, near_km), radius)
                                for s, radius in chain if radius > near_km]


def require_complete(result):
    if result['n_missing']:
        raise ValueError(f'{result["n_missing"]} missing terrain samples; refusing production output')
    mask = np.asarray(result['mask'])
    if mask.shape != (720,) or not np.isfinite(mask).all():
        raise ValueError('Expected 720 finite horizon angles')


def calculate(site, chain, *, n_steps=8000):
    result = hz.compute_horizon(site['lat'], site['lon'], chain,
                                min_km=0.005, max_km=300, n_steps=n_steps)
    require_complete(result)
    return result


def compute_site(site, raw, out, n_steps=8000, force=False):
    start = time.perf_counter()
    chain = runner.build_chain(site, raw, 300)
    sig = runner.chain_signature(chain)
    params = dict(min_km=0.005, max_km=300, n_steps=n_steps, engine_version=hz.ENGINE_VERSION,
                  card8_method=1)
    path = out / (site['id']+'.json')
    if not force and runner.up_to_date(path, site, params, sig):
        rec = json.loads(path.read_text(encoding='utf-8'))
        require_complete(dict(mask=rec['mask'], n_missing=rec['engine']['n_missing_samples']))
        print(f'{site["id"]}: cached', flush=True)
        return
    result = calculate(site, chain, n_steps=n_steps)
    record = hz.horizon_record(site, result)
    record['engine'].update(chain=sig, card8_method=1)
    hz.write_json_atomic(path, record)
    print(f'{site["id"]}: {time.perf_counter()-start:.1f}s, h0={result["h0_m"]:.2f} m, '
          f'mask={min(result["mask"]):.4f}..{max(result["mask"]):.4f} deg, missing=0', flush=True)


def sensitivity(site, raw, n_steps=8000):
    chain = runner.build_chain(site, raw, 300)
    baseline = calculate(site, chain, n_steps=n_steps)
    rows = []
    for res in (80, 240):
        changed = calculate(site, sensitivity_chain(site, chain, res), n_steps=n_steps)
        difference = changed['mask'] - baseline['mask']
        rows.append(dict(resolution_m=res, near_km=3,
                         rms_deg=float(np.sqrt(np.mean(difference**2))),
                         max_abs_deg=float(np.max(np.abs(difference))),
                         mean_signed_deg=float(np.mean(difference)),
                         h0_change_m=changed['h0_m']-baseline['h0_m'],
                         observer_height_policy='2 m above each variant DEM',
                         n_missing=changed['n_missing']))
    return dict(id=site['id'], lat=site['lat'], lon=site['lon'], n_steps=n_steps,
                baseline_h0_m=baseline['h0_m'], comparisons=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['compute', 'sensitivity'])
    parser.add_argument('--sites', type=Path, default=ROOT/'web/data/sites.json')
    parser.add_argument('--raw', type=Path, default=ROOT/'data/raw')
    parser.add_argument('--out', type=Path, default=ROOT/'web/data/horizon')
    parser.add_argument('--report', type=Path, default=ROOT/'data/processed/card8-sensitivity.json')
    parser.add_argument('--site', action='append')
    parser.add_argument('--n-steps', type=int, default=8000)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.n_steps < 1:
        parser.error('--n-steps must be positive')
    sites = [s for s in json.loads(args.sites.read_text(encoding='utf-8')) if s['lat'] < -80]
    selected = args.site or (SENSITIVITY_SITES if args.mode == 'sensitivity' else [s['id'] for s in sites])
    unknown = set(selected)-{s['id'] for s in sites}
    if unknown:
        parser.error(f'Unknown south-polar sites: {sorted(unknown)}')
    sites = [s for s in sites if s['id'] in selected]
    reports = []
    for site in sites:
        if args.mode == 'compute':
            compute_site(site, args.raw, args.out, args.n_steps, args.force)
        else:
            reports.append(sensitivity(site, args.raw, args.n_steps))
            hz.write_json_atomic(args.report, reports)
            print(json.dumps(reports[-1]), flush=True)


if __name__ == '__main__':
    main()
