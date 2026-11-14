# 948 m map: z4 web tiles and deployment size

Soyun Jeong, 2026-11-14 (KST), requested by the team lead (Sua Kim). Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.

## 1. Why the web map stopped at z3
`pipeline/global_maps.py` `export()` (unchanged):
- tile size `TILE = 512`;
- finest level `zmax = max(2, int(round(math.log2(nlon / 1024.0))))`;
- level z is `1024·2^z × 512·2^z` px.

For the 948 m grid (nlon = 11,520): log2(11.25) = 3.49, so zmax = 3.

| Level | Image (px) | Tiles per layer | km per px at the equator (2π·1737.4 km / width) |
|---|---|---|---|
| z3 (finest so far) | 8,192 × 4,096 | 16 × 8 = 128 | 1.333 |
| **z4 (added)** | **16,384 × 8,192** | **32 × 16 = 512** | **0.666** |
| computed grid | 11,520 × 5,760 cells | — | 0.948 |

- z3 shows the map coarser than it was computed (8,192 < 11,520 columns).
- **z4 is the 948 m grid upsampled with the exporter's bilinear resampler. It shows every computed cell, but it is not a 667 m computation: no new terrain, horizon or ephemeris detail is added.** `index.json` says this in `added_levels[0].note`.
- The 3.8 km map (`web/data/gmaps/`, ppd 8, z0–z2) is not changed.

## 2. How z4 was made
`pipeline/gmaps_add_zoom.py add --store data/processed/gmaps_ppd32_merged --web web/data/gmaps_ppd32 --z 4` (46 s):
- It uses the exporter's own `global_maps.resample` / `colorize` / `COLORMAPS` / `TILE` and the same JPEG quality 88. Colouring is done one tile row at a time to limit memory; `colorize` works per pixel, so the result is the same.
- It writes only `tiles/{sun,earth,both}/4/{x}_{y}.jpg` and appends `{"z": 4, "width": 16384, "height": 8192, "nx": 32, "ny": 16}` to `index.json` → `tiles.levels`, plus a new key `added_levels` (method, note, time).
- It refuses to run if the level already exists, or if it is not the next level after the finest one.
- `global_maps.py` was **not changed**, so other exports keep their behaviour. A `--max-zoom` option in the exporter was not added; a separate tool was chosen so that z0–z3 are never re-encoded.
- Not changed (SHA256 before/after): the 516 existing files in `web/data/gmaps_ppd32/` (z0–z3 tiles, overviews, value PNGs) and the 133 files of `web/data/gmaps/`. Only `index.json` changed.
- The merged store `data/processed/gmaps_ppd32_merged/` was only read. Nothing was recomputed.

**Data contract:** the `index.json` format stays the same; `tiles.levels` simply has one more entry with the existing keys. `added_levels` is a new, optional key. The `gmaps_ppd32/` folder itself is still a proposal outside contract §10 (which defines only `web/data/gmaps/`). **Team lead to confirm.**

## 3. Checks (`python pipeline/gmaps_add_zoom.py check` → `docs/gmaps_ppd32_z4_check.json`) — PASS
| Check | Sun | Earth | Both |
|---|---|---|---|
| 1. tiles present (512 expected, 512 × 512 px) | 512 / 0 missing | 512 / 0 | 512 / 0 |
| 2. `index.json` z4 entry | registered | | |
| 6. values encoded: NaN / min / max | 0 / 0.000 / 0.794 | 0 / 0.000 / 1.000 | 0 / 0.000 / 0.602 |
| JPEG vs exact colours: mean / p99 / max \|ΔRGB\| | 1.30 / 9 / 79 | 1.01 / 14 / 96 | 0.97 / 10 / 100 |
| 3. step across tile edges vs inside (RGB): z4 / before JPEG / z3 | 2.54 vs 1.28 / 1.36 vs 1.10 / 3.55 vs 2.49 | 2.36 vs 1.34 / 1.45 vs 1.24 / 3.48 vs 2.73 | 2.00 vs 0.88 / 1.26 vs 1.04 / 2.76 vs 1.68 |
| 4. ±180°: mean \|first − last column\|; z4 / grid (same metric) | 0.0077 / 0.0082 | 0.00022 / 0.00023 | 0.00011 / 0.00013 |
| 5. poles: top / bottom row NaN | 0 | 0 | 0 |
| 8. z4 box-averaged 2× vs z3 values: mean / p99 \|Δ\| | 0.0031 / 0.033 | 0.0037 / 0.070 | 0.0023 / 0.034 |
| 8. area mean z4 / z3 | 0.43512 / 0.43512 | 0.43502 / 0.43501 | 0.20001 / 0.20000 |
| 8. z4 at grid cell centres vs grid (43,836 cells): mean / p99 \|Δ\| | 0.0030 / 0.031 | 0.0034 / 0.068 | 0.0022 / 0.032 |
| no-data colour (40, 40, 40) in tiles | 3 px (JPEG, no NaN behind them) | 0 | 0 |

