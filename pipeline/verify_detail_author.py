"""Author-side independent formulas for Z1/Z4; no producer numerical imports.

This additional AI session is not independent team-member verification.
"""
import base64
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'web/data'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def states(site, mask, ephem):
    lat, lon = np.radians([site['lat'], site['lon']])
    north = np.array([-np.sin(lat)*np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)])
    east = np.array([-np.sin(lon), np.cos(lon), 0.])
    up = np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
    origin = up * (1737.4 + (mask['h0_m'] + 2) / 1000)
    horizons = np.array(mask['mask'])
    result = []
    for col in (0, 3):
        vec = ephem[:, col:col+3] - origin
        e, n, u = vec @ east, vec @ north, vec @ up
        az = np.degrees(np.arctan2(e, n)) % 360
        el = np.degrees(np.arctan2(u, np.hypot(e, n)))
        idx = az / mask['az_step_deg']
        lo = np.floor(idx).astype(int) % len(horizons)
        weight = idx - np.floor(idx)
        h = horizons[lo]*(1-weight) + horizons[(lo+1) % len(horizons)]*weight
        if col == 0:
            y = np.clip((h-el)/.2666, -1, 1)
            fraction = (np.arccos(y) - y*np.sqrt(np.maximum(0, 1-y*y))) / np.pi
            result.append(fraction >= .5)
        else:
            result.append(el > h)
    return result


def stats(bits):
    segments, pos = [], 0
    for state, group in itertools.groupby(bits):
        length = sum(1 for _ in group)
        if state:
            segments.append((pos, pos+length))
        pos += length
    clipped = [dict(start_i=a, end_i=b, duration_h=b-a, clipped_start=a==0, clipped_end=b==len(bits))
               for a,b in segments if a==0 or b==len(bits)]
    sizes = [b-a for a,b in segments]
    complete = [b-a for a,b in segments if a>0 and b<len(bits)]
    return dict(count=len(sizes), total_h=sum(sizes), mean_h=sum(sizes)/len(sizes) if sizes else None,
                longest_h=max(sizes,default=0), complete_count=len(complete),
                complete_mean_h=sum(complete)/len(complete) if complete else None,
                complete_longest_h=max(complete,default=0), clipped_runs=clipped)


def unit(lat, lon):
    a,b=map(math.radians,(lat,lon))
    return np.array([math.cos(a)*math.cos(b),math.cos(a)*math.sin(b),math.sin(a)])


def vector_geodesic(a, b):
    v, w = unit(a['lat'],a['lon']), unit(b['lat'],b['lon'])
    distance = 1737400 * math.atan2(float(np.linalg.norm(np.cross(v,w))),float(v@w))
    lat,lon=map(math.radians,(a['lat'],a['lon']))
    east=np.array([-math.sin(lon),math.cos(lon),0.])
    north=np.array([-math.sin(lat)*math.cos(lon),-math.sin(lat)*math.sin(lon),math.cos(lat)])
    bearing=math.degrees(math.atan2(float(w@east),float(w@north))) % 360
    return distance,bearing


def main():
    start=time.perf_counter()
    sites=read(DATA/'sites.json')
    ephem=np.fromfile(DATA/'ephem.bin',dtype='<f4').reshape(-1,6).astype(float)
    stations=read(DATA/'korea/stations.json')['stations']
    station_bits={s['id']:np.unpackbits(np.frombuffer(base64.b64decode(s['bits_b64']),dtype='u1'),bitorder='little')[:len(ephem)] for s in stations}
    n_stations=sum(station_bits.values())
    rows=[]
    for site in sites:
        obj=read(DATA/f"detail/time_stats/{site['id']}.json")
        sun,earth=states(site,read(DATA/f"horizon/{site['id']}.json"),ephem)
        expected=dict(sunlit_h=int(sun.sum()),earth_visible_h=int(earth.sum()),both_h=int((sun&earth).sum()),
                      dark_runs=stats(~sun),no_earth_runs=stats(~earth),sunlit_runs=stats(sun),
                      station_link_h=dict(kdsa_h=int((earth & station_bits['KDSA'].astype(bool)).sum()),
                                          at_least_1_h=int((earth & (n_stations>=1)).sum()),
                                          at_least_2_h=int((earth & (n_stations>=2)).sum())))
        mismatch=[key for key,val in expected.items() if obj[key]!=val]
        rows.append(dict(id=site['id'],mismatched_fields=mismatch,pass_exact=not mismatch))
    assert all(r['pass_exact'] for r in rows), rows
    result=dict(verification_status='author_verification_only; different team member still required',
                z1=dict(sites=len(rows),all_fields_exact=True,rows=rows))
    hist=DATA/'detail/history.json'
    if hist.exists():
        obj=read(hist);missions=obj['missions'];hr=[]
        for row in obj['sites']:
            independently_sorted=sorted([(vector_geodesic(row,m)[0],m['id'],vector_geodesic(row,m)[1]) for m in missions if m['id']!=row['id']])[:3]
            assert [r['id'] for r in row['nearest']]==[r[1] for r in independently_sorted]
            for stored,(distance,id,bearing) in zip(row['nearest'],independently_sorted):
                diff=abs((stored['bearing_deg']-bearing+180)%360-180) if stored['bearing_deg'] is not None else None
                hr.append(dict(site=row['id'],destination=id,distance_diff_m=abs(stored['distance_m']-distance),bearing_diff_deg=diff))
        result['z4']=dict(pairs=len(hr),max_distance_diff_m=max(r['distance_diff_m'] for r in hr),
                          max_bearing_diff_deg=max(r['bearing_diff_deg'] or 0 for r in hr),rows=hr)
        assert result['z4']['max_distance_diff_m'] < .001
        assert result['z4']['max_bearing_diff_deg'] < 1e-7
    result['elapsed_s']=time.perf_counter()-start
    result['input_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n') if p.suffix!='.bin' else p.read_bytes()).hexdigest() for p in [DATA/'sites.json',DATA/'ephem.bin',DATA/'korea/stations.json']}
    (ROOT/'docs/detail_author_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='input_sha256'},indent=2)[:650])


if __name__=='__main__':
    assert stats([False]*4)['mean_h'] is None
    assert stats([True]*4)['clipped_runs']==[dict(start_i=0,end_i=4,duration_h=4,clipped_start=True,clipped_end=True)]
    assert abs(vector_geodesic(dict(lat=0,lon=179),dict(lat=0,lon=-179))[0]-1737400*math.pi/90)<1e-8
    main()
