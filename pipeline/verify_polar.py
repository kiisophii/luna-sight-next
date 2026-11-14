"""Independent GDAL decoding and cross-resolution checks on downloaded windows."""
import argparse
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import rasterio
from rasterio.windows import Window

from fetch_polar import RangeFile, SOURCES, BASE
import tifffile


def sample(z, x, y):
    """Bilinear elevation at identical projected coordinates across grids."""
    xs, ys = z['x_m'], z['y_m']
    col = (x-xs[0])/(xs[1]-xs[0])
    row = (ys[0]-y)/(ys[0]-ys[1])
    r, c = int(np.floor(row)), int(np.floor(col))
    if r < 0 or c < 0 or r+1 >= len(ys) or c+1 >= len(xs):
        raise ValueError('Sample outside cache')
    dy, dx = row-r, col-c
    a = z['height_m'][r:r+2,c:c+2]
    return float(a[0,0]*(1-dy)*(1-dx)+a[0,1]*(1-dy)*dx+a[1,0]*dy*(1-dx)+a[1,1]*dy*dx)


def sparse_source(root, res):
    """Materialize fetched byte ranges as a sparse TIFF for independent GDAL reads.

    Unfetched tiles must never be sampled. Fetch all IFDs so GDAL can enumerate
    overviews, without fetching their imagery. NTFS sparse flag avoids multi-GB
    allocation on Windows. Only ignored raw files are written.
    """
    with RangeFile(BASE+SOURCES[res][0], root/'_blocks') as remote:
        with tifffile.TiffFile(remote) as t:
            for p in t.pages:
                _ = p.tags.values()
        dest = root/'_verify'/f'{res}.tif'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.touch()
        if os.name == 'nt':
            subprocess.run(['fsutil','sparse','setflag',str(dest.resolve())],check=True,capture_output=True)
        with dest.open('r+b') as f:
            f.truncate(remote.size)
            for b in remote.cache.iterdir():
                if b.name.isdigit():
                    f.seek(int(b.name))
                    f.write(b.read_bytes())
        return dest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/raw/polar'))
    p.add_argument('--site',default='TEST_POLAR_1')
    p.add_argument('--report',type=Path,default=Path('data/processed/polar_verification.json'))
    args=p.parse_args()
    caches={res:np.load(args.root/str(res)/(args.site+'.npz')) for res in SOURCES}
    rng=np.random.default_rng(42)
    fine=caches[5]
    # Interior coordinates common to every requested resolution.
    xs=rng.uniform(fine['x_m'][10],fine['x_m'][-11],5)
    ys=rng.uniform(fine['y_m'][-11],fine['y_m'][10],5)
    report={'site':args.site,'seed':42,'sources':{},'points':[],'gdal_max_abs_error_m':{}}
    for x,y in zip(xs,ys):
        values={str(res):sample(z,x,y) for res,z in caches.items()}
        report['points'].append(dict(x_m=float(x),y_m=float(y),height_m=values,
            delta_from_5m={res:v-values['5'] for res,v in values.items()}))
    for res,z in caches.items():
        m=json.loads(str(z['metadata']))
        report['sources'][str(res)]=m['source_url']
        src=sparse_source(args.root,res)
        errors=[]
        with rasterio.open(src) as d:
            for x,y in zip(xs,ys):
                r=int(np.argmin(abs(z['y_m']-y))); c=int(np.argmin(abs(z['x_m']-x)))
                gr,gc=m['bounds'][0]+r,m['bounds'][2]+c
                sx,sy=d.xy(gr,gc)
                np.testing.assert_allclose([sx,sy],[z['x_m'][c],z['y_m'][r]],atol=1e-6,rtol=0)
                actual=d.read(1,window=Window(gc,gr,1,1))[0,0]
                expected=z['height_m'][r,c]
                np.testing.assert_allclose(actual,expected,atol=0,rtol=0)
                errors.append(float(abs(actual-expected)))
        report['gdal_max_abs_error_m'][str(res)]=max(errors)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
