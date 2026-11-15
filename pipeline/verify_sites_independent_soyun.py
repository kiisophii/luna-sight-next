"""Task S (2026-11-15): independent audit of all 33 sites in web/data/sites.json (producer: Minchul Kim).

Checker: Soyun Jeong. Imports nothing from the producer's or earlier audits' scripts (build_sites.py,
crosscheck_sites_dongju.py, site_coordinate_audit, source-link checkers). Steps:

  fetch    download every source in pipeline/sites_audit_evidence_soyun.json (+ the USGS Gazetteer), extract text
  coords   find each quote in its source text, parse the coordinate from the quote, convert to N+/E+ and -180..180,
           compare with sites.json (exact decimal + great-circle distance on R = 1,737,400 m)
  terrain  PGDA LOLA windows (HTTP Range, own TIFF tile decoder) around the 15 south-polar feature points: local
           relief, slope, crest / peak tests, radial rim profiles from USGS crater centres
  report   docs/sites_full_independent_audit_soyun.json + the 33-row Markdown table (printed)

Run from the repository root with the project .venv:
  python pipeline/verify_sites_independent_soyun.py fetch
  python pipeline/verify_sites_independent_soyun.py coords
  python pipeline/verify_sites_independent_soyun.py terrain
  python pipeline/verify_sites_independent_soyun.py report
Downloads and DEM windows go to data/processed/sites_audit_soyun/ (git-ignored). sites.json is only read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import zlib
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "pipeline/sites_audit_evidence_soyun.json"
CACHE = ROOT / "data/processed/sites_audit_soyun"
OUT_JSON = ROOT / "docs/sites_full_independent_audit_soyun.json"
R_M = 1737400.0                                  # lunar reference radius (docs/data_contract.md section 0)
UA = {"User-Agent": "Mozilla/5.0 (compatible; lunar-site-audit/1.0)"}
PGDA = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/"
MINUS = "−"


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    tmp.replace(p)


# ---- coordinates -------------------------------------------------------------------------------------
def parse_value(text, convention, axis):
    """Parse one coordinate string from a quote. Returns (Decimal value N+/E+ in -180..180, decimals, raw)."""
    t = text.replace(MINUS, "-").replace("–", "-").replace("°", " ").strip()
    m = re.fullmatch(r"(-?)\s*(\d+(?:\.(\d+))?)\s*([NSEW]?)", t)
    if not m:
        raise ValueError(f"cannot parse {text!r}")
    sign, num, frac, hemi = m.groups()
    v = Decimal(num)
    dec = len(frac or "")
    if convention == "hemisphere":
        if not hemi:
            raise ValueError(f"{text!r}: hemisphere letter expected")
        if (axis == "lat") != (hemi in "NS"):
            raise ValueError(f"{text!r}: wrong axis letter")
        if sign:
            raise ValueError(f"{text!r}: sign and hemisphere both given")
        v = -v if hemi in "SW" else v
    else:
        if hemi:
            raise ValueError(f"{text!r}: unexpected hemisphere letter")
        v = -v if sign else v
    if axis == "lat":
        if not -90 <= v <= 90:
            raise ValueError(f"latitude out of range {text!r}")
    else:
        v = normalize_lon(v)
    return v, dec


def normalize_lon(v):
    """Any east longitude (including 0..360 E) -> [-180, 180)."""
    v = Decimal(v)
    while v >= 180:
        v -= 360
    while v < -180:
        v += 360
    return v


def gc_m(lat1, lon1, lat2, lon2):
    """Great-circle distance on the R = 1,737,400 m sphere (haversine)."""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_M * math.asin(min(1.0, math.sqrt(a)))


def rounding_bound_m(lat, dec_lat, dec_lon):
    """Largest distance a value can move when rounded to the source's decimals (half a unit in each axis)."""
    dla = 0.5 * 10.0 ** -dec_lat
    dlo = 0.5 * 10.0 ** -dec_lon
    return R_M * math.radians(1) * math.hypot(dla, dlo * math.cos(math.radians(float(lat))))


def bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    return math.degrees(math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)))


def destination(lat, lon, az_deg, dist_m):
    la, lo, az, t = math.radians(lat), math.radians(lon), math.radians(az_deg), dist_m / R_M
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.cross(up, east)
    p = up * math.cos(t) + (north * math.cos(az) + east * math.sin(az)) * math.sin(t)
    return math.degrees(math.asin(max(-1.0, min(1.0, p[2])))), math.degrees(math.atan2(p[1], p[0]))


