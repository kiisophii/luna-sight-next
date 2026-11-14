"""Compute horizon masks for every site in web/data/sites.json -> web/data/horizon/<ID>.json.

    python pipeline/run_horizons.py                     # all sites, one process
    python pipeline/run_horizons.py --site APOLLO17     # one site (repeatable)
    python pipeline/run_horizons.py --all-cores         # batch run on every CPU core
    python pipeline/run_horizons.py --force             # recompute even if up to date

Resume: each site is written atomically as soon as it is done. A site whose existing file
was made with the same engine parameters and the same DEM chain is skipped, so an
interrupted batch just continues when you rerun the same command.

DEM caches (git-ignored, made by the phase-1 cards):
  data/raw/polar/<res>/<ID>.npz       card 2, PGDA 5/10/20/60/80/240 m, south of -80 deg
  data/raw/sldem/<ID>.npz             card 3, SLDEM2015 59 m window (|lat| < 60)
  data/raw/global/ldem_64_float.img   card 3, LOLA LDEM_64 (474 m)   + .lbl
  data/raw/global/ldem_16_float.img   card 3, LOLA LDEM_16 (1895 m)  + .lbl
Sites whose required DEMs are missing are skipped with a message saying what to fetch.
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import horizon as hz  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POLAR_RES = [5, 10, 20, 60, 80, 240]
POLAR_LAT = -80.0          # card 2 covers lat <= -80
SLDEM_LAT = 60.0           # SLDEM2015 covers |lat| < 60


class MissingDEM(Exception):
    pass


def build_chain(site, raw, max_km):
    """[(sampler, max_km)] finest first, or raise MissingDEM with what to fetch."""
    sid, lat = site["id"], site["lat"]
    chain, missing = [], []
    if lat <= POLAR_LAT:
        for res in POLAR_RES:
            p = raw / "polar" / str(res) / f"{sid}.npz"
            if p.exists():
                s = hz.PolarStereoSampler(p)
                chain.append((s, min(s.radius_km or max_km, max_km)))
        if not chain:
            missing.append(f"data/raw/polar/<res>/{sid}.npz (card 2: fetch_polar.py --site {sid})")
    elif abs(lat) < SLDEM_LAT:
        p = raw / "sldem" / f"{sid}.npz"
        if p.exists():
            s = hz.LatLonWindowSampler(p)
            chain.append((s, min(float(s.radius_km or max_km), max_km)))
        else:
            missing.append(f"data/raw/sldem/{sid}.npz (card 3: fetch_global.py --site {sid} --skip-global)")
    glob = {}
    for ppd in (64, 16):
        img = raw / "global" / f"ldem_{ppd}_float.img"
        if img.exists() and img.with_suffix(".lbl").exists():
            glob[ppd] = hz.GlobalCylSampler(img)
    if lat > POLAR_LAT and abs(lat) >= SLDEM_LAT and 64 not in glob:
        missing.append("data/raw/global/ldem_64_float.img (+.lbl) - near field for |lat| >= 60 "
                       "outside the south-polar caches (card 3: fetch_global.py)")
    for ppd in (64, 16):
        if ppd in glob:
            chain.append((glob[ppd], max_km))
    reach = max((m for _, m in chain), default=0.0)
    if reach < max_km:
        missing.append(f"a DEM reaching {max_km:g} km (have {reach:g} km): "
                       "data/raw/global/ldem_16_float.img or ldem_64_float.img (card 3)")
    if missing:
        raise MissingDEM("; ".join(missing))
    return chain


def chain_signature(chain):
    out = []
    for s, m in chain:
        p = getattr(s, "path", None) or getattr(getattr(s, "data", None), "filename", None)
        st = Path(p).stat() if p else None
        out.append([s.name, round(m, 3), st.st_size if st else None, int(st.st_mtime) if st else None])
    return out


def up_to_date(path, site, params, sig):
    try:
        h = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    e = h.get("engine", {})
    return (not h.get("mock") and h.get("lat") == site["lat"] and h.get("lon") == site["lon"]
            and all(e.get(k) == v for k, v in params.items()) and e.get("chain") == sig)


def run_site(site, raw, out_dir, params, force):
    t0 = time.time()
    try:
        chain = build_chain(site, raw, params["max_km"])
    except MissingDEM as e:
        return site["id"], "SKIP", f"missing DEM: {e}"
    sig = chain_signature(chain)
    out = out_dir / f"{site['id']}.json"
    if not force and up_to_date(out, site, params, sig):
        return site["id"], "OK", "up to date (resume)"
    res = hz.compute_horizon(site["lat"], site["lon"], chain, min_km=params["min_km"],
                             max_km=params["max_km"], n_steps=params["n_steps"])
    rec = hz.horizon_record(site, res)
    rec["engine"]["chain"] = sig
    hz.write_json_atomic(out, rec)
    m = res["mask"]
    miss = res["n_missing"] / max(res["n_samples"], 1)
    warn = f"  WARNING {miss:.2%} samples had no DEM" if res["n_missing"] else ""
    src = ", ".join(f"{d['name']}<= {d['to_km']:g} km" for d in rec["dem_sources"])
    return site["id"], "DONE", (f"h0 {rec['h0_m']:.1f} m, mask {m.min():.2f}..{m.max():.2f} deg, "
                                f"[{src}], {time.time() - t0:.1f} s{warn}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sites", default=str(ROOT / "web" / "data" / "sites.json"))
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw"), help="DEM cache root")
    ap.add_argument("--out", default=str(ROOT / "web" / "data" / "horizon"))
    ap.add_argument("--site", action="append", help="only this site id (repeatable)")
    ap.add_argument("--min-km", type=float, default=0.2)
    ap.add_argument("--max-km", type=float, default=300.0)
    ap.add_argument("--n-steps", type=int, default=4000, help="geometric distance steps")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--all-cores", action="store_true", help="use every CPU core (batch runs)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    sites = json.loads(Path(a.sites).read_text(encoding="utf-8"))
    if a.site:
        unknown = set(a.site) - {s["id"] for s in sites}
        if unknown:
            ap.error(f"unknown site id(s): {sorted(unknown)}")
        sites = [s for s in sites if s["id"] in a.site]
    params = {"min_km": a.min_km, "max_km": a.max_km, "n_steps": a.n_steps,
              "engine_version": hz.ENGINE_VERSION}
    raw, out = Path(a.raw), Path(a.out)
    workers = os.cpu_count() if a.all_cores else max(1, a.workers)
    print(f"{len(sites)} sites, DEMs from {raw}, output {out}, {workers} worker(s)", flush=True)
    results = []
    if workers == 1:
        for s in sites:
            results.append(run_site(s, raw, out, params, a.force))
            print(" ".join(results[-1]), flush=True)
    else:
        with cf.ProcessPoolExecutor(workers) as ex:
            futs = [ex.submit(run_site, s, raw, out, params, a.force) for s in sites]
            for f in cf.as_completed(futs):
                results.append(f.result())
                print(" ".join(results[-1]), flush=True)
    n = {k: sum(r[1] == k for r in results) for k in ("DONE", "OK", "SKIP")}
    print(f"\ncomputed {n['DONE']}, already up to date {n['OK']}, skipped (missing DEM) {n['SKIP']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
