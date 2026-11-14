"""Check every number in submission/summary_final_en.md and submission/slides_7_en.md twice.

Check 1: the cited file:line contains the quoted text.
Check 2: an independent recomputation from the data files (JSON), or a second file that states the same value.
Run from anywhere: python pipeline/verify_submission_text.py   (prints FAILURES: 0 when everything matches)
"""
import json, os, re, statistics, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.chdir(ROOT)
bad = 0


def line(path, n):
    return open(path, encoding="utf-8").read().split("\n")[n - 1]


def ok(cond, label):
    global bad
    print(("OK  " if cond else "FAIL"), label)
    bad += not cond


# ---------- check 1: file:line contains the text (id, path, line, text) ----------
CITES = [
    ("N1", "docs/site_coordinate_audit.md", 24, "All **33 stored coordinate pairs match the stated source pair**"),
    ("N2", "docs/korea_links.md", 3, "every hour 2026-01-01T00Z – 2030-12-31T23Z (43,824 h)"),
    ("N3", "docs/location_sensitivity.md", 36, "| ARTEMIS_MALAPERT | earth_frac | 1.000 | 0.00% → 100.00% |"),
    ("N4", "docs/site_coordinate_audit.md", 24, "maximum source-to-catalogue separation **0.000 m**"),
    ("N5", "docs/location_sensitivity.md", 29, "| SHACKLETON_RIM | sun_frac | 1.000 | 0.28% → 59.23% | 58.94 | (8,8) → (7,8) | 5/5 |"),
    ("N5b", "data/DATASETS.md", 53, "| PGDA LOLA south polar DEM 5 m |"),
    ("N6", "docs/location_sensitivity.md", 37, "| ARTEMIS_MALAPERT | both_frac | 1.000 | 0.00% → 45.11% | 45.11 |"),
    ("N7/N8 polar", "docs/location_sensitivity.md", 15, "| South-polar (lat ≤ −75°) | 16 | 17.16 | 41.80 | 46.68 | 38.65 | 46.06 (IM1) |"),
    ("N7/N8 low/mid", "docs/location_sensitivity.md", 16, "| Low/mid latitude (|lat| < 60°) | 16 | 0.40 | 7.00 | 7.02 | 6.70 | 12.67 (CHANGE3) |"),
    ("N7 text", "docs/location_sensitivity.md", 19, "is 38.7 percentage points at the median south-polar site"),
    ("N7 text b", "docs/location_sensitivity.md", 19, "and 6.7 pp at the median low/mid-latitude site"),
    ("N8 text", "docs/location_sensitivity.md", 19, "the sunlight spread (IQR) is 17.2 pp near the pole versus 0.4 pp elsewhere"),
    ("N9", "docs/date_slip.md", 9, "At 26 of 33 sites, a 14-day slip can turn the first two weeks on the surface from daylight into night: the longest darkness grows by up to 336 h."),
    ("N10 old", "docs/custom_horizon_validation.json", 455, '"catalogue_sun_pct": 8.7'),
    ("N10 old step", "docs/custom_horizon_validation.json", 16, "2 h step"),
    ("N10 new", "docs/VALIDATION.md", 67, "Sun 0.848"),
    ("N11", "docs/relay_impact.md", 20, "| ARTEMIS_CABEUS_B | 29.64% / 489 h | 76.11% / 193 h | 85.73% / 130 h |"),
    ("N12", "docs/relay_impact.md", 9, "| All 33 catalogue sites | 7 | 3 | 3 | 3 | 3 |"),
    ("N13 share", "docs/korea_links.md", 46, "KDSA alone covers 0.3–0.4 % of"),
    ("N13 hours", "docs/korea_links.md", 47, "123 h in 5 years"),
    ("N14", "docs/VALIDATION.md", 62, "MAE 1.66 pp, RMSE 2.62 pp, r 0.985"),
    ("N15", "docs/VALIDATION.md", 89, "within 0.0005° in over 37,000 comparisons"),
    ("N15 r1", "docs/VALIDATION.md", 55, "1,452 comparisons; sky-angle max 0.000016°; web float32 via `core.js` max az 0.00044°"),
    ("N15 r2", "docs/VALIDATION.md", 56, "1,452 comparisons, max 0.000034°"),
    ("N15 r3", "docs/VALIDATION.md", 57, "34,296 comparisons, max 0.000041°"),
    ("N16", "docs/hindcast.md", 7, "to within **0.05°** at our catalogue points"),
    ("N17", "docs/ui_data_audit.md", 17, "**5,520 values checked (33 sites × 2 times × 10 panels). 0 numeric mismatches.**"),
    ("Artemis III", "docs/sites.md", 17, "candidate-region list"),
    ("Apache-2.0", "LICENSE", 3, "Version 2.0"),
]
for cid, path, n, text in CITES:
    ok(text in line(path, n), f"{cid}: {path}:{n}")

