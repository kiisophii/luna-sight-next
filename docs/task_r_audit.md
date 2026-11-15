# Task R — all landed catalogue missions

Checker: **Jiyong Sung**. Hindcast producer: Dongju. Base input: main `274e676`.

The 18 actual landed missions in the catalogue/hindcast union were checked. Future IM-3, Artemis candidate regions and polar research points are excluded. No production data were changed.

## Results and acceptance criteria

| Comparison | N | Maximum absolute difference | Median absolute difference | Criterion |
|---|---:|---:|---:|---|
| Independent direct Sun vs Horizons | 18 | 0.000338859 deg | 0.000005308 deg | <=0.05 deg |
| Existing Apollo landing Sun vs Horizons | 6 | 0.000641284 deg | 0.000183260 deg | <=0.05 deg |
| ALSJ computed Sun at ALSJ coordinates vs Horizons | 6 | 0.016684969 deg | 0.008944882 deg | <=0.05 deg |
| Existing robotic sunset vs Horizons, same mask | 5 | 0.000000000 min | 0.000000000 min | <=2 min |

Numerical criteria: PASS. Catalogue coordinate transcription maximum difference 0 deg. **Source-time agreement is a separate finding, not an all-clear:** Chandrayaan-3 differs by 120 seconds and IM-1 by 53 seconds; Luna 24 has a conflicting NASA time. The 2-minute numerical tolerance does not establish that a stored timestamp is correct.

**Only six existing landing Sun values are stored** in `hindcast.json`, all Apollo. The other 12 rows below establish independent geometry at historical landings; they do not verify a nonexistent stored landing elevation. The app ephemeris starts in 2026. No 2019–2025 historical NPZ was found in the local sibling checkouts, so its random-hour product is not reverified here.

## Landing-time Sun elevation

Sun centre, no atmospheric refraction, 2 m observer. `h0` is from the existing site horizon file, or zero above the reference sphere if unavailable. Values are mathematical geometry, not measured panel illumination or shadow state.

| Mission | UTC touchdown used | Latitude, longitude (deg N/E) | Horizons Sun (deg) | Independent − Horizons (deg) | Stored − Horizons (deg) |
|---|---|---|---:|---:|---:|
| APOLLO11 | 1969-07-20T20:17:39Z | 0.67416, 23.47314 | 10.703172185 | 0.000338859 | -0.000172185 |
| APOLLO12 | 1969-11-19T06:54:36Z | -3.0128, -23.4219 | 5.148358716 | 0.000292946 | 0.000641284 |
| APOLLO14 | 1971-02-05T09:18:13Z | -3.64589, -17.47194 | 10.348805665 | 0.000132712 | 0.000194335 |
| APOLLO15 | 1971-07-30T22:16:29Z | 26.13239, 3.6333 | 12.024153103 | 0.000060864 | -0.000153103 |
| APOLLO16 | 1972-04-21T02:23:35Z | -8.9734, 15.5011 | 14.760764131 | -0.000002664 | 0.000235869 |
| APOLLO17 | 1972-12-11T19:54:58Z | 20.1911, 30.7723 | 13.350125026 | 0.000000063 | -0.000125026 |
| LUNA16 | 1970-09-20T05:18:00Z | -0.5137, 56.3638 | -22.459699118 | -0.000185037 | no existing comparison |
| LUNA20 | 1972-02-21T19:19:00Z | 3.7863, 56.6242 | 53.754687223 | -0.000003096 | no existing comparison |
| LUNA24 | 1976-08-18T06:36:00Z | 12.7142, 62.2129 | -65.692936944 | 0.000002778 | no existing comparison |
| CHANGE3 | 2013-12-14T13:11:00Z | 44.1214, -19.5116 | 24.389788530 | -0.000005129 | no existing comparison |
| CHANGE4 | 2019-01-03T02:26:00Z | -45.4562, 177.5885 | 31.496383526 | 0.000001223 | no existing comparison |
| CHANGE5 | 2020-12-01T15:11:00Z | 43.0576, -51.9161 | 37.490918310 | -0.000009307 | no existing comparison |
| CHANGE6 | 2024-06-01T22:23:00Z | -41.6385, -153.9852 | 36.723209608 | -0.000002831 | no existing comparison |
| CHANDRAYAAN3 | 2023-08-23T12:34:00Z | -69.3741, 32.32 | 8.614636656 | -0.000005487 | no existing comparison |
| SLIM | 2024-01-19T15:20:00Z | -13.316, 25.251 | 37.210744219 | -0.000000812 | no existing comparison |
| IM1 | 2024-02-22T23:23:53Z | -80.13, 1.44 | 10.472814034 | 0.000007069 | no existing comparison |
| IM2 | 2025-03-06T17:28:00Z | -84.7906, 29.1957 | 2.464070197 | -0.000006270 | no existing comparison |
| BLUE_GHOST1 | 2025-03-02T08:34:00Z | 18.562, 61.81 | 3.425059816 | 0.000004306 | no existing comparison |

