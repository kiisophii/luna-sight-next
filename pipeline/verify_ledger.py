"""Check docs/verification_ledger.md against the records it cites.

Check 1: each quoted fact appears in the cited commit message (git log), SI_USAGE line, VALIDATION row or file line.
Check 2: authorship of each product (git log author of the web/data path) and the counts in the "Count" table.
Run: python pipeline/verify_ledger.py   (needs the full git history of main; prints FAILURES: 0)
"""
import os, re, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.chdir(ROOT)
bad = 0


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8").stdout


def msg(h):
    return re.sub(r"\s+", " ", git("log", "-1", "--format=%B", h))


def fline(path, n):
    return open(path, encoding="utf-8").read().split("\n")[n - 1]


def vrow(n):
    return next(l for l in open("docs/VALIDATION.md", encoding="utf-8") if l.startswith(f"| {n} | "))


def ok(cond, label):
    global bad
    print(("OK  " if cond else "FAIL"), label)
    bad += not cond


# (where, text) -- where = commit hash | ("SI", line) | ("ROW", n) | (path, line)
FACTS = [
    ("170d483", "differs only in name and name_ko"),
    (("docs/site_coordinate_audit.md", 24), "maximum source-to-catalogue separation **0.000 m**"),
    (("docs/source_link_ai_report_2026-11-14.md", 9), "24개 사이트는 모두 페이지 숫자와 0.01° 이내 일치"),
    (("ROW", 1), "1,452 comparisons; sky-angle max 0.000016°"),
    (("ROW", 2), "max 0.000034°"),
    (("ROW", 3), "34,296 comparisons, max 0.000041°; 21,912 overlap rows bit-identical"),
    (("docs/card10_npz_independent_check.json", 30), "21912 even-hour rows 2026-01-01..2030-12-31 bit-identical: True"),
    ("a7a0978", "brute-force DEM horizon at 10 azimuths (max |diff| 0.0035 deg)"),
    ("a7a0978", "metrics recomputed from ephem.bin (exact match)"),
    ("a7a0978", "relay 15 m network LOS + tower Earth visibility at 20 hours (20/20)"),
    (("SI", 38), "horizon coords vs sites.json"),
    (("ROW", 6), "max difference 0.00053°"),
    (("ROW", 7), "max 0.012–0.219° (0.016° with 1 m steps), RMS ≤ 0.026°"),
    (("ROW", 13), "identical on 3 synthetic fixtures and all 33 real sites"),
    ("4a760de", "60-month hour-weighted means = metrics/<ID>.json to 6 dp"),
    ("7ddda73", "visible_hours = metrics fraction x 43,824 exactly"),
    ("2b05c2c", "reproduced all 33 metric files byte-for-byte"),
    (("ROW", 18), "max full-window difference 0.0011 pp; 30-epoch mismatches 0/0/0"),
    ("bab473b", "ARTEMIS_CABEUS_B direct 29.6367 % and 15 m single tower 85.743 % vs 85.727 %"),
    ("bab473b", "5 nodes in 3 regions (incl. Malapert (-2,-2)/(-2,-1) km headline pair), max diff 0.009 pp"),
    ("42d3a21", "relay 15 m link 342 h / no link 378 h"),
    (("ROW", 16), "2 of 175,296 station-hours differ, both within 0.0008° of 10°"),
    (("ROW", 15), "max 0.0012°"),
    (("ROW", 17), "differences ≤ 1 h"),
    (("ROW", 12), "5 points × Sun/Earth identical; projection vs GeoTIFF CRS 0.000 m"),
    (("SI", 34), "recompute validation.json stats from its 240 points"),
    (("SI", 38), "recomputed MAE/bias from validation.json"),
    ("067f7c8", "own Skyfield 2020-2038 2 h ephemeris (0.84488/0.53847 exact)"),
    ("067f7c8", "(0.87060/0.53748"),
    (("ROW", 11), "engine vs independent MAE 0.37 pp"),
    (("docs/card14_pgda_analysis.md", 59), "B4 and B5 equal the stored maps exactly"),
    ("1c950be", "3.8 km cell Sun 4.337 pp r 0.8232"),
    ("1c950be", "30/30 values equal the published *_values.png DN"),
    ("086a9ed", "max |own - stored| 1.3e-6 pp"),
    (("docs/card14_pgda_analysis.md", 12), "CPU vs CUDA is identical at all 400 cells"),
    ("f8d29a6", "centre node == metrics/<ID>.json for 33/33"),
    ("f8d29a6", "within 0.007 pp"),
    ("f8d29a6", "38.65 pp polar (IM1 46.06) vs 6.70 pp low/mid; sunlight IQR 17.16 vs 0.40 pp"),
    ("33a7342", "centre node == metrics/<ID>.json for 16/16"),
    ("33a7342", "within 0.146 pp"),
    ("ed25936", "centre node == metrics/<ID>.json for 17/17"),
    ("ed25936", "within 0.014 pp"),
    (("ROW", 20), "max fraction difference 0.021 pp"),
    ("812cc94", "reproduces all 33 x 730 x 4 series values to 4 decimals (max diff 0)"),
    (("ROW", 19), "own numpy geometry (no `core.js`), 3 sites"),
    ("7ddda73", "every visible interval identical (sun 226/179/63, Earth 68/68/1 intervals; 20 random edges each matched to the hour)"),
    (("docs/windows_verification.md", 3), "Twenty internal visible-window edges per site"),
    (("ROW", 21), "Δ ≤ 0.0002°, 0 min"),
    ("e97de2d", "Apollo 11 10.7035 deg (doc 10.70), Apollo 17 13.3501 deg (doc 13.35)"),
    (("docs/globe3d.md", 30), "projection + height-encoding self-check"),
    (("docs/card14.md", 102), "within **0.251 m**"),
    (("docs/card14.md", 103), "**462 shared tile edges identical**"),
    (("ROW", 14), "catalogue median RMS 0.975° → **0.085°**"),
    (("ROW", 14), "random median 0.652° → **0.027°**"),
    ("d300e04", "own PGDA horizon vs hterrain.js in Node"),
    # merges that list no check (the ledger says "none recorded")
]
for where, text in FACTS:
    if isinstance(where, str):
        src, label = msg(where), f"commit {where}"
    elif where[0] == "SI":
        src, label = fline("docs/SI_USAGE.md", where[1]), f"SI_USAGE.md:{where[1]}"
    elif where[0] == "ROW":
        src, label = vrow(where[1]), f"VALIDATION row {where[1]}"
    else:
        src, label = fline(*where), f"{where[0]}:{where[1]}"
    ok(text in src, f"{label}: {text[:70]}")

