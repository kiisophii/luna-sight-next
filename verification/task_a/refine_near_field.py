"""Uniform near-field convergence check for ALL 33 sites and ALL 720 rays.

Reuse the independently recomputed full-range masks, not production masks.
Replace the coarse near-field lower bound with a denser independent march.
Keep the entire initial comparison so discrepancies cannot disappear silently.
"""
import json
import math
from pathlib import Path
import time
import numpy as np
import verify_horizons_independent as c

c.RAW = c.RAW / 'near_convergence'


class SmallPDS:
    def __init__(self, site, urls, metres_before_interpolation):
        self.parts=[]
        self.evidence=[]
        self.before=metres_before_interpolation
        arc=3500/c.R
        dla=math.degrees(arc)
        dlo=math.degrees(math.asin(math.sin(arc)/math.cos(math.radians(site['lat']))))
        for url in urls:
            label=c.text(url[:-4]+'.lbl')
            g=c.label(label)
            ppd=g['MAP_RESOLUTION']
            ns,nl=int(g['LINE_SAMPLES']),int(g['LINES'])
            assert g['SAMPLE_TYPE']=='PC_REAL' and g['UNIT']=='KILOMETER'
            assert g['OFFSET']==1737.4 and g.get('SCALING_FACTOR',1)==1
            lo=site['lon']%360
            ra=max(0,math.floor(g['LINE_PROJECTION_OFFSET']-(site['lat']+dla)*ppd)-2)
            rb=min(nl,math.ceil(g['LINE_PROJECTION_OFFSET']-(site['lat']-dla)*ppd)+3)
            ca=max(0,math.floor(g['SAMPLE_PROJECTION_OFFSET']+(lo-dlo-g['CENTER_LONGITUDE'])*ppd)-2)
            cb=min(ns,math.ceil(g['SAMPLE_PROJECTION_OFFSET']+(lo+dlo-g['CENTER_LONGITUDE'])*ppd)+3)
            if ra>=rb or ca>=cb:continue
            a=np.empty((rb-ra,cb-ca),dtype='<f4')
            for start in range(ra,rb,32):
                rows=list(range(start,min(rb,start+32)))
                spans=[(4*(r*ns+ca),4*(r*ns+cb)-1) for r in rows]
                raw=c.ranges(url,spans)
                for r,b in zip(rows,raw):a[r-ra]=np.frombuffer(b,dtype='<f4')
            # Match the source conversion precision recorded by the original
            # independent full-range reader, not a different observer terrain.
            if self.before:a=a*1000
            self.parts.append((a,g,ra,ca))
            self.evidence.append(dict(url=url,label_sha256=c.digest(label.encode('latin-1')),
                source_window_sha256=c.digest(a.tobytes()),bounds=[ra,rb,ca,cb]))

    def __call__(self,lat,lon):
        result=np.full(lat.shape,np.nan)
        for a,g,ra,ca in self.parts:
            need=~np.isfinite(result)
            if not need.any():break
            row=g['LINE_PROJECTION_OFFSET']-lat[need]*g['MAP_RESOLUTION']-ra
            col=g['SAMPLE_PROJECTION_OFFSET']+((lon[need]%360)-g['CENTER_LONGITUDE'])*g['MAP_RESOLUTION']-ca
            value=c.bilinear(a,row,col)
            if not self.before:value=value*1000
            result[need]=value
        return result


class Lazy:
    def __init__(self,factory):self.factory,self.reader=factory,None
    def __call__(self,lat,lon):
        if self.reader is None:self.reader=self.factory()
        if self.reader is None:return np.full(lat.shape,np.nan)
        return self.reader(lat,lon)


