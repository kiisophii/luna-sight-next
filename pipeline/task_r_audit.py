"""Independent Task R audit. No production pipeline/web imports.

python pipeline/task_r_audit.py --kernels ../lunar-card8-jiyong/data/raw/kernels
python pipeline/task_r_audit.py --kernels ../lunar-card8-jiyong/data/raw/kernels --offline
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request

# A single CPU process and bounded numerical-library thread counts.
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
from skyfield.api import Loader, PlanetaryConstants
from skyfield.planetarylib import PlanetTopos
from skyfield.units import Angle, Distance
import skyfield
from task_r_sources import SOURCES

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/processed/task_r'
UTC = timezone.utc


def digest(data):
    return hashlib.sha256(data).hexdigest()


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('UTC offset required')
    return result.astimezone(UTC)


def iso(value):
    return value.isoformat().replace('+00:00', 'Z')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.partial')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


def fetch(url, offline=False):
    key = digest(url.encode())
    raw_path, meta_path = CACHE / (key + '.raw'), CACHE / (key + '.json')
    if raw_path.exists() and meta_path.exists():
        raw = raw_path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta['url'] != url or digest(raw) != meta['sha256']:
            raise ValueError('Cache identity/hash mismatch')
        return raw, meta
    if offline:
        raise FileNotFoundError('No cached response: ' + url)
    request = urllib.request.Request(url, headers={'User-Agent': 'Lunar-Task-R-Research/1.0'})
    CACHE.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read()
            meta = dict(url=url, resolved_url=response.url, sha256=digest(raw), bytes=len(raw),
                        retrieved_utc=iso(datetime.now(UTC)), content_type=response.headers.get('Content-Type'),transport='urllib TLS')
    except Exception as exc:
        # Windows curl trusts the OS certificate store; do not disable TLS
        # verification to work around Python's missing intermediary CA.
        if os.name != 'nt':
            raise
        target=CACHE/(key+'.curl.partial')
        completed=subprocess.run(['curl.exe','--silent','--show-error','--fail','--location','--max-time','25',
                                  '--output',str(target),'--write-out','%{url_effective}',url],
                                 capture_output=True,text=True,check=True)
        raw=target.read_bytes();target.unlink()
        meta=dict(url=url,resolved_url=completed.stdout,sha256=digest(raw),bytes=len(raw),
                  retrieved_utc=iso(datetime.now(UTC)),transport='curl TLS with OS certificate store',urllib_error=str(exc))
    partial = raw_path.with_suffix('.partial')
    partial.write_bytes(raw)
    partial.replace(raw_path)
    write_json(meta_path, meta)
    return raw, meta


def request_url(lat, lon, h0, dates):
    jd = [2440587.5 + t.timestamp()/86400 for t in dates]
    options = dict(format='json', COMMAND="'10'", EPHEM_TYPE="'OBSERVER'", CENTER="'coord@301'",
                   COORD_TYPE="'GEODETIC'", SITE_COORD=f"'{lon},{lat},{(h0+2)/1000}'",
                   TLIST="'" + ','.join(f'{j:.10f}' for j in jd) + "'", TLIST_TYPE="'JD'",
                   TIME_TYPE="'UT'", QUANTITIES="'4'", CSV_FORMAT="'YES'", EXTRA_PREC="'YES'",
                   APPARENT="'AIRLESS'", TIME_DIGITS="'FRACSEC'", CAL_FORMAT="'JD'", OBJ_DATA="'NO'")
    return 'https://ssd.jpl.nasa.gov/api/horizons.api?' + urllib.parse.urlencode(options)


def parse_horizons(raw, dates):
    payload = json.loads(raw)
    if payload.get('error'):
        raise ValueError(payload['error'])
    result = payload.get('result', '')
    for marker in ('MEAN_ME (high precision)', 'NO (AIRLESS)', '$$SOE', '$$EOE'):
        if marker not in result:
            raise ValueError('Missing Horizons marker: '+marker)
    body = result.split('$$SOE',1)[1].split('$$EOE',1)[0].strip()
    rows = list(csv.reader(io.StringIO(body)))
    if len(rows) != len(dates):
        raise ValueError('Wrong Horizons sample count')
    values = np.array([[float(r[0]), float(r[3]), float(r[4])] for r in rows])
    expected = np.array([2440587.5+t.timestamp()/86400 for t in dates])
    if not np.isfinite(values).all() or np.max(abs(values[:,0]-expected))*86400 > .1:
        raise ValueError('Nonfinite value or wrong Horizons epoch')
    return values[:,1:], payload.get('signature'), [line for line in result.splitlines() if 'source:' in line or 'Center radii' in line]


class IndependentSun:
    def __init__(self, kernels):
        self.kernels = kernels
        loader = Loader(str(kernels))
        self.ts = loader.timescale(builtin=True)
        self.eph = loader('de440s.bsp')
        constants = PlanetaryConstants()
        for name in ('moon_080317.tf', 'pck00008.tpc'):
            with (kernels/name).open('rb') as stream:
                constants.read_text(stream)
        self.binary = (kernels/'moon_pa_de421_1900-2050.bpc').open('rb')
        constants.read_binary(self.binary)
        self.frame = constants.build_frame_named('MOON_ME_DE421')

    def angles(self, lat, lon, h0, dates):
        point = PlanetTopos.from_latlon_distance(self.frame, Angle(degrees=lat), Angle(degrees=lon),
                                                Distance(km=1737.4+(h0+2)/1000))
        observer = self.eph['moon'] + point
        alt, az, _ = observer.at(self.ts.from_datetimes(dates)).observe(self.eph['sun']).apparent().altaz()
        return np.column_stack((az.degrees, alt.degrees))


def horizon_angle(mask, az):
    values = np.asarray(mask, dtype=float)
    phase = np.asarray(az) % 360 * len(values)/360
    lower = np.floor(phase).astype(int) % len(values)
    weight = phase-np.floor(phase)
    return (1-weight)*values[lower] + weight*values[(lower+1)%len(values)]


def first_set(angles, mask):
    # A symmetric solar disk is >=50% visible exactly when its centre >= mask.
    lit = angles[:,1] >= horizon_angle(mask, angles[:,0])
    indices = np.flatnonzero(lit[:-1] & ~lit[1:]) + 1
    return int(indices[0]) if len(indices) else None


def stats(values):
    values = [abs(float(x)) for x in values if x is not None]
    return dict(n=len(values), max_abs=float(max(values)) if values else None,
                median_abs=float(np.median(values)) if values else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernels', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    engine = IndependentSun(args.kernels)
    catalogue_path = ROOT/'web/data/sites.json'
    hindcast_path = ROOT/'web/data/hindcast.json'
    catalogue = json.loads(catalogue_path.read_text(encoding='utf-8'))
    hindcast = json.loads(hindcast_path.read_text(encoding='utf-8'))
    landed = {s['id']:s for s in catalogue if s['group'] not in ('artemis3_region','polar_peak','future','custom')}
    original = {r['id']:r for k in ('apollo_sun_elevation','robotic_sunset') for r in hindcast[k]}
    source_ids = {s['id'] for s in SOURCES}
    if source_ids != set(landed)|set(original) or len(source_ids) != len(SOURCES):
        raise ValueError('Source inventory does not cover every landed/hindcast ID exactly once')
    manifest = dict(inputs=[dict(path=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for p in (catalogue_path,hindcast_path,ROOT/'pipeline/task_r_sources.py',ROOT/'pipeline/task_r_audit.py')],
                    kernels=[dict(name=p.name,sha256=digest(p.read_bytes())) for p in sorted(args.kernels.iterdir()) if p.name in ('de440s.bsp','moon_080317.tf','pck00008.tpc','moon_pa_de421_1900-2050.bpc')],
                    kernel_base_url='https://naif.jpl.nasa.gov/pub/naif/generic_kernels/',
                    runtime=dict(skyfield=skyfield.__version__,numpy=np.__version__,
                                 timescale='Skyfield built-in; leap date and offset arrays hashed separately',
                                 leap_dates_sha256=digest(engine.ts.leap_dates.tobytes()),
                                 leap_offsets_sha256=digest(engine.ts.leap_offsets.tobytes())),sources=[], horizons=[])
    urls = {s[k] for s in SOURCES for k in ('coordinate_source','time_source','alternate_source') if k in s}
    urls |= {'https://ssd-api.jpl.nasa.gov/doc/horizons.html','https://rhodesmill.org/skyfield/planetary.html','https://www.nasa.gov/history/alsj-and-afj/'}
    for url in sorted(urls):
        try:
            _, meta = fetch(url,args.offline)
        except Exception as exc:
            meta = dict(url=url,error=str(exc),status='raw retrieval failed; manually browsed source retained')
        manifest['sources'].append(meta)
        print('source',url,meta.get('error','cached'),flush=True)

    def reference(lat,lon,h0,dates):
        raw, meta = fetch(request_url(lat,lon,h0,dates),args.offline)
        values, signature, model = parse_horizons(raw,dates)
        manifest['horizons'].append(dict(**meta,signature=signature,model=model))
        return values

    rows, sunsets, failures = [], [], []
    for source in SOURCES:
        sid = source['id']
        site = landed[sid]
        hzpath = ROOT/f'web/data/horizon/{sid}.json'
        hz = json.loads(hzpath.read_text()) if hzpath.exists() else None
        h0 = hz['h0_m'] if hz else 0
        if hz:
            manifest['inputs'].append(dict(path=str(hzpath.relative_to(ROOT)),sha256=digest(hzpath.read_bytes())))
        date = timestamp(source['landing_utc'])
        row = dict(**source, catalogue_lat=site['lat'],catalogue_lon=site['lon'],
                   coord_difference_deg=max(abs(site['lat']-source['lat']),abs(((site['lon']-source['lon']+180)%360)-180)),
                   h0_m=h0,height_status='existing terrain mask height' if hz else 'reference sphere; terrain unavailable',
                   stored_landing_elevation_status='no existing comparison',
                   source_time_status='unresolved source conflict' if sid=='LUNA24' else 'published precision retained')
        try:
            ref = reference(source['lat'],source['lon'],h0,[date])[0]
            direct = engine.angles(source['lat'],source['lon'],h0,[date])[0]
            row.update(horizons_sun_deg=float(ref[1]),independent_sun_deg=float(direct[1]),
                       independent_minus_horizons_deg=float(direct[1]-ref[1]))
            old = original.get(sid)
            row['stored_landing_elevation_status'] = 'no existing comparison'
            if old:
                row['stored_landing_utc'] = old['landing_utc']
                row['source_minus_stored_seconds'] = (date-timestamp(old['landing_utc'])).total_seconds()
                row['time_agreement_within_2min'] = abs(row['source_minus_stored_seconds']) <= 120
                row['exact_time_agreement'] = row['source_minus_stored_seconds'] == 0
            if old and 'ours_sun_el_deg_catalogue_point' in old:
                row['stored_landing_elevation_status']='compared'
                row['stored_sun_deg']=old['ours_sun_el_deg_catalogue_point']
                row['stored_minus_horizons_deg']=row['stored_sun_deg']-float(ref[1])
            if 'alsj_point' in source:
                alsj_ref=reference(*source['alsj_point'],h0,[date])[0,1]
                row['alsj_point_horizons_deg']=float(alsj_ref)
                row['alsj_report_minus_horizons_deg']=source['alsj_sun_deg']-float(alsj_ref)
                row['catalogue_point_minus_alsj_report_deg']=float(ref[1])-source['alsj_sun_deg']
            if 'alternate_utc' in source:
                alt=reference(source['lat'],source['lon'],h0,[timestamp(source['alternate_utc'])])[0,1]
                row['alternate_horizons_sun_deg']=float(alt)
                row['alternate_minus_primary_sun_deg']=float(alt-ref[1])
            row['ephemeris_pass']=abs(row['independent_minus_horizons_deg'])<=.05
        except Exception as exc:
            row['ephemeris_pass']=False
            row['error']=str(exc)
            failures.append(sid+': '+str(exc))
        rows.append(row)
        write_json(CACHE/'landing_progress.json',rows)
        print(sid,row.get('horizons_sun_deg'),row.get('independent_minus_horizons_deg'),row.get('error',''),flush=True)

    # Full first-sunset search at every minute across 30 days so brief
    # terrain-induced reversals cannot be silently skipped.
    for old in hindcast['robotic_sunset']:
        sid=old['id']; site=landed[sid]
        hz=json.loads((ROOT/f'web/data/horizon/{sid}.json').read_text())
        landing=timestamp(old['landing_utc'])
        # Match production's minute grid, which starts on the landing minute.
        dates=[landing+timedelta(minutes=i) for i in range(30*24*60+1)]
        angles=np.concatenate([engine.angles(site['lat'],site['lon'],hz['h0_m'],dates[i:i+2048]) for i in range(0,len(dates),2048)])
        edge=first_set(angles,hz['mask'])
        result=dict(id=sid,stored_sunset_utc=old['ours_first_sunset_utc'],
                    mask_source=f'web/data/horizon/{sid}.json',terrain_independently_verified=False,
                    operation_proxy_is_sunset_truth=False)
        try:
            if edge is None:
                raise ValueError('No first sunset in 30 days')
            around=dates[max(0,edge-3):edge+4]
            ref=reference(site['lat'],site['lon'],hz['h0_m'],around)
            ref_edge=first_set(ref,hz['mask'])
            if ref_edge is None:
                raise ValueError('Horizons does not bracket the independently found sunset')
            reference_time=around[ref_edge]
            result.update(independent_sunset_utc=iso(dates[edge]),horizons_sunset_utc=iso(reference_time),
                          stored_minus_horizons_minutes=(timestamp(old['ours_first_sunset_utc'])-reference_time).total_seconds()/60,
                          independent_minus_horizons_minutes=(dates[edge]-reference_time).total_seconds()/60,
                          independent_landing_sunlit=bool(angles[0,1]>=horizon_angle(hz['mask'],angles[0,0])))
            result['stored_landing_sunlit']=old['sunlit_at_landing']
            result['landing_sunlit_agrees']=result['stored_landing_sunlit']==result['independent_landing_sunlit']
            result['pass']=abs(result['stored_minus_horizons_minutes'])<=2
        except Exception as exc:
            result.update(error=str(exc),passed=False)
            failures.append(sid+' sunset: '+str(exc))
        sunsets.append(result)
        write_json(CACHE/'sunset_progress.json',sunsets)
        print('sunset',result,flush=True)
    summary=dict(landing_count=len(rows),stored_landing_elevation_count=sum(r['stored_landing_elevation_status']=='compared' for r in rows),
                 coordinate_difference_deg=stats(r['coord_difference_deg'] for r in rows),
                 coordinate_transcription_pass=all(r['coord_difference_deg']<1e-10 for r in rows),
                 source_raw_retrieval_failures=[m['url'] for m in manifest['sources'] if 'error' in m],
                 horizons_requests=len(manifest['horizons']),
                 independent_vs_horizons_deg=stats(r.get('independent_minus_horizons_deg') for r in rows),
                 stored_vs_horizons_deg=stats(r.get('stored_minus_horizons_deg') for r in rows),
                 alsj_same_point_deg=stats(r.get('alsj_report_minus_horizons_deg') for r in rows),
                 stored_sunset_vs_horizons_minutes=stats(r.get('stored_minus_horizons_minutes') for r in sunsets),
                 source_time_difference_seconds=stats(r.get('source_minus_stored_seconds') for r in rows),
                 source_time_disagreements=[r['id'] for r in rows if r.get('source_minus_stored_seconds',0)!=0],
                 unresolved_source_conflicts=['LUNA24'],ephemeris_threshold_deg=.05,sunset_threshold_min=2,
                 ephemeris_pass=all(r.get('ephemeris_pass',False) for r in rows),
                 stored_elevation_pass=all(abs(r.get('stored_minus_horizons_deg',0))<=.05 for r in rows),
                 sunset_pass=all(r.get('pass',False) for r in sunsets),errors=failures)
    summary['stored_landing_sunlit_pass']=all(r.get('landing_sunlit_agrees',False) for r in sunsets)
    report=dict(generated_utc=iso(datetime.now(UTC)),checker='Jiyong Sung (not hindcast producer)',summary=summary,
                definitions=dict(elevation='Airless apparent topocentric solar centre; 2 m above supplied terrain height; R=1737.4 km',
                                 independent='Standalone Skyfield direct observer + DE440s + MOON_ME_DE421; built-in historical timescale; no production imports',
                                 horizons='JPL Horizons observer table; coord@301, quantity 4, high precision MEAN_ME; response source records retained',
                                 terrain='Existing mask reused only for conditional event calculation; not independently validated here',
                                 missing='No historical NPZ found in local sibling checkouts; app ephem.bin starts 2026 and does not cover landings'),
                landings=rows,sunsets=sunsets)
    write_json(ROOT/'docs/task_r_audit.json',report)
    write_json(ROOT/'docs/task_r_manifest.json',manifest)
    with (ROOT/'docs/task_r_landings.csv').open('w',newline='',encoding='utf-8') as stream:
        fields=['id','landing_utc','lat','lon','h0_m','horizons_sun_deg','independent_sun_deg','independent_minus_horizons_deg','stored_sun_deg','stored_minus_horizons_deg','stored_landing_elevation_status','source_minus_stored_seconds','coordinate_source','time_source','note']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,indent=2))
    return 0 if summary['ephemeris_pass'] and summary['stored_elevation_pass'] and summary['sunset_pass'] and summary['coordinate_transcription_pass'] and summary['stored_landing_sunlit_pass'] and not failures else 1


if __name__=='__main__':
    raise SystemExit(main())
