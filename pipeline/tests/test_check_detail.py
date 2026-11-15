"""Reject malformed detail payloads before they reach the UI."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('check_detail', Path(__file__).parents[1] / 'check_detail.py')
detail = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(detail)


class DetailContractTests(unittest.TestCase):
    def setUp(self):
        self.sites = {'A': {'lat': 0., 'lon': 0.}}
        self.record = {
            'schema_version': 1, 'product': 'nearest_historical_landings', 'radius_m': 1737400,
            'frame': 'MOON_ME_DE421', 'reference_utc': '2026-11-15T00:00:00Z',
            'provenance': {'sha256_normalization': 'CRLF_to_LF', 'inputs': [{'path':p,'sha256':'0'*64} for p in (
                'web/data/sites.json','docs/task_r_landings.csv','docs/detail_z4_sources.json','pipeline/detail_history.py')]},
            'nearest_count': 3, 'mission_count': 18, 'site_count': 1, 'mock': False,
            'missions': [{'id': str(i), 'lat': 0, 'lon': i, 'official_source_url': 'https://www.nasa.gov/'} for i in range(18)],
            'sites': [{'id': 'A', 'lat': 0., 'lon': 0., 'nearest': [
                {'id': str(i), 'rank': i, 'distance_m': i * 100., 'bearing_deg': 90.,
                 'bearing_status': 'defined', 'official_source_url': 'https://www.nasa.gov/'} for i in range(1, 4)]}]
        }

    def test_valid_history(self):
        detail.validate_history(self.record, self.sites)

    def test_missing_query(self):
        self.record['sites'] = []
        with self.assertRaises(ValueError):
            detail.validate_history(self.record, self.sites)

    def test_missing_provenance_or_wrong_frame(self):
        for mutate in (lambda r:r['provenance'].update(inputs=[]),lambda r:r.update(frame='WRONG_FRAME'),
                       lambda r:r.update(reference_utc='2050-01-01T00:00:00Z')):
            r=copy.deepcopy(self.record)
            mutate(r)
            with self.assertRaises(ValueError):
                detail.validate_history(r,self.sites)

    def test_self_or_duplicate_destination(self):
        for replacement in ('A', '2'):
            r = copy.deepcopy(self.record)
            r['sites'][0]['nearest'][0]['id'] = replacement
            with self.assertRaises(ValueError):
                detail.validate_history(r, self.sites)

    def test_time_stats_bad_mean_clipping_or_station(self):
        obj = json.loads((Path(__file__).parents[2] / 'web/data/detail/time_stats/APOLLO11.json').read_text(encoding='utf8'))
        site = {k: obj[k] for k in ('lat', 'lon')}
        detail.validate_time_stats(obj, site)
        for mutate in (
            lambda r: r['no_earth_runs'].update(mean_h=0),
            lambda r: r['sunlit_runs']['clipped_runs'][0].update(duration_h=0),
            lambda r: r['station_link_h'].update(at_least_2_h=43825),
            lambda r: r.update(both_h=r['sunlit_h']+1),
        ):
            r = copy.deepcopy(obj)
            mutate(r)
            with self.assertRaises(ValueError):
                detail.validate_time_stats(r, site)

    def test_psr_rejects_false_completeness_and_unknown_area(self):
        obj=json.loads((Path(__file__).parents[2]/'web/data/detail/psr/SHACKLETON_RIM.json').read_text(encoding='utf8'))
        site={k:obj[k] for k in ('lat','lon')}
        detail.validate_psr(obj,site)
        for mutate in (
            lambda r:r['source'].update(resolution_m=240),
            lambda r:r['search'].update(unsearched_or_nodata_lower_bound_m=1),
            lambda r:r.update(inside_psr=None,site_class=None),
            lambda r:r.update(distance_lower_bound_m=10000),
        ):
            r=copy.deepcopy(obj);mutate(r)
            with self.assertRaises(ValueError):
                detail.validate_psr(r,site)

    def test_invalid_distance_or_bearing(self):
        for field, value in [('distance_m', -1), ('distance_m', float('nan')), ('bearing_deg', 360), ('bearing_deg', None)]:
            r = copy.deepcopy(self.record)
            r['sites'][0]['nearest'][0][field] = value
            with self.assertRaises(ValueError):
                detail.validate_history(r, self.sites)


if __name__ == '__main__':
    unittest.main()
