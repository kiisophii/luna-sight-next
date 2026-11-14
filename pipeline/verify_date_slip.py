"""Card 19 verification: recompute random (site, landing day) cells of web/data/date_slip/<ID>.json
with an independent loop over web/data/ephem.bin + web/data/horizon/<ID>.json (no core.js, no
pipeline/date_slip.mjs), and compare to 4 decimals.

    python pipeline/verify_date_slip.py [--n 10] [--seed 19]

Independent implementation of the contract definitions (sections 0, 3, 6): topocentric Sun/Earth
direction from the Moon-centre vectors minus the observer at R + h0 + 2 m; mask linearly interpolated;
sunlit = visible solar-disc fraction (radius 0.2666 deg, flat mask line) >= 0.5; Earth = centre above
the mask; first 14 x 24 hourly samples from 00:00 UTC of the landing day; longest consecutive
not-sunlit run.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
R_KM = 1737.4
SUN_R = 0.2666


def load_ephem():
    raw = (DATA / "ephem.bin").read_bytes()
    import struct
    return [struct.unpack_from("<6f", raw, 24 * i) for i in range(len(raw) // 24)]


def mask_at(mask, step, az):
    x = (az % 360.0) / step
    k = int(math.floor(x)) % len(mask)
    f = x - math.floor(x)
    return mask[k] + (mask[(k + 1) % len(mask)] - mask[k]) * f


def cell(eph, site, hz, day, n_days=14):
    la, lo = math.radians(site["lat"]), math.radians(site["lon"])
    up = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
    east = (-math.sin(lo), math.cos(lo), 0.0)
    north = (-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la))
    r = R_KM + (hz["h0_m"] + 2.0) / 1000.0
    obs = tuple(r * u for u in up)
    ns = ne = nb = run = longest = 0
    n = n_days * 24
    for i in range(day * 24, day * 24 + n):
        row = eph[i]
        vis = []
        for c in (0, 3):
            v = (row[c] - obs[0], row[c + 1] - obs[1], row[c + 2] - obs[2])
            e = sum(a * b for a, b in zip(v, east)); nn = sum(a * b for a, b in zip(v, north)); u = sum(a * b for a, b in zip(v, up))
            az = math.degrees(math.atan2(e, nn)) % 360.0
            el = math.degrees(math.atan2(u, math.hypot(e, nn)))
            vis.append(el - mask_at(hz["mask"], hz["az_step_deg"], az))
        y = -vis[0] / SUN_R                      # mask line relative to disc centre, in radii
        frac = 1.0 if y <= -1 else 0.0 if y >= 1 else (math.acos(y) - y * math.sqrt(1 - y * y)) / math.pi
        s, g = frac >= 0.5, vis[1] > 0
        ns += s; ne += g; nb += s and g
        run = 0 if s else run + 1
        longest = max(longest, run)
    return {"sun_frac": ns / n, "earth_frac": ne / n, "both_frac": nb / n, "longest_dark_h": longest}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=19)
    a = ap.parse_args(argv)
    eph = load_ephem()
    sites = {s["id"]: s for s in json.loads((DATA / "sites.json").read_text(encoding="utf-8"))}
    files = sorted((DATA / "date_slip").glob("*.json"))
    rng = random.Random(a.seed)
    rows, ok = [], True
    for _ in range(a.n):
        f = rng.choice(files)
        rec = json.loads(f.read_text(encoding="utf-8"))
        k = rng.randrange(rec["n_landings"])
        hz = json.loads((DATA / "horizon" / f"{rec['id']}.json").read_text(encoding="utf-8"))
        ours = cell(eph, sites[rec["id"]], hz, k, rec["days_after_landing"])
        stored = {m: rec["series"][m][k] for m in ours}
        diff = {m: abs(round(ours[m], 4) - stored[m]) for m in ours}
        match = all(d < 1e-9 for d in diff.values())
        ok &= match
        rows.append({"id": rec["id"], "landing_index": k, "ours": {m: round(v, 4) for m, v in ours.items()},
                     "stored": stored, "match_4dp": match})
        print(f"{rec['id']:26s} day {k:3d}: ours {[round(v, 4) for v in ours.values()]} stored {list(stored.values())} "
              f"{'MATCH' if match else 'DIFF'}", flush=True)
    out = ROOT / "docs" / "date_slip_check.json"
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    prev["independent_cells"] = {"seed": a.seed, "n": a.n, "all_match_4dp": ok, "cells": rows}
    out.write_text(json.dumps(prev, indent=1), encoding="utf-8")
    print("ALL MATCH" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
