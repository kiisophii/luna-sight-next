"""Task Z2: bounded native 20 m NASA PSR windows and spherical distances.

Run from the repo root. Raw HTTP blocks and resumable windows are ignored on D:.
PSR is a modeled shadow classification, not evidence of confirmed ice.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_name, '1')

import argparse
import csv
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import tifffile
from pyproj import Geod

from fetch_polar import POLAR, PROJ, RADIUS, RangeFile, grid, read_window, validate_crs

URL = 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.TIF'
SOURCE_PAGE = 'https://pgda.gsfc.nasa.gov/products/90'
GEOD = Geod(a=RADIUS, b=RADIUS)
WARNING = 'PSR \u2260 confirmed ice.'


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def resume_matches(path, checkpoint, input_signature):
    return (path.exists() and checkpoint.get('input_signature') == input_signature
            and checkpoint.get('sha256') == file_hash(path))


def inverse(lat, lon, target_lat, target_lon):
    az, _, dist = GEOD.inv(lon, lat, target_lon, target_lat)
    return (None if dist < 1e-8 or abs(lat) == 90 else float(az % 360)), float(dist)


def _distances(lat, lon, x, y):
    if np.size(x) == 1:
        plon, plat = POLAR(float(np.asarray(x).item()), float(np.asarray(y).item()), inverse=True)
        return np.full(np.shape(x), GEOD.inv(lon, lat, plon, plat)[2])
    lons, lats = POLAR(x, y, inverse=True)
    _, _, distances = GEOD.inv(np.full_like(lons, lon), np.full_like(lats, lat), lons, lats)
    return np.asarray(distances)


def _point(lat, lon, x, y, guaranteed):
    plon, plat = POLAR(float(x), float(y), inverse=True)
    bearing, distance = inverse(lat, lon, plat, plon)
    return dict(lat=float(plat), lon=float(plon), x_m=float(x), y_m=float(y),
                distance_m=distance, bearing_deg=bearing, nearest_guaranteed=bool(guaranteed))


def _boundary_segments(a, x0, y0, step):
    """Only 1/0 interfaces; unknown pixels and window edges are not boundaries."""
    rr, cc = np.where(((a[:, :-1] == 1) & (a[:, 1:] == 0)) |
                      ((a[:, :-1] == 0) & (a[:, 1:] == 1)))
    xx = x0 + (cc + .5) * step
    yy = y0 - rr * step
    vertical = np.column_stack((xx, yy-step/2, xx, yy+step/2))
    rr, cc = np.where(((a[:-1, :] == 1) & (a[1:, :] == 0)) |
                      ((a[:-1, :] == 0) & (a[1:, :] == 1)))
    xx = x0 + cc * step
    yy = y0 - (rr + .5) * step
    horizontal = np.column_stack((xx-step/2, yy, xx+step/2, yy))
    return np.concatenate((vertical, horizontal))


def analyze(a, x0, y0, step, lat, lon, radius_m):
    """Nearest centers and union boundary, with a conservative missing-data bound.

    Pixel squares are mapped through inverse stereographic projection. Boundary
    distances minimize spherical geodesic distance continuously along each edge;
    this is deliberately not the PGDA vector product's interpolated contour.
    """
    valid = np.isfinite(a)
    if np.any(valid & (a != 0) & (a != 1)):
        raise ValueError('Unexpected PSR class; native full resolution must be 0/1/NaN')
    sx, sy = POLAR(lon, lat)
    rows, cols = a.shape
    left, right = x0-step/2, x0+(cols-.5)*step
    bottom, top = y0-(rows-.5)*step, y0+step/2
    maxrho = max(math.hypot(x, y) for x in (left, right) for y in (bottom, top))
    kmax = 1 + (maxrho/(2*RADIUS))**2
    # Any path leaving this rectangle must first cross its perimeter, where
    # stereographic scale is bounded by kmax. This bounds unsearched space.
    edge_lower = max(0., min(sx-left, right-sx, sy-bottom, top-sy)/kmax)
    ur, uc = np.where(~valid)
    unknown_lower = math.inf
    if ur.size:
        dx = np.maximum(abs(x0+uc*step-sx)-step/2, 0)
        dy = np.maximum(abs(y0-ur*step-sy)-step/2, 0)
        unknown_lower = float(np.hypot(dx, dy).min()/kmax)
    unseen_lower = min(edge_lower, unknown_lower)
    complete = unseen_lower >= radius_m
    col = math.floor((sx-left)/step)
    row = math.floor((top-sy)/step)
    code = a[row, col] if 0 <= row < rows and 0 <= col < cols else np.nan
    inside = bool(code == 1) if np.isfinite(code) else None
    rr, cc = np.where(a == 1)
    center = None
    if rr.size:
        xx, yy = x0+cc*step, y0-rr*step
        distances = _distances(lat, lon, xx, yy)
        i = int(np.argmin(distances))
        if distances[i] <= radius_m:
            center = _point(lat, lon, xx[i], yy[i], distances[i] < unseen_lower)
            center.update(row=int(rr[i]), col=int(cc[i]))
    segments = _boundary_segments(a, x0, y0, step)
    boundary = None
    if len(segments):
        px = np.clip(sx, segments[:, 0], segments[:, 2])
        py = np.clip(sy, segments[:, 1], segments[:, 3])
        projected = np.hypot(px-sx, py-sy)
        initial = _distances(lat, lon, px, py)
        best = float(initial.min())
        bx, by = px[int(initial.argmin())], py[int(initial.argmin())]
        # Rigorous scale lower bound prunes edges that cannot beat this best.
        for ax, ay, ex, ey in segments[projected/kmax <= best+1e-7]:
            def objective(t):
                return float(_distances(lat, lon, np.asarray(ax+t*(ex-ax)), np.asarray(ay+t*(ey-ay))))
            # Distance to a 20 m segment is unimodal in this south-polar cap.
            # Golden-section search avoids an extra numerical dependency.
            lo, hi = 0., 1.
            ratio = (math.sqrt(5)-1)/2
            u, v = hi-ratio*(hi-lo), lo+ratio*(hi-lo)
            fu, fv = objective(u), objective(v)
            for _ in range(55):
                if fu < fv:
                    hi, v, fv = v, u, fu
                    u = hi-ratio*(hi-lo)
                    fu = objective(u)
                else:
                    lo, u, fu = u, v, fv
                    v = lo+ratio*(hi-lo)
                    fv = objective(v)
            tmid = (lo+hi)/2
            for t, dist in ((0., objective(0)), (1., objective(1)), (tmid, objective(tmid))):
                if dist < best:
                    best, bx, by = float(dist), ax+t*(ex-ax), ay+t*(ey-ay)
        if best <= radius_m:
            boundary = _point(lat, lon, bx, by, best < unseen_lower)
    candidate = center if center is not None else boundary
    if candidate is not None:
        status = 'found' if candidate['nearest_guaranteed'] else 'incomplete_coverage'
    else:
        status = 'none_within_radius' if complete else 'incomplete_coverage'
    return dict(status=status, inside_psr=inside, site_class=None if inside is None else int(code),
                nearest_pixel_center=center, nearest_boundary=boundary,
                distance_to_psr_area_m=None if inside is None else (0. if inside else (boundary['distance_m'] if boundary else None)),
                distance_lower_bound_m=radius_m if complete and center is None and not inside and boundary is None else None,
                search=dict(radius_m=radius_m, complete_within_radius=bool(complete),
                            unsearched_or_nodata_lower_bound_m=unseen_lower,
                            window_edge_lower_bound_m=edge_lower,
                            nodata_lower_bound_m=None if math.isinf(unknown_lower) else unknown_lower,
                            nodata_pixels=int((~valid).sum()), pixels=int(a.size),
                            projection_max_scale=kmax))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    temp.replace(path)


def class_evidence(cache, page, stream):
    """Cross-check 1=PSR against a point strictly inside official PSR polygon 1."""
    with RangeFile(URL[:-3]+'CSV', cache/'blocks') as csv_stream:
        raw = csv_stream.read(1048576)
        csv.field_size_limit(1048576)
        row = next(csv.reader([raw.decode().splitlines()[1]]))
        ring_text = row[1].split('(((')[1].split(')')[0]
        ring = np.asarray([[float(v) for v in xy.strip().split()] for xy in ring_text.split(',')])
        y = (ring[:, 1].min()+ring[:, 1].max())/2 + .123
        crosses = []
        for (ax, ay), (bx, by) in zip(ring[:-1], ring[1:]):
            if (ay > y) != (by > y):
                crosses.append(ax+(y-ay)*(bx-ax)/(by-ay))
        crosses.sort()
        lo, hi = max(zip(crosses[::2], crosses[1::2]), key=lambda pair: pair[1]-pair[0])
        x = (lo+hi)/2
        x0, y0, step = grid(page)
        c, r = math.floor((x-x0)/step+.5), math.floor((y0-y)/step+.5)
        code = float(read_window(page, stream, (r, r+1, c, c+1))[0, 0])
        if code != 1:
            raise ValueError('Official PSR polygon interior does not match expected PSR class 1')
        return dict(url=URL[:-3]+'CSV', polygon_gid=int(row[0]), x_m=x, y_m=y,
                    sampled_class=code, first_record_sha256=hashlib.sha256(raw.splitlines()[1]).hexdigest(),
                    method='Scanline midpoint strictly inside first official PSR polygon; native raster class is 1')


def run(args):
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    cache = root/'data/processed/detail_z2'
    output = root/'web/data/detail/psr'
    # Withdraw a prior manifest before any preflight or regeneration can fail.
    # Per-site durable checkpoints still permit a safe interrupted resume.
    (output/'index.json').unlink(missing_ok=True)
    sites = [s for s in json.loads((root/'web/data/sites.json').read_text(encoding='utf-8')) if s['lat'] <= -80]
    if len(sites) != 16:
        raise ValueError(f'Expected 16 south-polar catalogue sites, got {len(sites)}')
    script_hash = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    with RangeFile(URL, cache/'blocks') as stream, tifffile.TiffFile(stream) as tif:
        page = tif.pages[0]
        validate_crs(page.geotiff_tags)
        x0, y0, step = grid(page)
        nodata = page.tags[42113].value.rstrip('\x00')
        if step != 20 or nodata.lower() != 'nan' or str(page.dtype) != 'float32':
            raise ValueError('Unexpected PSR native resolution/type/nodata')
        evidence = class_evidence(cache, page, stream)
        source = dict(url=URL, product_page=SOURCE_PAGE, paper_doi='10.3847/PSJ/acf3e1',
                      data_doi='10.60903/gsfcpgda-lola-spole', byte_size=stream.size,
                      etag=stream.etag, last_modified=stream.modified, resolution_m=step,
                      shape=list(page.shape), dtype=str(page.dtype), nodata=nodata,
                      codes={'0': 'not PSR', '1': 'PSR', 'NaN': 'unknown/no-data'},
                      projection=PROJ, frame='MOON_ME_DE421', reference_radius_m=RADIUS,
                      native_grid=dict(first_center_x_m=x0, first_center_y_m=y0),
                      geotiff_metadata=page.tags[42112].value, class_evidence=evidence)
        atomic_json(cache/'source.json', source)
        entries = []
        resumed = 0
        for site in sites:
            identity = dict(site={'id': site['id'], 'lat': site['lat'], 'lon': site['lon']},
                            radius_m=args.radius_m, source=source, script_sha256=script_hash,
                            fetch_polar_sha256=hashlib.sha256((root/'pipeline/fetch_polar.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest())
            sig = signature(identity)
            dest = output/(site['id']+'.json')
            checkpoint_path = cache/'results'/(site['id']+'.json')
            checkpoint = json.loads(checkpoint_path.read_text(encoding='utf-8')) if checkpoint_path.exists() else {}
            if not args.force and resume_matches(dest, checkpoint, sig):
                prior = json.loads(dest.read_text(encoding='utf-8'))
                if prior.get('input_signature') == sig:
                    entries.append(dict(id=site['id'], file=dest.name, status=prior['status'], sha256=file_hash(dest)))
                    resumed += 1
                    print(site['id'], 'resumed', flush=True)
                    continue
            sx, sy = POLAR(site['lon'], site['lat'])
            # The spherical search disk stays within angular distance c+d/R
            # of the pole. Its maximum scale bounds the projected path length.
            cap_angle = math.radians(90+site['lat']) + (args.radius_m+2*step)/RADIUS
            scale = 1/math.cos(cap_angle/2)**2
            half = scale*(args.radius_m+2*step)
            c0 = max(0, math.floor((sx-half-(x0-step/2))/step))
            c1 = min(page.imagewidth, math.ceil((sx+half-(x0-step/2))/step))
            r0 = max(0, math.floor(((y0+step/2)-(sy+half))/step))
            r1 = min(page.imagelength, math.ceil(((y0+step/2)-(sy-half))/step))
            bounds = [r0, r1, c0, c1]
            window_sig = signature(dict(source=[URL, stream.size, stream.etag, stream.modified], bounds=bounds))
            npz = cache/(site['id']+'_'+window_sig[:16]+'.npz')
            a = None
            if npz.exists():
                with np.load(npz) as saved:
                    cached = saved['classes']
                    if ('sha256' in saved and str(saved['sha256']) == hashlib.sha256(cached.astype('<f4').tobytes()).hexdigest()
                            and cached.shape == (r1-r0, c1-c0)):
                        a = cached
            if a is None:
                a = read_window(page, stream, bounds)
                tmp = npz.with_suffix('.tmp')
                with tmp.open('wb') as f:
                    np.savez_compressed(f, classes=a, sha256=hashlib.sha256(a.astype('<f4').tobytes()).hexdigest())
                tmp.replace(npz)
            wx, wy = x0+c0*step, y0-r0*step
            result = analyze(a, wx, wy, step, site['lat'], site['lon'], args.radius_m)
            if result['nearest_pixel_center']:
                result['nearest_pixel_center']['row'] += r0
                result['nearest_pixel_center']['col'] += c0
            result.update(schema_version=1, id=site['id'], lat=site['lat'], lon=site['lon'],
                          source=source, warning=WARNING, mock=False, input_signature=sig,
                          provenance=dict(script_sha256=script_hash, window_bounds_rc=bounds,
                                          window_first_center_xy_m=[wx, wy],
                                          window_sha256=hashlib.sha256(a.astype('<f4').tobytes()).hexdigest(),
                                          window_cache=str(npz.relative_to(root)).replace('\\', '/'),
                                          source_codes_observed=[float(x) for x in np.unique(a[np.isfinite(a)])]),
                          definitions=dict(center='Nearest center of a native class-1 pixel within search radius',
                                           boundary='Nearest 1/0 interface of the union of native 20 m pixel squares, inverse projected to the sphere; distance minimized continuously along edges',
                                           area='Zero inside PSR; otherwise nearest boundary distance',
                                           bearing='Initial true-north clockwise azimuth; null at geographic pole or zero distance',
                                           distance='Spherical geodesic on R=1737400 m; no terrain path or elevation correction'),
                          verification='Author checks only; independent team verification pending')
            atomic_json(dest, result)
            digest = file_hash(dest)
            atomic_json(checkpoint_path, dict(input_signature=sig, sha256=digest))
            entries.append(dict(id=site['id'], file=dest.name, status=result['status'], sha256=digest))
            center = result['nearest_pixel_center']
            print(site['id'], result['status'], None if center is None else round(center['distance_m'], 3), flush=True)
        atomic_json(output/'index.json', dict(schema_version=1, count=len(entries), sites=entries,
                                            source_url=URL, warning=WARNING, mock=False,
                                            input_signature=signature([json.loads((output/e['file']).read_text(encoding='utf-8'))['input_signature'] for e in entries])))
        stats = dict(elapsed_s=time.perf_counter()-started, resumed_sites=resumed,
                     downloaded_tif_bytes_this_run=stream.bytes_fetched, compute_workers=1, download_threads=1,
                     gpu_used=False, gpu_reason='Small native raster windows and HTTP I/O; no GPU transfer/kernel benefit expected')
        atomic_json(cache/'run.json', stats)
        atomic_json(cache/'runs'/(time.strftime('%Y%m%dT%H%M%S')+'.json'), stats)
        print(json.dumps(stats), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--radius-m', type=float, default=10000)
    parser.add_argument('--force', action='store_true')
    opts = parser.parse_args()
    if not 100 <= opts.radius_m <= 50000:
        parser.error('radius must be between 100 and 50000 m')
    run(opts)