import json
hv = json.load(open("web/data/hterrain/validation.json", encoding="utf-8"))
ok(hv["impl_rms_deg_max"] == 5.33e-11 and hv["full_ldem64_rms_deg_max"] == 0.155, "hterrain/validation.json 5.33e-11 / 0.155")
cu = json.load(open("docs/coordinate_uncertainty_check.json", encoding="utf-8"))
mx = max(p["comparison"][m]["absolute_difference_pp"] for p in cu["points"] for m in ("sun_frac", "earth_frac", "both_frac"))
ok(len(cu["points"]) == 15 and mx == 0 and sum(c["center_exact_match"] for c in cu["catalogue_checks"]) == 16, "polar uncertainty verifier: 15 nodes, 0 pp, 16/16")

# merges where the ledger says no check is listed: message must not contain "check"/"recompute"
for h in ["34b14b9", "b7f499d", "3d7d86d", "5804e63", "b80ebae", "8e6c0d8", "36a30e6"]:
    m = msg(h).lower()
    ok(not re.search(r"recomput|independent|brute|own ", m), f"commit {h}: no recomputation listed")

# check 2: who computed each product (git authors of the web/data path)
AUTH = {
    "web/data/sites.json": {"hmkmc9095-cell"}, "web/data/ephem.bin": {"hmkmc9095-cell"},
    "web/data/gmaps": {"Soyun Jeong"}, "web/data/gmaps_ppd32": {"Soyun Jeong"},
    "web/data/date_slip": {"Dongju Kim"}, "web/data/monthly": {"kiisophii"},
    "web/data/windows": {"hmkmc9095-cell"}, "web/data/hindcast.json": {"Dongju Kim"},
    "web/data/hterrain/tiles": {"kiisophii"}, "web/data/hterrain/polar_s": {"kiisophii"},
    "web/data/local": {"Jiyong", "Dongju Kim"}, "web/data/uncertainty": {"Jiyong", "kiisophii"},
    "web/data/korea": {"kiisophii", "hmkmc9095-cell"}, "web/data/globe": {"kiisophii", "Soyun Jeong"},
}
for p, want in AUTH.items():
    got = set(git("log", "--no-merges", "--format=%an", "--", p).split("\n")) - {"", "kiisophii"} | ({"kiisophii"} & want)
    got = {a for a in got if a}
    ok(got == want, f"authors of {p}: {sorted(got)}")

# counts in the ledger table
L = open("docs/verification_ledger.md", encoding="utf-8").read()
rows = [l for l in L.split("\n") if re.match(r"^\| \d+ \| `", l)]
st = [l.rstrip(" |").split("|")[-1].strip() for l in rows]
n_oth = sum(s.startswith("Independently verified (other member") for s in st)
n_int = sum(s.startswith("Independently") and not s.startswith("Independently verified (other member") for s in st)
n_auth = sum(s.startswith("Author-verified only") for s in st)
print("  rows", len(rows), "integrator", n_int, "other member", n_oth, "author only", n_auth)
ok((len(rows), n_int, n_oth, n_auth) == (18, 10, 8, 0), "count table 18 = 10 + 8 + 0")
ok("| Independently verified by another team member | 8 |" in L and "| Author-verified only | 0 |" in L, "count table text matches the rows")
print("FAILURES:", bad)
sys.exit(1 if bad else 0)
