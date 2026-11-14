# Verification ledger — who checked each published data product

One row per data product in `web/data/` (main `115d285`, web version 26). Every entry is taken from what the
repository records: merge-commit messages on main (short hash), integrator rows in `docs/SI_USAGE.md` (line number),
the validation table `docs/VALIDATION.md` ("row N" = full-table row), and the products' own check files.
If no check is recorded, the cell says so. Checks of all entries: `python pipeline/verify_ledger.py`.

**Status rule.**
- **Independently verified**: someone other than the person who computed the product recomputed part or all of its
  values with their own code, and the recorded result agrees. "Integrator" = Sua Kim at merge time; "other member" =
  another team member in a separate pull request.
- **Author-verified only**: the only recorded checks were run by the person who computed the product (even if with
  separate code), or the integrator only re-ran the same code / compared file diffs.
- **Not verified**: no check recorded.

Most independent checks are **samples** (a few sites, nodes, azimuths or cells); the "Scope" words say which.
Team: Minchul Kim, Jiyong Sung, Soyun Jeong, Dongju Kim, Sua Kim (integrator). All computation was done with AI help
(Claude Code), as logged in `docs/SI_USAGE.md`.

| # | Product (`web/data/`) | Computed by (card / PR, member) | Author-side verification | Independent recomputation (integrator at merge, or other member) | Commit / PR | Status |
|---|---|---|---|---|---|---|
| 1 | `sites.json` (33 sites) | Card 4, PR #5, Minchul (`a09b0db`); SHACKLETON_RIM moved to the published rim point, card 15, PR #16, Minchul (`648adfd`); 4 display labels, Minchul (`00bb8a5`) | Source audit `docs/sites_source_audit.json`; AI link check: the 24 checkable sites match the source pages within 0.01°, the 9 Artemis regions not confirmed (`docs/source_link_ai_report_2026-11-14.md:9`); coordinate audit: all 33 pairs equal the stated source pair, max 0.000 m (`docs/site_coordinate_audit.md:24`) | **None recorded.** Merge `34b14b9` (PR #5): no check listed. Merge `170d483`: diff check only (only `name`/`name_ko` of 4 sites changed) | `34b14b9`, `4fd2225`, `170d483` | Author-verified only |
| 2 | `ephem.bin`, `ephem.json` (Sun/Earth 2026–2030, hourly) | Card 1, PR #2, Minchul (`d89c42a`) | vs JPL Horizons: 1,452 comparisons, max 0.000016° (app float32 0.00044°) (row 1); 6 real sites max 0.000034° (row 2) | **Other member (Dongju, card 10 check, PR #11):** own code without `ephem.py`: the 21,912 overlapping rows of the 18.6-year file are bit-identical to `ephem.bin`, and that file matches Horizons in 34,296 comparisons, max 0.000041° (row 3; `docs/card10_npz_independent_check.json:30`). Integrator: none recorded for `ephem.bin` itself (merge `b7f499d`) | `b7f499d` (PR #2), `d360288` (PR #11) | Independently verified (other member) |
| 3 | `horizon/` (33 terrain masks) | Card 8, PR #8, Jiyong (16 south-polar, `5bde5df`); card 9, PR #9, Soyun (17 non-polar, `7de0271`); SHACKLETON_RIM recomputed in PR #14, Jiyong (`d477409`) | Polar: brute-force re-march 2.5 m steps, 2 sites × 10 azimuths, max 0.00053° (row 6, Jiyong); non-polar: own brute-force code, all 720 azimuths, max 0.012–0.219°, RMS ≤ 0.026° (row 7, Soyun) | **Integrator, merge `a7a0978` (PR #14):** brute-force DEM horizon at 10 azimuths for SHACKLETON_RIM, max diff 0.0035°. PR #8 merge: tests, contract check, horizon coordinates vs `sites.json` only (`docs/SI_USAGE.md:38`); PR #9 merge `3d7d86d`: no check listed. Scope: 1 of 33 sites | `491999e` (PR #8), `3d7d86d` (PR #9), `a7a0978` (PR #14) | Independently verified (sample) |
| 4 | `metrics/` (33 sites, 2026–2030) | Card 10, PR #12, Dongju (`5e105e7`, incl. Minchul's PR #6); SHACKLETON_RIM re-run in PR #14, Jiyong | **Other member (Minchul):** separate Python port = app `core.js` on 3 fixtures and all 33 sites (row 13) | **Integrator:** `a7a0978`: SHACKLETON_RIM metrics recomputed from `ephem.bin`, exact match; `4a760de`: own loop for SHACKLETON_RIM, ARTEMIS_HAWORTH, APOLLO17, 60-month hour-weighted means = `metrics/<ID>.json` to 6 dp; `7ddda73`: visible hours = metrics fraction × 43,824 exactly (same 3 sites). Re-running the same code reproduced all 33 files byte-for-byte (`2b05c2c`, reproduction, not independent) | `2b05c2c` (PR #12), `a7a0978`, `4a760de`, `7ddda73` | Independently verified (sample: 3 sites) |
| 5 | `relay/` (33 sites, towers 5–50 m) | Engine: Sua (s4-relay-tower-sua); 33-site run: card 13, PR #14, Jiyong (`d477409`) | Separate verifier without production geometry, 3 sites: max 0.0011 pp, 30-epoch mismatches 0 (row 18, Jiyong) | **Integrator:** `a7a0978`: own 15 m network line of sight + tower Earth visibility at 20 hours, 20/20; `bab473b`: ARTEMIS_CABEUS_B direct 29.6367 %, 15 m single tower 85.743 % vs 85.727 % (own tower horizon + LOS); `42d3a21`: SHACKLETON_RIM 30-day spot check 342 h / 378 h. Note: the integrator also wrote the relay engine | `a7a0978` (PR #14), `bab473b` | Independently verified (sample) |
| 6 | `korea/` (station visibility, KDSA/DSN windows) | Sua (`dd114ff`, `5284299`) | — | **Other member (Dongju, card 16, PR #13):** `stations.json` Moon ≥ 10° bits vs Horizons for all 43,824 h × 4 stations: 2 of 175,296 differ, both within 0.0008° of 10°; Moon az/el max 0.0012°; link hours for 5 sites by brute force within 1 h (rows 15–17, `docs/korea_links.md` §2). Not compared: the minute-level `windows_*.json` and `kdsa_daily_kst.json`. Integrator: merge `5804e63` lists no check | `5804e63` (PR #13) | Independently verified (other member; `stations.json` only) |
| 7 | `validation.json` (PGDA comparison, 240 points + 16 named sites) | Card 11, PR #7 and #10, Dongju (`c5b8fc0`, `a15b2c5`); Shackleton refresh, Dongju (`c6b018e`) | PGDA truth extraction self-test: 5 points identical, projection 0.000 m (row 12, card 5, Dongju) | **Integrator:** statistics recomputed from the 240 points (`docs/SI_USAGE.md:34`); named MAE/bias recomputed (`:38`); `067f7c8`: SHACKLETON_RIM named row recomputed from the merged horizon with an own Skyfield 2020–2038 ephemeris, exact (0.84488 / 0.53847), PGDA pixel read directly (0.87060 / 0.53748) | `5da68cd` (PR #7), `09a70f9` (PR #10), `067f7c8` | Independently verified (sample + statistics) |
| 8 | `gmaps/` (3.8 km whole-Moon map) | Engine: Sua (s2-global-maps-sua); run: card 9, PR #9, Soyun (`7de0271`) | Own re-implementation at 400 points 75–85° S: engine vs independent code MAE 0.37 pp (row 11, Soyun); cell-centre recomputation equals the stored map (`docs/card14_pgda_analysis.md`, run B5, Soyun) | **None recorded for the map values.** Merge `3d7d86d`: no check listed. Merge `1c950be` re-derived the PGDA statistics from the stored map (Sun 4.337 pp, r 0.8232): a statistics check, not a recomputation | `3d7d86d` (PR #9) | Author-verified only |
| 9 | `gmaps_ppd32/` (948 m whole-Moon map) | Card 14, PR #35/#39: CPU rows and merge Soyun (`5237b76`), CUDA rows Jiyong | CPU vs CUDA identical at 400 cells (Soyun, `docs/card14_pgda_analysis.md`); 600 latitude-stratified cells, max 2.96 × 10⁻⁶ pp (Jiyong, PR #41) | **Integrator:** `1c950be`: 10 overview pixels (5 CPU rows, 5 CUDA rows, 2 poleward of 85° S) recomputed with the CPU engine and the export's resampling: 30/30 values identical; `086a9ed`: 6 cells recomputed, max 1.3 × 10⁻⁶ pp | `1c950be` (PR #39), `086a9ed` (PR #41) | Independently verified (sample) |
| 10 | `local/` (±10 km grids, 33 sites) | Card 18, Jiyong (6 polar, `5982e09`); card 20, PR #26, Dongju (27, `792b1dd`, `c2f424e`) | `docs/card18_validation.json` (Jiyong); `docs/card20_validation.json` (Dongju) | **Integrator:** `bab473b`: own 720-azimuth PGDA horizons + `ephem.bin` loop at 5 nodes in 3 regions (incl. the Malapert headline pair), max diff 0.009 pp; `f8d29a6`: centre node = metrics file 33/33, own horizons at 5 nodes within 0.007 pp, headlines 38.65 / 6.70 pp and IQR 17.16 / 0.40 pp reproduced | `bab473b`, `f8d29a6` (PR #26) | Independently verified (sample) |
| 11 | `uncertainty/` (±500 m, 121 nodes, 33 sites) | Non-polar 17: Sua (`30c64f6`); south-polar 16: PR #27, Jiyong (`27a0470`, `acff6f4`) | Non-polar: own brute force at 15 nodes, max 0.021 pp (row 20, Sua); polar: separate verifier, 15 nodes, difference 0, centres 16/16 exact (`docs/coordinate_uncertainty_check.json`, Jiyong) | **Integrator (polar part):** `33a7342`: centre node = metrics 16/16; own PGDA horizons + `ephem.bin` loop at 5 nodes within 0.146 pp. Non-polar part: the checks in `ed25936` (centre 17/17, 5 nodes ≤ 0.014 pp) were run by the integrator, who is also its author | `ed25936`, `33a7342` (PR #27) | Independently verified (south-polar part only); non-polar part author-verified only |
| 12 | `date_slip/` (33 sites × 730 landing days) | Card 19, PR #25, Dongju (`68182a1`) | `pipeline/verify_date_slip.py` → `docs/date_slip_check.json` | **Integrator:** `812cc94`: own loop over `ephem.bin` + horizons reproduces all 33 × 730 × 4 series values to 4 decimals (max diff 0). Scope: all values | `812cc94` (PR #25) | Independently verified (full) |
| 13 | `monthly/` (seasons, 33 sites × 60 months) | Sua (`7bbf35e`) | Own numpy check, 3 sites × 6 random months + all 60; 33/33 five-year means = metrics (row 19) | **None by another person.** The check in merge `4a760de` was run by the integrator, who is also the author | `4a760de` | Author-verified only |
| 14 | `windows/` (Sun/Earth visibility windows, 33 sites) | Card 15-B, PR #19, Minchul (`3ae1974`) | 20 window edges per site vs the app's `core.js` (`docs/windows_verification.md`) | **Integrator:** `7ddda73`: own sunlit/Earth bits from `ephem.bin` + horizons for SHACKLETON_RIM, ARTEMIS_HAWORTH, APOLLO17: every interval identical (Sun 226/179/63, Earth 68/68/1), 20 random edges each matched to the hour | `7ddda73` (PR #19) | Independently verified (3 sites, all intervals) |
| 15 | `hindcast.json` (real missions) | Card 21, PR #28, Dongju (`43d0bba`) | 3 rows re-derived from Horizons: Δ ≤ 0.0002°, 0 min (row 21) | **Integrator:** `e97de2d`: own Skyfield Sun elevation at the landing times: Apollo 11 10.7035° (doc 10.70), Apollo 17 13.3501° (doc 13.35); sources opened (ALSJ six values, NASA, ISRO) | `e97de2d` (PR #28) | Independently verified (sample: 2 Apollo landings) |
| 16 | `globe/` (3D Moon tiles, display) | Sua (`f373647`); south z8 tiles from PGDA 10 m, PR #15, Soyun (`875cdbb`) | Projection + height-encoding self-test (`docs/globe3d.md:30`, Sua); z8 tiles: decoded heights within 0.251 m of the 10 m source, 462 shared edges identical (`docs/card14.md:102–103`, Soyun) | **None recorded** (merges `b80ebae`, `8e6c0d8` list no check) | `b80ebae`, `8e6c0d8` (PR #15) | Author-verified only |
| 17 | `hterrain/tiles/` (global terrain for user points) | Sua (`f4ef867`) | Browser horizon vs Python `horizon.py` on the same tiles RMS ≤ 5.33 × 10⁻¹¹°; vs full LDEM_64 RMS ≤ 0.155° (`web/data/hterrain/validation.json`; row 14) | **None by another person** (merge `36a30e6` lists no check) | `36a30e6` | Author-verified only |
| 18 | `hterrain/polar_s/` (south-polar terrain for user points) | Sua (`33831da`) | vs the card 8 chain (Jiyong's horizons) at 16 sites + 30 random points: median RMS 0.085° / 0.027°; PEAK_NEAR_SHACKLETON +2.40 pp written as a known limit (row 14) | **None by another person.** The checks in merge `d300e04` (3 points) were run by the integrator, who is also the author | `d300e04` | Author-verified only |

## Count

| Status | Products | Which |
|---|---:|---|
| Independently verified by the integrator before merging | 10 | horizon, metrics, relay, validation, 948 m map, local grids, uncertainty (south-polar part only), date_slip, windows, hindcast |
| Independently verified by another team member | 2 | ephem, korea (`stations.json`) |
| Author-verified only | 6 | sites, 3.8 km map, monthly, globe tiles, hterrain tiles, custom polar terrain |
| Not verified | 0 | — |

Only `date_slip/` was recomputed in full; the other independent checks are samples.

## Claim for the SI disclosure and validation text

> Of our 18 published data products, 12 had a sample of their values independently recomputed with separate code
> by someone other than their author (10 by the integrator before merging, 2 by another team member), with recorded
> differences of at most 0.15 percentage points or 0.004°; the other 6 were checked only by their authors.

This replaces "every number was independently re-verified", which the records do not support.

## Additional independent checks — Jiyong, 2026-11-14 23:39 KST

The table/count/claim above is the preserved PR #53 snapshot at main `115d285`;
its 12-of-18 count and shared 0.15 pp / 0.004° sentence are **not an updated bound for the checks below**.
This appendix uses new OpenAI Codex-assisted code, independent of the producers' check scripts.
Inputs: main `6829725`; custom-polar Worker/sampler/index match `s4-custom-polar-sua` (`33831da`).
Full method, limitations, all samples and reproduction: [independent cross-check report](crosscheck_maps_polar.md).

| Product | Computed by | New independent recomputation | Recorded differences / scope | Status after this check |
|---|---|---|---|---|
| `gmaps/` (3.8 km whole-Moon map) | Soyun, card 9 / PR #9; original CPU engine by Sua | Jiyong's separate DEM reader, full CPU ray march and Sun/Earth loop; ten deterministic random source cells, seed 53142026; four supporting cells for each nearest published overview pixel, 40 unique cells total including the ten centres | Max vs original CPU engine **9.4147e-12 pp** over Sun/Earth/both. Published PNG **30/30 DN values identical** after own interpolation/quantization (0 pp); pre-quantization residual ≤ **0.198773 pp** within its 0.2 pp rounding half-step. Producer's raw float32 grid unavailable, so no claim of direct raw-array equality. [Evidence](crosscheck_maps_polar/map_check.json) | Independently verified by another member (10 sampled source cells + published overview encoding) |
| `hterrain/polar_s/` (custom south-polar terrain) | Sua, `s4-custom-polar-sua` / `33831da` | Jiyong's independent card-8 PGDA-chain full march and time loop versus actual browser Worker at SHACKLETON_RIM, PEAK_NEAR_SHACKLETON, ARTEMIS_MALAPERT; second control independently decodes and marches identical browser tiles | Against card-8: RMS **0.105267 / 0.140531 / 0.063066°**, max **0.519843 / 0.413379 / 0.327241°**, Sun **+1.220792 / +2.430175 / +0.198521 pp**. Same browser tiles: all **2160 angles identical after output rounding**, unrounded max ≤ **0.000050°**, Sun difference **0 pp**, independent loop equals browser core. [Evidence](crosscheck_maps_polar/polar_check.json) | Independently verified by another member on identical inputs; high-resolution agreement is limited by the explicitly measured DEM-product differences |

With these two checks alone added to PR #53, **14/18 products have independent sample recomputation**
(10 integrator, 4 other member); **4 remain author-only** in this snapshot: sites, monthly, globe tiles,
and global hterrain tiles. Other team members' pending checks are not counted here. The custom-polar
control verifies implementation agreement, **not high-resolution equivalence or a universal <1 pp accuracy**.
All values above are sample results, not bounds on absolute physical accuracy. No production numbers changed.
