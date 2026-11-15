"""Render every north-polar comparison and retain threshold failures."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    data=json.loads((ROOT/'docs/task_u_north_check.json').read_text())
    assert data['complete'] and data['point_count']==30,'Do not publish a partial run as complete'
    s=data['summary'];rows=data['rows']
    lines=['# Task U — north-polar custom terrain','',
           'Checker: **Jiyong Sung**; browser global terrain producer: Sua. Inputs: main `274e676`. Thirty synthetic points, seed `2026111503`, ten area-uniform points in each of 75–80, 80–85 and 85–90 degrees N. No production data, algorithm or accuracy badge changed.','',
           '## Result','',
           f"**{'PASS' if s['rms_criterion_pass'] and s['sun_criterion_pass'] else 'FAIL'}** against VALIDATION row 14: median horizon RMS ≤0.2° and every point |Sun difference| ≤2 percentage points. Median RMS is **{s['median_rms_deg']:.6f}°**, maximum RMS **{s['max_rms_deg']:.6f}°**; largest angular difference **{s['max_abs_angle_deg']:.6f}°**. Maximum |Sun difference| **{s['max_abs_sun_pp']:.6f} pp**, |Earth difference| **{s['max_abs_earth_pp']:.6f} pp**, |both| **{s['max_abs_both_pp']:.6f} pp**. These are sampled differences against another DEM chain, not measured physical errors or universal bounds.",'',
           'Keep the north-polar lower-accuracy/unvalidated badge. Passing agreement on identical tiles does not establish adequate terrain resolution. This PR supplies evidence for a later north-polar terrain improvement; it does not change the UI.','',
           '## What was compared','',
           '- System under test: actual Chrome `custom_horizon_worker.js` and `core.js`, with the current global 32 ppd near tiles (2×2 means of LDEM_64, approximately 948 m) to 150 km, LDEM_16 to 300 km; 200 m ray start, 4,001 distances, 720 azimuths. North points do not use the south-polar patches.',
           '- Independent reference: original [PGDA north-polar product 98](https://pgda.gsfc.nasa.gov/products/98). Nearest available 10 m (≥83 N), 20 m (80–83 N) or 30 m (75–80 N) to 3 km; 60 m to 60 km; 240 m to 200 km; original LDEM_64 through 300 km, with LDEM_16 only as a missing-data fallback. 5 m ray start and 8,001 logarithmic distances. Resolution gates are centred on each observer. Partial source footprints fall through to the next available source; no extrapolated or zero terrain.',
           '- Both use bilinear sampling, spherical curvature, 2 m observer, 720 azimuths, MOON_ME DE421 and R=1737400 m. Reference uses its own centre terrain height; this source-dependent observer elevation is included in the total difference.',
           '- Reference geometry and metrics import no producer modules. Source download alone reuses the HTTP GeoTIFF reader. Independent Python north-stereographic equations are tested against PROJ. The full ray maximum has no producer early-stop optimization.',
           '- Primary metric table uses every second production ephemeris hour, matching the earlier row-14 comparison cadence (2026–2030, 21,912 samples). The JSON also records all 43,824 hourly samples. Sun is the fraction of bins with ≥50% solar disk visible; Earth is centre strictly above terrain; both is their conjunction.',
           '- A second source-DEM control uses the browser\'s 200 m start and 4,001 distances. This controls ray sampling as a bundle; it does **not** isolate only <200 m relief because radial density also changes. Its remaining difference also includes DEM resolution, source selection and centre height.','',
           'This north-specific reference is not the south card-8 5 m chain and is not an absolute truth model. PGDA DEM noise, missing sub-pixel relief, source footprints, 0.5° azimuth spacing and time sampling remain limits. Thirty points cannot rule out worse unsampled terrain.','',
           '## All 30 points','',
           'Difference sign is browser − original-DEM reference. Angles compare full 720-bin masks. Percentages below are **percentage points**, not relative percent.','',
           '| Point | Lat, lon N/E | Near DEM m | RMS ° | Max angle ° | Sun pp | Earth pp | Both pp | Sun >2 pp? |','|---|---|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        d=r['metrics']['2h']['difference']
        lines.append(f"| {r['id']} | {r['lat']}, {r['lon']} | {r['source_metadata'][0]['resolution_m']} | {d['rms_deg']:.6f} | {d['max_abs_deg']:.6f} | {d['sun_diff_pp']:+.6f} | {d['earth_diff_pp']:+.6f} | {d['both_diff_pp']:+.6f} | {'FAIL' if abs(d['sun_diff_pp'])>2 else 'no'} |")
    lines += ['','## Latitude bands and matched-start control','',
              '| Band | Median RMS ° | Max |Sun| pp | Matched-start median RMS ° | Matched-start max |Sun| pp |','|---|---:|---:|---:|---:|']
    for band in ('75-80N','80-85N','85-90N'):
        bandrows=[r for r in rows if r['band']==band]
        d=[r['metrics']['2h']['difference'] for r in bandrows]
        c=[r['metrics']['2h']['matched_start_difference'] for r in bandrows]
        lines.append(f"| {band} | {np.median([x['rms_deg'] for x in d]):.6f} | {max(abs(x['sun_diff_pp']) for x in d):.6f} | {np.median([x['rms_deg'] for x in c]):.6f} | {max(abs(x['sun_diff_pp']) for x in c):.6f} |")
    controls=[r for r in rows if r['same_tile_control']]
    assert len(controls)==3
    coremax=max(abs(v) for r in rows for v in r['core_loop_diff_pp'].values())
    lines += ['','## Independent implementation controls','',
              f"At one preselected point per band (3 points), independently decoded **identical browser tiles** and full CPU rays reproduce all **2,160 rounded angles exactly**. Unrounded maximum difference is {max(r['same_tile_control']['max_abs_deg'] for r in controls):.9f}°. Sun/Earth/both differences are zero. The independent hourly metric loop versus actual browser core at all 30 points differs by at most {coremax:.12g} pp.",'',
              'The common O–W stricter flags (not row-14 acceptance) are retained in the JSON: '+f"{len(s['common_angle_exceedances'])}/30 have a bin difference >0.05°, {len(s['common_fraction_exceedances'])}/30 have any fraction difference >0.1 pp. No failing row is removed.",'',
              f"Browser elapsed: {data['browser_elapsed_s']:.2f} s. Sum of measured independent per-point calculations: {data['reference_elapsed_s']:.2f} s. These exclude original raster acquisition, cached-input hashing and report generation; they are not total end-to-end task time.",'',
              '## Reproduce and provenance','',
              '```powershell','python -u pipeline/task_u_fetch.py','python -u pipeline/task_u_check.py --mode browser','python -u pipeline/task_u_check.py --mode reference','python pipeline/task_u_report.py','python -m pytest pipeline/tests/test_task_u.py -q','```','',
              'Fetch is resumable by original HTTP blocks and source windows. Reference checkpoints are invalidated by checker, ephemeris, browser/index and source-window hashes; incomplete acquisition is explicitly reported as pending, never a full pass. Run reference mode again after acquisition completes. Sources and local window hashes, full source metadata, every 720-angle mask, hourly/2-hour metrics and controls are in [the JSON evidence](task_u_north_check.json). The copied formulas originate from Jiyong\'s earlier independent verifier, not the terrain producer.']
    # Pipes inside table labels must be escaped for Markdown.
    lines=[x.replace('Max |Sun|','Max abs Sun').replace('max |Sun|','max abs Sun') for x in lines]
    (ROOT/'docs/task_u_north_check.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
