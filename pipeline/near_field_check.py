"""Five-site near-field audit; original PDS footprints and native SLDEM pixels.

Writes diagnostic documents only. Never edits production horizons, metrics or DEMs.
"""
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

import horizon as hz
import run_horizons as rh
from compare_near_field import IDS, METRICS, PGDA, ROOT
from local_maps import CoreMetrics, sha_file

WORK = ROOT / 'data/processed/near_field_check'
PDS = 'https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/'


def original_labels():
    """Read original labels, not overview pixels or a clamped map coordinate."""
    products = []
    WORK.mkdir(parents=True, exist_ok=True)
    for pole in ('S', 'N'):
        for suffix in ('', '_EARTH'):
            stem = f'AVGVISIB_65{pole}_240M_201608{suffix}'
            path = WORK / (stem + '.LBL')
            if not path.exists():
                with urllib.request.urlopen(PDS + path.name, timeout=30) as response:
                    path.write_bytes(response.read())
            label = hz._parse_pds_label(path.read_text(encoding='ascii'))
            products.append(dict(product=stem, label_url=PDS + path.name,
                image_url=PDS + stem + '.IMG', label_sha256=sha_file(path),
                pole=pole, metric='earth_frac' if suffix else 'sun_frac',
                metadata={k: label[k] for k in ('LINES', 'LINE_SAMPLES', 'MAP_SCALE',
                    'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET',
                    'CENTER_LATITUDE', 'MINIMUM_LATITUDE', 'MAXIMUM_LATITUDE',
                    'SCALING_FACTOR', 'OFFSET')}))
    return products


def footprint(site, product):
    """Conservative projected bounds for the complete geodesic 300 m disc."""
    label = product['metadata']
    south = product['pole'] == 'S'
    x, y = hz.polar_stereo_xy(site['lat'], site['lon'], south=south)
    angular_radius = 300 / hz.R_M
    colatitude = np.radians(90 + site['lat'] if south else 90 - site['lat'])
    # Stereographic local scale sec^2(theta/2); maximum along any path in this disc.
    bound_m = 300 / np.cos((colatitude + angular_radius) / 2)**2
    scale = label['MAP_SCALE']
    row = label['LINE_PROJECTION_OFFSET'] - float(y) / scale
    col = label['SAMPLE_PROJECTION_OFFSET'] + float(x) / scale
    pad = bound_m / scale
    nr, nc = label['LINES'], label['LINE_SAMPLES']
    outside = row + pad < -.5 or row - pad > nr-.5 or col + pad < -.5 or col - pad > nc-.5
    return dict(product=product['product'], row=row, col=col,
        radius_300m_projected_bound_m=float(bound_m), entire_300m_disc_outside=bool(outside),
        center=None, min_300m=None, max_300m=None,
        status='outside_raster_extent' if outside else 'requires_pixel_read')


def pixel_coordinates(sampler, lat, lon):
    mid = sampler.lon0 + .5 * sampler.dlon * (sampler.h.shape[1]-1)
    lon = (np.asarray(lon)-mid+180) % 360 + mid-180
    return (sampler.lat0-np.asarray(lat))/sampler.dlat, (lon-sampler.lon0)/sampler.dlon


def positive_spike(height, neighbors):
    """Diagnostic heuristic, not an instrument-calibrated noise classifier."""
    median = float(np.median(neighbors))
    mad = float(np.median(np.abs(neighbors-median)))
    threshold = max(1., 3*1.4826*mad)
    return dict(height_m=float(height), neighbor_median_m=median,
        excess_above_neighbor_median_m=float(height-median),
        excess_above_highest_neighbor_m=float(height-np.max(neighbors)),
        robust_threshold_m=threshold,
        candidate=bool(height > np.max(neighbors) and height-median > threshold))


