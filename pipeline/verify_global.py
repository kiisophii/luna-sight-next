"""Card 3 verification (kept separate from fetch_global.py).

Checks, using only files already cached by fetch_global.py:
  A. Height agreement at 10 non-polar points: SLDEM2015 (59 m) vs LDEM_64 (474 m) vs LDEM_16 (1.9 km).
  B. Registration: block-average SLDEM to 64 ppd and compare with LDEM_64 while shifting the
     block start by -8..+8 SLDEM pixels in rows and in columns. The RMS minimum must be at 0;
     a half-pixel (4 px) or longitude-origin error would move it.
  C. Same registration test LDEM_16 vs block-averaged LDEM_64 over the whole Moon (|lat| < 60).
  D. Apollo 17 sanity: the landing point should sit low in the Taurus-Littrow valley,
     well below the surrounding massifs within 10 km.

Run from the repository root:  python pipeline/verify_global.py
Writes data/raw/verify_global.json (not committed) and prints a summary.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_global as fg  # noqa: E402

RAW = fg.RAW
SEED = 42


def ldem(ppd):
    base = RAW / 'global' / fg.LDEM[ppd]
    img, lbl = base.with_suffix('.img'), base.with_suffix('.lbl')
    return fg.LdemFile(img, lbl) if img.exists() and lbl.exists() else None


def windows():
    out = []
    for f in sorted((RAW / 'sldem').glob('*.npz')):
        with np.load(f) as z:
            out.append(dict(path=f, meta=json.loads(str(z['meta']))))
    return out


def check_points(wins, l64, l16, n=10):
    rng = np.random.default_rng(SEED)
    rows = []
    per = [n // len(wins) + (1 if i < n % len(wins) else 0) for i in range(len(wins))]
    for w, k in zip(wins, per):
        m = w['meta']
        for _ in range(k):
            # random point within 100 km of the site (inside the 150 km window)
            d = 100.0 * math.sqrt(rng.random()) / fg.R_KM
            b = rng.random() * 2 * math.pi
            la1, lo1 = math.radians(m['site_lat']), math.radians(m['site_lon'])
            la2 = math.asin(math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(b))
            lo2 = lo1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(la1),
                                   math.cos(d) - math.sin(la1) * math.sin(la2))
            lat, lon = math.degrees(la2), float(fg.lon180(math.degrees(lo2)))
            r = dict(site=m['id'], lat=round(lat, 5), lon=round(lon, 5),
                     sldem_m=float(fg.sample_window(w['path'], lat, lon)))
            if l64:
                r['ldem64_m'] = float(l64.sample(lat, lon))
            if l16:
                r['ldem16_m'] = float(l16.sample(lat, lon))
            rows.append(r)
    stats = {}
    for a, b in [('sldem_m', 'ldem64_m'), ('sldem_m', 'ldem16_m'), ('ldem64_m', 'ldem16_m')]:
        d = np.array([r[a] - r[b] for r in rows if a in r and b in r])
        if d.size:
            stats[f'{a[:-2]}-{b[:-2]}'] = dict(n=int(d.size), mean_m=round(float(d.mean()), 1),
                                               mean_abs_m=round(float(np.abs(d).mean()), 1),
                                               max_abs_m=round(float(np.abs(d).max()), 1))
    return rows, stats


def subpixel_min(rms):
    """Shift of the RMS minimum, refined by a parabola through the best 3 integer shifts."""
    k = min(rms, key=rms.get)
    if k - 1 in rms and k + 1 in rms:
        a, b, c = rms[k - 1], rms[k], rms[k + 1]
        den = a - 2 * b + c
        if den > 0:
            return round(k + 0.5 * (a - c) / den, 2)
    return float(k)


def block_mean(a, f):
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    return a[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))


def shift_test_sldem(w, l64, max_shift=8):
    """RMS(SLDEM block mean - LDEM_64) vs shift of the block origin (SLDEM pixels)."""
    with np.load(w['path']) as z:
        h, lat, lu = z['height_m'].astype(np.float64), z['lat'], z['lon_unwrapped']
    g0 = int(round((90 - lat[0]) * 512 - 0.5))
    k0 = int(round(lu[0] * 512 - 0.5))
    a_r, a_c = (-g0) % 8, (-k0) % 8                   # first aligned block in window coords
    m = max_shift
    base_r, base_c = a_r + 8, a_c + 8                   # margin so shifted blocks stay inside
    nb_r = (h.shape[0] - base_r - m) // 8 - 1
    nb_c = (h.shape[1] - base_c - m) // 8 - 1
    G0, K0 = (g0 + base_r) // 8, (k0 + base_c) // 8
    ref = l64.data[G0:G0 + nb_r][:, np.arange(K0, K0 + nb_c) % l64.grid.samples] * 1000.0
    res = {'rows': {}, 'cols': {}}
    for s in range(-m, m + 1):
        sub = h[base_r + s: base_r + s + nb_r * 8, base_c: base_c + nb_c * 8]
        res['rows'][s] = float(np.sqrt(np.mean((block_mean(sub, 8) - ref) ** 2)))
        sub = h[base_r: base_r + nb_r * 8, base_c + s: base_c + s + nb_c * 8]
        res['cols'][s] = float(np.sqrt(np.mean((block_mean(sub, 8) - ref) ** 2)))
    return dict(site=w['meta']['id'], rms_m={k: {str(s): round(x, 1) for s, x in v.items()}
                                              for k, v in res.items()},
                best_shift_px={k: subpixel_min(v) for k, v in res.items()},
                best_shift_m={k: round(subpixel_min(v) * 1737400 * math.pi / 180 / 512, 1)
                              for k, v in res.items()})


def shift_test_ldem16(l64, l16, max_shift=4):
    """LDEM_16 vs 4x4 block mean of LDEM_64 for |lat| < 30 (rows 60..120 deg from north)."""
    r0, r1 = 60 * 64, 120 * 64
    res = {'rows': {}, 'cols': {}}
    ref = np.asarray(l16.data[60 * 16 + 1: 120 * 16 - 1], dtype=np.float64) * 1000.0
    for s in range(-max_shift, max_shift + 1):
        sub = np.asarray(l64.data[r0 + 4 + s: r1 - 4 + s], dtype=np.float32)
        res['rows'][s] = float(np.sqrt(np.mean((block_mean(sub, 4) * 1000.0 - ref) ** 2)))
        sub = np.roll(np.asarray(l64.data[r0 + 4: r1 - 4], dtype=np.float32), -s, axis=1)
        res['cols'][s] = float(np.sqrt(np.mean((block_mean(sub, 4) * 1000.0 - ref) ** 2)))
    return dict(rms_m={k: {str(s): round(x, 1) for s, x in v.items()} for k, v in res.items()},
                best_shift_px={k: subpixel_min(v) for k, v in res.items()},
                best_shift_m={k: round(subpixel_min(v) * 1737400 * math.pi / 180 / 64, 1)
                              for k, v in res.items()})


def apollo17(wins):
    w = next((w for w in wins if w['meta']['id'] == 'APOLLO17'), None)
    if not w:
        return None
    m = w['meta']
    with np.load(w['path']) as z:
        h, lat, lu = z['height_m'], z['lat'], z['lon_unwrapped']
    site_h = float(fg.sample_window(w['path'], m['site_lat'], m['site_lon']))
    la, lo = np.radians(lat)[:, None], np.radians(lu)[None, :]
    p, q = math.radians(m['site_lat']), math.radians(m['site_lon'] % 360)
    cosd = np.sin(la) * math.sin(p) + np.cos(la) * math.cos(p) * np.cos(lo - q)
    dist = fg.R_KM * np.arccos(np.clip(cosd, -1, 1))
    near = h[dist <= 10.0]
    return dict(site_h_m=round(site_h, 1), n_px_10km=int(near.size),
                min_10km_m=round(float(near.min()), 1), max_10km_m=round(float(near.max()), 1),
                site_percentile_10km=round(float((near < site_h).mean() * 100), 1),
                relief_above_site_m=round(float(near.max() - site_h), 1),
                coord_source='web/data/sites.json (mock entry; NSSDCA value per card 4 brief)')


def coverage(w, step_deg=0.1):
    """E. every point of the radius_km circle (and 2 km inside it) must be samplable."""
    m = w['meta']
    win = fg.SldemWindow(w['path'])
    p, q = math.radians(m['site_lat']), math.radians(m['site_lon'])
    az = np.radians(np.arange(0, 360, step_deg))
    bad = 0
    for d_km in (m['radius_km'], m['radius_km'] - 2):
        d = d_km / fg.R_KM
        la = np.arcsin(np.sin(p) * np.cos(d) + np.cos(p) * np.sin(d) * np.cos(az))
        lo = q + np.arctan2(np.sin(az) * np.sin(d) * np.cos(p), np.cos(d) - np.sin(p) * np.sin(la))
        ok = win.contains(np.degrees(la), np.degrees(lo))
        if m.get('clipped_at_60deg'):
            ok |= np.abs(np.degrees(la)) > 60 - 1 / 512
        bad += int((~ok).sum())
    return dict(site=m['id'], n_azimuths=int(az.size), outside=bad)


def main():
    wins = windows()
    if not wins:
        sys.exit('No SLDEM windows found; run pipeline/fetch_global.py first')
    l64, l16 = ldem(64), ldem(16)
    out = {}
    print('A. 10-point height comparison (bilinear)')
    out['points'], out['point_stats'] = check_points(wins, l64, l16)
    for r in out['points']:
        print('   ', {k: (round(v, 1) if isinstance(v, float) and k.endswith('_m') else v)
                      for k, v in r.items()})
    for k, v in out['point_stats'].items():
        print(f'   {k}: {v}')
    if l64:
        print('B. SLDEM -> 64 ppd registration (RMS m vs shift in SLDEM px; 4 px = half LDEM_64 px)')
        out['shift_sldem_vs_ldem64'] = [shift_test_sldem(w, l64) for w in wins]
        for r in out['shift_sldem_vs_ldem64']:
            print(f"   {r['site']}: best shift px {r['best_shift_px']} m {r['best_shift_m']}  rows {r['rms_m']['rows']}")
            print(f"   {' ' * len(r['site'])}  cols {r['rms_m']['cols']}")
        if l16:
            print('C. LDEM_64 -> 16 ppd registration (RMS m vs shift in LDEM_64 px; 2 px = half LDEM_16 px)')
            out['shift_ldem64_vs_ldem16'] = shift_test_ldem16(l64, l16)
            r = out['shift_ldem64_vs_ldem16']
            print(f"   best shift px {r['best_shift_px']} m {r['best_shift_m']}  rows {r['rms_m']['rows']}")
            print(f"   cols {r['rms_m']['cols']}")
    else:
        print('B/C skipped: LDEM_64 not downloaded yet')
    out['apollo17'] = apollo17(wins)
    if out['apollo17']:
        print('D. Apollo 17 valley check:', out['apollo17'])
    out['coverage'] = [coverage(w) for w in wins]
    print('E. window covers the full radius circle (outside must be 0):', out['coverage'])
    dest = RAW / 'verify_global.json'
    dest.write_text(json.dumps(out, indent=1))
    print(f'Saved {dest.relative_to(fg.ROOT)}')


if __name__ == '__main__':
    main()
