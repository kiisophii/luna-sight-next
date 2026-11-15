"""Analytic and provenance regressions for Task Y (no remote requests)."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))


class TerrainYTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PIPELINE / 'build_terrain_y.py'
        if path.exists():
            spec = importlib.util.spec_from_file_location('terrain_y', path)
            cls.y = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.y)
        else:
            cls.y = None

    def setUp(self):
        self.assertIsNotNone(self.y, 'Task Y producer must exist')

    def grid(self, res=5, n=31):
        x = (np.arange(n) - n // 2) * res + 12345
        y = -(np.arange(n) - n // 2) * res - 54321
        return x, y

    def test_plane_slope_exact_coordinate_and_projection_height_scale(self):
        x, y = self.grid()
        h = 2000 + 0.2 * (x[None, :] - x[15]) - 0.3 * (y[:, None] - y[15])
        slope = self.y.native_slopes(h, x, y, 5)
        k = 1 + (x[None, :] ** 2 + y[:, None] ** 2) / (4 * self.y.RADIUS ** 2)
        expected = np.degrees(np.arctan(np.hypot(.2, .3) * k * self.y.RADIUS / (self.y.RADIUS + h)))
        np.testing.assert_allclose(slope[1:-1, 1:-1], expected[1:-1, 1:-1], atol=1e-10)
        sx, sy = x[15] + 1.7, y[15] + 2.1
        sh = 2000 + .2 * 1.7 - .3 * 2.1
        sk = 1 + (sx ** 2 + sy ** 2) / (4 * self.y.RADIUS ** 2)
        want = np.degrees(np.arctan(np.hypot(.2, .3) * sk * self.y.RADIUS / (self.y.RADIUS + sh)))
        self.assertAlmostEqual(self.y.landing_slope(h, x, y, sx, sy, 5), want, places=10)

    def test_planar_roughness_zero_even_with_large_height_offset(self):
        x, y = self.grid()
        h = 1e8 + .2 * x[None, :] - .3 * y[:, None]
        rms = self.y.roughness_rms(h, 5, 11)
        self.assertLess(float(np.nanmax(rms)), 1e-7)

    def test_roughness_known_residual_and_explicit_lstsq(self):
        x, y = self.grid(n=9)
        h = np.full((9, 9), 1000.)
        h[4, 4] += 9
        rms = self.y.roughness_rms(h, 5, 3)
        self.assertAlmostEqual(rms[4, 4], np.sqrt(8), places=12)
        rng = np.random.default_rng(42)
        h += rng.normal(size=h.shape)
        rms = self.y.roughness_rms(h, 5, 5)
        xx, yy = np.meshgrid(np.arange(-2, 3) * 5., np.arange(-2, 3) * -5.)
        design = np.column_stack([np.ones(25), xx.ravel(), yy.ravel()])
        z = h[2:7, 2:7].ravel()
        residual = z - design @ np.linalg.lstsq(design, z, rcond=None)[0]
        self.assertAlmostEqual(rms[4, 4], np.sqrt(np.mean(residual ** 2)), places=11)

    def test_geodesic_radius_and_horizontal_area_weights(self):
        r = self.y.RADIUS
        angle = 1000 / r
        projected = 2 * r * np.tan(angle / 2)
        self.assertAlmostEqual(float(self.y.geodesic_distance(projected, 0., 0., 0.)), 1000, places=9)
        weights = self.y.area_weights(np.array([0., 2 * r]), 0., 10)
        np.testing.assert_allclose(weights, [100, 25])
        stats = self.y.summarize_slopes(np.array([1., 20.]), np.array([100., 25.]), [8, 15])
        self.assertEqual(stats['flat_fraction'], {'8': .8, '15': .8})
        self.assertEqual(stats['median_deg'], 10.5)
        self.assertEqual(stats['sampled_area_m2'], 125)

    def test_missing_derivative_neighbour_rejects_coverage(self):
        site = dict(id='TEST', lat=-90., lon=0.)
        x = np.arange(-1200, 1201, 20.)
        y = x[::-1]
        h = np.zeros((len(y), len(x)))
        h[len(y)//2, len(x)//2] = np.nan
        with self.assertRaises(self.y.SourceCoverageError):
            self.y.describe_window(h, x, y, site, 20, [8, 15])

    def test_roughness_window_sparse20m_and_radius_counts(self):
        site = dict(id='TEST', lat=-90., lon=0.)
        x = np.arange(-1200, 1201, 20.)
        y = x[::-1]
        h = np.zeros((len(y), len(x)))
        method, landing, slopes, rough = self.y.describe_window(h, x, y, site, 20, [8, 15])
        self.assertEqual(method['roughness_window_cells'], 3)
        self.assertEqual(method['roughness_sample_center_span_ground_m'], 40)
        self.assertEqual(method['slope_center_span_projected_m'], 40)
        self.assertEqual(method['slope_footprint_projected_m'], 60)
        self.assertEqual(landing, 0)
        self.assertGreater(slopes['1000']['n'], slopes['500']['n'])
        self.assertEqual(rough['n'], slopes['500']['n'])

    def test_relay_column_center_exact_provenance_and_unique(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'relay.json'
            relay = dict(lat=0, lon=0, params={'slope_box_m': 250}, dem_sources=[{'name': 'LDEM_64'}],
                         candidates={'e_m': [100, 0], 'n_m': [0, 0], 'slope_deg': [7.3, 3.7]}, mock=False)
            path.write_text(json.dumps(relay), encoding='utf-8')
            box, source = self.y.relay_comparison(path, root, {'lat': 0, 'lon': 0})
            self.assertEqual(box['slope_deg'], 3.7)
            self.assertEqual(box['candidate_index'], 1)
            self.assertEqual(box['source_sha256'], self.y.file_sha256(path))
            self.assertEqual(source, relay['dem_sources'])
            relay['candidates']['e_m'] = [0, 0]
            path.write_text(json.dumps(relay), encoding='utf-8')
            with self.assertRaises(ValueError):
                self.y.relay_comparison(path, root, {'lat': 0, 'lon': 0})

    def test_resume_requires_current_inputs_and_intact_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'TEST.json'
            inputs = self.y.make_inputs({'id': 'TEST'}, 'relay', 'source', {'thresholds_deg': [8, 15]})
            product = {'id': 'TEST', 'inputs': inputs, 'mock': False, 'schema_version': 1}
            product['content_sha256'] = self.y.canonical_hash(product)
            self.y.atomic_json(path, product)
            self.assertTrue(self.y.is_resumable(path, inputs))
            changed = self.y.make_inputs({'id': 'TEST'}, 'relay-new', 'source', {'thresholds_deg': [8, 15]})
            self.assertFalse(self.y.is_resumable(path, changed))
            product['inputs']['parameters']['thresholds_deg'] = [9, 15]
            self.y.atomic_json(path, product)
            self.assertFalse(self.y.is_resumable(path, inputs))

    def test_resume_rejects_changed_numeric_output_with_unchanged_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'TEST.json'
            inputs = self.y.make_inputs({'id': 'TEST'}, 'relay', 'source', {'thresholds_deg': [8, 15]})
            product = dict(id='TEST', inputs=inputs, mock=False, schema_version=1, landing_slope_deg=3.5)
            product['content_sha256'] = self.y.canonical_hash(product)
            self.y.atomic_json(path, product)
            self.assertTrue(self.y.is_resumable(path, inputs))
            product['landing_slope_deg'] = 72.0
            self.y.atomic_json(path, product)
            self.assertFalse(self.y.is_resumable(path, inputs))

    def write_native_window(self, root, site, res):
        x = np.arange(-1100, 1101, float(res))
        path = root / str(res) / (site['id'] + '.npz')
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, height_m=np.zeros((len(x), len(x))), x_m=x, y_m=x[::-1],
                 metadata=json.dumps({'source_url': f'https://example.test/{res}.tif'}))

    def test_all_nodata_source_selects_coarser_valid_product(self):
        site = dict(id='TEST', lat=-90., lon=0.)
        with tempfile.TemporaryDirectory(dir=self.y.ROOT) as folder:
            root = Path(folder)
            def fetch(site, res, radius, root, **kwargs):
                if res == 5:
                    raise ValueError('Window contains no valid elevations')
                self.write_native_window(root, site, res)
            with patch.object(self.y.fp, 'fetch', side_effect=fetch):
                source, _ = self.y.acquire(site, root, [8, 15])
            self.assertEqual(source['resolution_m'], 10)
            self.assertEqual(source['finer_unavailable'][0]['resolution_m'], 5)
            self.assertIn('no valid elevations', source['finer_unavailable'][0]['reason'])

    def test_partial_extra_storage_margin_preserves_finer_valid_product(self):
        site = dict(id='TEST', lat=-90., lon=0.)
        with tempfile.TemporaryDirectory(dir=self.y.ROOT) as folder:
            root = Path(folder)
            def fetch(site, res, radius, root, *, allow_partial=False):
                if res == 5 and not allow_partial:
                    raise self.y.SourceCoverageError('Requested window exceeds source coverage')
                self.write_native_window(root, site, res)
            with patch.object(self.y.fp, 'fetch', side_effect=fetch):
                source, _ = self.y.acquire(site, root, [8, 15])
            self.assertEqual(source['resolution_m'], 5)
            self.assertEqual(source['finer_unavailable'], [])

    def test_source_validation_and_transport_errors_are_not_coverage(self):
        import requests
        site = dict(id='TEST', lat=-90., lon=0.)
        for error in (ValueError('Invalid Range response or changed source'),
                      requests.ConnectionError('Connection interrupted')):
            with self.subTest(error=str(error)):
                with patch.object(self.y.fp, 'fetch', side_effect=error) as fetch:
                    with self.assertRaises(type(error)):
                        self.y.acquire(site, self.y.ROOT / 'data/processed/terrain_y/raw', [8, 15])
                    self.assertEqual(fetch.call_count, 1)


if __name__ == '__main__':
    unittest.main()
