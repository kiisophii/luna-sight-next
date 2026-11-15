"""Synthetic controls for the independent P/Q validation implementation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location('task_pq_check', Path(__file__).parents[1] / 'task_pq_check.py')
pq = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pq)
REPORT_SPEC = importlib.util.spec_from_file_location('task_pq_report', Path(__file__).parents[1] / 'task_pq_report.py')
reporter = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(reporter)


class PQTests(unittest.TestCase):
    def test_solar_disk_boundary_and_earth_strictness(self):
        self.assertEqual(pq.disk_fraction(np.array([0.0]))[0], 0.5)
        np.testing.assert_equal(pq.disk_fraction(np.array([-1., 1.])), [0., 1.])
        site = {'lat': 0., 'lon': 0.}
        h = {'h0_m': 0., 'mask': [0.] * 4, 'az_step_deg': 90.}
        # Offset makes the topocentric radial component exactly zero.
        eph = np.array([[1737.402, 10000., 0., 1737.402, 10000., 0.]])
        sun, earth = pq.hourly_states(site, h, eph)
        self.assertTrue(sun[0])
        self.assertFalse(earth[0])

    def test_cyclic_horizon(self):
        h = {'mask': [0., 10., 20., 30.], 'az_step_deg': 90.}
        np.testing.assert_allclose(pq.horizon_at(h, np.array([-45., 315., 360.])), [15., 15., 0.])

    def test_runs_and_month_boundaries(self):
        yes, no = pq.runs(np.array([False, True, True, False, False, True]))
        self.assertEqual(yes, [(1, 3), (5, 6)])
        self.assertEqual(no, [(0, 1), (3, 5)])
        self.assertEqual(pq.longest_dark(np.array([False, False, True, False])), 2)
        self.assertEqual(pq.longest_dark(np.array([True, True])), 0)
        self.assertEqual(pq.longest_dark(np.array([False, False])), 2)
        months = pq.months()
        self.assertEqual(len(months), 60)
        self.assertEqual(months[-1][2], 43824)
        self.assertEqual(next(b-a for m,a,b in months if m == '2028-02'), 696)
        self.assertTrue(all(a[2] == b[1] for a,b in zip(months, months[1:])))

    def test_negative_javascript_rounding(self):
        self.assertEqual(pq.js_round(-1.2345, 3), -1.234)
        self.assertEqual(pq.js_round(1.2345, 3), 1.235)

    def test_unrounded_threshold_and_missing_values(self):
        check = pq.Comparisons('S')
        check.number('Q', 'x', 0.1010000001, 0.1, 'pp', 0.1, 4)
        self.assertFalse(check.rows[-1]['pass'])
        check.number('Q', 'x', None, 1., 'h', 1.)
        self.assertFalse(check.rows[-1]['pass'])
        check.number('Q', 'x', float('nan'), 1., 'h', 1.)
        self.assertFalse(check.rows[-1]['pass'])

    def test_missing_extra_interval_and_gap_sort(self):
        check = pq.Comparisons('S')
        states = np.array([False, True, False, True, False])
        expected = pq.window_product(states)
        self.assertEqual([x['start_utc'] for x in expected['longest_gaps']],
                         [pq.utc_hour(0), pq.utc_hour(2), pq.utc_hour(4)])
        actual = dict(expected, visible=expected['visible'][:-1])
        pq.compare_windows(check, 'sun', actual, states)
        self.assertTrue(any(not x['pass'] for x in check.rows))
        check = pq.Comparisons('S')
        pq.compare_windows(check, 'sun', expected, states)
        self.assertTrue(all(x['pass'] for x in check.rows))

    def test_all_visible_and_dark_domain_clipping(self):
        bright = pq.window_product(np.ones(5, dtype=bool))
        dark = pq.window_product(np.zeros(5, dtype=bool))
        self.assertEqual(bright['longest_gaps'], [])
        self.assertEqual(dark['visible'], [])
        self.assertTrue(bright['visible'][0]['clipped_start'])
        self.assertTrue(bright['visible'][0]['clipped_end'])
        self.assertEqual(dark['longest_gaps'][0]['duration_h'], 5)
        ties = pq.window_product(np.tile([False, True], 15))
        self.assertEqual(len(ties['longest_gaps']), 10)
        self.assertEqual(ties['longest_gaps'][-1]['start_utc'], pq.utc_hour(18))

    def test_month_darkness_is_cut_and_lunation_is_709_hours(self):
        check = pq.Comparisons('S')
        sun = np.zeros(pq.N, dtype=bool)
        earth = np.ones(pq.N, dtype=bool)
        eph = np.tile([1., 0., 0., 1., 0., 0.], (pq.N, 1))
        pq.compare_monthly(check, {}, sun, earth, eph)
        rows = {r['field']: r for r in check.rows}
        self.assertEqual(rows['2026-01.series.longest_dark_h']['raw_expected'], 744)
        self.assertEqual(rows['2026-02.series.longest_dark_h']['raw_expected'], 672)
        self.assertEqual(rows['2028-02.series.longest_dark_h']['raw_expected'], 696)
        self.assertEqual(rows['2026-01.lunation.earth_frac']['raw_expected'], 1)
        self.assertEqual(rows['total.longest_dark_h_max_month']['raw_expected'], 744)

    def test_line_endings_accept_only_equivalent_source(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'source.js'
            p.write_bytes(b'line1\r\nline2\r\n')
            expected = pq.hashlib.sha256(b'line1\nline2\n').hexdigest()
            check, differences = pq.Comparisons('S'), []
            pq.compare_source_hash(check, 'P', 'source', expected, p, differences)
            self.assertTrue(check.rows[-1]['pass'])
            self.assertEqual(len(differences), 1)
            pq.compare_source_hash(check, 'P', 'source', 'wrong', p, differences)
            self.assertFalse(check.rows[-1]['pass'])

    def test_invalid_horizon_is_not_silently_flat(self):
        site = {'id': 'S', 'lat': 0., 'lon': 0.}
        with self.assertRaises(ValueError):
            pq.validate_horizon(site, dict(site, obs_height_m=2, mock=True))

    def test_missing_inputs_invalidate_previous_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'docs').mkdir()
            (root/'docs/task_pq_check.md').write_text('PASS stale result')
            result = subprocess.run([sys.executable, str(Path(pq.__file__)), '--root', directory], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root/'docs/task_pq_check.json').read_text())
            self.assertEqual(report['status'], 'ERROR')
            self.assertFalse(report['complete'])
            self.assertNotIn('PASS', (root/'docs/task_pq_check.md').read_text())

    def test_report_refuses_incomplete_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'docs').mkdir()
            table = root/'docs/task_pq_comparisons.csv'
            table.write_text('site,product\n')
            pq.write(root/'docs/task_pq_check.json', dict(status='PASS', complete=True, sites=[], source_hashes={},
                     comparison_file='docs/task_pq_comparisons.csv', comparison_sha256=pq.sha(table)))
            script = Path(pq.__file__).with_name('task_pq_report.py')
            result = subprocess.run([sys.executable, str(script), '--root', directory], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('ERROR', (root/'docs/task_pq_check.md').read_text())

    def test_report_does_not_claim_exact_equality_for_tolerated_difference(self):
        check = pq.Comparisons('S')
        check.number('Q', 'sun_frac', .5001, .5, 'pp', .1, 4)
        check.number('Q', 'longest_dark_h', 11, 10, 'h', 1.)
        self.assertTrue(all(r['pass'] for r in check.rows))
        rows = [{k: str(v) for k, v in r.items()} for r in check.rows]
        count, sentence = reporter.numerical_agreement(rows)
        self.assertEqual(count, 2)
        self.assertNotIn('values equal', sentence)
        self.assertIn('2 numerical values differ', sentence)
        self.assertEqual(reporter.numerical_agreement([])[0], 0)


if __name__ == '__main__':
    unittest.main()
