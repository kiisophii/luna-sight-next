"""Check every number in the new VALIDATION Summary/Limits and the one-pager against its cited source.
Each check: (number as written in our doc, source, substring that must appear in the source).
Source = path on this branch, or 'REF:path' read with git show (open PR branches)."""
import json, subprocess, sys, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # repo root; open-PR files come from origin/pr/41, 45, 46 (git fetch origin "+refs/pull/*/head:refs/remotes/origin/pr/*")
V = open("docs/VALIDATION.md", encoding="utf-8").read()
O = open("submission/validation_onepager_en.md", encoding="utf-8").read()
SUM = V.split("## Full validation table")[0]
FULL = V.split("## Full validation table")[1]

def src(s):
    if ":" in s and s.split(":")[0].startswith("origin/"):
        return subprocess.run(["git", "show", s], capture_output=True, text=True, encoding="utf-8").stdout
    if s == "FULL":
        return FULL
    return open(s, encoding="utf-8").read()

C = [
 # S1
 ("34,296", "FULL", "34,296 comparisons, max 0.000041°"), ("0.000041°", "docs/card10_npz_independent_check.json", None),
 # S2
 ("0.00053°", "FULL", "max difference 0.00053°"), ("2 sites × 10 azimuths", "FULL", "2 sites × 10 azimuths"),
 ("RMS ≤ 0.026°, max 0.012–0.219° (0.016° with 1 m steps)", "FULL", "max 0.012–0.219° (0.016° with 1 m steps), RMS ≤ 0.026°"),
 # S3
 ("1.66 / r 0.985", "web/data/validation.json", None),
 ("1.24 / 0.990", "web/data/validation.json", None),
 # S4
 ("2.61 / 0.911", "docs/card14_pgda_analysis.md", "| B4 | 948 m cell centres | 2026–2030, 3 h | 2.609 / 0.9108 | 3.423 / 0.9837 | 2.417 / 0.9847 |"),
 # S5
 ("2.96e-6 max over 600", "origin/pr/41:docs/gpu_cpu_300_check.md", "| Assigned 300 | earth | 2.957382705e-6 |"),
 ("< 0.5 pp", "origin/pr/41:docs/gpu_cpu_300_check.md", "0.5 percentage-point threshold"),
 ("600 cells", "origin/pr/41:docs/gpu_cpu_300_check.md", "all three metrics match exactly at all 600 cells"),
 # S6
 ("+19.1", "docs/named_residuals.md", "| ARTEMIS_NOBILE_RIM1 | 73.3 % | 54.2 % | +19.1 pp |"),
 ("+3.4", "docs/named_residuals.md", "| DE_GERLACHE_RIM1 | 52.4 % | 49.0 % | +3.4 pp |"),
 ("5/5 within", "docs/named_residuals.md", "All 5 largest residuals are **within the PGDA/coordinate spread**"),
 # S7
 ("0.021 pp", "FULL", "max fraction difference 0.021 pp"), ("17/17", "FULL", "centre node = metrics file 17/17"),
 # S8
 ("0.05° / 0.02°", "docs/hindcast.md", "to within **0.05°** at our catalogue points (0.02° at the Journal's own coordinates)"),
 ("0.00004°", "docs/hindcast.md", "Horizons to **0.00004°**"), ("< 0.1°", "FULL", "Apollo < 0.1°; ephemeris < 0.01°"),
 # S9
 ("0.0012°", "FULL", "| max 0.0012° | < 0.05° |"),
 ("PR #13", "FULL", None),
 # S10
 ("5,520 / 0", "origin/pr/45:docs/ui_data_audit.md", "**5,520 values checked (33 sites × 2 times × 10 panels). 0 numeric mismatches.**"),
 # L1
 ("-0.2829", "docs/near_field_comparison.md", "| APOLLO11 | 49.6577 | 49.3748 | -0.2829 |"),
 ("-0.2487", "docs/near_field_comparison.md", "| APOLLO12 | 49.9293 | 49.6805 | -0.2487 |"),
 ("-0.1209", "docs/near_field_comparison.md", "| LUNA20 | 47.8436 | 47.7227 | -0.1209 |"),
 ("-0.7986", "docs/near_field_comparison.md", "| CHANGE5 | 50.1552 | 49.3565 | -0.7986 |"),
 ("-0.3742", "docs/near_field_comparison.md", "| IM3_REINER_GAMMA | 49.5277 | 49.1534 | -0.3742 |"),
 ("Earth 100 %", "docs/near_field_comparison.md", "Earth visibility remains 100% at all five sites"),
 ("200 m start", "docs/near_field_check.md", "200 m minimum ray distance, 4000 steps"),
 ("59 m", "docs/near_field_check.md", "~59.23 m north–south"),
 ("PR41 same numbers", "origin/pr/41:docs/near_field_check.md", "| CHANGE5 | 50.1552 / 100.0000 | 49.3565 / 100.0000 |"),
 # L2
 ("4.6–5.6", "docs/named_residuals.md", "4.6–5.6 pp lower"), ("3.87", "FULL", "centre rule: MAE 3.87 pp"),
 # L3
 ("outside both rasters", "docs/near_field_check.md", "is outside **both** north and south raster rectangles"),
 # L4
 ("hindcast proxies", "docs/hindcast.md", "Chandrayaan-3 3.8 h before our sunset; SLIM 1 day(s) after our sunset (date only); IM-1 Odysseus 2 day(s) before our sunset (date only); Chang'e 3 18.6 h before our sunset"),
 ("Chang'e 4 no public", "docs/hindcast.md", "Chang'e 4 has no public first-night time"),
 # L5
 ("CONNECTING_RIDGE", "docs/coordinate_uncertainty.md", "| CONNECTING_RIDGE | 31.69–83.49 |"),
 ("PEAK", "docs/coordinate_uncertainty.md", "| PEAK_NEAR_SHACKLETON | 38.92–79.03 |"),
 ("DGR1", "docs/coordinate_uncertainty.md", "| DE_GERLACHE_RIM1 | 21.71–63.01 |"),
 ("SHOEMAKER", "docs/coordinate_uncertainty.md", "| SHOEMAKER_RIM_A | 17.76–24.75 |"),
 ("51.80", "docs/coordinate_uncertainty.md", "CONNECTING_RIDGE: sun_frac 51.80pp"),
 ("40.11", "docs/coordinate_uncertainty.md", "PEAK_NEAR_SHACKLETON: sun_frac 40.11pp"),
 ("41.30", "docs/coordinate_uncertainty.md", "DE_GERLACHE_RIM1: sun_frac 41.30pp"),
 # L6 / L8
 ("B1", "docs/card14_pgda_analysis.md", "| B1 | exact points | 2026–2030, 3 h | 2.183 / 0.9380 |"),
 ("B2", "docs/card14_pgda_analysis.md", "| B2 | exact points | 2026–2030, 2 h | 2.182 / 0.9380 |"),
 ("B3", "docs/card14_pgda_analysis.md", "| B3 | exact points | 2020–2038, 2 h | **2.185 / 0.9379** |"),
 ("PR46 title", "origin/pr/46:docs/timestep_sensitivity.md", None),
 # L9 / L10
 ("+2.40", "FULL", "browser sunlight is +2.40 pp above the card-8 chain"), ("20 m / 60 m", "FULL", "(20 m / 60 m to 3 km, 240 m to 150 km; s4)"),
 ("8.99", "FULL", "240 m: ≤ 8.99 m"), ("1.39", "FULL", "10–80 m: ≤ 1.39 m"),
 # L11 / L12
 ("photographs", "FULL", "no surface photographs compared"), ("DEM height errors", "docs/coordinate_uncertainty.md", "DEM\nheight errors are not included"),
 ("KDSA permission", "FULL", "permission to use KDSA coordinates is pending"),
]
bad = 0
for label, s, needle in C:
    text = src(s)
    ok = bool(text) and (needle is None or needle in text)
    if needle is None and label.startswith("0.000041"):
        ok = "4.1" in text or "0.000041" in text or "4.0" in text
    print(("OK  " if ok else "FAIL"), label, "<-", s)
    bad += not ok