def local_diagnostic(site, chain, far, near, core):
    sampler = chain[0][0]
    if not isinstance(sampler, hz.LatLonWindowSampler):
        raise ValueError('Expected native SLDEM window for these five sites')
    distances = hz.distances_km(.005, 300., 8000)
    distances = distances[distances < .2]
    az = np.arange(720)*.5
    lat, lon = hz.destination(site['lat'], site['lon'], az[:, None], distances[None, :]*1000)
    heights = sampler.sample(lat, lon)
    theta = distances / (hz.R_M/1000)
    rt = hz.R_M + heights
    angles = np.degrees(np.arctan2(rt*np.cos(theta)-(hz.R_M+near['h0_m']+2), rt*np.sin(theta)))
    winners = np.argmax(angles, axis=1)
    near_mask = angles[np.arange(720), winners]
    affected = near_mask > far['mask'] + .0001
    rows, cols = pixel_coordinates(sampler, lat[np.arange(720), winners], lon[np.arange(720), winners])
    cells = set()
    for row, col in zip(rows[affected], cols[affected]):
        r, c = int(np.floor(row)), int(np.floor(col))
        cells.update((r+dr, c+dc) for dr in (0, 1) for dc in (0, 1))
    # Include the ground interpolation cells: a bad observer pixel can also alter a mask.
    ground_row, ground_col = pixel_coordinates(sampler, site['lat'], site['lon'])
    gr, gc = int(np.floor(ground_row)), int(np.floor(ground_col))
    cells.update((gr+dr, gc+dc) for dr in (0, 1) for dc in (0, 1))
    pixels = []
    for row, col in sorted(cells):
        window = sampler.h[row-1:row+2, col-1:col+2]
        neighbors = np.delete(window.ravel(), 4)
        if neighbors.size != 8 or not np.isfinite(window).all():
            raise ValueError('Incomplete native-pixel neighborhood')
        pixels.append(dict(row=row, col=col, **positive_spike(window[1,1], neighbors)))
    candidates = [p for p in pixels if p['candidate']]
    # Replace only flagged native cells with their original eight-neighbour median,
    # in this in-memory sampler. Recompute observer and full horizon consistently.
    corrected = None
    if candidates:
        saved = [(p['row'], p['col'], sampler.h[p['row'], p['col']]) for p in candidates]
        try:
            for p in candidates: sampler.h[p['row'], p['col']] = p['neighbor_median_m']
            result = hz.compute_horizon(site['lat'], site['lon'], chain,
                min_km=.005, max_km=300., n_steps=8000, obs_height_m=2.)
            corrected = core.metrics(site, hz.horizon_record(site, result))
        finally:
            for row, col, value in saved: sampler.h[row, col] = value
    strongest = int(np.argmax(near_mask-far['mask']))
    native_patch = sampler.h[gr-5:gr+7, gc-5:gc+7]
    return dict(source=sampler.name, source_path=sampler.path.relative_to(ROOT).as_posix(),
        source_sha256=sha_file(sampler.path), nominal_resolution_m=sampler.res_m,
        local_ns_pixel_m=sampler.res_m,
        local_ew_pixel_m=float(sampler.res_m*np.cos(np.radians(site['lat']))),
        near_dominant_azimuth_bins=int(affected.sum()),
        near_dominant_distances_m=(np.quantile(distances[winners[affected]]*1000,[0,.5,1]).tolist() if affected.any() else []),
        maximum_near_over_far_deg=float(np.max(near_mask-far['mask'])),
        strongest_azimuth_deg=float(az[strongest]), supporting_native_pixels=pixels,
        positive_spike_candidates=len(candidates), despiked_near_metrics=corrected,
        diagnosis=('Candidate isolated positive pixel(s); replacement sensitivity is reported, but physical relief versus noise remains unverified.' if candidates else
            'No isolated positive spike under the stated heuristic in the supporting/observer pixels. Near-field obstruction is present in the interpolated SLDEM surface; physical accuracy is unverified.'),
        native_patch=dict(first_row=gr-5,first_col=gc-5,height_m=native_patch.tolist()))


