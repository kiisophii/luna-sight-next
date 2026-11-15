# Custom points near the south pole: PGDA browser terrain (s4, Sua)

Why: the phase-3 browser horizon for a user-defined point uses LOLA LDEM_64 at ~948 m. Near the south pole
it differed from the card-8 horizons by a median 0.96° RMS (max 4.87°) — too much where the Sun is only
1–2° above the horizon (`docs/VALIDATION.md` row 14, before this change).

## What changed
- **Data** `web/data/hterrain/polar_s/` (255.6 MB, written by `pipeline/build_polar_terrain.py`, contract §14b).
  NASA PGDA south-polar LOLA DEMs (https://pgda.gsfc.nasa.gov/products/90), same files and projection as card 2/8,
  read by HTTP Range, stored as 512-px tiles (int32 base + int16 planar residuals of heights in 0.25 m steps, gzip;
  every tile decoded and compared exactly when written).

  | Level | Source | Used to | For points | Tiles | Size |
  |---|---|---|---|---:|---:|
  | p20 | LDEM_80S_20MPP_ADJ.TIF, 20 m | 3 km | ≥ 85.5° S | 642 | 89.5 MB |
  | p60 | LDEM_60S_60MPP_ADJ.TIF, 60 m | 3 km | ≥ 75° S | 770 | 143.5 MB |
  | p240 | LDEM_60S_240MPP_ADJ.TIF, 240 m | 150 km | ≥ 75° S | 90 | 22.7 MB |
  | p5, p10 (PR #63) | native ldem_87s_5mpp / LDEM_83S_10MPP_ADJ | 3 km | only within 4 km of the 16 catalogue sites | 118 + 92 | 19.9 MB |

  Beyond these, the phase-3 grids (LDEM_64 ~948 m to 150 km, LDEM_16 to 300 km).
- **Engine** `web/js/hterrain.js`: one sampling chain (first source whose range covers the distance and has data,
  as `horizon.sample_chain`); on the polar path the march starts at 5 m with 8000 steps (card-8 settings). North of
  75° S nothing changes (old and new code give identical masks: max difference 0 at 6 test points).
- **Worker** loads `polar_s/index.json` if present. A polar point fetches ~30 tiles (~5 MB) the first time;
  Node timing 0.7 s median, 1.1 s max per point.
- **UI** (`custom_site.js`, `app.js`, `i18n.js`): the resolution text for the polar path, an "Accuracy at this point"
  line with the measured numbers for the point's latitude band, a **"Lower accuracy here"** badge (also a warning tag
  on the site card) when that band misses the target, and the same badge for points north of 75° N (no polar
  terrain there; the ~948 m grid is used and not validated in the north).

## Validation (`python pipeline/validate_custom_polar.py`, report `docs/custom_polar_validation.json`)
Reference = the card-8 chain run by `pipeline/horizon.py` (PGDA 5/10/20/60/80/240 m windows where the products
cover the point, then LDEM_64/16; 5 m start, 8000 steps):
- 16 catalogue south-polar sites: card-8 masks in `web/data/horizon/`. When this validation ran, SHACKLETON_RIM had no
  horizon after the card-15 coordinate fix, so its reference was run here with the same chain
  (`data/processed/custom_polar/ref/`, not committed); main now has card 13's recomputed SHACKLETON_RIM horizon (same chain).
- 30 random points (`pipeline/custom_polar_reference.py`, seed 20261114, 10 per band 75–80/80–85/85–90° S,
  area-uniform). Synthetic, not landing sites. One window (RANDPOLAR_3_04, 5 m) has no 5 m data; the chain falls
  back to 10 m, as card 8 does.
Sun / Earth fractions: 2026–2030, 2 h step, app definitions. Target (integrator): median RMS ≤ 0.2° and |Δsun| ≤ 2 pp
at every point.

| Group | n | Before: RMS median / max (°) | Before: \|Δsun\| median / max (pp) | After: RMS median / max (°) | After: \|Δsun\| median / max (pp) | After: \|ΔEarth\| max (pp) | Target |
|---|---:|---|---|---|---|---:|---|
Re-run 2026-11-15 on main `3086143`, after PR #63 added sparse native PGDA 5 m / 10 m tiles (to 3 km) within 4 km
of the 16 catalogue sites. "Before" is still the global path (`--no-polar`); "after" is the current polar path.

| Group | n | Before: RMS median / max (°) | Before: \|Δsun\| median / max (pp) | After: RMS median / max (°) | After: \|Δsun\| median / max (pp) | After: \|ΔEarth\| max (pp) | Target |
|---|---:|---|---|---|---|---:|---|
| Catalogue sites | 16 | 0.975 / 4.866 | 4.45 / 33.74 | **0.027 / 0.085** | 0.08 / 0.33 | 0.51 | ✅ |
| Random points | 30 | 0.652 / 4.031 | 0.94 / 30.28 | **0.027 / 0.165** | 0.06 / 0.42 | 0.49 | ✅ |
| All, 75–80° S | 10 | 0.772 / 3.836 | 0.82 / 30.28 | 0.021 / 0.054 | 0.03 / 0.20 | 0.38 | ✅ |
| All, 80–85° S | 14 | 0.696 / 4.866 | 2.08 / 33.74 | 0.037 / 0.163 | 0.10 / 0.42 | 0.49 | ✅ |
| All, 85–90° S | 22 | 0.867 / 4.031 | 2.48 / 26.91 | 0.028 / 0.165 | 0.10 / 0.36 | 0.51 | ✅ |

- Previous run (before PR #63, 20 m / 60 m near field everywhere): catalogue 0.085 / 0.177° and |Δsun| max 2.40 pp
  at PEAK_NEAR_SHACKLETON (the one point over 2 pp, shown in the app as "Lower accuracy here" for 85–90° S).
  Now PEAK_NEAR_SHACKLETON is +0.08 pp (RMS 0.027°); the largest catalogue sunlight difference is IM1 +0.33 pp
  (80° S, no 5/10 m patch there), the largest random one RANDPOLAR_2_08 +0.42 pp. No band misses the target, so the
  south-polar "Lower accuracy here" badge no longer appears; the band accuracy line still shows the numbers.
- **Remaining limit:** outside the 4 km patches, 85–90° S points use 20 m near-field terrain (the 10 random test points
  there: |Δsun| ≤ 0.36 pp). Sharp peaks/rims away from the catalogue sites were not tested individually.
  Largest Earth difference: CONNECTING_RIDGE +0.51 pp (previously ARTEMIS_HAWORTH +3.17 pp; no Earth target).
- Implementation: browser JS vs a Python twin on the same tiles (horizon.py engine) at 6 points: RMS ≤ 1.4e-11°,
  max 1.1e-10°. Those 6 are random points without 5/10 m tiles; the same twin at PEAK_NEAR_SHACKLETON and
  SHACKLETON_RIM (5 m) and ARTEMIS_CABEUS_B (10 m) gave RMS ≤ 2.3e-11°, max 2.6e-10° (separate run, not in the report).
- Design checks (scratch runs, not committed): near-field 20 m to 3 km vs to 10 km changed the catalogue median only
  0.063° → 0.061°; 40 m / 60 m / 80 m / 120 m near field gave medians 0.098° / 0.189° / 0.224° / 0.293° on the rims.

## Limits
- The badge is per latitude band (n = 10 / 14 / 22 points), not per point; within a band the error at a given point
  can be larger than the band's worst test point.
- Terrain inside 5 m, sub-pixel obstacles and PGDA vertical accuracy are not resolved (as card 8).
- North pole: not done (PGDA north-polar products were not added). 

## Reproduce
```
python pipeline/build_polar_terrain.py --levels p20,p60,p240 --to-km 3,3,150 --level-edges=-85.5,-75,-75 --lat-edge=-75
python pipeline/custom_polar_reference.py points && python pipeline/custom_polar_reference.py fetch && python pipeline/custom_polar_reference.py compute
python pipeline/custom_polar_reference.py fetch --points <file with SHACKLETON_RIM> && ... compute --points <same>
node pipeline/check_custom_horizon.mjs before.json --no-polar @all46.json
node pipeline/check_custom_horizon.mjs after.json @all46.json
python pipeline/validate_custom_polar.py --before before.json --after after.json
```
PGDA throttles each connection (~0.2–0.5 MB/s); `pipeline/polar_prefetch.py` downloads cache blocks with parallel
Range requests (same checks as `fetch_polar.RangeFile`). Building all three levels took ~1 h here.
