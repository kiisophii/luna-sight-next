# Live site QA — first screen, site detail, About (Soyun Jeong, 2026-11-15)

Checker: Soyun Jeong. The QA was operated by Claude Code, so it is **not a human sign-off**; the SI cells are `TO CHECK`.

| | |
|---|---|
| Target | https://kiisophii.github.io/lunar-landing-site-navigator/ |
| Deployed version | `version.json` = `{"v": 40}`, the same as main `aa1e1fb`, so the latest main is live. Loaded with a cache-busting query (`?qa=1115b`) |
| Browser | Chromium-based browser pane in the Claude desktop app, with viewport emulation |
| Viewports | 390×844 (main session), 360×800, 768×1024, 1280×800, 1920×1080 |

**How the checks were made.** The browser pane was hidden for most of the session, so screenshots were unreliable: they often timed out or rendered partially. Therefore:
- Layout, overflow, touch-target and label sizes were **measured from the DOM**: `getBoundingClientRect`, `scrollWidth`, computed style, and same-origin iframes at each width.
- Pixel-level visual review was **not** completed and is left for a human.

**Not tested:**
- Safari (iOS and macOS), Firefox, Samsung Internet;
- real phones and tablets: touch, pinch and rotation;
- landscape orientation;
- slow networks.

A manual checklist is given at the end.

## A. First screen

| Check | Result |
|---|---|
| Loads with no console errors | PASS: 0 console errors |
| 3D Moon renders | PASS: WebGL canvas present. The globe was black for the first few seconds at 390 px while textures loaded, then the Moon appeared |
| Horizontal page scroll | **None** at all 5 widths (`scrollWidth` = viewport width). Wide content (comparison table, timeline) scrolls inside its own container |
| KR / EN toggle | Works; 44 × 44 px; `lang` attribute switches. Korean page: no untranslated English phrases detected outside proper names |
| Candidate list | 33 sites (21 behind 'Show 21 more'). Long names are ellipsised at ≤ 390 px, e.g. 'Shackleton Rim' 104 → 88 px. Cosmetic |
| Selectors | Local-map and horizon site selectors list 33 sites each |
| Mobile touch targets | Unpin 15 × 19 px and info 19 × 18 px buttons are too small → **#90**. 3D-globe site labels are 21 px tall (map labels; acceptable) |

## B. Site detail (decision brief and detailed comparison)

### Displayed values vs an independent recomputation — all 33 sites

