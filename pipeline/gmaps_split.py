"""Card 14: verify, package, compare and merge split runs of a global map (948 m = ppd 32).

The 948 m map (5760 x 11520) was split by row between two machines (Soyun CPU rows 0:3104,
Jiyong GPU rows 3103:5760; row 3103 is computed by both as an independent cross-check). This tool
never changes an input store; it reads them read-only and writes only new folders.

  verify   check one store (or package): meta, done mask, shapes, NaN/Inf, value ranges, real
           ephemeris/DEMs; optional recomputation of random points with the same engine (--spot N)
  pack     copy a finished row range of a store into a hand-off package with manifest + SHA256
  check    re-hash a package and compare it with its manifest (receiver side)
  compare  compare one row (default 3103) of two sources field by field (no averaging, report only)
  merge    build a NEW full store from row-range parts; refuses on gaps, undone rows, signature
           differences or an overlap row that does not agree (unless a human records a reason)

Sources (SRC) are a store folder (meta.json + done.npy + <field>.npy, as global_maps.py writes),
a package folder (manifest.json), or a row file (*.npz with the fields as keys, compare only).
For a store folder give the row range explicitly as SRC::START:STOP (STOP exclusive).

  python pipeline/gmaps_split.py verify --src data/processed/gmaps_ppd32::0:3104 --spot 12
  python pipeline/gmaps_split.py pack --src data/processed/gmaps_ppd32::0:3104 --out data/processed/handoff/ppd32_rows_0_3104_soyun
  python pipeline/gmaps_split.py check --src data/processed/handoff/ppd32_rows_0_3104_soyun
  python pipeline/gmaps_split.py compare --a data/processed/gmaps_ppd32::0:3104 --b <jiyong package> --row 3103
  python pipeline/gmaps_split.py merge --part data/processed/gmaps_ppd32::0:3104 --part <jiyong package> --out data/processed/gmaps_ppd32_merged
  python pipeline/global_maps.py export --ppd 32 --out data/processed/gmaps_ppd32_merged --web web/data/gmaps_ppd32
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

FIELDS = ("sun", "earth", "both", "h0", "maskmax")
FRACTIONS = ("sun", "earth", "both")
# physical ranges: fractions of time 0..1; LOLA heights about -9.1 .. +10.8 km; elevation angles
RANGES = {"sun": (0.0, 1.0), "earth": (0.0, 1.0), "both": (0.0, 1.0),
          "h0": (-9500.0, 11000.0), "maskmax": (-90.0, 90.0)}
# compare tolerances (absolute). Fractions are sample counts / n_used: 1 sample of 14608 = 6.8e-5.
DEFAULT_TOL = {"sun": 1e-3, "earth": 1e-3, "both": 1e-3, "h0": 0.5, "maskmax": 0.01}
# signature keys that must be identical between merged parts
SIG_KEYS = ("engine_version", "naz", "near_km", "max_km", "step_frac", "n_steps", "obs_height_m",
            "sun_radius_deg", "near", "far", "ephem")
GRID = "pixel centres; lat 90 - (r+0.5)/ppd, lon -180 + (c+0.5)/ppd (MOON_ME)"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


# =========================================================================== sources
class Source:
    """Read-only view of rows [r0, r1) of a store or a package. row(f, r) uses global row numbers."""

    def __init__(self, spec):
        path, _, rng = str(spec).partition("::")
        self.path = Path(path)
        if (self.path / "manifest.json").exists():
            self.kind = "package"
            man = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
            self.manifest = man
            self.meta = man["store_meta"]
            self.r0, self.r1 = man["rows"]["start"], man["rows"]["stop"]
            if rng and tuple(map(int, rng.split(":"))) != (self.r0, self.r1):
                raise SystemExit(f"{spec}: package holds rows {self.r0}:{self.r1}")
            self.arr = {f: np.load(self.path / man["files"][f]["name"], mmap_mode="r") for f in FIELDS}
            self.done_local = np.load(self.path / man["files"]["done"]["name"], mmap_mode="r")
        elif (self.path / "meta.json").exists():
            self.kind = "store"
            if not rng:
                raise SystemExit(f"{spec}: give the row range of a store as {path}::START:STOP")
            self.r0, self.r1 = map(int, rng.split(":"))
            self.meta = json.loads((self.path / "meta.json").read_text(encoding="utf-8"))
            self.arr = {f: np.load(self.path / f"{f}.npy", mmap_mode="r") for f in FIELDS}
            self.done_local = np.load(self.path / "done.npy", mmap_mode="r")[self.r0:self.r1]
        else:
            raise SystemExit(f"{spec}: neither a store (meta.json) nor a package (manifest.json)")
        self.nlat, self.nlon = int(self.meta["nlat"]), int(self.meta["nlon"])
        if not (0 <= self.r0 < self.r1 <= self.nlat):
            raise SystemExit(f"{spec}: bad row range {self.r0}:{self.r1} for nlat {self.nlat}")
        self.sig = self.meta["signature"]

    def rows(self, f):
        """Array of shape (r1 - r0, nlon) for the declared range."""
        a = self.arr[f]
        return a[self.r0:self.r1] if self.kind == "store" else a

    def row(self, f, r):
        if not (self.r0 <= r < self.r1):
            raise KeyError(f"row {r} not in {self.path} ({self.r0}:{self.r1})")
        return np.asarray(self.rows(f)[r - self.r0], dtype=np.float64)

    def label(self):
        return f"{self.path} [{self.kind} rows {self.r0}:{self.r1}]"


def load_row(spec, r):
    """Dict field -> row values from a store/package source or a row .npz file."""
    p = Path(str(spec).split("::")[0])
    if p.suffix == ".npz":
        with np.load(p) as z:
            return {f: np.asarray(z[f], dtype=np.float64) for f in FIELDS if f in z.files}, None
    s = Source(spec)
    return {f: s.row(f, r) for f in FIELDS}, s.sig


# =========================================================================== verify
def verify_source(src, spot=0, seed=0, raw=None, ephem=None, log=print):
    """Return a report dict; report['ok'] is False on any hard failure."""
    rep = {"source": src.label(), "checked_utc": now(), "problems": [], "warnings": []}
    P, W = rep["problems"], rep["warnings"]
    m = src.meta
    ppd = int(m["ppd"])
    if (src.nlat, src.nlon) != (180 * ppd, 360 * ppd):
        P.append(f"nlat/nlon {src.nlat}x{src.nlon} do not match ppd {ppd}")
    sig = src.sig
    if sig["ephem"]["mock"] is not False:
        P.append("ephemeris is mock")
    for k in ("near", "far"):
        if str(sig[k]["name"]).startswith("SYNTH"):
            P.append(f"{k} DEM is synthetic ({sig[k]['name']})")
    if m.get("grid", GRID) != GRID:
        P.append(f"grid definition differs: {m.get('grid')}")
    done = np.asarray(src.done_local)
    n = src.r1 - src.r0
    rep["rows"] = {"start": src.r0, "stop": src.r1, "n": n, "done": int(done.sum())}
    if done.shape != (n,):
        P.append(f"done mask shape {done.shape}, expected ({n},)")
    elif not done.all():
        bad = np.flatnonzero(done == 0) + src.r0
        P.append(f"{bad.size} rows not done in {src.r0}:{src.r1} (first {bad[:10].tolist()})")
    rep["fields"] = {}
    for f in FIELDS:
        a = src.rows(f)
        d = {"shape": list(a.shape), "dtype": str(a.dtype)}
        if a.shape != (n, src.nlon) or a.dtype != np.float32:
            P.append(f"{f}: shape {a.shape} dtype {a.dtype}, expected ({n}, {src.nlon}) float32")
            rep["fields"][f] = d
            continue
        nan = inf = 0
        lo, hi, s, cnt = math.inf, -math.inf, 0.0, 0
        out_lo, out_hi = RANGES[f]
        n_out = 0
        for i in range(0, n, 256):                       # chunked: memmaps stay small in RAM
            b = np.asarray(a[i:i + 256], dtype=np.float64)
            nan += int(np.isnan(b).sum())
            inf += int(np.isinf(b).sum())
            g = b[np.isfinite(b)]
            if g.size:
                lo, hi = min(lo, g.min()), max(hi, g.max())
                s += g.sum()
                cnt += g.size
                n_out += int(((g < out_lo - 1e-6) | (g > out_hi + 1e-6)).sum())
        d.update(nan=nan, inf=inf, min=lo if cnt else None, max=hi if cnt else None,
                 mean=s / cnt if cnt else None, out_of_range=n_out, range=[out_lo, out_hi])
        if nan or inf:
            P.append(f"{f}: {nan} NaN, {inf} Inf in done rows")
        if n_out:
            P.append(f"{f}: {n_out} values outside {RANGES[f]}")
        rep["fields"][f] = d
    # both = sunlit AND Earth visible  ->  both <= earth everywhere
    viol = 0
    for i in range(0, n, 256):
        viol += int((np.asarray(src.rows("both")[i:i + 256]) > np.asarray(src.rows("earth")[i:i + 256]) + 1e-6).sum())
    rep["both_le_earth_violations"] = viol
    if viol:
        P.append(f"{viol} points with both > earth")
    # fractions must be multiples of 1/n_used for earth/both (counts of samples)
    nu = int(sig["ephem"]["n_used"])
    smp = np.asarray(src.rows("earth")[:: max(1, n // 16)], dtype=np.float64).ravel()[::97]
    q = np.abs(smp * nu - np.round(smp * nu)).max() if smp.size else 0.0
    rep["earth_count_quantisation_max"] = float(q)
    if q > 0.02:
        W.append(f"earth values are not multiples of 1/{nu} (max residual {q:.3f} samples)")
    if spot:
        rep["spot"] = spot_check(src, spot, seed, raw, ephem, log)
        if rep["spot"].get("max_abs_diff") is None or rep["spot"]["n_bad"]:
            P.append(f"spot recomputation disagrees: {rep['spot']}")
    rep["ok"] = not P
    return rep


def spot_check(src, n, seed, raw, ephem, log=print):
    """Recompute n random points with global_maps' engine and the store's own settings."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import global_maps as gm
    sig = src.sig
    root = gm.ROOT
    near, far = gm.load_dems(raw or root / "data" / "raw", sig["near"]["name"], sig["far"]["name"])
    eph = gm.load_ephem(ephem or root / "web" / "data" / sig["ephem"]["file"], sig["ephem"]["step_h"])
    eng = gm.Engine(near, far, eph, naz=sig["naz"], near_km=sig["near_km"], max_km=sig["max_km"],
                    step_frac=sig["step_frac"])
    esig = eng.signature()
    diff = [k for k in SIG_KEYS if esig.get(k) != sig.get(k)]
    if diff:
        return {"max_abs_diff": None, "n_bad": n, "note": f"engine signature differs from store: {diff}"}
    rng = random.Random(seed)
    pts = [(rng.randrange(src.r0, src.r1), rng.randrange(src.nlon)) for _ in range(n)]
    lat_ax, lon_ax = gm.grid_axes(int(src.meta["ppd"]))
    lat = np.array([lat_ax[r] for r, _ in pts])
    lon = np.array([lon_ax[c] for _, c in pts])
    log(f"spot check: recomputing {n} points with {esig['near']['name']}/{esig['far']['name']}, "
        f"ephem {esig['ephem']['sha1_12']} ...")
    out = eng.points(lat, lon)
    worst, n_bad, rows = 0.0, 0, []
    for k, (r, c) in enumerate(pts):
        stored = [float(src.row(f, r)[c]) for f in FIELDS]
        new = [float(x) for x in out[k, :5]]
        # float32 storage: compare at float32 precision
        dd = [abs(np.float32(a) - np.float32(b)) for a, b in zip(stored, new)]
        tol = [1e-6, 1e-6, 1e-6, 1e-3, 1e-4]
        bad = any(x > t for x, t in zip(dd, tol))
        n_bad += bad
        worst = max(worst, max(dd[:3]))
        rows.append({"row": r, "col": c, "lat": round(float(lat[k]), 5), "lon": round(float(lon[k]), 5),
                     "stored": [round(x, 7) for x in stored], "recomputed": [round(x, 7) for x in new]})
    return {"n": n, "seed": seed, "n_bad": n_bad, "max_abs_diff": float(worst), "points": rows}


