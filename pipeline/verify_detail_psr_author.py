"""Independent author check: analytic stereographic distance and edge minimum.

No imports from the PSR producer or PROJ. This is not other-member verification.
"""
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
R=1737400.
K=4*R*R


def project(lat,lon):
    c=math.radians(90+lat)
    rho=2*R*math.tan(c/2)
    return rho*math.sin(math.radians(lon)),rho*math.cos(math.radians(lon))


def distance(sx,sy,x,y):
    # Exact chord formula for the inverse stereographic sphere.
    q=K*((x-sx)**2+(y-sy)**2)/((K+sx*sx+sy*sy)*(K+x*x+y*y))
    return 2*R*np.arcsin(np.sqrt(np.clip(q,0,1)))


def boundary_min(a,x0,y0,step,sx,sy):
    # Independently enumerate all known 1/0 interfaces, not per-PSR-pixel outlines.
    vertical=np.isfinite(a[:,:-1])&np.isfinite(a[:,1:])&(a[:,:-1]!=a[:,1:])
    horizontal=np.isfinite(a[:-1,:])&np.isfinite(a[1:,:])&(a[:-1,:]!=a[1:,:])
    vr,vc=np.nonzero(vertical);hr,hc=np.nonzero(horizontal)
    x=np.concatenate([x0+(vc+.5)*step,x0+(hc-.5)*step])
    y=np.concatenate([y0-(vr+.5)*step,y0-(hr+.5)*step])
    dx=np.concatenate([np.zeros(len(vr)),np.full(len(hr),step)])
    dy=np.concatenate([np.full(len(vr),step),np.zeros(len(hr))])
    # Minimize ratio ((x-sx)^2+(y-sy)^2)/(K+x^2+y^2) on each edge t in [0,1].
    A=dx*dx+dy*dy;B=2*((x-sx)*dx+(y-sy)*dy);C=(x-sx)**2+(y-sy)**2
    D=A;E=2*(x*dx+y*dy);F=K+x*x+y*y
    aa=A*E-B*D;bb=2*(A*F-C*D);cc=B*F-C*E
    disc=np.maximum(0,bb*bb-4*aa*cc)
    q=-.5*(bb+np.copysign(np.sqrt(disc),bb))
    with np.errstate(divide='ignore',invalid='ignore'):
        t1=q/aa;t2=cc/q
        linear=-cc/bb
    t1=np.where(aa==0,linear,t1)
    t2=np.where(aa==0,linear,t2)
    choices=np.stack([np.zeros(len(x)),np.ones(len(x)),np.nan_to_num(np.clip(t1,0,1)),np.nan_to_num(np.clip(t2,0,1))])
    xx=x+choices*dx;yy=y+choices*dy
    ds=distance(sx,sy,xx,yy)
    k=np.unravel_index(np.argmin(ds),ds.shape)
    return float(ds[k]),float(xx[k]),float(yy[k])


def main():
    started=time.perf_counter();rows=[]
    sites=json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf8'))
    for sid in (s['id'] for s in sites if s['lat']<=-75):
        obj=json.loads((ROOT/f'web/data/detail/psr/{sid}.json').read_text(encoding='utf8'))
        with np.load(ROOT/obj['provenance']['window_cache']) as z:a=z['classes']
        assert hashlib.sha256(a.astype('<f4').tobytes()).hexdigest()==obj['provenance']['window_sha256']
        x0,y0=obj['provenance']['window_first_center_xy_m'];step=20.
        sx,sy=project(obj['lat'],obj['lon']);rr,cc=np.nonzero(a==1)
        ds=distance(sx,sy,x0+cc*step,y0-rr*step);ix=int(np.argmin(ds))
        global_r=obj['provenance']['window_bounds_rc'][0]+int(rr[ix]);global_c=obj['provenance']['window_bounds_rc'][2]+int(cc[ix])
        native_row=math.floor((y0+step/2-sy)/step);native_col=math.floor((sx-x0+step/2)/step)
        assert bool(a[native_row,native_col]==1)==obj['inside_psr']
        assert (global_r,global_c)==(obj['nearest_pixel_center']['row'],obj['nearest_pixel_center']['col'])
        bd,bx,by=boundary_min(a,x0,y0,step,sx,sy)
        centre_diff=abs(float(ds[ix])-obj['nearest_pixel_center']['distance_m'])
        boundary_diff=abs(bd-obj['nearest_boundary']['distance_m'])
        assert centre_diff<.001 and boundary_diff<.001
        rows.append(dict(id=sid,centre_diff_m=centre_diff,boundary_diff_m=boundary_diff,
                         centre_row_col_exact=True,inside_class_exact=True,independent_boundary_xy_m=[bx,by],
                         window_sha256=obj['provenance']['window_sha256']))
    result=dict(scope='Author-side separate analytic formulas; all class1 pixels and known interfaces in all 16 original native windows',
                method='Closed-form south-polar stereographic chord distances and quadratic stationary roots on every pixel-union edge; no producer or PROJ imports',
                independent_team_verification='pending',rows=rows,elapsed_s=time.perf_counter()-started)
    (ROOT/'docs/detail_z2_author_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    assert abs(float(distance(0.,0.,20.,0.))-2*R*math.atan(20/(2*R)))<1e-10
    test=np.array([[0.,1.],[0.,1.]])
    assert abs(boundary_min(test,0.,0.,20.,0.,0.)[0]-2*R*math.atan(10/(2*R)))<1e-8
    main()
