# Tray exact sync on top of PR #136 (jiyong/tray-reference-final)

Reference: Chaei's copy `index_chaei.html` 20:51, measured in Edge at 1440x900, same 3 sites (Haworth, Apollo 17, Nobile Rim 1), EN.
Earlier full rebuild (before #136) kept on branch `claude/tray-exact-v1` (ff614db), not merged.

## Hover / focus highlight (copy, measured)
| state | copy | this build |
|---|---|---|
| hovered site's chart line | opacity 1, stroke 2.4 px | same |
| other chart lines | opacity 0.22, stroke 1.6 px | same |
| hovered row background | rgba(237,237,237,.04) | same |
| other rows | unchanged in copy | opacity 0.45 (team request: rows fade too) |
| hover on a chart line | copy: no change measured | highlights that site (requested) |
| mouse leaves card / row | all back to normal | same |
| keyboard focus on a row | (copy: rows not focusable) | rows tabindex 0, same highlight |
Tabs: Sunlight, Earth view, Relay, Terrain (all checked).

## Spacing / type (y = top in px at 1440x900)
| item | copy | #136 before | now |
|---|---|---|---|
| card title size / weight | 14 px / 600 | 17 px / 700 | 14 px / 600 |
| fold button x | 1366 | 1375 | 1366 |
| mean-error badge x | 1257 | 1274 | 1257 |
| "Compare candidates" y / height | 150 / 22 | 151 / 25 | 150 / 22 |
| period y | 181 | 179 | 180 |
| tab group y | 218 | 239 | 218 |
| inactive tab text colour | #EDEDED | #9C9CA1 | #EDEDED |
| view heading y | 285 | 323 | 286 |
| description y | 328 | 369 | 329 |
| chart y / width | 356 / 301 | 396 / 306 | 356 / 301 |
| first row y | 464 | 500 | 464 |
| row divider colour | rgba(237,237,237,.08) | #2A2A2D | rgba(237,237,237,.08) |
| row name | 14 px / 500 | 13.5 px / 600 | 14 px / 500 |
| row value | 18 px / 500 | 17 px / 400 | 18 px / 500 |
| Detailed comparison button y | 819 | 819 | 819 |
