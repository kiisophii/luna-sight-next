# Card 14 — 948 m map: split run, verification and merge procedure

Soyun Jeong, 2026-11-14 (KST). Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
Split decided by the team lead (Sua Kim): Soyun's laptop (CPU) computes rows **0–3103**, Jiyong Sung's
desktop (GPU) computes rows **3103–5759**. Row **3103** is computed by both as an independent check.
Nothing has been merged or exported yet.

## 1. Rows 0–3103 (this laptop) — done
| Item | Value |
|---|---|
| Command | `pipeline/run_ppd32_rows.ps1 -Rows 0:3104 -Threads 16` → `global_maps.py run --ppd 32 --step-h 3 --rows 0:3104 --threads 16` |
| Finished | 2026-11-14 20:27:59 KST, exit code 0, 3.1 h for the last 2550 rows (earlier rows were done in the 16:13–17:22 runs) |
| Store | `data/processed/gmaps_ppd32/` (git-ignored), done mask 3104/5760; rows 3104–5759 not computed (NaN) |
| Settings | LDEM_64 (474 m, to 150 km) + LDEM_16 (1895 m, to 300 km), 360 azimuths, 283 march steps, observer 2 m, `web/data/ephem.bin` 2026–2030 at 3 h = 14,608 samples, sha1_12 `4772740f1aed`, mock = false |
| Log | `data/processed/logs/ppd32_rows_0_3104_20261114_172319.log` |

### Verification (`python pipeline/gmaps_split.py verify --src data/processed/gmaps_ppd32::0:3104 --spot 12 --seed 14`) — PASS
| Field | NaN | Inf | min | max | mean | outside range |
|---|---|---|---|---|---|---|
| sun | 0 | 0 | 0.0 | 0.8023 | 0.4410 | 0 (0..1) |
| earth | 0 | 0 | 0.0 | 1.0 | 0.4439 | 0 (0..1) |
| both | 0 | 0 | 0.0 | 0.6019 | 0.2072 | 0 (0..1) |
| h0 (m) | 0 | 0 | −6800.4 | 10755.5 | −322.4 | 0 (−9500..11000) |
| maskmax (°) | 0 | 0 | −0.32 | 78.87 | 8.80 | 0 (−90..90) |

- Shapes `(3104, 11520)` float32 in the requested range; done mask 3104/3104 in 0:3104 and 0 rows outside it.
- `both ≤ earth` at every point (0 violations). `earth` values are whole multiples of 1/14608 (max residual 0.0004 samples): they really are counts over the ephemeris.
- **Recomputation**: 12 random points (seed 14, rows 437–2877) recomputed with the same engine, DEMs and ephemeris → sun / earth / both identical at float32 (max difference 0.0); h0 and maskmax within 1e-3 m / 1e-4°.
- Real data: ephemeris `mock: false`, `ephem.bin` re-hashed now = `4772740f1aed` (same as the store); DEM sizes = the store signature (1,061,683,200 / 66,355,200 bytes); DEM files dated 09:53 / 09:56 KST, before the store was created (13:19 KST).
- `web/data/gmaps/` (3.8 km map), `web/data/ephem.bin` and `ephem.json`: no difference from `origin/main`.
- Row-3103 file `data/processed/gmaps_ppd32_row3103_book-hn13iedngg.npz` (+ `.json`): all 5 fields identical to row 3103 of the store; its signature = the store signature. Row 3103 = latitude −6.984375°.

## 2. Hand-off package for the merge (not in git)
`data/processed/handoff/ppd32_rows_0_3104_soyun/` — written by `gmaps_split.py pack`, checked with `gmaps_split.py check` (PASS):

| File | Bytes | Shape / dtype | SHA256 |
|---|---|---|---|
| sun.npy | 143,032,448 | (3104, 11520) float32 | `701af976785a4ac820b4acd4ba64c7cea61a107f4873afed776eef5d2fafb33c` |
| earth.npy | 143,032,448 | (3104, 11520) float32 | `2f6ee12d661997c2571a9141be234d963823e50bf3cc2ad9850eefc5de12c949` |
| both.npy | 143,032,448 | (3104, 11520) float32 | `068abb565a51ab42d9acfd364e2c8f5a0961884ddb1d41d0047794388090c991` |
| h0.npy | 143,032,448 | (3104, 11520) float32 | `7f9beab58488562d28795fe37b74f4d446322305bdb468e921091f56db75f0fe` |
| maskmax.npy | 143,032,448 | (3104, 11520) float32 | `337b350d5f14253a24a5439f930ce55242828a7b8a0855856969cbe5a0494307` |
| done.npy | 3,232 | (3104,) uint8 | `215ef7ceddf79e97e561d24e8d6b4edf0c1043f4bed6215e74fd175ef140b929` |
| row_3103.npz | 231,870 | 5 × (11520,) float32 | `2eacea81466711141cebf4769896fe42e7f6bad14287126b6d366b566e623611` |
| store_meta.json | 773 | — | `c1a2bcf90febf7b129a9c1dac2dab5135094cb47d6da01b0bdf685df07d79b8a` |
| manifest.json, README.md | — | — | manifest = every file above + `inputs_sha256` + the verify report |

