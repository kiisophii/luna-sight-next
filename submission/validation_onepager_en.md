# Validation in one page — Luna Sight — Lunar Landing Site Navigator (Team Ginkgo Orbit)

Sources: `docs/VALIDATION.md`.

All 18 published data products were re-checked by someone other than their author, who recomputed a sample with separate code (site coordinates: re-read from the sources); on identical inputs, differences were at most 0.15 percentage points, 0.004° or 0.37 m (tiles, within encoding steps); known gaps are listed in docs/verification_ledger.md. Sun and Earth directions match
NASA JPL Horizons to 0.000041° in 34,296 comparisons. Terrain horizons match
brute-force code to ~0.02°. Against NASA's 18.6-year south-polar illumination maps (PGDA), sunlight at 240
points differs by 1.66 percentage points on average (r = 0.985) and Earth visibility, with PGDA's any-part rule, by 1.24 points
(r = 0.990; the app's stricter centre rule: 3.87). Apollo 11–17
Sun elevations at landing match NASA's Apollo Lunar Surface Journal to 0.05°, and 5,520 live-website numbers
match the data.

**Limits.** Non-polar sites skip terrain closer than 200 m (sunlight 0.12–0.80
points lower when included, five sites). The app's Earth-centre rule reads 4.6–5.6
points below PGDA's at the named sites. There is no PGDA reference north of 75° S. Mission
end-of-operations dates are only a sunset proxy. Four polar points are region centres whose sunlight varies by
up to 51.8 points within 300 m. A 10-min instead of 1-h step changes sunlight by at most 0.03 points; a 1–10 m instead of 2 m observer height, by up to 10.7 points at a steep polar site (ARTEMIS_HAWORTH).

| Check | Independent source | Difference | Criterion | Pass |
|---|---|---|---|---|
| Sun & Earth directions, 2020–2038 | NASA JPL Horizons | max 0.000041° | < 0.01° | ✅ |
| Terrain horizons (17 non-polar sites, 720 azimuths) | own brute-force code | RMS ≤ 0.026° | ~0.02° | ✅ |
| Sunlight / Earth visibility, 240 points 85–90° S | NASA PGDA (18.6 years) | MAE 1.66 / 1.24 pp (Earth: PGDA any-part rule; app centre rule 3.87) | — (reported) | ✅ |
| 948 m map, 400 points 75–85° S, same Earth rule | NASA PGDA 120 m | MAE 2.61 / 2.42 pp | — (reported) | ✅ |
| 948 m map, GPU vs original CPU, 600 cells | unchanged CPU code | max 0.000003 pp | < 0.5 pp | ✅ |
| 5 largest named-site residuals | PGDA and our ±300 m ranges | 5/5 within spread | inside either range | ✅ |
| Coordinate-uncertainty grids, 30 random nodes | own brute-force code | max 0.021 pp | ≤ 1 pp | ✅ |
| Sun elevation at Apollo 11–17 landings | NASA Apollo Lunar Surface Journal | max 0.05° | < 0.1° | ✅ |
| Moon direction from KDSA and NASA DSN | NASA JPL Horizons | max 0.0012° | < 0.05° | ✅ |
| Website numbers vs data (5,520 values) | data files + app code | 0 mismatches | exact text | ✅ |

pp = percentage points.
