"""Task T: publish the original 3.8 km (ppd 8) whole-Moon float32 grid losslessly, and check publication integrity.

Producer side (Soyun Jeong ran the ppd 8 map in card 9, PR #9). This script does NOT verify the science of the map;
independent recomputation must be done by another team member (docs/task_t_gmaps_ppd8_float32.md, section "Handoff").

  package  copy data/processed/gmaps_ppd8/{sun,earth,both,h0,maskmax,done}.npy + meta.json byte for byte into
           data/processed/task_t_release/<NAME>/, write MANIFEST.json and SHA256SUMS.txt (also copied to docs/task_t/)
  check    DIR: compare a released copy (staging or downloaded) with the local originals: SHA-256, .npy headers,
           shape/dtype, float32 bit patterns, NaN positions, done mask, meta.json bytes
  export   DIR: from the released arrays, re-run the production export steps (global_maps.resample/colorize, the
           same PIL calls) and compare with the published web/data/gmaps/ values PNGs, overview JPEGs, tiles and
           index.json statistics -> docs/task_t/integrity_check.json

  .venv/Scripts/python -X utf8 pipeline/task_t_gmaps_ppd8_raw.py package
  .venv/Scripts/python -X utf8 pipeline/task_t_gmaps_ppd8_raw.py check data/processed/task_t_release/gmaps_ppd8_float32_v1
  .venv/Scripts/python -X utf8 pipeline/task_t_gmaps_ppd8_raw.py export data/processed/task_t_release/gmaps_ppd8_float32_v1
"""
import hashlib
import io
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/processed/gmaps_ppd8"
NAME = "gmaps_ppd8_float32_v1"
STAGE = ROOT / "data/processed/task_t_release" / NAME
DOCS = ROOT / "docs/task_t"
WEB = ROOT / "web/data/gmaps"
FIELDS = ["sun", "earth", "both", "h0", "maskmax"]
FILES = [f"{f}.npy" for f in FIELDS] + ["done.npy", "meta.json"]
RELEASE_TAG = "task-t-gmaps-ppd8-float32-v1"
REPO = "kiisophii/lunar-landing-site-navigator"
PPD, NLAT, NLON = 8, 1440, 2880
R_KM = 1737.4

DEFINITIONS = {
    "sun": "mean visible fraction of the solar disc (radius 0.2666 deg) above the 360-azimuth horizon mask, averaged "
           "over 21,912 ephemeris samples (every 2 h, 2026-01-01T00Z..2030-12-31T22Z); 0..1. NOT the sunlit-hours "
           "fraction of core.js",
    "earth": "fraction of the same samples with the Earth centre (topocentric) strictly above the mask; 0..1",
    "both": "fraction of the same samples with disc fraction >= 0.5 AND Earth centre above the mask; 0..1",
    "h0": "terrain height (m) at the cell centre above the 1737.4 km sphere, bilinear from LDEM_64 (LDEM_16 if NaN)",
    "maskmax": "maximum of the 360-azimuth horizon mask elevation (deg) at the cell centre (observer h0 + 2 m)",
}


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def npy_header(path):
    with open(path, "rb") as f:
        major, minor = np.lib.format.read_magic(f)
        reader = np.lib.format.read_array_header_1_0 if major == 1 else np.lib.format.read_array_header_2_0
        shape, fortran, dtype = reader(f)
        offset = f.tell()
    return dict(version=f"{major}.{minor}", descr=dtype.str, shape=list(shape), fortran_order=bool(fortran), data_offset=offset)


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def ephem_sha1_12(step_h=2):
    """The engine's signature hash: SHA-1 of the float64 copy of every step_h-th ephem.bin row (global_maps.load_ephem)."""
    v = np.fromfile(ROOT / "web/data/ephem.bin", dtype="<f4").astype(np.float64).reshape(-1, 6)[::step_h]
    return hashlib.sha1(np.ascontiguousarray(v).tobytes()).hexdigest()[:12], int(v.shape[0])


def field_stats(a):
    fin = np.isfinite(a)
    return dict(nan_count=int(np.isnan(a).sum()), inf_count=int(np.isinf(a).sum()), finite_count=int(fin.sum()),
                min=float(a[fin].min()) if fin.any() else None, max=float(a[fin].max()) if fin.any() else None)


