"""Analytic cases for the independent geodesic/ECEF verifier."""
import importlib
import math
import numpy as np
import pytest


def test_independent_flat_sphere_matches_analytic_horizon():
    verify = importlib.import_module('pipeline.verify_card8_horizons')
    distance = np.linspace(5, 10000, 10001)
    result = verify.trace(dict(lat=-89,lon=177), lambda la,lo,d: np.zeros_like(la),
                          [0,90,180,270], distance)
    want = -math.degrees(math.acos(1737400/1737402))
    assert [row['elevation_deg'] for row in result] == pytest.approx([want]*4,abs=1e-6)


def test_independent_trace_rejects_uncovered_terrain():
    verify = importlib.import_module('pipeline.verify_card8_horizons')
    def missing(la,lo,d):
        return np.where(d > 0.5, np.nan, 0.)
    with pytest.raises(ValueError,match='missing'):
        verify.trace(dict(lat=-89,lon=0), missing, [0], np.array([5.,1000.]))
