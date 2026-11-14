"""Independent card-8 check: PROJ geodesics, separate interpolation, ECEF sight lines.

Does not import horizon.py or reuse its geometry/interpolation/early-stop code.
Checks 10 directions at two sites on both the production distance grid and a
uniform 2.5 m grid from 5 m to 300 km. This verifies computations against the
same DEMs, not the physical accuracy of the DEM products themselves.
"""
import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
from pyproj import Geod, Proj

RADIUS = 1737400.0
GEOD = Geod(a=RADIUS, b=RADIUS)
ROOT = Path(__file__).resolve().parents[1]


def interpolate(array, row, col, wrap=False):
    """Four independent pixel weights; invalid neighbors remain missing."""
    ny, nx = array.shape
    valid = (row >= 0) & (row <= ny-1)
    if not wrap:
        valid &= (col >= 0) & (col <= nx-1)
    out = np.full(row.shape, np.nan)
    rr, cc = row[valid], col[valid]
    y = np.minimum(np.floor(rr).astype(int), ny-2)
    x = np.floor(cc).astype(int) if wrap else np.minimum(np.floor(cc).astype(int), nx-2)
    dy, dx = rr-y, cc-x
    out[valid] = (array[y,x % nx]*(1-dx)*(1-dy) + array[y,(x+1) % nx]*dx*(1-dy)
                  + array[y+1,x % nx]*(1-dx)*dy + array[y+1,(x+1) % nx]*dx*dy)
    return out


class IndependentDEM:
    def __init__(self, site, raw):
        self.sources = []
        for res in [5,10,20,60,80,240]:
            path = raw/'polar'/str(res)/(site['id']+'.npz')
            if path.exists():
                with np.load(path, allow_pickle=False) as z:
                    meta = json.loads(str(z['metadata']))
                    x, y = z['x_m'], z['y_m']
                    self.sources.append(dict(kind='polar', array=z['height_m'],
                        project=Proj(meta['projection']), x0=x[0], y0=y[0],
                        dx=x[1]-x[0], dy=y[0]-y[1], max_km=meta['radius_m']/1000))
        for ppd in [64,16]:
            path = raw/'global'/f'ldem_{ppd}_float.img'
            if path.exists():
                label = path.with_suffix('.lbl').read_text(encoding='latin-1')
                def number(key):
                    return float(re.search(r'^\s*'+key+r'\s*=\s*([-+0-9.eE]+)',label,re.M)[1])
                ny, nx = int(number('LINES')), int(number('LINE_SAMPLES'))
                self.sources.append(dict(kind='global',array=np.memmap(path,dtype='<f4',shape=(ny,nx),mode='r'),
                    ppd=number('MAP_RESOLUTION'), lpo=number('LINE_PROJECTION_OFFSET'),
                    spo=number('SAMPLE_PROJECTION_OFFSET'), clon=number('CENTER_LONGITUDE'),
                    scale=number('SCALING_FACTOR')*1000, max_km=300))

    def __call__(self, lat, lon, distances_km):
        out = np.full(lat.shape, np.nan)
        for source in self.sources:
            use = np.isnan(out) & (distances_km <= source['max_km'])
            if not use.any():
                continue
            la, lo = lat[use], lon[use]
            if source['kind'] == 'polar':
                x, y = source['project'](lo,la)
                row, col = (source['y0']-y)/source['dy'], (x-source['x0'])/source['dx']
                out[use] = interpolate(source['array'],row,col)
            else:
                row = np.clip(source['lpo']-la*source['ppd'],0,source['array'].shape[0]-1)
                col = source['spo']+(np.mod(lo,360)-source['clon'])*source['ppd']
                out[use] = interpolate(source['array'],row,col,wrap=True)*source['scale']
        return out


