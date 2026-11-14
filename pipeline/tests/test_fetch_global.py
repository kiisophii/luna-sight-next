"""Offline unit tests for pipeline/fetch_global.py (no network).

Run from the repository root:  python -m unittest pipeline.tests.test_fetch_global -v
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch_global as fg  # noqa: E402

LDEM16_LABEL = """PDS_VERSION_ID            = "PDS3"
PRODUCT_ID                = "LDEM_16_FLOAT"
RECORD_BYTES              = 23040
  OBJECT                  = IMAGE
    LINES                 = 2880
    LINE_SAMPLES          = 5760
    SAMPLE_TYPE           = PC_REAL
    SAMPLE_BITS           = 32
    UNIT                  = KILOMETER
    SCALING_FACTOR        = 1
    OFFSET                = 1737.4
/* HEIGHT = (DN * SCALING_FACTOR).                                         */
  END_OBJECT              = IMAGE
 MAP_PROJECTION_TYPE          = "SIMPLE CYLINDRICAL"
 MAP_RESOLUTION               = 16 <pix/deg>
 A_AXIS_RADIUS                = 1737.4 <km>
 POSITIVE_LONGITUDE_DIRECTION = "EAST"
 CENTER_LONGITUDE             = 180 <deg>
 MAXIMUM_LATITUDE             = 90 <deg>
 MINIMUM_LATITUDE             = -90 <deg>
 WESTERNMOST_LONGITUDE        = 0 <deg>
 EASTERNMOST_LONGITUDE        = 360 <deg>
 LINE_PROJECTION_OFFSET       = 1439.5 <pix>
 SAMPLE_PROJECTION_OFFSET     = 2879.5 <pix>
 COORDINATE_SYSTEM_NAME       = "MEAN EARTH/POLAR AXIS OF DE421"
"""

# Real values from sldem2015_512_00n_30n_000_045_float.lbl (PDS, read 2026-11-14)
SLDEM_TILE_LABEL = """RECORD_BYTES              = 92160
    LINES                 = 15360
    LINE_SAMPLES          = 23040
    SAMPLE_TYPE           = PC_REAL
    SAMPLE_BITS           = 32
    UNIT                  = KILOMETER
    SCALING_FACTOR        = 1
    OFFSET                = 1737.4
 MAP_PROJECTION_TYPE          = "SIMPLE CYLINDRICAL"
 MAP_RESOLUTION               = 512 <pix/deg>
 POSITIVE_LONGITUDE_DIRECTION = "EAST"
 CENTER_LONGITUDE             = 180. <deg>
 MAXIMUM_LATITUDE             = 30 <deg>
 MINIMUM_LATITUDE             = 0 <deg>
 WESTERNMOST_LONGITUDE        = 0 <deg>
 EASTERNMOST_LONGITUDE        = 45 <deg>
 LINE_PROJECTION_OFFSET       = 15359.5 <pix>
 SAMPLE_PROJECTION_OFFSET     = 92159.5 <pix>
 COORDINATE_SYSTEM_NAME       = "MEAN EARTH/POLAR AXIS OF DE421"
