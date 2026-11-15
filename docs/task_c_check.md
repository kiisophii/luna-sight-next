# Task C — full ground-station windows and lunar links

Jiyong; clarified task on main `64e11f9`. All four stations, the full five-year interval 2026-01-01T00Z to 2031-01-01T00Z, every KDSA daily row, and all 33 catalogue sites × four station series were recomputed. This PR changes verification code/docs only.

## Result

- Recomputed 10,517,764 one-minute samples and 7,058 observing windows; maximum rise/set difference **1.002930 s** (criterion ≤60 s). Unmatched windows: 0.
- Four hourly station series: **0 differing bits** across 175,296 hours. All 132 site×station series: **0 differing bits** across 5,784,768 bits; max total difference **0 h** (criterion ≤1 h).
- KDSA: 1826 dates / 2516 rows recomputed; **6 dates differ** under exact displayed-row comparison.
- **2 published files fail strict JSON parsing**: `windows_dsn_goldstone.json`, `windows_dsn_madrid.json`.

All mismatches are retained below and in the machine-readable report. Passing the geometric window criterion does not imply exact KST-minute formatting or valid JSON.

## Every station

| Station | Windows recomputed / stored | Max edge difference (s) | Hourly bit mismatches | Unmatched computed / stored |
|---|---:|---:|---:|---:|
| KDSA | 1764 / 1764 | 0.991210938 | 0 | 0 / 0 |
| DSN_GOLDSTONE | 1765 / 1765 | 1.000976562 | 0 | 0 / 0 |
| DSN_MADRID | 1765 / 1765 | 0.993164062 | 0 | 0 / 0 |
| DSN_CANBERRA | 1764 / 1764 | 1.002929688 | 0 | 0 / 0 |

All individual window comparisons, including signed rise/set differences and peak-height checks: [task_c_windows.csv](task_c_windows.csv). Every failure above 60 s is in [task_c_summary.json](task_c_summary.json); none are filtered from the full table.

## KST daily comparison

An exact row includes start minute, end minute and whole-window maximum elevation. The existing producer formats HH:MM by discarding seconds. Our roots are refined independently to a ≤0.04 s bracket; the producer uses a ≤1 s discrete search. A sub-second shift across an integer-minute boundary can therefore change one printed minute even though both edges pass the 60 s criterion. This is reported as a mismatch, not silently snapped to the published value.

| KST date | Independently computed rows | Published rows |
|---|---|---|
| 2026-03-04 | `[["00:00", "06:14", 57.59], ["20:17", "24:00", 51.09]]` | `[["00:00", "06:15", 57.59], ["20:17", "24:00", 51.09]]` |
| 2026-12-09 | `[["09:02", "15:45", 24.53]]` | `[["09:03", "15:45", 24.53]]` |
| 2028-06-23 | `[["06:17", "19:27", 77.25]]` | `[["06:17", "19:28", 77.25]]` |
| 2029-12-14 | `[["00:00", "00:19", 56.8], ["13:50", "24:00", 61.61]]` | `[["00:00", "00:20", 56.8], ["13:50", "24:00", 61.61]]` |
| 2030-07-28 | `[["04:16", "16:59", 73.8]]` | `[["04:16", "17:00", 73.8]]` |
| 2030-09-29 | `[["09:15", "18:05", 37.58]]` | `[["09:16", "18:05", 37.58]]` |

## Strict JSON defect

Goldstone’s final window ends at the analysis boundary before its internal altitude maximum. Madrid’s first window starts after its internal maximum. The producer writes `NaN` for those unavailable peaks. `JSON.parse`/browser `response.json()` reject these complete files. KDSA and Canberra files parse successfully. Existing KDSA UI and station-bit link calculation read different, valid files; this does not prove those current views fail.

Suggested integrator fix: encode missing interior peak as `null` (or explicitly define a clipped-window maximum), document that choice, and rerun the format check. No production values are changed here. Exact parse errors are in [task_c_check.json](task_c_check.json).

## All 33 site totals

`stations.json` stores station-only Moon visibility, not precomputed site×station bits. We therefore compare against actual `core.earthVisible`, `korea.stationBits` and `diff_data.siteStationLink` in a separate Node reference harness, and also against the existing `docs/korea_links_check.json` totals. This resolves the task wording without inventing a per-site cache.