# =========================================================================== pack / check
README = """# 948 m (ppd 32) global map - row package {r0}:{r1}

Produced by `pipeline/gmaps_split.py pack` (card 14) from `{store}` on host `{host}`, {utc}.
Values are real: LOLA LDEM_64 (474 m, to 150 km) + LDEM_16 (1895 m, to 300 km), ephemeris
`{ephem_file}` (sha1_12 `{ephem_sha}`, {n_used} samples every {step_h} h from {start}, mock = false).

## Rows and grid (read this before merging)
* Rows **{r0} to {last} inclusive** (`{r0}:{r1}` with STOP exclusive), {n} rows; full map 5760 x 11520.
* Arrays are `float32`, little-endian `.npy`, C order, shape `({n}, 11520)` = `[row, column]`.
* Local index `i` in these files = global row `{r0} + i`.
* Global row `r` -> latitude `90 - (r + 0.5) / 32` deg (row 0 = +89.984 deg, north on top).
  Row {r0} = {lat0:+.4f} deg, row {last} = {lat1:+.4f} deg.
* Column `c` -> longitude `-180 + (c + 0.5) / 32` deg east (MOON_ME, -180..180), column 0 = -179.984 deg.
* Pixel centres, not edges.

## Fields
| file | meaning | units |
|---|---|---|
| sun.npy | mean visible fraction of the solar disk (radius 0.2666 deg) over the ephemeris | 0..1 |
| earth.npy | fraction of time the Earth centre is above the horizon mask | 0..1 |
| both.npy | fraction of time sunlit (disk fraction >= 0.5) AND Earth visible | 0..1 |
| h0.npy | terrain height at the point, above R = 1737.4 km (observer is 2 m higher) | m |
| maskmax.npy | highest horizon elevation over the {naz} azimuths | deg |
| done.npy | uint8 per row, 1 = computed (all 1 here) | - |

`store_meta.json` is the original `meta.json` (parameter signature). `manifest.json` lists every file
with bytes, shape, dtype and SHA256. `row_{keep}.npz` = row {keep} only (the overlap row for the
CPU/GPU comparison), same values as row {keep} of the big files.

## Verify after transfer
```
python pipeline/gmaps_split.py check --src <this folder>
```
or without the repository (PowerShell): `Get-FileHash -Algorithm SHA256 *.npy` and compare with
`manifest.json`. `manifest.json` -> `inputs_sha256` holds the SHA256 of the DEM and ephemeris files
used; the other machine should hash its own copies (`Get-FileHash -Algorithm SHA256 <file>`) and compare.

## Merge (receiver)
```
python pipeline/gmaps_split.py compare --a <this folder> --b <other part> --row {keep}
python pipeline/gmaps_split.py merge --part <this folder> --part <other part> --out data/processed/gmaps_ppd32_merged
```
Do not average or overwrite rows by hand; `merge` refuses when the parts disagree.
"""


