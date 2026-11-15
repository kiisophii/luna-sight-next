"""Independent check of web/data/terrain/<ID>.json landing_slope_deg (non-polar, SLDEM2015).

Independent of pipeline/nonpolar_slope.py: it does NOT read the cached window. It re-reads a small block
of the PDS tile with its own per-row HTTP Range requests and its own pixel-registration arithmetic taken
from the .lbl (LINE_PROJECTION_OFFSET / SAMPLE_PROJECTION_OFFSET), converts pixels to 3-D Cartesian points
and a local east-north-up frame (full curvature), and computes three different slope estimates:

  V1  Horn (1981) weighted 3x3 gradient at the four surrounding pixel centres, bilinear-interpolated
  V2  second-order polynomial surface fitted over 5x5 pixels in ENU, gradient at the site
  V3  least-squares plane in ENU over the 3x3 native pixels nearest the site (no interpolation)

Pass: every estimate within +/-0.5 deg of the stored value. Also prints the 500 m median by Horn.
Usage: python pipeline/verify_nonpolar_slope.py --site APOLLO17 [--practice 1.9]
"""
import argparse
import json
import math
import re
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
R = 1737400.0


def get(url, rng=None):
    req = urllib.request.Request(url, headers={'Range': rng} if rng else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def label_value(text, key):
    return float(re.search(rf'{key}\s*=\s*([-\d.]+)', text).group(1))


def read_block(url, rows, c0, c1, line_samples):
    out = []
    for r in rows:
        b = r * line_samples * 4
        out.append(np.frombuffer(get(url, f'bytes={b + c0 * 4}-{b + c1 * 4 - 1}'), '<f4'))
    return np.array(out, dtype=np.float64) * 1000.0       # km -> m above OFFSET


def enu(lat, lon, h, lat0, lon0):
    la, lo = np.radians(lat), np.radians(lon)
    p = (R + h)[..., None] * np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)
    a, b = math.radians(lat0), math.radians(lon0)
    e = np.array([-math.sin(b), math.cos(b), 0])
    n = np.array([-math.sin(a) * math.cos(b), -math.sin(a) * math.sin(b), math.cos(a)])
    u = np.array([math.cos(a) * math.cos(b), math.cos(a) * math.sin(b), math.sin(a)])
    o = R * u
    return (p - o) @ e, (p - o) @ n, (p - o) @ u


