# Task S — independent audit of all 33 landing sites (`web/data/sites.json`)

Producer: Minchul Kim. Checker: Soyun Jeong, 2026-11-15. Work by Claude Code; the human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
Data: main `673e250` (web version 37); `sites.json` SHA-256 `bc98c7ce…4b64017`. **No production file was changed.**
- Script: `pipeline/verify_sites_independent_soyun.py` (`fetch`, `coords`, `terrain`, `report`, `table`).
- Evidence (quotes, page references, feature claims): `pipeline/sites_audit_evidence_soyun.json`.
- Results: `docs/sites_full_independent_audit_soyun.json`.
- Ledger: row 1 of `docs/verification_ledger.md`.

## Summary

| Item | Count / value |
|---|---|
| Sites checked | **33 / 33** (all, not a sample) |
| Original coordinate found in the listed source, opened directly | **24** |
| Original coordinate found in the same publication through an alternative copy (listed URL blocked) | **9** (the 9 Artemis region points) |
| Coordinates matching the source | **33 / 33**: all exact decimal matches after sign / longitude conversion |
| Coordinate mismatches / unverified coordinates | **0 / 0** |
| Maximum / median coordinate difference | **0 m / 0 m** (exact; source precision ±0.2 to ±153.8 m, per row below) |
| Geographic feature confirmed (explicit source label + independent evidence) | **19** (18 landers, SHACKLETON_RIM) |
| Geographic feature consistent but approximate (no published boundary; region points, polygon centres, planned target) | **13** |
| Geographic mismatches | **0** in the current catalogue (the **old** SHACKLETON_RIM point R04 is not on the rim; see below) |
| Geographic unresolved | **1**: SHOEMAKER_RIM_A (ambiguous rim placement) |
| Listed URL that could not be opened | 1 URL (Wiley, used by 9 sites): HTTP 403 Cloudflare bot check |
| Second source (NSSDCA artifact table) for the 9 LROC landers | 7 identical; Chang'e 3 and Chang'e 4 differ by 2.2 m and 3.0 m (last digit) |

**Coordinates are fully confirmed (33/33 exact). The geographic result is not 33/33 PASS:**
- 19 confirmed;
- 13 consistent but approximate by nature;
- 1 unresolved.

## Method

All code is new; no producer or earlier-audit script is used (`build_sites.py`, `crosscheck_sites_dongju.py`, site-coordinate and source-link audit tools). The existing audit reports were read only to see what had been covered before.

1. **Sources.**
   - All 15 listed source URLs and one alternative copy were fetched again on 2026-11-15. The fetch times (UTC), sizes and SHA-256 hashes are in the JSON.
   - Text was extracted with a parser written for this audit (HTML) and with `pypdf` (PDF).
2. **Quotes.**
   - Each site's quote is in the evidence file. The script checks that it occurs verbatim in the extracted text (33/33 found).
   - Context quotes are also checked:
     - coordinate frame;
     - column headers;
     - NSSDCA note "d";
     - Table A1 title;
     - ACD-50044 polygon-centre statement.
3. **Conversion.**
   - The script parses the latitude and longitude strings inside each quote itself, handling:
     - hemisphere letters;
     - signs;
     - U+2212;
     - 0–360° E longitudes.
   - It converts to N+ / E+ with longitude in −180…180°. Examples: 340.4884° E → −19.5116°; Gläser 197.19 → −162.81°.
   - It compares the result with `sites.json` as exact decimals.
4. **Distance.**
   - Haversine great-circle distance on the lunar sphere, R = 1,737,400 m (tested against pyproj on that sphere).
   - Each row also gives the source's rounding bound: half a unit of the last published digit in each axis, as a distance.
