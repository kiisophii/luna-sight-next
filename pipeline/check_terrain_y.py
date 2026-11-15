"""Section 23 validation, independent of the numeric terrain producer."""
import hashlib
import json
import math
from pathlib import Path
import re


def number(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_terrain_y(data, sites, err):
    directory=Path(data)/'terrain'
    if not directory.exists():return
    def read(path):
        if not path.is_file():raise ValueError(f'missing file {path.name}')
        return json.loads(path.read_text(encoding='utf8'))
    try:
        index=read(directory/'index.json')
        assert index['schema_version']==1 and index['mock'] is False,'index version/mock'
        thresholds=index['thresholds_deg']
        assert thresholds and all(number(t) and 0<t<90 for t in thresholds),'invalid thresholds'
        assert sorted(set(thresholds))==thresholds,'thresholds must be unique and ascending'
        assert index['thresholds_label']=='reference_only','thresholds must be reference_only'
        entries=index['sites'];assert len(entries)==len(sites),'index catalogue count mismatch'
        assert {e['id'] for e in entries}==set(sites),'index catalogue IDs mismatch'
        assert {p.stem for p in directory.glob('*.json')}==set(sites)|{'index'},'missing or unexpected site files'
    except (KeyError,ValueError,TypeError,AssertionError) as exc:
        err('terrain/index.json',str(exc));return
    count=0
    for entry in entries:
        sid=entry['id'];where=f'terrain/{sid}.json'
        def require(condition,message):
            if not condition:err(where,message)
        try:
            assert entry['path']==sid+'.json','unexpected product path'
            obj=read(directory/entry['path']);site=sites[sid]
            content=json.dumps({k:v for k,v in obj.items() if k!='content_sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            require(obj.get('content_sha256')==hashlib.sha256(content).hexdigest(),'content hash mismatch')
            assert obj['id']==sid and obj['lat']==site['lat'] and obj['lon']==site['lon'],'catalogue coordinate mismatch'
            assert obj['schema_version']==1 and obj['mock'] is False and obj['frame']=='MOON_ME_DE421','version/frame/mock mismatch'
            require(obj['thresholds_label']=='reference_only','thresholds must be reference_only, not a safety claim')
            require(obj['thresholds_deg']==thresholds,'thresholds differ from index')
            require(obj['verification_status']=='author_checks_only_team_verification_pending','unexpected verification status')
            polar=site['lat']<=-75;kind='polar_detailed' if polar else 'coarse_relay_comparison'
            # nonpolar_detailed: SLDEM2015 lander-scale slope from pipeline/nonpolar_slope.py (|lat| < 60 only)
            fine_np=not polar and obj['kind']=='nonpolar_detailed' and abs(site['lat'])<60
            assert obj['kind']==entry['kind']==('nonpolar_detailed' if fine_np else kind),'product kind does not match catalogue latitude'
            inputs=obj['inputs']
            for key in ('producer_sha256','sites_sha256','relay_sha256','signature'):
                require(isinstance(inputs.get(key),str) and re.fullmatch('[0-9a-f]{64}',inputs[key]) is not None,f'invalid input {key}')
            assert isinstance(inputs['parameters'],dict),'missing input parameters'
            box=obj['relay_box'];relay_path=Path(data)/'relay'/(sid+'.json');relay=read(relay_path)
            assert box['source_path']==f'web/data/relay/{sid}.json','relay source path mismatch'
            require(box['source_sha256']==inputs['relay_sha256']==digest(relay_path),'relay source hash mismatch')
            c=relay['candidates'];centres=[i for i,(e,n) in enumerate(zip(c['e_m'],c['n_m'])) if e==n==0]
            assert len(centres)==1,'relay must have exactly one centre'
            i=centres[0]
            require(box['candidate_index']==i and box['e_m']==box['n_m']==0,'relay centre index/offset mismatch')
            require(box['box_m']==relay['params']['slope_box_m']==250,'relay box must be 250 m')
            require(box['slope_deg']==c['slope_deg'][i] and number(box['slope_deg']) and 0<=box['slope_deg']<=90,'relay stored slope mismatch')
            assert box['provenance'],'relay provenance missing'
            source=obj['source']
            if fine_np:
                res=source['resolution_m'];assert source['dem_name']=='SLDEM2015' and res==59.2 and entry['dem_resolution_m']==res,'unexpected SLDEM2015 resolution'
                assert all(k in source for k in ('url','window_path','window_sha256','download_sha256')),'missing source provenance'
                assert re.fullmatch('[0-9a-f]{64}',source['window_sha256']),'bad source window hash'
                require(obj['method']['slope_window_cells']==3 and obj['method']['reference_radius_m']==1737400,'slope method mismatch')
                require(number(obj['landing_slope_deg']) and 0<=obj['landing_slope_deg']<=90,'invalid landing slope')
                assert set(obj['slope_by_radius_m'])=={'100','500','1000'},'missing radius distributions'
                for radius,stats in obj['slope_by_radius_m'].items():
                    vals=[stats[k] for k in ('median_deg','p95_deg','max_deg')]
                    require(isinstance(stats['n'],int) and stats['n']>0 and all(number(v) and 0<=v<=90 for v in vals) and vals==sorted(vals),f'{radius}: invalid slope distribution')
                    values=[stats['flat_fraction'][format(t,'g')] for t in thresholds]
                    require(all(number(v) and 0<=v<=1 for v in values) and values==sorted(values),f'{radius}: invalid flat fraction')
                require(obj['roughness_within_500m'] is None,'59 m product must not claim 50 m roughness')
            elif not polar:
                require(source['label']=='coarse (SLDEM2015 59 m / LDEM_64)','coarse source label missing')
                require(entry['dem_resolution_m'] is None,'coarse index must not claim precise resolution')
                for key in ('method','landing_slope_deg','slope_by_radius_m','roughness_within_500m'):
                    require(obj[key] is None,f'coarse product must have null {key}')
            else:
                res=source['resolution_m'];assert res in (5,10,20) and entry['dem_resolution_m']==res,'unexpected native resolution'
                assert all(k in source for k in ('dem_name','url','window_path','window_sha256','metadata')),'missing source provenance'
                assert re.fullmatch('[0-9a-f]{64}',source['window_sha256']),'bad source window hash'
                method=obj['method']
                require(method['slope_window_cells']==3 and method['slope_center_span_projected_m']==2*res and method['slope_footprint_projected_m']==3*res,'slope baseline does not match 3 native cells')
                require(method['reference_radius_m']==1737400,'reference radius mismatch')
                require(method['roughness_window_width_ground_m']==50 and isinstance(method['roughness_window_cells'],int) and method['roughness_window_cells']>=3 and method['roughness_window_cells']%2==1,'roughness must use odd native window within nominal 50 m square')
                require(number(method['roughness_sample_center_span_ground_m']) and 0<method['roughness_sample_center_span_ground_m']<=50+1e-8,'roughness sample span outside window')
                require(number(obj['landing_slope_deg']) and 0<=obj['landing_slope_deg']<=90,'invalid landing slope')
                assert set(obj['slope_by_radius_m'])=={'100','500','1000'},'missing radius distributions'
                for radius,stats in obj['slope_by_radius_m'].items():
                    require(isinstance(stats['n'],int) and stats['n']>0,f'{radius}: invalid sample count')
                    vals=[stats[k] for k in ('median_deg','p95_deg','max_deg')]
                    require(all(number(v) and 0<=v<=90 for v in vals) and vals==sorted(vals),f'{radius}: invalid slope distribution')
                    require(number(stats['sampled_area_m2']) and stats['sampled_area_m2']>0,f'{radius}: invalid area')
                    fractions=stats['flat_fraction'];keys=[format(t,'g') for t in thresholds]
                    assert set(fractions)==set(keys),'flat fraction threshold keys mismatch'
                    values=[fractions[k] for k in keys]
                    require(all(number(v) and 0<=v<=1 for v in values) and values==sorted(values),f'{radius}: invalid flat fraction')
                r=obj['roughness_within_500m']
                require(isinstance(r['n'],int) and r['n']>0 and all(number(r[k]) and r[k]>=0 for k in ('median_m','p95_m')) and r['median_m']<=r['p95_m'],'invalid roughness distribution')
            count+=1
        except (KeyError,ValueError,TypeError,AssertionError,IndexError) as exc:
            err(where,str(exc))
    print(f'terrain: {count} site files checked')
