"""Generate the Card23 300 m table from validated complete site files."""
import json
from pathlib import Path
from coordinate_uncertainty import ROOT,METRICS,validate,check_center

def main():
    sites=json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
    lines=['# Coordinate uncertainty — Card 23','',
        'Each of 33 catalogue locations has 121 geodesic nodes on an 11x11 grid, ±500 m in east/north offsets at 100 m spacing. Statistics use circular radii 100/300/500 m (5/29/81 nodes). They describe sampled spatial sensitivity, not statistical confidence intervals or actual coordinate-error probabilities.','',
        'Every site uses its unchanged main horizon method and terrain chain: polar sites already start rays at 5 m with 8000 steps; nonpolar sites retain 200 m / 4000 steps. All use 720 azimuths, lunar curvature, 2 m observer and 2026–2030 hourly production core.js. Every independently recomputed centre equals its existing metrics file.','',
        '## Within 300 m','',
        '| Site | Sunlit % range | Earth-visible % range | Both % range | Longest dark h range | Ground DEM m/px |',
        '|---|---:|---:|---:|---:|---:|']
    striking=[];centres=[]
    for site in sites:
        r=json.loads((ROOT/f"web/data/uncertainty/{site['id']}.json").read_text(encoding='utf-8'));validate(r)
        baseline=json.loads((ROOT/f"web/data/metrics/{site['id']}.json").read_text());check_center(r['points'][60],baseline)
        stats=r['radii']['300'];cells=[]
        for metric in METRICS:
            d=stats[metric];scale=1 if metric=='longest_dark_h' else 100
            cells.append(f"{d['min']*scale:.2f}–{d['max']*scale:.2f}" if scale==100 else f"{d['min']:.0f}–{d['max']:.0f}")
        res=sorted(set(p['ground_resolution_m'] for p in r['points'] if p['e_m']**2+p['n_m']**2<=300**2))
        lines.append('| '+site['id']+' | '+' | '.join(cells)+' | '+', '.join(f'{v:g}' for v in res)+' |')
        widths={m:100*(stats[m]['max']-stats[m]['min']) for m in METRICS[:3]}
        if max(widths.values())>10:striking.append(dict(id=site['id'],range_pp=widths))
        centres.append(site['id'])
    lines+=['','## Ranges exceeding 10 percentage points','']
    if striking:
        for r in striking:lines.append('- '+r['id']+': '+', '.join(f'{m} {v:.2f}pp' for m,v in r['range_pp'].items() if v>10))
    else:lines.append('No site exceeds 10 percentage points within 300 m in the computed grid.')
    lines+=['','## Interpretation and verification','',
        '- `sun_frac` counts hours with at least half the solar disk visible; Earth visibility uses its centre. These are geometric metrics, not delivered power or RF-link availability.',
        '- Fine-source coverage varies. Reported DEM resolution is the actual finest available source at each node, not vertical accuracy. Windows can fall back to coarser sources near their edges.',
        '- A 100 m node grid can miss smaller features. Min/max and quantiles describe these sampled nodes only.',
        '- The independent verifier uses full brute-force rays and a separate hourly metric loop on 5 random nodes each at polar, mid-latitude and equatorial sites; see `coordinate_uncertainty_check.json`.',
        '- The five-site alternative near-field experiment is separate: see `near_field_comparison.md`. Existing baseline files are unchanged; PGDA values are unavailable at those nonpolar coordinates.',
        '', 'Reproduce: `python pipeline/coordinate_uncertainty.py --workers 6`, then `python pipeline/coordinate_uncertainty_report.py` and `python pipeline/verify_coordinate_uncertainty.py`.','',
        'Sources: [PGDA terrain](https://pgda.gsfc.nasa.gov/products/90), [LOLA/SLDEM PDS](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/), [NAIF kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/). Per-output source/code hashes record provenance.']
    (ROOT/'docs/coordinate_uncertainty.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'docs/coordinate_uncertainty_summary.json').write_text(json.dumps(dict(site_count=len(sites),nodes=len(sites)*121,centres_exact=centres,over_10pp_within_300m=striking),indent=2)+'\n')
if __name__=='__main__':main()