"""


def all_tiles():
    tiles = []
    for s, n in [(-60, -30), (-30, 0), (0, 30), (30, 60)]:
        for w in range(0, 360, 45):
            tiles.append(dict(name=f't_{s}_{w}', south=s, north=n, west=w, east=w + 45))
    return tiles


class LabelAndGrid(unittest.TestCase):
    def test_parse_label_values_and_units(self):
        L = fg.parse_label(LDEM16_LABEL)
        self.assertEqual(L['LINES'], 2880)
        self.assertEqual(L['OFFSET'], 1737.4)           # not LINE_PROJECTION_OFFSET
        self.assertEqual(L['LINE_PROJECTION_OFFSET'], 1439.5)
        self.assertEqual(L['UNIT'], 'KILOMETER')
        self.assertEqual(L['MAP_RESOLUTION'], 16)

    def test_ldem16_pixel_centres(self):
        g = fg.Grid(LDEM16_LABEL)
        self.assertAlmostEqual(float(g.row_lat(0)), 90 - 1 / 32)
        self.assertAlmostEqual(float(g.col_lon(0)), 1 / 32)
        self.assertAlmostEqual(float(g.lat_to_row(0.0)), 1439.5)
        self.assertAlmostEqual(float(g.lon_to_col(-0.03125)), 5759.0)  # lon -180..180 input

    def test_sldem_tile_edges(self):
        g = fg.Grid(SLDEM_TILE_LABEL)
        self.assertAlmostEqual(g.north, 30)
        self.assertAlmostEqual(g.south, 0)
        self.assertAlmostEqual(g.west, 0)
        self.assertAlmostEqual(g.east, 45)

    def test_half_pixel_error_is_caught(self):
        bad = SLDEM_TILE_LABEL.replace('15359.5', '15360.0')
        with self.assertRaises(ValueError):
            fg.Grid(bad)

    def test_wrong_unit_or_radius_rejected(self):
        with self.assertRaises(ValueError):
            fg.Grid(SLDEM_TILE_LABEL.replace('KILOMETER', 'METER'))
        with self.assertRaises(ValueError):
            fg.Grid(SLDEM_TILE_LABEL.replace('OFFSET                = 1737.4',
                                             'OFFSET                = 1738.0'))


class Windows(unittest.TestCase):
    def test_cap_extent(self):
        dlat, dlon = fg.cap_extent(0.0, 150.0)
        self.assertAlmostEqual(dlat, math.degrees(150 / 1737.4))
        self.assertAlmostEqual(dlon, dlat, places=6)
        _, dlon60 = fg.cap_extent(60.0, 150.0)
        self.assertGreater(dlon60, 2 * dlat * 0.99)

    def test_plan_is_pixel_aligned_and_centred(self):
        g0, g1, k0, k1, clipped = fg.window_plan(20.1908, 30.7717, 150)
        lat_c = 90 - (np.arange(g0, g1) + 0.5) / 512
        lon_c = (np.arange(k0, k1) + 0.5) / 512
        self.assertFalse(clipped)
        self.assertTrue(lat_c.min() < 20.1908 - 4.9 and lat_c.max() > 20.1908 + 4.9)
        self.assertTrue(lon_c.min() < 30.7717 - 5.2 and lon_c.max() > 30.7717 + 5.2)

    def test_pieces_cover_window_once_across_0_360(self):
        plan = fg.window_plan(1.0, -1.0, 150)   # crosses 0 E, stays in one lat band
        pieces = fg.tile_pieces(plan, all_tiles(), {})
        g0, g1, k0, k1, _ = plan
        cover = np.zeros((g1 - g0, k1 - k0), int)
        for p in pieces:
            cover[p['wrows'][0]:p['wrows'][1], p['wcols'][0]:p['wcols'][1]] += 1
            self.assertGreaterEqual(p['cols'][0], 0)
            self.assertLessEqual(p['cols'][1], 45 * 512)
        self.assertTrue((cover == 1).all())
        self.assertEqual({p['tile'] for p in pieces}, {'t_-30_0', 't_-30_315', 't_0_0', 't_0_315'})

    def test_pieces_cross_180(self):
        plan = fg.window_plan(-45.4446, 177.5991, 150)
        pieces = fg.tile_pieces(plan, all_tiles(), {})
        self.assertEqual({p['tile'] for p in pieces}, {'t_-60_135', 't_-60_180'})

    def test_clip_at_60(self):
        *_, clipped = fg.window_plan(58.0, 10.0, 150)
        self.assertTrue(clipped)
        g0 = fg.window_plan(58.0, 10.0, 150)[0]
        self.assertEqual(g0, 30 * 512)

    def test_tile_anchor_matches_label(self):
        t = dict(name='x', south=0, north=30, west=0, east=45)
        plan = fg.window_plan(20.0, 30.0, 150)
        fg.tile_pieces(plan, [t], {'x': fg.Grid(SLDEM_TILE_LABEL)})  # asserts inside


class Http(unittest.TestCase):
    def test_parse_multipart(self):
        b = 'q1w2<>'
        body = (f'\r\n--{b}\r\nContent-Type: application/octet-stream\r\n'
                f'Content-Range: bytes 0-3/100\r\n\r\n').encode() + b'ABCD' + \
               (f'\r\n--{b}\r\nContent-Range: bytes 10-11/100\r\n\r\n').encode() + b'XY' + \
               f'\r\n--{b}--\r\n'.encode()
        parts = fg.parse_multipart(body, f'multipart/byteranges; boundary={b}')
        self.assertEqual(parts, [(0, b'ABCD'), (10, b'XY')])


class Sampling(unittest.TestCase):
    def test_sample_window_plane(self):
        lat = 10 - (np.arange(20) + 0.5) / 512
        lu = 359.98 + (np.arange(30) + 0.5) / 512       # crosses 360
        h = (1000 * lat[:, None] + 10 * lu[None, :]).astype(np.float32)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'w.npz'
            np.savez(f, height_m=h, lat=lat, lon_unwrapped=lu, lon=fg.lon180(lu),
                     meta=json.dumps({}))
            v = fg.sample_window(f, 9.99, 0.01)            # lon given as 0.01 -> 360.01
            self.assertAlmostEqual(float(v), 1000 * 9.99 + 10 * 360.01, delta=0.05)
            with self.assertRaises(ValueError):
                fg.sample_window(f, 0.0, 0.01)

    def test_ldem_sampling_wraps_longitude(self):
        g = fg.Grid(LDEM16_LABEL)
        with tempfile.TemporaryDirectory() as d:
            img, lbl = Path(d) / 'a.img', Path(d) / 'a.lbl'
            lbl.write_text(LDEM16_LABEL)
            data = np.zeros((g.lines, g.samples), '<f4')
            data[:, 0] = 1.0           # 1 km at lon 0.03125
            data.tofile(img)
            L = fg.LdemFile(img, lbl)
            self.assertAlmostEqual(float(L.sample(0.0, 0.03125)), 1000.0, places=3)
            self.assertAlmostEqual(float(L.sample(0.0, 0.0)), 500.0, places=3)   # between cols -1 and 0
            self.assertAlmostEqual(float(L.sample(0.0, -0.03125)), 0.0, places=3)
            del L


class Sites(unittest.TestCase):
    def test_non_polar_filter(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 's.json'
            f.write_text(json.dumps([dict(id='A', lat=20, lon=30), dict(id='P', lat=-85, lon=0),
                                     dict(id='B', lat=-79.9, lon=0)]))
            sites, _ = fg.load_sites(f)
            self.assertEqual([s['id'] for s in sites], ['A', 'B'])


if __name__ == '__main__':
    unittest.main()
