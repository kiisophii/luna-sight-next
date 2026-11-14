import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
import tifffile
import requests

from pipeline.fetch_polar import RangeFile, project, read_window, grid, validate_crs


@pytest.fixture
def server():
    payload = bytes(range(256)) * 1024
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_HEAD(self):
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('ETag', '"test"')
            self.end_headers()
        def do_GET(self):
            start, end = map(int, self.headers['Range'][6:].split('-'))
            self.send_response(200 if self.path == '/bad' else 206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{len(payload)}')
            self.send_header('Content-Length', str(end-start+1))
            self.send_header('ETag', '"changed"' if self.path == '/changed' and end > 0 else '"test"')
            self.end_headers()
            self.wfile.write(payload[start:end] if self.path == '/short' and end > 0 else payload[start:end+1])
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{http.server_port}', payload
    http.shutdown()
    thread.join()


def test_range_restart_and_seek(server, tmp_path):
    url, payload = server
    with RangeFile(url, tmp_path) as f:
        f.seek(65530)
        assert f.read(30) == payload[65530:65560]
        assert f.bytes_fetched > 0
    with RangeFile(url, tmp_path) as f:
        f.seek(65530)
        assert f.read(30) == payload[65530:65560]
        assert f.bytes_fetched == 0
        f.seek(-10, 2)
        assert f.read() == payload[-10:]


def test_reject_full_response(server, tmp_path):
    with pytest.raises(ValueError, match='Range'):
        with RangeFile(server[0] + '/bad', tmp_path) as f:
            f.read(10)


def test_projection():
    assert project(-90, 0) == pytest.approx((0, 0), abs=1e-8)
    x, y = project(-89, 0)
    assert x == pytest.approx(0, abs=1e-8)
    assert y > 30000
    x, y = project(-89, 90)
    assert x > 30000
    assert abs(y) < 1e-8


@pytest.mark.parametrize('tiled', [True, False])
def test_decode_window(tiled):
    data = np.arange(64*64, dtype=np.float32).reshape(64, 64)
    b = io.BytesIO()
    tifffile.imwrite(b, data, tile=(16,16) if tiled else None,
                     rowsperstrip=None if tiled else 8, compression='deflate')
    b.seek(0)
    with tifffile.TiffFile(b) as tif:
        assert np.array_equal(read_window(tif.pages[0], b, (3,25,7,38)), data[3:25,7:38])


def test_pixel_centres():
    b = io.BytesIO()
    tifffile.imwrite(b, np.ones((16,16), dtype='float32'), extratags=[
        (33550, 'd', 3, (5,5,0), False),
        (33922, 'd', 6, (0,0,0,-40,40,0), False),
    ])
    b.seek(0)
    with tifffile.TiffFile(b) as tif:
        assert grid(tif.pages[0]) == (-37.5, 37.5, 5.0)


def test_changed_source(server, tmp_path):
    with RangeFile(server[0] + '/changed', tmp_path) as f:
        with pytest.raises(ValueError, match='validator'):
            f.read(10)


def test_short_response_is_not_cached(server, tmp_path):
    with RangeFile(server[0] + '/short', tmp_path) as f:
        with pytest.raises((ValueError, requests.RequestException)):
            f.read(10)
        assert not (f.cache/'0').exists()


def test_incomplete_cache(server, tmp_path):
    with RangeFile(server[0], tmp_path) as f:
        (f.cache / '0').write_bytes(b'bad')
        assert f.read(10) == server[1][:10]
        assert f.bytes_fetched > 0


def test_reject_wrong_crs():
    with pytest.raises(ValueError, match='CRS'):
        validate_crs({'GeogSemiMajorAxisGeoKey': 6378137})


def test_point_registration_and_nodata():
    b = io.BytesIO()
    data = np.ones((16,16), dtype='float32')
    data[0,0] = -9999
    tifffile.imwrite(b, data, extratags=[
        (33550, 'd', 3, (5,5,0), False),
        (33922, 'd', 6, (0,0,0,-40,40,0), False),
        (34735, 'H', 8, (1,1,0,1,1025,0,1,2), False),
        (42113, 's', 0, '-9999', False),
    ])
    b.seek(0)
    with tifffile.TiffFile(b) as tif:
        assert grid(tif.pages[0]) == (-40,40,5)
        assert np.isnan(read_window(tif.pages[0],b,(0,1,0,1))[0,0])
        with pytest.raises(ValueError, match='window'):
            read_window(tif.pages[0],b,(-1,1,0,1))


def test_opt_in_partial_coverage_retains_available_pixels():
    from pipeline import fetch_polar as fp
    assert fp.clip_window((-2, 8, 4, 12), (10, 10), allow_partial=True) == (0, 8, 4, 10)
    with pytest.raises(ValueError, match='coverage'):
        fp.clip_window((-2, 8, 4, 12), (10, 10))


def test_partial_coverage_rejects_empty_intersection():
    from pipeline import fetch_polar as fp
    with pytest.raises(ValueError, match='coverage'):
        fp.clip_window((12, 15, 1, 4), (10, 10), allow_partial=True)
    assert fp.clip_window((0, 10, 0, 10), (10, 10)) == (0, 10, 0, 10)


def test_batch_skip_only_source_coverage_not_transport_errors(tmp_path, monkeypatch, capsys):
    import json
    import sys
    from pipeline import fetch_polar as fp
    sites = tmp_path/'sites.json'
    sites.write_text(json.dumps([dict(id='TEST',lat=-89,lon=0)]))
    monkeypatch.setattr(sys,'argv',['fetch_polar','--sites',str(sites),'--res','5','--skip-unavailable'])
    def uncovered(*args,**kwargs):
        raise fp.SourceCoverageError('no source coverage')
    monkeypatch.setattr(fp,'fetch',uncovered)
    fp.main()
    assert 'UNAVAILABLE TEST 5m' in capsys.readouterr().out
    def broken(*args,**kwargs):
        raise requests.ConnectionError('connection dropped')
    monkeypatch.setattr(fp,'fetch',broken)
    with pytest.raises(SystemExit,match='1 windows failed'):
        fp.main()
