# Designer review 10 (v47): side cards on one rule set

Reference = the copy's final left panel (measured 1440 EN, 1280 KO). The left card markup (sort label, mission summary,
"+ Condition", fold arrow) is being edited by Chaei and was not touched; only shared CSS values for the right card changed.

| Item | Left card (copy, standard) | Right card before | Right card after |
|---|---|---|---|
| Content inset from card edge | 15 px | 17 px (padding 16 + border) | 15 px (padding 12 14 16) |
| Card title | 17 px / 700, top 14 | 14 px / 600, top 20 | 17 px / 700, top 14 |
| Fold button | 28 x 28, top 13 | 28 x 28, top 17 | 28 x 28, top 13 |
| Info button | 20 x 20 | 22 x 22 | 20 x 20 |
| Title row → next block | — | tabs at 164 | tabs at 178 (+14 gap), heading +14 below tabs |
| Category tabs text | — | 12 px | 14 px at >= 1440, 12.5 px at 1100-1439 |
| Heading vs sub-tabs (1100-1439) | — | one squeezed line (touched at 1280) | sub-tabs on their own row, gap 16 |
| Sub-tab gap | — | 10 px | 14 px |
| Description | — | directly under the heading line | 10 px gap |
| "Detailed comparison" button (b9feb3d) | — | 286 px | full content width (copy 316 px) |

Checked: 1920 / 1440 / 1280, EN and KO, 0 console errors, no horizontal scroll. Screens: shots/review_v47/after_side.png.
