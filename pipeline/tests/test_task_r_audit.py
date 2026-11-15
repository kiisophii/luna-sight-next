"""Task R fail-closed parser, coordinate/time and event-boundary checks."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from task_r_audit import SOURCES, first_set, horizon_angle, parse_horizons, timestamp


class TaskRTests(unittest.TestCase):
    def test_catalogue_coverage_and_no_future_target(self):
        root=Path(__file__).resolve().parents[2]
        sites=json.loads((root/'web/data/sites.json').read_text(encoding='utf-8'))
        expected={s['id'] for s in sites if s['group'] not in ('future','custom','polar_peak','artemis3_region')}
        self.assertEqual(expected,{s['id'] for s in SOURCES})
        self.assertEqual(len(SOURCES),len(expected))

    def test_timezones_and_day_boundary(self):
        self.assertEqual(timestamp('2024-06-02T06:23:00+08:00'),timestamp('2024-06-01T22:23:00Z'))
        self.assertEqual(timestamp('2023-08-23T18:04:00+05:30'),timestamp('2023-08-23T12:34:00Z'))
        with self.assertRaises(ValueError): timestamp('2024-06-01T22:23:00')

    def test_circular_mask_and_north_wrap(self):
        self.assertAlmostEqual(float(horizon_angle([0,10,0,-10],359)), -10/90)
        self.assertAlmostEqual(float(horizon_angle([0,10,0,-10],-1)), -10/90)

    def test_sunset_uses_half_disk_boundary_and_first_crossing(self):
        angles=np.array([[0,1],[0,0],[0,-.01],[0,1],[0,-1]])
        self.assertEqual(first_set(angles,[0,0,0,0]),2)
        self.assertIsNone(first_set(np.array([[0,-1],[0,-2]]),[0]*4))

    def test_horizons_errors_missing_frame_wrong_epoch_and_count(self):
        date=timestamp('2025-01-01T00:00:00Z')
        valid='MEAN_ME (high precision)\nNO (AIRLESS)\n$$SOE\n2460676.5, , ,123.0,5.0,\n$$EOE'
        values,_,_=parse_horizons(json.dumps({'result':valid}),[date])
        np.testing.assert_array_equal(values,[[123,5]])
        bad=[{'error':'bad request'},{'result':valid.replace('MEAN_ME','IAU_MOON')},
             {'result':valid.replace('2460676.5','2460677.5')},
             {'result':valid.replace('5.0','NaN')}]
        for payload in bad:
            with self.assertRaises(ValueError):parse_horizons(json.dumps(payload),[date])
        with self.assertRaises(ValueError):parse_horizons(json.dumps({'result':valid}),[date,date])


if __name__=='__main__': unittest.main()