def pack(src, out, keep_row=None, inputs=(), log=print):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} exists and is not empty - choose a new folder")
    rep = verify_source(src, log=log)
    if not rep["ok"]:
        raise SystemExit("refusing to pack, source fails verify:\n  " + "\n  ".join(rep["problems"]))
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for f in FIELDS:
        name = f"{f}.npy"
        a = src.rows(f)
        m = np.lib.format.open_memmap(out / name, mode="w+", dtype=np.float32, shape=a.shape)
        for i in range(0, a.shape[0], 256):
            m[i:i + 256] = a[i:i + 256]
        m.flush()
        del m
        log(f"  {name}: {a.shape}")
    np.save(out / "done.npy", np.asarray(src.done_local, dtype=np.uint8))
    write_json(out / "store_meta.json", src.meta)
    if keep_row is not None:
        np.savez(out / f"row_{keep_row}.npz", row=np.int64(keep_row), **{f: np.array(src.row(f, keep_row), np.float32) for f in FIELDS})
    for p in sorted(out.iterdir()):
        if p.suffix in (".npy", ".npz", ".json") and p.name != "manifest.json":
            e = {"name": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
            if p.suffix == ".npy":
                a = np.load(p, mmap_mode="r")
                e.update(shape=list(a.shape), dtype=str(a.dtype))
            files[p.stem] = e
    ppd = int(src.meta["ppd"])
    lat = lambda r: 90 - (r + 0.5) / ppd  # noqa: E731
    sig = src.sig
    man = {"what": "card 14 split global map, row package", "created_utc": now(), "host": platform.node(),
           "source_store": str(src.path), "rows": {"start": src.r0, "stop": src.r1, "stop_exclusive": True,
                                                   "lat_first": lat(src.r0), "lat_last": lat(src.r1 - 1)},
           "grid": GRID, "array_order": "[row - start, column], C order, float32 little-endian",
           "keep_row": keep_row, "files": files, "store_meta": src.meta, "verify": rep,
           "inputs_sha256": {Path(i).name: {"bytes": Path(i).stat().st_size, "sha256": sha256(i)} for i in inputs}}
    write_json(out / "manifest.json", man)
    e = sig["ephem"]
    (out / "README.md").write_text(README.format(
        r0=src.r0, r1=src.r1, last=src.r1 - 1, n=src.r1 - src.r0, store=src.path, host=platform.node(), utc=now(),
        ephem_file=e["file"], ephem_sha=e["sha1_12"], n_used=e["n_used"], step_h=e["step_h"], start=e["start"],
        lat0=lat(src.r0), lat1=lat(src.r1 - 1), naz=sig["naz"], keep=keep_row), encoding="utf-8")
    total = sum(v["bytes"] for v in files.values())
    log(f"package {out}: {len(files)} files, {total / 1e6:.1f} MB")
    return man


def check_package(path, log=print):
    path = Path(path)
    man = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    bad = []
    for k, e in man["files"].items():
        p = path / e["name"]
        if not p.exists():
            bad.append(f"missing {e['name']}")
            continue
        if p.stat().st_size != e["bytes"]:
            bad.append(f"{e['name']}: {p.stat().st_size} bytes, manifest {e['bytes']}")
        elif sha256(p) != e["sha256"]:
            bad.append(f"{e['name']}: SHA256 differs")
        else:
            log(f"  ok {e['name']} {e['bytes']} B")
    return bad


# =========================================================================== compare
def sig_diff(a, b):
    return [k for k in SIG_KEYS if a.get(k) != b.get(k)]


def compare_rows(ra, rb, tol=None, n_used=None):
    """Field-by-field comparison of two rows. Never modifies or averages anything."""
    tol = {**DEFAULT_TOL, **(tol or {})}
    out = {"tolerance": tol, "fields": {}}
    ok = True
    for f in FIELDS:
        if f not in ra or f not in rb:
            out["fields"][f] = {"missing": True}
            ok = False
            continue
        a, b = np.asarray(ra[f], np.float64), np.asarray(rb[f], np.float64)
        if a.shape != b.shape:
            out["fields"][f] = {"shape_a": list(a.shape), "shape_b": list(b.shape)}
            ok = False
            continue
        nan_mis = int((np.isnan(a) != np.isnan(b)).sum())
        both_ok = np.isfinite(a) & np.isfinite(b)
        d = np.where(both_ok, b - a, 0.0)
        ad = np.abs(d)
        nbad = int((ad > tol[f] * (1 + 1e-9) + 1e-12).sum())   # boundary-safe
        worst = np.argsort(ad)[::-1][:5]
        e = {"n": int(a.size), "nan_mismatch": nan_mis, "max_abs": float(ad.max()) if a.size else 0.0,
             "mean_abs": float(ad[both_ok].mean()) if both_ok.any() else None,
             "mean_signed_b_minus_a": float(d[both_ok].mean()) if both_ok.any() else None,
             "n_exact": int((d[both_ok] == 0).sum()), "n_over_tol": nbad,
             "worst": [{"col": int(c), "a": float(a[c]), "b": float(b[c])} for c in worst if ad[c] > 0]}
        if f in FRACTIONS and n_used:
            e["max_abs_in_samples"] = float(ad.max() * n_used)
        out["fields"][f] = e
        ok &= (nbad == 0 and nan_mis == 0)
    # hints for the cause when they differ: are differences where the horizon is high / terrain steep?
    if not ok and all(f in ra and f in rb for f in FIELDS):
        dm = np.abs(np.asarray(rb["maskmax"]) - np.asarray(ra["maskmax"]))
        dh = np.abs(np.asarray(rb["h0"]) - np.asarray(ra["h0"]))
        ds = np.abs(np.asarray(rb["sun"]) - np.asarray(ra["sun"]))
        out["diagnosis"] = {
            "points_h0_differs": int((dh > tol["h0"]).sum()),
            "points_maskmax_differs": int((dm > tol["maskmax"]).sum()),
            "sun_diff_where_maskmax_same": int(((ds > tol["sun"]) & (dm <= tol["maskmax"])).sum()),
            "hint": "h0 differs -> DEM file / sampling differs; maskmax differs with same h0 -> horizon "
                    "marching (steps, DEM switch at near_km, curvature, float32); sun/earth differ with the "
                    "same maskmax -> ephemeris subset, step, solar-disk model or time window",
        }
    out["ok"] = bool(ok)
    return out


# =========================================================================== merge
def merge(parts, out, tol=None, accept_reason=None, log=print):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} exists and is not empty - merge only writes a NEW folder")
    srcs = [Source(p) for p in parts]
    base = srcs[0]
    nlat, nlon = base.nlat, base.nlon
    problems = []
    for s in srcs[1:]:
        if (s.nlat, s.nlon) != (nlat, nlon):
            problems.append(f"{s.label()}: grid {s.nlat}x{s.nlon} != {nlat}x{nlon}")
        d = sig_diff(base.sig, s.sig)
        if d:
            problems.append(f"{s.label()}: signature differs from {base.label()} in {d}")
        if s.meta.get("grid", GRID) != base.meta.get("grid", GRID):
            problems.append(f"{s.label()}: grid definition differs")
    for s in srcs:
        r = verify_source(s, log=log)
        if not r["ok"]:
            problems += [f"{s.label()}: {p}" for p in r["problems"]]
    cover = np.zeros(nlat, np.int32)
    for s in srcs:
        cover[s.r0:s.r1] += 1
    gaps = np.flatnonzero(cover == 0)
    if gaps.size:
        problems.append(f"{gaps.size} rows covered by no part (first {gaps[:10].tolist()})")
    overlap = np.flatnonzero(cover > 1).tolist()
    if problems:
        raise SystemExit("merge refused:\n  " + "\n  ".join(problems))
    cmp = {}
    disagree = []
    for r in overlap:
        have = [s for s in srcs if s.r0 <= r < s.r1]
        for s in have[1:]:
            c = compare_rows({f: have[0].row(f, r) for f in FIELDS}, {f: s.row(f, r) for f in FIELDS},
                             tol, int(base.sig["ephem"]["n_used"]))
            cmp[f"{r}: {have[0].path.name} vs {s.path.name}"] = c
            if not c["ok"]:
                disagree.append(r)
    if disagree and not accept_reason:
        rep = out.parent / f"{out.name}_overlap_report.json"
        write_json(rep, cmp)
        raise SystemExit(f"merge refused: overlap rows {disagree} disagree beyond tolerance; report -> {rep}.\n"
                         f"Find the cause first. Only if a person decides the difference is acceptable, rerun "
                         f"with --accept-overlap-diff \"<reason>\" (the first --part supplies overlap rows).")
    out.mkdir(parents=True)
    owner = np.full(nlat, -1, np.int32)
    for i in range(len(srcs) - 1, -1, -1):        # first part wins on overlap rows (documented)
        owner[srcs[i].r0:srcs[i].r1] = i
    for f in FIELDS:
        m = np.lib.format.open_memmap(out / f"{f}.npy", mode="w+", dtype=np.float32, shape=(nlat, nlon))
        for i, s in enumerate(srcs):
            rows = np.flatnonzero(owner == i)
            for a in range(0, rows.size, 256):
                rr = rows[a:a + 256]
                m[rr] = np.asarray(s.rows(f)[rr - s.r0], dtype=np.float32)
        m.flush()
        del m
        log(f"  merged {f}")
    np.save(out / "done.npy", np.ones(nlat, np.uint8))
    meta = {**{k: base.meta[k] for k in ("ppd", "nlat", "nlon", "signature")}, "grid": base.meta.get("grid", GRID),
            "created_utc": now(),
            "merged_from": [{"source": s.label(), "rows": [s.r0, s.r1], "rows_used": int((owner == i).sum()),
                             "host": getattr(s, "manifest", {}).get("host"), "created_utc": s.meta.get("created_utc")}
                            for i, s in enumerate(srcs)],
            "overlap_rows": overlap, "overlap_rule": "first --part supplies overlap rows; the others are only compared",
            "overlap_ok": not disagree, "overlap_accept_reason": accept_reason}
    write_json(out / "meta.json", meta)
    write_json(out / "merge_report.json", {"overlap": cmp, "merged_utc": now()})
    final = verify_source(Source(f"{out}::0:{nlat}"), log=log)
    write_json(out / "verify_report.json", final)
    if not final["ok"]:
        raise SystemExit(f"merged store fails verify: {final['problems']}")
    log(f"merged store {out}: {nlat}/{nlat} rows, overlap rows {overlap} ok={not disagree}")
    return meta