def main():
    start = time.monotonic()
    products = original_labels()
    sites = {s['id']: s for s in json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))}
    rows = []
    with CoreMetrics(ROOT) as core:
        for sid in IDS:
            site = sites[sid]
            checks = [footprint(site, p) for p in products]
            if not all(c['entire_300m_disc_outside'] for c in checks):
                raise ValueError('A footprint intersects: read its original IMG pixels before reporting a reference')
            chain = rh.build_chain(site, ROOT/'data/raw', 300.)
            baseline = json.loads((ROOT/f'web/data/horizon/{sid}.json').read_text())
            params = {k:baseline['engine'][k] for k in ('min_km','max_km','n_steps')}
            old = hz.compute_horizon(site['lat'],site['lon'],chain,**params)
            old_record = hz.horizon_record(site,old)
            expected = json.loads((ROOT/f'web/data/metrics/{sid}.json').read_text())
            a = core.metrics(site,old_record)
            assert old_record['mask'] == baseline['mask']
            assert all(a[k]==expected[k] for k in METRICS)
            near = hz.compute_horizon(site['lat'],site['lon'],chain,min_km=.005,max_km=300.,n_steps=8000)
            b = core.metrics(site,hz.horizon_record(site,near))
            far = hz.compute_horizon(site['lat'],site['lon'],chain,min_km=.2,max_km=300.,n_steps=8000)
            control = core.metrics(site,hz.horizon_record(site,far))
            diagnostic = local_diagnostic(site,chain,far,near,core)
            row = dict(id=sid,lat=site['lat'],lon=site['lon'],ours_a=a,ours_b=b,
                step_only_control=control,step_only_differences={k:control[k]-a[k] for k in METRICS},
                pgda=dict(sun_frac=None,earth_frac=None,sun_300m_min=None,sun_300m_max=None,
                    earth_300m_min=None,earth_300m_max=None,closer=None,status='outside_raster_extent',checks=checks),
                terrain_diagnostic=diagnostic,baseline_horizon_sha256=sha_file(ROOT/f'web/data/horizon/{sid}.json'),
                baseline_metrics_sha256=sha_file(ROOT/f'web/data/metrics/{sid}.json'))
            rows.append(row)
            print(sid, 'sun_delta_pp',100*(b['sun_frac']-a['sun_frac']),
                'positive_spike_candidates',diagnostic['positive_spike_candidates'],flush=True)
    report=dict(rows=rows,pgda_products=products,elapsed_s=time.monotonic()-start,
        source_url=PGDA,baseline_files_modified=False,
        ephem_sha256=sha_file(ROOT/'web/data/ephem.bin'),core_sha256=sha_file(ROOT/'web/js/core.js'),
        script_sha256=sha_file(__file__),horizon_sha256=sha_file(ROOT/'pipeline/horizon.py'),
        method='Current production centre versus 5 m minimum distance/8000 steps; 200 m/8000 step-only control; native SLDEM pixel diagnostics. All use 2 m observer, 720 azimuths, curvature, actual hourly core.js 2026-2030.')
    (ROOT/'docs/near_field_check.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# Near-field terrain check — five nonpolar centres','',
        'No production horizon, metrics or raw DEM is changed. (a) is the current production method (200 m minimum ray distance, 4000 steps); (b) includes 5–200 m (5 m minimum, 8000 steps). Both use 720 azimuths, curvature, a 2 m observer and actual hourly core.js over 2026–2030. These alternatives do not enter Card 23 grids.','',
        '**These are not five 5 m DEM sites.** All five use SLDEM2015 at 512 pixels/degree (~59.23 m north–south, narrower east–west at higher latitude). A ray beginning at 5 m interpolates those existing pixels; it does not resolve new 5 m relief.','',
        '## Requested comparison','',
        'Entries show sun / Earth visibility percentages; PGDA neighbourhoods mean a geodesic radius of 300 m.','',
        '| Site | Ours (a), % | Ours (b), % | PGDA centre; ±300 m min/max | Closer |',
        '|---|---:|---:|---|---|']
    for row in rows:
        a,b=row['ours_a'],row['ours_b']
        lines.append(f"| {row['id']} | {100*a['sun_frac']:.4f} / {100*a['earth_frac']:.4f} | {100*b['sun_frac']:.4f} / {100*b['earth_frac']:.4f} | Sun and Earth: N/A — entire disc outside raster | Not determinable |")
    lines+=['','## Direct original-product footprint check','',
        f'[NASA PGDA product 69]({PGDA}) links polar AVGVISIB maps. We downloaded and parsed the **four original PDS labels** for the broadest north/south Sun/Earth products, rather than treating a missing sample as zero. Their 6420×6420 rasters have 240 m pixels. Although named 65N/65S, the square raster corners reach approximately 55.2° latitude; using only the advertised 65° cutoff would be incomplete.',
        'Every requested centre, and its entire 300 m disc, is outside **both** north and south raster rectangles. Projected row/column coordinates and conservative stereographic disc bounds are saved in `near_field_check.json`. No valid IMG address exists there, so no numerical PGDA centre or neighbourhood value can be read. We did not clamp, extrapolate or substitute a different location.','']
    for product in products:lines.append(f"- [{product['product']} original label]({product['label_url']}) (SHA256 in JSON).")
    lines+=['','Even at covered sites a physical accuracy comparison would need matching time windows (~18.6 years versus five years), observer heights and visibility definitions: the original Sun label counts any visible solar-disc part; our sunlit threshold is half the disc. PGDA Earth visibility accepts any visible part; ours uses the centre.','',
        '## Relief versus single-pixel noise','',
        'We traced the near-field maxima on the same 8000-step distance grid and inspected the native bilinear-support pixels plus the observer pixels. An isolated positive-spike **candidate** must exceed all eight neighbours and exceed their median by more than max(1 m, 3×1.4826×MAD). This is a diagnostic heuristic, not a calibrated DEM error threshold. Candidate pixels, when present, are replaced by their eight-neighbour median in memory and the full near-field horizon/observer are recomputed. Raw files remain untouched.','',
        '| Site | Near-field-dominant azimuth bins / 720 | Blocker distance min / median / max, m | Supporting + observer native pixels | Positive spike candidates | Interpretation |',
        '|---|---:|---:|---:|---:|---|']
    for row in rows:
        d=row['terrain_diagnostic'];dist=' / '.join(f'{v:.1f}' for v in d['near_dominant_distances_m'])
        lines.append(f"| {row['id']} | {d['near_dominant_azimuth_bins']} | {dist} | {len(d['supporting_native_pixels'])} | {d['positive_spike_candidates']} | {d['diagnosis']} |")
        if d['despiked_near_metrics'] is not None:
            delta=100*(d['despiked_near_metrics']['sun_frac']-row['ours_b']['sun_frac'])
            lines.append(f"\n{row['id']}: replacing flagged cells changes near-field sun fraction by {delta:+.4f} percentage points.\n")
    lines+=['','Native 12×12 pixel height patches and individual neighbour residuals are in the JSON. Multi-pixel support and absence of a flagged positive spike do **not** prove real relief: correlated DEM errors, observer-height interpolation errors, negative spikes and unresolved subpixel terrain remain possible. Independent local high-resolution elevation data would be needed to distinguish those cases. No 5 m DEM or PGDA accuracy claim is made.','',
        'The 200 m / 8000-step control isolates distance-grid density from near-field inclusion; its metric differences are recorded per site. These results support retaining current main baselines until the team decides on a consistent recalculation.','',
        'Reproduce: `python pipeline/near_field_check.py`; numerical evidence: `docs/near_field_check.json`. Terrain and code/ephemeris hashes are recorded there and in the existing dataset manifest.']
    (ROOT/'docs/near_field_check.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
