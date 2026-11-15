"""Independent full station-window, KST-day and lunar-link verification (task C)."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse
import atexit
import ctypes
import base64
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import re
import time
import numpy as np
import skyfield
from skyfield.api import Loader,wgs84

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'data/processed/task_c'
DATA=ROOT/'web/data'
START=datetime(2026,1,1,tzinfo=timezone.utc)
STOP=datetime(2031,1,1,tzinfo=timezone.utc)
END=(STOP-START).total_seconds()
N=43824
KST=timezone(timedelta(hours=9))
KDSA_URL='https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf'
DSN_URL='https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(obj,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8');temp.replace(p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unpack(s,n):return np.unpackbits(np.frombuffer(base64.b64decode(s),dtype=np.uint8),bitorder='little')[:n].astype(bool)
def pack(b):return base64.b64encode(np.packbits(b,bitorder='little').tobytes()).decode('ascii')

def source_stations():
    source=WORK/'sources/kdsa01.tf';text=source.read_text(encoding='ascii')
    match=re.search(r'KDSA01_LATLON\s*=\s*\(\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)',text)
    lat,lon,height=map(float,match.groups())
    stations=[dict(id='KDSA',lat=lat,lon=lon,height_m=height*1000,source_url=KDSA_URL)]
    # Independently transcribed from DSN 301 Rev P Table 5, page 16.
    for sid,la,lo,h in [('DSN_GOLDSTONE',(35,25,33.24312),(243,6,37.66244),1001.390),
                         ('DSN_MADRID',(40,25,52.35510),(355,45,7.16924),864.816),
                         ('DSN_CANBERRA',(-35,24,8.72724),(148,58,52.56231),688.867)]:
        latitude=np.sign(la[0])*(abs(la[0])+la[1]/60+la[2]/3600)
        longitude=(lo[0]+lo[1]/60+lo[2]/3600+180)%360-180
        stations.append(dict(id=sid,lat=float(latitude),lon=longitude,height_m=h,source_url=DSN_URL))
    stored={s['id']:s for s in read(DATA/'korea/stations.json')['stations']}
    for s in stations:
        assert abs(s['lat']-stored[s['id']]['lat'])<=5.1e-9 and abs(s['lon']-stored[s['id']]['lon'])<=5.1e-9
        assert abs(s['height_m']-stored[s['id']]['height_m'])<1e-9
    return stations

def bisect_roots(fn,left,right,left_above,tolerance=.04):
    left,right=np.asarray(left).copy(),np.asarray(right).copy()
    while np.max(right-left,initial=0)>tolerance:
        mid=(left+right)/2;same=(fn(mid)>=0)==left_above
        left=np.where(same,mid,left);right=np.where(same,right,mid)
    return (left+right)/2

def peaks(fn,left,right):
    # Ternary search over each independently bracketed local maximum.
    left,right=np.asarray(left).copy(),np.asarray(right).copy()
    for _ in range(28):
        a=(2*left+right)/3;b=(left+2*right)/3;choose_right=fn(a)<fn(b)
        left=np.where(choose_right,a,left);right=np.where(choose_right,right,b)
    t=(left+right)/2;return t,fn(t)

def daily_rows(windows):
    days={}
    for a,b,peak in windows:
        first=(START+timedelta(seconds=float(a))).astimezone(KST)
        last=(START+timedelta(seconds=float(b))).astimezone(KST)
        midnight=first.replace(hour=0,minute=0,second=0,microsecond=0)
        while midnight<last:
            nxt=midnight+timedelta(days=1);lo=max(first,midnight);hi=min(last,nxt)
            if lo<hi:days.setdefault(midnight.date().isoformat(),[]).append([lo.strftime('%H:%M'),'24:00' if hi==nxt else hi.strftime('%H:%M'),peak])
            midnight=nxt
    return days

def months():
    d=START
    while d<STOP:
        nxt=datetime(d.year+(d.month==12),d.month%12+1,1,tzinfo=timezone.utc)
        yield d,(d-START).total_seconds(),(nxt-START).total_seconds()
        d=nxt

def station_check(args):
    st,kernel_dir,common=args;sid=st['id'];begin=time.time()
    identity=dict(**common,station=st,windows_sha256=sha(DATA/'korea'/f'windows_{sid.lower()}.json'));fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    folder=WORK/sid;folder.mkdir(exist_ok=True)
    finished=folder/'result.json'
    if finished.exists():
        saved=read(finished)
        if saved['fingerprint']==fingerprint:return saved
    ld=Loader(kernel_dir,verbose=False);ts=ld.timescale(builtin=True);e=ld('de440s.bsp')
    observer=e['earth']+wgs84.latlon(st['lat'],st['lon'],elevation_m=st['height_m'])
    def alt(seconds):
        seconds=np.atleast_1d(seconds);values=[]
        for first in range(0,len(seconds),4096):
            t=ts.utc(2026,1,1,0,0,seconds[first:first+4096])
            values.append(observer.at(t).observe(e['moon']).apparent().altaz()[0].degrees)
        return np.concatenate(values)
    chunks=[]
    for mi,(date,a,b) in enumerate(months()):
        path=folder/f'{date:%Y%m}.npz';values=None
        if path.exists():
            with np.load(path,allow_pickle=False) as z:
                if str(z['fingerprint'])==fingerprint:values=z['altitude']
        grid=np.arange(a,b+1,60.)
        if values is None:
            values=alt(grid);tmp=path.with_suffix('.tmp.npz')
            np.savez_compressed(tmp,altitude=values,fingerprint=fingerprint);tmp.replace(path)
        assert len(values)==len(grid) and np.isfinite(values).all()
        chunks.append(values[:-1] if b<END else values)
        if (mi+1)%12==0:print(sid,'minute-grid months',mi+1,'/60','seconds',round(time.time()-begin,1),flush=True)
    values=np.concatenate(chunks);assert len(values)==N*60+1
    above=values>=10;cross=np.flatnonzero(above[1:]!=above[:-1])
    edges=bisect_roots(lambda x:alt(x)-10,cross*60.,(cross+1)*60.,above[cross])
    rising=above[cross+1];starts=list(edges[rising]);ends=list(edges[~rising])
    if above[0]:starts.insert(0,0.)
    if above[-1]:ends.append(END)
    assert len(starts)==len(ends)
    pi=np.flatnonzero((values[1:-1]>values[:-2])&(values[1:-1]>=values[2:]))+1
    pt,pv=peaks(alt,(pi-1)*60.,(pi+1)*60.)
    windows=[];clipped_without_peak=[]
    for wi,(a,b) in enumerate(zip(starts,ends)):
        inside=pv[(pt>=a)&(pt<=b)]
        if not len(inside):
            clipped_without_peak.append(wi);peak=None
        else:peak=round(float(inside.max()),2)
        windows.append([float(a),float(b),peak])
    hourly=above[::60][:-1];assert len(hourly)==N
    stored=next(s for s in read(DATA/'korea/stations.json')['stations'] if s['id']==sid)
    old=read(DATA/'korea'/f'windows_{sid.lower()}.json')['windows']
    old_seconds=[[(datetime.fromisoformat(v.replace('Z','+00:00'))-START).total_seconds() for v in w[:2]] for w in old]
    comparisons=[];unmatched=[]
    # Match by temporal overlap rather than assuming equal counts/index alignment.
    matched=set()
    for i,w in enumerate(windows):
        candidates=[j for j,o in enumerate(old_seconds) if min(w[1],o[1])>max(w[0],o[0])]
        if len(candidates)!=1:unmatched.append(dict(computed_index=i,overlap_matches=candidates));continue
        j=candidates[0];matched.add(j)
        comparisons.append(dict(index=i,stored_index=j,rise_diff_s=w[0]-old_seconds[j][0],set_diff_s=w[1]-old_seconds[j][1],
            peak_diff_deg=None if w[2] is None or not np.isfinite(old[j][2]) else w[2]-old[j][2]))
    bit_mismatches=np.flatnonzero(hourly!=unpack(stored['bits_b64'],N)).tolist()
    result=dict(station=sid,identity=identity,fingerprint=fingerprint,minute_samples=len(values),complete=True,
                windows=windows,window_count=len(windows),stored_window_count=len(old),comparisons=comparisons,
                unmatched_computed=unmatched,unmatched_stored=[j for j in range(len(old)) if j not in matched],
                clipped_without_interior_peak=clipped_without_peak,bits_b64=pack(hourly),hourly_mismatches=bit_mismatches,
                max_edge_diff_s=max(max(abs(c['rise_diff_s']),abs(c['set_diff_s'])) for c in comparisons),
                minimum_interior_peak_deg=float(pv.min()),elapsed_s=time.time()-begin)
    write(finished,result);print('STATION COMPLETE',sid,'windows',len(windows),'max edge seconds',result['max_edge_diff_s'],'hour bits',len(bit_mismatches),flush=True)
    e.close();return result

def earth_bits(site,h,eph):
    la,lo=np.radians([site['lat'],site['lon']]);up=np.array([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)])
    east=np.array([-np.sin(lo),np.cos(lo),0]);north=np.cross(up,east)
    ray=eph[:,3:]-(1737.4+(h['h0_m']+2)/1000)*up
    el=np.degrees(np.arctan2(ray@up,np.hypot(ray@east,ray@north)))
    az=np.degrees(np.arctan2(ray@east,ray@north))%360;pos=az/h['az_step_deg'];i=np.floor(pos).astype(int)%len(h['mask']);f=pos-np.floor(pos)
    mask=np.array(h['mask']);return el>mask[i]*(1-f)+mask[(i+1)%len(mask)]*f

def resources():
    if os.name!='nt':return
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    atexit.register(lambda:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
    class Info(ctypes.Structure):
        _fields_=[('mask',ctypes.c_size_t),('relationship',ctypes.c_ulong),('data',ctypes.c_byte*16)]
    k=ctypes.windll.kernel32;size=ctypes.c_ulong();k.GetLogicalProcessorInformation(None,ctypes.byref(size))
    buf=ctypes.create_string_buffer(size.value)
    if not k.GetLogicalProcessorInformation(buf,ctypes.byref(size)):raise ctypes.WinError()
    info=ctypes.cast(buf,ctypes.POINTER(Info));cores=[info[i].mask for i in range(size.value//ctypes.sizeof(Info)) if info[i].relationship==0]
    mask=0
    for c in cores[:max(1,len(cores)-2)]:mask|=c
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(ctypes.c_void_p(-1),mask):raise ctypes.WinError()
    print('Reserved two physical CPU cores; affinity',hex(mask),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kernel-dir',required=True);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    WORK.mkdir(parents=True,exist_ok=True);resources()
    if os.name=='nt':
        import msvcrt
        lock=(WORK/'runner.lock').open('a+b');lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);atexit.register(lock.close)
    stations=source_stations();started=time.time()
    app=read(WORK/'browser_reference.json')
    if not app.get('inputs'):raise ValueError('Run task_c_browser.mjs to generate a fingerprinted app reference')
    for name,expected in app['inputs'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Stale browser reference: '+name)
    common=dict(kernel_sha256=sha(Path(a.kernel_dir)/'de440s.bsp'),skyfield_version=skyfield.__version__,
                code_sha256=sha(Path(__file__)),stations_sha256=sha(DATA/'korea/stations.json'),
                kdsa_source_sha256=sha(WORK/'sources/kdsa01.tf'),dsn_source_sha256=sha(WORK/'sources/301P.pdf'))
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(station_check,(s,a.kernel_dir,common)) for s in stations];results=[]
        for f in as_completed(futures):results.append(f.result());write(WORK/'stations_progress.json',dict(complete=len(results)==4,stations=results))
    results.sort(key=lambda s:[x['id'] for x in stations].index(s['station']))
    kdsa=next(s for s in results if s['station']=='KDSA');daily=daily_rows(kdsa['windows']);old_daily=read(DATA/'korea/kdsa_daily_kst.json')['days']
    daily_diff=[dict(day=d,computed=daily.get(d),stored=old_daily.get(d)) for d in sorted(set(daily)|set(old_daily)) if daily.get(d)!=old_daily.get(d)]
    bits={s['station']:unpack(s['bits_b64'],N) for s in results}
    old_table={s['id']:s for s in read(ROOT/'docs/korea_links_check.json')['sites']}
    eph=np.fromfile(DATA/'ephem.bin',dtype='<f4').reshape(N,6).astype(float);site_rows=[]
    input_hashes={str(p.relative_to(ROOT)):sha(p) for p in [DATA/'ephem.bin',DATA/'ephem.json',DATA/'sites.json',DATA/'korea/kdsa_daily_kst.json',ROOT/'web/js/core.js',ROOT/'web/js/diff_data.js',ROOT/'web/js/korea.js']}
    input_hashes.update(app['inputs'])
    for p in [WORK/'browser_reference.json',ROOT/'docs/korea_links_check.json']:
        input_hashes[str(p.relative_to(ROOT))]=sha(p)
    for site in read(DATA/'sites.json'):
        sid=site['id'];p=DATA/'horizon'/f'{sid}.json';input_hashes[str(p.relative_to(ROOT))]=sha(p);h=read(p);ev=earth_bits(site,h,eph)
        browser=app['sites'][sid];station_comparisons={}
        for st in stations:
            key=st['id'];link=ev&bits[key];expected=unpack(browser['by_station'][key]['bits_b64'],N)
            station_comparisons[key]=dict(hours=int(link.sum()),browser_hours=browser['by_station'][key]['hours'],
                diff_h=int(link.sum())-browser['by_station'][key]['hours'],mismatched_hour_indices=np.flatnonzero(link!=expected).tolist(),bits_b64=pack(link))
        dsn=bits['DSN_GOLDSTONE']|bits['DSN_MADRID']|bits['DSN_CANBERRA']
        totals=dict(hours=N,earth=int(ev.sum()),kdsa=int((ev&bits['KDSA']).sum()),dsn=int((ev&dsn).sum()))
        historical={key:totals[key]-old_table[sid][key+'_h'] for key in ('earth','kdsa','dsn')}
        site_rows.append(dict(id=sid,stations=station_comparisons,totals=totals,app_totals=browser['app_totals'],
                              totals_equal_app=totals==browser['app_totals'],historical_totals_diff=historical,
                              earth_bit_mismatches=np.flatnonzero(ev!=unpack(browser['earth_bits_b64'],N)).tolist()))
    for p in (DATA/'korea').glob('windows_*.json'):input_hashes[str(p.relative_to(ROOT))]=sha(p)
    report=dict(complete=True,runtime_s=time.time()-started,inputs=input_hashes,station_results=results,
        daily=dict(computed_dates=len(daily),stored_dates=len(old_daily),computed_rows=sum(map(len,daily.values())),
                   stored_rows=sum(map(len,old_daily.values())),mismatches=daily_diff,computed=daily),
        sites=site_rows,json_validity=app['json_validity'])
    write(ROOT/'docs/task_c_check.json',report)
    print('COMPLETE C',len(site_rows),'sites','daily mismatches',len(daily_diff),'seconds',round(report['runtime_s'],1),flush=True)

if __name__=='__main__':main()
