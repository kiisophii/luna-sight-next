# Card 14 — why the PGDA numbers differ (VALIDATION row 11 vs the 948 m map)

Soyun Jeong, 2026-11-14 (KST), requested by the team lead (Sua Kim) before PR #35 / #39 are merged.
Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
Script: `pipeline/analyze_card14_pgda.py` → `docs/card14_pgda_analysis.json` (all numbers below). `docs/VALIDATION.md` is not changed.

**Short answer.** Row 11 (Sun 2.19 pp, Earth any 1.73 pp) and card 14 (Sun 2.61 pp, Earth centre 3.42 pp) measure different things:
1. Row 11 is computed **at the exact 400 points**, while card 14 reads the **stored map cell** that contains each point. The cell value is computed at the cell centre, 0.24 km away from the point on average (max 0.47 km).
2. Row 11's Earth number uses **any part of the Earth disc** (the PGDA definition), while the map stores the **Earth centre**.
3. Row 11 combines two codes: the Sun number is from the engine, the Earth number is from the card 9 independent re-implementation (720 azimuths).

**Ruled out, with numbers:** the period (5 vs 18.6 years) and the time step (3 vs 2 h) hardly change the Sun error. **CPU vs CUDA is identical at all 400 cells.** No code or data error was found.

## 1. Where the row 11 numbers come from (reproduced)
| Row 11 text | Code | Points | Period, step | Definition | Reproduced here |
|---|---|---|---|---|---|
| engine Sun MAE 2.19 pp, r 0.938 | `global_maps.py validate --n 400` (production engine, 360 az) | exact 400 points | 2020-01-01 – 2038-07-31, 2 h (81,444 samples, `data/processed/ephem_2020-2038_2h.npz`) | Sun mean disc | run B3: **2.185 pp, r 0.9379** |
| independent Sun MAE 2.12 pp, r 0.940 | `verify_card9.py` (own horizon code, 720 az, 200 m / 500 m steps) | exact 400 points | same 18.6 years, 2 h | Sun mean disc | cache: **2.119 pp, r 0.9399** |
| Earth (any) MAE 1.73 pp, r 0.989 | `verify_card9.py` | exact 400 points | same | **Earth any part of the disc** | cache: **1.733 pp, r 0.9891** |

- The card 9 values come from the per-point cache `data/processed/verify_card9_pgda_points.jsonl`.
- 5 cached points (k = 0, 99, 199, 299, 399) were recomputed fresh with `verify_card9.py`'s functions: max difference 5e-6.
- None of the row 11 values is read from a stored map, although the row is titled "Whole-Moon 3.8 km map engine".
- The engine's Earth (centre) value at these points is 3.137 pp (card 9 doc), but that number is not in row 11.

Common to everything below:
- the same 400 points (`verify_card9.random_points`, seed 42, uniform by area in 75–85° S);
- the same PGDA files (`AVGVISIB_75S_120M_201608[_EARTH].TIF`) and reader (`verify_card9.Pgda`: nearest 120 m pixel, polar stereographic `R = 1737.4 km`, pixel-is-area);
- Sun = mean visible fraction of the disc (radius 0.2666°) everywhere.

## 2. Stored maps, same window 2026–2030 (no recomputation)
| Map value at the point | Sun MAE | RMSE | bias | **r** | Earth (centre) MAE | RMSE | bias | **r** |
|---|---|---|---|---|---|---|---|---|
| **948 m**, nearest cell | **2.609** | 5.353 | +0.971 | **0.9108** | **3.423** | 6.638 | −1.611 | **0.9837** |
| 948 m, bilinear between cell centres | 2.388 | 4.912 | +1.142 | 0.9273 | 3.232 | 5.787 | −1.441 | 0.9878 |
| **3.8 km**, nearest cell | **4.337** | 7.446 | +1.272 | **0.8232** | **5.327** | 10.519 | −1.232 | **0.9566** |
| 3.8 km, bilinear between cell centres | 3.967 | 6.802 | +1.510 | 0.8539 | 4.796 | 9.046 | −1.196 | 0.9681 |

(pp = percentage points; MAE, RMSE and bias in pp.)