def plane_slope(x, y, z):
    A = np.c_[x.ravel(), y.ravel(), np.ones(x.size)]
    (gx, gy, _), *_ = np.linalg.lstsq(A, z.ravel(), rcond=None)
    return math.degrees(math.atan(math.hypot(gx, gy)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True)
    ap.add_argument('--practice', type=float, default=None, help='practice-board value, comparison only')
    a = ap.parse_args()
    prod = json.loads((ROOT / f'web/data/terrain/{a.site}.json').read_text(encoding='utf-8'))
    lat0, lon0 = prod['lat'], prod['lon'] % 360
    url = prod['source']['url']
    lbl = get(url[:-4] + '.lbl').decode('latin-1')
    res = label_value(lbl, 'MAP_RESOLUTION')
    loff, soff = label_value(lbl, 'LINE_PROJECTION_OFFSET'), label_value(lbl, 'SAMPLE_PROJECTION_OFFSET')
    clat, clon = label_value(lbl, 'CENTER_LATITUDE'), label_value(lbl, 'CENTER_LONGITUDE')
    ns = int(label_value(lbl, 'LINE_SAMPLES'))
    minlat, westlon = label_value(lbl, 'MINIMUM_LATITUDE'), label_value(lbl, 'WESTERNMOST_LONGITUDE')
    # PDS simple cylindrical (label): lat = clat + (LINE_PROJECTION_OFFSET - line)/res with line 0-based here,
    # where the offset is relative to the tile's southern edge; sample: lon = clon + (sample - SAMPLE_OFFSET)/res.
    line = loff - (lat0 - minlat - clat) * res
    samp = soff + (lon0 - clon) * res - westlon * res
    r0, c0 = int(math.floor(line)), int(math.floor(samp))
    half = 22                                                     # rows/cols around the site (~1.3 km)
    rows = range(r0 - half, r0 + half + 2)
    h = read_block(url, rows, c0 - half, c0 + half + 2, ns)
    lat = minlat + clat + (loff - np.arange(r0 - half, r0 + half + 2)) / res
    lon = westlon + clon + (np.arange(c0 - half, c0 + half + 2) - soff) / res
    LAT, LON = np.meshgrid(lat, lon, indexing='ij')
    E, N, U = enu(LAT, LON, h, lat0, lon0)
    fr, fc = line - r0, samp - c0
    i, j = half, half                                             # block index of (r0, c0)

    # V1 Horn at four pixel centres, then bilinear in (row, col)
    def horn(ii, jj):
        z = U[ii - 1:ii + 2, jj - 1:jj + 2]
        dx = (E[ii, jj + 1] - E[ii, jj - 1]) / 2
        dy = (N[ii - 1, jj] - N[ii + 1, jj]) / 2
        gx = ((z[0, 2] + 2 * z[1, 2] + z[2, 2]) - (z[0, 0] + 2 * z[1, 0] + z[2, 0])) / (8 * dx)
        gy = ((z[0, 0] + 2 * z[0, 1] + z[0, 2]) - (z[2, 0] + 2 * z[2, 1] + z[2, 2])) / (8 * dy)
        return math.degrees(math.atan(math.hypot(gx, gy)))
    v1 = ((1 - fr) * (1 - fc) * horn(i, j) + (1 - fr) * fc * horn(i, j + 1)
          + fr * (1 - fc) * horn(i + 1, j) + fr * fc * horn(i + 1, j + 1))
    # V2 quadratic over 5x5 centred on the nearest pixel, gradient at the site (ENU origin)
    ii, jj = i + round(fr), j + round(fc)
    x, y, z = (q[ii - 2:ii + 3, jj - 2:jj + 3].ravel() for q in (E, N, U))
    A = np.c_[np.ones_like(x), x, y, x * x, x * y, y * y]
    c, *_ = np.linalg.lstsq(A, z, rcond=None)
    v2 = math.degrees(math.atan(math.hypot(c[1], c[2])))
    # V3 plane over the nearest 3x3 native pixels
    v3 = plane_slope(*(q[ii - 1:ii + 2, jj - 1:jj + 2] for q in (E, N, U)))
    # 500 m median by Horn on native centres (comparison with slope_by_radius_m['500'])
    d = R * np.arccos(np.clip(np.sin(np.radians(LAT)) * math.sin(math.radians(lat0)) + np.cos(np.radians(LAT))
                              * math.cos(math.radians(lat0)) * np.cos(np.radians(LON - lon0)), -1, 1))
    hs = [horn(p, q) for p in range(1, h.shape[0] - 1) for q in range(1, h.shape[1] - 1) if d[p, q] <= 500]
    stored = prod['landing_slope_deg']
    print(f'{a.site}: stored landing_slope_deg {stored:.3f}; centre-pixel h {h[i, j]:.1f} m')
    ok = True
    for name, v in (('V1 Horn bilinear', v1), ('V2 quadratic 5x5', v2), ('V3 plane 3x3 nearest', v3)):
        dv = v - stored
        ok &= abs(dv) <= 0.5
        print(f'  {name:22s} {v:.3f} deg  diff {dv:+.3f}  {"PASS" if abs(dv) <= 0.5 else "FAIL"}')
    print(f'  500 m median: stored {prod["slope_by_radius_m"]["500"]["median_deg"]:.3f}, Horn {np.median(hs):.3f} (n={len(hs)})')
    if a.practice is not None:
        print(f'  practice-board value {a.practice} deg (comparison only): diff {stored - a.practice:+.2f} deg')
    print('RESULT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