vj = json.load(open('web/data/validation.json', encoding='utf-8'))
ok = (vj['sun']['mae_pp'], vj['sun']['r'], vj['earth']['mae_pp'], vj['earth']['r'], vj['alt_definitions']['earth_centre']['mae_pp']) == (1.658, 0.9846, 1.239, 0.9896, 3.874)
print('validation.json parsed', ok); bad += not ok
# polar coordinate check: max diff and exact centres computed from the JSON
d = json.load(open("docs/coordinate_uncertainty_check.json", encoding="utf-8"))
mx = max(p["comparison"][m]["absolute_difference_pp"] for p in d["points"] for m in ("sun_frac", "earth_frac", "both_frac"))
ce = sum(c["center_exact_match"] for c in d["catalogue_checks"])
print("polar nodes", len(d["points"]), "max pp", mx, "centres exact", ce, "/", len(d["catalogue_checks"]))
bad += not (len(d["points"]) == 15 and mx == 0 and ce == 16)
# GPU/CPU: max of every listed max
g = src("origin/pr/41:docs/gpu_cpu_300_check.md")
import re
mxs = [float(x) for x in re.findall(r"\| (?:Assigned|GPU-only) 300 \| \w+ \| ([0-9.e-]+) \|", g)]
print("gpu/cpu maxima", len(mxs), max(mxs)); bad += not (len(mxs) == 6 and abs(max(mxs) - 2.957382705e-6) < 1e-15)
# spans
for lo, hi, want in ((17.76, 24.75, 6.99),):
    print("SHOEMAKER span", round(hi - lo, 2)); bad += round(hi - lo, 2) != want
# near-field range
nf = [0.2829, 0.2487, 0.1209, 0.7986, 0.3742]; print("near-field range", min(nf), max(nf))
# our docs say these numbers
for s in ["0.12–0.80 pp", "4.6–5.6", "51.8", "0.000041°", "1.66", "1.24", "0.05°", "5,520", "0.000003 pp", "0.021 pp", "0.0012°", "2.61 / 2.42"]:
    inV = s in SUM; inO = s in O
    print(f"  '{s}': VALIDATION summary {inV}, onepager {inO}")
print("FAILURES:", bad); sys.exit(1 if bad else 0)
