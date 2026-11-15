# Task D — independent fine globe terrain and albedo checks

Checker: Jiyong Sung, OpenAI Codex-assisted; 2026-11-15. Production author: Sua Kim.
Reference main: `8fd119b`; latest-main integration `3086143` does not change these globe inputs.

**Result:** all 160 sampled vertices equal the independently predicted encoded height. Largest difference from the unquantized reference is **0.248620272 m**, within the 0.5 m encoding step (and its 0.25 m half-step). This verifies encoding/resampling, not absolute lunar elevation accuracy.

## Terrain samples

| Region | Zoom | Random + catalogue controls | Mean absolute difference (m) | Median (m) | Max (m) | Encoded equality |
|---|---:|---:|---:|---:|---:|---:|
| band | 4 | 10 + 10 | 0.096423712 | 0.074357033 | 0.215874672 | 20/20 |
| band | 5 | 10 + 10 | 0.123303828 | 0.126846313 | 0.246246338 | 20/20 |
| band | 6 | 10 + 10 | 0.119409928 | 0.123958468 | 0.234477997 | 20/20 |
| band | 7 | 10 + 10 | 0.146696185 | 0.164076177 | 0.247314453 | 20/20 |
| south | 3 | 10 + 10 | 0.109944717 | 0.103673019 | 0.248620272 | 20/20 |
| south | 4 | 10 + 10 | 0.121506524 | 0.107812447 | 0.242874220 | 20/20 |
| south | 5 | 10 + 10 | 0.124655988 | 0.125355965 | 0.244286351 | 20/20 |
| south | 6 | 10 + 10 | 0.137830950 | 0.165207496 | 0.245700035 | 20/20 |

Seed `2026111504`. Source counts: {'LDEM_64': 29, 'SLDEM2015': 57, 'PGDA': 74}. Band z4 random samples all fall on LDEM_64; the ten additional catalogue controls at that level cover SLDEM. No fallback samples were removed. All coordinates, signed differences and source choices: [160 vertices](task_d_vertices.csv). All 34 reconstructed windows: [window origins](task_d_windows.csv).

## Full inventory and same-zoom shared vertices

- All **3,294** indexed files exist.
- All **1,638** requested-level PNGs decode as RGB 259 × 259, with zero blue channel; no constant tile.
- **2,549** adjacent same-zoom shared-vertex edges: maximum difference **0.0 m**, no failures. Includes four band z4 longitude-wrap edges (x79 → x0, y24–27).
- Full failure lists and per-tile SHA256 are retained in [machine-readable evidence](task_d_check.json).

Scope: file existence is checked for every indexed zoom. Height samples and PNG integrity/seams cover only band z4–z7 and south z3–z6. Normal-calculation border pixels, different-zoom joins, band–cap joins, browser rendering and south z7/z8 geometry are not checked here. No universal claim that the rendered globe has no gaps.

## Albedo

