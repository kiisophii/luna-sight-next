"""Z4 author checks: geometry boundaries, eligibility and published provenance."""
import csv
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from detail_history import geometry, nearest_landings, build_history, normalized_sha256


class HistoryTests(unittest.TestCase):
    def test_dateline_takes_short_arc_and_east_bearing(self):
        distance, bearing, status = geometry(0, 179, 0, -179)
        self.assertAlmostEqual(distance, 60646.700848299, places=6)
        self.assertAlmostEqual(bearing, 90)
        self.assertEqual(status, 'defined')

    def test_north_south_and_polar_origin(self):
        distance, bearing, status = geometry(-89, 0, -89, 180)
        self.assertAlmostEqual(distance, 60646.700848299, places=6)
        self.assertAlmostEqual(bearing, 180)
        distance, bearing, status = geometry(-90, 17, -89, 100)
        self.assertAlmostEqual(distance, 30323.3504241495, places=6)
        self.assertIsNone(bearing)
        self.assertEqual(status, 'origin_pole')

    def test_coincident_and_antipodal_bearings_are_undefined(self):
        for coordinates, expected in [((0, 180, 0, -180), 'coincident'),
                                      ((90, 0, 90, 80), 'coincident'),
                                      ((10, 23, -10, -157), 'antipodal'),
                                      ((0, 0, 0, 180), 'antipodal')]:
            distance, bearing, status = geometry(*coordinates)
            self.assertIsNone(bearing)
            self.assertEqual(status, expected)
            self.assertAlmostEqual(distance, math.pi * 1737400 if expected == 'antipodal' else 0)

    def test_invalid_coordinates_fail_closed(self):
        for coordinates in [(91, 0, 0, 0), (0, 181, 0, 0), (math.nan, 0, 0, 0)]:
            with self.assertRaises(ValueError):
                geometry(*coordinates)

    def test_self_exclusion_future_exclusion_and_id_tie_break(self):
        site = {'id': 'SELF', 'lat': 0, 'lon': 0}
        missions = [dict(id=sid, lat=0, lon=lon, landing_utc=date,
                         official_source_url='https://www.nasa.gov/')
                    for sid, lon, date in [('SELF', 0, '1969-01-01T00:00:00Z'),
                                          ('FUTURE', .01, '2027-01-01T00:00:00Z'),
                                          ('B', -1, '1970-01-01T00:00:00Z'),
                                          ('A', 1, '1970-01-01T00:00:00Z'),
                                          ('C', 2, '1970-01-01T00:00:00Z')]]
        nearest = nearest_landings(site, missions, '2026-11-15T00:00:00Z')
        self.assertEqual([m['id'] for m in nearest], ['A', 'B', 'C'])
        self.assertEqual([m['rank'] for m in nearest], [1, 2, 3])

    def test_all_sites_preserve_task_r_pool_and_coordinates(self):
        product = build_history(ROOT)
        sites = json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8'))
        with (ROOT / 'docs/task_r_landings.csv').open(encoding='utf-8', newline='') as stream:
            records = {r['id']: r for r in csv.DictReader(stream)}
        self.assertEqual(len(product['sites']), 33)
        self.assertEqual(len(product['missions']), 18)
        self.assertEqual({s['id'] for s in sites}, {s['id'] for s in product['sites']})
        self.assertEqual(set(records), {m['id'] for m in product['missions']})
        for mission in product['missions']:
            self.assertEqual((mission['lat'], mission['lon']),
                             (float(records[mission['id']]['lat']), float(records[mission['id']]['lon'])))
            self.assertTrue(mission['official_source_url'].startswith('https://'))
        for site in product['sites']:
            self.assertEqual(len(site['nearest']), 3)
            self.assertNotIn(site['id'], [n['id'] for n in site['nearest']])
            self.assertTrue(all(n['id'] in records for n in site['nearest']))
            self.assertEqual([n['distance_m'] for n in site['nearest']],
                             sorted(n['distance_m'] for n in site['nearest']))
        for record in product['provenance']['inputs']:
            self.assertEqual(record['sha256'], normalized_sha256(ROOT / record['path']))


if __name__ == '__main__':
    unittest.main()
