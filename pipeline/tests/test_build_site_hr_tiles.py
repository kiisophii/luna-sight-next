"""Offline tests for pipeline/build_site_hr_tiles.py (no DEM files needed).

python -m unittest pipeline.tests.test_build_site_hr_tiles -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_globe_tiles as bg  # noqa: E402
import build_site_hr_tiles as hr  # noqa: E402


class Encoding(unittest.TestCase):
    def test_png_round_trip_half_metre(self):
        rng = np.random.default_rng(0)
        h = rng.uniform(-9000, 10000, (bg.N + 3, bg.N + 3)).astype(np.float32)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 't.png'
            bg.encode_png(h, p)
            back = hr.decode_png(p)
        self.assertEqual(back.shape, h.shape)
        # 0.5 m steps -> <= 0.25 m, plus float32 precision of the input (~1e-3 m near 10 km)
        self.assertLessEqual(float(np.abs(back - h).max()), 0.25 + 2e-3)


class Geometry(unittest.TestCase):
    def test_z8_children_share_edges_and_parent_vertices(self):
        z, x, y = hr.Z_NEW, 128, 130
        lat, lon = bg.tile_sample_grid('south', z, x, y)
        lat_e, lon_e = bg.tile_sample_grid('south', z, x + 1, y)
        # vertex column 256 of a tile == vertex column 0 of its east neighbour (bordered index +1)
        np.testing.assert_allclose(lat[:, bg.N + 1], lat_e[:, 1], atol=1e-9)
        np.testing.assert_allclose(lon[:, bg.N + 1], lon_e[:, 1], atol=1e-9)
        # every 2nd child vertex coincides with a parent vertex
        plat, plon = bg.tile_sample_grid('south', z - 1, x // 2, y // 2)
        ox, oy = (x % 2) * 128, (y % 2) * 128
        np.testing.assert_allclose(lat[1:bg.N + 2:2, 1:bg.N + 2:2], plat[1 + oy:1 + oy + 129, 1 + ox:1 + ox + 129], atol=1e-9)

    def test_spacing(self):
        self.assertAlmostEqual(bg.tile_spacing_m('south', hr.Z_NEW), 17.09, places=2)
        self.assertAlmostEqual(bg.tile_spacing_m('south', hr.Z_PARENT), 34.18, places=2)


if __name__ == '__main__':
    unittest.main()
