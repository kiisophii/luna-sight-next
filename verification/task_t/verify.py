import numpy as np
from PIL import Image
import pathlib,hashlib,json,subprocess,csv,datetime
P=pathlib.Path;out=P('docs/task_t_independent');out.mkdir(parents=True,exist_ok=True);cache=P('task_t_cache');cache.mkdir(exist_ok=True)
m=json.loads(P('target/docs/task_t/MANIFEST.json').read_text());rows=[];hashes=[]
def get(url,p):
 if not p.exists():subprocess.run(['curl','-fL','--retry','3','-o',str(p),url],check=True)
 return p
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for f in m['files']:
 p=get('https://github.com/kiisophii/lunar-landing-site-navigator/releases/download/task-t-gmaps-ppd8-float32-v1/'+f['name'],cache/f['name'])
 hashes.append(dict(file=f['name'],actual=sha(p),expected=f['sha256']))
assert all(x['actual']==x['expected'] for x in hashes)
rng=np.random.default_rng(15112026);xy=np.column_stack([rng.integers(0,2048,1000),rng.integers(0,4096,1000)])
for field in ['sun','earth','both']:
 a=np.load(cache/(field+'.npy'),mmap_mode='r');png=np.asarray(Image.open('target/web/data/gmaps/'+field+'_values.png'))
 for y,x in xy:
  yy=np.clip((y+.5)*1440/2048-.5,0,1439);xx=np.clip((x+.5)*2880/4096-.5,0,2879);r=int(yy);c=int(xx);fy=yy-r;fx=xx-c
  v=float((1-fy)*((1-fx)*a[r,c]+fx*a[r,min(c+1,2879)])+fy*((1-fx)*a[min(r+1,1439),c]+fx*a[min(r+1,1439),min(c+1,2879)]))
  mine=float(png[y,x])/250;d=(mine-v)*100
  rows.append(dict(kind='png',field=field,row=int(y),col=int(x),stored=v,mine=mine,delta_pp=d,pass_=abs(d)<=.20001))
dems=[]
for d in m['computation']['dems']:
 p=get(d['url'],cache/d['file']);assert sha(p)==d['sha256_local']
 ppd=64 if '64' in d['name'] else 16;dems.append((np.memmap(p,dtype='<f4',mode='r',shape=(180*ppd,360*ppd)),ppd))
def height(lat,lon,k):
 a,p=dems[k];y=np.clip((90-lat)*p-.5,0,a.shape[0]-1);x=(lon%360)*p-.5;r=np.minimum(np.floor(y).astype(int),a.shape[0]-2);c=np.floor(x).astype(int);fy=y-r;fx=x-c;c%=a.shape[1];c1=(c+1)%a.shape[1]
 return 1000*((1-fy)*((1-fx)*a[r,c]+fx*a[r,c1])+fy*((1-fx)*a[r+1,c]+fx*a[r+1,c1]))
R=1737400.;res64=np.pi*R/180/64;res16=np.pi*R/180/16;ds=[];s=res64/2
while s<=300000+1e-6:ds.append(s);s+=max(res64 if s<=150000 else res16,.01*s)
theta=np.array(ds)/R;az=np.arange(360)*np.pi/180;eph=np.fromfile('target/web/data/ephem.bin',dtype='<f4').reshape(-1,6)[::2].astype(float)*1000
cells=np.column_stack([rng.integers(0,1440,10),rng.integers(0,2880,10)])
for r,c in cells:
 lat=90-(r+.5)/8;lon=-180+(c+.5)/8;la,lo=np.radians([lat,lon]);up=np.array([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)]);east=np.array([-np.sin(lo),np.cos(lo),0]);north=np.cross(up,east)
 h0=float(height(lat,lon,0))
 if np.isnan(h0):h0=float(height(lat,lon,1))
 direction=np.cos(az)[:,None]*north+np.sin(az)[:,None]*east;pos=up[None,None,:]*np.cos(theta)[None,:,None]+direction[:,None,:]*np.sin(theta)[None,:,None]
 plat=np.degrees(np.arcsin(np.clip(pos[:,:,2],-1,1)));plon=np.degrees(np.arctan2(pos[:,:,1],pos[:,:,0]));hh=height(plat,plon,0);far=height(plat,plon,1);hh=np.where((np.array(ds)[None,:]>150000)|np.isnan(hh),far,hh)
 mask=np.nanmax(np.arctan2((R+hh)*np.cos(theta)[None,:]-(R+h0+2),(R+hh)*np.sin(theta)[None,:]),axis=1);states=[]
 for col in [0,3]:
  vec=eph[:,col:col+3]-up*(R+h0+2);ee=vec@east;nn=vec@north;uu=vec@up;aa=np.mod(np.arctan2(ee,nn),2*np.pi)*180/np.pi;k=np.floor(aa).astype(int);f=aa-k;mm=mask[k]*(1-f)+mask[(k+1)%360]*f;states.append((np.arctan2(uu,np.hypot(ee,nn)),mm))
 x=np.clip((states[0][0]-states[0][1])/np.radians(.2666),-1,1);sun=.5+(x*np.sqrt(1-x*x)+np.arcsin(x))/np.pi;earth=states[1][0]>states[1][1]
 for field,v in [('sun',sun.mean()),('earth',earth.mean()),('both',((sun>=.5)&earth).mean())]:
  raw=float(np.load(cache/(field+'.npy'),mmap_mode='r')[r,c]);d=float((v-raw)*100);rows.append(dict(kind='dem',field=field,row=int(r),col=int(c),lat=lat,lon=lon,stored=raw,mine=float(v),delta_pp=d,pass_=abs(d)<=.1))
 (out/'comparisons.json').write_text(json.dumps(rows,indent=2));print('checkpoint',int(r),int(c),flush=True)
