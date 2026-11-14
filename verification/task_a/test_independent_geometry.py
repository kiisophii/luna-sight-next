"""Analytic controls for the independent verifier, not producer-output replicas."""
import ast
import math
from pathlib import Path
import unittest

import numpy as np
import verify_horizons_independent as check


class GeometryControls(unittest.TestCase):
    def test_cardinal_great_circle_and_wrap(self):
        arc = check.R * math.pi / 180
        lat, lon = check.destinations(0, 179.5, np.array([0, 90, 180, 270]), np.array([arc]))
        np.testing.assert_allclose(lat[:, 0], [1, 0, -1, 0], atol=1e-12)
        np.testing.assert_allclose(lon[:, 0], [179.5, -179.5, 179.5, 178.5], atol=1e-12)

    def test_polar_projection_cardinals(self):
        radius = 2 * check.R * math.tan(math.radians(1) / 2)
        x, y = check.stereographic(np.full(4, -89), np.array([0,90,180,-90]))
        np.testing.assert_allclose(x, [0,radius,0,-radius], atol=1e-8)
        np.testing.assert_allclose(y, [radius,0,-radius,0], atol=1e-8)

    def test_interpolation_plane_and_outside(self):
        a = np.array([[0,2,4],[10,12,14],[20,22,24]], dtype=np.float32)
        v = check.bilinear(a,np.array([.5,1.75,-.1]),np.array([.25,1.5,0]))
        np.testing.assert_allclose(v[:2],[5.5,20.5])
        self.assertTrue(np.isnan(v[2]))
        w = check.bilinear(a,np.array([1.]),np.array([2.5]),True)
        self.assertEqual(w[0],12)

    def test_curvature_dip_on_smooth_sphere(self):
        ds = check.distances(.005)
        th = ds/check.R
        vertical = -2-check.R*2*np.sin(th/2)**2
        el = np.degrees(np.arctan2(vertical,check.R*np.sin(th)))
        exact = -math.degrees(math.acos(check.R/(check.R+2)))
        self.assertLess(abs(float(el.max())-exact),.00001)
        self.assertGreater(ds[np.argmax(el)],2000)
        self.assertLess(ds[np.argmax(el)],3000)

    def test_no_production_imports(self):
        tree=ast.parse(Path(check.__file__).read_text(encoding='utf-8'))
        names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names.extend(n.name for n in node.names)
            if isinstance(node,ast.ImportFrom):names.append(node.module or '')
        self.assertFalse(any(n.startswith(('pipeline','web.')) for n in names))

    def test_non_source_network_is_blocked_before_send(self):
        with self.assertRaisesRegex(ValueError,'Blocked non-source'):
            check.session().get('https://example.invalid/not-a-dem',timeout=1)


if __name__=='__main__':
    unittest.main()
