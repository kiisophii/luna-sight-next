"""Offline tests for the decoders and samplers in pipeline/verify_terrain_tiles.py (synthetic data only).

The encoders below are written here from the documented formats, independently of the production builders.
python -m pytest pipeline/tests/test_verify_terrain_tiles.py -q
"""
import gzip
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_terrain_tiles as vt  # noqa: E402


def test_png_height_decoding(tmp_path):
    from PIL import Image
    h = np.array([[-10000.0, -0.5, 0.0], [1234.5, 8191.5, 22767.0]])
    v = np.round((h + 10000) * 2).astype(np.int64)
    rgb = np.zeros(h.shape + (3,), np.uint8)
    rgb[..., 0], rgb[..., 1] = v >> 8, v & 255
    Image.fromarray(rgb, "RGB").save(tmp_path / "t.png")
    np.testing.assert_array_equal(vt.decode_png(tmp_path / "t.png"), h)


def test_row_delta_decoding(tmp_path):
    rng = np.random.default_rng(1)
    a = rng.integers(-9000, 10000, (5, 5))
    d = a.copy()
    d[:, 1:] = a[:, 1:] - a[:, :-1]
    (tmp_path / "t.i16.gz").write_bytes(gzip.compress(d.astype("<i2").tobytes()))
    np.testing.assert_array_equal(vt.decode_i16_rows(tmp_path / "t.i16.gz", 5), a)


def test_planar_residual_decoding(tmp_path):
    rng = np.random.default_rng(2)
    a = rng.integers(-40000, 40000, (6, 6)) // 7 + 123456
    base = int(a[0, 0])
    b = a - base
    r = np.zeros_like(b)
    r[0, 1:] = b[0, 1:] - b[0, :-1]
    r[1:, 0] = b[1:, 0] - b[:-1, 0]
    r[1:, 1:] = b[1:, 1:] - b[1:, :-1] - b[:-1, 1:] + b[:-1, :-1]
    raw = np.int32(base).astype("<i4").tobytes() + r.astype("<i2").tobytes()
    (tmp_path / "t.bin.gz").write_bytes(gzip.compress(raw))
    np.testing.assert_array_equal(vt.decode_polar(tmp_path / "t.bin.gz", 6), a)


def test_level_rule():
    # coarsest 64/32/16/8/4 ppd level with pixel <= 1.01 x spacing (spacings of band z1..z3, cap z0..z2)
    assert [vt.level_ppd(s) for s in (4264.2, 2132.1, 1066.1, 4375.0, 2187.5, 1093.8, 533.0)] == [8, 16, 32, 8, 16, 32, 64]


def test_bilinear_block_mean_and_wrap():
    class Fake(vt.LolaCyl):
        def __init__(self):
            self.ppd, self.nl, self.ns, self.used = 4, 720, 1440, {}
            r, c = np.meshgrid(np.arange(self.nl), np.arange(self.ns), indexing="ij")
            self.a = (r * 10 + c).astype(np.float32) / 1000.0        # km
    f = Fake()
    # 2x2 block mean of pixels (0..1, 0..1): (0+1+10+11)/4 = 5.5 m
    assert abs(f.level_value(2, 0, 0) - 5.5) < 1e-3          # float32 km storage (as in LDEM): ~1e-4 m at 2.4 km
    # at a pixel centre bilinear returns the pixel; across lon 0/360 it blends the last and first columns
    lat = 90 - 100.5 / 4
    assert abs(f.bilinear(4, lat, 10.5 / 4) - (100 * 10 + 10)) < 1e-3
    v = f.bilinear(4, lat, 0.0)                         # halfway between col 1439 (lon 359.875) and col 0 (0.125)
    assert abs(v - (100 * 10 + (1439 + 0) / 2)) < 1e-3
