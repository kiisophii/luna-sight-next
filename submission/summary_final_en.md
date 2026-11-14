# Project Summary — final draft (Luna Sight, Team Ginkgo Orbit, challenge 04)

> **팀용 (한국어):** Space Apps 공식 'Summary' 칸(150–200단어)에 붙여 넣을 최종안이다. 단어 수는 BEGIN/END 표시 줄 사이만 센다(공백 기준).
> 숫자 출처(파일:줄)는 본문에 넣지 않고 맨 아래 표에만 적었다. 내일 팀이 같이 읽고 확정한다.
> 초안(`summary_en.md` B/C)에서 바뀐 점: 1 km 비교를 "남극 38.7 pp vs 극지 밖 6.7 pp"(중앙값)로 바꿨고, 10 km 안 일조 IQR(17.2 pp vs 0.4 pp)을 넣었다. 섀클턴 8.7 % → 84.8 % 문장은 뺐다(옛 값은 2시간 간격, 새 값은 1시간 간격이라 요약 칸에는 맞지 않음; 슬라이드 4에는 "약"으로 남김).

<!-- BEGIN -->
Luna Sight — Lunar Landing Site Navigator helps mission planners, students and the public compare Moon landing sites and dates with two questions: will a lander see the Sun for power, and the Earth for a direct radio link? For 33 sites with published coordinates, from Apollo to the Artemis III candidate regions, it checks every hour of 2026–2030 using NASA LOLA terrain (down to 5 m near the south pole) and JPL Sun and Earth positions.

Near the south pole, moving 1 km can change the time with both Sun and Earth in view by up to 38.7 percentage points at a typical site; away from the poles, by only 6.7. Within 10 km, the typical spread in sunlight is 17.2 points near the pole but only 0.4 elsewhere: at the pole the spot decides, elsewhere the date. At 26 of 33 sites, a two-week delay can turn the first two weeks into night. A single 15 m relay tower lifts Cabeus B's Earth link from 30% to 86% of the time. Results agree with NASA's south-polar illumination maps to 1.7 points on average.

The ideas are the team's; AI tools helped write code and check results.
<!-- END -->

**Words: 198**

> 한국어 요약: 이 도구는 "착륙선이 해를 보나(전력), 지구를 보나(직접 통신)" 두 질문으로 33개 착륙지와 날짜를 2026–2030년 매시간 비교한다. 남극에선 1 km만 옮겨도 해·지구 동시 시간이 중앙값 사이트 기준 최대 38.7 pp 달라지지만 극지 밖에선 6.7 pp뿐이다. 10 km 안 일조의 가운데 절반 폭은 남극 17.2 pp, 그 밖 0.4 pp — 극지에선 지점이, 그 밖에선 날짜가 결과를 정한다. 33곳 중 26곳에서 2주 지연이 첫 2주를 밤으로 바꿀 수 있다. 15 m 중계탑 하나로 카베우스 B 지구 연결 30 % → 86 %. NASA 극지 조명 지도와 평균 1.7 pp 차이. 아이디어는 팀, AI는 코드 작성과 검증을 도움.

Word count (run before pasting):
```bash
python -c "import re;t=open('submission/summary_final_en.md',encoding='utf-8').read();print(len(re.search(r'^<!-- BEGIN -->$(.*?)^<!-- END -->$',t,re.S|re.M).group(1).split()))"
```

## Numbers used → source (main `64e3bee`, web version 24)

| # | Number as used | Source (file:line) | Second check (independent) |
|---|---|---|---|
| N1 | 33 sites | `docs/site_coordinate_audit.md:24` (all 33 coordinate pairs match their source) | `web/data/sites.json` has 33 records |
| N2 | every hour of 2026–2030 (43,824 h) | `docs/korea_links.md:3` | `docs/location_sensitivity.md:5` (43,824 hourly samples, 2026–2030) |
| N5 | terrain down to 5 m near the south pole | `docs/location_sensitivity.md:29` (ground DEM 5 m); `data/DATASETS.md:53` (PGDA LOLA 5 m) | `web/data/local/SHACKLETON_RIM.json`: minimum ground resolution 5 m |
| A3 | Artemis III candidate regions | `docs/sites.md:17` (NASA 2024-10-28 candidate-region list) | — |
| N7 | 1 km contrast in Sun + Earth time: 38.7 pp polar vs 6.7 pp elsewhere (medians 38.65 / 6.70; largest neighbouring pair per site) | `docs/location_sensitivity.md:15–16` (table), `:19` (sentence) | recomputed from all 33 `web/data/local/<ID>.json` grids (16 + 16 sites): 38.65 / 6.70 |
| N8 | sunlight spread within 10 km (IQR): 17.2 pp polar vs 0.4 pp elsewhere (medians 17.16 / 0.40) | `docs/location_sensitivity.md:15–16`, `:19` | recomputed from the same grids (10 km circle, linear quartiles): 17.16 / 0.40 |
| N9 | 26 of 33 sites; two-week delay turns the first two weeks into night; up to 336 h | `docs/date_slip.md:9` | `docs/date_slip_summary.json` (+14 d worst change of longest darkness): 26 sites ≥ 300 h, max 336 h |
| N11 | Cabeus B Earth link 30% → 86% (29.64% → 85.73%), one 15 m tower, 2026–2030 | `docs/relay_impact.md:20` | `docs/card13_relay_report.md` states 85.7 |
| N14 | PGDA: 1.7 points on average (MAE 1.66 pp), r = 0.985, 240 points | `docs/VALIDATION.md:60` | `web/data/validation.json`: 1.658 pp, r 0.9846, 240 points |

Both checks are automated in `python pipeline/verify_submission_text.py` (result: FAILURES: 0); each row was also read by hand against the file.
