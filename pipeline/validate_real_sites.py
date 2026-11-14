"""Card 10: fresh 60-day Horizons comparison at six real catalogue points.

python pipeline/validate_real_sites.py --prepare-requests
python pipeline/validate_real_sites.py [--offline]

Raw response cache is isolated from card 1. No ephemeris regeneration.
Terrain heights are unknown: explicitly test 0 m above the reference sphere,
with the same +2 m observer in Horizons and our geometry, not real terrain.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json

import numpy as np

from ephem import ROOT, EPOCH, Ephemeris, az_el, digest, write_json
import validate_ephem as base

IDS = ['APOLLO17', 'CHANGE4', 'SHACKLETON_RIM', 'CHANDRAYAAN3', 'SLIM', 'IM1']
CACHE = ROOT / 'data/raw/horizons_card10'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare-requests', action='store_true')
    ap.add_argument('--offline', action='store_true')
    args = ap.parse_args()
    catalogue = json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8'))
    by_id = {s['id']: s for s in catalogue}
    sites = [by_id[sid] for sid in IDS]
    queries = [dict(site=s['id'], body=b, url=base.request_url(s, b),
                    file=s['id'].lower() + '_' + b + '.json')
               for s in sites for b in ('sun', 'earth')]
    write_json(CACHE / 'requests.json', queries)
    if args.prepare_requests:
        print(CACHE / 'requests.json')
        return
    base.CACHE = CACHE
    binary = ROOT / 'web/data/ephem.bin'
    meta = json.loads((ROOT / 'web/data/ephem.json').read_text())
    assert meta['mock'] is False and meta['frame'] == 'MOON_ME_DE421'
    assert meta['n'] == 43824 and meta['step_h'] == 1
    values = np.fromfile(binary, dtype='<f4').reshape(-1, 6)
    assert values.shape == (43824, 6) and np.isfinite(values).all()
    engine = Ephemeris()
    rows, cases = [], []
    for site in sites:
        for body in ('sun', 'earth'):
            query = next(q for q in queries if q['site'] == site['id'] and q['body'] == body)
            hours, reference, checksum, signature = base.response_for(query, args.offline)
            dates = [EPOCH + timedelta(hours=int(h)) for h in hours]
            ours = az_el(values[hours], site['lat'], site['lon'], body=body)
            direct = engine.direct_az_el(site['lat'], site['lon'], 0, dates, body)
            differences = base.differences(ours, reference)
            rows.append(dict(id=site['id'], lat=site['lat'], lon=site['lon'],
                             source_url=site['source_url'], body=body, n=len(hours),
                             terrain_height_m=0, obs_height_m=2,
                             web_float32_vs_horizons=differences,
                             direct_topocentric_vs_horizons=base.differences(direct, reference),
                             url=query['url'], response_sha256=checksum,
                             retrieved_utc=json.loads((CACHE / query['file']).read_text())['retrieved_utc'],
                             signature=signature))
            cases.extend(dict(id=site['id'], lat=site['lat'], lon=site['lon'], body=body,
                              hour=int(hour), az=float(ref[0]), el=float(ref[1]),
                              python_az=float(our[0]), python_el=float(our[1]))
                         for hour, ref, our in zip(hours, reference, ours))
            print(site['id'], body, differences, flush=True)
    passed = all(max(r['web_float32_vs_horizons'][k] for k in ('max_az_deg', 'max_el_deg')) < 0.01 for r in rows)
    report = dict(generated_utc=datetime.now(timezone.utc).isoformat(), passed=passed,
                  threshold_deg=0.01, n_sites=6, n_times_per_body_site=121, n_comparisons=len(cases),
                  window='2026-01-01T00Z..2026-03-02T00Z inclusive, 12 h step',
                  binary_sha256=digest(binary), sites_sha256=digest(ROOT / 'web/data/sites.json'),
                  notes=['Current catalogue coordinates, including revised Apollo 17 and Chang\'e 4; Shackleton R04 is a published south-polar study point, not a landed vehicle.',
                         'Heights are unconfirmed; 0 m terrain + 2 m observer is a reference-sphere test, not measured terrain validation.',
                         'Horizons DE441 / high-precision MEAN_ME versus required DE440s / MOON_ME_DE421; exact datum of non-Apollo/Luna catalogue points remains unverified.',
                         'Sixty-day geometry test only; not independent five-year visibility or terrain-obstruction validation.',
                         'Moon-center apparent vector minus observer is an approximation; direct-topocentric reference also reported.'],
                  results=rows)
    write_json(ROOT / 'docs/real_sites_horizons_check.json', report)
    write_json(ROOT / 'data/processed/card10_horizons_cases.json', cases)
    print('PASS' if passed else 'FAIL', len(cases))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
