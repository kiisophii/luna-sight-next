# Design sync — contest build vs. designer's mock-up (Chaei's copy)

Reference specs for making the contest UI match the team designer's mock-up.
**Rule: never copy code from the practice board.** Implement from these measurements and screenshots only.
Numbers on screen must come from this repository's data, never from the screenshots.

- `채이사본_동기화_전수_1555.md` — full difference list, bundles 5–11 (latest; "★ 기준 변경" at the top)
- `채이사본_동기화_1303.md`, `채이사본_동기화_동작_1303.md` — bundles 1–4 (layout, interaction states)
- `채이사본_동기화_About히어로.md` — About hero rocket scroll animation
- `첫화면_채이사본_실측명세_1115.md` — first-screen measured spec (11:49 version)
- `대회판_변형제안.md` — optional variants (NOT in the base build)
- Screenshots: `shots/sync_full/` (A = mock-up, B = contest build) and `shots/top_match/`.
  Paths inside the documents that point to `...side-session-notes\...\sync_full\` or `...\top_match\` map to these folders.

Exceptions to "identical": no AI logo image (text wordmark in the same place/size), contest data only, no practice code,
accurate wording for things we did not compute (power, link performance), the 3D ×3 height note stays,
and the 390 px mobile layout keeps the contest build's stacked layout (the mock-up has no mobile layout) with the mock-up's styling.

- `채이사본_동기화_로켓모션.md` — About/intro rocket motion, frame-by-frame (p = 0…1 in 0.05 steps); contact sheets in `shots/rocket/sheet_*.png`
- `채이님_요청_전수체크_1720.md` — every request the designer made (51 requests, 481 rows) with mock-up status; contest-build column being filled in
- Intro: the mock-up has a ~10 s intro (Moon disc, LOADING %, lander descent with flame, wordmark lighting up letter by letter, T+ clock, ALT, TOUCHDOWN, SKIP). See the rocket-motion doc.