- Both stores average 2026-01-01 … 2030-12-31. The 948 m store uses 3 h (14,608 samples) and the 3.8 km store 2 h (21,912 samples); this step difference is negligible (§4, factor 2).
- Point to cell centre: 948 m mean 0.241 km (max 0.474); 3.8 km mean 0.954 km (max 1.896).
- "Nearest" = the cell that contains the point (as in `validate_card14_pgda.py`). "Bilinear" interpolates between the 4 nearest cell centres; it is an evaluation choice, not something the web map does.
- On every metric except the Earth bias, the 948 m map is closer to PGDA than the 3.8 km map.

## 3. Point recomputation with the production engine (400 points only)
`global_maps.Engine`, LDEM_64 to 150 km + LDEM_16 to 300 km, 360 az, observer 2 m. Earth "any disc" uses the same engine horizon mask with `verify_card9.fractions()`. With the same mask, `fractions()` reproduces the engine's Sun and Earth-centre values exactly (difference 0.0 in every run).

| Run | Where | Period, step | Sun MAE / r | Earth centre MAE / r | Earth any-disc MAE / r |
|---|---|---|---|---|---|
| B1 | exact points | 2026–2030, 3 h | 2.183 / 0.9380 | 2.995 / 0.9878 | 2.087 / 0.9884 |
| B2 | exact points | 2026–2030, 2 h | 2.182 / 0.9380 | 2.994 / 0.9878 | 2.087 / 0.9884 |
| B3 | exact points | 2020–2038, 2 h | **2.185 / 0.9379** | 3.137 / 0.9879 | 1.827 / 0.9889 |
| B4 | 948 m cell centres | 2026–2030, 3 h | 2.609 / 0.9108 | 3.423 / 0.9837 | 2.417 / 0.9847 |
| B5 | 3.8 km cell centres | 2026–2030, 2 h | 4.337 / 0.8232 | 5.327 / 0.9566 | 4.737 / 0.9574 |
| B6 | exact points, **near DEM LDEM_16** (1895 m) | 2026–2030, 3 h | 4.953 / 0.7973 | 4.667 / 0.9616 | 5.234 / 0.9575 |
| C | exact points, card 9 independent code (720 az) | 2020–2038, 2 h | 2.119 / 0.9399 | 3.249 / 0.9875 | **1.733 / 0.9891** |

B4 and B5 equal the stored maps exactly (same numbers as §2 "nearest"); see factor 6.
The stored maps are 2026–2030 only; the 18.6-year values (B3, C) exist only at the 400 recomputed points.

## 4. Factors, one at a time
| # | Factor | Test | Change between the two runs (pp) | Effect on PGDA MAE |
|---|---|---|---|---|
| 1 | 5 years vs 18.6 years | B2 vs B3 | Sun mean \|Δ\| 0.093 (max 0.43); Earth centre 0.342 (max 1.93) | Sun 2.182 vs 2.185 (**none**); Earth centre 2.994 vs 3.137; Earth any 2.087 vs 1.827 (the 18.6-year run is 0.26 pp closer) |
| 2 | 3 h vs 2 h step | B1 vs B2 | Sun 0.003 (max 0.03); Earth 0.009 (max 0.06) | **none** (≤ 0.001 pp) |
| 3 | value at the cell centre instead of the point | B4 vs B1 (948 m), B5 vs B2 (3.8 km) | 948 m: Sun 1.233 (max 20.3), Earth 1.286 (max 47.3); 3.8 km: Sun 3.171 (max 30.7), Earth 3.701 (max 58.9) | Sun 2.18 → **2.61** (948 m) and → **4.34** (3.8 km). **Largest factor for the Sun** |
| 4 | terrain resolution | B6 vs B1 (LDEM_16 instead of LDEM_64 near the point) | Sun 3.759 (bias +3.61); Earth 3.546 | Sun 2.18 → 4.95 with 1.9 km terrain |
| 5 | Earth any-disc vs centre | same masks, B1 and B3 | any − centre = +3.04 pp on average (always ≥ 0, max 14.8) | B4: 3.423 (centre) vs 2.417 (any); B3: 3.137 vs 1.827. **Largest factor for the Earth** |
| 6 | CPU vs CUDA | stored 948 m value at the 400 cells vs this laptop's CPU engine at the same cell centres | sun, earth, both, h0, maskmax: **400 / 400 identical at float32** (max \|Δ\| 0.0) | **none** |