# =========================================================================== CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("verify")
    p.add_argument("--src", required=True)
    p.add_argument("--spot", type=int, default=0, help="recompute N random points with the engine")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--raw", default=None)
    p.add_argument("--ephem", default=None)
    p.add_argument("--report", default=None)
    p = sub.add_parser("pack")
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--keep-row", type=int, default=None)
    p.add_argument("--input", action="append", default=[], help="DEM / ephemeris file to hash into the manifest")
    p = sub.add_parser("check")
    p.add_argument("--src", required=True)
    p = sub.add_parser("compare")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--row", type=int, default=3103)
    p.add_argument("--report", default=None)
    p = sub.add_parser("merge")
    p.add_argument("--part", action="append", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--accept-overlap-diff", default=None, metavar="REASON")
    for q in (sub.choices["compare"], sub.choices["merge"]):
        for f in FIELDS:
            q.add_argument(f"--tol-{f}", type=float, default=DEFAULT_TOL[f])
    a = ap.parse_args(argv)

    if a.cmd == "verify":
        rep = verify_source(Source(a.src), a.spot, a.seed, a.raw, a.ephem)
        if a.report:
            write_json(a.report, rep)
        print(json.dumps({k: v for k, v in rep.items() if k != "spot"}, indent=1))
        if "spot" in rep:
            print("spot:", {k: v for k, v in rep["spot"].items() if k != "points"})
        print("VERIFY", "PASS" if rep["ok"] else "FAIL")
        return 0 if rep["ok"] else 1
    if a.cmd == "pack":
        pack(Source(a.src), a.out, a.keep_row, a.input)
        return 0
    if a.cmd == "check":
        bad = check_package(a.src)
        print("CHECK", "PASS" if not bad else "FAIL: " + "; ".join(bad))
        return 0 if not bad else 1
    tol = {f: getattr(a, f"tol_{f}") for f in FIELDS}
    if a.cmd == "compare":
        ra, sa = load_row(a.a, a.row)
        rb, sb = load_row(a.b, a.row)
        rep = {"row": a.row, "a": a.a, "b": a.b}
        if sa is not None and sb is not None:
            rep["signature_diff"] = sig_diff(sa, sb)
        nu = int((sa or sb or {"ephem": {"n_used": 0}})["ephem"]["n_used"]) or None
        rep.update(compare_rows(ra, rb, tol, nu))
        if rep.get("signature_diff"):
            rep["ok"] = False
        if a.report:
            write_json(a.report, rep)
        print(json.dumps(rep, indent=1))
        print("COMPARE", "PASS" if rep["ok"] else "FAIL")
        return 0 if rep["ok"] else 1
    if a.cmd == "merge":
        merge(a.part, a.out, tol, a.accept_overlap_diff)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
