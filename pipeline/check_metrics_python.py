"""Independent vectorized Python port for checking the actual JS metrics.

Input fixtures are supplied by test_metrics.mjs, never exported to web/data.
"""
import json
from pathlib import Path
import sys

import numpy as np


def metrics(vectors, site, horizon):
    lat, lon = np.deg2rad([site['lat'], site['lon']])
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    east = np.array([-so, co, 0])
    north = np.array([-sl * co, -sl * so, cl])
    up = np.array([cl * co, cl * so, sl])
    observer = up * (1737.4 + (horizon['h0_m'] + 2) / 1000)
    mask = np.array(horizon['mask'])

    def geometry(col):
        vector = vectors[:, col:col + 3].astype(np.float64) - observer
        e, n, u = vector @ east, vector @ north, vector @ up
        az = np.rad2deg(np.arctan2(e, n)) % 360
        el = np.rad2deg(np.arctan2(u, np.hypot(e, n)))
        x = ((az % 360 + 360) % 360) / horizon['az_step_deg']
        k = np.floor(x).astype(int) % len(mask)
        t = x - np.floor(x)
        line = mask[k] + (mask[(k + 1) % len(mask)] - mask[k]) * t
        return el, line

    el, line = geometry(0)
    y = (line - el) / 0.2666
    clipped = np.clip(y, -1, 1)
    disk = (np.arccos(clipped) - clipped * np.sqrt(1 - clipped ** 2)) / np.pi
    sun = disk >= 0.5
    el, line = geometry(3)
    earth = el > line
    run, longest = 0, 0
    for lit in sun:
        run = 0 if lit else run + 1
        longest = max(longest, run)
    return dict(sun_frac=float(sun.mean()), earth_frac=float(earth.mean()),
                both_frac=float((sun & earth).mean()), longest_dark_h=longest)


if __name__ == '__main__':
    plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    vectors = np.fromfile(plan['binary'], dtype='<f4').reshape(-1, 6)
    print(json.dumps([metrics(vectors, row['site'], row['horizon']) for row in plan['cases']]))
