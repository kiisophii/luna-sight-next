"""Render the Task R evidence tables without changing production data."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    report=json.loads((ROOT/'docs/task_r_audit.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'docs/task_r_manifest.json').read_text(encoding='utf-8'))
    summary=report['summary']
    numeric_pass=all(summary[k] for k in ('ephemeris_pass','stored_elevation_pass','sunset_pass','coordinate_transcription_pass','stored_landing_sunlit_pass'))
    lines=['# Task R — all landed catalogue missions', '',
           'Checker: **Jiyong Sung**. Hindcast producer: Dongju. Base input: main `274e676`.', '',
           'The 18 actual landed missions in the catalogue/hindcast union were checked. Future IM-3, Artemis candidate regions and polar research points are excluded. No production data were changed.', '',
           '## Results and acceptance criteria', '',
           '| Comparison | N | Maximum absolute difference | Median absolute difference | Criterion |',
           '|---|---:|---:|---:|---|']
    for label,key,unit,limit in [('Independent direct Sun vs Horizons','independent_vs_horizons_deg','deg','<=0.05 deg'),
                               ('Existing Apollo landing Sun vs Horizons','stored_vs_horizons_deg','deg','<=0.05 deg'),
                               ('ALSJ computed Sun at ALSJ coordinates vs Horizons','alsj_same_point_deg','deg','<=0.05 deg'),
                               ('Existing robotic sunset vs Horizons, same mask','stored_sunset_vs_horizons_minutes','min','<=2 min')]:
        s=summary[key]
        lines.append(f"| {label} | {s['n']} | {s['max_abs']:.9f} {unit} | {s['median_abs']:.9f} {unit} | {limit} |")
    lines += ['',f"Numerical criteria: {'PASS' if numeric_pass else 'FAIL — inspect JSON errors'}. Catalogue coordinate transcription maximum difference {summary['coordinate_difference_deg']['max_abs']:.3g} deg. **Source-time agreement is a separate finding, not an all-clear:** Chandrayaan-3 differs by 120 seconds and IM-1 by 53 seconds; Luna 24 has a conflicting NASA time. The 2-minute numerical tolerance does not establish that a stored timestamp is correct.", '',
              '**Only six existing landing Sun values are stored** in `hindcast.json`, all Apollo. The other 12 rows below establish independent geometry at historical landings; they do not verify a nonexistent stored landing elevation. The app ephemeris starts in 2026. No 2019–2025 historical NPZ was found in the local sibling checkouts, so its random-hour product is not reverified here.', '',
              '## Landing-time Sun elevation', '',
              'Sun centre, no atmospheric refraction, 2 m observer. `h0` is from the existing site horizon file, or zero above the reference sphere if unavailable. Values are mathematical geometry, not measured panel illumination or shadow state.', '',
              '| Mission | UTC touchdown used | Latitude, longitude (deg N/E) | Horizons Sun (deg) | Independent − Horizons (deg) | Stored − Horizons (deg) |',
              '|---|---|---|---:|---:|---:|']
    for r in report['landings']:
        stored=f"{r['stored_minus_horizons_deg']:.9f}" if 'stored_minus_horizons_deg' in r else 'no existing comparison'
        lines.append(f"| {r['id']} | {r['landing_utc']} | {r['lat']}, {r['lon']} | {r['horizons_sun_deg']:.9f} | {r['independent_minus_horizons_deg']:.9f} | {stored} |")
    lines += ['', 'Negative Sun elevations for Luna 16 and Luna 24 are preserved; a successful landing does not imply a sunlit landing. Luna 24 source-time ambiguity is quantified below.', '',
              '## Source audit and precision', '',
              'Each coordinate and time below was read independently from the linked page. NSSDCA Apollo coordinates explicitly use planetocentric Mean Earth/Polar Axis DE421 and identify the Lunar Module. LROC robotic coordinates are actual imaged landers; this audit does not independently establish their exact datum realization. Source precision is retained: minute-only times are written with `:00` for computation, not claimed as second-exact observations.', '',
              '| Mission | Coordinate source | Time source | Precision and interpretation |',
              '|---|---|---|---|']
    for r in report['landings']:
        lines.append(f"| {r['id']} | [coordinates]({r['coordinate_source']}) | [touchdown]({r['time_source']}) | {r['time_precision']}; {r['note']} |")
    lines += ['',
              'ALSJ is the Apollo Lunar Surface Journal linked by [NASA History](https://www.nasa.gov/history/alsj-and-afj/). Its Sun elevations are older **computed ephemerides**, not independent instrument measurements. At the ALSJ coordinates the largest difference is 0.016684969 degrees. At the modern catalogue point Apollo 11 differs from the ALSJ reported value by 0.053172185 degrees (>0.05); this is retained as a coordinate/input mismatch, not hidden as an ephemeris failure.', '',
              'Chandrayaan-3: the [post-event Indian government release](https://www.eoibahrain.gov.in/pdf/PR-%20Chandrayaan%203sd.pdf), page 1, reports 18:04 IST (12:34 UTC), while hindcast stores 12:32. This is a government report, not a second-resolved ISRO telemetry event. Its launch-date sentence is erroneous; the landing date is separately supported by the LROC page. The result should be interpreted at minute precision. IM-1: LROC explicitly reports 23:23:53, while hindcast stores 23:23:00.', '',
              'Luna 24: NASA SP-4021, printed page 183 / PDF page 187, reports 06:36 GMT; the NSSDCA Soviet summary gives 02:00 UT. Both alternatives are retained. The later historical chronology is used for the primary calculation; this audit does not resolve the documentary conflict.', '',
              '| Mission | Primary time | Alternative time | Alternative source | Alternative − primary Sun (deg) |',
              '|---|---|---|---|---:|']
    for r in report['landings']:
        if 'alternate_utc' in r:
            lines.append(f"| {r['id']} | {r['landing_utc']} | {r['alternate_utc']} | [source]({r['alternate_source']}) | {r['alternate_minus_primary_sun_deg']:.9f} |")
    lines += ['',
              'Luna 20: 19:19:09 in NASA Beyond Earth is consistent with the summary minute 19:19. IM-2: PRIME-1 team slide 2 gives 17:28 UTC; the immediate NASA news post says approximately 17:30. The same slide distinguishes the target coordinate from the actual resting point. Neither approximate alternative is silently promoted to exact telemetry.', '',
              '## Conditional terrain sunset check', '',
              'A fresh direct topocentric Skyfield observation was computed at every minute for 30 days after each stored robotic landing (43,201 samples per mission). The first lit-to-unlit edge was selected with solar centre >= linearly interpolated circular terrain mask, equivalent to >=50% of a symmetric solar disk. Seven Horizons samples around each edge reproduce the same first minute. The minute grid is aligned to the existing landing time to compare like with like.', '',
              '| Mission | Existing sunset UTC | Independent/Horizons sunset UTC | Difference (min) |',
              '|---|---|---|---:|']
    for r in report['sunsets']:
        lines.append(f"| {r['id']} | {r['stored_sunset_utc']} | {r['horizons_sunset_utc']} | {r['stored_minus_horizons_minutes']:.0f} |")
    lines += ['',
              f"The five stored robotic `sunlit_at_landing` booleans were also compared with the independent geometry at their stored timestamp: {'all agree' if summary['stored_landing_sunlit_pass'] else 'disagreement; inspect JSON'}. These booleans are distinct from absent numeric Sun elevations.", '',
              '**This is conditional on the existing masks and heights.** It independently verifies event calculation and ephemeris agreement, not the DEM, horizon march, local boulder shadows, tilted panels or the real shutdown time. A power-down/hibernation decision is not a sunset measurement. The existing news-based shutdown comparisons and missing Chang\'e-4 dormancy source remain limitations; they are not promoted to scientific ground truth.', '',
              '## Reproduction and provenance', '',
              'The standalone verifier imports Skyfield/NumPy and its own manually transcribed source file; it imports no production pipeline modules or web code. Direct topocentric observation uses DE440s and MOON_ME_DE421. Horizons uses its independently served ephemeris and high-precision MEAN_ME lunar orientation, quantity 4, airless observer table. Actual model labels are retained in the manifest. Built-in Skyfield historical timescale arrays are hashed; the small pre-1972 differences are retained rather than fitted away.', '',
              f"The [manifest](task_r_manifest.json) records {len(manifest['sources'])} source URLs with raw SHA-256 hashes, {len(manifest['horizons'])} Horizons request/response identities, input hashes, kernel hashes, and library versions. Raw data are ignored under `data/processed/task_r/`, cache keys are full URL hashes, and cache reuse verifies byte hashes. All source raw bytes were retrieved with TLS verification; Python CA/network failures were recovered using Windows curl with the OS trust store. No raw source retrieval gaps remain.", '',
              '```powershell',
              '$py = "C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe"',
              '& $py -m unittest discover -s pipeline/tests -p "test_task_r*.py" -v',
              '& $py pipeline/task_r_audit.py --kernels ../lunar-card8-jiyong/data/raw/kernels --offline',
              '& $py pipeline/task_r_report.py',
              '```', '',
              'Omit `--offline` on a fresh checkout. Tests exercise complete mission coverage, UTC/date rollover, circular horizon interpolation, first half-disk sunset selection and rejection of wrong-frame, wrong-epoch, nonfinite and malformed Horizons responses. Fresh run: five tests passed; online and offline calculations completed successfully.', '',
              'Machine-readable full results: [audit JSON](task_r_audit.json), [landing CSV](task_r_landings.csv). Source transcription: `pipeline/task_r_sources.py`. No all-claims-verified status is asserted: source disagreements and absent stored products remain explicit.', '']
    (ROOT/'docs/task_r_audit.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__': main()
