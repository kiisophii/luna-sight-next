"""Card 20 independent check: 5 random nodes from 3 sites (one south-polar, one mid-latitude, one
equatorial), brute-force horizon (all 720 azimuths x 8,001 distances, no early stop) with the
independent card 13 DEM reader + PROJ geodesics, and an independent NumPy Sun/Earth loop over all
43,824 hours. Fractions must match the published web/data/local/<ID>.json within 1 percentage point.

No production horizon/local-map/core.js code is imported (same rule as verify_card18_local.py).

    python pipeline/verify_card20_local.py   -> docs/card20_validation.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import verify_card18_local as V18
from verify_card13_relay import trace_mask

ROOT = Path(__file__).resolve().parents[1]
SITES = ('ARTEMIS_NOBILE_RIM1', 'CHANGE4', 'APOLLO11')   # polar (-85.3), mid-latitude (-45.4), equatorial (0.7)
SEED = 20261120
SLDEM_GATE_KM = 150


class PointDEM(V18.PointDEM):
    """Card 18 point reader plus the card 20 SLDEM gate (150 km from the observer, like card 9)."""
    def __init__(self, center, point, raw):
        super().__init__(center, point, raw)
        for source in self.sources:
            if source['kind'] == 'sldem':
                source['max_km'] = SLDEM_GATE_KM


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--raw', type=Path, default=ROOT/'data/processed/card18/raw')
    ap.add_argument('--web-data', type=Path, default=ROOT/'web/data')
    ap.add_argument('--output', type=Path, default=ROOT/'docs/card20_validation.json')
    a = ap.parse_args(argv)
    ephem = V18.load_ephemeris(a.web_data)
    records = {s: json.loads((a.web_data/'local'/f'{s}.json').read_text(encoding='utf-8')) for s in SITES}
    selected = random.Random(SEED).sample([(s, i) for s in SITES for i in range(441)], 5)
    # make sure each of the three latitude classes is represented
    have = {s for s, _ in selected}
    rng = random.Random(SEED + 1)
    for s in SITES:
        if s not in have:
            selected[[k for k, (t, _) in enumerate(selected) if [x for x, _ in selected].count(t) > 1][0]] = (s, rng.randrange(441))
            have = {t for t, _ in selected}
    points = []
    for site, index in selected:
        rec = records[site]
        point = rec['points'][index]
        terrain = PointDEM(dict(id=site, **rec['center']), point, a.raw)
        ground = float(terrain(np.array([point['lat']]), np.array([point['lon']]))[0])
        if not np.isfinite(ground):
            raise ValueError(f'{site}/{index}: missing ground terrain')
        # same near-field start as production: 5 m for south-polar sites (card 18), 200 m elsewhere (card 9 settings)
        start_m = 5. if rec['center']['lat'] <= -75 else 200.
        mask = trace_mask(point['lat'], point['lon'], ground, 2., terrain,
                          np.arange(720)*.5, np.geomspace(start_m, 300000., 8001))
        metrics = V18.evaluate_metrics(point['lat'], point['lon'], ground, mask, ephem)
        comp = V18.compare_metrics(metrics, point)
        points.append(dict(id=site, index=index, e_m=point['e_m'], n_m=point['n_m'], lat=point['lat'], lon=point['lon'],
                           independent_ground_m=ground, reported_ground_m=point['h0_m'],
                           sources=terrain.manifest(), comparison=comp, passed=comp['passed']))
        print(site, index, {k: round(comp[k]['difference_pp'], 3) for k in V18.FRACTIONS},
              'dark diff h', comp['longest_dark_h']['difference_h'], 'PASS' if comp['passed'] else 'FAIL', flush=True)
    report = dict(method='Independent card 13 DEM reader, PROJ geodesics, ECEF brute-force rays (720 az x 8001 distances, '
                         'no early stop), NumPy full-window metrics; no production geometry or core.js imports',
                  criterion='sun_frac, earth_frac, both_frac each within 1 percentage point; dark-run difference reported',
                  sites=list(SITES), seed=SEED, points=points, passed=all(p['passed'] for p in points),
                  output_sha256={s: hashlib.sha256((a.web_data/'local'/f'{s}.json').read_bytes()).hexdigest() for s in SITES},
                  generated_utc=datetime.now(timezone.utc).isoformat())
    V18.save_report(a.output, report)
    print('ALL PASS' if report['passed'] else 'FAIL')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