def package():
    meta = json.loads((SRC / "meta.json").read_text(encoding="utf-8"))
    assert meta["ppd"] == PPD and meta["nlat"] == NLAT and meta["nlon"] == NLON, meta
    STAGE.mkdir(parents=True, exist_ok=True)
    files = []
    for name in FILES:
        src, dst = SRC / name, STAGE / name
        shutil.copyfile(src, dst)
        rec = dict(name=name, bytes=dst.stat().st_size, sha256=sha256(dst))
        assert rec["sha256"] == sha256(src)
        if name.endswith(".npy"):
            rec["npy"] = npy_header(dst)
            a = np.load(dst)
            rec.update(field_stats(a) if a.dtype.kind == "f" else dict(all_rows_done=bool(np.all(a == 1)), rows_done=int((a == 1).sum())))
            if name[:-4] in DEFINITIONS:
                rec["definition"] = DEFINITIONS[name[:-4]]
        files.append(rec)
    sig = meta["signature"]
    sha1_now, n_used = ephem_sha1_12(sig["ephem"]["step_h"])
    dems = []
    for key in ("near", "far"):
        d = sig[key]
        p = ROOT / "data/raw/global" / d["file"]
        dems.append(dict(role=key, name=d["name"], file=d["file"], res_m=d["res_m"], bytes_in_signature=d["bytes"],
                         bytes_local=p.stat().st_size if p.exists() else None, sha256_local=sha256(p) if p.exists() else None,
                         to_km=sig["near_km"] if key == "near" else sig["max_km"],
                         url=f"https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/{d['file']}"))
    manifest = dict(
        name=NAME, format="NumPy .npy v1.0, little-endian float32 ('<f4'), C order (row-major); files are the original "
                          "memmaps of the producing run, copied byte for byte (no recompression, no quantisation)",
        producer="Soyun Jeong (card 9 run, PR #9, commit 7de0271); engine pipeline/global_maps.py by Sua Kim",
        release=dict(repo=REPO, tag=RELEASE_TAG, url=f"https://github.com/{REPO}/releases/tag/{RELEASE_TAG}",
                     download=f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/<file>"),
        grid=dict(ppd=PPD, shape=[NLAT, NLON], rows="r = 0..1439, north to south", cols="c = 0..2879, west to east",
                  lat_centre_deg="90 - (r + 0.5) / 8", lon_centre_deg="-180 + (c + 0.5) / 8",
                  frame="MOON_ME (mean Earth / polar axis, DE421), sphere R = 1737.4 km",
                  spacing_deg=1 / PPD, spacing_km_equator=round(2 * math.pi * R_KM / NLON, 4),
                  note="pixel centres; meta.json 'grid' string is the producer's own statement"),
        no_data="NaN = cell not computed (rows with done.npy == 0). This run has done = 1 for all 1440 rows and 0 NaN in every field",
        fields=DEFINITIONS, files=files,
        computation=dict(meta_json=meta,
                         ephemeris=dict(file="web/data/ephem.bin", step_h=sig["ephem"]["step_h"], n_used=sig["ephem"]["n_used"],
                                        samples="hours 0, 2, 4, ..., 43822 from 2026-01-01T00:00:00Z (2026-01-01T00Z..2030-12-31T22Z)",
                                        sha1_12_in_signature=sig["ephem"]["sha1_12"], sha1_12_of_current_file=sha1_now,
                                        n_used_of_current_file=n_used, current_file_matches=sha1_now == sig["ephem"]["sha1_12"],
                                        sha256_current_file=sha256(ROOT / "web/data/ephem.bin"),
                                        ephem_bin_last_commit=git("log", "-1", "--format=%h %cI", "--", "web/data/ephem.bin")),
                         dems=dems,
                         engine=dict(file="pipeline/global_maps.py", sha256_current=sha256(ROOT / "pipeline/global_maps.py"),
                                     last_commit=git("log", "-1", "--format=%h %cI %s", "--", "pipeline/global_maps.py"),
                                     run_commit="7de0271 (card 9, PR #9)", engine_version=sig["engine_version"],
                                     command="python pipeline/global_maps.py run --ppd 8 (then export --ppd 8)"),
                         params={k: sig[k] for k in ("naz", "near_km", "max_km", "step_frac", "n_steps", "obs_height_m", "sun_radius_deg")}),
        derived_products=dict(web_gmaps_index_sha256=sha256(WEB / "index.json"),
                              note="web/data/gmaps/ (JPEG tiles, overviews, 8-bit values PNG) were exported from these arrays; "
                                   "see docs/task_t/integrity_check.json"),
        independent_verification="PENDING - must be done by a team member other than Soyun Jeong (producer)")
    text = json.dumps(manifest, indent=1, ensure_ascii=False) + "\n"
    (STAGE / "MANIFEST.json").write_text(text, encoding="utf-8", newline="\n")
    sums = "".join(f"{sha256(STAGE / n)}  {n}\n" for n in FILES + ["MANIFEST.json"])
    (STAGE / "SHA256SUMS.txt").write_text(sums, encoding="utf-8", newline="\n")
    DOCS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STAGE / "MANIFEST.json", DOCS / "MANIFEST.json")
    shutil.copyfile(STAGE / "SHA256SUMS.txt", DOCS / "SHA256SUMS.txt")
    print(sums, f"staged in {STAGE}; ephem match {sha1_now == sig['ephem']['sha1_12']}")


