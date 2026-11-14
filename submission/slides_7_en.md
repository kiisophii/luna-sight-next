# Backup deck — 7 slides (Luna Sight, Team Ginkgo Orbit)

> **팀용 (한국어):** 영상이 안 될 때 쓰는 예비 슬라이드 내용(최대 7장 — **8장 이상이면 탈락**, 표지·마지막 장 포함). 전부 영어. 그림은 우리 앱 스크린숏만 쓴다(AI 이미지 금지, NASA 로고 금지).
> 각 장의 "Numbers" 줄은 발표자용이다(슬라이드에 꼭 넣을 필요는 없음). 출처는 맨 아래 표에 file:line으로 적었다. 7장의 "Next"는 팀이 직접 쓴다(AI가 쓰지 않음).

---

## Slide 1 — Luna Sight — Lunar Landing Site Navigator

- Can a lander see the Sun (for power) and the Earth (for a direct radio link)?
- 33 Moon landing sites, every hour of 2026–2030
- Team Ginkgo Orbit · NASA Space Apps Challenge 2026 · Seoul
- Live demo: kiisophii.github.io/lunar-landing-site-navigator

**Numbers:** 33 sites [N1]; 43,824 hours = every hour of 2026–2030 [N2].
**Visual:** 3D Moon from the app, south-pole view.

## Slide 2 — The problem: the horizon decides

- Near the south pole, the Sun and Earth stay low and skim the horizon
- Nearby ridges and crater rims can hide them from a lander
- At Malapert, the Earth is never visible from one spot and always visible from a spot 1 km away
- Planners need hour-by-hour Sun and Earth visibility for each site and date

**Numbers:** Malapert Earth visibility 0% → 100% between two grid points 1 km apart (the most extreme pair in the region, not a typical move) [N3].
**Visual:** horizon panorama of Cabeus B with the Sun and Earth tracks.

## Slide 3 — What Luna Sight does

- 33 sites with published coordinates, from Apollo to the Artemis III candidate regions
- Compare three sites side by side, scan landing dates, test your own point, explore a 3D Moon
- Terrain from NASA LOLA (down to 5 m near the south pole) + Sun and Earth positions from JPL
- A comparison tool, not a landing-safety verdict

**Numbers:** 33 sites; all 33 stored coordinates match their published source (0.000 m) [N1, N4]; 5 m terrain near the south pole [N5].
**Visual:** three comparison cards + the period table.

## Slide 4 — Where the choice matters

- Malapert: two spots 1 km apart see Sun and Earth together 0% vs 45% of the time
- Near the south pole, a 1 km move can change Sun + Earth time by up to 38.7 percentage points at a typical site; elsewhere only 6.7
- Within 10 km, the typical spread in sunlight is 17.2 points near the pole but only 0.4 elsewhere: at the pole the spot decides, elsewhere the date
- At 26 of 33 sites, a two-week delay can turn the first two weeks into night (up to 336 more hours of darkness)

**Numbers:** 0% → 45.11% [N6]; 38.65 / 6.70 pp median largest 1 km contrast, 17.16 / 0.40 pp median sunlight IQR [N7, N8]; 26 of 33 sites, up to 336 h [N9].
**Visual:** 1 km local map (Malapert, "Both") + the date-slip table.
*Optional speaker note (not a bullet):* moving the Shackleton point to a published rim location changes sunlight from about 9% to 85% — a different point, not a correction [N10].

## Slide 5 — Restoring the Earth link

- One 15 m relay tower lifts the Earth link at Cabeus B from 30% to 86% of the time (2026–2030)
- Of 7 sites that see the Earth less than half the time, 3 pass 50% with a single tower
- Korea: the Yeoju KDSA antenna adds hours no NASA DSN antenna covers (123 h in 5 years at a site that always sees the Earth)
- Geometry only: no link budget, power or scheduling model

**Numbers:** 29.64% → 85.73% at 15 m [N11]; 7 sites, 3 reach ≥ 50% [N12]; 123 h in 5 years, 0.3–0.4% of Earth-visible hours [N13].
**Visual:** relay panel with the link timeline; Korea links panel.

## Slide 6 — Validated, not guessed

- NASA south-polar illumination maps (PGDA): sunlight differs by 1.7 points on average (r = 0.985, 240 random points)
- Sun and Earth directions match NASA JPL Horizons within 0.0005° (over 37,000 comparisons); Apollo 11–17 Sun elevation at landing within 0.05°
- 5,520 numbers read from the live website: 0 mismatches with the data
- Limits: Earth counts only when its centre is visible (stricter than PGDA); no PGDA reference north of 75° S

