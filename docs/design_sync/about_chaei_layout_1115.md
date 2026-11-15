# Chaei About layout sync — 2026-11-15

Reference: https://claude.ai/artifact/RLsov5Ka36gqeFmJFThNMx (the current copy, explicitly confirmed by Chaei). Base: main 490c024. Measurements and screenshots only; no practice source copied.

The contest's approved About copy, numeric calculations, rocket module, hero markup, and shared layout stylesheet are unchanged. Existing validation cards are moved into section 05; existing supporting content is grouped into disclosure rows, with its text retained. The extra definitions disclosure retains contest-only explanation rather than deleting it. Text length changes from the reference are intentional: Dongju's approved contest text remains the source of truth. This is a match of layout rules, not an assertion of identical whole-page pixels.

## Implemented measurements

- Body left/right 4vw; 12 columns, 24px column gap; heading spans 4 and body spans 8.
- First body starts 40px below the existing hero band; subsequent sections have 64px top spacing.
- Section heading 30px/600, number 11px/500 with 8px bottom margin.
- Step cards: 2 columns, 12px gap; question cards: 3 columns. Padding 18/18/16; radius 12; border #2a2a2d; fill #121213.
- Measure table: max 760px, first column 34%, 12px vertical cell padding, line separators.
- Geist body; Geist Mono card/table text. Fonts load the original Google Fonts distribution directly (SIL OFL 1.1, https://github.com/vercel/geist-font). Hero typography is untouched.
- Question buttons radius 10 with 6/12 padding; Korea/final CTA 40px; data links are plain text with 22px gaps.
- Existing computed validation values are shown in 3 equal cards, max 760px. No mock-up numbers.
- Mobile keeps the contest's single-column composition.

## Verification

Chrome browser checks at 1920×1080, 1440×900, 1280×800, each EN and KR: no document horizontal overflow, no About controls/cards/table outside the viewport, 3 computed validation cards present, 0 captured console errors in all six cases. Additional 390×844 check with the Methods disclosure open: document width 390. Methods link opens its disclosure. Full before/after screenshots for all six desktop cases were saved locally. Automated attachment is blocked: Chrome fileChooser.setFiles continues to report missing file-URL access after the user enabled it and after a fresh tool connection. Screenshots are provided separately to Chaei; they are not in this PR.

The live original and modified About have identical non-whitespace text character multisets in EN after text relocation. about_copy.js and about_hero.js are byte-identical to main; the hero markup is unchanged. Scientific calculations/data files are unchanged. No claim of independent scientific validation.

Reproduce: `python3 -m http.server 8765 --bind 127.0.0.1 --directory web`, open `http://127.0.0.1:8765/#about`, select EN/KR and each viewport, inspect Console. Open Methods and validation to confirm the disclosure and original tables.

## Remaining design review

The final copy has horizontal page tabs beside the wordmark; live v43 has only the right-side step rail. The final copy also uses different type families on the map and comparison cards. These are outside this About PR and should be handled with the owning design sessions. Open PRs #96, #97, #98, #99 already cover Site check, tray, comparison/common pages, and rocket motion respectively. Screenshots compare component geometry; selected sites and computed numbers differ and are not defects. Reference screenshots include Claude's 45px outer toolbar; subtract it for page y positions.