# ---- sources -----------------------------------------------------------------------------------------
class _Text(HTMLParser):
    BLOCK = {"br", "p", "tr", "li", "div", "h1", "h2", "h3", "h4", "table", "pre", "figcaption"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(raw):
    p = _Text()
    p.feed(raw.decode("utf-8", "replace"))
    return "".join(p.out)


def pdf_text(path):
    import pypdf
    r = pypdf.PdfReader(str(path))
    return "".join(f"\n=====PAGE {i + 1}=====\n" + (pg.extract_text() or "") for i, pg in enumerate(r.pages))


def normalize(text):
    text = re.sub(r"\x00\s*", MINUS, text)                 # AGU Table A1 minus glyph (see evidence glyph_note)
    return re.sub(r"\s+", " ", text)


def run_fetch():
    import requests
    ev = read_json(EVIDENCE)
    (CACHE / "src").mkdir(parents=True, exist_ok=True)
    rec = {}
    for key, s in ev["sources"].items():
        if key == "USGS_GAZETTEER":
            continue
        t0 = time.time()
        try:
            r = requests.get(s["url"], headers=UA, timeout=180, allow_redirects=True)
            raw = r.content
            (CACHE / "src" / key).write_bytes(raw)
            ok = r.status_code == 200 and (raw[:4] == b"%PDF" if s["kind"] == "pdf" else True)
            text = ""
            if ok:
                text = pdf_text(CACHE / "src" / key) if s["kind"] == "pdf" else html_text(raw)
            (CACHE / "src" / f"{key}.txt").write_text(text, encoding="utf-8")
            rec[key] = dict(url=s["url"], status=r.status_code, final_url=r.url, bytes=len(raw), ok=ok,
                            sha256=hashlib.sha256(raw).hexdigest(), content_type=r.headers.get("Content-Type"),
                            fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), seconds=round(time.time() - t0, 1))
        except Exception as e:  # noqa: BLE001
            rec[key] = dict(url=s["url"], ok=False, error=repr(e))
        print(key, rec[key].get("status"), rec[key].get("bytes"), "ok" if rec[key]["ok"] else "NOT OK", flush=True)
    write_json(CACHE / "fetch.json", rec)
    fetch_gazetteer()


def fetch_gazetteer():
    import requests
    url = "https://planetarynames.wr.usgs.gov/SearchResults"
    r = requests.get(url, params={"Target": "16_Moon", "Feature Name": "Shackleton"}, headers=UA, timeout=300)
    r.raise_for_status()
    rows, hdr = [], None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if "Feature ID" in cells:
            hdr = cells
        elif hdr and len(cells) == len(hdr):
            rows.append(dict(zip(hdr, cells)))
    want = {"Shackleton", "Shoemaker", "de Gerlache", "Nobile", "Haworth", "Cabeus B", "Mons Malapert", "Mons Mouton",
            "Slater", "Reiner Gamma", "Mons Latreille", "Statio Tranquillitatis"}
    sel = {}
    for o in rows:
        if o["Feature Name"] in want:
            sel[o["Feature Name"]] = dict(feature_id=o["Feature ID"], diameter_km=float(o["Diameter"]),
                                          lat=float(o["Center Latitude"]), lon=float(o["Center Longitude"]),
                                          type=o["Feature Type"], status=o["Approval Status"], coord=o["Coordinate System"])
    write_json(CACHE / "gazetteer.json", dict(url=r.url, sha256=hashlib.sha256(r.content).hexdigest(), n_moon=len(rows),
                                              fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), features=sel))
    print("gazetteer", len(rows), "Moon features;", len(sel), "selected", flush=True)


def source_text(key):
    return normalize((CACHE / "src" / f"{key}.txt").read_text(encoding="utf-8"))


# ---- part: coordinates -------------------------------------------------------------------------------
def compare_one(lat_text, lon_text, conv, site_lat, site_lon):
    la, dla = parse_value(lat_text, conv if conv != "signed_N_E360" else "signed_N_E", "lat")
    lo, dlo = parse_value(lon_text, "signed_N_E" if conv == "signed_N_E360" else conv, "lon")
    d = gc_m(la, lo, site_lat, site_lon)
    bound = rounding_bound_m(la, dla, dlo)
    return dict(source_lat=str(la), source_lon=str(lo), lat_decimals=dla, lon_decimals=dlo,
                exact_equal=(la == site_lat and normalize_lon(lo) == normalize_lon(site_lon)),
                distance_m=d, rounding_bound_m=bound, within_rounding=d <= bound + 1e-9)


