"""Optional detail-product contracts; called by check_contract.py."""
import hashlib
import json
import math
from pathlib import Path


def validate_time_stats(obj, site):
    require(obj['format'] == 'detail-time-stats-v1' and obj['complete'] is True and obj['mock'] is False, 'Invalid time-stat format or incomplete result')
    require(obj['lat'] == site['lat'] and obj['lon'] == site['lon'], 'Time-stat coordinates differ from catalogue')
    require(obj['window'] == dict(start_utc='2026-01-01T00:00:00Z',end_utc='2031-01-01T00:00:00Z',step_h=1,n=43824), 'Incorrect time-stat window')
    n = 43824
    for key in ('sunlit_h','earth_visible_h','both_h'):
        require(type(obj[key]) is int and 0 <= obj[key] <= n, 'Hours must be bounded integers')
    require(obj['both_h'] <= min(obj['sunlit_h'],obj['earth_visible_h']), 'Both hours exceed Sun/Earth hours')
    for key, total in [('dark_runs',n-obj['sunlit_h']),('no_earth_runs',n-obj['earth_visible_h']),('sunlit_runs',obj['sunlit_h'])]:
        r = obj[key]
        require(r['total_h'] == total, 'Run total differs from hourly total')
        for field in ('count','complete_count','longest_h','complete_longest_h'):
            require(type(r[field]) is int and 0 <= r[field] <= n, 'Invalid run count/duration')
        require(r['count'] <= total and r['complete_count'] <= r['count'] and r['complete_longest_h'] <= r['longest_h'] <= total, 'Inconsistent run counts/lengths')
        require(r['count'] > 0 if total > 0 else r['count'] == 0, 'Run count disagrees with total')
        require(r['mean_h'] == (total/r['count'] if r['count'] else None), 'Incorrect mean or no-run null')
        clipped = r['clipped_runs']
        require(len(clipped) <= 2 and r['complete_count'] + len(clipped) == r['count'], 'Incorrect clipped run count')
        endpoints = set()
        for c in clipped:
            a,b=c['start_i'],c['end_i']
            require(type(a) is int and type(b) is int and 0 <= a < b <= n and c['duration_h'] == b-a, 'Invalid clipped interval')
            require(type(c['clipped_start']) is bool and type(c['clipped_end']) is bool and c['clipped_start'] == (a==0) and c['clipped_end'] == (b==n) and (a==0 or b==n), 'Incorrect clipping flag')
            for edge,flag in [('start',c['clipped_start']),('end',c['clipped_end'])]:
                if flag:
                    require(edge not in endpoints, 'Duplicate clipped window edge')
                    endpoints.add(edge)
            require(b-a <= r['longest_h'], 'Clipped run exceeds longest run')
        complete_total = total-sum(c['duration_h'] for c in clipped)
        require(complete_total >= 0 and r['complete_mean_h'] == (complete_total/r['complete_count'] if r['complete_count'] else None), 'Incorrect complete-only mean')
        require((r['complete_count'] == 0) == (complete_total == 0), 'Complete count disagrees with complete total')
        if not r['complete_count']:
            require(r['complete_longest_h'] == 0, 'No complete run must have zero longest')
    station=obj['station_link_h']
    require(all(type(v) is int and 0 <= v <= n for v in station.values()), 'Invalid station hours')
    require(station['kdsa_h'] <= station['at_least_1_h'] <= obj['earth_visible_h'] and station['at_least_2_h'] <= station['at_least_1_h'], 'Station link bounds inconsistent')
    require(obj['parity'] == dict(metrics_exact=True,windows_exact=True), 'Existing metric/window parity is required')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate_psr(obj, site):
    require(obj['schema_version']==1 and obj['mock'] is False, 'Invalid PSR schema/mock flag')
    require(obj['lat']==site['lat'] and obj['lon']==site['lon'], 'PSR coordinates differ from catalogue')
    require(obj['warning']=='PSR \u2260 confirmed ice.', 'PSR ice caveat required')
    src=obj['source']
    require(src['url']=='https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.TIF' and src['resolution_m']==20 and src['reference_radius_m']==1737400, 'Incorrect native PSR source/resolution/radius')
    require(src['frame']=='MOON_ME_DE421' and src['nodata']=='nan' and src['codes']=={'0':'not PSR','1':'PSR','NaN':'unknown/no-data'}, 'PSR class/frame metadata inconsistent')
    inside=obj['inside_psr']
    require(inside is None or type(inside) is bool, 'PSR membership must be boolean or unknown')
    require(obj['site_class']==(None if inside is None else int(inside)), 'PSR class/membership disagree')
    search=obj['search'];radius=search['radius_m'];bound=search['unsearched_or_nodata_lower_bound_m']
    require(number(radius) and 100<=radius<=50000 and number(bound) and bound>=0, 'Invalid PSR search radius/bound')
    nodata=search['nodata_lower_bound_m'];edge=search['window_edge_lower_bound_m']
    require(number(edge) and edge>=0 and (nodata is None or number(nodata) and nodata>=0), 'Invalid missing-data bounds')
    require(bound==min(edge,nodata if nodata is not None else edge), 'PSR combined missing-data bound inconsistent')
    require(type(search['complete_within_radius']) is bool and search['complete_within_radius']==(bound>=radius), 'False PSR coverage claim')
    require(type(search['nodata_pixels']) is int and type(search['pixels']) is int and 0<=search['nodata_pixels']<=search['pixels'], 'Invalid PSR coverage counts')
    center,boundary=obj['nearest_pixel_center'],obj['nearest_boundary']
    for point in (center,boundary):
        if point is None:
            continue
        require(number(point['lat']) and -90<=point['lat']<=90 and number(point['lon']) and -180<=point['lon']<=180, 'Invalid PSR nearest coordinates')
        require(number(point['distance_m']) and 0<=point['distance_m']<=radius, 'PSR candidate beyond search radius')
        require(type(point['nearest_guaranteed']) is bool and point['nearest_guaranteed']==(point['distance_m']<bound), 'False PSR nearest guarantee')
        if abs(site['lat'])==90 or point['distance_m']<1e-8:
            require(point['bearing_deg'] is None, 'Singular PSR bearing must be null')
        else:
            require(number(point['bearing_deg']) and 0<=point['bearing_deg']<360, 'Invalid PSR bearing')
    candidate=center if center is not None else boundary
    expected_status=('found' if candidate['nearest_guaranteed'] else 'incomplete_coverage') if candidate is not None else ('none_within_radius' if search['complete_within_radius'] else 'incomplete_coverage')
    require(obj['status']==expected_status, 'PSR status disagrees with candidates/coverage')
    expected_area=None if inside is None else (0 if inside else boundary['distance_m'] if boundary else None)
    require(obj['distance_to_psr_area_m']==expected_area, 'PSR area distance inconsistent with membership/boundary')
    expected_lower=radius if search['complete_within_radius'] and center is None and inside is False and boundary is None else None
    require(obj['distance_lower_bound_m']==expected_lower, 'Unsupported PSR absence/lower bound')


