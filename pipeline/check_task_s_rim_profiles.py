"""Independent local radial-profile diagnostic on cached original PGDA pixels.

Not a geological rim classifier. No imports from the producer or Soyun audit.
Requires the ignored native 20 m PGDA windows acquired for card 18/local250.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from pyproj import Geod, Proj

ROOT = Path(__file__).resolve().parents[1]
R = 1737400.0
GEOD = Geod(a=R, b=R)
PROJ = Proj(proj='stere', lat_0=-90, lat_ts=-90, lon_0=0, R=R)


def interpolate(z, xs, ys, x, y):
    ix = (np.asarray(x) - xs[0]) / (xs[1] - xs[0])
    iy = (np.asarray(y) - ys[0]) / (ys[1] - ys[0])
    i, j = np.floor(ix).astype(int), np.floor(iy).astype(int)
    if np.any(i < 0) or np.any(j < 0) or np.any(i + 1 >= z.shape[1]) or np.any(j + 1 >= z.shape[0]):
        raise ValueError('Requested profile exceeds native window')
    u, v = ix - i, iy - j
    return (1-u)*(1-v)*z[j,i] + u*(1-v)*z[j,i+1] + (1-u)*v*z[j+1,i] + u*v*z[j+1,i+1]


def main():
    # Independent analytic checks: descending-y pixel registration and constant plane.
    np.testing.assert_allclose(interpolate(np.array([[0.,2.],[3.,5.]]), [0.,1.], [1.,0.], .25, .25), 2.75)
    sites = {s['id']:s for s in json.loads((ROOT/'web/data/sites.json').read_text(encoding='utf8'))}
    results = []
    for id, clat, clon, url in (
        ('SHOEMAKER_RIM_A', -88.14, 45.91, 'https://planetarynames.wr.usgs.gov/Feature/5494'),
        ('SHACKLETON_RIM', -89.67, 129.78, 'https://planetarynames.wr.usgs.gov/Feature/5450'),
    ):
        path = ROOT / f'data/processed/local250/raw/polar/20/{id}.npz'
        with np.load(path, allow_pickle=False) as a:
            z, xs, ys = a['height_m'].astype(float), a['x_m'], a['y_m']
            metadata = json.loads(str(a['metadata']))
        targets = [(id, sites[id]['lat'], sites[id]['lon'])]
        if id == 'SHACKLETON_RIM':
            targets.append(('OLD_R04_POLYGON_CENTRE', -89.7668, -171.87))
        for label, lat, lon in targets:
            bearing, _, radius = GEOD.inv(clon, clat, lon, lat)
            h0 = float(interpolate(z, xs, ys, *PROJ(lon, lat)))
            profiles = []
            for step in (20, 5):
                offsets = np.arange(-3000., 3000. + step, step)
                radii = radius + offsets
                lons, lats, _ = GEOD.fwd(np.full_like(radii, clon), np.full_like(radii, clat), np.full_like(radii, bearing), radii)
                hh = interpolate(z, xs, ys, *PROJ(lons, lats))
                k = int(np.argmax(hh))
                profiles.append(dict(sampling_step_m=step, point_outward_of_local_radial_max_m=float(-offsets[k]),
                                     point_below_local_radial_max_m=float(hh[k]-h0),
                                     inward_1km_drop_m=float(h0-hh[np.argmin(abs(offsets+1000))])))
            results.append(dict(id=label, lat=lat, lon=lon, crater_centre=[clat,clon], crater_source=url,
                                source_dem=metadata['source_url'], cache_path=str(path.relative_to(ROOT)),
                                cache_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                centre_distance_m=radius, height_m=h0, profiles=profiles))
    out = dict(method='Spherical geodesic from published crater centre through point; +/-3 km radial search, bilinear native 20 m pixels; 5 m sampling does not create 5 m terrain resolution.',
               limits='Local radial maximum is not a surveyed geological crest. USGS centre precision and DEM/product choice affect the result. Exact catalogue source match is a separate question.', rows=results)
    (ROOT/'docs/task_s_jiyong/rim_profiles.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    print(json.dumps(out,indent=2))


if __name__ == '__main__':
    main()
