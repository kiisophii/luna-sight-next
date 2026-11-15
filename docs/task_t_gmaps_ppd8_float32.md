# Task T — original 3.8 km (ppd 8) whole-Moon float32 grid, published losslessly

Publisher: Soyun Jeong, 2026-11-15. Work by Claude Code; the human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.

**Status:**
- Publication: **done**.
- Publication integrity: **checked by the producer side**.
- **Independent raw-array verification: PENDING.** It must be done by a team member other than Soyun Jeong, who ran this map in card 9 (PR #9).

This document does not claim that the map values are scientifically correct.

## What is published

The original arrays from the producing run (`data/processed/gmaps_ppd8/`, created 2026-11-14T02:02:31Z, all 1,440 rows done) are copied **byte for byte**:
- no recompression, quantisation or resampling;
- not the 948 m `gmaps_ppd32` arrays;
- not the PNG or JPEG products.

| | |
|---|---|
| Location | GitHub release **`task-t-gmaps-ppd8-float32-v1`** (pre-release) of this repository: https://github.com/kiisophii/lunar-landing-site-navigator/releases/tag/task-t-gmaps-ppd8-float32-v1 |
| Assets | `sun.npy`, `earth.npy`, `both.npy`, `h0.npy`, `maskmax.npy` (16,588,928 B each), `done.npy`, `meta.json`, `MANIFEST.json`, `SHA256SUMS.txt`; about 80 MB in total |
| In git | Only `docs/task_t/MANIFEST.json`, `docs/task_t/SHA256SUMS.txt`, check outputs and this document |

Why a release asset:
- 80 MB of binary data would grow the git history permanently.
- Files under `web/` are deployed to GitHub Pages, and the browser does not need these arrays.
- A release asset keeps the original bytes downloadable and checksummed without either cost.

### Format and coordinates

- NumPy `.npy` version 1.0, header 128 B, `descr '<f4'` (little-endian IEEE float32), C order, shape **(1440, 2880)**. `done.npy` is `uint8` (1440,).
- Row `r` (north → south) is the pixel centre at latitude **90 − (r + 0.5)/8**. Column `c` (west → east) is at longitude **−180 + (c + 0.5)/8**.
- Frame MOON_ME (DE421), sphere R = 1737.4 km. Grid spacing 1/8° = 3.7903 km at the equator.
- No-data is NaN for rows with `done == 0`. In this run `done == 1` for all rows, and every field has 0 NaN and 0 Inf.

| Field | Meaning | Range in file |
|---|---|---|
| `sun` | Mean visible fraction of the solar disc (radius 0.2666°) above the horizon mask, 0–1. **Not** the sunlit-hours fraction used in `core.js` | 0 … 0.76043057 |
| `earth` | Fraction of samples with the Earth centre strictly above the mask | 0 … 1 |
| `both` | Fraction of samples with disc fraction ≥ 0.5 AND the Earth centre above the mask | 0 … 0.57959110 |
| `h0` | Cell-centre terrain height (m) above 1737.4 km. Bilinear from LDEM_64, with LDEM_16 used if that is NaN | −8956.425 … 10689.565 |
| `maskmax` | Maximum horizon-mask elevation (°) over 360 azimuths, observer at h0 + 2 m | −0.1627 … 79.0325 |

### Computation parameters and inputs

All of these are recorded in `MANIFEST.json`, which includes `meta.json` verbatim.

- **Engine:** `pipeline/global_maps.py`, engine_version 1, unchanged since `48929ec` (before the run). Run in card 9, commit `7de0271` (PR #9).
- **Horizon:**
  - 360 azimuths;
  - terrain march with step fraction 0.01, 283 steps;
  - LDEM_64 out to 150 km, then LDEM_16 out to 300 km;
  - curvature exact;
  - observer 2 m above the terrain.
- **Ephemeris:** `web/data/ephem.bin` at a 2 h step, i.e. hours 0, 2, …, 43822 from 2026-01-01T00Z, 21,912 samples.
  - The engine's signature SHA-1 (float64 copy of every second row) is `bf98b99edc04`.
  - Recomputed from the current file it is the same, so the current `ephem.bin` (SHA-256 `c0a22639…`, last changed in `d89c42a`) is the one used.
- **DEMs:** LOLA GDR LDEM_64 / LDEM_16 float V3.1 from PDS. Local copies, sizes equal to the signature:

| DEM | Bytes | SHA-256 |
|---|---|---|
| `ldem_64_float.img` | 1,061,683,200 | `4dd151f2…188ec25b` |
| `ldem_16_float.img` | 66,355,200 | `c6b790f1…f567a432` |

### Checksums (`SHA256SUMS.txt`)

```
b1f39c54e634b62f58066f026b59dd67540931bc526409cb716328cba0347f6c  sun.npy
82a7bcdb249c4a5a19a91e36fd39011dcc97a43db7440ea56665d249777c6613  earth.npy
f8d5903ac6a6de957f83cc85c129af9e66a0430b19fe5ef46236a2e1f706d073  both.npy
0075b4dbc7d9fb71ff9ab4016a02f6780910c4461c2440e2d151ee6fdba124a3  h0.npy
af20e8c2053f1f72b281a9962504107bf341ef8db6b1b7e21d21e0f230d6ce88  maskmax.npy
0a7b0388f6e4ea09a0a0cd0475110256bfc56bbd2352e6957034e74772c52551  done.npy
d6241fe542dca126909fc0cbfc8845b285056168308c8fcabefcad155c4e65d0  meta.json
```

`MANIFEST.json` is listed in the release's `SHA256SUMS.txt` as well.

## Publication integrity (producer-side, not independent)

Script: `pipeline/task_t_gmaps_ppd8_raw.py`.

1. **Release copy vs the local originals.** Checked twice: on the staging copy, and on the copy downloaded back from the release (`docs/task_t/check_staging.json`, `docs/task_t/check_download.json`). For every file:
   - SHA-256 equals `SHA256SUMS.txt`, and the bytes equal the original;
   - the `.npy` header is identical;
   - shape (1440, 2880) and dtype `<f4`;
   - **identical float32 bit patterns** (compared as `uint32`) and identical NaN positions;
   - `done` is all 1, and `meta.json` is byte-identical.
2. **Published map vs the released grid.** The production export steps were re-run on the released arrays: `global_maps.resample` and `colorize`, PIL JPEG quality 88. Output: `docs/task_t/integrity_check.json`.
   - Values PNGs: **8,388,608 / 8,388,608 DN identical** per layer (sun, earth, both); maximum |ΔDN| 0; no no-data pixels.
   - Overview JPEGs: **byte-identical** (3/3).
   - Tiles: **126 / 126 byte-identical** (42 per layer, z0–z2).
   - `index.json` statistics: min, max and area mean exactly equal for all three layers, as are `rows_done` 1440 / 1440, the ephemeris signature and the parameters.
   - The largest gap between a published DN/250 and the resampled float value is 0.2000015 pp, i.e. half a DN step (0.2 pp) plus float32 rounding of the resampled value. This is the expected quantisation, not an error.
3. **Rounding of what is shown.** The web map shows these values only after bilinear up-sampling to 4096 × 2048 and 1/250 quantisation. The raw cell values are in the release.

These checks show that the release *is* the computed grid and that the website was made from it. They do not show that the grid is correct; that needs the independent check below.

## Handoff: independent raw-array verification (another member, not Soyun)

1. **Download and check.**
   ```
   gh release download task-t-gmaps-ppd8-float32-v1 -R kiisophii/lunar-landing-site-navigator -D gmaps_ppd8_raw
   cd gmaps_ppd8_raw && sha256sum -c SHA256SUMS.txt
   ```
   Every line must say OK.
2. **Read with your own code**, for example `np.load(...)` or `np.fromfile(..., dtype='<f4', offset=128).reshape(1440, 2880)`.
   - Confirm the shape, the 0 NaN count and the coordinate formulas above.
   - Do not use `pipeline/global_maps.py` or `pipeline/task_t_gmaps_ppd8_raw.py` to read or to compute.
3. **Choose cells yourself** with a stated seed, e.g. ≥ 10 cells: random, a few poleward of 80° S / 80° N, and one in a bright and one in a dark region.
   - For each cell, compute the cell-centre latitude and longitude, then recompute independently from the original PDS LDEM_64 / LDEM_16 files (URLs and SHA-256 in `MANIFEST.json`) and `web/data/ephem.bin`:
     - `h0` (bilinear);
     - the 360-azimuth horizon to 300 km (LDEM_64 to 150 km, then LDEM_16; curvature; observer 2 m);
     - `maskmax`;
     - the three fractions over the 21,912 samples at a 2 h step, with the definitions in the table above. Note that `sun` is the mean **disc fraction**.
   - Jiyong's earlier 10-cell check (ledger row 8, seed 53142026) compared against the engine, not against these arrays. The same cells may be reused, now compared against the raw float32 values.
4. **Compare the raw float32 values directly.** Report per field: max, median and every cell over the criterion. Suggested criteria: fractions ≤ 0.1 pp (as for `gmaps_ppd32`), `h0` ≤ 0.5 m, `maskmax` ≤ 0.05°. State whichever criteria are used. Do not drop failures.
5. **Record the result** in `docs/verification_ledger.md` row 8 (`gmaps/`) and the Task T section, with name, seed, cells and numbers, and add one SI row.

Until that is done, the ledger keeps Task T's independent comparison as **PENDING**.

## Limits

- The release is a GitHub pre-release asset outside git history. Its availability depends on the release not being deleted; `SHA256SUMS.txt` and `MANIFEST.json` are also committed in `docs/task_t/`.
- The integrity check uses the production export functions on purpose: it tests publication, not science.
- The local DEM copies were not re-downloaded from PDS for this task. Their sizes equal the run signature, and their SHA-256 values are recorded so the verifier can compare.