Total **715.4 MB**. zlib compresses the float data only to 84 %, so the files are shared uncompressed.
Too large for GitHub (100 MB per-file limit) → share through a team drive / USB, then run `check` on the receiving side.

Input files used (for the other machine to compare with its own copies):

| Input | Bytes | SHA256 |
|---|---|---|
| ldem_64_float.img | 1,061,683,200 | `4dd151f230984316602f13df36214563ff575683cb5612f1a7bc4699188ec25b` |
| ldem_16_float.img | 66,355,200 | `c6b790f14409f0a74d6640b69ddb0c48b8cd3e330117366162669f85f567a432` |
| web/data/ephem.bin | 1,051,776 | `c0a226391f7a47c22c71d8b187cc98fb80101631bee37bd13b32a6870f965da3` |
| web/data/ephem.json | 323 | `c6294c416a16bcc34d08752b8f0541d803e2e5784af09ce291b0a211269f52b8` |

Grid (also in the package README): global row `r` → lat `90 − (r + 0.5)/32`, column `c` → lon `−180 + (c + 0.5)/32` (MOON_ME, east +), arrays `[row − start, column]`, row 0 = north.

## 3. What the GPU part must provide
Either a store folder written by `global_maps.py` (same `meta.json` / `done.npy` / `<field>.npy` layout) or a package made with `gmaps_split.py pack`. Required:
- rows 3103–5759 (`3103:5760`) with all five fields (sun, earth, both, h0, maskmax) as float32, same grid;
- a signature equal to ours in `engine_version, naz, near_km, max_km, step_frac, n_steps, obs_height_m, sun_radius_deg, near, far, ephem` (a GPU port that changes any of these is refused by `merge`);
- the same DEM and ephemeris files (compare the SHA256 values above).

## 4. Merge and export procedure (after the GPU result arrives; not run yet)
1. `python pipeline/gmaps_split.py check --src <gpu package>` (if it is a package) and `python pipeline/gmaps_split.py verify --src <gpu>` (`<gpu>` = package folder, or `<store>::3103:5760`).
2. Row 3103: `python pipeline/gmaps_split.py compare --a data/processed/handoff/ppd32_rows_0_3104_soyun --b <gpu> --row 3103 --report data/processed/handoff/compare_row3103.json`
   - reports per field: max |diff|, mean |diff|, mean signed diff, exact matches, points over tolerance, NaN mismatches, the worst 5 columns, and for fractions the difference in ephemeris samples (1 sample = 1/14608 = 6.8e-5);
   - default tolerances: sun / earth / both 1e-3, h0 0.5 m, maskmax 0.01°;
   - on FAIL it adds a diagnosis (h0 differs → DEM/sampling; maskmax differs with equal h0 → horizon marching / float32; sun/earth differ with equal maskmax → ephemeris subset, step or solar-disk model).
3. `python pipeline/gmaps_split.py merge --part data/processed/handoff/ppd32_rows_0_3104_soyun --part <gpu> --out data/processed/gmaps_ppd32_merged`
   - writes a NEW folder only (refuses an existing one); the input stores are read-only;
   - refuses on a missing row, an undone row inside a part's range, a signature difference or a failed part verify;
   - the overlap row 3103 is compared again; on disagreement it stops and writes `gmaps_ppd32_merged_overlap_report.json`. Values are never averaged. Only if a person decides the difference is acceptable: rerun with `--accept-overlap-diff "<reason>"` (the reason is stored in `meta.json`; the first `--part` supplies the overlap row);
   - finishes with a full verify of 5760/5760 rows (`verify_report.json`: NaN/Inf, ranges, `both ≤ earth`).
4. `python pipeline/global_maps.py status --ppd 32 --out data/processed/gmaps_ppd32_merged` → `5760/5760`.
5. Export (unchanged exporter): `python pipeline/global_maps.py export --ppd 32 --out data/processed/gmaps_ppd32_merged --web web/data/gmaps_ppd32` (not `web/data/gmaps/`, which keeps the reviewed 3.8 km map). The web location is still a proposal; data contract §10 only defines `web/data/gmaps/`.
6. Then the card 14 PGDA check (948 m and 3.8 km maps vs AVGVISIB_75S) and a new PR with the export.

## 5. Tool and tests
- `pipeline/gmaps_split.py` (verify / pack / check / compare / merge); `pipeline/run_ppd32_rows.ps1` (row-range runner: pre-flight, refuses a second run, keeps the PC awake, log, 3 resumes, never exports, saves the overlap row).
- `pipeline/tests/test_gmaps_split.py` (fake ppd-1 stores, 6 tests): verify catches NaN / out-of-range / mock; pack+check round trip and a corrupted byte; merge with overlap row = original values, refusal of an existing output folder; disagreeing overlap → refused, report counts the 10 changed columns, accepted only with a reason and without averaging; gap and signature refusals; compare at the tolerance boundary (1 sample).
- `pipeline/run_ppd32_overnight.ps1` fixes (Windows PowerShell 5.1): UInt32 for `SetThreadExecutionState`, `Continue` for native stderr, `[string[]]` argument array. These were made after PR #15 was merged, so they are in this branch.
