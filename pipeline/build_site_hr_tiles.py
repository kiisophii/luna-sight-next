"""Card 14: add finer south-cap terrain tiles around the polar catalogue sites (incremental).

The globe pyramid in web/data/globe/ (pipeline/build_globe_tiles.py, Sua) stops at south z7
(34.2 m tile spacing) because its finest polar source is PGDA 20 m. This script adds south
**z8 (17.1 m spacing)** children from PGDA LOLA **10 m** windows (LDEM_83S_10MPP_ADJ.TIF, card 2
fetch_polar.py, data/raw/polar/10/<ID>.npz), without touching any existing tile:

  * candidates = the 4 children of every existing south z7 tile that build_globe_tiles.near_site()
    would refine (same refinement radius rule: 10 km for spacing < 50 m);
  * a quad is written only if all 4 children are 100 % covered by 10 m data (no LDEM fallback
    inside a fine tile, and the viewer only splits a tile when all 4 children exist);
  * same tile format, sample grid, projection and height encoding as build_globe_tiles.py
    (functions imported from it); index.json gets the new tiles appended (existing entries,
    levels and sources kept) and its totals updated.

    python pipeline/build_site_hr_tiles.py plan      # list candidate quads + coverage, no writes
    python pipeline/build_site_hr_tiles.py build     # write PNGs + update index.json (resumable)
    python pipeline/build_site_hr_tiles.py check     # decode new tiles, parent/child + edge checks

Resume: PNGs already written are skipped (data/processed/globe_hr_progress.json, git-ignored).
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_globe_tiles as bg  # noqa: E402

ROOT = bg.ROOT
OUT = bg.OUT
IDX = OUT / 'index.json'
SRC_DIR = bg.RAW / 'polar' / '10'
PROG = ROOT / 'data' / 'processed' / 'globe_hr_progress.json'
Z_PARENT, Z_NEW = 7, 8
PGDA10_URL = 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF'


def polar_sites():
    return [s for s in bg.load_sites() if s['lat'] <= -71.95]


def sources():
    out = [bg.PolarWin(p) for p in sorted(SRC_DIR.glob('*.npz'))]
    if not out:
        raise SystemExit(f'no 10 m windows in {SRC_DIR} (fetch with pipeline/fetch_polar.py, res 10)')
    return out


def heights(srcs, kind, z, x, y):
    lat, lon = bg.tile_sample_grid(kind, z, x, y)
    sp = bg.tile_spacing_m(kind, z)
    h = np.full(lat.shape, np.nan, np.float32)
    for s in srcs:
        m = np.isnan(h)
        if not m.any():
            break
        h[m] = s.sample(lat[m], lon[m], sp)
    return h


def plan(srcs, idx):
    have = {(t[0], t[1], t[2]) for t in idx['tiles'].get('south', [])}
    sites = polar_sites()
    quads, skipped = [], []
    for (z, x, y) in sorted(have):
        if z != Z_PARENT or not bg.near_site('south', z, x, y, sites):
            continue
        kids = [(Z_NEW, 2 * x + i, 2 * y + j) for j in (0, 1) for i in (0, 1)]
        cov = []
        for k in kids:
            lat, lon = bg.tile_sample_grid('south', *k)
            ok = np.zeros(lat.shape, bool)
            for s in srcs:
                ok |= np.isfinite(s.sample(lat, lon, bg.tile_spacing_m('south', Z_NEW)))
            cov.append(float(ok.mean()))
        (quads if min(cov) >= 1.0 else skipped).append(dict(parent=(z, x, y), kids=kids, coverage=cov))
    return quads, skipped


def cmd_plan(a):
    idx = json.loads(IDX.read_text())
    q, s = plan(sources(), idx)
    print(f'{len(q)} complete quads ({4 * len(q)} new z{Z_NEW} tiles); {len(s)} parents skipped (coverage < 100 %)')
    for d in s:
        print('  skip', d['parent'], [round(c, 3) for c in d['coverage']])
    return 0


def cmd_build(a):
    idx = json.loads(IDX.read_text())
    srcs = sources()
    quads, skipped = plan(srcs, idx)
    prog = json.loads(PROG.read_text()) if PROG.exists() else {}
    t0 = time.time()
    n = 0
    for d in quads:
        for k in d['kids']:
            key = f'south/{k[0]}/{k[1]}/{k[2]}'
            path = OUT / 'south' / str(k[0]) / f'{k[1]}_{k[2]}.png'
            if key in prog and path.exists():
                continue
            h = heights(srcs, 'south', *k)
            if np.isnan(h).any():
                raise RuntimeError(f'{key}: {int(np.isnan(h).sum())} samples without 10 m data')
            bg.encode_png(h, path)
            prog[key] = dict(min=float(np.floor(h.min())), max=float(np.ceil(h.max())),
                             bytes=path.stat().st_size, src=['PGDA 10 m'])
            n += 1
            if n % 20 == 0:
                PROG.parent.mkdir(parents=True, exist_ok=True)
                PROG.write_text(json.dumps(prog))
                print(f'  {n} tiles, {time.time() - t0:.0f} s', flush=True)
    PROG.parent.mkdir(parents=True, exist_ok=True)
    PROG.write_text(json.dumps(prog))
    # ---- index.json: append, keep everything else
    south = idx['tiles'].setdefault('south', [])
    existing = {(t[0], t[1], t[2]) for t in south}
    added = 0
    for key, r in sorted(prog.items()):
        _, z, x, y = key.split('/')
        z, x, y = int(z), int(x), int(y)
        if (z, x, y) not in existing:
            south.append([z, x, y, r['min'], r['max'], 1])
            added += 1
    south.sort()
    lv = idx.setdefault('levels', {}).setdefault('south', {})
    nz = sum(1 for t in south if t[0] == Z_NEW)
    lv[str(Z_NEW)] = dict(n=nz, spacing_m=round(bg.tile_spacing_m('south', Z_NEW), 1))
    idx['sources']['PGDA 10 m (south z8)'] = PGDA10_URL
    new_bytes = sum(r['bytes'] for r in prog.values())
    idx['total_bytes'] = int(idx['total_bytes'] + sum(r['bytes'] for k, r in prog.items()
                                                      if tuple(map(int, k.split('/')[1:])) not in existing))
    idx['max_tile_bytes'] = max(idx['max_tile_bytes'], max((r['bytes'] for r in prog.values()), default=0))
    idx['hr_tiles'] = dict(card=14, kind='south', z=Z_NEW, spacing_m=round(bg.tile_spacing_m('south', Z_NEW), 1),
                           source='PGDA LOLA 10 m (LDEM_83S_10MPP_ADJ.TIF) site windows, bilinear at tile vertices',
                           n=nz, bytes=new_bytes, builder='pipeline/build_site_hr_tiles.py')
    IDX.write_text(json.dumps(idx, separators=(',', ':')))
    print(f'wrote {n} new PNGs this run; index +{added} entries; south z{Z_NEW} = {nz} tiles, '
          f'{new_bytes / 1e6:.1f} MB; {len(skipped)} parents skipped (coverage < 100 %)')
    return 0


def decode_png(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.int64)
    return (a[..., 0] * 256 + a[..., 1]) / 2.0 + bg.HMIN


def cmd_check(a):
    idx = json.loads(IDX.read_text())
    south = {(t[0], t[1], t[2]): t for t in idx['tiles']['south']}
    new = [k for k in south if k[0] == Z_NEW]
    srcs = sources()
    rep = dict(n_new=len(new), problems=[])
    enc_err, edge_err, par_diff = [], [], []
    for (z, x, y) in new:
        p = OUT / 'south' / str(z) / f'{x}_{y}.png'
        if not p.exists():
            rep['problems'].append(f'missing {p.name}')
            continue
        h = decode_png(p)
        if h.shape != (bg.N + 3, bg.N + 3):
            rep['problems'].append(f'{p.name} shape {h.shape}')
        # encoding: decoded == source heights within 0.25 m (0.5 m steps)
        enc_err.append(float(np.abs(h - heights(srcs, 'south', z, x, y)).max()))
        t = south[(z, x, y)]
        if not (t[3] <= h.min() + 1 and h.max() <= t[4] + 1):
            rep['problems'].append(f'{p.name} min/max in index {t[3:5]} vs {h.min()},{h.max()}')
        # shared edge with the east neighbour (same z) must be identical
        e = south.get((z, x + 1, y))
        if e:
            he = decode_png(OUT / 'south' / str(z) / f'{x + 1}_{y}.png')
            edge_err.append(float(np.abs(h[:, bg.N + 1] - he[:, 1]).max()))   # col N+1 == neighbour col 1
        # parent must exist and agree at coincident vertices (different DEM: 20 m vs 10 m)
        par = (z - 1, x // 2, y // 2)
        if par not in south:
            rep['problems'].append(f'{p.name} has no parent')
            continue
        hp = decode_png(OUT / 'south' / str(par[0]) / f'{par[1]}_{par[2]}.png')
        ox, oy = (x % 2) * 128, (y % 2) * 128
        child = h[1:bg.N + 2:2, 1:bg.N + 2:2]               # every 2nd child vertex
        parent = hp[1 + oy:1 + oy + 129, 1 + ox:1 + ox + 129]
        par_diff.append(child - parent)
    for (z, x, y) in new:      # sibling completeness
        bx, by = x - x % 2, y - y % 2
        if not all((z, bx + i, by + j) in south for i in (0, 1) for j in (0, 1)):
            rep['problems'].append(f'incomplete quad at {z}/{bx}/{by}')
    d = np.concatenate([q.ravel() for q in par_diff]) if par_diff else np.array([0.0])
    rep.update(encoding_max_abs_m=round(max(enc_err, default=0), 3),
               shared_edge_max_abs_m=round(max(edge_err, default=0), 3), n_edges=len(edge_err),
               child_vs_parent_m=dict(mean=round(float(d.mean()), 2), rms=round(float(np.sqrt((d ** 2).mean())), 2),
                                      p99_abs=round(float(np.percentile(np.abs(d), 99)), 2),
                                      max_abs=round(float(np.abs(d).max()), 2)),
               bytes=sum((OUT / 'south' / str(k[0]) / f'{k[1]}_{k[2]}.png').stat().st_size for k in new
                         if (OUT / 'south' / str(k[0]) / f'{k[1]}_{k[2]}.png').exists()))
    # which polar sites now reach z8 at the site itself
    sites_z8 = []
    for s in polar_sites():
        X, Y = bg.stere_fwd(s['lat'], s['lon'], True)
        sp = 2 * bg.CAP_HALF / 2 ** Z_NEW
        k = (Z_NEW, int((X + bg.CAP_HALF) // sp), int((bg.CAP_HALF - Y) // sp))
        sites_z8.append((s['id'], k in south))
    rep['sites_with_z8_at_site'] = [i for i, ok in sites_z8 if ok]
    rep['sites_without_z8'] = [i for i, ok in sites_z8 if not ok]
    dest = ROOT / 'data' / 'processed' / 'globe_hr_check.json'
    dest.write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != 'problems'}, indent=1))
    print('problems:', rep['problems'] or 'none')
    return 1 if rep['problems'] else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for c in ('plan', 'build', 'check'):
        sub.add_parser(c)
    a = ap.parse_args(argv)
    return {'plan': cmd_plan, 'build': cmd_build, 'check': cmd_check}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