def validate_history(obj, sites):
    require(obj['schema_version'] == 1 and obj['product'] == 'nearest_historical_landings', 'Unknown history schema')
    require(obj['frame']=='MOON_ME_DE421' and obj['reference_utc']=='2026-11-15T00:00:00Z', 'Incorrect history frame/reference date')
    provenance=obj['provenance']
    required_paths={'web/data/sites.json','docs/task_r_landings.csv','docs/detail_z4_sources.json','pipeline/detail_history.py'}
    require(provenance['sha256_normalization']=='CRLF_to_LF' and len(provenance['inputs'])==4 and {p['path'] for p in provenance['inputs']}==required_paths, 'Missing or unexpected history provenance inputs')
    require(obj['mock'] is False and obj['radius_m'] == 1737400 and obj['nearest_count'] == 3, 'History must use real data, lunar radius and three neighbours')
    missions = obj['missions']
    ids = [m['id'] for m in missions]
    require(len(ids) == len(set(ids)) == obj['mission_count'] == 18, 'History requires 18 distinct actual landers')
    for m in missions:
        require(number(m['lat']) and -90 <= m['lat'] <= 90 and number(m['lon']) and -180 <= m['lon'] <= 180, 'Invalid mission coordinates')
        require(m['official_source_url'].startswith('https://'), 'Official mission source URL required')
    rows = obj['sites']
    require(len(rows) == obj['site_count'] == len(sites) and {r['id'] for r in rows} == set(sites), 'History catalogue coverage incomplete')
    for row in rows:
        site = sites[row['id']]
        require(row['lat'] == site['lat'] and row['lon'] == site['lon'], 'History query coordinates differ from catalogue')
        neighbours = row['nearest']
        near_ids = [r['id'] for r in neighbours]
        require(len(near_ids) == len(set(near_ids)) == 3 and row['id'] not in near_ids and set(near_ids) <= set(ids), 'History destinations must be distinct real missions and exclude self')
        distances = []
        for rank, n in enumerate(neighbours, 1):
            require(n['rank'] == rank and number(n['distance_m']) and 0 <= n['distance_m'] <= math.pi * 1737400, 'Invalid history rank or distance')
            distances.append(n['distance_m'])
            if n['bearing_status'] == 'defined':
                require(number(n['bearing_deg']) and 0 <= n['bearing_deg'] < 360, 'Invalid history bearing')
            else:
                require(n['bearing_status'] in {'coincident', 'antipodal', 'origin_pole'} and n['bearing_deg'] is None, 'Undefined bearing must have an explicit reason and null value')
            require(n['official_source_url'].startswith('https://'), 'History neighbour source URL required')
        require(distances == sorted(distances), 'History distances must be sorted')