def run_coords():
    ev = read_json(EVIDENCE)
    sites = json.loads((ROOT / "web/data/sites.json").read_text(encoding="utf-8"), parse_float=Decimal)
    by_id = {s["id"]: s for s in sites}
    fetch = read_json(CACHE / "fetch.json")
    assert len(sites) == 33 and len(by_id) == 33 and {e["id"] for e in ev["sites"]} == set(by_id)
    texts = {k: source_text(k) for k, v in fetch.items() if v.get("ok")}
    ctx = {k: {q: (q in texts.get(k, "")) for q in s.get("context_quotes", [])} for k, s in ev["sources"].items()}
    out = []
    for e in ev["sites"]:
        s = by_id[e["id"]]
        listed_ok = fetch[e["source"]].get("ok", False)
        used = e.get("used_source", e["source"])
        txt = texts.get(used, "")
        found = e["quote"] in txt
        assert e["lat_text"] in e["quote"] and e["lon_text"] in e["quote"]
        cmp = compare_one(e["lat_text"], e["lon_text"], e["convention"], s["lat"], s["lon"])
        r = dict(id=e["id"], name=s["name"], group=s["group"], listed_url=s["source_url"],
                 listed_url_matches_evidence=s["source_url"] == ev["sources"][e["source"]]["url"],
                 listed_source_opened=listed_ok, listed_http_status=fetch[e["source"]].get("status"),
                 used_source=used, used_url=ev["sources"][used]["url"], location=e["location"], quote=e["quote"],
                 quote_found=found, site_lat=str(s["lat"]), site_lon=str(s["lon"]), **cmp)
        if e.get("region_header"):
            r["region_header_found"] = e["region_header"] in txt
        lab = e["feature"].get("label_quote")
        if lab:
            r["label_quote_found"] = lab in txt
        sec = e.get("second_source")
        if sec:
            st = texts.get(sec["source"], "")
            c2 = compare_one(sec["lat_text"], sec["lon_text"], "hemisphere", s["lat"], s["lon"])
            r["second_source"] = dict(source=sec["source"], url=ev["sources"][sec["source"]]["url"], quote=sec["quote"],
                                      quote_found=sec["quote"] in st, **c2)
        if not found:
            r["coord_status"] = "UNVERIFIED"
        elif not cmp["within_rounding"]:
            r["coord_status"] = "MISMATCH"
        else:
            r["coord_status"] = "PASS"
        r["coord_basis"] = ("listed source" if used == e["source"] else
                            "same publication via an alternative copy (listed URL not reachable)")
        out.append(r)
        print(f"{e['id']:24s} {r['coord_status']:10s} quote {'found' if found else 'NOT FOUND'}  "
              f"Δ {cmp['distance_m']:.6f} m (rounding bound {cmp['rounding_bound_m']:.1f} m)", flush=True)
    write_json(CACHE / "coords.json", dict(sites=out, context_quotes=ctx))


# ---- PGDA windows (own TIFF reader: tifffile IFD over HTTP Range, zlib + predictor 3) ---------------
class HttpFile:
    BLOCK = 1 << 20

    def __init__(self, url):
        import requests
        self.url, self.pos, self.blocks, self.s = url, 0, {}, requests.Session()
        h = self.s.head(url, timeout=60, allow_redirects=True)
        h.raise_for_status()
        self.size = int(h.headers["Content-Length"])

    def _block(self, k):
        if k not in self.blocks:
            a, b = k * self.BLOCK, min(self.size, (k + 1) * self.BLOCK) - 1
            for t in range(6):
                try:
                    r = self.s.get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=120)
                    assert r.status_code == 206 and len(r.content) == b - a + 1
                    self.blocks[k] = r.content
                    break
                except Exception:  # noqa: BLE001
                    if t == 5:
                        raise
                    time.sleep(5 * (t + 1))
        return self.blocks[k]

    def read(self, n=-1):
        n = self.size - self.pos if n is None or n < 0 else min(n, self.size - self.pos)
        out = bytearray()
        while len(out) < n:
            k, o = divmod(self.pos + len(out), self.BLOCK)
            out += self._block(k)[o:o + n - len(out)]
        self.pos += n
        return bytes(out)

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def tell(self):
        return self.pos

    def seekable(self):
        return True

    def readable(self):
        return True