Notes:
- **Tile edges (3).** Before JPEG the step across a tile edge equals the step inside (the tiles are aligned). The extra step after JPEG comes from encoding each tile separately; the existing z3 tiles have the same effect, with larger steps.
- **±180° (4).** The step equals one grid-cell step of the computed map itself (the exporter's resampler does not wrap). It is the same as at z3.
- **Value differences (8).** The differences to z3 and to the grid are the bilinear interpolation (largest at crater walls and terminator edges); the area means agree.
- **7. Loader test.** **No code in `web/` loads `gmaps` or `gmaps_ppd32` tiles today**: searched in `web/js/*.js` and `web/*.html` on main and on every remote branch. The existing 2D (`local_map.js`) and 3D (`globe3d.js`, `web/data/globe/`) views use other data. So no app loader could be tested.
  - Instead I used a stand-alone test page, not committed. It chooses the coarsest level whose px/deg ≥ the requested screen px/deg, from `index.json` only, and fetches `tiles.url`. It ran in the browser pane over a local read-only server.
  - Whole Moon (2.8 px/deg) → z0. 20 px/deg → z3. 30 / 45 / 60 / 120 / 200 px/deg → **z4**. 0 failed tile loads, including views centred on +180°, −180°, 89.9° N and SHACKLETON_RIM. The 3.8 km map stayed at its own finest level z2.
  - The colour shown at the view centre equals the decoded z4 tile pixel exactly. Example: SHACKLETON_RIM (171, 120, 3) at 60 px/deg and (203, 151, 29) at 120 px/deg, where the grid changes by up to 0.34 per cell. At APOLLO17 it is within 2 RGB levels of the grid value's colour.
- **For the UI owner.** A loader should take its max zoom from `index.json` `tiles.levels`, not from a fixed number.

## 4. Deployment size (GitHub Pages)
`.github/workflows/pages.yml` uploads the checked-out `web/` folder of `main` (`actions/upload-pages-artifact`, `path: web`). Only tracked files count; `data/processed/` (the 1.33 GB stores, the 10-minute ephemeris) is git-ignored and never deployed. No Git LFS (`git lfs ls-files` empty).

| | Files | MB (10⁶ bytes, tracked) |
|---|---|---|
| `web/` on main (`19867c3`, already includes the 948 m z0–z3) | 6,121 | 663.34 |
| of which `web/data/gmaps_ppd32/` z0–z3 + overviews | 517 | 32.25 |
| of which `web/data/gmaps/` (3.8 km) | 133 | 16.69 |
| **added by this PR: z4 tiles** | **1,536** | **40.18** (Sun 18.76, Earth 11.34, Both 10.09; mean 26.2 kB, max 99.4 kB) |
| `web/` after this PR | 7,657 | **703.52** |
| other open PRs touching `web/` (14 Nov, 23:00 KST) | — | +0.2 (#42) |
| **expected deployment** | | **≈ 703.7 / 900 MB** (≈ 196 MB headroom) |

- Largest single file in `web/`: 6.57 MB (`globe/moon_color_8k.jpg`), far below GitHub's 50 MB warning and 100 MB limit.
- The JPEG quality stays at 88, the same as z0–z3. The budget did not require stronger compression.