5. **Geographic features.** These are checked independently of the coordinates.
   - **Data.** For the 15 south-polar feature points, small windows of the **NASA PGDA LOLA DEMs** are read: 20 m DEM ±9 km around each point, and 60 m DEM around each named crater to 1.4 × radius + 3 km. Windows come by HTTP Range, with tiles decoded by this audit's own code (deflate + TIFF predictor 3). Crater centres and diameters come from the **USGS Gazetteer of Planetary Nomenclature**, re-downloaded (9,204 Moon features).
   - **Rim test.** A radial elevation profile runs from the crater centre through the point (±4 km).
     - PASS if the point is within 500 m of the profile's crest, at most 50 m below it, with lower ground toward the centre.
     - UNVERIFIED (ambiguous) if it is within 1 km and 50 m of the crest but fails that test.
     - The rim-crest radius in 36 bearings is reported for context.
   - **Ridge test.** In some direction the ground 1 km away on both sides is ≥ 50 m lower, and the point is higher than ≥ 60% of the ground within 1 km.
   - **Peak test.** The ground is lower 1 km away in every direction, and the highest point within 500 m is ≤ 10 m higher.
   - **Massif, plateau and plain region points.** Evidence: the paper's region grouping; the distance to the USGS feature centre (inside the radius for a *Mons*); descriptive slope and relief.
   - **Landers.** Checked by the source's own labelling: "Lunar Module" rows vs ALSEP / LRRR rows, and LROC's "coordinates for the lander". The NSSDCA artifact table is used as a second source.

## The 33 sites

