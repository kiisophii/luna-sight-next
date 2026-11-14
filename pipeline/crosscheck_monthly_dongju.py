"""Cross-check of web/data/monthly/ (seasons, producer Sua Kim) by Dongju Kim.

Own code, not pipeline/seasons.mjs, web/js/core.js or pipeline/verify_seasons.py: a plain-Python
hourly loop over web/data/ephem.bin + web/data/horizon/<ID>.json using the contract definitions
(sunlit = solar disc (radius 0.2666 deg) >= 50 % above the linearly interpolated mask line,
seen from R + h0 + 2 m; Earth visible = Earth centre above the mask; longest dark = longest
not-sunlit run inside the calendar month). Random sample: 3 sites x 3 calendar months.

    python pipeline/crosscheck_monthly_dongju.py [--seed 20261115]
Writes docs/crosscheck_monthly_dongju.json and prints expected (file) vs got (own loop).
"""
import argparse
import calendar
import json
import math
import random
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"
R_KM = 1737.4
SUN_R = 0.2666


def load_ephem():
    raw = (DATA / "ephem.bin").read_bytes()
    return [struct.unpack_from("<6f", raw, 24 * i) for i in range(len(raw) // 24)]


def mask_at(mask, step, az):
    x = (az % 360.0) / step
    k = int(math.floor(x)) % len(mask)
    f = x - math.floor(x)
    return mask[k] + (mask[(k + 1) % len(mask)] - mask[k]) * f


def month_metrics(eph, site, hz, i0, i1):
    la, lo = math.radians(site["lat"]), math.radians(site["lon"])
    up = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
    east = (-math.sin(lo), math.cos(lo), 0.0)
    north = (-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la))
    r = R_KM + (hz["h0_m"] + 2.0) / 1000.0
    obs = tuple(r * u for u in up)
    ns = ne = nb = run = longest = 0
    for i in range(i0, i1):
        row = eph[i]
        margin = []
        for c in (0, 3):                      # 0..2 Sun, 3..5 Earth (Moon-centred, MOON_ME, km)
            v = (row[c] - obs[0], row[c + 1] - obs[1], row[c + 2] - obs[2])
            e = sum(a * b for a, b in zip(v, east))
            n = sum(a * b for a, b in zip(v, north))
            u = sum(a * b for a, b in zip(v, up))
            az = math.degrees(math.atan2(e, n)) % 360.0
            el = math.degrees(math.atan2(u, math.hypot(e, n)))
            margin.append(el - mask_at(hz["mask"], hz["az_step_deg"], az))
        y = -margin[0] / SUN_R
        frac = 1.0 if y <= -1 else 0.0 if y >= 1 else (math.acos(y) - y * math.sqrt(1 - y * y)) / math.pi
        s, g = frac >= 0.5, margin[1] > 0
        ns += s; ne += g; nb += s and g
        run = 0 if s else run + 1
        longest = max(longest, run)
    return {"hours": i1 - i0, "sun_h": ns, "earth_h": ne, "both_h": nb, "longest_dark_h": longest}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261115)
    a = ap.parse_args(argv)
    sites = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))
    sites = sites["sites"] if isinstance(sites, dict) else sites
    rng = random.Random(a.seed)
    pick = rng.sample(sites, 3)
    eph = load_ephem()
    rows, worst = [], {"hours": 0, "sun_h": 0, "earth_h": 0, "both_h": 0, "longest_dark_h": 0, "frac": 0.0}
    for s in pick:
        mon = json.loads((DATA / "monthly" / f"{s['id']}.json").read_text(encoding="utf-8"))
        hz = json.loads((DATA / "horizon" / f"{s['id']}.json").read_text(encoding="utf-8"))
        for m in sorted(rng.sample(range(60), 3)):
            y, mo = 2026 + m // 12, m % 12 + 1
            # hour index of the month start, counted from 2026-01-01T00Z
            i0 = sum(calendar.monthrange(2026 + k // 12, k % 12 + 1)[1] for k in range(m)) * 24
            i1 = i0 + calendar.monthrange(y, mo)[1] * 24
            got = month_metrics(eph, s, hz, i0, i1)
            exp = {k: mon["series"][k][m] for k in ("hours", "sun_h", "earth_h", "both_h", "longest_dark_h")}
            fr = {k: (mon["series"][k + "_frac"][m], round(got[k + "_h"] / got["hours"], 4)) for k in ("sun", "earth", "both")}
            diff = {k: got[k] - exp[k] for k in exp}
            for k in diff:
                worst[k] = max(worst[k], abs(diff[k]))
            worst["frac"] = max(worst["frac"], max(abs(e - g) for e, g in fr.values()))
            rows.append({"id": s["id"], "month": f"{y}-{mo:02d}", "expected": exp, "got": got, "diff": diff,
                         "frac_expected_vs_got": fr})
            print(f"{s['id']:<24} {y}-{mo:02d} expected {exp} got {got} diff {diff}")
    ok = all(v == 0 for k, v in worst.items() if k != "frac") and worst["frac"] == 0
    out = {"product": "web/data/monthly/", "producer": "Sua Kim", "checker": "Dongju Kim",
           "method": "own plain-Python hourly loop over ephem.bin + horizon files (no core.js / seasons.mjs / verify_seasons.py)",
           "seed": a.seed, "sample": [f"{r['id']} {r['month']}" for r in rows], "rows": rows,
           "max_abs_diff": worst, "criterion": "hour counts and longest dark identical; fractions equal to 4 dp",
           "passed": ok}
    (ROOT / "docs" / "crosscheck_monthly_dongju.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("max abs diff", worst, "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