Original: [NASA SVS CGI Moon Kit](https://svs.gsfc.nasa.gov/4720), [8192 × 4096 TIFF](https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif). Credit: NASA’s Scientific Visualization Studio. Compare every RGB channel, then independently replay LANCZOS resize (2k only) and JPEG quality 88 with optimization.

| Texture | TIFF/resize MAE (DN) | RMSE (DN) | Max (DN) | PSNR (dB) | Re-encoded bytes |
|---|---:|---:|---:|---:|---|
| moon_color_8k.jpg | 2.159976 | 2.878571 | 94 | 38.947264 | identical |
| moon_color_2k.jpg | 2.077311 | 2.777088 | 19 | 39.259012 | identical |

Both full-image JPEG replays are byte-identical. The correct orientation has smaller strided MAE than latitude/longitude flips or a 180° shift (all scores in JSON). TIFF-to-JPEG differences are lossy display compression, not DEM height error. No independent landmark registration or photometric calibration was performed.

## Independent method and provenance

The checker imports no production builder, sampler or verifier. It reads original native DEM pixels from cached NASA sources, reconstructs the published original window origins, calculates vertices with PROJ, computes local hierarchical box means, bilinearly samples in source-priority order, and decodes PNG RG heights as `(256*R+G)/2-10000` m. Each pyramid level rounds to float32; final encoding uses float32 and nearest integer, matching the documented storage operations. Source geometry, window phase and production conventions are shared by design; the numerical implementation is separate.

The [18 polar origins](globe_south_window_origins.json) identify 20/60/80 m PGDA windows. Expanded caches are cropped at integer native-pixel offsets, with spacing, shape, frame, radius and source URL assertions. SLDEM windows are reconstructed from the 62 km spherical bounds plus two native pixels at 512 ppd. Global fallback reads native LDEM_64 (km converted to m). Raw-cache, input-code, index, source-TIFF and tile SHA256 hashes are in the JSON; execution-byte hashes may differ on a checkout with different line endings. Existing HTTP readers are used only to acquire raw NASA data, not to evaluate terrain.

Sources: [PGDA product 90](https://pgda.gsfc.nasa.gov/products/90), [SLDEM2015 float tiles](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [LOLA global float grids](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/). Exact individual URLs and original-cache metadata are preserved in the JSON. Raw rasters stay ignored.

## Reproduction and validation

Requires Python, NumPy, Pillow, pyproj and pytest (requests/tifffile for raw acquisition). Run from the repository root. Existing raw caches: `data/processed/local250/raw/polar` (expanded PGDA), `data/raw/sldem` (151 km windows, 16 sites at abs(lat)<60), `data/processed/local250/raw/global/ldem_64_float.img`. Use checker flags `--polar-root`, `--sldem-root`, `--ldem64` to point to equivalent native caches. Missing 80 m cap and 60 m CHANDRAYAAN3 windows fall back to `data/processed/task_d/raw/polar`. Acquisition commands are below; original, larger caches may be reused.

```powershell
python pipeline/fetch_polar.py --res 20 --radius-m 41000 --output data/processed/local250/raw/polar --skip-unavailable
python pipeline/fetch_polar.py --res 60 --radius-m 76000 --output data/processed/local250/raw/polar --skip-unavailable
python pipeline/fetch_global.py --skip-global --radius-km 151 --workers 4
python -c "import json; from pathlib import Path; p=Path('data/processed/task_d'); p.mkdir(parents=True,exist_ok=True); (p/'cap_site.json').write_text(json.dumps([dict(id='SOUTH_CAP_80S',lat=-90.,lon=0.)]))"
python pipeline/fetch_polar.py --sites data/processed/task_d/cap_site.json --res 80 --radius-m 300000 --output data/processed/task_d/raw/polar
python -c "import json; from pathlib import Path; from pipeline.fetch_polar import fetch; s=next(s for s in json.loads(Path('web/data/sites.json').read_text(encoding='utf-8')) if s['id']=='CHANDRAYAAN3'); fetch(s,60,63000,Path('data/processed/task_d/raw/polar'))"
curl.exe -L --fail -C - -o data/processed/task_d/lroc_color_poles_8k.tif https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif
python -m pytest pipeline/tests/test_task_d.py -q
python pipeline/task_d_check.py
python pipeline/task_d_report.py
python pipeline/verify_ledger.py
```

Fetch LDEM_64 from the linked float-grid archive if absent; keep the original little-endian float32 IMG (11520 × 23040). Acquisition uses resumable HTTP blocks. The checker checkpoints its sample plan and completed sample rows, but reruns this short audit rather than skipping existing samples.

Final full-check computation: **25.18 seconds** on Jiyong’s desktop; excludes downloads, development/review, and the final LDEM64 hash/output serialization. Four focused tests pass. A fresh AI review identified the missing dateline-wrap audit; a failing synthetic seam test reproduced it, then the fix passed and the full check was rerun (2,549 edges). No production data or browser code changed.
