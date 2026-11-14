"""Analytic controls for the independent verifier (no producer imports)."""
import gzip
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from independent_map_polar_check import BrowserTiles, R, interpolate, march, metrics


def test_bilinear_wrap_and_missing():
    a=np.array([[0.,10.,20.],[30.,40.,50.]])
    assert interpolate(a,[.5],[.5])[0]==20
    assert interpolate(a,[.5],[2.5],wrap=True)[0]==25
    assert np.isnan(interpolate(a,[.5],[-.1])[0])


def test_flat_sphere_horizon_is_analytic_and_azimuth_invariant():
    distance=np.array([5.,100.,1000.,10000.])
    out=march(-87.1,179.9,[(lambda lat,lon:np.zeros_like(lat),300000)],distance,24)
    expected=np.rad2deg(np.arctan2(R*np.cos(distance/R)-(R+2),R*np.sin(distance/R))).max()
    np.testing.assert_allclose(out['mask'],expected,atol=1e-12)


def test_disk_mean_is_distinct_from_app_sunlit_time():
    el=np.deg2rad(.1333)
    observer=np.array([(R+2)/1000,0.,0.])
    v=observer+1e8*np.array([np.sin(el),np.cos(el),0.])
    ep=np.array([list(v)+[400000.,0.,0.]])
    h=dict(h0_m=0,mask=[0.]*720)
    disk=metrics(0,0,h,ep)
    binary=metrics(0,0,h,ep,sunlit_time=True)
    assert .80<disk['sun']<.81
    assert binary==dict(sun=1.,earth=1.,both=1.)


def test_predictor_decode_fixed_integer_fixture(tmp_path):
    reader=object.__new__(BrowserTiles);reader.root=tmp_path;reader.cache={}
    # Desired encoded integer heights [[100,103],[105,110]] at q=.25 m.
    (tmp_path/'p.gz').write_bytes(gzip.compress((100).to_bytes(4,'little',signed=True)+
        np.array([0,3,5,2],dtype='<i2').tobytes()))
    np.testing.assert_array_equal(reader.tile('p.gz',2,.25),[[25.,25.75],[26.25,27.5]])
    (tmp_path/'g.gz').write_bytes(gzip.compress(np.array([10,3,20,-4],dtype='<i2').tobytes()))
    np.testing.assert_array_equal(reader.tile('g.gz',2),[[10,13],[20,16]])