def check(d):
    d = Path(d)
    sums = dict(reversed(line.split("  ", 1)) for line in (DOCS / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines())
    sums = {k.strip(): v for k, v in sums.items()}
    out = dict(dir=str(d), files={})
    for name in FILES + ["MANIFEST.json"]:
        p = d / name
        r = dict(present=p.exists())
        if p.exists():
            r["sha256"] = sha256(p)
            r["sha256_matches_SHA256SUMS"] = r["sha256"] == sums.get(name)
            if (SRC / name).exists():
                r["bytes_identical_to_original"] = p.read_bytes() == (SRC / name).read_bytes()
            if name.endswith(".npy"):
                a, o = np.load(p), np.load(SRC / name)
                r["header"] = npy_header(p)
                r["header_identical"] = r["header"] == npy_header(SRC / name)
                r["shape_ok"] = list(a.shape) == ([NLAT, NLON] if name != "done.npy" else [NLAT])
                r["dtype"] = a.dtype.str
                if a.dtype.kind == "f":
                    r["dtype_ok"] = a.dtype.str == "<f4"
                    r["array_equal_nan"] = bool(np.array_equal(a, o, equal_nan=True))
                    r["bit_patterns_identical"] = bool(np.array_equal(a.view("<u4"), o.view("<u4")))
                    r["nan_positions_identical"] = bool(np.array_equal(np.isnan(a), np.isnan(o)))
                    r.update(field_stats(a))
                else:
                    r["all_rows_done"] = bool(np.all(a == 1))
        out["files"][name] = r
    ok = all(r["present"] and r.get("sha256_matches_SHA256SUMS") and r.get("bytes_identical_to_original", True)
             and all(r.get(k, True) for k in ("header_identical", "shape_ok", "dtype_ok", "array_equal_nan",
                                              "bit_patterns_identical", "nan_positions_identical", "all_rows_done"))
             for r in out["files"].values())
    out["all_ok"] = bool(ok)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ('sha256_matches_SHA256SUMS', 'bytes_identical_to_original', 'bit_patterns_identical', 'nan_positions_identical')} for k, v in out["files"].items()}, indent=1))
    print("ALL OK" if ok else "FAILURES")
    return out


