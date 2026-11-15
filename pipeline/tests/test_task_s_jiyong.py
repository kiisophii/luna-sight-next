"""Guard against longitude-wrap and missing-source false passes in task S."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / 'verify_task_s_jiyong.py'


class CoordinateAuditTests(unittest.TestCase):
    def test_checker_exists(self):
        self.assertTrue(SCRIPT.exists(), 'Independent coordinate checker is not implemented')

    def test_comparison(self):
        if not SCRIPT.exists():
            self.skipTest('Checker not implemented')
        spec = importlib.util.spec_from_file_location('task_s_check', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.normalize_lon('197.19'), module.Decimal('-162.81'))
        self.assertEqual(module.normalize_lon('-180'), module.normalize_lon('180'))
        self.assertEqual(module.normalize_lon('-540'), module.Decimal('-180'))
        self.assertEqual(module.distance_m(0, 180, 0, -180), 0)
        self.assertAlmostEqual(module.distance_m(0, 0, 0, 1), 30323.350423, places=5)
        self.assertGreater(module.distance_m(-45.4561, 177.5885, -45.4562, 177.5885), 3)


if __name__ == '__main__':
    unittest.main()
