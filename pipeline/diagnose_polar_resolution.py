"""Distinguish source/caching errors from DEM spatial-support differences.

Uses existing full-radius TEST_POLAR caches. Does not modify terrain data.
--fresh checks encoded source tile bytes against fresh, uncached HTTP requests.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
import requests
import tifffile

from verify_polar import sample


def aggregate(z, x, y, width=240):
    """Mean of fully aligned fine pixel footprints inside one coarse cell."""
    xs, ys = z['x_m'], z['y_m']
    step = float(xs[1]-xs[0])
    n = round(width/step)
    if abs(n*step-width) > 1e-6:
        raise ValueError('Cell size is not an integer multiple')
    c = round((x-width/2+step/2-xs[0])/step)
    r = round((ys[0]-(y+width/2-step/2))/step)
    if not (0 <= r and r+n <= len(ys) and 0 <= c and c+n <= len(xs)):
        raise ValueError('Coarse footprint outside fine cache')
    np.testing.assert_allclose([xs[c],ys[r]], [x-width/2+step/2,y+width/2-step/2],atol=1e-7,rtol=0)
    return float(np.mean(z['height_m'][r:r+n,c:c+n],dtype=np.float64))


def stats(values):
    a=np.asarray(values,dtype=float)
    if not np.isfinite(a).all():
        raise ValueError('Nonfinite comparison')
    return dict(n=len(a),bias_m=float(a.mean()),mae_m=float(abs(a).mean()),
                rmse_m=float(np.sqrt(np.mean(a*a))),max_abs_m=float(abs(a).max()))


def source_check(root,res,z,x,y,fresh):
    """Independent GDAL geolocation/value check of ALL four interpolation pixels."""
    meta=json.loads(str(z['metadata']))
    path=root/'_verify'/f'{res}.tif'
    with rasterio.open(path) as d:
        c,r=(~d.transform)*(x,y)
        c,r=c-0.5,r-0.5
        c0,r0=int(np.floor(c)),int(np.floor(r))
        dc,dr=c-c0,r-r0
        weights=np.array([[(1-dr)*(1-dc),(1-dr)*dc],[dr*(1-dc),dr*dc]])
        pixels=d.read(1,window=Window(c0,r0,2,2)).astype(float)
        zr,zc=r0-meta['bounds'][0],c0-meta['bounds'][2]
        np.testing.assert_array_equal(pixels,z['height_m'][zr:zr+2,zc:zc+2])
        independent=float((pixels*weights).sum())
        np.testing.assert_allclose(independent,sample(z,x,y),atol=1e-8,rtol=0)
    checks=[]
    if fresh:
        with tifffile.TiffFile(path) as t, path.open('rb') as local:
            p=t.pages[0]
            across=int(np.ceil(p.imagewidth/p.tilewidth))
            indices={(rr//p.tilelength)*across+cc//p.tilewidth
                     for rr in [r0,r0+1] for cc in [c0,c0+1]}
            for idx in sorted(indices):
                off,size=p.dataoffsets[idx],p.databytecounts[idx]
                local.seek(off)
                cached=local.read(size)
                with requests.get(meta['source_url'],headers={'Range':f'bytes={off}-{off+size-1}',
                    'Accept-Encoding':'identity'},stream=True,timeout=60) as response:
                    response.raise_for_status()
                    assert response.status_code==206
                    assert response.headers['Content-Range']==f'bytes {off}-{off+size-1}/{meta["source_size_bytes"]}'
                    assert response.headers.get('ETag')==meta['etag']
                    raw=response.raw.read(size+1)
                assert raw==cached, 'Fresh source tile differs from cache'
                checks.append(dict(tile=idx,bytes=size,sha256=hashlib.sha256(raw).hexdigest()))
    return dict(source_url=meta['source_url'],pixel_row=r0,pixel_col=c0,
                four_heights_m=pixels.tolist(),weights=weights.tolist(),
                independent_bilinear_m=independent,fresh_tiles=checks)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/raw/polar'))
    p.add_argument('--fresh',action='store_true')
    p.add_argument('--report',type=Path,default=Path('data/processed/polar_resolution_diagnosis.json'))
    args=p.parse_args()
    previous=json.loads(Path('data/processed/polar_verification.json').read_text())
    worst=max(previous['points'],key=lambda q:abs(q['delta_from_5m']['240']))
    x,y=worst['x_m'],worst['y_m']
    report=dict(point_xy_m=[x,y],source_checks={},point_decomposition={},sites={})
    for site in ['TEST_POLAR_1','TEST_POLAR_2','TEST_POLAR_3']:
        caches={k:dict(np.load(args.root/str(k)/(site+'.npz'))) for k in [5,10,20,60,80,240]}
        co,fine=caches[240],caches[5]
        # Common area: only complete 240 m cells fully inside the fine cache.
        cols=np.flatnonzero((co['x_m']-120 >= fine['x_m'][0]-2.5)&(co['x_m']+120 <= fine['x_m'][-1]+2.5))
        rows=np.flatnonzero((co['y_m']+120 <= fine['y_m'][0]+2.5)&(co['y_m']-120 >= fine['y_m'][-1]-2.5))
        site_stats={}
        for res in [5,10,20,60,80]:
            area_errors=[];point_errors=[]
            q=caches[res]
            independent=np.empty((len(rows),len(cols)),dtype=np.float64)
            crs=json.loads(str(q['metadata']))['projection']
            reproject(q['height_m'],independent,
                src_transform=from_origin(q['x_m'][0]-res/2,q['y_m'][0]+res/2,res,res),
                src_crs=crs,src_nodata=np.nan,
                dst_transform=from_origin(co['x_m'][cols[0]]-120,co['y_m'][rows[0]]+120,240,240),
                dst_crs=crs,dst_nodata=np.nan,resampling=Resampling.average,num_threads=1)
            aggregation_errors=[]
            for ri,r in enumerate(rows):
                for ci,c in enumerate(cols):
                    cx,cy=float(co['x_m'][c]),float(co['y_m'][r])
                    truth=float(co['height_m'][r,c])
                    area_value=aggregate(caches[res],cx,cy)
                    aggregation_errors.append(area_value-independent[ri,ci])
                    area_errors.append(truth-area_value)
                    point_errors.append(truth-sample(caches[res],cx,cy))
            np.testing.assert_allclose(aggregation_errors,0,atol=1e-7,rtol=0)
            site_stats[str(res)]=dict(area_matched=stats(area_errors),point_sampled=stats(point_errors),
                                     independent_gdal_average=stats(aggregation_errors))
        report['sites'][site]=site_stats
        if site=='TEST_POLAR_1':
            for res in [5,240]:
                report['source_checks'][str(res)]=source_check(args.root,res,caches[res],x,y,args.fresh)
            c=int(np.searchsorted(co['x_m'],x))-1
            r=int(np.searchsorted(-co['y_m'],-y))-1
            weights=np.array(report['source_checks']['240']['weights'])
            coarse_point=sample(co,x,y)
            for res in [5,10,20,60,80]:
                averaged=np.array([[aggregate(caches[res],float(co['x_m'][c+j]),float(co['y_m'][r+i]))
                                    for j in range(2)] for i in range(2)])
                area_point=float((averaged*weights).sum())
                fine_point=sample(caches[res],x,y)
                report['point_decomposition'][str(res)]=dict(native_point_m=fine_point,
                    area_matched_point_m=area_point,coarse_point_m=coarse_point,
                    scale_effect_m=area_point-fine_point,residual_m=coarse_point-area_point,
                    area_averaged_four_cells_m=averaged.tolist())
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
