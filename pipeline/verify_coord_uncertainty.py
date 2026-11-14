"""Independent check of card 23 (non-polar part), web/data/uncertainty/<ID>.json.

Does NOT import horizon.py, coord_uncertainty.py, local_maps.py or core.js.
Terrain is read with this file's own bilinear code (SLDEM2015 window npz) and card 3's
fetch_global.LdemFile (LDEM_64 / LDEM_16).

Check A (all sites): the centre node (e=n=0) equals web/data/metrics/<ID>.json to 4 decimals
(longest_dark_h exactly).
Check B: for --sites (default 3), 5 random nodes each (seed 20261114, without replacement,
centre excluded) are recomputed by
  - brute-force horizon: 720 azimuths, uniform 20 m steps from 0.2 km to 150 km and 100 m
    steps to 300 km, no early stop, exact sphere (R = 1737.4 km), observer 2 m above terrain,
    chain SLDEM (<=150 km from the node, |lat|<60) -> LDEM_64 -> LDEM_16;
  - independent hourly Sun/Earth loop over ephem.bin (43,824 h): topocentric vector,
    azimuth/elevation from the site frame, horizon linearly interpolated between 0.5 deg bins,
    sunlit = Sun centre elevation >= horizon (equivalent to >= 50 % of the disc for a
    straight mask line), Earth = centre elevation > horizon; longest run of not-sunlit hours.
Pass: every fraction within 1 percentage point. Darkness differences are reported.

    python pipeline/verify_coord_uncertainty.py [--sites A B C] [--out docs/coord_uncertainty_validation.json]
"""
import argparse
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_global import LdemFile  # noqa: E402  (card 3 reader, not the horizon engine)

ROOT = Path(__file__).resolve().parents[1]
RK = 1737.4                  # km
METRICS = ('sun_frac', 'earth_frac', 'both_frac', 'longest_dark_h')


class Window:
    def __init__(self, path):
        with np.load(path) as z:
            self.h = z['height_m'].astype(np.float64)
            self.lat = z['lat'].astype(np.float64)
            self.lon = z['lon_unwrapped'].astype(np.float64)

    def sample(self, lat, lon):
        # nearest copy of lon to the window
        mid = 0.5 * (self.lon[0] + self.lon[-1])
        lon = mid + ((lon - mid + 180.0) % 360.0 - 180.0)
        fr = (self.lat[0] - lat) / (self.lat[0] - self.lat[1])
        fc = (lon - self.lon[0]) / (self.lon[1] - self.lon[0])
        nr, nc = self.h.shape
        ok = (fr >= 0) & (fr <= nr - 1) & (fc >= 0) & (fc <= nc - 1)
        out = np.full(lat.shape, np.nan)
        r0 = np.clip(np.floor(fr[ok]).astype(int), 0, nr - 2)
        c0 = np.clip(np.floor(fc[ok]).astype(int), 0, nc - 2)
        a, b = fr[ok] - r0, fc[ok] - c0
        H = self.h
        out[ok] = (H[r0, c0] * (1 - a) * (1 - b) + H[r0, c0 + 1] * (1 - a) * b
                   + H[r0 + 1, c0] * a * (1 - b) + H[r0 + 1, c0 + 1] * a * b)
        return out


