import os,json,math,hashlib,csv,io,urllib.request
os.environ['GDAL_DISABLE_READDIR_ON_OPEN']='EMPTY_DIR'
import numpy as np,rasterio
from rasterio.windows import Window
from pyproj import Proj,Geod,CRS
from scipy.optimize import minimize_scalar
from pathlib import Path
R=1737400.; proj=Proj(proj='stere',lat_0=-90,lat_ts=-90,lon_0=0,R=R); geo=Geod(a=R,b=R)
root=Path('z2-review'); out=[]
u='https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.TIF'
from original_psr import Reader
with Reader(u) as src:
 assert src.width==src.height==30400 and src.transform.a==20 and src.transform.e==-20 and math.isnan(src.nodata)
 assert src.crs.to_dict()['lat_0']==-90 and CRS(src.crs).ellipsoid.semi_major_metre==R
 for sid in ['ARTEMIS_HAWORTH','SHACKLETON_RIM','IM1']:
  o=json.loads((root/'web/data/detail/psr'/f'{sid}.json').read_text());cx,cy=proj(o['lon'],o['lat']);row,col=src.index(cx,cy)
  r0=max(0,row-560);c0=max(0,col-560);r1=min(src.height,row+561);c1=min(src.width,col+561)
  a=src.read(1,window=Window(c0,r0,c1-c0,r1-r0)); assert np.isfinite(a).all() and set(np.unique(a))<={0,1}
  inside=int(a[row-r0,col-c0]);ys,xs=np.where(a==1);xx=-303990+(xs+c0)*20;yy=303990-(ys+r0)*20
  lo,la=proj(xx,yy,inverse=True);az,_,dist=geo.inv(np.full(lo.shape,o['lon']),np.full(la.shape,o['lat']),lo,la);i=int(np.argmin(dist))
  best=float(dist[i]); ba=None;bp=None
  kmax=1+(max(abs(-304000+c0*20),abs(-304000+c1*20))**2+max(abs(304000-r0*20),abs(304000-r1*20))**2)/(4*R*R)
  def objective(t,p,q):
   x=p[0]+t*(q[0]-p[0]);y=p[1]+t*(q[1]-p[1]);lon,lat=proj(x,y,inverse=True);return geo.inv(o['lon'],o['lat'],lon,lat)[2]
  for dr,dc,axis,sign in [(0,-1,'x',-1),(0,1,'x',1),(-1,0,'y',1),(1,0,'y',-1)]:
   valid=(ys+dr>=0)&(ys+dr<a.shape[0])&(xs+dc>=0)&(xs+dc<a.shape[1]);idx=np.flatnonzero(valid);idx=idx[a[ys[idx]+dr,xs[idx]+dc]==0]
   for j in idx:
    x,y=xx[j],yy[j]
    if np.hypot(x-cx,y-cy)-15>best*kmax:continue
    p=(x+sign*10,y-10) if axis=='x' else (x-10,y+sign*10);q=(p[0],p[1]+20) if axis=='x' else (p[0]+20,p[1])
    opt=minimize_scalar(lambda t:objective(t,p,q),bounds=(0,1),method='bounded',options={'xatol':1e-12})
    for t in [0.,1.,float(opt.x)]:
     d=objective(t,p,q)
     if d<best:best=d;bp=(p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1]))
  lon,lat=proj(*bp,inverse=True);bearing=geo.inv(o['lon'],o['lat'],lon,lat)[0]%360
  edge=min(cx-(-304000+c0*20),(-304000+c1*20)-cx,cy-(304000-r1*20),(304000-r0*20)-cy)/kmax
  result=dict(id=sid,inside=bool(inside),center_m=float(dist[i]),center_bearing=float(az[i]%360),boundary_m=best,boundary_bearing=bearing,unsearched_lower_bound_m=edge,window=[r0,r1,c0,c1],raw_sha256=hashlib.sha256(a.tobytes()).hexdigest())
  for key,got,stored in [('center',result['center_m'],o['nearest_pixel_center']['distance_m']),('boundary',best,o['nearest_boundary']['distance_m'])]:
   result[key+'_relative_error']=abs(got-stored)/stored;assert result[key+'_relative_error']<=.01
  assert bool(inside)==o['inside_psr'] and edge>result['center_m'] and edge>best
  assert abs((result['center_bearing']-o['nearest_pixel_center']['bearing_deg']+180)%360-180)<.01
  assert abs((bearing-o['nearest_boundary']['bearing_deg']+180)%360-180)<.01
  out.append(result);print(result,flush=True)
Path('z2-independent-results.json').write_text(json.dumps(dict(head='beedb67e7993258720ebfc9219e140636f6e4b11',source=u,results=out,passed=True),indent=2))