| # | Site ID | Site name | Listed source URL | Original coordinate quotation | Source lat | Source lon | sites.json lat | sites.json lon | Difference (m) | Coordinate status | Feature type | Feature status | Evidence / remarks |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| 1 | APOLLO11 | Apollo 11 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | “Lunar Module \| 0.67416 \| 23.47314” (table 'The full locations are given below', Apollo 11 block, row 'Lunar Module') | 0.67416 | 23.47314 | 0.67416 | 23.47314 | 0 (exact decimal match; source precision ±0.2 m) | PASS | historical lander (Apollo LM) | PASS | row labelled 'Lunar Module' in the LRO-derived NSSDCA table; LRRR row 22 m away; 158 m from the USGS Statio Tranquillitatis centre |
| 2 | APOLLO12 | Apollo 12 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | “Lunar Module \| -3.0128 \| -23.4219” (same table, Apollo 12 block, row 'Lunar Module') | -3.0128 | -23.4219 | -3.0128 | -23.4219 | 0 (exact decimal match; source precision ±2.1 m) | PASS | historical lander (Apollo LM) | PASS | row labelled 'Lunar Module' in the LRO-derived NSSDCA table; ALSEP row 129 m away |
| 3 | APOLLO14 | Apollo 14 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | “Lunar Module \| -3.64589 \| -17.47194” (same table, Apollo 14 block, row 'Lunar Module') | -3.64589 | -17.47194 | -3.64589 | -17.47194 | 0 (exact decimal match; source precision ±0.2 m) | PASS | historical lander (Apollo LM) | PASS | row labelled 'Lunar Module' in the LRO-derived NSSDCA table; LRRR row 210 m away; ALSEP row 181 m away |
| 4 | APOLLO15 | Apollo 15 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | “Lunar Module \| 26.13239 \| 3.63330” (same table, Apollo 15 block, row 'Lunar Module') | 26.13239 | 3.63330 | 26.13239 | 3.6333 | 0 (exact decimal match; source precision ±0.2 m) | PASS | historical lander (Apollo LM) | PASS | row labelled 'Lunar Module' in the LRO-derived NSSDCA table; LRRR row 134 m away; ALSEP row 105 m away |
| 5 | APOLLO16 | Apollo 16 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | “Lunar Module \| -8.9734 \| 15.5011” (same table, Apollo 16 block, row 'Lunar Module') | -8.9734 | 15.5011 | -8.9734 | 15.5011 | 0 (exact decimal match; source precision ±2.1 m) | PASS | historical lander (Apollo LM) | PASS | row labelled 'Lunar Module' in the LRO-derived NSSDCA table; ALSEP row 107 m away |
| 6 | APOLLO17 | Apollo 17 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | “Lunar Module \| 20.1911 \| 30.7723” (same table, Apollo 17 block, row 'Lunar Module') | 20.1911 | 30.7723 | 20.1911 | 30.7723 | 0 (exact decimal match; source precision ±2.1 m) | PASS | historical lander (Apollo LM) | PASS | row labelled 'Lunar Module' in the LRO-derived NSSDCA table; ALSEP row 197 m away |
| 7 | LUNA16 | Luna 16 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html | “Luna 16 \| Soft Landing \| 20 September 1970 \| 0.5137 S, 56.3638 E” (main table, row 'Luna 16' (green row, note d)) | -0.5137 | 56.3638 | -0.5137 | 56.3638 | 0 (exact decimal match; source precision ±2.1 m) | PASS | historical lander (Luna) | PASS | NSSDCA row 'Soft Landing' with note d (spacecraft imaged on the surface by LROC) |
| 8 | LUNA20 | Luna 20 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html | “Luna 20 \| Soft Landing \| 21 February 1972 \| 3.7863 N, 56.6242 E” (main table, row 'Luna 20' (note d)) | 3.7863 | 56.6242 | 3.7863 | 56.6242 | 0 (exact decimal match; source precision ±2.1 m) | PASS | historical lander (Luna) | PASS | NSSDCA row 'Soft Landing' with note d (spacecraft imaged on the surface by LROC) |
| 9 | LUNA24 | Luna 24 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html | “Luna 24 \| Soft Landing \| 18 August 1976 \| 12.7142 N, 62.2129 E” (main table, row 'Luna 24' (note d)) | 12.7142 | 62.2129 | 12.7142 | 62.2129 | 0 (exact decimal match; source precision ±2.1 m) | PASS | historical lander (Luna) | PASS | NSSDCA row 'Soft Landing' with note d (spacecraft imaged on the surface by LROC) |
| 10 | CHANGE3 | Chang'e 3 | https://lroc.im-ldi.com/images/637 | “derived accurate map coordinates for the lander (44.1214°N, 340.4884°E, -2640 meters elevation)” (post text, paragraph on before/after NAC images) | 44.1214 | -19.5116 | 44.1214 | -19.5116 | 0 (exact decimal match; source precision ±1.9 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives 44.1214, -19.5117 (2.2 m apart, last digit differs) |
| 11 | CHANGE4 | Chang'e 4 | https://lroc.im-ldi.com/images/1168 | “the LROC team refined the lander coordinates to be 45.4562°S, 177.5885 °E, with an uncertainty of 13 meters (95% confidence interval)” (post text, last paragraph) | -45.4562 | 177.5885 | -45.4562 | 177.5885 | 0 (exact decimal match; source precision ±1.9 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives -45.4561, 177.5885 (3.0 m apart, last digit differs) |
| 12 | CHANGE5 | Chang'e 5 | https://lroc.im-ldi.com/images/1172.2020 | “The LROC team computed the coordinates of the lander to be 43.0576° N, 308.0839°E, –2570 m elevation, with an estimated accuracy of plus-or-minus 20 meters” (post text, first paragraph) | 43.0576 | -51.9161 | 43.0576 | -51.9161 | 0 (exact decimal match; source precision ±1.9 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives 43.0576, -51.9161 (same value) |
| 13 | CHANGE6 | Chang'e 6 | https://lroc.im-ldi.com/images/1374 | “The LROC team computed the landing site coordinates as 41.6385°S, 206.0148°E, at -5256 meters elevation relative to the average lunar surface, with an estimated horizontal accuracy of plus-or-minus 30 meters” (post text, paragraph 2) | -41.6385 | -153.9852 | -41.6385 | -153.9852 | 0 (exact decimal match; source precision ±1.9 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives -41.6385, -153.9852 (same value) |
| 14 | CHANDRAYAAN3 | Chandrayaan-3 | https://lroc.im-ldi.com/images/1314 | “The Chandrayaan-3 landing site is located about 600 kilometers from the south pole (69.3741°S, 32.32°E, 532 m elevation)” (image caption) | -69.3741 | 32.32 | -69.3741 | 32.32 | 0 (exact decimal match; source precision ±53.4 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives -69.3741, 32.32 (same value) |
| 15 | SLIM | SLIM | https://lroc.im-ldi.com/images/1358 | “The SLIM lander on the lunar surface (13.3160°S, 25.2510°E, -912 m elevation)” (image caption) | -13.3160 | 25.2510 | -13.316 | 25.251 | 0 (exact decimal match; source precision ±2.1 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives -13.3160, 25.2510 (same value) |
| 16 | IM1 | IM-1 Odysseus | https://lroc.im-ldi.com/images/1360 | “Odysseus came to rest at 80.13°S, 1.44°E, 2579 m elevation” (post text) | -80.13 | 1.44 | -80.13 | 1.44 | 0 (exact decimal match; source precision ±153.8 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives -80.13, 1.44 (same value) |
| 17 | IM2 | IM-2 Athena | https://lroc.im-ldi.com/images/1408 | “ended up on its side within a 20-meter diameter crater (84.7906° S, 29.1957° E)” (image caption) | -84.7906 | 29.1957 | -84.7906 | 29.1957 | 0 (exact decimal match; source precision ±1.5 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; NSSDCA table gives -84.7906, 29.1957 (same value) |
| 18 | BLUE_GHOST1 | Blue Ghost Mission 1 | https://lroc.im-ldi.com/images/1406 | “The Firefly Blue Ghost lander is seen as bright pixel casting a shadow in the middle of the box (18.562°N, 61.810°E, -3650 meters elevation)” (image caption 1 (lander); caption 2 gives LRO's imaging position (19.294°N, 67.956°E), not used) | 18.562 | 61.810 | 18.562 | 61.81 | 0 (exact decimal match; source precision ±20.9 m) | PASS | historical lander | PASS | the LROC post gives the coordinate of the lander itself as identified in NAC images; 4217 m from the USGS Mons Latreille centre; NSSDCA table gives 18.562, 61.810 (same value) |
| 19 | ARTEMIS_CABEUS_B | Peak near Cabeus B (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “PCB01 −83.7630 −69.9830” (Appendix Table A1 (printed p. 26 of 34), region 'Peak Near Cabeus B (PCB)', row PCB01) | -83.7630 | -69.9830 | -83.763 | -69.983 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (peak region) | PASS (approximate) | listed under 'Peak Near Cabeus B (PCB)' in Table A1 (region membership as defined by the paper; NASA region boundaries are not published as coordinates); 72.5 km from the USGS Cabeus B centre (59.62 km across); terrain: slope 3.4°, higher than 62% within 1 km and 70% within 3 km; highest point within 3 km is 421 m higher |
| 20 | ARTEMIS_HAWORTH | Haworth (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “HW01 −86.7680 −20.5140” (Appendix Table A1 (printed p. 25), region 'Haworth (HW)', row HW01) | -86.7680 | -20.5140 | -86.768 | -20.514 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point | PASS (approximate) | listed under 'Haworth (HW)' in Table A1 (region membership as defined by the paper; NASA region boundaries are not published as coordinates); 31.1 km from the USGS Haworth centre (51.42 km across); terrain: slope 4.0°, higher than 95% within 1 km and 98% within 3 km; highest point within 3 km is 3 m higher |
| 21 | ARTEMIS_MALAPERT | Malapert Massif (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “MMA01 −85.9420 −0.9440” (Appendix Table A1 (printed p. 25), region 'Mons Malapert (MMA)', row MMA01) | -85.9420 | -0.9440 | -85.942 | -0.944 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (massif) | PASS (approximate) | listed under 'Mons Malapert (MMA)' in Table A1 (region membership as defined by the paper; NASA region boundaries are not published as coordinates); 1.9 km from the USGS Mons Malapert centre (67.0 km across); terrain: slope 3.3°, higher than 58% within 1 km and 58% within 3 km; highest point within 3 km is 263 m higher |
| 22 | ARTEMIS_MOUTON_PLATEAU | Mons Mouton Plateau (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “MMP01 −85.1110 26.7100” (Appendix Table A1 (printed p. 26), region 'Mons Mouton Plateau (MMP)', row MMP01) | -85.1110 | 26.7100 | -85.111 | 26.71 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (plateau) | PASS (approximate) | listed under 'Mons Mouton Plateau (MMP)' in Table A1 (region membership as defined by the paper; NASA region boundaries are not published as coordinates); 19.4 km from the USGS Mons Mouton centre (130.0 km across); terrain: slope 0.3°, higher than 53% within 1 km and 56% within 3 km; highest point within 3 km is 116 m higher |
| 23 | ARTEMIS_MOUTON | Mons Mouton (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “MMO01 −85.4160 31.8510” (Appendix Table A1 (printed p. 25), region 'Mons Mouton (MMO)', row MMO01) | -85.4160 | 31.8510 | -85.416 | 31.851 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (mountain) | PASS (approximate) | listed under 'Mons Mouton (MMO)' in Table A1 (region membership as defined by the paper; NASA region boundaries are not published as coordinates); 24.8 km from the USGS Mons Mouton centre (130.0 km across); terrain: slope 4.6°, higher than 83% within 1 km and 94% within 3 km; highest point within 3 km is 17 m higher |
| 24 | ARTEMIS_NOBILE_RIM1 | Nobile Rim 1 (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “NR101 −85.2950 36.9170” (Appendix Table A1 (printed p. 26), region 'Nobile Rim 1 (NR1)', row NR101) | -85.2950 | 36.9170 | -85.295 | 36.917 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (crater rim) | PASS (approximate) | 40.60 km from the USGS Nobile centre (radius 39.63 km; rim-crest radius over 36 bearings 26.1–54.6 km); 0 m inward of the radial crest and -0.0 m below it; 1 km toward the centre is 95 m lower |
| 25 | ARTEMIS_NOBILE_RIM2 | Nobile Rim 2 (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “NR201 −84.0540 56.4810” (Appendix Table A1 (printed p. 26), region 'Nobile Rim 2 (NR2)', row NR201) | -84.0540 | 56.4810 | -84.054 | 56.481 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (crater rim) | PASS (approximate) | 38.25 km from the USGS Nobile centre (radius 39.63 km; rim-crest radius over 36 bearings 26.1–54.6 km); 20 m inward of the radial crest and 0.1 m below it; 1 km toward the centre is 285 m lower |
| 26 | ARTEMIS_DE_GERLACHE_RIM2 | de Gerlache Rim 2 (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “dGR201 −88.3890 −68.8650” (Appendix Table A1 (printed p. 25), region 'de Gerlache Rim 2 (dGR2)', row dGR201) | -88.3890 | -68.8650 | -88.389 | -68.865 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (crater rim) | PASS (approximate) | 16.28 km from the USGS de Gerlache centre (radius 16.36 km; rim-crest radius over 36 bearings 14.4–17.4 km); 120 m inward of the radial crest and 0.6 m below it; 1 km toward the centre is 211 m lower |
| 27 | ARTEMIS_SLATER_PLAIN | Slater Plain (region) | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | “SP01 −87.4780 124.5210” (Appendix Table A1 (printed p. 27), region 'Slater Plain (SP)', row SP01) | -87.4780 | 124.5210 | -87.478 | 124.521 | 0 (exact decimal match; source precision ±1.5 m) | PASS (alt. copy) | Artemis III candidate region representative point (plain, informal name) | PASS (approximate) | listed under 'Slater Plain (SP)' in Table A1 (region membership as defined by the paper; NASA region boundaries are not published as coordinates); 23.9 km from the USGS Slater centre (25.12 km across); terrain: slope 3.4°, higher than 77% within 1 km and 89% within 3 km; highest point within 3 km is 39 m higher |
| 28 | SHACKLETON_RIM | Shackleton Rim (S) | https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf | “Shackleton, S -89.6866 197.19 85.5 89.4 66” (Table 2 (printed p. 12; PDF p. 12), South pole, row 'Shackleton, S', first coordinate pair (maximum average illumination at 2 m); the second pair (-89.7815, 204.70) is the longest-solar-visibility point) | -89.6866 | -162.81 | -89.6866 | -162.81 | 0 (exact decimal match; source precision ±1.7 m) | PASS | crater rim (Shackleton) | PASS | 10.83 km from the USGS Shackleton centre (radius 10.46 km; rim-crest radius over 36 bearings 10.0–11.3 km); 0 m inward of the radial crest and -0.0 m below it; 1 km toward the centre is 373 m lower |
| 29 | CONNECTING_RIDGE | Connecting Ridge (DEM region centre, R01) | https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf | “R01 or Site01 Connecting Ridge -89.4632 -137.49” (Appendix A2.1, Table A2-2 Lunar South Pole Features (printed p. 58 of 70)) | -89.4632 | -137.49 | -89.4632 | -137.49 | 0 (exact decimal match; source precision ±2.1 m) | PASS | ridge (DEM region centre) | PASS (approximate) | crest test: in one direction the ground 1 km away on both sides is ≥ 140 m lower; higher than 77% of the ground within 1 km; highest point within 500 m is 12.5 m higher |
| 30 | PEAK_NEAR_SHACKLETON | Peak Near Shackleton (DEM region centre, R07) | https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf | “R07 or Site07 Peak Near Shackleton -88.811 123.6901” (Table A2-2 (printed p. 58)) | -88.811 | 123.6901 | -88.811 | 123.6901 | 0 (exact decimal match; source precision ±15.2 m) | PASS | peak (DEM region centre) | PASS (approximate) | summit test: lower ground 1 km away in every direction (≥ 46 m); highest point within 500 m is 3.3 m higher; higher than 91% within 1 km |
| 31 | DE_GERLACHE_RIM1 | de Gerlache Rim 1 (DEM region centre, R11) | https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf | “R11 or Site11 de Gerlache Rim 1 -88.6834 -67.9321” (Table A2-2 (printed p. 58)) | -88.6834 | -67.9321 | -88.6834 | -67.9321 | 0 (exact decimal match; source precision ±1.5 m) | PASS | crater rim (DEM region centre) | PASS (approximate) | 16.40 km from the USGS de Gerlache centre (radius 16.36 km; rim-crest radius over 36 bearings 14.4–17.4 km); 340 m outward of the radial crest and 5.7 m below it; 1 km toward the centre is 91 m lower |
| 32 | SHOEMAKER_RIM_A | Shoemaker Rim A (DEM region centre, LM2) | https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf | “LM2 Shoemaker Rim A -88.0792 11.88866” (Table A2-2 (printed p. 57)) | -88.0792 | 11.88866 | -88.0792 | 11.88866 | 0 (exact decimal match; source precision ±1.5 m) | PASS | crater rim (DEM region centre) | UNVERIFIED (ambiguous) | 33.58 km from the USGS Shoemaker centre (radius 25.91 km; rim-crest radius over 36 bearings 25.0–36.2 km); 540 m outward of the radial crest and 27.7 m below it; 1 km toward the centre is 3 m lower; within 1 km and 50 m of the crest but fails the strict rim test (offset from the crest at most 500 m, at most 50 m below it, lower toward the centre) |
| 33 | IM3_REINER_GAMMA | IM-3 / Lunar Vertex target | https://www.frontiersin.org/journals/astronomy-and-space-sciences/articles/10.3389/fspas.2022.926018/full | “The LVx landing site (7.585°N, 58.725°W) is indicated by a yellow star on profile #3.” (figure caption (Reiner Gamma profiles figure; LVx landing site marked by a yellow star on profile #3)) | 7.585 | -58.725 | 7.585 | -58.725 | 0 (exact decimal match; source precision ±21.3 m) | PASS | planned landing target inside an albedo feature (Reiner Gamma swirl) | PASS (approximate) | planned target, not a landing; 9.2 km from the USGS Reiner Gamma centre (albedo feature, 73.44 km across); the paper places it in central Reiner Gamma |

Source lat/lon are the converted values (N+, E+, −180…180°).
- "Alt. copy": the coordinate was read from the publisher's published PDF of the same article, held by the ETH Zurich Research Collection, because the listed Wiley URL was blocked.
- "Approximate": a claim without a published boundary to test against; it is not a precise PASS.

## Every mismatch and unresolved case

**Coordinate mismatches: none.** All 33 values equal the source digits exactly.

**Unresolved geographic case: SHOEMAKER_RIM_A.** ACD-50044 LM2, a published DEM-polygon centre named "Shoemaker Rim A".
- Evidence against a rim position:
  - The USGS Gazetteer gives Shoemaker a 51.82 km diameter (radius 25.91 km), and the point is 33.58 km from its centre (1.30 radii).
  - The strict rim test fails: the point is 540 m outward of the radial crest and 27.7 m below it, and the ground 1 km toward the centre is only 3 m lower.
- Evidence for a rim position:
  - On this bearing the PGDA 60 m profile rises from the floor (about −3,900 m) to a broad rim top 28–34 km from the centre (−590 to −705 m), then falls to −2,920 m at 40 km.
  - The point (−619 m) lies on that rim top, near its outer edge.
  - Shoemaker's rim-crest radius varies from 25.0 to 36.2 km over 36 bearings.
- Reading: the point is on the broad rim massif but not on a crest line. It is a polygon centre, not a surveyed rim point.
- **Status: UNVERIFIED (ambiguous), not PASS.** The catalogue already qualifies the name as "(DEM region centre, LM2)".

**Listed source not reachable: Wueller et al. (2026) Wiley URL**, used by all 9 Artemis region points.
- The URL returned HTTP 403 (Cloudflare security check) to the script and in the in-app browser. This was not bypassed.
- The same article was read from its **published-version PDF** in the ETH Zurich Research Collection (doi:10.3929/ethz-c-000797022).
  - The article is CC BY 4.0, doi:10.1029/2025JE009434.
  - The PDF carries the Wiley download stamp.
  - The 9 rows are in Table A1, printed pp. 25–27.
- This is the original publication, not a secondary reference. The listed URL itself is still **not** verified. A team member with browser access should open it once; task J also lists this link.
- **Minus signs in Table A1.** Text extraction returns U+0000 where the minus signs are.
  - The embedded font is StixTwoMathSymbols. Its ToUnicode map starts at code 1 = U+00B7, 2 = U+00D7, 3 = U+2217. That is the TeX cmsy layout, in which code 0 is the minus sign.
  - Each code-0 glyph sits immediately before a number.
  - Every latitude carries one, as expected for 83–88° S.
  - Longitudes carry one exactly where `sites.json` has a west longitude. Reading those as east would move PCB01 by 355 km, dGR201 by 91 km, HW01 by 69 km and MMA01 by 4.1 km.
  - Reading any latitude as north would move a point by more than 5,000 km.

**Second-source differences** (informational; the listed LROC values match `sites.json` exactly):
- Chang'e 3: the NSSDCA table gives 19.5117° W against LROC's 340.4884° E (−19.5116°), 2.2 m apart.
- Chang'e 4: NSSDCA gives 45.4561° S against LROC's refined 45.4562° S, 3.0 m apart.
- Both are below LROC's stated accuracy (±13 m for Chang'e 4).

## Special findings

**SHACKLETON_RIM.**
- **Source.** Gläser et al. Table 2, the first "Shackleton, S" pair, i.e. the maximum-average-illumination point at 2 m.
- **The current point is on the rim:**
  - 10.83 km from the USGS centre (radius 10.46 km; rim-crest radius 10.0–11.3 km over 36 bearings);
  - exactly on the radial crest (0 m offset);
  - higher than 99.5% of the ground within 1 km;
  - 1 km toward the centre the ground is 373 m lower.
- **The old point is not on the rim.** The old catalogue point was the ACD-50044 R04 "Shackleton Rim" polygon centre (−89.7668, −171.87), used before commit `00bb8a5`. It lies 1,820 m inside the crest and 934 m below it, on the inner wall at a 31.6° slope. The earlier correction was right.
- Table 2's second Shackleton pair (−89.7815, 204.70) is the longest-solar-visibility point. The catalogue uses the first pair, as its note says.

**Rims.**
- ARTEMIS_NOBILE_RIM1 (NR101), ARTEMIS_NOBILE_RIM2 (NR201) and ARTEMIS_DE_GERLACHE_RIM2 (dGR201) are on their crater's radial crest: 0, 20 and 120 m from it, at most 0.6 m below.
- DE_GERLACHE_RIM1 (polygon centre R11) is 340 m outward of the crest and 5.7 m below it, so it is on the rim, approximately.
- Nobile is irregular (rim-crest radius 26.1–54.6 km over 36 bearings), so the rim test follows the actual profile, not the Gazetteer radius.

**Ridge and peak** (ACD-50044 polygon centres).
- **CONNECTING_RIDGE passes the crest test.** Across the ridge, the ground 1 km away is ≥ 140 m lower on both sides; the highest ground within 500 m is 12.5 m higher.
- **PEAK_NEAR_SHACKLETON passes the summit test.** The ground 1 km away is ≥ 46 m lower in every direction; the highest point within 500 m is 3.3 m higher.
- Both are DEM-polygon centres, as their names say. Neither is claimed as a surveyed summit or crest point.

**Artemis regions.**
- All 9 are research candidate landing sites from Wueller et al.: PCB01, HW01, MMA01, MMP01, MMO01, NR101, NR201, dGR201, SP01. None is a NASA-selected touchdown point or a region centre.
- NASA has not published the regions as coordinate boundaries. Region membership therefore rests on the paper's Table A1 grouping, and the status is "approximate".

| Point | Finding |
|---|---|
| **Peak near Cabeus B** (PCB01) | **Not at a summit**: 421 m below the highest ground within 3 km, higher than only 62% within 1 km; 72.5 km from the USGS Cabeus B centre ("near"). |
| **Malapert** (MMA01) | 1.9 km from the USGS Mons Malapert centre (radius 33.5 km), on the massif. The catalogue name "Malapert Massif" is NASA's region name; the paper writes "Mons Malapert". |
| **Mons Mouton Plateau** (MMP01) | Slope 0.3°, local relief < 70 m within 1 km (plateau-like), inside Mons Mouton. |
| **Mons Mouton** (MMO01) | A local high (lower ground in every direction), inside Mons Mouton. |
| **Haworth** (HW01) | A local high 31.1 km from the Haworth centre (radius 25.7 km), outside the crater. |
| **Slater Plain** (SP01) | A gentle rise (slope 3.4°) 23.9 km from the Slater centre. "Slater Plain" is an informal region name with no USGS feature to test against. |

**IM3_REINER_GAMMA.**
- A planned Lunar Vertex target taken from the paper, not an observed landing.
- It is 9.2 km from the USGS Reiner Gamma centre (an albedo feature 73 km across), inside the swirl as the paper describes.

**Landers.**
- Apollo: "Lunar Module" rows are separate from the ALSEP and LRRR rows, 22–210 m away.
- Luna 16 / 20 / 24: NSSDCA note d (imaged on the surface by LROC).
- The 9 others: LROC's coordinates of the lander itself.
  - BLUE_GHOST1 uses the lander caption (18.562° N, 61.810° E), not LRO's own position given in the second caption (19.294° N, 67.956° E).
  - IM2 is the resting position on its side, not the target.
- Coarse source precision:
  - IM1 has only 2 decimals (rounding bound ±154 m).
  - CHANDRAYAAN3 has 2 decimals in longitude (±53 m).

## Proposed corrections and downstream impact

**No coordinate correction is proposed.** All 33 values equal their sources. Nothing downstream needs recomputing:
- horizons;
- metrics;
- local 1 km and 250 m grids;
- uncertainty, relay and date-slip data;
- windows, monthly data and maps.

Optional, label-only suggestions for the producer and integrator (no coordinate change):
- SHOEMAKER_RIM_A could note that its polygon centre lies on the broad rim massif, 0.5 km outside the local crest.
- ARTEMIS_CABEUS_B could note that PCB01 is not the summit.

Even a label change alters `site_sha256` in provenance records that hash the whole site object (see `docs/site_coordinate_audit.md`). It is therefore the integrator's decision.

## Limits

- **Listed Wiley URL.** It was not opened. Those 9 coordinates come from the same article's published PDF in a university repository.
- **Geographic tests.** They use LOLA / PGDA terrain and USGS centres.
  - They show whether a point lies on a rim, ridge or peak in the DEM; they are not field truth.
  - The thresholds (500 m, 50 m, 1 km) are this audit's choice, stated above.
- **Artemis region membership.** It relies on the paper's own grouping, because NASA's boundaries are not public as coordinates.
- **Lander positions.** These are LROC's published measurements; their stated accuracies (±13–30 m) were not re-derived from images.
- **Coordinate frames.** USGS Gazetteer centres are given to 2 decimals and called "planetographic" (on the spherical Moon this equals planetocentric). The DEMs are MOON_ME DE421. These differences are far below the 100 m scale of the feature tests.