**Numbers:** MAE 1.66 pp, r 0.985, 240 points [N14]; within 0.0005°, over 37,000 comparisons (largest single difference 0.00044°, the app's float32 file) [N15]; Apollo 0.05° [N16]; 5,520 values, 0 mismatches [N17].
**Visual:** scatter plot ours vs PGDA (from `web/data/validation.json`).

## Slide 7 — Data, open source and AI use

- NASA data: LOLA terrain and PGDA illumination maps; JPL / NAIF ephemerides; full list in `data/DATASETS.md` (team to confirm the final list)
- Open source (Apache-2.0): github.com/kiisophii/lunar-landing-site-navigator
- Ideas and decisions by the team; AI tools helped write code and check results (log: `docs/SI_USAGE.md`)
- Next: *[TEAM TO WRITE — future plans must be the team's own idea]*

**Numbers:** none.
**Visual:** text slide with links.

---

## Numbers used → source (main `64e3bee`, web version 24)

| # | Number as used | Source (file:line) | Second check (independent) |
|---|---|---|---|
| N1 | 33 sites | `docs/site_coordinate_audit.md:24` (all 33 coordinate pairs match their source) | `web/data/sites.json` has 33 records |
| N2 | every hour of 2026–2030 (43,824 h) | `docs/korea_links.md:3` | `docs/location_sensitivity.md:5` (43,824 hourly samples, 2026–2030) |
| N3 | Malapert Earth 0% → 100%, 1 km apart | `docs/location_sensitivity.md:36` | recomputed from `web/data/local/ARTEMIS_MALAPERT.json` nodes (−2,−2) and (−2,−1) |
| N4 | coordinates match source, 0.000 m | `docs/site_coordinate_audit.md:24` | — |
| N5 | terrain down to 5 m near the south pole | `docs/location_sensitivity.md:29` (ground DEM 5 m); `data/DATASETS.md:53` (PGDA LOLA 5 m) | `web/data/local/SHACKLETON_RIM.json`: minimum ground resolution 5 m |
| N6 | Malapert Sun + Earth together 0% vs 45% (45.11%) | `docs/location_sensitivity.md:37` | recomputed from `web/data/local/ARTEMIS_MALAPERT.json` |
| N7 | 1 km contrast in Sun + Earth time: 38.7 pp polar vs 6.7 pp elsewhere (medians 38.65 / 6.70; largest neighbouring pair per site) | `docs/location_sensitivity.md:15–16` (table), `:19` (sentence) | recomputed from all 33 `web/data/local/<ID>.json` grids (16 + 16 sites): 38.65 / 6.70 |
| N8 | sunlight spread within 10 km (IQR): 17.2 pp polar vs 0.4 pp elsewhere (medians 17.16 / 0.40) | `docs/location_sensitivity.md:15–16`, `:19` | recomputed from the same grids (10 km circle, linear quartiles): 17.16 / 0.40 |
| N9 | 26 of 33 sites; two-week delay turns the first two weeks into night; up to 336 h | `docs/date_slip.md:9` | `docs/date_slip_summary.json` (+14 d worst change of longest darkness): 26 sites ≥ 300 h, max 336 h |
| N10 | Shackleton point: about 9% → 85% sunlight (8.7% old point, 2 h step; 84.8% new point, hourly) | old: `docs/custom_horizon_validation.json:455` (step `:16`); new: `docs/VALIDATION.md:24` (Sun 0.848) | `web/data/metrics/SHACKLETON_RIM.json` sun_frac 0.8483; context `docs/shackleton_handoff.md:18` (different published point, not an error fix) |
| N11 | Cabeus B Earth link 30% → 86% (29.64% → 85.73%), one 15 m tower, 2026–2030 | `docs/relay_impact.md:20` | `docs/card13_relay_report.md` states 85.7 |
| N12 | 7 sites below 50% direct, 3 reach ≥ 50% with one tower | `docs/relay_impact.md:9` | counted from the 7 rows of the single-tower table (`docs/relay_impact.md:18–24`) |
| N13 | Yeoju KDSA only: 123 h in 5 years; 0.3–0.4% of Earth-visible hours | `docs/korea_links.md:47` (123 h), `:46` (0.3–0.4 %) | table rows `docs/korea_links.md:11–43` (KDSA only = 123 h at always-Earth-facing sites) |
| N14 | PGDA: 1.7 points on average (MAE 1.66 pp), r = 0.985, 240 points | `docs/VALIDATION.md:19` | `web/data/validation.json`: 1.658 pp, r 0.9846, 240 points |
| N15 | JPL Horizons within 0.0005°, over 37,000 comparisons | `docs/VALIDATION.md:46` (team paragraph) | rows `docs/VALIDATION.md:12–14`: 0.000016° / 0.00044° (web float32), 0.000034°, 0.000041°; 1,452 + 1,452 + 34,296 = 37,200 comparisons |
| N16 | Apollo 11–17 Sun elevation 0.05° | `docs/hindcast.md:7` | `docs/VALIDATION.md:32` (row 21) |
| N17 | 5,520 website numbers, 0 mismatches | `docs/ui_data_audit.md:17` | `docs/ui_audit/findings.json` (checks = 5520) |
| LIC | Apache-2.0 | `LICENSE:3` | — |

Both checks are automated in `python pipeline/verify_submission_text.py` (result: FAILURES: 0); each row was also read by hand against the file.