Negative Sun elevations for Luna 16 and Luna 24 are preserved; a successful landing does not imply a sunlit landing. Luna 24 source-time ambiguity is quantified below.

## Source audit and precision

Each coordinate and time below was read independently from the linked page. NSSDCA Apollo coordinates explicitly use planetocentric Mean Earth/Polar Axis DE421 and identify the Lunar Module. LROC robotic coordinates are actual imaged landers; this audit does not independently establish their exact datum realization. Source precision is retained: minute-only times are written with `:00` for computation, not claimed as second-exact observations.

| Mission | Coordinate source | Time source | Precision and interpretation |
|---|---|---|---|
| APOLLO11 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html) | [touchdown](https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html) | second;  |
| APOLLO12 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html) | [touchdown](https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html) | second;  |
| APOLLO14 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html) | [touchdown](https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html) | second;  |
| APOLLO15 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html) | [touchdown](https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html) | second;  |
| APOLLO16 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html) | [touchdown](https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html) | second;  |
| APOLLO17 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html) | [touchdown](https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html) | second;  |
| LUNA16 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html) | [touchdown](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunarussr.html) | minute; Legacy mission page coordinates differ from LRO coordinates; latter used. |
| LUNA20 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html) | [touchdown](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunarussr.html) | minute; NASA Beyond Earth gives 19:19:09 UT, compatible with minute precision. |
| LUNA24 | [coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html) | [touchdown](https://www.nasa.gov/wp-content/uploads/2023/04/1976.pdf) | minute; Unresolved NASA source conflict: chronology August entry 06:36 GMT versus NSSDCA summary 02:00 UT. Compute both; do not declare source agreement. |
| CHANGE3 | [coordinates](https://lroc.im-ldi.com/images/637) | [touchdown](https://www.cnsa.gov.cn/n6758968/n6758972/c6798565/content.html) | minute; 21:11 Beijing time minus 8 h; longitude 340.4884 E minus 360. |
| CHANGE4 | [coordinates](https://lroc.im-ldi.com/images/1168) | [touchdown](https://lroc.im-ldi.com/images/1168) | minute; Refined LROC location; 13 m horizontal uncertainty, 95% confidence. |
| CHANGE5 | [coordinates](https://lroc.im-ldi.com/images/1172.2020) | [touchdown](https://lroc.im-ldi.com/images/1172.2020) | minute; Longitude 308.0839 E minus 360; horizontal accuracy +/-20 m. |
| CHANGE6 | [coordinates](https://lroc.im-ldi.com/images/1374) | [touchdown](https://www.cnsa.gov.cn/n6758823/n6758838/c10541444/content.html) | minute; June 2 06:23 Beijing minus 8 h is June 1 UTC; longitude 206.0148 E minus 360; horizontal accuracy +/-30 m. |
| CHANDRAYAAN3 | [coordinates](https://lroc.im-ldi.com/images/1314) | [touchdown](https://www.eoibahrain.gov.in/pdf/PR-%20Chandrayaan%203sd.pdf) | minute; Indian government post-event release: 18:04 IST minus 5h30. ISRO mission page confirms date but its 18:04 schedule is a prediction, not used as measured time. |
| SLIM | [coordinates](https://lroc.im-ldi.com/images/1358) | [touchdown](https://lroc.im-ldi.com/images/1358) | minute;  |
| IM1 | [coordinates](https://lroc.im-ldi.com/images/1360) | [touchdown](https://lroc.im-ldi.com/images/1360) | second; Coordinates only 0.01 degree precision; no metre-level accuracy implied. |
| IM2 | [coordinates](https://lroc.im-ldi.com/images/1408) | [touchdown](https://ntrs.nasa.gov/api/citations/20260003150/downloads/MSolo%20PRIME-1%20overview%20and%20results%20-%20LSSW.pdf) | minute; PRIME-1 science-team slide 2 distinguishes target from actual site; NASA initial blog rounds to approximately 17:30 UTC. Lander on side in crater. |
| BLUE_GHOST1 | [coordinates](https://lroc.im-ldi.com/images/1406) | [touchdown](https://fireflyspace.com/missions/blue-ghost-mission-1/) | minute; 02:34 CST plus 6 h; use lander coordinates, not LRO observer position. |

ALSJ is the Apollo Lunar Surface Journal linked by [NASA History](https://www.nasa.gov/history/alsj-and-afj/). Its Sun elevations are older **computed ephemerides**, not independent instrument measurements. At the ALSJ coordinates the largest difference is 0.016684969 degrees. At the modern catalogue point Apollo 11 differs from the ALSJ reported value by 0.053172185 degrees (>0.05); this is retained as a coordinate/input mismatch, not hidden as an ephemeris failure.

Chandrayaan-3: the [post-event Indian government release](https://www.eoibahrain.gov.in/pdf/PR-%20Chandrayaan%203sd.pdf), page 1, reports 18:04 IST (12:34 UTC), while hindcast stores 12:32. This is a government report, not a second-resolved ISRO telemetry event. Its launch-date sentence is erroneous; the landing date is separately supported by the LROC page. The result should be interpreted at minute precision. IM-1: LROC explicitly reports 23:23:53, while hindcast stores 23:23:00.

Luna 24: NASA SP-4021, printed page 183 / PDF page 187, reports 06:36 GMT; the NSSDCA Soviet summary gives 02:00 UT. Both alternatives are retained. The later historical chronology is used for the primary calculation; this audit does not resolve the documentary conflict.

| Mission | Primary time | Alternative time | Alternative source | Alternative − primary Sun (deg) |
|---|---|---|---|---:|
| LUNA20 | 1972-02-21T19:19:00Z | 1972-02-21T19:19:09Z | [source](https://www.nasa.gov/wp-content/uploads/2018/09/beyond-earth-tagged.pdf) | 0.001262177 |
| LUNA24 | 1976-08-18T06:36:00Z | 1976-08-18T02:00:00Z | [source](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunarussr.html) | 2.076715182 |
| IM2 | 2025-03-06T17:28:00Z | 2025-03-06T17:30:00Z | [source](https://www.nasa.gov/blogs/missions/2025/03/06/intuitive-machines-mission-lands-near-south-pole-carrying-nasa-science/) | 0.001358651 |

Luna 20: 19:19:09 in NASA Beyond Earth is consistent with the summary minute 19:19. IM-2: PRIME-1 team slide 2 gives 17:28 UTC; the immediate NASA news post says approximately 17:30. The same slide distinguishes the target coordinate from the actual resting point. Neither approximate alternative is silently promoted to exact telemetry.

## Conditional terrain sunset check

A fresh direct topocentric Skyfield observation was computed at every minute for 30 days after each stored robotic landing (43,201 samples per mission). The first lit-to-unlit edge was selected with solar centre >= linearly interpolated circular terrain mask, equivalent to >=50% of a symmetric solar disk. Seven Horizons samples around each edge reproduce the same first minute. The minute grid is aligned to the existing landing time to compare like with like.

| Mission | Existing sunset UTC | Independent/Horizons sunset UTC | Difference (min) |
|---|---|---|---:|
| CHANDRAYAAN3 | 2023-09-04T06:17Z | 2023-09-04T06:17:00Z | 0 |
| SLIM | 2024-01-31T04:05Z | 2024-01-31T04:05:00Z | 0 |
| IM1 | 2024-03-02T13:55Z | 2024-03-02T13:55:00Z | 0 |
| CHANGE3 | 2013-12-26T16:01Z | 2013-12-26T16:01:00Z | 0 |
| CHANGE4 | 2019-01-13T19:18Z | 2019-01-13T19:18:00Z | 0 |

The five stored robotic `sunlit_at_landing` booleans were also compared with the independent geometry at their stored timestamp: all agree. These booleans are distinct from absent numeric Sun elevations.

**This is conditional on the existing masks and heights.** It independently verifies event calculation and ephemeris agreement, not the DEM, horizon march, local boulder shadows, tilted panels or the real shutdown time. A power-down/hibernation decision is not a sunset measurement. The existing news-based shutdown comparisons and missing Chang'e-4 dormancy source remain limitations; they are not promoted to scientific ground truth.

## Reproduction and provenance

The standalone verifier imports Skyfield/NumPy and its own manually transcribed source file; it imports no production pipeline modules or web code. Direct topocentric observation uses DE440s and MOON_ME_DE421. Horizons uses its independently served ephemeris and high-precision MEAN_ME lunar orientation, quantity 4, airless observer table. Actual model labels are retained in the manifest. Built-in Skyfield historical timescale arrays are hashed; the small pre-1972 differences are retained rather than fitted away.

The [manifest](task_r_manifest.json) records 24 source URLs with raw SHA-256 hashes, 32 Horizons request/response identities, input hashes, kernel hashes, and library versions. Raw data are ignored under `data/processed/task_r/`, cache keys are full URL hashes, and cache reuse verifies byte hashes. All source raw bytes were retrieved with TLS verification; Python CA/network failures were recovered using Windows curl with the OS trust store. No raw source retrieval gaps remain.

```powershell
$py = "C:/Users/jy02s/Documents/lunar-card8-jiyong/.venv/Scripts/python.exe"
& $py -m unittest discover -s pipeline/tests -p "test_task_r*.py" -v
& $py pipeline/task_r_audit.py --kernels ../lunar-card8-jiyong/data/raw/kernels --offline
& $py pipeline/task_r_report.py
```

Omit `--offline` on a fresh checkout. Tests exercise complete mission coverage, UTC/date rollover, circular horizon interpolation, first half-disk sunset selection and rejection of wrong-frame, wrong-epoch, nonfinite and malformed Horizons responses. Fresh run: five tests passed; online and offline calculations completed successfully.

Machine-readable full results: [audit JSON](task_r_audit.json), [landing CSV](task_r_landings.csv). Source transcription: `pipeline/task_r_sources.py`. No all-claims-verified status is asserted: source disagreements and absent stored products remain explicit.
