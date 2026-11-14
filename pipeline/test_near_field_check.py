"""Analytic tests for footprint rejection and the explicitly limited spike heuristic."""
import numpy as np
from near_field_check import footprint, positive_spike


def product(pole):
    return dict(product='TEST',pole=pole,metadata=dict(MAP_SCALE=240,
        LINE_PROJECTION_OFFSET=3209.5,SAMPLE_PROJECTION_OFFSET=3209.5,
        LINES=6420,LINE_SAMPLES=6420))


def test_outside_extent_never_returns_zero_visibility():
    for pole in ('N','S'):
        for lat,lon in [(0.67416,23.47314),(-3.0128,-23.4219),(3.7863,56.6242),
                        (43.0576,-51.9161),(7.585,-58.725)]:
            result=footprint(dict(lat=lat,lon=lon),product(pole))
            assert result['entire_300m_disc_outside']
            assert result['center'] is result['min_300m'] is result['max_300m'] is None


def test_polar_site_requires_real_pixel_read():
    result=footprint(dict(lat=-89.9,lon=30),product('S'))
    assert not result['entire_300m_disc_outside']
    assert result['status']=='requires_pixel_read'


def test_positive_spike_heuristic_does_not_flag_a_planar_slope():
    assert positive_spike(10.,np.zeros(8))['candidate']
    assert not positive_spike(0.,np.array([-3,-2,-1,-1,1,1,2,3]))['candidate']
    assert not positive_spike(.2,np.zeros(8))['candidate']
