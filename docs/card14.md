# Card 14 — 948 m whole-Moon map (prepared, not run) + finer 3D terrain at the polar sites

Soyun Jeong, 2026-11-14 (KST). Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.

## 1. 948 m map (`global_maps.py --ppd 32`): benchmark only — the full run has NOT been started

| Item | Value |
|---|---|
| Grid | 5760 × 11520 (0.95 km), 66.4 M points |
| Terrain | LDEM_64 (474 m) to 150 km, LDEM_16 (1.9 km) to 300 km, curvature exact, observer 2 m |
| Ephemeris | `web/data/ephem.bin` (`mock: false`), 2026–2030, `--step-h 3` = 14,608 samples |
| Store | `data/processed/gmaps_ppd32/` (git-ignored): 5 × 265 MB float32 + done mask = 1.33 GB, already allocated |
| **Done** | **10/5760 rows (2800:2810, lat +2.48…+2.20°)** — kept; the full run resumes after them |

### Timing
| Run | Threads | Time | Note |
|---|---|---|---|
| Main store, rows 2800:2810 (10 rows) | 4 | **672.4 s (67 s/row)** | Laptop on battery; a PowerShell memory probe ran every 5 s beside it; only ~1 core busy (698 s CPU time). Peak working set ~1.2 GB |
| Scratch store, 1 row (2800) | 1 | 195.7 s | Single thread; much slower than linear (hybrid-core scheduling suspected, unverified) |
| Scratch store, 1 row (2800) | 4 | 8.3 s | — |
| Scratch store, 1 row (1000), twice | 4 | 11.4 s, 10.9 s | — |
| Scratch store, 1 row (1000) | 8 | 7.6 s | — |

The scratch stores were in the session scratchpad and were deleted; they never touched `data/processed/gmaps_ppd32/`.

### Estimate for the remaining 5750 rows
| Threads | s/row (measured) | Wall time |
|---|---|---|
| 4 | ~11 | **~17.6 h** |
| 8 | 7.6 | **~12.1 h** |
| all 22 | not measured (not allowed now) | ~6–9 h if it scales like the ppd 8 run (4 → 14 threads = 2.2×); **unverified** |
| any, if conditions are like the first 10-row run | 67 | ~107 h |

- The difference between 67 s/row and 8–11 s/row shows that power and scheduling matter a lot.
- So run on **AC power**, in a visible terminal, with Windows power mode = best performance, and the lid **open**.
- The power scheme "SAMSUNG MODE" does not expose the lid-close action.
- Sleep is set to "never" on AC and on battery. Hibernate is 30 days (AC) / 3 days (DC). The script also blocks sleep while it runs.
- Export size (z0–z3, 170 tiles per layer + overviews) is estimated at roughly 60–80 MB from the ppd 8 export (133 files, 17 MB); unverified.

### Overnight command (ready, not started)
```powershell
powershell -ExecutionPolicy Bypass -File pipeline\run_ppd32_overnight.ps1 -CheckOnly    # pre-flight only
powershell -ExecutionPolicy Bypass -File pipeline\run_ppd32_overnight.ps1 -Threads 16   # while other lab jobs run
powershell -ExecutionPolicy Bypass -File pipeline\run_ppd32_overnight.ps1 -AllCores     # only when nothing else runs
```
`pipeline/run_ppd32_overnight.ps1`:
- **Pre-flight checks**: real ephemeris; existing store made with step 3 h and a non-mock ephemeris; DEMs present; free disk ≥ 5 GB; on AC power (refuses on battery unless `-AllowBattery`); other Python jobs (refuses `-AllCores` while they run unless `-Force`).
- **While running**:
  - keeps the PC awake (`SetThreadExecutionState`)
  - writes a timestamped log to `data/processed/logs/ppd32_<time>.log` (kept on failure)
  - resumes after a crash (up to 3 attempts; finished rows are kept)
  - never uses `--restart`
- **Export**: writes to **`web/data/gmaps_ppd32/`**, so the reviewed 3.8 km map in `web/data/gmaps/` is not overwritten.
- `-CheckOnly` was run on 2026-11-14 13:43. It refused because the laptop was on battery (82 %). It also listed one other Python job (`ansys.fluent.mcp`, lab automation).

## 2. Finer 3D terrain around the sites (`web/data/globe/`)