fail=[x for x in rows if not x['pass_']];stats={k:{f:dict(max_abs_pp=max(abs(x['delta_pp']) for x in rows if x['kind']==k and x['field']==f),median_abs_pp=float(np.median([abs(x['delta_pp']) for x in rows if x['kind']==k and x['field']==f]))) for f in ['sun','earth','both']} for k in ['png','dem']}
summary=dict(seed=15112026,head='0fc89ad0791d7b19c3e7d7bfe03dd188c6f6dca5',integrity=hashes,statistics=stats,failures=fail);(out/'summary.json').write_text(json.dumps(summary,indent=2))
with open(out/'comparisons.csv','w') as fo:
 w=csv.DictWriter(fo,fieldnames=list(dict.fromkeys(k for x in rows for k in x)));w.writeheader();w.writerows(rows)
report='# Task T independent comparison\n\nMinchul Kim checks Soyun Jeong PR87 head '+summary['head']+'. Seed 15112026. All seven release-asset SHA256 values match committed manifest. Full original PDS LDEM64/16 downloaded and SHA256 checked. Own NumPy bilinear readers, full 360-azimuth spherical terrain march without early stop, 21912 topocentric ephemeris samples; no production imports. Sun means visible disc fraction, not sunlit hours. PNG 1000 output pixels per layer compared to independently interpolated raw floats, <=0.20001 pp quantization; DEM 10 raw cells <=0.1 pp. Every signed difference: comparisons.csv.\n\n'+json.dumps(stats,indent=2)+'\n\nFailures: '+str(len(fail))+'\n\n'+json.dumps(fail,indent=2)+'\n\nReproduce: python verification/task_t/verify.py with pinned target checkout. Source URLs and hashes: target/docs/task_t/MANIFEST.json. Raw inputs ignored. Agreement is same-input algorithm agreement, not physical accuracy certification.\n';(out/'report.md').write_text(report)
note='Task T independent raw-array comparison: '+('PASS' if not fail else 'FAIL')+'; 7 asset hashes, 1000 PNG pixels/layer and 10 DEM-recomputed cells. See task_t_independent/report.md; all failures retained.'
p=P('docs/verification_ledger.md');lines=p.read_text().splitlines()
for i,line in enumerate(lines):
 if 'gmaps/' in line and line.startswith('|') and 'gmaps_ppd32' not in line:lines[i]=line[:-1]+' '+note+' |'
p.write_text('\n'.join(lines)+'\n\n## Task T independent comparison\n\n'+note+'\n')
with open('docs/SI_USAGE.md','a') as fo:fo.write('\n| '+(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')+' (KST) | Minchul Kim | Task T independent check | ChatGPT Codex GPT-6 | Release hashes; PNG 1000 pixels; DEM 10 cells with own code | verification/task_t; docs/task_t_independent; docs/verification_ledger.md; docs/SI_USAGE.md | TO CHECK | TO CHECK |\n')
print(json.dumps(summary),flush=True)
