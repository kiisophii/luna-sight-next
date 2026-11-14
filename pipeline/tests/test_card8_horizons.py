"""Behavior checks for the card-8 calculation and resolution comparison."""
import importlib
import numpy as np
import pytest
from pipeline import horizon as hz


def module():
    return importlib.import_module('pipeline.card8_horizons')


def test_near_field_replacement_preserves_far_field_and_original_chain():
    card = module()
    site = dict(id='TEST', lat=-89, lon=0)
    chain = [(hz.FunctionSampler(lambda la, lo, v=v: np.full_like(la, v), str(v), v), radius)
             for v, radius in [(5, 3), (10, 25), (60, 60), (80, 60), (240, 200), (1900, 300)]]
    altered = card.sensitivity_chain(site, chain, 80)
    distance = np.array([0, 1, 2.99, 3.01, 30, 100, 250.])
    lat, lon = hz.destination(-89, 0, np.zeros(7), distance * 1000)
    assert hz.sample_chain(altered, lat, lon, distance) == pytest.approx([80, 80, 80, 10, 60, 240, 1900])
    assert hz.sample_chain(chain, lat, lon, distance) == pytest.approx([5, 5, 5, 10, 60, 240, 1900])


def test_missing_coarse_near_field_is_not_silently_replaced_by_fine_data():
    card = module()
    site = dict(id='TEST', lat=-89, lon=0)
    fine = hz.FunctionSampler(lambda la,lo: np.zeros_like(la), 'FINE', 5)
    coarse = hz.FunctionSampler(lambda la,lo: np.full_like(la,np.nan), 'COARSE', 80)
    chain = card.sensitivity_chain(site, [(fine,300),(coarse,300)], 80)
    assert np.isnan(hz.sample_chain(chain,np.array([-89.]),np.array([0.]),np.array([0.]))[0])


def test_incomplete_results_cannot_be_published():
    card = module()
    result = dict(mask=np.zeros(720), n_missing=1)
    with pytest.raises(ValueError, match='missing'):
        card.require_complete(result)
    result['n_missing'] = 0
    result['mask'][5] = np.nan
    with pytest.raises(ValueError, match='finite'):
        card.require_complete(result)


def test_nearby_terrain_is_included_by_card8_sampling():
    card = module()
    # A 5 m high ring at 40-60 m must not disappear behind a 200 m inner cutoff.
    lat0, lon0 = -89., 0.
    def surface(lat,lon):
        a=np.radians(lat); b=np.radians(lon)
        v=np.sin((a-np.radians(lat0))/2)**2+np.cos(a)*np.cos(np.radians(lat0))*np.sin(b/2)**2
        distance=2*1737400*np.arcsin(np.sqrt(np.clip(v,0,1)))
        return np.where((distance>=40)&(distance<=60),5.,0.)
    result=card.calculate(dict(lat=lat0,lon=lon0),[(hz.FunctionSampler(surface),300)],n_steps=1200)
    assert np.min(result['mask']) > 4.0