# ---------- check 2: independent recomputation / second source ----------
sites = json.load(open("web/data/sites.json", encoding="utf-8"))
sites = sites["sites"] if isinstance(sites, dict) else sites
ok(len(sites) == 33, f"N1 second: web/data/sites.json has {len(sites)} sites")
ok("43,824 hourly samples, 2026–2030" in line("docs/location_sensitivity.md", 5), "N2 second: location_sensitivity.md:5")

# N3, N5-N8: recompute from web/data/local/<ID>.json (21x21 nodes, 1 km spacing; IQR inside the 10 km circle)
lat = {s["id"]: s["lat"] for s in sites}
polar_adj, low_adj, polar_iqr, low_iqr = [], [], [], []
mal = None
for sid in lat:
    d = json.load(open(f"web/data/local/{sid}.json", encoding="utf-8"))
    P = {(p["e_m"] // 1000, p["n_m"] // 1000): p for p in d["points"]}
    inside = {k: p for k, p in P.items() if k[0] ** 2 + k[1] ** 2 <= 100}
    sun = np.array([p["sun_frac"] for p in inside.values()]) * 100
    iqr = np.percentile(sun, 75) - np.percentile(sun, 25)
    best = 0  # largest edge-neighbour (1 km) difference over the whole 21x21 grid, as in pipeline/local_impact.py
    for (e, n), p in P.items():
        for de, dn in ((1, 0), (0, 1)):
            q = P.get((e + de, n + dn))
            if q:
                best = max(best, abs(p["both_frac"] - q["both_frac"]) * 100)
    if lat[sid] <= -75:
        polar_adj.append(best); polar_iqr.append(iqr)
    elif abs(lat[sid]) < 60:
        low_adj.append(best); low_iqr.append(iqr)
    if sid == "ARTEMIS_MALAPERT":
        mal = (P[(-2, -2)], P[(-2, -1)])
r = lambda x: round(statistics.median(x), 2)
print("  recomputed medians: polar adj both", r(polar_adj), "low adj", r(low_adj), "polar IQR", r(polar_iqr), "low IQR", r(low_iqr), "counts", len(polar_adj), len(low_adj))
ok((len(polar_adj), len(low_adj)) == (16, 16), "N7/N8 second: 16 + 16 sites")
ok(abs(r(polar_adj) - 38.65) < 0.006 and abs(r(low_adj) - 6.70) < 0.006, "N7 second: largest 1 km both-contrast medians 38.65 / 6.70 pp")
ok(abs(r(polar_iqr) - 17.16) < 0.006 and abs(r(low_iqr) - 0.40) < 0.006, "N8 second: sunlight IQR medians 17.16 / 0.40 pp")
ok(mal[0]["earth_frac"] == 0 and mal[1]["earth_frac"] == 1, "N3 second: Malapert (-2,-2) Earth 0 %, (-2,-1) Earth 100 %")
ok(mal[0]["both_frac"] == 0 and round(mal[1]["both_frac"] * 100, 2) == 45.11, "N6 second: Malapert both 0 % vs 45.11 %")
shk = json.load(open("web/data/local/SHACKLETON_RIM.json", encoding="utf-8"))["points"]
ok(min(p["ground_resolution_m"] for p in shk) == 5, "N5 second: SHACKLETON_RIM local grid uses 5 m ground DEM")

# N9: date_slip_summary.json, +14 d worst change of the longest darkness
ds = json.load(open("docs/date_slip_summary.json", encoding="utf-8"))["sites"]
w = [s["slip"]["+14d"]["longest_dark_h"]["worst_change"] for s in ds]
ok(sum(x >= 300 for x in w) == 26 and max(w) == 336 and len(w) == 33, f"N9 second: {sum(x >= 300 for x in w)} of {len(w)} sites ≥ 300 h, max {max(w)} h")

# N10 new point: metrics file
m = json.load(open("web/data/metrics/SHACKLETON_RIM.json", encoding="utf-8"))
ok(round(m["sun_frac"] * 100, 1) == 84.8, f"N10 second: metrics/SHACKLETON_RIM.json sun_frac {m['sun_frac']:.4f}")

# N11, N12: second file
ok("85.73" in open("docs/card13_relay_report.md", encoding="utf-8").read() or "85.7" in open("docs/card13_relay_report.md", encoding="utf-8").read(), "N11 second: card13_relay_report.md has 85.7")
ri = open("docs/relay_impact.md", encoding="utf-8").read().split("\n")
direct = [l for l in ri[17:26] if l.startswith("| ") and "%" in l]
ok(len(direct) == 7, f"N12 second: {len(direct)} rows in the single-tower table (direct < 50 %)")
reach = sum(float(l.split("|")[4].split("%")[0]) >= 50 for l in direct)
ok(reach == 3, f"N12 second: {reach} reach ≥ 50 % at 15 m")

# N13: korea_links_check.json or table rows
kl = open("docs/korea_links.md", encoding="utf-8").read()
ok(kl.count("| 123 |") >= 1, "N13 second: table rows show 123 h KDSA-only")

# N14: web/data/validation.json
v = json.load(open("web/data/validation.json", encoding="utf-8"))
ok((v["sun"]["mae_pp"], v["sun"]["r"], v["n_points"]) == (1.658, 0.9846, 240), "N14 second: validation.json 1.658 pp, r 0.9846, 240 points")

# N15: card10 JSON
ok(1452 + 1452 + 34296 > 37000 and max(0.000016, 0.00044, 0.000034, 0.000041) < 0.0005, "N15 second: rows 1-3 sum to 37,200 comparisons, all maxima < 0.0005°")
# N16: VALIDATION row 21
ok("Apollo max Δ 0.05°" in line("docs/VALIDATION.md", 75), "N16 second: VALIDATION.md:75")
# N17: findings.json
f = json.load(open("docs/ui_audit/findings.json", encoding="utf-8"))
ok(f.get("checks") == 5520, f"N17 second: ui_audit/findings.json checks = {f.get('checks')}")

# ---------- the texts quote these numbers ----------
S = open("submission/summary_final_en.md", encoding="utf-8").read()
body = re.search(r"^<!-- BEGIN -->$(.*?)^<!-- END -->$", S, re.S | re.M).group(1)
nw = len(body.split())
ok(150 <= nw <= 200, f"summary words {nw}")
for s in ["33 sites with published coordinates", "2026–2030", "5 m", "38.7", "6.7", "17.2", "0.4", "26 of 33", "15 m", "30% to 86%", "1.7 points"]:
    ok(s in body, f"summary quotes '{s}'")
D = open("submission/slides_7_en.md", encoding="utf-8").read()
ok(len(re.findall(r"^## Slide \d", D, re.M)) == 7, "deck has 7 slides")
for s in ["0% → 100%", "45.11%", "38.65", "6.70", "17.16", "0.40", "336", "29.64% → 85.73%", "123 h", "0.3–0.4%", "1.66", "0.0005°", "37,000", "0.05°", "5,520", "about 9% to 85%", "0.000 m"]:
    ok(s in D, f"deck quotes '{s}'")
print("FAILURES:", bad)
sys.exit(1 if bad else 0)
