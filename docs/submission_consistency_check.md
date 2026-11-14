# Submission documents — cross-consistency check

Soyun Jeong, 2026-11-14 (KST), requested by the team lead (Sua Kim). Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
**Review only: no submission file was changed.** Every finding cites file:line on main `4fbdd63` (web version 27).

## 1. Files and version
| File | Lines | Last change on main | Own source snapshot stated in the file |
|---|---|---|---|
| `submission/summary_final_en.md` | 38 | ≤ `e8fe5fb` (2026-11-14 22:35) | main `64e3bee`, web v24 (:24) |
| `submission/slides_7_en.md` | 104 | same batch | main `64e3bee`, web v24 (:81) |
| `submission/validation_onepager_en.md` | 33 | same batch | `docs/VALIDATION.md` (:3) |
| `submission/si_disclosure_en.md` | 116 | `0068eed` (merge s4-si-disclosure-minchul) | `64e3bee`, 98 SI rows (:3) |
| `submission/resources_en.md` | 306 | `e8fe5fb` (PR #36) | `c799395` + addendum `30d7877` + web audit `64e3bee` (:7, :185, :211) |
| `docs/VALIDATION.md` | 91 | after `19867c3` | "version 23 (`19867c3`)" (:4) |

- Main: `4fbdd63` = web version **27**. It contains the version-26 submission batch (`115d285`), then PR #48 (z4 tiles, `533220c`) and contract §21 (`4fbdd63`).
- All six files were read end to end.
- `python pipeline/verify_submission_text.py` on `4fbdd63`: **77 OK, FAILURES: 0**. It must run with `PYTHONIOENCODING=utf-8`; see m14.
- Original reports and JSON opened to trace the numbers:
  - `docs/location_sensitivity.md`, `docs/date_slip.md`, `docs/relay_impact.md`, `docs/korea_links.md`
  - `docs/site_coordinate_audit.md`, `docs/hindcast.md`, `docs/ui_data_audit.md`, `docs/gpu_cpu_300_check.md`
  - `docs/assumption_sensitivity.md`, `docs/near_field_comparison.md`, `docs/named_residuals.md`, `docs/coordinate_uncertainty.md`
  - `docs/validation_pgda.md`, `docs/card9_verification.md`, `docs/card14_pgda_analysis.md`, `docs/timestep_sensitivity.md`
  - `docs/source_permissions.md`, `docs/1단계_분배.md`, `docs/SI_USAGE.md`, `web/js/korea_panel.js`, `web/index.html`, `README.md`, `LICENSE`
  - GitHub states of PRs #35 #36 #39 #41 #45 #46 #47 and issues #43 #44
- The PGDA product page and PDS label were also opened: https://pgda.gsfc.nasa.gov/products/69 and http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.LBL.

Labels: CONSISTENT · CONTEXT DIFFERENCE · INCONSISTENT · OUTDATED · OVERCLAIM · UNVERIFIED.

## 2. Cross-check table (items that appear in more than one place)
| Item | Where (file:line) | Values / wording | Source checked | Verdict |
|---|---|---|---|---|
| Team name | summary:1, slides:1,12, onepager:1, si:1, resources:1, VALIDATION:1, README:1 | "Ginkgo Orbit" everywhere | — | CONSISTENT |
| Project name | summary:1,8, slides:1,8 "Luna Sight — Lunar Landing Site Navigator"; onepager:1, VALIDATION:1, resources:3, README:1, `web/index.html:6` "Lunar Landing Site Navigator" only | "Luna Sight" in 2 of 6 files and not in the app | no repo file defines "Luna Sight" | INCONSISTENT → **M6** |
| Team members | si:19–24 (Sua Kim, Minchul Kim, Jiyong, Soyun Jeong, Dongju Kim, 오채이); `docs/1단계_분배.md:8–14` (김민철, 성지용, 정소윤, 김동주, 김수아, 오채이) | 6 members, same people | assignment doc | CONSISTENT (spelling of Jiyong → m8) |
| Team lead | VALIDATION:84 "Dongju Kim (team lead)"; `docs/card14_*.md`, `docs/timestep_sensitivity.md:3`, `docs/gmaps_z4.md:3` "team lead (Sua Kim)"; si:19 Sua = integration | two different people | `1단계_분배.md` names no 팀장 (Sua = 통합, Dongju = 팀 미팅 대표) | INCONSISTENT → **M5** |
| 33 sites | summary:8, slides:11,15,30,35, resources:156,285, VALIDATION:17,65,71 | 33 | `web/data/sites.json` 33 records; `site_coordinate_audit.md:24` | CONSISTENT ("33 Moon landing sites" → m12) |
| Every hour 2026–2030 | summary:8, slides:11,15 | 43,824 h | `location_sensitivity.md:5`, `korea_links.md:3` | CONSISTENT |
| 5 m terrain near the pole | summary:8, slides:32,35 | 5 m | `location_sensitivity.md:29`, DATASETS PGDA 5 m | CONSISTENT |
| 1 km contrast 38.7 / 6.7 pp | summary:10, slides:41,45 | median over sites of the largest neighbouring-node "both" difference | `location_sensitivity.md:15–16,19` (38.65 / 6.70, 16 + 16 sites); checker recomputed | CONSISTENT; wording note m10 |
| 10 km sunlight IQR 17.2 / 0.4 pp | summary:10, slides:42,45 | medians 17.16 / 0.40 | same table | CONSISTENT |
| Malapert 0 → 100 % Earth, 0 → 45 % both | slides:22,25,40,45 | 1 km apart, most extreme pair | `location_sensitivity.md` Malapert rows (100.00, 45.11) | CONSISTENT |
| Date slip 26 of 33, 336 h | summary:10, slides:43,45 | | `date_slip.md:9` | CONSISTENT |
| Cabeus B 30 → 86 % with a 15 m tower | summary:10, slides:51,56 | 29.64 → 85.73 % | `relay_impact.md:20` | CONSISTENT; "Earth link" wording m11 |
| 7 sites < 50 %, 3 pass with one tower | slides:52,56 | | `relay_impact.md:9,18–24` | CONSISTENT |
| KDSA-only 123 h / 0.3–0.4 % | slides:53,56; VALIDATION:90 | | `korea_links.md:46–47` | CONSISTENT |
| **PGDA 1.66 pp** (Sun, 240 points 85–90° S, r 0.985) | summary:10 "1.7"; slides:61,66; onepager:8,24; VALIDATION:13,60,88 | MAE 1.66, RMSE 2.62, r 0.985 | `web/data/validation.json` 1.658 / 0.9846 / 240; `validation_pgda.md:30` | CONSISTENT as a value. Summary generalises it → **M1**. Definition note m1 |
| PGDA Earth 1.24 pp | onepager:8–9,24; VALIDATION:13,61,88–89 | any-part rule | `validation_pgda.md:33`; app's centre rule 3.87 (VALIDATION:30,61) | CONTEXT DIFFERENCE, unstated in prose → **M3** |
| **JPL Horizons 0.0005°** | slides:62,66; VALIDATION:87 | "within 0.0005°, over 37,000 comparisons (2020–2038)" | rows 1–3: 1,452 + 1,452 + 34,296 = 37,200; maxima 0.000016° / 0.00044° (app float32) / 0.000034° / 0.000041° | CONSISTENT |
| JPL Horizons 0.000041° | onepager:6,22; VALIDATION:11,55 | 34,296 comparisons, validation file only | row 3 | CONTEXT DIFFERENCE vs 0.0005° → m2 |
| Terrain horizons ~0.02° | onepager:7,23; VALIDATION:12,59,87 | RMS ≤ 0.026°, max 0.012–0.219° | `card9_verification.md` | CONSISTENT ("about 0.02°" = RMS) |
| 948 m map vs PGDA (400 points 75–85° S) | onepager:25; VALIDATION:14,74 | Sun 2.61; Earth 2.42 (any-part at cell centres) / 3.42 (stored centre value) | `card14_pgda_analysis.md` §3 B4 | CONTEXT DIFFERENCE; onepager omits 3.42 → m3 |
| VALIDATION row 11 (2.19 / 1.73) vs row 22 (2.61 / 3.42) | VALIDATION:63,74 | different code, period, point vs cell, Earth rule | `card14_pgda_analysis.md` | CONTEXT DIFFERENCE, explained in row 22 |
| GPU vs CPU 600 cells, max 0.000003 pp | onepager:10,26; VALIDATION:15 | | `gpu_cpu_300_check.md:3,8` | CONSISTENT ("independent source" column → m-note below) |
| Named-site residuals 5/5 within spread | onepager:9–10,27; VALIDATION:16 | | `named_residuals.md` | CONSISTENT |
| Coordinate grids 30 nodes, 0.021 pp | onepager:28; VALIDATION:17 | | rows 20, PR #27 | CONSISTENT |
| Apollo 11–17 Sun elevation 0.05° | slides:62,66; onepager:10–11,29; VALIDATION:18,73 | | `hindcast.md:7` | CONSISTENT |
| KDSA / DSN Moon direction 0.0012° | onepager:30; VALIDATION:19,67,89 | | row 15 | CONSISTENT |
| 5,520 website values, 0 mismatches | slides:63,66; onepager:11–12,31; VALIDATION:20 | VALIDATION adds "2 display issues opened: #43, #44" | `ui_data_audit.md:17`; issues #43, #44 **OPEN** | CONSISTENT number; caveat dropped → m4 |
| Near field 0.12–0.80 pp | onepager:14; VALIDATION:29 | | `near_field_comparison.md` | CONSISTENT |
| Earth centre vs any part 4.6–5.6 pp | onepager:15–16; VALIDATION:30 | | `named_residuals.md:37` | CONSISTENT |
| No PGDA north of 75° S | slides:64; onepager:16; VALIDATION:31 | | rows 8–11, 22 | CONSISTENT |
| Region centres, up to 51.8 pp in 300 m | onepager:17–18; VALIDATION:33 | 51.80 | `coordinate_uncertainty.md:78` | CONSISTENT |
| Time step 1 h vs 10 min ≤ 0.03 pp | onepager:18; VALIDATION:34 | 0.029 pp | `timestep_sensitivity.md` (PR #46, merged) | CONSISTENT |
| Observer height 1–10 m ≤ 10.7 pp (HAWORTH) | onepager:18; VALIDATION:35 | 10.69 | `assumption_sensitivity.md:7` | CONSISTENT |
| Analysis period | summary:8, slides:11 2026–2030 hourly; PGDA checks 2020–2038 2 h vs PGDA hourly 18.6 y; 948 m map 2026–2030 3 h | | VALIDATION:36 (5 vs 18.6 y: 2.183 vs 2.185 pp) | CONTEXT DIFFERENCE, documented |
| KDSA permission | VALIDATION:40,78,84,90–91 "pending"; `web/js/korea_panel.js:28` "(use pending)"; resources:81,144 "PROJECT USE APPROVED" | | `docs/source_permissions.md:9` (approval relayed by the user, 14 Nov) | INCONSISTENT → **M4** |
| PGDA Sun definition | resources:50 "any part of the solar disc"; `card9_verification.md:14` "finite disc"; VALIDATION:60 compares our "mean disc fraction" | | PDS label: "percentage of timesteps where each pixel was sunlit (by any fraction of the solar disc)" | CONTEXT DIFFERENCE (+ wrong wording in `card9_verification.md:14`) → m1 |
| AI tools | si:7,19–23 (Claude Code, OpenAI Codex); resources:136–137; slides:73; summary:12 | | `docs/SI_USAGE.md` | CONSISTENT |
| SI row counts | si:3,25 "98 rows, 72 TO CHECK" | main now 114 rows, 77 TO CHECK | `docs/SI_USAGE.md` @ `4fbdd63` | OUTDATED → **M7** |
| "independent" / "every" claims | onepager:5 "We checked every step"; VALIDATION:84,86 deliberately "key numbers"; si:11 rejects the blanket sentence | | — | OVERCLAIM in onepager → **M2** |
| Licence | slides:72 Apache-2.0; resources:11 | | `LICENSE` (Apache 2.0) | CONSISTENT |
| NASA logos / AI images | slides:3; resources:261–262 | none | resources web audit | CONSISTENT |
| Datasets and papers | slides:71; resources NASA data / papers tables; VALIDATION:13 (Mazarico et al. 2011) | LOLA, PGDA, SLDEM2015, NAIF, Horizons, Mazarico 2011, Barker 2016/2021/2023, Smith 2010 | `data/DATASETS.md` | CONSISTENT; gmaps_ppd32 file count → m9 |

No "NASA-validated", "accurate" or "real-time" claims were found in the six files. "Live" only names the live website or demo (slides:13,63; onepager:12).

## 3–6. Findings (severity, location, original text, recommended text, evidence)

### Critical
**C1. Unfinished placeholders in the backup deck.**
- Location: `submission/slides_7_en.md:74` and `:71`.
- Original: `Next: *[TEAM TO WRITE — future plans must be the team's own idea]*` and `full list in data/DATASETS.md (team to confirm the final list)`.
- Recommendation: the team writes its own "Next" text (AI must not write it, per :4), and removes "(team to confirm the final list)" once the list is confirmed.
- Evidence: slides:4 says the 7-slide deck is a fallback for the video, so it must be complete if used.

### Major
**M1. OVERCLAIM — the summary generalises the PGDA agreement to all "results".**
- Location: `summary_final_en.md:10`.
- Original: "Results agree with NASA's south-polar illumination maps to 1.7 points on average."
- Recommended (12 words, total stays 198): "**South-polar sunlight agrees with NASA's PGDA maps to 1.7 points on average.**"
- Evidence:
  - 1.66 pp is the Sun at 240 random points 85–90° S (VALIDATION:60).
  - The Earth with the app's centre rule is 3.87 pp (VALIDATION:61); the 16 named sites are 3.67 pp (VALIDATION:62); the 948 m map at 75–85° S is 2.61 pp (VALIDATION:74).

**M2. OVERCLAIM — "every step".**
- Location: `validation_onepager_en.md:5`.
- Original: "We checked every step, from sky geometry to the screen, against independent sources."
- Recommended: "**We checked the key steps, from sky geometry to the screen, against independent sources.**"
- Evidence: VALIDATION:84 records the team decision for "key numbers" instead of "every number". si_disclosure:11 says the blanket claim "is not established by the available log". VALIDATION:76–80 lists what is not validated.

**M3. CONTEXT DIFFERENCE stated as agreement — Earth 1.24 pp is PGDA's any-part rule, not the app's Earth metric.**
- Location: `validation_onepager_en.md:8–9`.
  - Original: "and Earth visibility by 1.24 points (r = 0.990)"
  - Recommended: "**and Earth visibility, with PGDA's any-part rule, by 1.24 points (r = 0.990; the app's stricter centre rule: 3.87)**"
- Location: `docs/VALIDATION.md:88–89` (submission paragraph, exactly 150 words).
  - Original: "and Earth visibility by 1.2 points (r = 0.990)"
  - Recommended, still 150 words: "**and Earth visibility (PGDA's any-part rule) by 1.2 points**"
- Evidence: `validation_pgda.md:33` (any part 1.239) and :39 (centre bias −3.25); VALIDATION:30,61 (centre MAE 3.87 pp). The app counts the Earth centre (CLAUDE.md "Definitions").

**M4. INCONSISTENT — KDSA permission "pending" vs "approved".**
- Locations: `docs/VALIDATION.md:40` (L12), `:78`, `:84`, `:90–91` and `web/js/korea_panel.js:28` say pending. `resources_en.md:81,144` say "PROJECT USE APPROVED" (user-relayed, 14 Nov), citing `docs/source_permissions.md:9`.
- Recommendation: the team confirms which is true.
  - If the approval stands, change VALIDATION:90–91 "and permission to use the KDSA coordinates is still pending." to "**and KDSA coordinates used with project permission (14 Nov 2026).**" (10 → 10 words; the paragraph stays 150), and update L12 / :78.
  - The app string in `korea_panel.js:28` is the UI owner's.
  - If the approval does not stand, resources:81,144 must go back to PENDING.
- Evidence: resources:254 itself notes "main UI/data still has pending-use wording".

**M5. INCONSISTENT — who is the team lead.**
- Location: `docs/VALIDATION.md:84`.
- Original: "Wording decided by Dongju Kim (team lead)".
- Recommendation: confirm the role. If Sua Kim is the team lead (as in `docs/card14_split_merge.md:4`, `docs/timestep_sensitivity.md:3`, `docs/gmaps_z4.md:3`), write "**Wording decided by Dongju Kim (validation owner)**", or name the person who actually decided.
- Evidence: `docs/1단계_분배.md:8–14,26`: Sua Kim = integration, Dongju Kim = PGDA validation and team-meeting representative; no 팀장 entry.

**M6. INCONSISTENT — project name.**
- Location: "Luna Sight — Lunar Landing Site Navigator" in `summary_final_en.md:1,8` and `slides_7_en.md:1,8`. Only "Lunar Landing Site Navigator" (the challenge name) in `validation_onepager_en.md:1`, `docs/VALIDATION.md:1`, `resources_en.md:3`, `README.md:1` and `web/index.html:6`.
- Recommendation: the team decides the official name.
  - If it is "Luna Sight", use "**Luna Sight — Lunar Landing Site Navigator (Team Ginkgo Orbit)**" in the one-pager title, and make the README / app title match (owners: integrator).
  - If not, drop "Luna Sight" from the summary and slides.
- Evidence: no repository file other than these two defines "Luna Sight".

**M7. OUTDATED — SI disclosure counts.**
- Location: `si_disclosure_en.md:3,17–25,31`: 98 rows, 72 TO CHECK.
- Main `4fbdd63` has **114 rows, 77 TO CHECK**:

| Member | Rows | TO CHECK |
|---|---|---|
| Sua Kim | 43 | 43 |
| Minchul Kim | 24 | 0 |
| Jiyong | 18 | 18 |
| Soyun Jeong | 10 | 6 |
| Dongju Kim | 19 | 10 |

- Recommendation: refresh the snapshot, as si:27 itself requires ("Refresh this inventory ... before final submission"). The statement at :7 can stay.
- Evidence: count of `^| 2026-` rows in `docs/SI_USAGE.md` on `4fbdd63`, penultimate cell.

> **Addendum (2026-11-15, main `8eff7ac`, web version 28; the M7 finding above is kept as written for `4fbdd63`).**
> - Main `8eff7ac` filled all 77 `TO CHECK` human-check cells in `docs/SI_USAGE.md` with "Confirmed by <member> — in-person team confirmation relayed by Sua, 2026-11-14". It also added an update note at `si_disclosure_en.md:33`.
> - That note gives the 77-cell breakdown (Sua Kim 43, Jiyong 18, Dongju Kim 10, Soyun Jeong 6, Minchul Kim 0) and states "Pending human-check cells in the current log: 0".
> - It also states that the counts and list below describe the pinned snapshot `64e3bee`. The 98 / 72 figures at `si_disclosure_en.md:25,35` are therefore now explicitly labelled as a snapshot.
> - **What remains:**
>   1. Main has **115 rows** (not stated in the disclosure).
>   2. After this PR (#54) merges, the log has **116 rows and 1 `TO CHECK`**: the 23:50 row for this review. So "Pending … 0" at `si_disclosure_en.md:33` becomes out of date unless that row is confirmed first.
> - Suggested addition at :33: "Current log: 115 rows (116 after PR #54; its one new row is pending)".
> - **Severity for the remaining part: Minor** (was Major).
> - Evidence: `git show 8eff7ac:submission/si_disclosure_en.md` line 33; `^| 2026-` rows and penultimate cells of `docs/SI_USAGE.md` on `8eff7ac` (115 / 0) and on this branch (116 / 1).

### Minor
- **m1. CONTEXT DIFFERENCE — PGDA Sun definition.**
  - The PDS label defines the PGDA Sun value as the fraction of hourly time steps "sunlit (by any fraction of the solar disc)". The headline 1.66 pp (VALIDATION:60, onepager:8, slides:61) compares it with our *mean visible disc fraction*. With the same any-part rule it is 1.400 pp, r 0.9834 (`validation_pgda.md:31`), so the headline is the more conservative number.
  - `docs/card9_verification.md:14` ("solar illumination of the **finite disc**") misreads the product page: the page says the light source is modelled as a finite disc. Fix that line to quote the label.
  - Optionally add "(our mean disc fraction; with PGDA's any-part rule 1.40 pp)" to VALIDATION:60.
  - The app's `sun_frac` uses the half-disc predicate (resources:106). The difference between that and the validated mean-disc quantity at these points was not measured: **UNVERIFIED**.
- **m2. CONTEXT DIFFERENCE — Horizons accuracy.** `validation_onepager_en.md:6` gives 0.000041° (validation file, 34,296 comparisons), while slides:62 / VALIDATION:87 give 0.0005° (37,200 comparisons including the app's float32 file, 0.00044°). Recommended at onepager:6: "to 0.000041° in 34,296 comparisons (2020–2038; **the app's float32 file: within 0.0005°**)".
- **m3. CONTEXT DIFFERENCE — 948 m Earth value.** `validation_onepager_en.md:25` "MAE 2.61 / 2.42 pp": 2.42 is the any-part rule recomputed at the cell centres. The stored map holds the Earth centre (3.42 pp). Recommended: "MAE 2.61 / 2.42 pp (**stored Earth-centre value 3.42**)". Evidence: VALIDATION:14, `card14_pgda_analysis.md` §3 B4.
- **m4. Caveat dropped — website audit.** `slides_7_en.md:63` and `validation_onepager_en.md:11–12,31` say "0 mismatches". VALIDATION:20 adds that 2 display issues were opened, and issues #43 and #44 are still **open** (#43: 27 sites show "No local map"). Recommended: "5,520 numbers read from the live website: 0 numeric mismatches (**2 display issues open**)".
- **m5. OUTDATED / INCONSISTENT inside VALIDATION.md.** :4 "main version 23 (`19867c3`)" (now v27, `4fbdd63`). :29 "re-run in docs/near_field_check.md (PR #41, open)" although :4 and GitHub say #41 is merged. Recommended at :29: "(PR #41)".
- **m6. OUTDATED source label.** `summary_final_en.md:24` and `slides_7_en.md:81` say "main `64e3bee`, web version 24". All 77 checks still pass on `4fbdd63`, so only the label is old. Recommended: "main `4fbdd63`, web version 27 (re-checked)".
- **m7. OUTDATED.** `si_disclosure_en.md:27` "the still-unmerged PR #36". PR #36 is merged (`e8fe5fb`).
- **m8. Name spelling.** `si_disclosure_en.md:21,42–100` use "Jiyong". `docs/SI_USAGE.md:11` and `docs/card14_split_merge.md:4` use "Jiyong Sung" (성지용, `1단계_분배.md:9`). Recommended: "Jiyong Sung" in the member table, keeping the log label in the row links. 오채이's English spelling is still not recorded (si:24); the team should supply it.
- **m9. OUTDATED file counts.** `resources_en.md:238,275` say `gmaps_ppd32/` has 517 files, and :266 says web/data has 6093 files. After PR #48 `gmaps_ppd32/` has 2,053 files: +1,536 z4 display tiles, team-derived, same sources. Recommended: "517 → 2,053 (z4 display tiles added in PR #48)".
- **m10. Wording — the 1 km contrast.**
  - `summary_final_en.md:10` and `slides_7_en.md:41`: "up to 38.7 percentage points at a typical site". This is correct: the median site's largest neighbouring pair. But `location_sensitivity.md:19` warns these "are the most extreme neighbouring pairs, not the typical effect of a 1 km move".
  - "Away from the poles" means the 16 sites with |lat| < 60°; Chandrayaan-3 (69° S) gives 21.44 pp.
  - Optional (summary has 0 spare words): keep as is. In the slides, add "(16 sites with |lat| < 60°)" to the speaker notes.
- **m11. OVERCLAIM (small) — "Earth link".** `summary_final_en.md:10` "lifts Cabeus B's Earth link". The result is line-of-sight geometry only (slides:54, VALIDATION:40). Recommended, same word count: "lifts Cabeus B's **Earth visibility** from 30% to 86%".
- **m12. Wording — "33 Moon landing sites".** `slides_7_en.md:11`. The catalogue includes 9 Artemis III representative points (resources:250), 4 DEM-region centres (VALIDATION:33) and one planned target, IM3 (resources:253). Recommended: "**33 landing sites and candidate points**". The summary's "33 sites with published coordinates" (:8) is fine.
- **m13. UNVERIFIED.** `summary_final_en.md:1` "challenge 04": no repository file states the challenge number.
- **m14. Tooling.** `pipeline/verify_submission_text.py` stops with `UnicodeEncodeError` on a Korean Windows console (cp949) at the first "–". Run it with `PYTHONIOENCODING=utf-8`, or have the script reconfigure stdout. It is not a content error.
- **m15. OUTDATED (outside the six files).** `README.md:5` "Live demo: (GitHub Pages link — added once the first build is deployed)" while slides:13 give the live URL.

Wording note (no change needed): in `validation_onepager_en.md:26` the "Independent source" for the GPU check is the unchanged CPU code. That is the same algorithm, not an independent method. The cell text says this correctly ("unchanged CPU code").

## 7. Fix list before submission (priority order)
1. **C1** — write slide 7 "Next" (team's own words) and remove the "team to confirm" note. Owner: team.
2. **M1** — summary sentence (same word count).
3. **M2** — one-pager "every step" → "key steps".
4. **M3** — say "PGDA's any-part rule" next to Earth 1.24 / 1.2, in the one-pager and the VALIDATION paragraph.
5. **M4** — decide the KDSA status, then align VALIDATION:40,78,84,90–91, resources:81,144 and the app string.
6. **M6** — decide the project name and align the one-pager title, README and app title.
7. **M5** — correct the "team lead" label at VALIDATION:84.
8. **M7** — refresh the SI disclosure counts (114 / 77 on `4fbdd63`) just before submitting. Owners fill their own `TO CHECK` cells.
   - *Addendum, main `8eff7ac`:* the 77 cells are filled and `si_disclosure_en.md:33` explains this. What is left is the current row count (115, or 116 with PR #54) and this PR's one pending row. Now Minor; see the M7 addendum.
9. Minor, if time allows: m2, m3, m4, m11, m12 (short additions), m5, m6, m7, m8, m9 (labels and counts), m1 (`card9_verification.md:14` wording), m14.

## 8. Items checked and found consistent
- Team name, the six members, Apache-2.0, no NASA logos or AI images.
- 33 sites (coordinates 0.000 m from source).
- Hourly 2026–2030 = 43,824 h; 5 m polar terrain.
- 38.65 / 6.70 pp and 17.16 / 0.40 pp, recomputed by the checker from all 33 grids.
- Malapert 0 → 100 % and 45.11 %; 26 of 33 sites and 336 h; Cabeus B 29.64 → 85.73 %; 7 / 3 sites; KDSA 123 h and 0.3–0.4 %.
- PGDA 1.66 pp / r 0.985 / 240 points (as a value).
- Horizons 0.0005° (37,200 comparisons) and 0.000041° (34,296).
- Horizons RMS ≤ 0.026°; Apollo 0.05°; KDSA / DSN 0.0012°; GPU / CPU 600 cells; named residuals 5/5; coordinate grids 0.021 pp; 5,520 values.
- Limits: 0.12–0.80, 4.6–5.6, 51.8, 0.03 and 10.7 pp; no PGDA north of 75° S.
- The row-11 vs row-22 difference is explained in VALIDATION:74.
- AI tools named the same way in SI, resources, slides and summary.
- Summary word count 198 (limit 150–200).

## 9. Submission risk
**Medium-low for numbers, medium for wording.** No number contradicts its source or another document: every repeated value matches, and the differences found are context differences with documented conditions.

The risk lies in:
- one unfinished slide (C1);
- three statements stronger than the evidence or missing their definition (M1–M3);
- three facts the team must decide once and align: KDSA status, project name, team lead (M4–M6);
- one stale SI snapshot (M7).

All are text edits. No recomputation is needed.
