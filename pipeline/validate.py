"""Card 5 - PGDA "answer key" for our Sun / Earth visibility results (data contract v1.1, section 5).

What it does
  1. Downloads the PGDA 18.6-year average visibility maps (Mazarico et al. 2011), resumable:
       AVGVISIB_85S_060M_201608.TIF (+ _EARTH)  - 85-90 S, 60 m/px   (main truth for the 240 points)
       AVGVISIB_75S_120M_201608.TIF (+ _EARTH)  - 75-90 S, 120 m/px  (named sites outside 85 S, cross-check)
     Source: https://pgda.gsfc.nasa.gov/products/69  ->  https://pgda.gsfc.nasa.gov/data/MoonIllumination/
  2. Decodes values: DN (int16) x 0.00004 = fraction of time steps (0..1). (PDS label SCALING_FACTOR.)
  3. Draws 240 random points between 85 S and 90 S (seed 42, uniform in AREA, lon -180..180 east-positive)
     and records, for Sun and Earth: the PGDA value and min/max within +-60 m and +-300 m.
  4. Does the same for the named south-polar sites in web/data/sites.json (lat <= -75).
  5. compare(ours) turns our phase-2 results into web/data/validation.json (contract v1.1):
     MAE / RMSE in percentage points, Pearson r, and % of points inside the PGDA +-60 m spread.

Outputs
  data/processed/validation_points.csv   240 points + PGDA values (committed: small, needed by phase 2)
  data/processed/validation_named.csv    named sites + PGDA values
  web/data/validation.json               only written by compare() (real results) - never invented

Definitions to keep in mind when comparing (from the PDS labels / PGDA page):
  * PGDA Sun:   pixel counts as lit if ANY fraction of the solar disc is visible.
  * PGDA Earth: Earth counts as visible if ANY part of its disc is visible.
  Our brief uses "sunlit = disc fraction >= 0.5" and "Earth CENTRE above the mask", which are stricter.
  For a like-for-like check, phase 2 should ALSO compute the "any part of the disc" version for validation.
  * PGDA heights: surface (0 m observer); ours: 2 m observer.  * PGDA window: 18.6-year cycle, hourly.

Usage
  python pipeline/validate.py                  # download + sample + write CSVs
  python pipeline/validate.py --selftest       # also run compare() with ours = PGDA (must give MAE 0, 100 %)
  from pipeline.validate import compare; compare(ours)   # phase 2

Needs: numpy, rasterio (pip install numpy rasterio).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "pgda"
PROCESSED = ROOT / "data" / "processed"
WEB_DATA = ROOT / "web" / "data"
BASE_URL = "https://pgda.gsfc.nasa.gov/data/MoonIllumination/"

R_MOON_M = 1737400.0          # reference sphere (PDS label A_AXIS_RADIUS = 1737.4 km)
DN_SCALE = 0.00004            # PDS label SCALING_FACTOR (DN 25000 -> 1.0)
SEED = 42
N_POINTS = 240
LAT_MIN, LAT_MAX = -90.0, -85.0
NAMED_LAT_LIMIT = -75.0       # named sites must be inside the 75S map
WINDOW = "2020-01-01..2038-08-01"   # our comparison window (card 1 validation ephemeris, 2 h step)
STEP_H = 2

MAPS = {
    # key: (file stem, metres per pixel)
    "sun60":    ("AVGVISIB_85S_060M_201608", 60.0),
    "earth60":  ("AVGVISIB_85S_060M_201608_EARTH", 60.0),
    "sun120":   ("AVGVISIB_75S_120M_201608", 120.0),
    "earth120": ("AVGVISIB_75S_120M_201608_EARTH", 120.0),
}


# --------------------------------------------------------------------------- download
def download(stem: str) -> Path:
    """Download BASE_URL/<stem>.TIF to data/raw/pgda/, resuming a partial file (HTTP Range)."""
    RAW.mkdir(parents=True, exist_ok=True)
    url = BASE_URL + stem + ".TIF"
    dest = RAW / (stem + ".TIF")
    head = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(head, timeout=60) as r:
        total = int(r.headers["Content-Length"])
    have = dest.stat().st_size if dest.exists() else 0
    if have == total:
        print(f"  {dest.name}: present ({total / 1e6:.1f} MB)")
        return dest
    if have > total:
        dest.unlink()
        have = 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    print(f"  {dest.name}: downloading {(total - have) / 1e6:.1f} MB (resume from {have} B)")
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "ab" if have else "wb") as f:
        if have and r.status != 206:      # server ignored Range -> start again
            f.truncate(0)
        while chunk := r.read(1 << 20):
            f.write(chunk)
    if dest.stat().st_size != total:
        sys.exit(f"incomplete download: {dest} - run again to resume")
    return dest


# --------------------------------------------------------------------------- map access
class PolarMap:
    """One PGDA GeoTIFF in memory, values as fractions 0..1, with lat/lon -> pixel lookup."""

    def __init__(self, path: Path, res_m: float):
        import rasterio

        with rasterio.open(path) as d:
            raw = d.read(1)
            self.transform = d.transform
            self.crs = d.crs
            scale = d.scales[0] if d.scales and d.scales[0] not in (None, 0) else 1.0
            offset = d.offsets[0] if d.offsets else 0.0
        if np.issubdtype(raw.dtype, np.integer):
            # GDAL may or may not carry the PDS scaling; the label says DN x 0.00004.
            if abs(scale - 1.0) < 1e-12:
                scale, offset = DN_SCALE, 0.0
            self.data = raw.astype(np.float32) * np.float32(scale) + np.float32(offset)
        else:
            self.data = raw.astype(np.float32)
        if np.nanmax(self.data) > 1.0001:
            raise ValueError(f"{path.name}: values > 1 after scaling - check the scale factor")
        self.name = path.name
        self.res = res_m
        self.h, self.w = self.data.shape

    def xy_to_ij(self, x: np.ndarray, y: np.ndarray):
        """Projected metres -> (row, col) of the pixel containing the point."""
        inv = ~self.transform
        col, row = inv * (x, y)
        return np.floor(row).astype(int), np.floor(col).astype(int)

    def sample(self, x, y, half_m=(60.0, 300.0)):
        """Value at the pixel + min/max inside square windows of +-half_m metres."""
        row, col = self.xy_to_ij(np.atleast_1d(x), np.atleast_1d(y))
        out = []
        for r, c in zip(row, col):
            if not (0 <= r < self.h and 0 <= c < self.w):
                out.append(None)
                continue
            rec = {"value": float(self.data[r, c]), "row": int(r), "col": int(c)}
            for h in half_m:
                k = max(1, int(round(h / self.res)))   # 60 m map: +-60 m -> 1 px, +-300 m -> 5 px
                win = self.data[max(r - k, 0): r + k + 1, max(c - k, 0): c + k + 1]
                rec[f"min{int(h)}"] = float(win.min())
                rec[f"max{int(h)}"] = float(win.max())
                rec[f"half_px{int(h)}"] = k
            out.append(rec)
        return out


def latlon_to_xy(lat, lon):
    """South polar stereographic on a 1737.4 km sphere, true scale at the pole (PDS DSMAP_POLAR).

    rho = 2 R tan(pi/4 + lat/2);  x = rho sin(lon);  y = rho cos(lon)   (Snyder 1987, south polar aspect)
    """
    lat = np.radians(np.asarray(lat, dtype=float))
    lon = np.radians(np.asarray(lon, dtype=float))
    rho = 2.0 * R_MOON_M * np.tan(np.pi / 4.0 + lat / 2.0)
    return rho * np.sin(lon), rho * np.cos(lon)


def check_projection(m: PolarMap):
    """Make sure our formula agrees with the CRS stored in the GeoTIFF (GDAL/PROJ)."""
    from rasterio.crs import CRS
    from rasterio.warp import transform

    lats = np.array([-89.9, -88.0, -86.5, -85.0])
    lons = np.array([0.0, 45.0, -120.0, 170.0])
    x1, y1 = latlon_to_xy(lats, lons)
    moon_geo = CRS.from_proj4(f"+proj=longlat +R={R_MOON_M} +no_defs")
    x2, y2 = transform(moon_geo, m.crs, lons.tolist(), lats.tolist())
    err = float(np.max(np.hypot(x1 - np.array(x2), y1 - np.array(y2))))
    print(f"  projection check vs GeoTIFF CRS: max difference {err:.3f} m")
    if err > 1.0:
        raise ValueError(f"projection mismatch {err:.1f} m - CRS is {m.crs}")


# --------------------------------------------------------------------------- points
def random_points(n=N_POINTS, seed=SEED):
    """n points uniform in area between LAT_MIN and LAT_MAX (sin(lat) uniform), lon -180..180."""
    rng = np.random.default_rng(seed)
    s = rng.uniform(math.sin(math.radians(LAT_MIN)), math.sin(math.radians(LAT_MAX)), n)
    lat = np.degrees(np.arcsin(s))
    lon = rng.uniform(-180.0, 180.0, n)
    return np.round(lat, 5), np.round(lon, 5)


def named_sites():
    p = WEB_DATA / "sites.json"
    sites = json.loads(p.read_text(encoding="utf-8"))
    return [s for s in sites if s["lat"] <= NAMED_LAT_LIMIT]


def build_tables(maps: dict[str, PolarMap]):
    lat, lon = random_points()
    x, y = latlon_to_xy(lat, lon)
    s60 = maps["sun60"].sample(x, y)
    e60 = maps["earth60"].sample(x, y)
    s120 = maps["sun120"].sample(x, y)
    e120 = maps["earth120"].sample(x, y)
    points = []
    for k in range(len(lat)):
        if s60[k] is None or e60[k] is None:
            raise ValueError(f"point {k} ({lat[k]}, {lon[k]}) outside the 85S map")
        points.append({
            "k": k, "lat": float(lat[k]), "lon": float(lon[k]),
            "x_m": round(float(x[k]), 2), "y_m": round(float(y[k]), 2),
            "row60": s60[k]["row"], "col60": s60[k]["col"],
            "pgda_sun": s60[k]["value"], "pgda_sun_min60": s60[k]["min60"], "pgda_sun_max60": s60[k]["max60"],
            "pgda_sun_min300": s60[k]["min300"], "pgda_sun_max300": s60[k]["max300"],
            "pgda_earth": e60[k]["value"], "pgda_earth_min60": e60[k]["min60"], "pgda_earth_max60": e60[k]["max60"],
            "pgda_earth_min300": e60[k]["min300"], "pgda_earth_max300": e60[k]["max300"],
            # same point on the coarser 120 m map: shows how much resolution alone changes the answer
            "pgda120_sun": s120[k]["value"] if s120[k] else None,
            "pgda120_earth": e120[k]["value"] if e120[k] else None,
        })

    named = []
    for s in named_sites():
        sx, sy = latlon_to_xy(s["lat"], s["lon"])
        use = "60" if maps["sun60"].sample(sx, sy)[0] is not None else "120"
        sm = maps["sun" + use].sample(sx, sy)[0]
        em = maps["earth" + use].sample(sx, sy)[0]
        if sm is None:
            print(f"  skip {s['id']}: outside both maps")
            continue
        named.append({
            "id": s["id"], "lat": s["lat"], "lon": s["lon"], "map_res_m": int(use),
            "mock_site": bool(s.get("mock", False)),
            "pgda_sun": sm["value"], "pgda_sun_min300": sm["min300"], "pgda_sun_max300": sm["max300"],
            "pgda_earth": em["value"], "pgda_earth_min300": em["min300"], "pgda_earth_max300": em["max300"],
            "half_px300": sm["half_px300"],
        })
    return points, named


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.5f}" if isinstance(v, float) else v) for k, v in r.items()})
    print(f"  wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


def read_csv(path: Path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k in ("id",):
                continue
            try:
                r[k] = float(v) if v not in ("", "None") else None
            except ValueError:
                pass
    return rows


# --------------------------------------------------------------------------- compare (phase 2)
def _stats(ours, pgda, lo, hi):
    ours, pgda, lo, hi = map(lambda a: np.asarray(a, dtype=float), (ours, pgda, lo, hi))
    d = ours - pgda
    r = float(np.corrcoef(ours, pgda)[0, 1]) if np.std(ours) > 0 and np.std(pgda) > 0 else 0.0
    inside = (ours >= lo) & (ours <= hi)
    return {
        "mae_pp": round(float(np.mean(np.abs(d))) * 100, 3),
        "rmse_pp": round(float(np.sqrt(np.mean(d ** 2))) * 100, 3),
        "r": round(r, 4),
        "within_pgda_60m_spread_pct": round(float(inside.mean()) * 100, 2),
    }


def compare(ours: dict, out: Path | None = None, mock: bool = False) -> dict:
    """Build web/data/validation.json (contract v1.1) from our phase-2 results.

    ours = {
      "points": [{"ours_sun": 0..1, "ours_earth": 0..1}, ...]   # same order as validation_points.csv (240)
      "named":  {"SHACKLETON_RIM": {"ours_sun": .., "ours_earth": ..}, ...}
    }
    Fractions are over WINDOW at STEP_H, observer 2 m above terrain.
    """
    pts = read_csv(PROCESSED / "validation_points.csv")
    named_rows = read_csv(PROCESSED / "validation_named.csv") if (PROCESSED / "validation_named.csv").exists() else []
    if len(ours["points"]) != len(pts):
        raise ValueError(f"ours has {len(ours['points'])} points, expected {len(pts)}")

    points = []
    for p, o in zip(pts, ours["points"]):
        points.append({
            "lat": p["lat"], "lon": p["lon"],
            "ours_sun": round(float(o["ours_sun"]), 5), "pgda_sun": p["pgda_sun"],
            "pgda_sun_min60": p["pgda_sun_min60"], "pgda_sun_max60": p["pgda_sun_max60"],
            "ours_earth": round(float(o["ours_earth"]), 5), "pgda_earth": p["pgda_earth"],
            "pgda_earth_min60": p["pgda_earth_min60"], "pgda_earth_max60": p["pgda_earth_max60"],
        })
    result = {"window": WINDOW, "step_h": STEP_H, "n_points": len(points), "seed": SEED}
    for body in ("sun", "earth"):
        result[body] = _stats([p[f"ours_{body}"] for p in points], [p[f"pgda_{body}"] for p in points],
                              [p[f"pgda_{body}_min60"] for p in points], [p[f"pgda_{body}_max60"] for p in points])
    result["points"] = points
    result["named"] = []
    for n in named_rows:
        o = ours.get("named", {}).get(n["id"])
        if o is None:
            continue
        result["named"].append({
            "id": n["id"],
            "ours_sun": round(float(o["ours_sun"]), 5), "pgda_sun": n["pgda_sun"],
            "pgda_sun_min300": n["pgda_sun_min300"], "pgda_sun_max300": n["pgda_sun_max300"],
            "ours_earth": round(float(o["ours_earth"]), 5), "pgda_earth": n["pgda_earth"],
            "pgda_earth_min300": n["pgda_earth_min300"], "pgda_earth_max300": n["pgda_earth_max300"],
        })
    result["pgda_files"] = [MAPS[k][0] + ".TIF" for k in MAPS]
    result["mock"] = mock
    out = out or (WEB_DATA / "validation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"  wrote {out}: sun {result['sun']}  earth {result['earth']}")
    return result


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true",
                    help="run compare() with ours = PGDA into data/processed/validation_selftest.json")
    args = ap.parse_args()

    print("1) download PGDA maps")
    paths = {k: download(stem) for k, (stem, _) in MAPS.items()}
    print("2) load + decode (DN x 0.00004)")
    maps = {k: PolarMap(paths[k], MAPS[k][1]) for k in MAPS}
    for k, m in maps.items():
        print(f"  {m.name}: {m.w}x{m.h} px, {m.res:.0f} m/px, range {m.data.min():.4f}..{m.data.max():.4f}")
    check_projection(maps["sun60"])
    check_projection(maps["sun120"])
    print("3) sample 240 random points + named sites")
    points, named = build_tables(maps)
    write_csv(points, PROCESSED / "validation_points.csv")
    if named:
        write_csv(named, PROCESSED / "validation_named.csv")
    sun = np.array([p["pgda_sun"] for p in points])
    earth = np.array([p["pgda_earth"] for p in points])
    print(f"  PGDA sun   mean {sun.mean():.3f}, permanently dark points {int((sun == 0).sum())}/{len(sun)}")
    print(f"  PGDA earth mean {earth.mean():.3f}, never-visible points {int((earth == 0).sum())}/{len(earth)}")
    d = np.array([abs(p["pgda_sun"] - p["pgda120_sun"]) for p in points if p["pgda120_sun"] is not None])
    print(f"  60 m vs 120 m map, sun: mean |diff| {d.mean() * 100:.2f} pp, max {d.max() * 100:.2f} pp")

    if args.selftest:
        print("4) self-test: compare() with ours = PGDA (expect MAE 0, r 1, 100 % inside)")
        ours = {"points": [{"ours_sun": p["pgda_sun"], "ours_earth": p["pgda_earth"]} for p in points],
                "named": {n["id"]: {"ours_sun": n["pgda_sun"], "ours_earth": n["pgda_earth"]} for n in named}}
        compare(ours, out=PROCESSED / "validation_selftest.json", mock=True)


if __name__ == "__main__":
    main()