def unit(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def brute_horizon(lat, lon, win, l64, l16):
    up = unit(lat, lon)
    z = np.array([0.0, 0.0, 1.0])
    east = np.cross(z, up); east /= np.linalg.norm(east)
    north = np.cross(up, east)
    def height(la, lo, d_km):
        h = np.full(la.shape, np.nan)
        if win is not None:
            m = d_km <= 150.0
            h[m] = win.sample(la[m], lo[m])
        m = np.isnan(h)
        h[m] = l64.sample(la[m], lo[m])
        m = np.isnan(h)
        if m.any():
            h[m] = l16.sample(la[m], lo[m])
        return h
    h0 = float(height(np.array([lat]), np.array([lon]), np.array([0.0]))[0])
    ro = RK * 1000 + h0 + 2.0
    d_km = np.concatenate([np.arange(0.2, 150.0 + 1e-9, 0.02), np.arange(150.1, 300.0 + 1e-9, 0.1)])
    th = d_km / RK
    mask = np.empty(720)
    for a0 in range(0, 720, 24):
        az = np.radians(np.arange(a0, a0 + 24) * 0.5)[:, None]
        t = np.cos(az)[..., None] * north + np.sin(az)[..., None] * east          # (24,1,3)
        p = up * np.cos(th)[None, :, None] + t * np.sin(th)[None, :, None]         # (24,N,3)
        la = np.degrees(np.arcsin(np.clip(p[..., 2], -1, 1)))
        lo = np.degrees(np.arctan2(p[..., 1], p[..., 0]))
        dd = np.broadcast_to(d_km, la.shape)
        h = height(la.ravel(), lo.ravel(), dd.ravel()).reshape(la.shape)
        if np.isnan(h).any():
            raise ValueError('missing terrain')
        rt = RK * 1000 + h
        el = np.degrees(np.arctan2(rt * np.cos(th) - ro, rt * np.sin(th)))
        mask[a0:a0 + 24] = el.max(axis=1)
    return h0, mask


def hourly(lat, lon, h0, mask, eph):
    up = unit(lat, lon)
    east = np.array([-math.sin(math.radians(lon)), math.cos(math.radians(lon)), 0.0])
    north = np.cross(up, east)
    obs = up * (RK + (h0 + 2.0) / 1000.0)
    def azel(v):
        v = v - obs
        e, n, u = v @ east, v @ north, v @ up
        el = np.degrees(np.arcsin(u / np.linalg.norm(v, axis=1)))
        az = np.degrees(np.arctan2(e, n)) % 360.0
        x = az / 0.5
        k = np.floor(x).astype(int) % 720
        line = mask[k] * (1 - (x - np.floor(x))) + mask[(k + 1) % 720] * (x - np.floor(x))
        return el, line
    se, sl = azel(eph[:, 0:3])
    ee, el_ = azel(eph[:, 3:6])
    sun, ear = se >= sl, ee > el_
    longest = run = 0
    for s in sun.tolist():            # plain loop for the darkness run
        run = 0 if s else run + 1
        if run > longest:
            longest = run
    n = len(sun)
    return dict(sun_frac=sun.sum() / n, earth_frac=ear.sum() / n, both_frac=(sun & ear).sum() / n,
                longest_dark_h=longest)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sites', nargs='+', default=['CHANGE3', 'CHANDRAYAAN3', 'APOLLO15'])
    ap.add_argument('--n', type=int, default=5)
    ap.add_argument('--seed', type=int, default=20261114)
    ap.add_argument('--out', default=str(ROOT / 'docs' / 'coord_uncertainty_validation.json'))
    a = ap.parse_args(argv)
    udir = ROOT / 'web' / 'data' / 'uncertainty'
    report = dict(centre=[], nodes=[], seed=a.seed)
    bad = 0
    for p in sorted(udir.glob('*.json')):
        u = json.loads(p.read_text(encoding='utf-8'))
        c = next(x for x in u['nodes'] if x['e_m'] == 0 and x['n_m'] == 0)
        m = json.loads((ROOT / 'web/data/metrics' / p.name).read_text(encoding='utf-8'))
        ok = all(round(c[k], 4) == round(m[k], 4) for k in METRICS[:3]) and c['longest_dark_h'] == m['longest_dark_h']
        bad += not ok
        report['centre'].append(dict(id=u['id'], ok=ok, node={k: c[k] for k in METRICS}, metrics_file={k: m[k] for k in METRICS}))
    print(f"A centre = metrics file: {len(report['centre']) - bad}/{len(report['centre'])} sites match")
    meta = json.loads((ROOT / 'web/data/ephem.json').read_text(encoding='utf-8'))
    eph = np.fromfile(ROOT / 'web/data/ephem.bin', dtype='<f4').reshape(meta['n'], 6).astype(np.float64)
    gdir = ROOT / 'data' / 'raw' / 'global'
    l64 = LdemFile(gdir / 'ldem_64_float.img', gdir / 'ldem_64_float.lbl')
    l16 = LdemFile(gdir / 'ldem_16_float.img', gdir / 'ldem_16_float.lbl')
    rng = np.random.default_rng(a.seed)
    worst = 0.0
    for sid in a.sites:
        u = json.loads((udir / f'{sid}.json').read_text(encoding='utf-8'))
        npz = ROOT / 'data' / 'raw' / 'sldem' / f'{sid}.npz'
        win = Window(npz) if abs(u['center']['lat']) < 60 else None
        cand = [x for x in u['nodes'] if not (x['e_m'] == 0 and x['n_m'] == 0)]
        pick = rng.choice(len(cand), a.n, replace=False)
        ck = ROOT / 'data' / 'processed' / 'uncert' / sid
        for i in sorted(pick.tolist()):
            node = cand[i]
            t0 = time.time()
            h0, mask = brute_horizon(node['lat'], node['lon'], win, l64, l16)
            r = hourly(node['lat'], node['lon'], h0, mask, eph)
            stored = json.loads((ck / f"{node['index']:03d}.json").read_text(encoding='utf-8'))
            dmask = np.abs(mask - np.array(stored['mask']))
            diff = {k: float(abs(r[k] - node[k]) * 100) for k in METRICS[:3]}
            worst = max(worst, max(diff.values()))
            row = dict(id=sid, index=node['index'], e_m=node['e_m'], n_m=node['n_m'],
                       h0_brute=round(h0, 3), h0_file=node['h0_m'],
                       mask_max_abs_diff_deg=round(float(dmask.max()), 4),
                       mask_rms_diff_deg=round(float(np.sqrt((dmask ** 2).mean())), 4),
                       brute={k: (round(float(r[k]), 6) if k != 'longest_dark_h' else int(r[k])) for k in METRICS},
                       file={k: node[k] for k in METRICS},
                       diff_pp={k: round(v, 4) for k, v in diff.items()},
                       dark_diff_h=int(r['longest_dark_h']) - node['longest_dark_h'],
                       pass_1pp=bool(max(diff.values()) <= 1.0), seconds=round(time.time() - t0, 1))
            report['nodes'].append(row)
            print(json.dumps(row), flush=True)
    report['summary'] = dict(centre_match=f"{len(report['centre']) - bad}/{len(report['centre'])}",
                             nodes_pass=f"{sum(r['pass_1pp'] for r in report['nodes'])}/{len(report['nodes'])}",
                             worst_fraction_diff_pp=round(worst, 4),
                             worst_mask_diff_deg=max(r['mask_max_abs_diff_deg'] for r in report['nodes']),
                             max_abs_dark_diff_h=max(abs(r['dark_diff_h']) for r in report['nodes']))
    Path(a.out).write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(report['summary']))
    return 0 if bad == 0 and all(r['pass_1pp'] for r in report['nodes']) else 1


if __name__ == '__main__':
    sys.exit(main())
