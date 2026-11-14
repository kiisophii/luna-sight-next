"""Card 9 basic quality checks (separate from the computation code).

    python pipeline/check_card9.py horizons     # non-polar horizon files
    python pipeline/check_card9.py gmaps        # whole-Moon map store + web export
    python pipeline/check_card9.py all

Horizons (web/data/horizon/<ID>.json for every site with lat > -80 in sites.json):
  file present; id/lat/lon identical to sites.json; 720 finite mask values in a plausible
  range; contract keys (az_step 0.5, obs 2 m, 300 km); mock flags; no missing DEM samples;
  DEM sources as expected (SLDEM2015 for |lat| < 60); h0_m equals the terrain height sampled
  directly from the cached DEM at the site; no polar (card 8) file written by this card.
Global maps (data/processed/gmaps_ppd<P>/ + web/data/gmaps/), not covered by check_contract.py:
  every row done; values finite and in 0..1; both <= earth; run parameters (real ephemeris,
  LDEM_64 near / LDEM_16 far, 2 m, 300 km); index.json consistent; every tile / overview /
  values PNG present with the right size and no no-data pixels; PNG values match the store;
  physical sanity (Earth always visible at the sub-Earth point, never on the far-side centre).
Exit code 1 if any check fails. Prints a summary and writes data/processed/check_card9.json.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_global as fg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web' / 'data'
POLAR_LAT = -80.0
FAIL = []


def bad(where, msg):
    FAIL.append(f'{where}: {msg}')
    print(f'  FAIL {where}: {msg}')


def check_horizons():
    sites = json.loads((WEB / 'sites.json').read_text(encoding='utf-8'))
    targets = [s for s in sites if s['lat'] > POLAR_LAT]
    polar_ids = {s['id'] for s in sites if s['lat'] <= POLAR_LAT}
    l64 = fg.LdemFile(fg.RAW / 'global' / 'ldem_64_float.img', fg.RAW / 'global' / 'ldem_64_float.lbl')
    rows = []
    print(f'Horizons: {len(targets)} non-polar targets (lat > {POLAR_LAT:g})')
    for s in targets:
        w = f'horizon/{s["id"]}.json'
        p = WEB / 'horizon' / f'{s["id"]}.json'
        if not p.exists():
            bad(w, 'missing')
            continue
        h = json.loads(p.read_text(encoding='utf-8'))
        m = np.array(h.get('mask', []), dtype=float)
        if h.get('id') != s['id'] or h.get('lat') != s['lat'] or h.get('lon') != s['lon']:
            bad(w, f'coords {h.get("lat")},{h.get("lon")} != sites.json {s["lat"]},{s["lon"]}')
        if m.size != 720 or not np.isfinite(m).all():
            bad(w, f'mask has {m.size} values, {int((~np.isfinite(m)).sum())} non-finite')
        elif not (-10 < m.min() and m.max() < 45):
            bad(w, f'mask range {m.min():.2f}..{m.max():.2f} deg implausible')
        for k, v in (('az_step_deg', 0.5), ('obs_height_m', 2), ('max_range_km', 300.0), ('mock', False),
                     ('site_coords_mock', bool(s.get('mock', False)))):
            if h.get(k) != v:
                bad(w, f'{k} = {h.get(k)!r}, expected {v!r}')
        e = h.get('engine', {})
        if e.get('n_missing_samples') != 0:
            bad(w, f'{e.get("n_missing_samples")} DEM samples missing')
        names = [d['name'] for d in h.get('dem_sources', [])]
        in_sldem = abs(s['lat']) < fg.SLDEM_LAT_LIMIT
        if in_sldem and (not names or names[0] != 'SLDEM2015'):
            bad(w, f'expected SLDEM2015 first, got {names}')
        if not in_sldem and 'SLDEM2015' in names:
            bad(w, 'SLDEM2015 used outside its coverage')
        # h0 straight from the cached DEM (independent of the horizon engine's samplers)
        if in_sldem:
            win = fg.SldemWindow(fg.RAW / 'sldem' / f'{s["id"]}.npz')
            if win.meta.get('site_lat') != s['lat'] or win.meta.get('site_lon') != s['lon']:
                bad(w, 'SLDEM window was cut for other coordinates')
            h0 = float(win.height(s['lat'], s['lon']))
        else:
            h0 = float(l64.sample(s['lat'], s['lon']))
        if abs(h0 - h['h0_m']) > 0.5:
            bad(w, f'h0_m {h["h0_m"]} vs DEM {h0:.2f} m')
        rows.append(dict(id=s['id'], lat=s['lat'], lon=s['lon'], h0_m=h['h0_m'], h0_dem_m=round(h0, 2),
                         mask_min=round(float(m.min()), 2), mask_max=round(float(m.max()), 2),
                         mask_mean=round(float(m.mean()), 2), sources=h['dem_sources']))
    extra = sorted(p.stem for p in (WEB / 'horizon').glob('*.json') if p.stem in polar_ids)
    if extra:
        print(f'  note: polar horizon files present (card 8, not checked here): {extra}')
    print(f'  {len(rows)}/{len(targets)} files checked')
    return dict(targets=len(targets), files=len(rows), sites=rows, polar_files_present=extra)


def check_gmaps(ppd=8):
    from PIL import Image
    store = ROOT / 'data' / 'processed' / f'gmaps_ppd{ppd}'
    web = WEB / 'gmaps'
    out = {}
    meta = json.loads((store / 'meta.json').read_text(encoding='utf-8'))
    sig = meta['signature']
    done = np.load(store / 'done.npy')
    print(f'Global map ppd {ppd}: {int(done.sum())}/{done.size} rows done')
    out['rows_done'], out['rows_total'] = int(done.sum()), int(done.size)
    if not done.all():
        bad('gmaps store', f'{int((~done.astype(bool)).sum())} rows not computed')
    expect = {('ephem', 'mock'): False, ('near', 'name'): 'LDEM_64', ('far', 'name'): 'LDEM_16'}
    for (a, b), v in expect.items():
        if sig[a][b] != v:
            bad('gmaps signature', f'{a}.{b} = {sig[a][b]!r}, expected {v!r}')
    for k, v in (('obs_height_m', 2.0), ('max_km', 300.0), ('near_km', 150.0), ('sun_radius_deg', 0.2666)):
        if sig[k] != v:
            bad('gmaps signature', f'{k} = {sig[k]!r}, expected {v!r}')
    arr = {f: np.load(store / f'{f}.npy') for f in ('sun', 'earth', 'both', 'h0', 'maskmax')}
    for f, a in arr.items():
        fin = np.isfinite(a)
        if not fin.all():
            bad(f'gmaps {f}', f'{int((~fin).sum())} non-finite cells')
        if f in ('sun', 'earth', 'both') and (np.nanmin(a) < 0 or np.nanmax(a) > 1):
            bad(f'gmaps {f}', f'values outside 0..1 ({np.nanmin(a)}..{np.nanmax(a)})')
    if np.any(arr['both'] > arr['earth'] + 1e-6):
        bad('gmaps both', 'both > earth somewhere')
    lat = 90 - (np.arange(180 * ppd) + 0.5) / ppd
    wgt = np.cos(np.radians(lat))[:, None] * np.ones((1, 360 * ppd))
    out['stats'] = {f: dict(min=round(float(np.nanmin(arr[f])), 4), max=round(float(np.nanmax(arr[f])), 4),
                            area_mean=round(float(np.nansum(arr[f] * wgt) / wgt.sum()), 4))
                    for f in ('sun', 'earth', 'both')}

    def at(f, la, lo):
        r = int((90 - la) * ppd)
        c = int((lo + 180) * ppd) % (360 * ppd)
        return float(arr[f][min(r, 180 * ppd - 1), c])
    probes = {'near_side_centre(0,0)': (0, 0), 'far_side_centre(0,180)': (0, 179.9),
              'east_limb(0,90)': (0, 90), 'west_limb(0,-90)': (0, -90)}
    out['probes'] = {k: {f: round(at(f, *v), 4) for f in ('sun', 'earth', 'both')} for k, v in probes.items()}
    if out['probes']['near_side_centre(0,0)']['earth'] < 0.99:
        bad('gmaps earth', 'Earth not always visible at the sub-Earth point')
    if out['probes']['far_side_centre(0,180)']['earth'] > 0.01:
        bad('gmaps earth', 'Earth visible at the far-side centre')
    eq = arr['sun'][(np.abs(lat) < 5)]
    out['sun_equator_band_mean'] = round(float(eq.mean()), 4)
    if not (0.40 < eq.mean() < 0.52):
        bad('gmaps sun', f'equatorial mean sun fraction {eq.mean():.3f} outside 0.40..0.52')

    # ---------------- web export
    idx_p = web / 'index.json'
    if not idx_p.exists():
        bad('gmaps web', 'index.json missing (run export)')
        return out
    idx = json.loads(idx_p.read_text(encoding='utf-8'))
    if idx.get('rows_done') != idx.get('rows_total') or idx.get('rows_done') != int(done.sum()):
        bad('index.json', f'rows_done {idx.get("rows_done")} / {idx.get("rows_total")} vs store {int(done.sum())}')
    if idx.get('mock') is not False or idx.get('ephem', {}).get('mock') is not False:
        bad('index.json', 'mock flag is not false')
    if idx.get('ppd') != ppd:
        bad('index.json', f'ppd {idx.get("ppd")}')
    n_tiles, n_missing = 0, 0
    for L in idx['layers']:
        for lv in idx['tiles']['levels']:
            for ty in range(lv['ny']):
                for tx in range(lv['nx']):
                    t = web / 'tiles' / L['id'] / str(lv['z']) / f'{tx}_{ty}.jpg'
                    n_tiles += 1
                    if not t.exists():
                        n_missing += 1
                    elif tx == 0 and ty == 0:
                        with Image.open(t) as im:
                            if im.size != (512, 512):
                                bad(str(t.relative_to(web)), f'size {im.size}')
        for key in ('overview', 'values_png'):
            f = web / L[key]
            if not f.exists():
                bad(f'gmaps {L["id"]}', f'{L[key]} missing')
                continue
            with Image.open(f) as im:
                if im.size != tuple(idx['overview_size']):
                    bad(L[key], f'size {im.size}')
                if key == 'values_png':
                    q = np.asarray(im)
        if (q == 255).any():
            bad(L['values_png'], f'{int((q == 255).sum())} no-data pixels')
        # PNG vs store: block-mean of the store at overview size (4096 = 2880 * 64/45; use 2x2-ish probe points)
        rng = np.random.default_rng(1)
        rr = rng.integers(0, q.shape[0], 500)
        cc = rng.integers(0, q.shape[1], 500)
        la_p = 90 - (rr + 0.5) * 180 / q.shape[0]
        lo_p = -180 + (cc + 0.5) * 360 / q.shape[1]
        sv = np.array([at(L['id'], a, b) for a, b in zip(la_p, lo_p)])
        dv = q[rr, cc] / 250.0 - sv
        out.setdefault('png_vs_store_median_abs', {})[L['id']] = round(float(np.median(np.abs(dv))), 4)
        if np.median(np.abs(dv)) > 0.02:
            bad(L['values_png'], f'median |PNG - store| {np.median(np.abs(dv)):.3f}')
    out['tiles_expected'], out['tiles_missing'] = n_tiles, n_missing
    if n_missing:
        bad('gmaps tiles', f'{n_missing}/{n_tiles} missing')
    out['index_stats'] = {L['id']: L['stats'] for L in idx['layers']}
    print(f'  tiles {n_tiles - n_missing}/{n_tiles}, stats {out["stats"]}')
    print(f'  probes {out["probes"]}')
    return out


def main(argv=None):
    what = (argv or sys.argv[1:] or ['all'])[0]
    rep = {}
    if what in ('horizons', 'all'):
        rep['horizons'] = check_horizons()
    if what in ('gmaps', 'all'):
        rep['gmaps'] = check_gmaps()
    rep['failures'] = FAIL
    dest = ROOT / 'data' / 'processed' / 'check_card9.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rep, indent=1), encoding='utf-8')
    print(f'\n{"OK" if not FAIL else f"{len(FAIL)} FAILURE(S)"} - report {dest.relative_to(ROOT).as_posix()}')
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
