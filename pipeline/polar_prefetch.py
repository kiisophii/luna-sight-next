"""Parallel block prefetch for fetch_polar.RangeFile (PGDA serves each connection slowly, ~0.2-0.5 MB/s).

install(workers) wraps fetch_polar.read_window: before a window is decoded, every 1 MiB cache block that holds
an intersecting TIFF tile is downloaded with `workers` parallel Range requests, with the same checks as
RangeFile.read (206 status, exact Content-Range, unchanged ETag / Last-Modified, exact length) and atomic writes.
The normal sequential read then finds every block in the cache. Bytes are identical either way.
"""
from __future__ import annotations

import concurrent.futures as cf
import math
import os
import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import fetch_polar as fp

_local = threading.local()


def _session():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(max_retries=Retry(total=6, backoff_factor=1,
                                                          status_forcelist=[429, 500, 502, 503, 504])))
        s.headers["Accept-Encoding"] = "identity"
        _local.s = s
    return _local.s


def _get_block(stream, start):
    stop = min(start + stream.block_size, stream.size)
    path = stream.cache / str(start)
    if path.exists() and path.stat().st_size == stop - start:
        return 0
    with _session().get(stream.url, headers={"Range": f"bytes={start}-{stop - 1}"}, stream=True, timeout=120) as r:
        r.raise_for_status()
        if r.status_code != 206 or r.headers.get("Content-Range") != f"bytes {start}-{stop - 1}/{stream.size}":
            raise ValueError("Invalid Range response or changed source")
        if r.headers.get("ETag") != stream.etag or r.headers.get("Last-Modified") != stream.modified:
            raise ValueError("Source validator changed during Range download")
        data = r.raw.read(stop - start + 1)
    if len(data) != stop - start:
        raise ValueError("Truncated or oversized Range response")
    part = path.with_name(f"{start}.{os.getpid()}.{threading.get_ident()}.part")
    part.write_bytes(data)
    part.replace(path)
    return len(data)


def blocks_for(page, stream, bounds):
    r0, r1, c0, c1 = bounds
    th = page.tilelength if page.is_tiled else page.rowsperstrip
    tw = page.tilewidth if page.is_tiled else page.imagewidth
    cols = math.ceil(page.imagewidth / tw)
    want = set()
    for tr in range(max(r0, 0) // th, (min(r1, page.imagelength) - 1) // th + 1):
        for tc in range(max(c0, 0) // tw, (min(c1, page.imagewidth) - 1) // tw + 1):
            idx = tr * cols + tc
            off, n = page.dataoffsets[idx], page.databytecounts[idx]
            if n == 0:
                continue
            for b in range(off // stream.block_size, (off + n - 1) // stream.block_size + 1):
                want.add(b * stream.block_size)
    return sorted(want)


def prefetch(page, stream, bounds, workers=8):
    starts = blocks_for(page, stream, bounds)
    with cf.ThreadPoolExecutor(workers) as ex:
        got = sum(ex.map(lambda s: _get_block(stream, s), starts))
    stream.bytes_fetched += got
    return got


def install(workers=8):
    original = fp.read_window

    def read_window(page, stream, bounds):
        prefetch(page, stream, bounds, workers)
        return original(page, stream, bounds)

    fp.read_window = read_window
