"""Render the full Task V evidence without importing its numeric implementation."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "docs/task_v_earth_definition.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    random, named = data["random_summary"], data["named_summary"]
    rows = data["rows"] + data["named"]
    out_csv = ROOT / "docs/task_v_earth_definition_rows.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as stream:
        columns = ["scope", "id", "lat", "lon", "centre", "any_part", "pgda", "centre_residual_pp",
                   "any_residual_pp", "definition_increase_pp", "reproduction_delta_pp", "pgda_delta_pp",
                   "pgda_row", "pgda_col", "raw_dn", "reproduction_pass_0_1pp", "pgda_residual_pass_0_1pp"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            truth = row["pgda"]["value"]
            writer.writerow(dict(scope="random" if row["id"].startswith("P") and len(row["id"]) == 4 else "named",
                                 id=row["id"], lat=row["lat"], lon=row["lon"], centre=row["centre"],
                                 any_part=row["any_part"], pgda=truth, centre_residual_pp=(row["centre"] - truth) * 100,
                                 any_residual_pp=(row["any_part"] - truth) * 100,
                                 definition_increase_pp=row["definition_increase_pp"],
                                 reproduction_delta_pp=row["stored_any_delta_pp"], pgda_delta_pp=row["stored_pgda_delta_pp"],
                                 pgda_row=row["pgda"]["row"], pgda_col=row["pgda"]["col"], raw_dn=row["pgda"]["raw_dn"],
                                 reproduction_pass_0_1pp=abs(row["stored_any_delta_pp"]) <= .1,
                                 pgda_residual_pass_0_1pp=abs(row["any_part"] - truth) * 100 <= .1))
    lines = ["# Task V — independent Earth-definition comparison", "",
             "Jiyong Sung, 2026-11-15. Numerical producer imports: none. Production files unchanged.", "",
             "## Result", "",
             f"For all **240 original random points**, switching only the Earth visibility predicate from centre to the original producer's upper-limb any-part approximation changes MAE from **{random['centre']['mae_pp']:.6f} pp to {random['any_part']['mae_pp']:.6f} pp**. The reduction is **{random['mae_reduction_pp']:.6f} pp ({random['mae_reduction_pct']:.3f}%)**. The remaining error is nonzero; this does **not** prove the entire original difference was caused by definition.", "",
             "The published validation file already uses the upper-limb approximation as its primary Earth result; its `alt_definitions.earth_centre` contains the approximately 3.87 pp result. This task independently recomputes both quantities; it does not change the app's conservative Earth-centre rule.", "",
             "| Scope / predicate | N | MAE pp | RMSE pp | Bias (ours−PGDA) pp | Pearson r | Median absolute pp | Max absolute pp |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, summary in (("Random", random), ("Named (separate)", named)):
        for predicate in ("centre", "any_part"):
            s = summary[predicate]
            lines.append(f"| {name} / {predicate} | {s['n']} | {s['mae_pp']:.9f} | {s['rmse_pp']:.9f} | {s['bias_pp']:+.9f} | {s['r']:.9f} | {s['median_abs_pp']:.9f} | {s['max_abs_pp']:.9f} |")
    lines += ["", f"At the random points, the definition increases visibility by mean **{random['definition_increase_mean_pp']:.6f} pp**, median {random['definition_increase_median_pp']:.6f} pp, maximum {random['definition_increase_max_pp']:.6f} pp. Absolute PGDA residual improves at {random['improved_points']} points, worsens at {random['worsened_points']}, and is unchanged at {random['unchanged_points']}. This pointwise mixed behavior is why the mean definition increase cannot simply be subtracted from the original MAE.", "",
              "## Reproduction and criteria", "",
              "Reproduction criterion: independently calculated any-part fraction versus the stored `ours_earth`, ≤0.1 pp per point. Direct raster check: the stored scaled PGDA fraction must equal the original pixel's scaled value within 0.00001 pp. The producer scales DN using float32, then writes every floating CSV field to five decimals (`validate.py:write_csv`); `validate_ours.py` reads those CSVs into the published JSON. The requested 0.1 pp absolute PGDA comparison is also reported, but is a scientific residual diagnostic, not evidence that the independent implementation failed.", ""]
    for name, group, summary in (("Random", data["rows"], random), ("Named", data["named"], named)):
        deltas = sorted(abs(r["stored_any_delta_pp"]) for r in group)
        n = len(deltas)
        median = (deltas[(n - 1)//2] + deltas[n//2]) / 2
        pgda_delta = max(abs(r["stored_pgda_delta_pp"]) for r in group)
        lines += [f"- {name}: {n} rows; reproduction maximum {max(deltas):.12f} pp, median {median:.12f} pp; {len(summary['reproduction_above_0_1pp'])} failures. Direct PGDA maximum difference {pgda_delta:.12f} pp. PGDA residual >0.1 pp: {len(summary['residual_above_0_1pp'])}/{n}."]
    lines += ["", "Rounded exactly like the original summary (ours and PGDA to five decimals):", "",
              "| Predicate | Recomputed MAE pp | Original MAE pp | Recomputed r | Original r |", "|---|---:|---:|---:|---:|"]
    for key, oldkey in (("centre", "earth_centre"), ("any_part", "earth_any_part")):
        new = random["rounded_like_original"][key]
        old = data["original_alt_definitions"][oldkey]
        lines.append(f"| {key} | {new['mae_pp']:.9f} | {old['mae_pp']} | {new['r']:.9f} | {old['r']} |")
    lines += ["", "## Controlled comparison and limits", "",
              "- Every random-point pair uses exactly the same location, reconstructed terrain mask, observer height, Earth vectors, and 81,444 epochs. Dates are 2020-01-01 00:00 UTC through 2038-07-31 22:00 UTC, two-hour cadence; only the binary visibility predicate changes.",
              "- Original random-point mask checkpoints were not available locally. The independent Cartesian ray marcher reconstructs all 240 masks using the original PGDA 60 m raster to 60 km and 240 m raster to 300 km, bilinear heights, 720 bearings, 4,001 logarithmic distances from 200 m, lunar curvature and a 2 m observer. All samples are examined, with missing terrain treated as an error. This isolates the definition conditional on this reconstructed mask; reproduction error is shown above.",
              "- Centre predicate: `elevation > horizon(azimuth)`. Original any-part approximation: `elevation + asin(6371 km / topocentric_distance) > horizon(centre_azimuth)`. The approximation tests the upper limb at the centre azimuth. It does **not** search the whole disk against a varying horizon. PGDA's general any-part description alone does not establish identical implementation geometry.",
              "- The existing 18.6-year Earth ephemeris is reused and hashed. This is an independent metric integration and random-point terrain reconstruction, not a fresh independent ephemeris calculation.",
              "- The 16 named points are separate evidence. Their existing, finer site masks were authored by Jiyong; reusing them in an independent metric loop does not independently validate those masks. They do not enter the 240-point headline MAE.",
              "- PGDA describes hourly averaging over an 18.6-year cycle, but the exact modeled dates and observer height are not established by the product page/label. The label's 2009–2013 start/stop fields span about four years and cannot identify that modeled cycle. Temporal sampling, observer height, terrain differences, and upper-limb approximation remain possible contributors; their individual shares of the residual have not been measured.",
              "- Neighbourhood spread uses the original square-pixel convention (±1 pixel at 60 m for random points; ±5 pixels at 60 m or ±2 pixels at 120 m for named sites). It is location sensitivity, not a statistical uncertainty interval.", "",
              "## Sources and exact inputs", "",
              "- [NASA PGDA product 69](https://pgda.gsfc.nasa.gov/products/69): Earth considered visible when any part of its disk is unobscured; hourly 18.6-year averages. Citation: [Mazarico et al. (2011)](https://doi.org/10.1016/j.icarus.2010.10.030).",
              "- [60 m Earth GeoTIFF](https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF), [120 m Earth GeoTIFF](https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_75S_120M_201608_EARTH.TIF), and [original PDS label](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL): DN × 0.00004, zero offset, DE421 mean-Earth/polar-axis, radius 1737.4 km. Reads use original full-resolution pixels, not COG overviews.",
              "- [PGDA product 90](https://pgda.gsfc.nasa.gov/products/90), [Barker et al. (2023)](https://doi.org/10.3847/PSJ/acf3e1): [60 m terrain](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF) and [240 m terrain](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF). Only the needed source windows are fetched.",
              "- All used ephemeris, validation, mask and raster hashes, input paths, source validators, and decoded DEM window bounds are recorded in [machine-readable evidence](task_v_earth_definition.json). The [source audit](task_v_sources.json) includes the original label SHA256 and fields. All 256 rows with full precision and explicit pass/fail columns are in [CSV](task_v_earth_definition_rows.csv).", "",
              "## Re-run", "", "The standalone audit disables Numba disk JIT caching because dynamic test imports otherwise serialize a non-importable module identity. Each process compiles its kernels locally; hashed scientific DEM/mask checkpoints still support resume. This affects startup only, not the numerical method.", "", "```powershell",
              "& 'C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe' pipeline/task_v_earth_definition.py --ephem 'C:/Users/jy02s/Documents/lunar-card8-jiyong/data/processed/ephem_2020-2038_2h.npz'",
              "& 'C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe' pipeline/task_v_report.py",
              "& 'C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe' -m pytest pipeline/tests/test_task_v_earth_definition.py -q", "```", "",
              "## Full row table", "", "Fractions shown as percentages; residuals and definition changes are percentage points. `FAIL` means absolute any-part PGDA residual >0.1 pp. Unrounded results and every failure are retained in JSON/CSV.", "",
              "| ID | Centre % | Any-part % | PGDA % | Centre residual pp | Any residual pp | Definition increase pp | PGDA criterion |",
              "|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in rows:
        c, a, p = row["centre"] * 100, row["any_part"] * 100, row["pgda"]["value"] * 100
        lines.append(f"| {row['id']} | {c:.6f} | {a:.6f} | {p:.6f} | {c-p:+.6f} | {a-p:+.6f} | {a-c:.6f} | {'FAIL' if abs(a-p)>.1 else 'pass'} |")
    (ROOT / "docs/task_v_earth_definition.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Rendered {len(rows)} rows; source JSON SHA256 {hashlib.sha256(path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