Notes on the factors:
- **1 (period).** PGDA averages 18.6 years (exact dates not stated), so the 5-year window should matter. In this band it does not for the Sun, and only by about 0.26 pp of MAE for the Earth.
- **3 (cell centre).** This is how the stored map is defined (`global_maps.py`: one value per cell, at the cell centre). It is not an error. The finer grid reduces it, and bilinear reading reduces it further (§2).
- **4 (terrain).** Coarser terrain clearly hurts, so terrain resolution matters. Whether terrain finer than 474 m (like PGDA's own, resolution not stated) would bring the error below 2.18 pp **was not tested**: no finer DEM covers these 400 points in our data. The Sun error correlates with the local PGDA 3 × 3 spread (r = 0.618) and not with our horizon height (r = −0.09). This fits small-scale terrain the 474 m DEM cannot resolve, but it is **not proven**.
- **5 (definition).** The map's Earth is the stricter centre definition by design (`global_maps.py` docstring, contract section 0). Comparing it with PGDA's any-disc product therefore shows a negative bias. With the same definition as PGDA, the 948 m cells give 2.42 pp.
- **6 (CPU vs CUDA).** All 400 evaluation cells are in rows 5281–5595, which Jiyong computed with CUDA (rows 3455–5759). Row 3103, the split-overlap row, was computed with `global_maps.py` on the **CPU of Jiyong's PC** (his manifest: CPU rows 3103–3454). So the row 3103 comparison (11,520 columns identical) was CPU vs CPU. The CUDA check is this table plus the 42 random CUDA-row points in `docs/card14_split_merge.md` §6, which were also identical. The 3.8 km store also equals its recomputation (max \|Δ\| 0.0).
- **720 vs 360 azimuths / marching.** Independent code C vs engine B3 at 18.6 years: Sun MAE 0.37 pp between them (max 5.4). Their PGDA MAE differs by 0.07 pp (Sun) and 0.09 pp (Earth any).

### From row 11 to card 14, step by step (Sun)
2.119 (C, 720 az, 18.6 y, point) → 2.185 (engine 360 az, B3) → 2.183 (5 years, 3 h, B1) → **2.609 (948 m cell centre = stored map)** → 4.337 (3.8 km cell centre = stored map).

### Earth
1.733 (C, any disc, 18.6 y) → 1.827 (engine, B3) → 2.087 (5 years, B1) → 2.417 (948 m cell centre, B4) → **3.423 (centre definition = stored map)**.

The steps are taken in this order. With another order the share per step changes a little, but the totals do not.

## 5. Is the 948 m map worse anywhere?
- **Than row 11: yes** (Sun 2.61 vs 2.19, Earth 3.42 vs 1.73). This is the evaluation method (stored cell-centre value vs the exact point, Earth centre vs any disc), not a code or data error. At the exact points, the same engine and the stored map's own 5-year, 3 h ephemeris give 2.18 pp (Sun) and 2.09 pp (Earth any).
- **Than the 3.8 km map:**
  - MAE, RMSE and r are better for Sun and Earth, with both nearest and bilinear reading.
  - Only the Earth (centre) bias is larger: −1.61 vs −1.23 pp (bilinear −1.44 vs −1.20). Its MAE is lower (3.42 vs 5.33), so this is not a worse fit.
  - The cause of the bias difference is **not determined**. A plausible reading: at 3.8 km the cell offsets scatter both ways and partly cancel the definition bias. This was not tested.
- **No error was found** in the code or the data:
  - the stores reproduce exactly from the engine (B4, B5);
  - CPU = CUDA;
  - the engine agrees with the independent code to 0.37 pp MAE.

## 6. Not done / open
- 18.6-year values exist only at the 400 recomputed points. The stored maps stay 2026–2030 (contract ephemeris). No 18.6-year map is claimed.
- The effect of terrain finer than 474 m on these points is untested (no DEM).
- PGDA's exact 18.6-year dates, observer height and terrain resolution are not stated (as in card 9).
- `python pipeline/check_contract.py`: the card 15-B windows-provenance check needs Node.js, which is not installed on this laptop, so it could not run here. All other checks pass (§7 of the PR text).
