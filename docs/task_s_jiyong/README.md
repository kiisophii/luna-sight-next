# Task S: independent re-reading of all 33 coordinate sources

Checker: Jiyong Sung with OpenAI Codex; 2026-11-15. Catalogue producer: Minchul Kim. Base main `300b849`; independent comparison with Soyun [PR #76](https://github.com/kiisophii/lunar-landing-site-navigator/pull/76), head `31a11b27a8877d5aab6e5ad40a643c3c7e747254`.

**33/33 coordinate pairs equal their cited primary-source decimals after hemisphere and longitude normalization; maximum transcription displacement is 0 m. This is NOT a claim of zero physical position error, uniform coordinate frames, or agreement between every available source.**

No production coordinates, labels, horizons, metrics or UI files change. No forced coordinate correction or downstream recomputation is proposed by this audit. Three alternate-source differences and several interpretation limits remain explicit below.

## What was actually checked

Freshly reopened NASA Apollo and artifact tables (9 sites), nine LROC posts (9), the Artemis paper Table A1 (9), NASA NTRS Glaser Table 2 (1), NASA Lunar Surface Data Book Table A2-2 (4), and the Frontiers Lunar Vertex target paper (1). Separate source groups read original pages without using the producer's audit as truth. A new Decimal comparator rechecks all 33 signed source strings, rejects missing/duplicate evidence, and computes spherical separations at R=1737.4 km. Source acquisition itself is not automated by the comparator: the source strings were transcribed and visually inspected by AI, with human SI review pending.

All successful raw HTML/PDF responses are retained locally under ignored `data/processed/task_s_jiyong/` (D-drive-backed storage); evidence JSON records URL, retrieval channel/status/time, SHA256, location and coordinate role. Raw copyrighted full publications are not committed. The following files retain the detailed evidence:

- [Historical and planned target](historical.json): Apollo 6, Luna 3, IM3 target.
- [Robotic landers](robotic.json): 9 cited LROC posts and selected alternate posts.
- [Artemis research points](artemis.json): 9 CLS rows, published PDF identification and visible minus signs.
- [Polar research/DEM centres](polar.json): 5 rows, freshly rendered PDF tables and USGS source metadata.
- [Computed comparisons](comparison.json): all 33 results and input hashes.

## Findings beyond an exact source copy

| Item | Catalogue / cited source | Other primary-source statement | Meaning / action |
|---|---|---|---|
| Chang'e 3 | 44.1214 N, 19.5116 W, [LROC /637](https://lroc.im-ldi.com/images/637) | [NASA artifact table](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html): 19.5117 W; **2.1768 m** difference | Real source-to-source disagreement in the last digit. Cited LROC value is copied correctly. LROC post supplies no numeric uncertainty; do not claim this difference is below a stated error bar. |
| Chang'e 4 | 45.4562 S, 177.5885 E, [LROC /1168](https://lroc.im-ldi.com/images/1168) | NASA artifact table: 45.4561 S; **3.0323 m** difference | LROC specifically reports a refined estimate and 13 m uncertainty at 95% confidence; retain cited refined coordinate. |
| Blue Ghost 1 | 18.562 N, 61.810 E, [LROC /1406](https://lroc.im-ldi.com/images/1406), March 4 2025 | Later [LROC /1407](https://lroc.im-ldi.com/images/1407), March 7: 18.5623 N, 61.8103 E; **12.5349 m** difference | Later values round to the current three-decimal values. The post does not call this a refinement or quantify increased accuracy. Optional source/precision update for integrator consideration, not evidence that the current value was mistranscribed. Recompute dependent data only if the team adopts a coordinate change. |
| Chang'e 5 uncertainty wording | Catalogue note calls accuracy horizontal | [LROC /1172.2020](https://lroc.im-ldi.com/images/1172.2020) gives estimated accuracy +/-20 m without explicitly qualifying horizontal or a confidence level | Suggested future note-only correction: use the source's unqualified accuracy wording. No data edit here. |
| Source coordinate frames | App uses MOON_ME DE421 | NASA Apollo table explicitly identifies compatible ME/PA DE421; the nine cited robotic posts do not name that frame | Numeric equality is not an independently established frame transformation. Leave unsupported frame claims unverified. |

The alternate-source search is targeted, not an exhaustive search of every historical measurement. Short printed precision (notably IM1) also limits what matching decimals can establish. Actual positional uncertainty is not estimated by this audit.

## The Shoemaker and Shackleton questions

[Data Book Rev A](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf), p.57 section A2.1, explicitly identifies its table positions as centres of original DEM polygons. Its stated 5-10 m accuracy concerns those centres, not surveyed crests. LM2 = -88.0792, 11.88866 exactly; the catalogue already labels it **DEM region centre**. R01, R07 and R11 have the same qualification. A name containing Rim or Peak does not turn these coordinates into a summit survey.

We independently sampled the original PGDA 20 m DEM along the spherical ray from the freshly read USGS crater centre through each point. The search is +/-3 km around the point, with bilinear interpolation and both 20 m and 5 m radial sampling. A denser sampling step does not increase DEM resolution. This diagnostic uses its own NumPy/pyproj code, not Soyun's script or a production horizon routine. Exact inputs and results: [rim_profiles.json](rim_profiles.json).

| Point | Distance from local radial maximum, 20 m / 5 m sampling | Below that maximum, 20 m / 5 m sampling | Interpretation |
|---|---:|---:|---|
| SHOEMAKER_RIM_A (LM2) | 540 / 530 m outward | 27.72 / 27.83 m | Reproduces the broad terrain finding in #76. Fails that audit's chosen 500 m crest threshold, but is a correctly copied polygon centre. |
| Current SHACKLETON_RIM | 0 / 0 m | 0 / 0 m | On the sampled radial maximum in this DEM, consistent with the published research rim point. |
| Old R04 polygon centre | 1820 / 1835 m inward | 933.79 / 934.11 m | On the interior side well below the local rim maximum. R04 remains a valid published polygon centre; it is a different point from the current illumination-study location. |

[USGS Shoemaker](https://planetarynames.wr.usgs.gov/Feature/5494) and [USGS Shackleton](https://planetarynames.wr.usgs.gov/Feature/5450) provide approximate crater centres, not surveyed radial crest lines. A local elevation maximum and a 500 m cutoff are diagnostic choices, not geological ground truth. We do not independently endorse all 33 terrain classifications in #76: this audit rechecks all 33 **source coordinates**, and independently probes these two material rim questions.

## Artemis access and interpretation

The direct Wiley GET returned HTTP 403. The web retrieval channel exposed the original article HTML, but that does not mean a live desktop browser passed Wiley's access check. The ETH published version downloaded successfully after earlier 429 responses: [published PDF](https://www.research-collection.ethz.ch/server/api/core/bitstreams/fdbbd74d-ec07-4adc-9869-51a416cce9f1/content), SHA256 `46bdd0636b169225c89a9860cdd99307ac513c6355873845e8790ec69568df95`. Cover/DOI/version were checked against [10.1029/2025JE009434](https://doi.org/10.1029/2025JE009434).

Table A1 article pages 25-27 (ETH file pages 26-28) was rendered and visually read. PDF extraction/rendering can lose minus signs and leading digits; a working PyMuPDF rendering was used to confirm the numerical cells, not guessed sign restoration. The nine entries are the paper's representative research **candidate landing sites**, not NASA-selected touchdown points or the centres of nine regions. IM3 is likewise a published planned science target, not an observed touchdown. This audit does not determine current mission scheduling/status.

## All 33 source-coordinate results

| Site | Source latitude | Normalized east-positive longitude | Source locator | Transcription displacement |
|---|---:|---:|---|---:|
| APOLLO11 | 0.67416 | 23.47314 | Apollo Landing Site Coordinates table, Apollo 11, Lunar Module row (not LRRR or ALSEP). | 0 m |
| APOLLO12 | -3.0128 | -23.4219 | Apollo Landing Site Coordinates table, Apollo 12, Lunar Module row (not LRRR or ALSEP). | 0 m |
| APOLLO14 | -3.64589 | -17.47194 | Apollo Landing Site Coordinates table, Apollo 14, Lunar Module row (not LRRR or ALSEP). | 0 m |
| APOLLO15 | 26.13239 | 3.63330 | Apollo Landing Site Coordinates table, Apollo 15, Lunar Module row (not LRRR or ALSEP). | 0 m |
| APOLLO16 | -8.9734 | 15.5011 | Apollo Landing Site Coordinates table, Apollo 16, Lunar Module row (not LRRR or ALSEP). | 0 m |
| APOLLO17 | 20.1911 | 30.7723 | Apollo Landing Site Coordinates table, Apollo 17, Lunar Module row (not LRRR or ALSEP). | 0 m |
| LUNA16 | -0.5137 | 56.3638 | Table of Anthropogenic Impacts and Spacecraft on the Moon, Luna 16 Soft Landing row; note d. | 0 m |
| LUNA20 | 3.7863 | 56.6242 | Table of Anthropogenic Impacts and Spacecraft on the Moon, Luna 20 Soft Landing row; note d. | 0 m |
| LUNA24 | 12.7142 | 62.2129 | Table of Anthropogenic Impacts and Spacecraft on the Moon, Luna 24 Soft Landing row; note d. | 0 m |
| CHANGE3 | 44.1214 | -19.5116 | Paragraph beginning Since the rover; lander coordinates sentence | 0 m |
| CHANGE4 | -45.4562 | 177.5885 | Final paragraph after rover distance table | 0 m |
| CHANGE5 | 43.0576 | -51.9161 | First body paragraph after opening image | 0 m |
| CHANGE6 | -41.6385 | -153.9852 | Second body paragraph: coordinates computed by the LROC team | 0 m |
| CHANDRAYAAN3 | -69.3741 | 32.32 | Caption below annotated orbital image, before Full NAC image | 0 m |
| SLIM | -13.3160 | 25.2510 | Opening image caption | 0 m |
| IM1 | -80.13 | 1.44 | Second image caption: Odysseus came to rest | 0 m |
| IM2 | -84.7906 | 29.1957 | Second image caption: lander on its side in crater | 0 m |
| BLUE_GHOST1 | 18.562 | 61.810 | Second image caption: lander pixel in the middle of the box | 0 m |
| ARTEMIS_CABEUS_B | -83.7630 | -69.9830 | Table A1, PCB01, article p.26 | 0 m |
| ARTEMIS_HAWORTH | -86.7680 | -20.5140 | Table A1, HW01, article p.25 | 0 m |
| ARTEMIS_MALAPERT | -85.9420 | -0.9440 | Table A1, MMA01, article p.25 | 0 m |
| ARTEMIS_MOUTON_PLATEAU | -85.1110 | 26.7100 | Table A1, MMP01, article p.26 | 0 m |
| ARTEMIS_MOUTON | -85.4160 | 31.8510 | Table A1, MMO01, article p.25 | 0 m |
| ARTEMIS_NOBILE_RIM1 | -85.2950 | 36.9170 | Table A1, NR101, article p.26 | 0 m |
| ARTEMIS_NOBILE_RIM2 | -84.0540 | 56.4810 | Table A1, NR201, article p.26 | 0 m |
| ARTEMIS_DE_GERLACHE_RIM2 | -88.3890 | -68.8650 | Table A1, dGR201, article p.25 | 0 m |
| ARTEMIS_SLATER_PLAIN | -87.4780 | 124.5210 | Table A1, SP01, article p.27 | 0 m |
| SHACKLETON_RIM | -89.6866 | -162.81 | Table 2, printed/PDF p.12, first Shackleton S row | 0 m |
| CONNECTING_RIDGE | -89.4632 | -137.49 | Table A2-2 p.58, R01/Site01 | 0 m |
| PEAK_NEAR_SHACKLETON | -88.811 | 123.6901 | Table A2-2 p.58, R07/Site07 | 0 m |
| DE_GERLACHE_RIM1 | -88.6834 | -67.9321 | Table A2-2 p.58, R11/Site11 | 0 m |
| SHOEMAKER_RIM_A | -88.0792 | 11.88866 | Table A2-2 p.57, LM2 | 0 m |
| IM3_REINER_GAMMA | 7.585 | -58.725 | Figure 3 caption; same numeric coordinates appear in Figures 9 and 10 captions. | 0 m |

## Reproduce and limitations

```powershell
python -X utf8 pipeline/verify_task_s_jiyong.py
python -X utf8 -m unittest pipeline.tests.test_task_s_jiyong
# Optional, requires the ignored original 20 m PGDA windows:
python -X utf8 pipeline/check_task_s_rim_profiles.py
python -X utf8 pipeline/verify_ledger.py
```

The coordinate checker is offline and validates the supplied source transcriptions; a human can reopen each recorded URL/table and compare the short coordinate excerpt. Evidence hashes identify exact local bytes (Windows checkout line endings may affect text-file hashes). The two-coordinate rim diagnostic requires NumPy/pyproj and original cached windows whose hashes are recorded. It is not a new mission-safety certification or a blanket terrain audit. Luna's three linked LROC supporting pages redirected to a generic featured-sites page, so those links supply no independently recovered supporting coordinates in this run; the NASA primary artifact table itself was read successfully.

Compared with #76, the exact-transcription conclusion agrees. We additionally retain Blue Ghost's later displayed precision, qualify Chang'e 5 uncertainty wording, and explicitly separate the Shoemaker heuristic from the source's polygon-centre claim. Human SI review remains TO CHECK.

Validation: 33/33 coordinate comparisons passed; 2 arithmetic/wrap tests passed; existing ledger verifier reported 0 failures. A separate Codex review session inspected the critical original PDF pages and alternate-source excerpts, verified 29 retained raw-response hashes, reproduced the coordinate report and all three radial profiles exactly, and found no blocking issue. This is additional AI review, not another team member's human sign-off or a second full 33-source re-reading. Production `web/` files are unchanged.
