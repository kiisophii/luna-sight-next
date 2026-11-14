"""Card 1 checks: analytic geometry, UTC, stored samples and interpolation.

Run from the repository root: python -m unittest discover -s pipeline -p test_ephem.py -v
Run ephem.py first. No requests are made when kernels are already cached.
"""
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import ephem
from ephem import ROOT, EPOCH, Ephemeris, az_el
from validate_ephem import differences


class GeometryTests(unittest.TestCase):
    def test_known_cardinal_rays_and_earth_parallax(self):
        # At lat=lon=0, up=X, east=Y, north=Z. A body on the local
        # horizontal plane is at x=observer radius, not at x=0.
        r = ephem.R_MOON_KM + 0.002
        values = np.array([[r, 100, 0, r, 0, 100],
                           [r, -100, 0, r, 0, -100]], dtype=float)
        np.testing.assert_allclose(az_el(values, 0, 0, body="sun"), [[90, 0], [270, 0]], atol=1e-10)
        np.testing.assert_allclose(az_el(values, 0, 0, body="earth"), [[0, 0], [180, 0]], atol=1e-10)

    def test_site_validation(self):
        for args in [(91, 0, 0), (0, 181, 0), (0, 0, float("nan"))]:
            with self.assertRaises(ValueError):
                az_el(np.zeros(6), *args)

    def test_interrupted_generation_resumes_at_flushed_chunk(self):
        class Interrupted:
            calls = 0

            def vectors(self, dates):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("simulated interruption")
                return np.ones((len(dates), 6))

        class Restarted:
            seen = []

            def vectors(self, dates):
                self.seen.extend(dates)
                return np.ones((len(dates), 6))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(ephem, "ROOT", root):
                output = root / "test.bin"
                stop = EPOCH + timedelta(hours=5)
                with self.assertRaisesRegex(RuntimeError, "simulated"):
                    ephem.generate(Interrupted(), EPOCH, stop, 1, output, {"test": True}, 2)
                restarted = Restarted()
                ephem.generate(restarted, EPOCH, stop, 1, output, {"test": True}, 2)
                self.assertEqual(restarted.seen[0], EPOCH + timedelta(hours=2))
                self.assertEqual(output.stat().st_size, 5 * 24)
                np.testing.assert_array_equal(np.fromfile(output, dtype="<f4"), np.ones(30))


@unittest.skipUnless((ROOT / "web/data/ephem.bin").exists()
                     and (ROOT / "data/raw/kernels/de440s.bsp").exists(), "generate real data first")
class GeneratedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Ephemeris()
        cls.data = np.fromfile(ROOT / "web/data/ephem.bin", dtype="<f4").reshape(-1, 6)

    def test_utc_and_endpoints(self):
        self.assertEqual(self.data.shape, (43824, 6))
        self.assertEqual(EPOCH + timedelta(hours=43823), datetime(2030, 12, 31, 23, tzinfo=timezone.utc))
        # Explicit LSK leap offsets must agree with Skyfield's builtin table.
        from skyfield.api import load
        dates = [datetime(2016, 12, 31, 23, 59, 59, tzinfo=timezone.utc), EPOCH]
        np.testing.assert_allclose(self.engine.ts.from_datetimes(dates).tai,
                                   load.timescale(builtin=True).from_datetimes(dates).tai, atol=0, rtol=0)
        exact = self.engine.vectors([EPOCH, EPOCH + timedelta(hours=43823)])
        np.testing.assert_array_equal(self.data[[0, -1]], exact.astype("<f4"))

    def test_validation_series_endpoints(self):
        series = np.load(ROOT / "data/processed/ephem_2020-2038_2h.npz")
        self.assertEqual(series["vectors"].shape, (81444, 6))
        self.assertEqual(series["vectors"].dtype, np.dtype("<f4"))
        self.assertEqual(series["hour_index"][0], -52608)
        self.assertEqual(series["hour_index"][-1], 110278)
        dates = [datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2038, 7, 31, 22, tzinfo=timezone.utc)]
        exact = self.engine.vectors(dates)
        np.testing.assert_array_equal(series["vectors"][[0, -1]], exact.astype("<f4"))

    def test_hourly_interpolation_and_surface_height_over_five_years(self):
        rng = np.random.default_rng(42)
        hours = rng.uniform(0, len(self.data) - 1, 240)
        dates = [EPOCH + timedelta(hours=float(h)) for h in hours]
        lo = np.floor(hours).astype(int)
        alpha = (hours - lo)[:, None]
        interpolated = self.data[lo] * (1 - alpha) + self.data[lo + 1] * alpha
        rows = []
        for lat, lon, height in [(-89.5, 0, 0), (20.1908, 30.7717, -1800),
                                  (-45.4446, 177.5991, -5900), (0, 0, 1000)]:
            for body in ("sun", "earth"):
                ours = az_el(interpolated, lat, lon, height, body)
                direct = self.engine.direct_az_el(lat, lon, height, dates, body)
                stats = differences(ours, direct)
                self.assertLess(stats["max_sky_deg"], 0.01)
                rows.append({"lat": lat, "lon": lon, "terrain_height_m": height,
                             "body": body, **stats})
        ephem.write_json(ROOT / "docs/ephem_interpolation_check.json", {
            "seed": 42, "n_times": 240, "window": "2026-2030",
            "height_note": "Synthetic height test values, not surveyed site heights",
            "criterion": "max 3D angular separation < 0.01 deg; azimuth singular at zenith",
            "results": rows})


if __name__ == "__main__":
    unittest.main()
