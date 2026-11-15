# 일요일 아침 할 일 — 온 사람부터 위에서 하나씩 가져가기

> 일어나자마자 시작용. **오래 걸려도 전부(샘플 말고 전체) 다시 계산**하는 게 목표. 계산 걸어 두고 기다리는 동안 아래 칸 하나 더 가져가기.
> 파일: `docs/morning_tasks_1115.md` (main). 가져갈 때 단톡에 "A 제가 할게요" 한 줄. 끝나면 PR → 수아가 합침. 각자 AI에 먼저:
> `Pull the latest main, read docs/verification_ledger.md and docs/data_contract.md. I am <이름>, task <글자>.`
> **규칙:** 자기가 만든 데이터는 자기가 검증 못 함(다른 사람 것만). 결과 숫자는 그대로 적고, 안 맞으면 숨기지 말고 그대로 보고. 각자 SI 기록 한 줄씩.

## 계산·검증 (검증표 빈칸 메우기 — 정확도 점수)

| | 할 일 | 못 하는 사람 (자기 데이터) | 시간 |
|---|---|---|---|
| A | 지평선 **33곳 전부** 독립 재계산 (지금 1곳뿐) | 지용 | 2–3시간 |
| B | 남극 밖 **17곳 전부** 좌표 오차 독립 재계산 (지금 작성자=검증자) | 수아 | 1–2시간 |
| C | 한국 연결 다시 계산 — **(1)** 지상국 4곳(여주 KDSA, DSN 3곳)의 '달 고도 ≥ 10°' 뜨고 지는 시각 전체 기간 (`windows_*.json`), **(2)** 여주 KST 일정표 전체 (`kdsa_daily_kst.json`), **(3)** 33곳 × 지상국 교신 시간 (`stations.json`) | 동주 | 1–2시간 |
| D | 3D 지구본 타일 빈칸: 띠 z4–z7, 남극 z3–z6, 알베도 | 수아 (소윤님은 z8 말고 나머지만) | 1–2시간 |
| E | 250 m 지도 16곳: 1 km 대비 차이표 + **노드 전부** 재계산 | 지용 | 2시간+ |
| F | 남극 사용자 지점 지형 +0.2–2.4 %p 오차 줄이기 (더 고운 타일) | 수아 | 3시간+ |
| M | 지표 33곳 **전부** 독립 재계산 (일조·지구·둘 다·최장 어둠, ephem + 지평선) | — | 1–2시간 |
| N | 중계탑 33곳 **전부** 독립 재계산 (탑→착륙지 가시선, Fresnel, 탑 지구 가시) | 지용 | 3시간+ |
| O | 948 m 달 전체 지도: 남극 75–90° 구역 셀 **전부** 독립 재계산 (지금 샘플) | 소윤 | 3시간+ |
| P | 해·지구 보이는 구간(windows) **33곳 전부** (지금 3곳) | 만든 사람 | 1시간 |
| Q | 월별 계절(monthly) **33곳 × 60개월 전부** (지금 3×3) | 만든 사람 | 1시간 |
| R | 실제 임무 검증: 착륙한 임무 **전부**(창어 3·4·5, SLIM, IM-1, Blue Ghost, 찬드라얀 3 등) 착륙 시각 태양 고도 vs Horizons (지금 아폴로 2개) | 동주 | 1–2시간 |
| S | 착륙지 좌표 **33곳 전부** 원 출처에서 다시 읽기 + 이름이 그 장소가 맞는지 (섀클턴 교훈, 지금 5곳) | 만든 사람 | 1시간 |
| T | 3.8 km 지도 원본 float32 격자 공개 + 다른 사람이 원본끼리 비교 | 공개=만든 사람, 비교=다른 사람 | 1시간 |
| U | 북극 75–90° N 사용자 지점 검증 (지금 '미검증' 배지) — PGDA 북극 DEM 30점 | 수아 | 2시간+ |
| V | 지구 가시 기준을 PGDA와 같게(any-part) 바꿔 다시 비교 → 3.87 %p 차이가 정말 정의 차이인지 증명 | 만든 사람 | 1–2시간 |
| W | 민감도 33곳 전부: 관측 높이 0/2/10 m, 200 m 안쪽 지형 포함/제외 → 한계 숫자 근거 | — | 2시간+ |
| X | 남극 밖 **17곳 250 m 주변 격자** 새로 만들기 (SLDEM2015 59 m, #61과 같은 정의·형식) → 검증은 다른 사람 | 만들기: 누구나(GPU 있으면 빠름) / 검증: 만든 사람 X | 2–3시간 + 검증 1시간 |

**A 프롬프트**: Pick all 33 sites in `web/data/horizon/` (not ones I produced). For each, choose 10 random azimuths and recompute the horizon elevation by brute force directly from the DEM listed in `docs/DATASETS`/the horizon file header (same observer height 2 m, curvature, near-field rule), with my own code, no imports from `pipeline/`. Report a table site × azimuth: stored vs mine, difference. Criterion ≤ 0.05°. Then recompute sun_frac for those 10 sites from ephem + my horizons; criterion ≤ 1 %p. Add a row to `docs/verification_ledger.md` (row `horizon/`) with my name and numbers.

**B 프롬프트**: For all 17 non-polar sites in `web/data/uncertainty/`, independently recompute — the ±500 m / ±100 m sample points' sun_frac, earth_frac and the reported min/max — with my own loop over ephem + horizons. Criterion ≤ 1 %p. Update the `uncertainty/` gap line in `docs/verification_ledger.md`.

**C 프롬프트** (11/15 07:40 지용님 지적 반영 — `windows_*.json`은 착륙지별이 아니라 지상국별 달 관측 창): (1) For each of the 4 stations (coordinates from the cited NAIF kdsa01.tf / DSN 810-005 files), recompute every Moon rise/set at 10° elevation over the full period of `web/data/korea/windows_<station>.json` with my own code (Skyfield or JPL Horizons, not `pipeline/korea_links.py`); report count of windows, max edge difference (criterion ≤ 60 s) and any missing/extra window. (2) Recompute every day of `kdsa_daily_kst.json` from (1) (KST split at midnight); all rows must match. (3) For all 33 sites, recompute from `web/data/ephem.bin` + `web/data/horizon/` + my station Moon elevations the hourly site×station link bits in `stations.json` (Earth centre above site horizon AND Moon ≥ 10° at station) and compare the per-site totals (criterion ≤ 1 h) and bit agreement. Update the `korea/` ledger row.

**D 프롬프트**: In `web/data/globe/`, decode 10 random vertices per zoom level for the equatorial band z4–z7 and compare with SLDEM2015 / PGDA 60 m; for south z3–z6 use the source-window origins now published in `docs/globe_south_window_origins.json` (18 PGDA windows: 20 m site windows, 60 m, and the 80 m 80S cap, with first-pixel centres and source URLs), then compare 10 vertices per level. Criterion: within the encoding step. Update the `globe/` gap line.

**E 프롬프트** (#61이 main에 들어간 뒤): For the 16 polar sites, compare `web/data/local250/` with `web/data/local/` (1 km) at shared nodes: table of differences per site (median, max). Then recompute 5 random 250 m nodes from the DEM by brute force; criterion ≤ 1 %p. Add a ledger row.

**F**: 결과가 기존보다 정확해지면 PR, 아니면 측정 결과만 보고(한계 문구 L9 근거가 됨).

**M 프롬프트**: For all 33 sites, recompute sun_frac, earth_frac, both_frac and longest_dark_h for the app's default window with my own loop over `web/data/ephem.bin` + `web/data/horizon/` (exact `web/js/core.js` definitions, no imports from the repo). Compare with `web/data/metrics/`; criterion ≤ 0.1 %p and ≤ 1 h. Full table in the PR, add a ledger row.

**N 프롬프트**: For all 33 sites in `web/data/relay/`, recompute the best tower's tower→lander line of sight, first-Fresnel clearance and tower Earth visibility from the DEM with my own code at hourly steps, and the resulting link fractions. Criterion ≤ 1 %p. Full table in the PR, update the relay ledger row.

**O–W 공통 프롬프트**: Read the row for this product in `docs/verification_ledger.md` and its producing script. Recompute it in FULL (every site / cell / interval listed in the task) with my own code, no imports from `pipeline/` or `web/js/` (definitions copied from `web/js/core.js` and `docs/data_contract.md`). Report a full table, max/median difference, the criterion I used (≤ 0.1 %p for fractions, ≤ 0.05° for angles, ≤ 2 min for interval edges, ≤ 1 h for durations), and every row that fails — do not drop or round away failures. Update the ledger row with my name, numbers and commit. Task-specific: R = landing times and coordinates from the cited mission sources, Sun elevation from JPL Horizons API at the landing coordinates; S = open each `source_url`, quote the coordinate text, and say whether the named place (rim / ridge / crater floor) is really at that point; U = compare the browser global path north of 75° N with a horizon built from the PGDA north-polar DEM at 30 random points (same criterion as VALIDATION row 14); V = recompute the app's Earth fraction with the any-part definition and compare with PGDA AVGVISIB at the same points; W = rerun the 33 sites' metrics for observer height 0, 2, 10 m and with/without the < 200 m near field, report the change per site.

## 제출물 (사람이 해야 하는 일)

| | 할 일 | 비고 |
|---|---|---|
| G | 30초 영상 영어 자막 (초안 `제출자료/video_30s.md`) — 디자인 합친 뒤 녹화 | 녹화는 지용님 데스크톱 |
| H | 슬라이드 7 "Next" 문장 — 팀이 직접 아이디어 내기 (AI로 아이디어 금지) | 다 같이 |
| I | 라이브 사이트 최종 점검: 한 사람당 화면 하나 (휴대폰/1280/1920/한국어) — 이상한 것 Issue 한 칸에 하나 | 여러 명 가능 |
| J | 출처 링크 깨진 것 고치기 (PGDA 폴더 2개, Wiley 1개) | — |
| K | 각자 SI 기록 줄 다시 세기 + 빠진 것 추가 | 전원 |
| L | 개인 체크인 설문 (일 06–12 / 15–20) | 전원 |

## 수아(통합)
- #61 독립 확인 → 합치기 → 남극 주변 지도 250 m 연결
- 디자인 브랜치 미리보기 → main 합치기
- 들어오는 PR 독립 재계산 후 합치기 → 최종 QA → 제출

**X 프롬프트**: Using the same runner and exact definitions as PR #61 (`web/data/local250/`, contract section for local grids), compute 250 m 41×41 local grids for the 17 non-polar sites from SLDEM2015 59 m (LDEM_64 where SLDEM2015 does not cover, e.g. CHANDRAYAAN3 per card 3), 2026–2030 hourly, observer 2 m. Write `web/data/local250/<ID>.json` + index entries, run `check_contract.py`, and in the PR give per-site min/max/IQR within 1/3/5/10 km and the difference vs the 1 km grid at shared nodes. **Verification (another person)**: recompute 5 random nodes per 3 sites by brute force from the DEM with own code; ≤ 1 %p.