| Site | Earth-visible h | KDSA link h | Any-DSN link h | App totals equal | Station bit mismatches |
|---|---:|---:|---:|---|---:|
| APOLLO11 | 43824 | 18213 | 43123 | True | 0 |
| APOLLO12 | 43824 | 18213 | 43123 | True | 0 |
| APOLLO14 | 43824 | 18213 | 43123 | True | 0 |
| APOLLO15 | 43824 | 18213 | 43123 | True | 0 |
| APOLLO16 | 43824 | 18213 | 43123 | True | 0 |
| APOLLO17 | 43824 | 18213 | 43123 | True | 0 |
| LUNA16 | 43824 | 18213 | 43123 | True | 0 |
| LUNA20 | 43824 | 18213 | 43123 | True | 0 |
| LUNA24 | 43824 | 18213 | 43123 | True | 0 |
| CHANGE3 | 43824 | 18213 | 43123 | True | 0 |
| CHANGE4 | 0 | 0 | 0 | True | 0 |
| CHANGE5 | 43824 | 18213 | 43123 | True | 0 |
| CHANGE6 | 0 | 0 | 0 | True | 0 |
| CHANDRAYAAN3 | 43824 | 18213 | 43123 | True | 0 |
| SLIM | 43824 | 18213 | 43123 | True | 0 |
| IM1 | 43824 | 18213 | 43123 | True | 0 |
| IM2 | 35682 | 15299 | 35190 | True | 0 |
| BLUE_GHOST1 | 43824 | 18213 | 43123 | True | 0 |
| ARTEMIS_CABEUS_B | 12988 | 6075 | 12918 | True | 0 |
| ARTEMIS_HAWORTH | 25653 | 11507 | 25416 | True | 0 |
| ARTEMIS_MALAPERT | 43824 | 18213 | 43123 | True | 0 |
| ARTEMIS_MOUTON_PLATEAU | 25579 | 11474 | 25343 | True | 0 |
| ARTEMIS_MOUTON | 26197 | 11703 | 25946 | True | 0 |
| ARTEMIS_NOBILE_RIM1 | 29790 | 13118 | 29462 | True | 0 |
| ARTEMIS_NOBILE_RIM2 | 33747 | 14547 | 33300 | True | 0 |
| ARTEMIS_DE_GERLACHE_RIM2 | 24220 | 10974 | 24022 | True | 0 |
| ARTEMIS_SLATER_PLAIN | 17429 | 8037 | 17317 | True | 0 |
| SHACKLETON_RIM | 21887 | 9986 | 21723 | True | 0 |
| CONNECTING_RIDGE | 19234 | 8856 | 19106 | True | 0 |
| PEAK_NEAR_SHACKLETON | 24244 | 10948 | 24042 | True | 0 |
| DE_GERLACHE_RIM1 | 25067 | 11291 | 24849 | True | 0 |
| SHOEMAKER_RIM_A | 19042 | 8669 | 18905 | True | 0 |
| IM3_REINER_GAMMA | 43824 | 18213 | 43123 | True | 0 |

All 132 per-station totals: [task_c_links.csv](task_c_links.csv). Complete packed computed link bits, mismatched hour indices, all windows, KST rows and input hashes: [task_c_check.json](task_c_check.json).

## Method, sources and scope

Coordinates were independently read from [NAIF KDSA01 kernel](https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf) and [DSN 810-005 module 301 Rev P, Table 5, page 16](https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf). Exact downloaded source hashes are in station identities. DSN DMS coordinates were converted directly; KDSA LATLON was parsed from the kernel. Published rounded coordinates agree within 5.1e-9°. As in the app’s generator, Skyfield uses WGS84 station positions and apparent Moon-centre altitude without refraction or local station terrain; this checks that convention, not the effect of changing terrestrial reference frames.

Independent station search: all one-minute samples, every sign-change bracket refined by our vector bisection to ≤0.04 s, local maxima refined with our ternary search, explicit endpoint clipping. Monthly NPZ checkpoints are guarded by source/code/station/input hashes. The full-minute grid also checks the whole span for missing/extra events. All interior daily peaks are comfortably above 10° at these stations; clipped endpoints are explicitly retained.

We use Skyfield 1.54, DE440s and builtin timescale/Delta-T, as does the producer. The numerical search, KST splitting and lunar Earth-mask loop are our own code; neither korea_links.py nor verify_korea.py is imported. This is an independent implementation of the search/composition, **not an independent astronomical ephemeris model**. Future Earth-rotation prediction accuracy is outside this software agreement test.

Hourly lunar link = Earth centre above the fixed production terrain mask AND Moon centre ≥10° at the station. Independent NumPy vectors include 2 m observer height, 0.5° mask interpolation and all 43,824 samples. The actual-JS harness is only the comparison target. No lunar terrain is recomputed in this task. This is geometric availability, not antenna booking, signal strength or a link budget.

## Reproduction

Full minute-grid recomputation: **128.84 s**; final fingerprint-checked checkpoint resume: 0.75 s. Implementation/review time is additional. Four CPU station workers, single-thread numerical libraries, two physical CPU cores reserved. GPU was not needed for the Skyfield library.

```powershell
node pipeline/task_c_browser.mjs
python pipeline/task_c_check.py --kernel-dir PATH_TO_NAIF_KERNELS
python pipeline/task_c_report.py
python -m pytest pipeline/tests/test_task_c.py -q
```

The kernel directory must contain the existing de440s.bsp. Download the two cited coordinate sources unchanged to data/processed/task_c/sources/kdsa01.tf and 301P.pdf. Raw sources and monthly altitude arrays remain ignored. Re-running the checker validates checkpoints and every actual-browser input hash before comparisons; a stale-reference rejection was exercised. The browser harness fingerprints its source modules, every fetched file and all four windows files even when strict parsing fails. Text-file SHA-256 can change with CRLF/LF conversion. SI usage and the verification ledger record this check; existing global verification counts are not inflated.