_TIFF = {}


def tiff_meta(url):
    if url not in _TIFF:
        import tifffile
        f = HttpFile(url)
        with tifffile.TiffFile(f) as t:
            pg = t.pages[0]
            sx, sy, _ = pg.tags[33550].value
            i, j, _, x, y, _ = pg.tags[33922].value
            geo = pg.geotiff_tags or {}
            assert int(pg.compression) == 8 and int(pg.predictor) == 3 and str(pg.dtype) == "float32"
            assert int(geo["ProjCoordTransGeoKey"]) == 15 and geo["ProjNatOriginLatGeoKey"] == -90
            assert geo["GeogSemiMajorAxisGeoKey"] == R_M == geo["GeogSemiMinorAxisGeoKey"]
            assert int(geo.get("GTRasterTypeGeoKey", 1)) == 1                    # pixel is area
            _TIFF[url] = dict(width=pg.imagewidth, height=pg.imagelength, th=pg.tilelength, tw=pg.tilewidth,
                              offsets=np.array(pg.dataoffsets, np.int64), counts=np.array(pg.databytecounts, np.int64),
                              res=float(sx), left=float(x - i * sx), top=float(y + j * sy), size=f.size)
    return _TIFF[url]


def own_tile(url, offset, nbytes, th, tw):
    import requests
    for k in range(6):
        try:
            b = requests.get(url, headers={"Range": f"bytes={offset}-{offset + nbytes - 1}"}, timeout=120).content
            assert len(b) == nbytes
            raw = np.frombuffer(zlib.decompress(b), np.uint8).reshape(th, 4 * tw)
            break
        except Exception:  # noqa: BLE001
            if k == 5:
                raise
            time.sleep(5 * (k + 1))
    und = np.cumsum(raw, axis=1, dtype=np.uint64).astype(np.uint8)          # undo TIFF predictor 3 byte differencing
    planes = und.reshape(th, 4, tw).transpose(0, 2, 1)
    return np.ascontiguousarray(planes).view(">f4").reshape(th, tw).astype(np.float32)


def stereo(lat, lon):
    """Spherical south-polar stereographic, k0 = 1 at the pole (the GeoTIFFs' CRS, R = 1,737,400 m)."""
    la, lo = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    rho = 2 * R_M * np.tan(np.pi / 4 + la / 2)
    return rho * np.sin(lo), rho * np.cos(lo)