### Before card 14
From `index.json` (Sua's `build_globe_tiles.py`):
| Sites | Finest tile at the site | Source | Reach (min over 8 directions) |
|---|---|---|---|
| 17 non-polar | band z7, **66.6 m** spacing | SLDEM2015 59 m (PGDA 60 m for CHANDRAYAAN3) | 26–36 km |
| 15 polar, lat ≤ −83° | south z7, **34.2 m** | PGDA 20 m | 12–23 km |
| IM1 (−80.13°) | south z6, **68.4 m** | PGDA 60 m | 37 km |

- No south z8 existed: the builder only loads PGDA 20/60/80 m, all coarser than the z8 spacing (17.1 m).
- A full rebuild on this computer would use fewer fine DEMs than the original build and could degrade existing tiles. So card 14 **adds tiles only**.

### Added
`pipeline/build_site_hr_tiles.py` writes south **z8 (17.1 m spacing)** tiles from PGDA LOLA **10 m** windows.
- Source: `LDEM_83S_10MPP_ADJ.TIF`, fetched with card 2's unchanged `fetch_polar.fetch`: radius 25 km for SHACKLETON_RIM, 20 km for the other 14 polar sites.
- Download: 15/15 sites, 0 failures, ~26 min, 1.4 GB local cache (git-ignored).
- Same tile grid, projection, PNG height encoding and parent/child layout as `build_globe_tiles.py` (its functions are imported, not re-implemented).
- Only complete quads whose 4 children are 100 % covered by 10 m data are written (134 quads; 2 parents skipped at 91 % coverage).
- **536 new tiles, 17.9 MB** (largest tile 128.8 kB, unchanged). `index.json` gets the new entries appended plus `levels.south.8`, `sources["PGDA 10 m (south z8)"]` and `hr_tiles`. Every existing entry is unchanged (checked against a copy). Total 201.4 → 219.3 MB.
- `globe3d.js` was not changed: it reads the maximum level from `index.json`.
- **Real resolution**: DEM 10 m, displayed at 17.1 m vertex spacing. The 5 m product (87° S) was not used because it adds nothing at 17 m spacing. Nothing here is "5 m".

| Site | z8 at the site | z8 reach, min / median (km) |
|---|---|---|
| IM2 | yes | 13.5 / 22.0 |
| ARTEMIS_CABEUS_B | yes | 11.5 / 14.5 |
| ARTEMIS_HAWORTH | yes | 13.0 / 17.0 |
| ARTEMIS_MALAPERT | yes | 11.5 / 17.0 |
| ARTEMIS_MOUTON_PLATEAU | yes | 14.0 / 26.5 |
| ARTEMIS_MOUTON | yes | 13.0 / 25.5 |
| ARTEMIS_NOBILE_RIM1 | yes | 11.5 / 20.5 |
| ARTEMIS_NOBILE_RIM2 | yes | 10.5 / 15.5 |
| ARTEMIS_DE_GERLACHE_RIM2 | yes | 11.0 / 17.5 |
| ARTEMIS_SLATER_PLAIN | yes | 12.0 / 17.0 |
| SHACKLETON_RIM | yes | 12.0 / 19.0 |
| CONNECTING_RIDGE | yes | 14.0 / 19.0 |
| PEAK_NEAR_SHACKLETON | yes | 11.0 / 15.0 |
| DE_GERLACHE_RIM1 | yes | 11.5 / 17.0 |
| SHOEMAKER_RIM_A | yes | 12.0 / 14.5 |
| IM1 | **no**: outside the 83° S 10 m product; stays z6 68 m | — |

The ~30 km target is reached at 17 m only in some directions. Beyond the z8 patch the existing z7 (34 m) and z6 (68 m) tiles continue.
The 17 non-polar sites are unchanged: z7 66.6 m from SLDEM 59 m, which is about the native SLDEM resolution. A z8 band level would only oversample the 59 m data, so it was not added.

### Checks (`python pipeline/build_site_hr_tiles.py check`)
- All 536 tiles present, 259 × 259 px. Decoded heights equal the 10 m source within **0.251 m** (0.5 m encoding step).
- **462 shared tile edges identical** (max difference 0.0 m).
- Every tile has its z7 parent, and every quad is complete.
- Child − parent at coincident vertices (10 m vs the parent's 20/60/80 m data): mean +0.04 m, RMS 3.6 m, 99th percentile 17.5 m, max 164.5 m.
  - The maximum is in the Shackleton crater wall (−89.49°, 3.9 km relief), where 10 m resolves slopes that 20/80 m smooth.
  - Median per-tile RMS 0.46 m.
- `python pipeline/build_globe_tiles.py test`: projection + encoding OK.
- **3D viewer** (`web/globe_test.html`, local `python -m http.server`, Claude browser pane):
  - fresh load at SHACKLETON_RIM, range 2 km → 52 south/8 tiles requested, 0 pending
  - IM2: 100 km → no z8, 2 km → 64 z8
  - ARTEMIS_MALAPERT: 2 km → 40 z8
  - ARTEMIS_HAWORTH: 25 km (45° tilt) → 16 z8
  - APOLLO17 (non-polar): 2 km → band z7 (SLDEM) tiles
  - 0 tile-load warnings. A screenshot at Malapert (6 km, 55° tilt) shows no cracks.
  - The browser pane was hidden during these checks, so frames were driven with `globe.step()`.
- Tests: `pytest pipeline/tests pipeline/test_horizon.py pipeline/test_global_maps.py pipeline/test_relay_tower.py pipeline/test_run_relay.py pipeline/test_korea_links.py` → 80 passed. `python pipeline/check_contract.py` → PASS, 0 errors, 0 warnings.

## 3. Open items
1. Done (2026-11-14 21:00 KST): rows 0–3103 (CPU, this laptop) and 3103–5759 (Jiyong; CPU 3103–3454, CUDA 3455–5759) merged and verified; exported to `web/data/gmaps_ppd32/` (32.3 MB, web tiles ≈ 1.33 km/px at z3); PGDA 400 points: Sun MAE 2.61 pp (r 0.911), Earth MAE 3.42 pp (r 0.984). See `docs/card14_split_merge.md` §6 and `docs/card14_pgda.json`; why these differ from VALIDATION row 11: `docs/card14_pgda_analysis.md`. The web folder is still a proposal (contract §10 defines only `web/data/gmaps/`).
2. IM1 has no 10 m / 20 m tiles. The PGDA 20 m 80° S product could add z7 there; not done.
3. The z8 reach is 10.5–14 km minimum, not 30 km. Extending it would need wider 10 m windows and ~4× more tiles (web size).
4. The north cap has no PGDA data in our cache (unchanged).
