"""Offline tests for pipeline/verify_card9.py helpers (no network, no DEM files).

python -m unittest pipeline.tests.test_verify_card9 -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_card9 as V  # noqa: E402


class Geometry(unittest.TestCase):
    def test_ray_points_distance_and_azimuth(self):
        # 100 km due north / east from (10 N, 20 E): great-circle distance and bearing preserved
        p, la, lo = V.ray_points(10.0, 20.0, [0.0, 90.0], [100e3])
        u = V.unit(10.0, 20.0)
        for i in range(2):
            ang = math.acos(float(np.clip(p[i, 0] @ u, -1, 1)))
            self.assertAlmostEqual(ang * V.R, 100e3, delta=1e-3)
        self.assertGreater(la[0, 0], 10.0)                        # north
        self.assertAlmostEqual(lo[0, 0], 20.0, places=9)
        self.assertGreater(lo[1, 0], 20.0)                        # east

    def test_flat_sphere_horizon_is_dip_angle(self):
        # bare sphere, observer 2 m: horizon dip = -acos(R/(R+2)) at every azimuth
        flat = lambda la, lo, d: np.zeros(la.shape)  # noqa: E731
        m, _, miss = V.brute_mask(0.0, 0.0, [0.0, 123.5], flat, 0.0, 150e3, d_near=5.0)
        dip = -math.degrees(math.acos(V.R / (V.R + 2.0)))
        self.assertEqual(miss, 0)
        np.testing.assert_allclose(m, dip, atol=2e-3)

    def test_obs_height_and_flat_switches(self):
        hill = lambda la, lo, d: np.where(d <= 1000.0, 100.0, 0.0)  # noqa: E731
        m2, _, _ = V.brute_mask(0.0, 0.0, [0.0], hill, 0.0, 150e3)
        m0, _, _ = V.brute_mask(0.0, 0.0, [0.0], hill, 0.0, 150e3, obs=0.0)
        mf, _, _ = V.brute_mask(0.0, 0.0, [0.0], hill, 0.0, 150e3, flat=True)
        self.assertLess(m2[0], m0[0])        # a higher observer sees a lower horizon
        self.assertGreater(mf[0], m2[0])     # flat ground ignores the curvature drop


class Fractions(unittest.TestCase):
    def test_disk_fraction(self):
        self.assertAlmostEqual(float(V.disk_frac(0.0)), 0.5)
        self.assertAlmostEqual(float(V.disk_frac(1.0)), 1.0)
        self.assertAlmostEqual(float(V.disk_frac(-1.0)), 0.0)
        self.assertAlmostEqual(float(V.disk_frac(0.3) + V.disk_frac(-0.3)), 1.0)

    def test_random_points_band_and_repeatability(self):
        a = V.random_points(400, 42)
        b = V.random_points(400, 42)
        np.testing.assert_array_equal(a[0], b[0])
        self.assertTrue(((a[0] >= -85) & (a[0] <= -75)).all())


if __name__ == '__main__':
    unittest.main()
