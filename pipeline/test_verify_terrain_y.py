"""Analytic checks for the separate Task Y author verifier."""
import unittest

import numpy as np

from verify_terrain_y import (
    RADIUS, bilinear, circle_summary, fit_centres, physical_slope,
    project_site, spherical_distances,
)


class IndependentTerrainTests(unittest.TestCase):
    def setUp(self):
        self.x = np.arange(-40, 41, 10, dtype=float)
        self.y = self.x[::-1].copy()
        self.xx, self.yy = np.meshgrid(self.x, self.y)

    def test_plane_and_height_offset(self):
        z = 1000 + 0.2*self.xx - 0.3*self.yy
        centres = np.array([[3, 3], [4, 4], [5, 5]])
        coeff, rms = fit_centres(z, self.x, self.y, centres, 3)
        shifted, shifted_rms = fit_centres(z + 100000, self.x, self.y, centres, 3)
        np.testing.assert_allclose(coeff[:, :2], np.tile([0.2, -0.3], (3, 1)), atol=1e-12)
        np.testing.assert_allclose(shifted[:, :2], coeff[:, :2], atol=1e-10)
        np.testing.assert_allclose(rms, 0, atol=1e-10)
        np.testing.assert_allclose(shifted_rms, 0, atol=1e-9)

    def test_checkerboard_known_residual(self):
        z = (-1.0)**np.indices((9, 9)).sum(axis=0)
        _, rms = fit_centres(z, self.x, self.y, np.array([[4, 4]]), 5)
        self.assertAlmostEqual(rms[0], np.sqrt(624/625), places=13)

    def test_bilinear_exact_off_grid(self):
        z = 7 + 0.2*self.xx - 0.3*self.yy + 0.01*self.xx*self.yy
        xp, yp = np.array([-3.2, 8.7]), np.array([2.4, -12.3])
        np.testing.assert_allclose(bilinear(z, self.x, self.y, xp, yp),
                                   7+0.2*xp-0.3*yp+0.01*xp*yp, atol=1e-12)
        with self.assertRaises(ValueError):
            bilinear(z, self.x, self.y, np.array([100]), np.array([0]))

    def test_projection_distance_and_height_scale(self):
        x, y = project_site(-89, 0)
        self.assertAlmostEqual(x, 0)
        self.assertAlmostEqual(y, 2*RADIUS*np.tan(np.deg2rad(0.5)))
        dist = spherical_distances(np.array([0, x]), np.array([0, y]), -90, 0)
        np.testing.assert_allclose(dist, [0, RADIUS*np.pi/180], atol=1e-8)
        result = physical_slope(np.array([1.0]), np.array([0.0]),
                                np.array([0.0]), np.array([0.0]), np.array([RADIUS]))
        self.assertAlmostEqual(result[0], np.rad2deg(np.arctan(0.5)))

    def test_flat_area_weighting_and_inclusive_boundary(self):
        result = circle_summary(np.array([0., 10., 20.]), np.array([0., 100., 101.]),
                                np.array([1., 3., 100.]), 100, [8, 15])
        self.assertEqual(result['n'], 2)
        self.assertEqual(result['flat_fraction']['8'], 0.25)
        self.assertEqual(result['flat_fraction']['15'], 1.0)
        self.assertEqual(result['sampled_area_m2'], 4)


if __name__ == '__main__':
    unittest.main()