def trace(site, sample, azimuths, distance_m):
    lat0, lon0 = site['lat'], site['lon']
    h0 = sample(np.array([lat0]),np.array([lon0]),np.array([0.]))[0]
    if not np.isfinite(h0):
        raise ValueError('missing observer elevation')
    la0, lo0 = np.radians([lat0,lon0])
    up = np.array([np.cos(la0)*np.cos(lo0), np.cos(la0)*np.sin(lo0), np.sin(la0)])
    observer = (RADIUS+h0+2)*up
    rows = []
    for az in azimuths:
        lon,lat,_ = GEOD.fwd(np.full(distance_m.shape,lon0),np.full(distance_m.shape,lat0),
                            np.full(distance_m.shape,az),distance_m)
        heights = sample(lat,lon,distance_m/1000)
        if not np.isfinite(heights).all():
            raise ValueError(f'{az} deg: missing terrain samples')
        la,lo = np.radians(lat),np.radians(lon)
        unit = np.column_stack([np.cos(la)*np.cos(lo),np.cos(la)*np.sin(lo),np.sin(la)])
        delta = (RADIUS+heights)[:,None]*unit - observer
        vertical = np.sum(delta*up,axis=1)
        horizontal = np.linalg.norm(delta-vertical[:,None]*up,axis=1)
        elevations = np.degrees(np.arctan2(vertical,horizontal))
        peak = int(np.argmax(elevations))
        rows.append(dict(azimuth_deg=float(az),elevation_deg=float(elevations[peak]),
                         peak_distance_m=float(distance_m[peak])))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,default=ROOT/'data/raw')
    parser.add_argument('--site',action='append')
    parser.add_argument('--step-m',type=float,default=2.5)
    parser.add_argument('--report',type=Path,default=ROOT/'data/processed/card8-independent.json')
    args=parser.parse_args()
    if not math.isfinite(args.step_m) or args.step_m <= 0:
        parser.error('--step-m must be positive and finite')
    sites=json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf-8'))
    selected=args.site or ['SHACKLETON_RIM','ARTEMIS_DE_GERLACHE_RIM2']
    if set(selected)-{s['id'] for s in sites}:
        parser.error('Unknown site')
    report=[]
    for site in [s for s in sites if s['id'] in selected]:
        record=json.loads((ROOT/'web/data/horizon'/(site['id']+'.json')).read_text(encoding='utf-8'))
        params=record['engine']
        same=1000*np.exp(np.linspace(math.log(params['min_km']),math.log(params['max_km']),params['n_steps']+1))
        same[0],same[-1]=params['min_km']*1000,params['max_km']*1000
        fine=np.unique(np.append(np.arange(same[0],same[-1],args.step_m),same[-1]))
        dem=IndependentDEM(site,args.raw)
        azimuths=np.arange(10)*36.
        a=trace(site,dem,azimuths,same)
        b=trace(site,dem,azimuths,fine)
        for exact,dense in zip(a,b):
            baseline=record['mask'][int(exact['azimuth_deg']/.5)]
            exact.update(stored_deg=baseline,same_grid_difference_deg=exact['elevation_deg']-baseline,
                         fine_grid_deg=dense['elevation_deg'],fine_grid_difference_deg=dense['elevation_deg']-baseline,
                         fine_peak_distance_m=dense['peak_distance_m'])
        item=dict(id=site['id'],uniform_step_m=args.step_m,rows=a,
                  max_same_grid_abs_deg=max(abs(x['same_grid_difference_deg']) for x in a),
                  max_fine_grid_abs_deg=max(abs(x['fine_grid_difference_deg']) for x in a))
        report.append(item)
        args.report.parent.mkdir(parents=True,exist_ok=True)
        temp=args.report.with_suffix('.tmp')
        temp.write_text(json.dumps(report,indent=2),encoding='utf-8')
        temp.replace(args.report)
        print(json.dumps({k:v for k,v in item.items() if k!='rows'}),flush=True)
    if any(x['max_same_grid_abs_deg'] > 0.0001 for x in report):
        raise SystemExit('FAIL: same-grid disagreement exceeds stored-angle rounding plus numerical allowance')


if __name__ == '__main__':
    main()