def normalized_hash(path):
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b'\r\n', b'\n') if path.suffix != '.bin' else raw).hexdigest()


def check_detail(data, sites, err, warn):
    """Validate optional products only when present; require complete indexed sets."""
    # --data may point at a disposable candidate dataset, as in existing contract
    # tests. Producers/docs live beside this checker, not beside arbitrary data.
    root = Path(__file__).resolve().parents[1]
    directory = data / 'detail/time_stats'
    if directory.exists():
        try:
            index = json.loads((directory/'index.json').read_text(encoding='utf8'))
            require(index['complete'] is True and index['mock'] is False, 'Incomplete time-stat index')
            require(len(index['ids']) == len(sites) and set(index['ids']) == set(index['sha256']) == set(sites), 'Time-stat index coverage differs from catalogue')
            require({p.stem for p in directory.glob('*.json') if p.name!='index.json'} == set(sites), 'Time-stat file coverage differs from catalogue')
            shared_inputs = dict(core_sha256=data.parent/'js/core.js', ephem_sha256=data/'ephem.bin',
                                 ephem_meta_sha256=data/'ephem.json', sites_sha256=data/'sites.json',
                                 stations_sha256=data/'korea/stations.json', producer_sha256=root/'pipeline/detail_time_stats.mjs',
                                 helper_sha256=root/'pipeline/cache_metrics.mjs')
            shared_hashes = {key:normalized_hash(path) for key,path in shared_inputs.items()}
            for sid,site in sites.items():
                path=directory/(sid+'.json')
                obj=json.loads(path.read_text(encoding='utf8'))
                require(obj['id']==sid and obj['window']==index['window'], 'Time-stat ID/window mismatch')
                validate_time_stats(obj,site)
                require(normalized_hash(path)==index['sha256'][sid], 'Time-stat output hash changed: '+sid)
                inputs={**shared_hashes, **{kind+'_sha256':normalized_hash(data/f'{kind}/{sid}.json') for kind in ('horizon','metrics','windows')}}
                require(obj['source']==inputs, 'Time-stat input provenance changed: '+sid)
                metric=json.loads((data/f'metrics/{sid}.json').read_text(encoding='utf8'))
                for key,field in [('sun_frac','sunlit_h'),('earth_frac','earth_visible_h'),('both_frac','both_h')]:
                    require(obj[field]/43824==metric[key], 'Time-stat metric mismatch: '+sid)
                require(obj['dark_runs']['longest_h']==metric['longest_dark_h'], 'Time-stat longest-dark mismatch: '+sid)
            print(f'detail/time_stats: {len(sites)} records checked')
        except (ValueError, KeyError, TypeError, OSError) as exc:
            err('detail/time_stats',str(exc))
    history=data/'detail/history.json'
    if history.exists():
        try:
            obj=json.loads(history.read_text(encoding='utf8'))
            validate_history(obj,sites)
            for item in obj['provenance']['inputs']:
                source_path=data/'sites.json' if item['path']=='web/data/sites.json' else root/item['path']
                require(normalized_hash(source_path)==item['sha256'], 'History input changed: '+item['path'])
            import csv
            originals={r['id']:r for r in csv.DictReader((root/'docs/task_r_landings.csv').read_text(encoding='utf8').splitlines())}
            missions={m['id']:m for m in obj['missions']}
            sources=json.loads((root/'docs/detail_z4_sources.json').read_text(encoding='utf8'))['missions']
            require(set(missions)==set(originals), 'History mission pool differs from actual landing CSV')
            for sid,m in missions.items():
                require(sid in sites and sites[sid]['group'] not in {'future','custom','artemis3_region','polar_peak'}, 'Non-lander in history pool')
                require(m['lat']==float(originals[sid]['lat']) and m['lon']==float(originals[sid]['lon']) and m['landing_utc']==originals[sid]['landing_utc'], 'History differs from landing CSV')
                require(m['landing_utc']<=obj['reference_utc'], 'Future landing in history pool')
                require(m['official_source_url']==sources[sid]['url'] and m['official_source_agency']==sources[sid]['agency'], 'History official source differs from evidence')
            for row in obj['sites']:
                require(all(n['official_source_url']==missions[n['id']]['official_source_url'] for n in row['nearest']), 'History source URL mismatch')
            print(f'detail/history: {len(sites)} queries, {len(missions)} actual landers checked')
        except (ValueError, KeyError, TypeError, OSError) as exc:
            err('detail/history',str(exc))
    directory=data/'detail/psr'
    if directory.exists():
        try:
            index=json.loads((directory/'index.json').read_text(encoding='utf8'))
            polar={sid:s for sid,s in sites.items() if s['lat']<=-75}
            require(index['schema_version']==1 and index['count']==len(index['sites'])==len(polar)==16 and index['mock'] is False, 'Incomplete PSR index')
            require({e['id'] for e in index['sites']}==set(polar) and {p.stem for p in directory.glob('*.json') if p.name!='index.json'}==set(polar), 'PSR catalogue/file coverage mismatch')
            script_hash=normalized_hash(root/'pipeline/detail_psr.py')
            fetch_hash=normalized_hash(root/'pipeline/fetch_polar.py')
            signatures=[]
            for entry in index['sites']:
                sid=entry['id'];path=directory/(sid+'.json')
                require(entry['file']==sid+'.json' and entry['sha256']==normalized_hash(path), 'PSR output hash/path changed: '+sid)
                obj=json.loads(path.read_text(encoding='utf8'))
                require(obj['id']==sid and obj['status']==entry['status'], 'PSR ID/status mismatch')
                validate_psr(obj,polar[sid])
                require(obj['provenance']['script_sha256']==script_hash, 'PSR producer changed')
                identity=dict(site={k:obj[k] for k in ('id','lat','lon')},radius_m=obj['search']['radius_m'],source=obj['source'],script_sha256=script_hash,fetch_polar_sha256=fetch_hash)
                signature=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                require(signature==obj['input_signature'], 'PSR input signature differs')
                signatures.append(signature)
            require(hashlib.sha256(json.dumps(signatures,sort_keys=True,separators=(',',':')).encode()).hexdigest()==index['input_signature'], 'PSR index signature differs')
            print(f'detail/psr: {len(polar)} native 20 m records checked')
        except (ValueError, KeyError, TypeError, OSError) as exc:
            err('detail/psr',str(exc))
