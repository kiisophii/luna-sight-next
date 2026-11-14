"""Reproducible Card 18 location and single-tower impact summaries."""
import argparse
import json
from pathlib import Path

import numpy as np
from local_maps import ROOT, IDS, METRICS, sha_file, validate_map, catalogue_ids


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def radius_summary(points, radius_km):
    selected=[p for p in points if np.hypot(p['e_m'],p['n_m'])<=radius_km*1000+1e-6]
    result=dict(radius_km=radius_km,n=len(selected))
    for metric in METRICS:
        a=np.array([p[metric] for p in selected])
        q1,q3=np.quantile(a,[.25,.75],method='linear')
        result[metric]=dict(min=float(a.min()),max=float(a.max()),q1=float(q1),q3=float(q3),iqr=float(q3-q1))
    return result


def separation_km(a,b):
    la,lb=np.radians([a['lat'],b['lat']]);dl=np.radians(b['lon']-a['lon'])
    h=np.sin((lb-la)/2)**2+np.cos(la)*np.cos(lb)*np.sin(dl/2)**2
    return float(2*1737.4*np.arcsin(np.sqrt(np.clip(h,0,1))))


def striking_pair(points, metric, adjacent=False):
    if adjacent:
        lookup={(p['e_m'],p['n_m']):p for p in points}
        pairs=[(p,lookup[q]) for p in points for q in [(p['e_m']+1000,p['n_m']),(p['e_m'],p['n_m']+1000)] if q in lookup]
        a,b=max(pairs,key=lambda pair:abs(pair[1][metric]-pair[0][metric]))
    else:
        a=min(points,key=lambda p:p[metric]);b=max(points,key=lambda p:p[metric])
        if a is b:
            b=next(p for p in points if p is not a)
    if a[metric]>b[metric]:a,b=b,a
    keep=['index','e_m','n_m','lat','lon','ground_resolution_m',metric]
    return dict(metric=metric,adjacent=adjacent,a={k:a[k] for k in keep},b={k:b[k] for k in keep},
        distance_km=separation_km(a,b),difference=float(b[metric]-a[metric]))


def segments(codes):
    codes=np.asarray(codes,dtype=np.uint8)
    starts=np.r_[0,np.flatnonzero(codes[1:]!=codes[:-1])+1]
    ends=np.r_[starts[1:],len(codes)]
    return [[int(a),int(b-a),int(codes[a])] for a,b in zip(starts,ends)]


def single_link(direct,tower,linked):
    direct=np.asarray(direct,dtype=bool);tower=np.asarray(tower,dtype=bool)
    via=tower & bool(linked)
    codes=np.where(direct,1,np.where(via,2,0))
    runs=segments(codes)
    return dict(link_frac=float((codes>0).mean()),longest_outage_h=max((n for _,n,c in runs if c==0),default=0),
                timeline_segments=runs)


def unpack_visibility(packed,n):
    """Card 13 uses NumPy's default MSB-first packing, unlike Korea's LSB bits."""
    return np.unpackbits(packed,bitorder='big')[:n].astype(bool)


def threshold_counts(rows):
    low=[r for r in rows if r['direct_frac']<.5]
    return dict(below_50_count=len(low),reached_50_by_height={str(h):sum(next(t for t in r['heights'] if t['height_m']==h)['link_frac']>=.5 for r in low) for h in [5,15,30,50]})


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])