def refine(site):
    p=c.OUT/(site['id']+'.json')
    r=json.loads(p.read_text())
    if r.get('near_refinement',{}).get('checker_sha256')==c.digest(Path(__file__).read_bytes()):
        print('REUSED refined',site['id'],flush=True);return
    ref=json.loads((c.ROOT/'web/data/horizon'/(site['id']+'.json')).read_text())
    assert r['stored_sha256']==c.digest((c.ROOT/'web/data/horizon'/(site['id']+'.json')).read_bytes())
    chain=[]
    urls=next((x['metadata']['sources'] for x in r['sources'] if x['name']=='SLDEM2015'),[])
    urls=[x['url'] for x in urls]
    for name,limit,*_ in ref['engine']['chain']:
        if name.startswith('PGDA_LOLA_'):
            res=int(name.split('_')[-1][:-1]); radius=min(limit,3.25)
            reader=Lazy(lambda res=res,radius=radius:c.polar_window(site,res,radius))
        elif name=='SLDEM2015':reader=Lazy(lambda:SmallPDS(site,urls,True))
        else:
            ppd=int(name.split('_')[-1])
            reader=Lazy(lambda ppd=ppd:SmallPDS(site,[c.PDS+f'lola_gdr/cylindrical/float_img/ldem_{ppd}_float.img'],False))
        chain.append((limit*1000,reader))

    def sample(lat,lon,dist):
        h=np.full(lat.shape,np.nan)
        for limit,reader in chain:
            need=~np.isfinite(h)&(dist<=limit)
            if need.any():h[need]=reader(lat[need],lon[need])
        if not np.isfinite(h).all():raise ValueError(site['id']+' missing near-field source pixels')
        return h

    minimum=ref['engine']['min_km']*1000
    ds=np.unique(np.r_[np.arange(minimum,200,.025),np.arange(max(minimum,200),3000,.25),3000.])
    th=ds/c.R
    h0=r['own_h0_m']
    fresh_h0=float(sample(np.array([site['lat']]),np.array([site['lon']]),np.array([0.]))[0])
    if abs(fresh_h0-h0)>.001:raise ValueError('Observer height changed '+site['id'])
    near=[];peak=[]
    start=time.time()
    for a in range(0,720,12):
        la,lo=c.destinations(site['lat'],site['lon'],np.arange(a,a+12)*.5,ds)
        terrain=sample(la,lo,np.broadcast_to(ds,la.shape))
        v=terrain-h0-2-(c.R+terrain)*2*np.sin(th/2)**2
        angles=np.degrees(np.arctan2(v,(c.R+terrain)*np.sin(th)))
        k=angles.argmax(axis=1)
        near.extend(angles[np.arange(12),k].tolist());peak.extend(ds[k].tolist())
    old=np.array(r['mask_deg']);dense=np.array(near)
    final=np.maximum(old,dense)
    difference=final-np.array(r['stored_mask_deg'])
    r['initial_comparison']=dict(mask_deg=r['mask_deg'],difference_deg=r['difference_deg'],
        failures_deg=r['failures_deg'],max_abs_deg=r['max_abs_deg'],
        own_sun_frac=r['own_sun_frac'],sun_difference_pp=r['sun_difference_pp'])
    r['mask_deg']=final.tolist();r['difference_deg']=difference.tolist()
    r['peak_distance_m']=np.where(dense>old,np.array(peak),np.array(r['peak_distance_m'])).tolist()
    r['max_abs_deg']=float(abs(difference).max());r['median_abs_deg']=float(np.median(abs(difference)))
    r['failures_deg']=np.flatnonzero(abs(difference)>.05).tolist()
    r['own_sun_frac']=c.sunlight(site,final,h0)
    r['sun_difference_pp']=100*(r['own_sun_frac']-r['stored_sun_frac'])
    r['near_refinement']=dict(checker_sha256=c.digest(Path(__file__).read_bytes()),
        near_max_m=3000,near_step_m=.025,near_step_end_m=200,outer_near_step_m=.25,
        distances_per_ray=len(ds),rays=720,all_sites_rule=True,own_h0_resample_m=fresh_h0,
        monotonic_dense_extension=True,max_mask_increase_deg=float((final-old).max()),elapsed_s=time.time()-start,
        sources=[getattr(x.reader,'evidence',getattr(x.reader,'meta',None)) for _,x in chain if x.reader is not None])
    c.atomic(p,r)
    print('REFINED',site['id'],'max angle',r['max_abs_deg'],'failures',len(r['failures_deg']),
          'sun pp',r['sun_difference_pp'],flush=True)


if __name__=='__main__':
    sites=json.loads((c.ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
    assert len(sites)==33
    for s in sites:refine(s)