- Each site was opened in its own brief (period 2026-11-15, 29.5 d, selected hour 7639).
- The coordinates and these values were read from the live page: Sunlight %, Direct-to-Earth %, Sun+Earth %, longest shadow, KDSA hours, any-station hours, sunlit hours.
- They were then recomputed with own code from `ephem.bin`, `horizon/`, `sites.json` and `stations.json`, using the `core.js` definitions (the code is the Z1 checker of PR #86).

**Result: 33 / 33 sites, 0 mismatches.** For example, Shackleton Rim shows 100 % / 44 % / 44 %, 0 h, KDSA 152 h, any station 312 h, 708 h sunlit; the recomputation is identical.

The three pinned sites in the comparison also match: Shackleton Rim, Haworth and Apollo 17 for Sunlight, Direct-to-Earth, Sun+Earth, longest shadow (0 h / 53 h = 2.2 d / 370 h = 15.4 d), KDSA (152 / 178 / 288 h), DSN (312 / 385 / 695 h), and the sunlit / Earth states at the selected hour.

| Site | Coords shown | Sun % | Earth % | Both % | Longest shadow | KDSA h | Any station h | Sunlit h |
|---|---|---|---|---|---|---|---|---|
| APOLLO11 | 0.6742, 23.4731 | 50 | 100 | 50 | 14.7 d | 288 | 695 | 354 |
| APOLLO12 | -3.0128, -23.4219 | 50 | 100 | 50 | 10.7 d | 288 | 695 | 356 |
| APOLLO14 | -3.6459, -17.4719 | 49 | 100 | 49 | 11.3 d | 288 | 695 | 349 |
| APOLLO15 | 26.1324, 3.6333 | 47 | 100 | 47 | 13.1 d | 288 | 695 | 333 |
| APOLLO16 | -8.9734, 15.5011 | 50 | 100 | 50 | 13.9 d | 288 | 695 | 354 |
| APOLLO17 | 20.1911, 30.7723 | 48 | 100 | 48 | 15.4 d | 288 | 695 | 338 |
| LUNA16 | -0.5137, 56.3638 | 49 | 100 | 49 | 15.0 d | 288 | 695 | 349 |
| LUNA20 | 3.7863, 56.6242 | 48 | 100 | 48 | 15.4 d | 288 | 695 | 338 |
| LUNA24 | 12.7142, 62.2129 | 49 | 100 | 49 | 15.0 d | 288 | 695 | 349 |
| CHANGE3 | 44.1214, -19.5116 | 49 | 100 | 49 | 11.2 d | 288 | 695 | 350 |
| CHANGE4 | -45.4562, 177.5885 | 50 | 0 | 0 | 14.8 d | 0 | 0 | 353 |
| CHANGE5 | 43.0576, -51.9161 | 49 | 100 | 49 | 8.5 d | 288 | 695 | 350 |
| CHANGE6 | -41.6385, -153.9852 | 50 | 0 | 0 | 14.7 d | 0 | 0 | 355 |
| CHANDRAYAAN3 | -69.3741, 32.3200 | 50 | 100 | 50 | 14.8 d | 288 | 695 | 353 |
| SLIM | -13.3160, 25.2510 | 48 | 100 | 48 | 14.9 d | 288 | 695 | 340 |
| IM1 | -80.1300, 1.4400 | 43 | 100 | 43 | 12.8 d | 288 | 695 | 303 |
| IM2 | -84.7906, 29.1957 | 53 | 82 | 53 | 13.6 d | 250 | 576 | 374 |
| BLUE_GHOST1 | 18.5620, 61.8100 | 49 | 100 | 49 | 15.0 d | 288 | 695 | 349 |
| ARTEMIS_CABEUS_B | -83.7630, -69.9830 | 47 | 23 | 0 | 7.0 d | 82 | 164 | 335 |
| ARTEMIS_HAWORTH | -86.7680, -20.5140 | 82 | 55 | 49 | 2.2 d | 178 | 385 | 582 |
| ARTEMIS_MALAPERT | -85.9420, -0.9440 | 48 | 100 | 48 | 12.9 d | 288 | 695 | 340 |
| ARTEMIS_MOUTON_PLATEAU | -85.1110, 26.7100 | 47 | 54 | 46 | 14.4 d | 177 | 380 | 333 |
| ARTEMIS_MOUTON | -85.4160, 31.8510 | 100 | 56 | 56 | 0 h | 180 | 393 | 708 |
| ARTEMIS_NOBILE_RIM1 | -85.2950, 36.9170 | 100 | 68 | 68 | 0 h | 216 | 478 | 708 |
| ARTEMIS_NOBILE_RIM2 | -84.0540, 56.4810 | 49 | 80 | 49 | 14.9 d | 243 | 558 | 350 |
| ARTEMIS_DE_GERLACHE_RIM2 | -88.3890, -68.8650 | 88 | 50 | 44 | 3.4 d | 164 | 354 | 625 |
| ARTEMIS_SLATER_PLAIN | -87.4780, 124.5210 | 62 | 32 | 15 | 11.1 d | 116 | 228 | 442 |
| SHACKLETON_RIM | -89.6866, -162.8100 | 100 | 44 | 44 | 0 h | 152 | 312 | 708 |
| CONNECTING_RIDGE | -89.4632, -137.4900 | 78 | 37 | 23 | 6.4 d | 126 | 259 | 554 |
| PEAK_NEAR_SHACKLETON | -88.8110, 123.6901 | 100 | 50 | 50 | 0 h | 165 | 351 | 708 |
| DE_GERLACHE_RIM1 | -88.6834, -67.9321 | 81 | 51 | 51 | 5.5 d | 175 | 361 | 577 |
| SHOEMAKER_RIM_A | -88.0792, 11.8887 | 47 | 37 | 30 | 10.2 d | 137 | 263 | 335 |
| IM3_REINER_GAMMA | 7.5850, -58.7250 | 49 | 100 | 49 | 7.9 d | 288 | 695 | 350 |

- For each site, every displayed value equals the recomputed value after the app's rounding: whole percent, d = h / 24 to one decimal.
- **Date change → timeline link:** changing the landing date to 2027-03-01 updated:
  - the period;
  - the slider range (10176–10883 = the new 708-hour window);
  - the selected time, the URL `d`/`t`, and every value.

  Recomputed for the new period: 73 / 43 / 42 %, 2.0 d, KDSA 145 h. Identical.

### Other detail checks

| Check | Result |
|---|---|
| No-data guidance | Non-polar sites show 'This site vs NASA PGDA: no data'. True (PGDA covers the poles), but it could say 'outside PGDA coverage'; not filed |
| Far-side sites (CHANGE4/6) | Earth 0 %, links 0 h, shown correctly. The status reads 'no Earth · no change in data to rise' (EN) and the Korean equivalent with '남음' — same root as existing **#84**, so not filed again |
| Map / graph overlap | No overlap between visible charts, maps and headings at 360 and 768 px. The only overlaps found were inside closed `<details>`, i.e. not displayed |
| Graph readability on phones | Comparison-timeline labels render at 5.5 px (phones) and 6.5 px (tablet) → **#91** |
| Scientific wording | 'Sun + Earth together' subtitle says '… h with power and link together' / '전력과 교신을 함께 쓰는 시간' → **#88** (Major). KDSA 'can receive' / '수신 가능' / '교신' → **#89** (Minor). Elsewhere the brief states 'link = geometric visibility (not radio performance)' and the About page defines both terms correctly |

## C. About

| Check | Result |
|---|---|
| Goal, method, definitions, limits | Present: 'A comparison tool, not a "best site" picker'. Definitions match `core.js` (disc ≥ 50 %, Earth centre, 2 m, hourly). 'Example verdict thresholds … not mission requirements' |
| NASA data sources | C1–C15 list with DOIs (PGDA LOLA, LDEM, SLDEM2015, NAIF, LROC, NSSDCA, ACD-50044, …) |
| Numbers vs the submission summary | MAE 1.66 pp, r 0.985 (240 points) matches `submission/summary_final_en.md` (N14) |
| External links | 8 / 8 return HTTP 200 (PGDA product 69, the DOI, news and NASA pages, GitHub) |
| Layout at 390 px | No element wider than the viewport |
| Korean / English | Both rendered; no untranslated English found |

## D. Issues

| # | Page | Severity | Title |
|---|---|---|---|
| [#88](https://github.com/kiisophii/lunar-landing-site-navigator/issues/88) | Brief | Major | 'Sun + Earth together' subtitle says 'with power and link together' |
| [#89](https://github.com/kiisophii/lunar-landing-site-navigator/issues/89) | Brief, compare, About | Minor | KDSA 'can receive' / '수신 가능' / '교신' implies radio reception |
| [#90](https://github.com/kiisophii/lunar-landing-site-navigator/issues/90) | Compare, brief | Minor | Unpin and info buttons are 15–19 px touch targets |
| [#91](https://github.com/kiisophii/lunar-landing-site-navigator/issues/91) | Compare | Minor | Timeline labels 5.5 px on phones |

- **Duplicates seen but not filed:** #84 (Korean 'no change … 남음'; reproduced on v40; the English text has the same awkward form).
- No Critical issue was found.
- No code or design was changed; all suggested fixes are wording or size changes for the team to decide.

## Manual checklist (Soyun, on real devices)

- [ ] iPhone Safari (portrait and landscape): first load, 3D Moon appears, pinch-zoom and drag on the globe, page does not scroll sideways.
- [ ] Android Chrome / Samsung Internet: same; KR/EN toggle; date picker opens and changes the period.
- [ ] Tablet (iPad or Android, 768 px class): candidate list, comparison table scroll, timeline readability (#91).
- [ ] Desktop Firefox and Safari at 1280 and 1920: first screen, brief, About links.
- [ ] Tap the unpin '×' and 'i' buttons with a finger (#90).
- [ ] Visual check of the cards for clipped text in Korean at 360 px (the DOM measurement found no clipping except ellipsised list names).
- [ ] Read the brief once in Korean for wording that overstates power or communication (#88, #89).