def location_report(web,docs):
    records=[]
    sites={s['id']:s for s in read(web/'sites.json')}
    for sid in [s for s in catalogue_ids() if (web/'local'/f'{s}.json').exists()]:
        path=web/'local'/f'{sid}.json';record=read(path);validate_map(record)
        points=record['points']
        baseline=read(web/'metrics'/f'{sid}.json')
        centre=points[220]
        differences={k:centre[k]-baseline[k] for k in METRICS}
        records.append(dict(id=sid,lat=sites[sid]['lat'],group=('south_polar' if sites[sid]['lat']<=-75 else 'low_mid_latitude' if abs(sites[sid]['lat'])<60 else 'high_latitude'),local_sha256=sha_file(path),
            radial=[radius_summary(points,r) for r in [1,3,5,10]],
            pairs={m:dict(extreme=striking_pair(points,m),adjacent=striking_pair(points,m,True)) for m in METRICS},
            ground_resolution_counts={str(v):sum(p['ground_resolution_m']==v for p in points) for v in sorted({p['ground_resolution_m'] for p in points})},
            centre_metric_difference=differences,centre_metrics_sha256=sha_file(web/'metrics'/f'{sid}.json')))
    evidence=dict(method='Sampled nodes, linear quartiles; spherical separation. Adjacent pairs share a grid edge.',sites=records)
    (docs/'location_sensitivity.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    n=len(records)
    lines=['# Cards 18 + 20 — local location sensitivity (all catalogue sites)','Owners: Jiyong (card 18, six south-polar regions) and Dongju (card 20, the other 27 sites). Computed 2026-11-14.',
        f'{n} grids of 21×21 nodes, ±10 km east/north at 1 km spacing ({441*n:,} nodes). All results use the actual production core.js over 43,824 hourly samples, 2026–2030. Earth visibility is geometric direct-to-Earth visibility, not station availability or guaranteed radio service.',
        '![Six-region visibility maps (card 18)](location_sensitivity.png)',
        *polar_vs_equatorial(records),
        'Plot: `python pipeline/plot_local_maps.py`. Each square represents a sampled node; all regions share each metric\'s colour scale.',
        '## Nearby contrasts useful for the Impact story',
        'These pairs are adjacent grid nodes, approximately 1 km apart. Selection maximises the difference within each sampled region; it is not a representative average or an uncertainty bound. Coordinates and all source hashes are retained in location_sensitivity.json.']
    rows=[]
    for r in records:
        for metric in METRICS[:3]:
            p=r['pairs'][metric]['adjacent'];a,b=p['a'],p['b']
            rows.append([r['id'],metric,f"{p['distance_km']:.3f}",f"{100*a[metric]:.2f}% → {100*b[metric]:.2f}%",f"{100*p['difference']:.2f}",f"({a['e_m']/1000:g},{a['n_m']/1000:g}) → ({b['e_m']/1000:g},{b['n_m']/1000:g})",f"{a['ground_resolution_m']:g}/{b['ground_resolution_m']:g}"])
    lines.append(table(['Region','Metric','Separation km','Values','Difference pp','East/north offsets km','Ground DEM m (A/B)'],rows))
    best_region=max(records,key=lambda r:r['pairs']['both_frac']['adjacent']['difference'])
    p=best_region['pairs']['both_frac']['adjacent']
    lines.append(f"**Measured example:** at {best_region['id']}, two sampled locations {p['distance_km']:.3f} km apart have simultaneous Sun/Earth visibility of {100*p['a']['both_frac']:.2f}% and {100*p['b']['both_frac']:.2f}% ({100*p['difference']:.2f} percentage points). This illustrates why comparing nearby terrain is useful; it does not establish a safe landing site.")
    lines+=['## Radial distributions','Circular radius from the catalogue centre, not a square crop. Counts are 5/29/81/317 nodes at 1/3/5/10 km. Q1/Q3 use linear interpolation; IQR=Q3−Q1. Fraction statistics are displayed in percent (IQR in percentage points). Darkness statistics are hours.']
    for metric in METRICS:
        rows=[];scale=1 if metric=='longest_dark_h' else 100
        for r in records:
            for radius in r['radial']:
                s=radius[metric]
                rows.append([r['id'],radius['radius_km'],radius['n']]+[f"{scale*s[k]:.2f}" for k in ['min','max','q1','q3','iqr']])
        lines+=['### '+metric,table(['Region','Radius km','Nodes','Min','Max','Q1','Q3','IQR'],rows)]
    rows=[]
    for r in records:
        for metric in METRICS:
            p=r['pairs'][metric]['extreme'];scale=1 if metric=='longest_dark_h' else 100
            rows.append([r['id'],metric,f"{p['distance_km']:.3f}",f"{scale*p['a'][metric]:.2f}",f"{scale*p['b'][metric]:.2f}",p['a']['index'],p['b']['index']])
    lines+=['## Full-square extremes','These are extremes across the full square, whose corners extend 14.14 km from the centre. Their separation is reported explicitly; they must not be presented as 1 km neighbours.',table(['Region','Metric','Distance km','Min','Max','Node A','Node B'],rows),
        '## Resolution, validation and limits',
        table(['Region','Ground source resolution: node count','Maximum centre fraction difference pp','Centre dark-run difference h'],[[r['id'],str(r['ground_resolution_counts']),f"{100*max(abs(r['centre_metric_difference'][k]) for k in METRICS[:3]):.6f}",r['centre_metric_difference']['longest_dark_h']] for r in records]),
        'Storage windows were expanded while keeping the same observer-centred 3/25/25/60/60/200 km gates. Original 5 m source coverage can still end within a region; the fallback resolution is disclosed rather than extrapolated. Grid spacing is not DEM resolution. A 1 km grid can miss smaller-scale features. Radial distributions reflect location variability, not prediction error. A low-resolution display is not interchangeable with a fine-resolution analysis.',
        'Independent verification: `python pipeline/verify_card18_local.py` → `docs/card18_validation.json`, five uniformly selected nodes using a fixed seed, no production geometry imports; fractions must match within 1 pp. This tests implementation against the same DEM, not physical terrain truth. The new Shackleton point retains the Card 15 unverified precise datum alignment.',
        card20_validation_line(docs),
        'Sources: [PGDA LOLA](https://pgda.gsfc.nasa.gov/products/90), [SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [LOLA global terrain](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/), production `web/data/ephem.bin` and `web/js/core.js`. Exact hashes: [machine-readable evidence](location_sensitivity.json).',
        'Reproduce: `python -I pipeline/local_fetch27.py` (card 20 terrain) and the card 18 fetch for the first six; then `python pipeline/local_maps.py --jobs 12`; `python pipeline/local_impact.py --locations`. No partial map is published.']
    (docs/'location_sensitivity.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    return evidence


def card20_validation_line(docs):
    path=docs/'card20_validation.json'
    if not path.exists():
        return 'Card 20 independent verification: not run yet (`python pipeline/verify_card20_local.py`).'
    v=read(path);worst=max(abs(p['comparison'][k]['difference_pp']) for p in v['points'] for k in METRICS[:3])
    return (f"Card 20 independent verification: `python pipeline/verify_card20_local.py` → `docs/card20_validation.json`, "
            f"{len(v['points'])} random nodes from {', '.join(v['sites'])} (south-polar, mid-latitude, equatorial), brute-force 720×8,001 rays "
            f"with the independent card 13 DEM reader and an independent NumPy Sun/Earth loop: largest fraction difference {worst:.3f} pp "
            f"(criterion 1 pp), {'all passed' if v['passed'] else 'NOT all passed'}.")


def polar_vs_equatorial(records):
    """Short comparison generated from the numbers only (card 20)."""
    groups={'south_polar':'South-polar (lat ≤ −75°)','low_mid_latitude':'Low/mid latitude (|lat| < 60°)','high_latitude':'Other (Chandrayaan-3, 69° S)'}
    rows=[];med={}
    for g,label in groups.items():
        rs=[r for r in records if r['group']==g]
        if not rs:continue
        iqr_sun=[100*next(x for x in r['radial'] if x['radius_km']==10)['sun_frac']['iqr'] for r in rs]
        rng_both=[100*(next(x for x in r['radial'] if x['radius_km']==10)['both_frac']['max']-next(x for x in r['radial'] if x['radius_km']==10)['both_frac']['min']) for r in rs]
        adj_both=[100*r['pairs']['both_frac']['adjacent']['difference'] for r in rs]
        adj_sun=[100*r['pairs']['sun_frac']['adjacent']['difference'] for r in rs]
        med[g]=dict(iqr_sun=float(np.median(iqr_sun)),adj_both=float(np.median(adj_both)),adj_sun=float(np.median(adj_sun)),rng_both=float(np.median(rng_both)),n=len(rs),
                    max_adj_both=max(adj_both),max_site=rs[int(np.argmax(adj_both))]['id'])
        rows.append([label,len(rs),f"{np.median(iqr_sun):.2f}",f"{np.median(rng_both):.2f}",f"{np.median(adj_sun):.2f}",f"{np.median(adj_both):.2f}",f"{max(adj_both):.2f} ({rs[int(np.argmax(adj_both))]['id']})"])
    out=['## South pole vs the rest (card 20)',
         'Medians over the sites in each group, within the 10 km circle. Adjacent = two grid nodes 1 km apart.',
         table(['Group','Sites','Sunlight IQR pp','Both: max−min pp','Largest 1 km sunlight jump pp (median)','Largest 1 km both jump pp (median)','Largest 1 km both jump pp (max, site)'],rows)]
    if 'south_polar' in med and 'low_mid_latitude' in med:
        p,e=med['south_polar'],med['low_mid_latitude']
        out.append(f"**From the numbers:** moving the landing point by just 1 km changes simultaneous Sun + Earth visibility by up to {p['adj_both']:.1f} percentage points at a typical south-polar site (median of {p['n']} sites; largest {p['max_adj_both']:.1f} pp at {p['max_site']}), but only {e['adj_both']:.1f} pp at a typical low/mid-latitude site (median of {e['n']} sites). Within 10 km the sunlight spread (IQR) is {p['iqr_sun']:.1f} pp near the pole versus {e['iqr_sun']:.1f} pp elsewhere: at the poles the exact spot decides the result, away from them the date does.")
    return out


def direct_bits(record):
    n=record['window']['n'];bits=np.zeros(n,dtype=bool);cursor=0
    for start,length,code in record['networks'][0]['timeline']['segments']:
        if start!=cursor or length<=0 or code not in [0,1,2]:raise ValueError('Invalid relay timeline')
        bits[start:start+length]=code==1;cursor+=length
    if cursor!=n:raise ValueError('Incomplete relay timeline')
    return bits


def relay_report(web,work,docs):
    rows=[];sources=[]
    for site in read(web/'sites.json'):
        path=web/'relay'/f"{site['id']}.json";r=read(path)
        if (r['lat'],r['lon'])!=(site['lat'],site['lon']):raise ValueError('Stale relay coordinate')
        direct=direct_bits(r)
        if abs(direct.mean()-r['lander']['earth_frac'])>5.1e-5:raise ValueError('Inconsistent relay fraction')
        sources.append(dict(id=site['id'],relay_sha256=sha_file(path)))
        if direct.mean()>=.5:continue
        cache=work/site['id'];key=read(cache/'key.json')
        if (key['inputs']!=r['input_identity'] or key['v']!=r['params']['engine_version']
                or key['lat']!=r['lat'] or key['lon']!=r['lon'] or key['heights_m']!=r['params']['heights_m']):
            raise ValueError('Stale relay checkpoint: '+site['id'])
        done=np.load(cache/'done.npy',mmap_mode='r');visibility=np.load(cache/'vis.npy',mmap_mode='r')
        if not done.all() or visibility.shape!=(r['candidates']['n'],4,(len(direct)+7)//8):raise ValueError('Incomplete relay checkpoint')
        row=dict(id=site['id'],direct_frac=float(direct.mean()),direct_longest_outage_h=single_link(direct,direct,False)['longest_outage_h'],heights=[],
                 relay_sha256=sha_file(path),visibility_sha256=sha_file(cache/'vis.npy'),cache_key_sha256=sha_file(cache/'key.json'))
        for j,tower in enumerate(r['best']):
            visible=unpack_visibility(visibility[tower['idx'],j],len(direct))
            one=single_link(direct,visible,tower['link_to_lander'])
            if abs(one['link_frac']-tower['link_frac'])>5.1e-5:raise ValueError('Best-tower fraction differs from cache')
            row['heights'].append(dict(height_m=tower['height_m'],tower_idx=tower['idx'],
                tower_e_m=tower['e_m'],tower_n_m=tower['n_m'],tower_sun_frac=tower['sun_frac'],
                tower_longest_dark_h=tower['longest_dark_h'],**one))
        rows.append(row)
    evidence=dict(window=dict(start='2026-01-01T00:00:00Z',step_h=1,n=43824),catalogue_size=len(sources),
        counts=threshold_counts(rows),six_local_regions_counts=threshold_counts([r for r in rows if r['id'] in IDS]),
        sources=sources,sites=rows,definition='Single selected tower plus direct visibility; longest consecutive none run. No other network towers included.')
    (docs/'relay_impact.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    lines=['# Card 18 — measured relay impact','Owner: Jiyong. Card 13 real-terrain results, 2026–2030.',
        'The denominator is all catalogue sites with exact hourly direct Earth visibility <50%. At each height, count sites whose direct OR selected single-tower link is ≥50%. This threshold is a communication-screening example, not a mission requirement or a guarantee of RF service.',
        table(['Scope','Direct <50% sites','Reached ≥50%: 5 m','15 m','30 m','50 m'],
              [[label,c['below_50_count']]+[c['reached_50_by_height'][str(h)] for h in [5,15,30,50]] for label,c in [('All 33 catalogue sites',evidence['counts']),('Six local-grid regions',evidence['six_local_regions_counts'])]]),
        '## Single-tower availability and remaining outage',
        'Each height cell is availability % / longest remaining outage h. Counts and outages use exact saved hourly visibility bits; percentage rounding is display only. Greedy three-tower network outages are not substituted for single-tower outages.']
    detail=[]
    for r in rows:
        detail.append([r['id'],f"{100*r['direct_frac']:.2f}% / {r['direct_longest_outage_h']} h"]+
            [f"{100*t['link_frac']:.2f}% / {t['longest_outage_h']} h" for t in r['heights']])
    lines.append(table(['Site','Direct % / outage h','5 m','15 m','30 m','50 m'],detail))
    lines+=['## Interpretation and limits',
        'A geometric improvement does not supply power: the selected tower’s sunlight and longest darkness are separately retained in relay_impact.json. No battery, throughput, interference or Earth-station schedule is modelled. The chosen site and tower heights do not prove structural feasibility. Some low-direct sites are on the far side; nearby surface towers may not see Earth either.',
        'Evidence includes exact single-tower timeline segments [start hour,length hours,code], with codes 0 none, 1 direct, 2 via selected tower. The report can be audited without treating a three-tower network as one tower. Source JSON and visibility-cache hashes are included.',
        'Reproduce: `python pipeline/local_impact.py --relay` with matching Card 13 visibility checkpoints. [Machine-readable evidence](relay_impact.json), [Card 13 method and sources](card13_relay_report.md).']
    (docs/'relay_impact.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    return evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--locations',action='store_true');parser.add_argument('--relay',action='store_true')
    args=parser.parse_args();both=not(args.locations or args.relay)
    if args.locations or both:location_report(ROOT/'web/data',ROOT/'docs')
    if args.relay or both:relay_report(ROOT/'web/data',ROOT/'data/processed/relay',ROOT/'docs')


if __name__=='__main__':main()