def export_compare(d):
    """Re-run the production export steps on the released arrays and compare with web/data/gmaps/ (integrity only)."""
    sys.path.insert(0, str(ROOT / "pipeline"))
    import global_maps as gm          # producer export functions: this is a publication-integrity check, not independent
    from PIL import Image
    d = Path(d)
    idx = json.loads((WEB / "index.json").read_text(encoding="utf-8"))
    done = np.load(d / "done.npy").astype(bool)
    res = dict(source_dir=str(d), pillow=Image.__version__ if hasattr(Image, "__version__") else None, layers={})
    import PIL
    res["pillow"] = PIL.__version__
    res["numpy"] = np.__version__
    lat = gm.grid_axes(PPD)[0]
    for L in idx["layers"]:
        name = L["id"]
        a = np.array(np.load(d / f"{name}.npy"), dtype=np.float32)
        a[~done] = np.nan
        r = {}
        # index statistics exactly as export() computes them
        fin = a[np.isfinite(a)]
        w = np.cos(np.radians(lat))[:, None] * np.isfinite(a)
        stats = {"min": float(fin.min()), "max": float(fin.max()),
                 "area_mean": float(np.nansum(np.nan_to_num(a) * w) / max(w.sum(), 1e-12))}
        r["index_stats"] = dict(recomputed=stats, published=L["stats"], exact=stats == L["stats"])
        # values PNG (8-bit DN = round(clip(v,0,1)*250), 255 = no data) after resampling to the overview size
        ov = gm.resample(a, *idx["overview_size"])
        q = np.where(np.isfinite(ov), np.round(np.clip(ov, 0, 1) * 250), 255).astype(np.uint8)
        pub = np.asarray(Image.open(WEB / L["values_png"]))
        dq = np.abs(q.astype(int) - pub.astype(int))
        r["values_png"] = dict(shape=list(pub.shape), identical_pixels=int((dq == 0).sum()), total_pixels=int(dq.size),
                               max_abs_dn=int(dq.max()), n_diff=int((dq != 0).sum()), nodata_dn255=int((pub == 255).sum()))
        # pre-quantisation residual: how far the published DN/250 is from the resampled float value
        r["values_png"]["max_abs_residual_pp"] = float(np.nanmax(np.abs(pub.astype(np.float64) / 250 - ov)) * 100)
        # overview JPEG: re-encode with the exporter's settings; compare bytes and decoded pixels
        buf = io.BytesIO()
        Image.fromarray(gm.colorize(ov, gm.COLORMAPS[name])).save(buf, format="JPEG", quality=88, optimize=True)
        pubb = (WEB / L["overview"]).read_bytes()
        dj = np.abs(np.asarray(Image.open(io.BytesIO(buf.getvalue()))).astype(int) - np.asarray(Image.open(WEB / L["overview"])).astype(int))
        r["overview_jpg"] = dict(bytes_identical=buf.getvalue() == pubb, decoded_max_abs=int(dj.max()), decoded_n_diff=int((dj != 0).sum()))
        # tiles
        tb = tdiff = tn = tmax = 0
        for lev in idx["tiles"]["levels"]:
            img = gm.colorize(gm.resample(a, lev["width"], lev["height"]), gm.COLORMAPS[name])
            for ty in range(lev["ny"]):
                for tx in range(lev["nx"]):
                    tile = img[ty * 512:(ty + 1) * 512, tx * 512:(tx + 1) * 512]
                    b = io.BytesIO()
                    Image.fromarray(tile).save(b, format="JPEG", quality=88, optimize=True)
                    pubt = WEB / "tiles" / name / str(lev["z"]) / f"{tx}_{ty}.jpg"
                    tn += 1
                    tb += b.getvalue() == pubt.read_bytes()
                    dd = np.abs(np.asarray(Image.open(io.BytesIO(b.getvalue()))).astype(int) - np.asarray(Image.open(pubt)).astype(int))
                    tdiff += int(dd.max() > 0)
                    tmax = max(tmax, int(dd.max()))
        r["tiles"] = dict(n=tn, bytes_identical=tb, decoded_differs=tdiff, decoded_max_abs=tmax)
        res["layers"][name] = r
        print(name, json.dumps(r))
    res["index_other"] = dict(rows_done=idx["rows_done"] == int(done.sum()) == NLAT,
                              ephem_signature_equal=idx["ephem"] == json.loads((d / "meta.json").read_text(encoding="utf-8"))["signature"]["ephem"],
                              params_equal=all(idx["params"][k] == json.loads((d / "meta.json").read_text(encoding="utf-8"))["signature"][k] for k in idx["params"]))
    res["published_files_sha256"] = {p.name: sha256(p) for p in sorted(WEB.glob("*.*"))}
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "integrity_check.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "package":
        package()
    elif cmd == "check":
        r = check(sys.argv[2])
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8", newline="\n")
        sys.exit(0 if r["all_ok"] else 1)
    elif cmd == "export":
        export_compare(sys.argv[2])
    else:
        sys.exit(__doc__)
