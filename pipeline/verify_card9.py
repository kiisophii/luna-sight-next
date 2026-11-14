"""Card 9 independent verification (does NOT import horizon.py or global_maps.py).

    python pipeline/verify_card9.py horizons [--site APOLLO17 --site CHANGE4]
    python pipeline/verify_card9.py pgda [--n 400 --seed 42 --limit K]

horizons: brute-force re-computation of the site horizon from the raw DEM caches.
  - terrain read directly from the card 3 caches with its own bilinear code (SLDEM2015 NPZ,
    LDEM_64 via fetch_global.LdemFile - card 3 code, not the horizon engine samplers);
  - terrain points built with 3-D vector rotation (Rodrigues), elevation angle from the
    observer->point vector against the observer's local horizontal plane (curvature exact);
  - uniform fine distance steps (20 m to 150 km, 100 m to 300 km), no early stop;
  - also reports the effect of removing the 2 m observer height and of a flat-ground model,
    so the comparison shows that both are applied in the stored masks.
pgda: the card 9 check from docs/2단계_분배.md - sun fraction at random points 75-85 S vs
  PGDA AVGVISIB_75S_120M, computed over an 18.6-year window (one nodal cycle) instead of the
  2026-2030 window of the map:
  - same terrain as the 3.8 km map (LDEM_64 to 150 km, LDEM_16 to 300 km), observer 2 m,
    720 azimuths, fine steps, no early stop, own code;
  - ephemeris data/processed/ephem_2020-2038_2h.npz (pipeline/ephem.py validation series);
  - definitions: sun_mean (map definition, mean visible disc fraction), sun_any (any part of the
    disc), earth_ctr (map definition), earth_any (PGDA definition, any part of the Earth disc);
  - PGDA read with tifffile and the GeoTIFF tie point / pixel scale (pixel-is-area), nearest
    pixel plus the min..max over the 3x3 neighbourhood (+-120 m);
  - per-point results cached (resume) in data/processed/verify_card9_pgda_points.jsonl.
Outputs: data/processed/verify_card9_horizons.json, data/processed/verify_card9_pgda.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_global as fg  # noqa: E402  (card 3 DEM readers; independent of horizon.py)

ROOT = Path(__file__).resolve().parents[1]
R = 1737400.0
OBS = 2.0
SUN_R_DEG = 0.2666
EARTH_R_KM = 6371.0
PROC = ROOT / 'data' / 'processed'


# ------------------------------------------------------------------ terrain (own readers)
class Sldem:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as z:
            self.h = z['height_m'].astype(np.float64)
            self.lat = z['lat'].astype(float)
            self.lu = z['lon_unwrapped'].astype(float)
            self.meta = json.loads(str(z['meta']))

    def __call__(self, lat, lon):
        out = np.full(np.shape(lat), np.nan)
        res = 512.0
        mid = 0.5 * (self.lu[0] + self.lu[-1])
        lon = np.mod(lon - mid + 180.0, 360.0) + mid - 180.0
        r = (self.lat[0] - lat) * res
        c = (lon - self.lu[0]) * res
        ok = (r >= 0) & (r <= self.h.shape[0] - 1) & (c >= 0) & (c <= self.h.shape[1] - 1)
        r, c = r[ok], c[ok]
        r0 = np.minimum(np.floor(r).astype(int), self.h.shape[0] - 2)
        c0 = np.minimum(np.floor(c).astype(int), self.h.shape[1] - 2)
        fr, fc = r - r0, c - c0
        h = self.h
        out[ok] = ((1 - fr) * ((1 - fc) * h[r0, c0] + fc * h[r0, c0 + 1])
                   + fr * ((1 - fc) * h[r0 + 1, c0] + fc * h[r0 + 1, c0 + 1]))
        return out


def ldem(ppd):
    base = fg.RAW / 'global' / f'ldem_{ppd}_float'
    return fg.LdemFile(base.with_suffix('.img'), base.with_suffix('.lbl'))


# ------------------------------------------------------------------ geometry (own)
def unit(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)


def enu(lat, lon):
    u = unit(lat, lon)
    e = np.array([-math.sin(math.radians(lon)), math.cos(math.radians(lon)), 0.0])
    n = np.cross(u, e)
    return e, n, u


def ray_points(lat, lon, az_deg, dist_m):
    """Rodrigues rotation of the site vector about the axis perpendicular to the azimuth plane."""
    e, n, u = enu(lat, lon)
    az = np.radians(np.asarray(az_deg, float))
    d = np.outer(np.cos(az), n) + np.outer(np.sin(az), e)          # (na, 3) initial direction
    k = np.cross(u[None, :], d)                                     # rotation axis
    th = np.asarray(dist_m, float) / R
    # p(theta) = u cos(theta) + (k x u) sin(theta)   (k is perpendicular to u)
    kxu = np.cross(k, u[None, :])
    p = u[None, None, :] * np.cos(th)[None, :, None] + kxu[:, None, :] * np.sin(th)[None, :, None]
    lat_p = np.degrees(np.arcsin(np.clip(p[..., 2], -1, 1)))
    lon_p = np.degrees(np.arctan2(p[..., 1], p[..., 0]))
    return p, lat_p, lon_p


def elevation_deg(u_obs, r_obs, p_unit, r_t):
    """Angle of (P_t - P_o) above the plane perpendicular to u_obs."""
    v = p_unit * r_t[..., None] - u_obs * r_obs
    return np.degrees(np.arcsin(np.einsum('...k,k->...', v, u_obs) / np.linalg.norm(v, axis=-1)))


def brute_mask(lat, lon, az, sample, h0, near_m, max_m=300e3, d_near=20.0, d_far=100.0,
               d_min=20.0, obs=OBS, flat=False):
    """Max elevation per azimuth from uniform steps (no early stop). sample(lat, lon, dist) -> h."""
    dist = np.concatenate([np.arange(d_min, near_m + 1e-6, d_near),
                           np.arange(near_m + d_far, max_m + 1e-6, d_far)])
    p, la, lo = ray_points(lat, lon, az, dist)
    h = sample(la, lo, np.broadcast_to(dist[None, :], la.shape))
    u = unit(lat, lon)
    if flat:   # flat ground: height difference over horizontal distance, no curvature
        el = np.degrees(np.arctan2(h - (h0 + obs), dist[None, :]))
    else:
        el = elevation_deg(u, R + h0 + obs, p, R + h)
    miss = int(np.isnan(el).sum())
    el = np.where(np.isnan(el), -np.inf, el)
    k = np.argmax(el, axis=1)
    return el.max(axis=1), dist[k], miss


# ------------------------------------------------------------------ horizons
def verify_horizons(ids):
    sites = {s['id']: s for s in json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8'))}
    l64, l16 = ldem(64), ldem(16)
    out = []
    for sid in ids:
        s = sites[sid]
        rec = json.loads((ROOT / 'web/data/horizon' / f'{sid}.json').read_text(encoding='utf-8'))
        mask = np.array(rec['mask'])
        in_sldem = abs(s['lat']) < 60
        sl = Sldem(fg.RAW / 'sldem' / f'{sid}.npz') if in_sldem else None
        near_m = 150e3          # fine 20 m steps to 150 km for every site (LDEM_64 when no SLDEM)

        def sample(la, lo, dist):
            h = np.full(la.shape, np.nan)
            if sl is not None:
                m = dist <= 150e3
                h[m] = sl(la[m], lo[m])
            rest = np.isnan(h)
            h[rest] = l64.sample(la[rest], lo[rest])
            rest = np.isnan(h)
            if rest.any():
                h[rest] = l16.sample(la[rest], lo[rest])
            return h

        h0 = float(sl(np.array([s['lat']]), np.array([s['lon']]))[0]) if sl else float(l64.sample(s['lat'], s['lon']))
        k_az = np.arange(0, 720, 36) + 7                    # 20 azimuths, odd offsets (not just cardinal)
        az = k_az * 0.5
        t0 = time.time()
        ind, dmax, miss = brute_mask(s['lat'], s['lon'], az, sample, h0, max(near_m, 1.0))
        ind_0m, _, _ = brute_mask(s['lat'], s['lon'], az, sample, h0, max(near_m, 1.0), obs=0.0)
        ind_flat, _, _ = brute_mask(s['lat'], s['lon'], az, sample, h0, max(near_m, 1.0), flat=True)
        ind_02, _, _ = brute_mask(s['lat'], s['lon'], az, sample, h0, max(near_m, 1.0), d_min=200.0)
        stored = mask[k_az]
        d = ind - stored
        row = dict(id=sid, lat=s['lat'], lon=s['lon'], file_lat=rec['lat'], file_lon=rec['lon'],
                   h0_file_m=rec['h0_m'], h0_dem_m=round(h0, 2), obs_height_m=rec['obs_height_m'],
                   n_azimuths=int(az.size), missing_samples=miss, seconds=round(time.time() - t0, 1),
                   max_abs_err_deg=round(float(np.abs(d).max()), 4),
                   mean_abs_err_deg=round(float(np.abs(d).mean()), 4),
                   max_abs_err_vs_independent_from_0p2km=round(float(np.abs(ind_02 - stored).max()), 4),
                   effect_obs_2m_vs_0m_deg=round(float(np.abs(ind - ind_0m).max()), 4),
                   effect_curvature_flat_minus_sphere_deg=round(float((ind_flat - ind).max()), 4),
                   rms_stored_vs_no_obs_height=round(float(np.sqrt(np.mean((stored - ind_0m) ** 2))), 4),
                   rms_stored_vs_flat=round(float(np.sqrt(np.mean((stored - ind_flat) ** 2))), 4),
                   azimuths=[dict(az=float(a), stored=round(float(x), 4), independent=round(float(y), 4),
                                  diff=round(float(y - x), 4), peak_km=round(float(p) / 1000, 2))
                             for a, x, y, p in zip(az, stored, ind, dmax)])
        out.append(row)
        print(f"{sid}: max |diff| {row['max_abs_err_deg']} deg, mean {row['mean_abs_err_deg']} deg; "
              f"h0 file {rec['h0_m']} vs DEM {h0:.2f} m; 2 m effect {row['effect_obs_2m_vs_0m_deg']} deg; "
              f"flat-ground excess up to {row['effect_curvature_flat_minus_sphere_deg']} deg; {row['seconds']} s")
    dest = PROC / 'verify_card9_horizons.json'
    dest.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(f'-> {dest.relative_to(ROOT).as_posix()}')
    return out


# ------------------------------------------------------------------ PGDA
class Pgda:
    """GeoTIFF read with tifffile; georeferencing from ModelTiepoint / ModelPixelScale."""

    def __init__(self, path):
        import tifffile
        with tifffile.TiffFile(path) as t:
            pg = t.pages[0]
            self.dn = pg.asarray()
            tags = {tg.name: tg.value for tg in pg.tags}
        tie = tags['ModelTiepointTag']
        scale = tags['ModelPixelScaleTag']
        self.x0, self.y0 = tie[3] - tie[0] * scale[0], tie[4] + tie[1] * scale[1]   # outer corner
        self.dx, self.dy = scale[0], scale[1]
        gkeys = tags.get('GeoKeyDirectoryTag')
        self.pixel_is_area = True
        if gkeys is not None:
            g = list(gkeys)
            for i in range(4, len(g), 4):
                if g[i] == 1025:          # GTRasterTypeGeoKey: 1 = PixelIsArea, 2 = PixelIsPoint
                    self.pixel_is_area = (g[i + 3] == 1)
        if not self.pixel_is_area:
            self.x0 -= self.dx / 2
            self.y0 += self.dy / 2
        self.val = np.where(self.dn == -32768, np.nan, self.dn * 4e-5)

    def rc(self, lat, lon):
        la, lo = np.radians(lat), np.radians(lon)
        rho = 2 * R * np.tan(np.pi / 4 + la / 2)
        x, y = rho * np.sin(lo), rho * np.cos(lo)
        return np.floor((self.y0 - y) / self.dy).astype(int), np.floor((x - self.x0) / self.dx).astype(int)

    def sample(self, lat, lon):
        r, c = self.rc(lat, lon)
        v = self.val[r, c]
        blk = np.stack([self.val[r + a, c + b] for a in (-1, 0, 1) for b in (-1, 0, 1)])
        return v, np.nanmin(blk, axis=0), np.nanmax(blk, axis=0)


def random_points(n, seed, lat_min=-85.0, lat_max=-75.0):
    rng = np.random.default_rng(seed)
    s = rng.uniform(math.sin(math.radians(lat_min)), math.sin(math.radians(lat_max)), n)
    return np.degrees(np.arcsin(s)), rng.uniform(-180.0, 180.0, n)


def disk_frac(x):
    x = np.clip(x, -1, 1)
    return 0.5 + (x * np.sqrt(1 - x * x) + np.arcsin(x)) / np.pi


def fractions(lat, lon, h0, az_grid, mask, eph):
    u = unit(lat, lon)
    e, n, _ = enu(lat, lon)
    ro = (R + h0 + OBS) / 1000.0                              # km
    res = {}
    for body, cols, rad_km in (('sun', slice(0, 3), 696000.0), ('earth', slice(3, 6), EARTH_R_KM)):
        v = eph[:, cols] - ro * u
        dist = np.linalg.norm(v, axis=1)
        el = np.degrees(np.arcsin(v @ u / dist))
        az = np.degrees(np.arctan2(v @ e, v @ n)) % 360
        m = np.interp(az, np.append(az_grid, 360.0), np.append(mask, mask[0]))
        if body == 'sun':
            f = disk_frac((el - m) / SUN_R_DEG)
            res['sun_mean'] = float(f.mean())
            res['sun_any'] = float((el > m - SUN_R_DEG).mean())
            sunlit = f >= 0.5
        else:
            er = np.degrees(np.arcsin(rad_km / dist))
            vis_c = el > m
            res['earth_ctr'] = float(vis_c.mean())
            res['earth_any'] = float((el > m - er).mean())
            res['both_ctr'] = float((vis_c & sunlit).mean())
    return res


def verify_pgda(n, seed, limit=None, n_az=720):
    eph = np.load(PROC / 'ephem_2020-2038_2h.npz')['vectors'].astype(np.float64)
    pg_s = Pgda(fg.RAW / 'pgda' / 'AVGVISIB_75S_120M_201608.TIF')
    pg_e = Pgda(fg.RAW / 'pgda' / 'AVGVISIB_75S_120M_201608_EARTH.TIF')
    l64, l16 = ldem(64), ldem(16)
    lat, lon = random_points(n, seed)
    cache = PROC / 'verify_card9_pgda_points.jsonl'
    done = {}
    if cache.exists():
        for line in cache.read_text(encoding='utf-8').splitlines():
            d = json.loads(line)
            if d.get('seed') == seed and d.get('n_total') == n:
                done[d['k']] = d
    az = np.arange(n_az) * 360.0 / n_az

    def sample(la, lo, dist):
        h = np.where(dist <= 150e3, l64.sample(la, lo), l16.sample(la, lo))
        return h

    todo = [k for k in range(n) if k not in done][:limit]
    t0 = time.time()
    with cache.open('a', encoding='utf-8') as fh:
        for i, k in enumerate(todo, 1):
            h0 = float(l64.sample(lat[k], lon[k]))
            mask, _, miss = brute_mask(lat[k], lon[k], az, sample, h0, 150e3, d_near=200.0, d_far=500.0, d_min=200.0)
            fr = fractions(lat[k], lon[k], h0, az, mask, eph)
            ps, ps_lo, ps_hi = pg_s.sample(np.array([lat[k]]), np.array([lon[k]]))
            pe, pe_lo, pe_hi = pg_e.sample(np.array([lat[k]]), np.array([lon[k]]))
            d = dict(k=k, seed=seed, n_total=n, lat=float(lat[k]), lon=float(lon[k]), h0_m=round(h0, 1),
                     mask_max=round(float(mask.max()), 3), missing=miss, **{a: round(b, 5) for a, b in fr.items()},
                     pgda_sun=float(ps[0]), pgda_sun_min=float(ps_lo[0]), pgda_sun_max=float(ps_hi[0]),
                     pgda_earth=float(pe[0]), pgda_earth_min=float(pe_lo[0]), pgda_earth_max=float(pe_hi[0]))
            fh.write(json.dumps(d) + '\n')
            fh.flush()
            done[k] = d
            if i % 20 == 0 or i == len(todo):
                el = time.time() - t0
                print(f'  {i}/{len(todo)} points, {el / i:.2f} s/point, ETA {(len(todo) - i) * el / i / 60:.1f} min',
                      flush=True)
    rows = [done[k] for k in sorted(done)]
    if len(rows) < n:
        print(f'partial: {len(rows)}/{n} points cached')
        return None

    def stats(ours, truth, lo=None, hi=None):
        a, b = np.array(ours), np.array(truth)
        ok = np.isfinite(a) & np.isfinite(b)
        a, b = a[ok], b[ok]
        dd = (a - b) * 100
        s = dict(n=int(ok.sum()), mae_pp=round(float(np.abs(dd).mean()), 3),
                 rmse_pp=round(float(np.sqrt((dd ** 2).mean())), 3), bias_pp=round(float(dd.mean()), 3),
                 r=round(float(np.corrcoef(a, b)[0, 1]), 4))
        if lo is not None:
            l, h = np.array(lo)[ok], np.array(hi)[ok]
            s['inside_pgda_3x3_range_pct'] = round(float(((a >= l) & (a <= h)).mean() * 100), 1)
        return s
    g = lambda key: [r[key] for r in rows]  # noqa: E731
    rep = {
        'what': 'card 9 PGDA check, independent code (no horizon.py / global_maps.py)',
        'points': {'n': n, 'seed': seed, 'lat_range': [-85, -75], 'sampling': 'uniform by area'},
        'ephemeris': {'file': 'data/processed/ephem_2020-2038_2h.npz', 'window': '2020-01-01..2038-07-31T22Z',
                      'step_h': 2, 'n': int(eph.shape[0])},
        'terrain': 'LDEM_64 to 150 km, LDEM_16 to 300 km (same DEMs as the 3.8 km map); 720 az; '
                   '200 m steps to 150 km, 500 m to 300 km; no early stop; observer 2 m; curvature exact',
        'pgda': {'files': ['AVGVISIB_75S_120M_201608.TIF', 'AVGVISIB_75S_120M_201608_EARTH.TIF'],
                 'value': 'DN x 4e-5, nearest 120 m pixel; range = min..max of 3x3 pixels'},
        'sun_mean_vs_pgda_sun': stats(g('sun_mean'), g('pgda_sun'), g('pgda_sun_min'), g('pgda_sun_max')),
        'sun_any_vs_pgda_sun': stats(g('sun_any'), g('pgda_sun'), g('pgda_sun_min'), g('pgda_sun_max')),
        'earth_any_vs_pgda_earth': stats(g('earth_any'), g('pgda_earth'), g('pgda_earth_min'), g('pgda_earth_max')),
        'earth_ctr_vs_pgda_earth': stats(g('earth_ctr'), g('pgda_earth'), g('pgda_earth_min'), g('pgda_earth_max')),
        'missing_dem_samples': int(sum(r['missing'] for r in rows)),
    }
    err = np.array([abs(r['sun_mean'] - r['pgda_sun']) for r in rows])
    worst = np.argsort(-np.nan_to_num(err))[:10]
    rep['largest_sun_errors'] = [dict(k=rows[i]['k'], lat=round(rows[i]['lat'], 3), lon=round(rows[i]['lon'], 3),
                                      ours=rows[i]['sun_mean'], pgda=round(rows[i]['pgda_sun'], 4),
                                      pgda_3x3=[round(rows[i]['pgda_sun_min'], 4), round(rows[i]['pgda_sun_max'], 4)],
                                      mask_max=rows[i]['mask_max'], h0_m=rows[i]['h0_m']) for i in worst]
    dest = PROC / 'verify_card9_pgda.json'
    dest.write_text(json.dumps(rep, indent=1), encoding='utf-8')
    for k in ('sun_mean_vs_pgda_sun', 'sun_any_vs_pgda_sun', 'earth_any_vs_pgda_earth', 'earth_ctr_vs_pgda_earth'):
        print(f'{k}: {rep[k]}')
    print(f'-> {dest.relative_to(ROOT).as_posix()}')
    return rep


def site_sampler(s, l64, l16):
    sl = Sldem(fg.RAW / 'sldem' / f'{s["id"]}.npz') if abs(s['lat']) < 60 else None

    def sample(la, lo, dist):
        h = np.full(la.shape, np.nan)
        if sl is not None:
            m = dist <= 150e3
            h[m] = sl(la[m], lo[m])
        rest = np.isnan(h)
        h[rest] = l64.sample(la[rest], lo[rest])
        rest = np.isnan(h)
        if rest.any():
            h[rest] = l16.sample(la[rest], lo[rest])
        return h
    h0 = float(sl(np.array([s['lat']]), np.array([s['lon']]))[0]) if sl else float(l64.sample(s['lat'], s['lon']))
    return sample, h0


def full_sites():
    """All 720 azimuths for every non-polar site, brute force from 20 m and from 200 m, plus the
    effect of the near-field cut-off on the 2026-2030 sun / Earth fractions (map definitions)."""
    sites = [s for s in json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8')) if s['lat'] > -80]
    l64, l16 = ldem(64), ldem(16)
    eph = np.fromfile(ROOT / 'web/data/ephem.bin', '<f4').reshape(-1, 6)[::2].astype(np.float64)
    az = np.arange(720) * 0.5
    out = []
    for s in sites:
        rec = json.loads((ROOT / 'web/data/horizon' / f'{s["id"]}.json').read_text(encoding='utf-8'))
        stored = np.array(rec['mask'])
        sample, h0 = site_sampler(s, l64, l16)
        t0 = time.time()
        m20 = np.empty(720)
        m200 = np.empty(720)
        pk = np.empty(720)
        for i in range(0, 720, 60):
            m20[i:i + 60], pk[i:i + 60], _ = brute_mask(s['lat'], s['lon'], az[i:i + 60], sample, h0, 150e3)
            m200[i:i + 60], _, _ = brute_mask(s['lat'], s['lon'], az[i:i + 60], sample, h0, 150e3, d_min=200.0)
        f_st = fractions(s['lat'], s['lon'], h0, az, stored, eph)
        f_20 = fractions(s['lat'], s['lon'], h0, az, m20, eph)
        row = dict(id=s['id'], lat=s['lat'],
                   max_abs_vs_brute_200m=round(float(np.abs(m200 - stored).max()), 4),
                   rms_vs_brute_200m=round(float(np.sqrt(np.mean((m200 - stored) ** 2))), 4),
                   max_abs_vs_brute_20m=round(float(np.abs(m20 - stored).max()), 4),
                   n_az_raised_over_0p05deg_by_0p02_0p2km=int(((m20 - stored) > 0.05).sum()),
                   sun_mean_stored=round(f_st['sun_mean'], 5), sun_mean_from_20m=round(f_20['sun_mean'], 5),
                   earth_ctr_stored=round(f_st['earth_ctr'], 5), earth_ctr_from_20m=round(f_20['earth_ctr'], 5),
                   seconds=round(time.time() - t0, 1))
        out.append(row)
        print(f"{s['id']:<17} vs brute(0.2 km): max {row['max_abs_vs_brute_200m']:.4f} rms {row['rms_vs_brute_200m']:.4f} | "
              f"vs brute(20 m): max {row['max_abs_vs_brute_20m']:.4f}, {row['n_az_raised_over_0p05deg_by_0p02_0p2km']} az >0.05 | "
              f"sun {row['sun_mean_stored']:.4f}->{row['sun_mean_from_20m']:.4f} earth {row['earth_ctr_stored']:.4f}->"
              f"{row['earth_ctr_from_20m']:.4f} | {row['seconds']} s", flush=True)
    dest = PROC / 'verify_card9_full_sites.json'
    dest.write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(f'-> {dest.relative_to(ROOT).as_posix()}')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('full', help='720 azimuths x 17 sites brute force + near-field effect on fractions')
    p = sub.add_parser('horizons')
    p.add_argument('--site', action='append')
    p = sub.add_parser('pgda')
    p.add_argument('--n', type=int, default=400)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--limit', type=int, default=None, help='compute at most K new points (benchmark)')
    a = ap.parse_args(argv)
    if a.cmd == 'full':
        full_sites()
    elif a.cmd == 'horizons':
        verify_horizons(a.site or ['APOLLO17', 'CHANGE4'])
    else:
        verify_pgda(a.n, a.seed, a.limit)
    return 0


if __name__ == '__main__':
    sys.exit(main())
