# 일요일 아침 할 일 — 온 사람부터 위에서 하나씩 가져가기

> 빨리 끝낼수록 좋아요. 끝나면 다음 칸 바로 가져가기.
> 파일: `docs/morning_tasks_1115.md` (main). 가져갈 때 단톡에 "A 제가 할게요" 한 줄. 끝나면 PR → 수아가 합침. 각자 AI에 먼저:
> `Pull the latest main, read docs/verification_ledger.md and docs/data_contract.md. I am <이름>, task <글자>.`
> **규칙:** 자기가 만든 데이터는 자기가 검증 못 함(다른 사람 것만). 결과 숫자는 그대로 적고, 안 맞으면 숨기지 말고 그대로 보고. 각자 SI 기록 한 줄씩.

## 계산·검증 (검증표 빈칸 메우기 — 정확도 점수)

| | 할 일 | 못 하는 사람 (자기 데이터) | 시간 |
|---|---|---|---|
| A | 지평선 33곳 독립 재계산 늘리기 (지금 1곳뿐) | 지용 | 1시간 |
| B | 남극 밖 17곳 좌표 오차(uncertainty) 독립 확인 (지금 작성자=검증자) | 수아 | 40분 |
| C | 한국 연결 분 단위 창·KDSA 일정표 대조 (지금 미대조) | 동주 | 40분 |
| D | 3D 지구본 타일 빈칸: 띠 z4–z7, 남극 z3–z6 | 수아 (소윤님은 z8 말고 z4–z7·z3–z6만) | 1시간 |
| E | #61 250 m 합친 뒤: 1 km 대비 차이표 + 무작위 점 재계산 | 지용 | 40분 |
| F | 남극 사용자 지점 지형 +0.2–2.4 %p 오차 줄이기 (더 고운 타일) | — (GPU 있는 사람) | 2시간+, 선택 |

**A 프롬프트**: Pick 10 random sites from `web/data/horizons/` (not ones I produced). For each, choose 10 random azimuths and recompute the horizon elevation by brute force directly from the DEM listed in `docs/DATASETS`/the horizon file header (same observer height 2 m, curvature, near-field rule), with my own code, no imports from `pipeline/`. Report a table site × azimuth: stored vs mine, difference. Criterion ≤ 0.05°. Then recompute sun_frac for those 10 sites from ephem + my horizons; criterion ≤ 1 %p. Add a row to `docs/verification_ledger.md` (row `horizon/`) with my name and numbers.

**B 프롬프트**: For the 17 non-polar sites in `web/data/uncertainty/`, independently recompute 5 sites (random) — the ±500 m / ±100 m sample points' sun_frac, earth_frac and the reported min/max — with my own loop over ephem + horizons. Criterion ≤ 1 %p. Update the `uncertainty/` gap line in `docs/verification_ledger.md`.

**C 프롬프트**: Compare `web/data/korea/windows_*.json` and `kdsa_daily_kst.json` against my own recomputation for 3 sites (Haworth, one near-side, one far-side) over 30 days: Earth centre above the site horizon AND Moon ≥ 10° at the station (coordinates from the cited NAIF/DSN files), minute steps. Report start/end differences (criterion ≤ 2 min) and total hours (≤ 1 %). Update the `korea/` gap line.

**D 프롬프트**: In `web/data/globe/`, decode 10 random vertices per zoom level for the equatorial band z4–z7 and compare with SLDEM2015 / PGDA 60 m; for south z3–z6 first reconstruct the window origin from the tile metadata (write it down), then compare 10 vertices per level. Criterion: within the encoding step. Update the `globe/` gap line.

**E 프롬프트** (#61이 main에 들어간 뒤): For the 16 polar sites, compare `web/data/local250/` with `web/data/local/` (1 km) at shared nodes: table of differences per site (median, max). Then recompute 5 random 250 m nodes from the DEM by brute force; criterion ≤ 1 %p. Add a ledger row.

**F**: 오래 걸리면 안 끝나도 됨. 안 되면 지금 한계 문구(L9) 그대로 둠.

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