class Window:
    def __init__(self, name, res, lat, lon, half_m):
        path = CACHE / "dem" / f"{name}_{res}.npz"
        url = PGDA + {20: "LDEM_80S_20MPP_ADJ.TIF", 60: "LDEM_60S_60MPP_ADJ.TIF"}[res]
        if path.exists():
            z = np.load(path)
            self.a, self.x0, self.y0, self.res = z["a"], float(z["x0"]), float(z["y0"]), float(z["res"])
            return
        m = tiff_meta(url)
        cx, cy = (float(v) for v in stereo(lat, lon))
        c0 = max(0, math.floor((cx - half_m - m["left"]) / res - 0.5))
        c1 = min(m["width"], math.ceil((cx + half_m - m["left"]) / res - 0.5) + 1)
        r0 = max(0, math.floor((m["top"] - (cy + half_m)) / res - 0.5))
        r1 = min(m["height"], math.ceil((m["top"] - (cy - half_m)) / res - 0.5) + 1)
        th, tw = m["th"], m["tw"]
        ncol = -(-m["width"] // tw)
        a = np.full((r1 - r0, c1 - c0), np.nan, np.float32)
        for ty in range(r0 // th, (r1 - 1) // th + 1):
            for tx in range(c0 // tw, (c1 - 1) // tw + 1):
                k = ty * ncol + tx
                full = own_tile(url, int(m["offsets"][k]), int(m["counts"][k]), th, tw)
                ya, yb, xa, xb = max(r0, ty * th), min(r1, (ty + 1) * th), max(c0, tx * tw), min(c1, (tx + 1) * tw)
                a[ya - r0:yb - r0, xa - c0:xb - c0] = full[ya - ty * th:yb - ty * th, xa - tx * tw:xb - tx * tw]
        self.a, self.res = a, float(res)
        self.x0, self.y0 = m["left"] + (c0 + 0.5) * res, m["top"] - (r0 + 0.5) * res
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, a=a, x0=self.x0, y0=self.y0, res=self.res)

    def h(self, lat, lon):
        x, y = stereo(lat, lon)
        r, c = (self.y0 - np.atleast_1d(y)) / self.res, (np.atleast_1d(x) - self.x0) / self.res
        nr, nc = self.a.shape
        out = np.full(r.shape, np.nan)
        ok = (r >= 0) & (r <= nr - 1) & (c >= 0) & (c <= nc - 1)
        r0 = np.minimum(np.floor(r[ok]).astype(int), nr - 2)
        c0 = np.minimum(np.floor(c[ok]).astype(int), nc - 2)
        fr, fc = r[ok] - r0, c[ok] - c0
        a = self.a
        out[ok] = (1 - fr) * ((1 - fc) * a[r0, c0] + fc * a[r0, c0 + 1]) + fr * ((1 - fc) * a[r0 + 1, c0] + fc * a[r0 + 1, c0 + 1])
        return out


def ring_heights(W, lat, lon, radius_m, step=20.0):
    pts = [destination(lat, lon, a, r) for a in np.arange(0, 360, 5.0) for r in np.arange(step, radius_m + 1, step)]
    return W.h(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))


def point_metrics(name, lat, lon, crater=None):
    W = Window(name, 20, lat, lon, 9000)
    h0 = float(W.h(lat, lon)[0])
    m = dict(dem="PGDA LDEM_80S_20MPP_ADJ (20 m)", h_m=h0)
    for rad in (500, 1000, 3000):
        hh = ring_heights(W, lat, lon, rad)
        m[f"pct_below_{rad}m"] = float(np.mean(hh < h0) * 100)
        m[f"max_within_{rad}m"] = float(np.nanmax(hh))
        m[f"min_within_{rad}m"] = float(np.nanmin(hh))
    e = [W.h(*destination(lat, lon, a, 30))[0] for a in (90, 270, 0, 180)]
    m["slope_deg_60m"] = math.degrees(math.atan(math.hypot((e[0] - e[1]) / 60, (e[2] - e[3]) / 60)))
    drops = []
    for a in range(0, 180, 5):
        p, q = W.h(*destination(lat, lon, a, 1000))[0], W.h(*destination(lat, lon, a + 180, 1000))[0]
        drops.append(min(h0 - p, h0 - q))
    m["max_two_sided_drop_1km_m"] = float(max(drops))     # > 0: lower on both sides in some direction (crest)
    m["min_two_sided_drop_1km_m"] = float(min(drops))     # > 0: lower on both sides in every direction (summit)
    if crater:
        clat, clon, D = crater["lat"], crater["lon"], crater["diameter_km"]
        d = gc_m(clat, clon, lat, lon)
        b = bearing_deg(clat, clon, lat, lon)
        rs = np.arange(max(0.0, d - 4000), d + 4001, 20.0)
        pts = [destination(clat, clon, b, r) for r in rs]
        hh = W.h(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
        k = int(np.nanargmax(hh))
        m.update(crater_centre_dist_m=d, crater_radius_m=D * 500, dist_over_radius=d / (D * 500), crest_radius_m=float(rs[k]),
                 offset_from_radial_crest_m=float(d - rs[k]), below_radial_crest_m=float(hh[k] - h0),
                 h_1km_inward_m=float(W.h(*destination(clat, clon, b, d - 1000))[0]),
                 h_1km_outward_m=float(W.h(*destination(clat, clon, b, d + 1000))[0]))
    return m


def crater_crest_radii(name, crater):
    """Rim-crest radius in 36 bearings: radial elevation maximum between 0.6 R and 1.4 R (PGDA 60 m)."""
    clat, clon, D = crater["lat"], crater["lon"], crater["diameter_km"]
    R = D * 500
    W = Window("crater_" + name.replace(" ", "_"), 60, clat, clon, 1.4 * R + 3000)
    radii = []
    for b in range(0, 360, 10):
        rr = np.arange(0.6 * R, 1.4 * R, 60.0)
        pts = [destination(clat, clon, b, r) for r in rr]
        hh = W.h(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
        radii.append(float(rr[int(np.nanargmax(hh))]))
    return dict(dem="PGDA LDEM_60S_60MPP_ADJ (60 m)", median_m=float(np.median(radii)), min_m=min(radii), max_m=max(radii), bearings_deg=list(range(0, 360, 10)), radii_m=radii)


def run_terrain():
    ev = read_json(EVIDENCE)
    gz = read_json(CACHE / "gazetteer.json")["features"]
    sites = {s["id"]: s for s in read_json(ROOT / "web/data/sites.json")}
    out, craters = {}, {}
    for e in ev["sites"]:
        f = e["feature"]
        s = sites[e["id"]]
        if f.get("gazetteer_check"):
            g = gz[f["gazetteer_check"]]
            d = gc_m(g["lat"], g["lon"], s["lat"], s["lon"])
            out.setdefault(e["id"], {})["gazetteer"] = dict(name=f["gazetteer_check"], **g, dist_m=d, dist_over_radius=d / (g["diameter_km"] * 500))
        if not f.get("terrain"):
            continue
        cr = gz[f["crater"]] if f.get("crater") else None
        t0 = time.time()
        out.setdefault(e["id"], {})["terrain"] = point_metrics(e["id"], s["lat"], s["lon"], cr)
        if f.get("old_point"):
            out[e["id"]]["old_point_terrain"] = point_metrics(e["id"] + "_OLD", *f["old_point"], cr)
        if cr and f["crater"] not in craters:
            craters[f["crater"]] = crater_crest_radii(f["crater"], cr)
        print(e["id"], {k: round(v, 1) for k, v in out[e["id"]]["terrain"].items() if isinstance(v, float)}, f"{time.time() - t0:.0f} s", flush=True)
    write_json(CACHE / "terrain.json", dict(points=out, crater_crest_radii=craters))


# ---- geographic decision ------------------------------------------------------------------------------
def geo_decision(e, c, t, crest):
    """Return (status, strength, reason). Thresholds are stated in the report."""
    f = e["feature"]
    typ = f["type"]
    if typ.startswith("historical lander"):
        extra = ""
        g = t.get("gazetteer")
        if g:
            extra += f"; {g['dist_m']:.0f} m from the USGS {g['name']} centre"
        sec = c.get("second_source")
        if sec:
            same = "same value" if sec["exact_equal"] else "%.1f m apart, last digit differs" % sec["distance_m"]
            extra += f"; NSSDCA table gives {sec['source_lat']}, {sec['source_lon']} ({same})"
        if e["id"].startswith("APOLLO"):
            ok = c.get("label_quote_found")
            others = "; ".join(f"{k} row {gc_m(float(c['site_lat']), float(c['site_lon']), *xy):.0f} m away"
                               for k, xy in e["feature"].get("others", {}).items())
            return ("PASS" if ok else "UNVERIFIED", "confirmed",
                    f"row labelled 'Lunar Module' in the LRO-derived NSSDCA table; {others}" + extra)
        if e["id"].startswith("LUNA"):
            return ("PASS" if c.get("label_quote_found") else "UNVERIFIED", "confirmed",
                    "NSSDCA row 'Soft Landing' with note d (spacecraft imaged on the surface by LROC)")
        return ("PASS", "confirmed", "the LROC post gives the coordinate of the lander itself as identified in NAC images" + extra)
    if typ.startswith("planned landing target"):
        g = t.get("gazetteer", {})
        inside = g.get("dist_over_radius", 9) <= 1
        return ("PASS" if inside else "MISMATCH", "approximate",
                f"planned target, not a landing; {g.get('dist_m', float('nan')) / 1000:.1f} km from the USGS Reiner Gamma centre "
                f"(albedo feature, {g.get('diameter_km')} km across); the paper places it in central Reiner Gamma")
    tm = t.get("terrain", {})
    region = e.get("region_header")
    if region and not c.get("region_header_found"):
        return ("UNVERIFIED", "approximate", "region header not found in the source text")
    if f.get("crater"):
        off, below = tm["offset_from_radial_crest_m"], tm["below_radial_crest_m"]
        inward_drop = tm["h_m"] - tm["h_1km_inward_m"]
        on_rim = abs(off) <= 500 and below <= 50 and inward_drop > 0
        cr = crest.get(f["crater"], {})
        why = (f"{tm['crater_centre_dist_m'] / 1000:.2f} km from the USGS {f['crater']} centre (radius {tm['crater_radius_m'] / 1000:.2f} km; "
               f"rim-crest radius over 36 bearings {cr.get('min_m', 0) / 1000:.1f}–{cr.get('max_m', 0) / 1000:.1f} km); "
               f"{abs(off):.0f} m {'outward' if off > 0 else 'inward'} of the radial crest and {below:.1f} m below it; "
               f"1 km toward the centre is {inward_drop:.0f} m lower")
        # published rim research point = confirmed; DEM-polygon centres and research CLSs = approximate
        strength = "confirmed" if e["id"] == "SHACKLETON_RIM" else "approximate"
        if on_rim:
            return ("PASS", strength, why)
        if abs(off) <= 1000 and below <= 50:
            # near the crest but the strict test fails (broad, flat rim top): neither PASS nor a proven mismatch
            return ("UNVERIFIED", "ambiguous", why + "; within 1 km and 50 m of the crest but fails the strict rim test "
                    "(offset from the crest at most 500 m, at most 50 m below it, lower toward the centre)")
        return ("MISMATCH", strength, why)
    if f.get("ridge"):
        ok = tm["max_two_sided_drop_1km_m"] >= 50 and tm["pct_below_1000m"] >= 60
        return ("PASS" if ok else "MISMATCH", "approximate",
                f"crest test: in one direction the ground 1 km away on both sides is ≥ {tm['max_two_sided_drop_1km_m']:.0f} m lower; "
                f"higher than {tm['pct_below_1000m']:.0f}% of the ground within 1 km; highest point within 500 m is "
                f"{tm['max_within_500m'] - tm['h_m']:.1f} m higher")
    if f.get("peak"):
        ok = tm["min_two_sided_drop_1km_m"] > 0 and tm["max_within_500m"] - tm["h_m"] <= 10
        return ("PASS" if ok else "MISMATCH", "approximate",
                f"summit test: lower ground 1 km away in every direction (≥ {tm['min_two_sided_drop_1km_m']:.0f} m); highest point within "
                f"500 m is {tm['max_within_500m'] - tm['h_m']:.1f} m higher; higher than {tm['pct_below_1000m']:.0f}% within 1 km")
    g = t.get("gazetteer", {})
    gtxt = (f"; {g['dist_m'] / 1000:.1f} km from the USGS {g['name']} centre ({g['diameter_km']} km across)" if g else "")
    desc = (f"terrain: slope {tm['slope_deg_60m']:.1f}°, higher than {tm['pct_below_1000m']:.0f}% within 1 km and "
            f"{tm['pct_below_3000m']:.0f}% within 3 km; highest point within 3 km is {tm['max_within_3000m'] - tm['h_m']:.0f} m higher")
    inside = (g.get("dist_over_radius", 0) <= 1) if g and g.get("type", "").startswith("Mons") else True
    return ("PASS" if inside else "MISMATCH", "approximate",
            f"listed under '{region}' in Table A1 (region membership as defined by the paper; NASA region boundaries are not "
            f"published as coordinates){gtxt}; {desc}")


# ---- report --------------------------------------------------------------------------------------------
def run_report():
    ev = read_json(EVIDENCE)
    coords = read_json(CACHE / "coords.json")
    terr = read_json(CACHE / "terrain.json")
    fetch = read_json(CACHE / "fetch.json")
    gz = read_json(CACHE / "gazetteer.json")
    rows = []
    for e, c in zip(ev["sites"], coords["sites"]):
        assert e["id"] == c["id"]
        t = terr["points"].get(e["id"], {})
        st, strength, why = geo_decision(e, c, t, terr["crater_crest_radii"])
        rows.append(dict(**c, feature_type=e["feature"]["type"], feature_claim=e["feature"]["claim"], geo_status=st,
                         geo_strength=strength, geo_evidence=why, terrain=t.get("terrain"), gazetteer=t.get("gazetteer"),
                         old_point_terrain=t.get("old_point_terrain")))
    d = np.array([r["distance_m"] for r in rows])
    summary = dict(
        total=len(rows),
        coord_pass=sum(r["coord_status"] == "PASS" for r in rows),
        coord_pass_listed_source=sum(r["coord_status"] == "PASS" and r["used_source"] == next(x["source"] for x in ev["sites"] if x["id"] == r["id"]) for r in rows),
        coord_pass_alternative_copy=sum(r["coord_status"] == "PASS" and r["coord_basis"].startswith("same publication") for r in rows),
        coord_mismatch=sum(r["coord_status"] == "MISMATCH" for r in rows),
        coord_unverified=sum(r["coord_status"] == "UNVERIFIED" for r in rows),
        exact_equal=sum(r["exact_equal"] for r in rows),
        max_distance_m=float(d.max()), median_distance_m=float(np.median(d)),
        geo_pass_confirmed=sum(r["geo_status"] == "PASS" and r["geo_strength"] == "confirmed" for r in rows),
        geo_pass_approximate=sum(r["geo_status"] == "PASS" and r["geo_strength"] == "approximate" for r in rows),
        geo_mismatch=sum(r["geo_status"] == "MISMATCH" for r in rows),
        geo_unverified=sum(r["geo_status"] == "UNVERIFIED" for r in rows),
        old_shackleton_r04=next(dict(lat=-89.7668, lon=-171.87, offset_from_rim_crest_m=r["old_point_terrain"]["offset_from_radial_crest_m"],
                                     below_rim_crest_m=r["old_point_terrain"]["below_radial_crest_m"],
                                     slope_deg=r["old_point_terrain"]["slope_deg_60m"],
                                     on_rim=abs(r["old_point_terrain"]["offset_from_radial_crest_m"]) <= 500
                                     and r["old_point_terrain"]["below_radial_crest_m"] <= 50)
                                for r in rows if r.get("old_point_terrain")),
        listed_urls_not_opened=sorted({r["listed_url"] for r in rows if not r["listed_source_opened"]}),
        second_source_max_m=max(r["second_source"]["distance_m"] for r in rows if r.get("second_source")),
    )
    out = dict(task="S", product="web/data/sites.json", producer="Minchul Kim", checker="Soyun Jeong", R_m=R_M,
               sites_json_sha256=hashlib.sha256((ROOT / "web/data/sites.json").read_bytes()).hexdigest(),
               summary=summary, sites=rows, sources=ev["sources"], fetch=fetch, context_quotes=coords["context_quotes"],
               gazetteer=dict(url=gz["url"], sha256=gz["sha256"], n_moon=gz["n_moon"], features=gz["features"]),
               crater_crest_radii={k: {kk: v for kk, v in x.items() if kk != "radii_m"} | {"radii_m": x["radii_m"]} for k, x in terr["crater_crest_radii"].items()},
               script="pipeline/verify_sites_independent_soyun.py", evidence="pipeline/sites_audit_evidence_soyun.json")
    write_json(OUT_JSON, out)
    print(json.dumps(summary, indent=1))


def run_table():
    d = read_json(OUT_JSON)
    print("| # | Site ID | Site name | Listed source URL | Original coordinate quotation | Source lat | Source lon | sites.json lat | sites.json lon | Difference (m) | Coordinate status | Feature type | Feature status | Evidence / remarks |")
    print("|---:|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|")
    for i, r in enumerate(d["sites"], 1):
        cs = r["coord_status"] + ("" if r["coord_basis"] == "listed source" else " (alt. copy)")
        gs = r["geo_status"] + {"approximate": " (approximate)", "ambiguous": " (ambiguous)"}.get(r["geo_strength"], "")
        q = r["quote"].replace("|", "\\|")
        diff = (f"0 (exact decimal match; source precision ±{r['rounding_bound_m']:.1f} m)" if r["exact_equal"]
                else f"{r['distance_m']:.3f} (rounding bound {r['rounding_bound_m']:.1f})")
        print(f"| {i} | {r['id']} | {r['name']} | {r['listed_url']} | “{q}” ({r['location']}) | {r['source_lat']} | {r['source_lon']} | "
              f"{r['site_lat']} | {r['site_lon']} | {diff} | {cs} | {r['feature_type']} | {gs} | {r['geo_evidence']} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["fetch", "coords", "terrain", "report", "table"])
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    dict(fetch=run_fetch, coords=run_coords, terrain=run_terrain, report=run_report, table=run_table)[a.part]()


if __name__ == "__main__":
    sys.exit(main())
