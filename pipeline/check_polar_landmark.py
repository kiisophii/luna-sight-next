"""Check NASA's Site04 region center against the named PGDA Shackleton rim DEM."""
import json
import math
from pathlib import Path

import numpy as np
import tifffile

from fetch_polar import BASE, SOURCES, RADIUS, POLAR, RangeFile, grid, read_window, validate_crs

LAT, LON = -89.7668, -171.87
SOURCE = 'https://ntrs.nasa.gov/api/citations/20250002845/downloads/M2M-30044%20Lunar%20Surface%20Data%20Book%20Baseline_Final.pdf'


def main():
    x,y=POLAR(LON,LAT)
    rho=2*RADIUS*math.tan(math.pi/4+math.radians(LAT)/2)
    analytic=(rho*math.sin(math.radians(LON)),rho*math.cos(math.radians(LON)))
    np.testing.assert_allclose([x,y],analytic,atol=1e-7,rtol=0)
    np.testing.assert_allclose(POLAR(x,y,inverse=True),[LON,LAT],atol=1e-9,rtol=0)
    report=dict(lat=LAT,lon=LON,source=SOURCE,kind='region center, not surveyed summit',
                x_m=x,y_m=y,analytic_error_m=float(np.max(np.abs(np.array([x,y])-analytic))),dems=[])
    for url in [BASE+'LOLA_5mpp/Site04/Site04_final_adj_5mpp_surf.tif',BASE+SOURCES[5][0]]:
        with RangeFile(url,Path('data/raw/landmark_blocks')) as remote, tifffile.TiffFile(remote) as t:
            page=t.pages[0]
            validate_crs(page.geotiff_tags)
            x0,y0,step=grid(page)
            r,c=round((y0-y)/step),round((x-x0)/step)
            height=float(read_window(page,remote,(r,r+1,c,c+1))[0,0])
            if not math.isfinite(height):
                raise ValueError('No valid terrain at landmark')
            report['dems'].append(dict(url=url,row=r,col=c,height_m=height,
                                      pixel_center_distance_m=math.hypot(x0+c*step-x,y0-r*step-y)))
    report['mosaic_minus_regional_m']=report['dems'][1]['height_m']-report['dems'][0]['height_m']
    out=Path('data/processed/polar_landmark.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
