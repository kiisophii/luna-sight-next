"""Separate five-site near-field experiment; never updates catalogue baselines."""
import argparse,json
from pathlib import Path
import numpy as np
import horizon as hz
import run_horizons as rh
from local_maps import CoreMetrics,sha_file

ROOT=Path(__file__).resolve().parents[1]
IDS=('APOLLO11','APOLLO12','LUNA20','CHANGE5','IM3_REINER_GAMMA')
METRICS=('sun_frac','earth_frac','both_frac','longest_dark_h')
PGDA='https://pgda.gsfc.nasa.gov/products/69'

def main():
    sites={s['id']:s for s in json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))}
    rows=[]
    with CoreMetrics(ROOT) as core:
        for sid in IDS:
            site=sites[sid];chain=rh.build_chain(site,ROOT/'data/raw',300.)
            existing=json.loads((ROOT/f'web/data/horizon/{sid}.json').read_text())
            baseline=json.loads((ROOT/f'web/data/metrics/{sid}.json').read_text())
            p=existing['engine'];params={k:p[k] for k in ['min_km','max_km','n_steps']}
            old=hz.horizon_record(site,hz.compute_horizon(site['lat'],site['lon'],chain,obs_height_m=2.,**params))
            oldmetrics=core.metrics(site,old)
            assert old['mask']==existing['mask']
            assert all(oldmetrics[k]==baseline[k] for k in METRICS)
            near=hz.horizon_record(site,hz.compute_horizon(site['lat'],site['lon'],chain,min_km=.005,max_km=300.,n_steps=8000,obs_height_m=2.))
            newmetrics=core.metrics(site,near)
            assert abs(site['lat'])<65
            rows.append(dict(id=sid,lat=site['lat'],lon=site['lon'],legacy_params=params,
                near_params=dict(min_km=.005,max_km=300.,n_steps=8000),legacy=oldmetrics,near=newmetrics,
                delta={k:newmetrics[k]-oldmetrics[k] for k in METRICS},
                pgda=dict(source_url=PGDA,status='outside_product_coverage',value=None,legacy_error=None,near_error=None,closer=None),
                legacy_horizon_sha256=sha_file(ROOT/f'web/data/horizon/{sid}.json'),legacy_metrics_sha256=sha_file(ROOT/f'web/data/metrics/{sid}.json')))
    report=dict(rows=rows,baseline_files_modified=False,ephem_sha256=sha_file(ROOT/'web/data/ephem.bin'),
        core_sha256=sha_file(ROOT/'web/js/core.js'),pgda_coverage='Published illumination/Earth products cover polar latitudes >=65N or <=65S; all five sites are outside.',
        caveats=['PGDA averages ~18.6 years, while this comparison uses 2026-2030.',
                 'PGDA Earth visibility accepts any visible disk portion; our metric uses Earth centre.',
                 '5 m is minimum ray distance, not DEM pixel resolution. These five sites use ~59 m SLDEM.',
                 'No conclusion about which method is closer to PGDA can be drawn for these coordinates.'])
    (ROOT/'docs/near_field_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# Five-site near-field sensitivity experiment','',
        'Catalogue horizons and metrics remain unchanged. This experiment compares independently recomputed legacy centres with a 5 m minimum ray-distance / 8000-step alternative, on the same DEM chain and hourly production core.js.','',
        '| Site | Legacy sun % | Near-field sun % | Change pp | Legacy / near longest dark h | PGDA sun value | Closer to PGDA |',
        '|---|---:|---:|---:|---:|---|---|']
    for r in rows:
        a,b=r['legacy'],r['near'];lines.append(f"| {r['id']} | {100*a['sun_frac']:.4f} | {100*b['sun_frac']:.4f} | {100*r['delta']['sun_frac']:+.4f} | {a['longest_dark_h']} / {b['longest_dark_h']} | N/A: outside coverage | Not determinable |")
    lines+=['','Earth visibility remains 100% at all five sites; both_frac equals sun_frac in both versions. Full metrics, parameters and baseline hashes are in `near_field_comparison.json`.','',
        f'NASA PGDA source: [Lunar Polar Illumination]({PGDA}). Published grids extend from 65 degrees latitude to each pole; all five coordinates above fall outside those products. Consequently neither version has a PGDA reference value or an error score here. Do not substitute a polar pixel or extrapolate a reference value.','',
        'Even in coverage, a controlled PGDA comparison must align the time window, observer height, spatial support and solar/Earth disk definitions. PGDA documentation describes ~18.6-year averages and any-part-of-Earth-disk visibility.','',
        'The test isolates inclusion of nearby terrain. SLDEM pixel spacing remains approximately 59 m; interpolating rays from 5 m does not create 5 m terrain accuracy. The team can review the method separately; these alternative values are not used in Card 23 uncertainty grids.','',
        'Reproduce: `python pipeline/compare_near_field.py`.']
    (ROOT/'docs/near_field_comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(rows),flush=True)
if __name__=='__main__':main()
