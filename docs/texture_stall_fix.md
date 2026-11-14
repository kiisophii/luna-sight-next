# First-zoom colour texture stall

## Problem and change

The first close view used to assign an HTMLImageElement-backed 8192×4096 colour texture on the render thread. The desktop audit linked its first `texSubImage2D` call to a roughly 200 ms pause ([issue #37](https://github.com/kiisophii/lunar-landing-site-navigator/issues/37), [original audit](desktop_performance.md)).

`globe3d.js` now lazily starts `globe_color_worker.js` below the same 3000 km threshold. The worker fetches the **same JPEG**, decodes it, flips its rows to the existing UV convention, and transfers an RGBA buffer to a Three.js DataTexture. The existing 2K image remains visible until preparation finishes. sRGB, repeat wrapping, anisotropy, linear/mipmap filters and final 8K detail are preserved. GPUs with a smaller maximum texture size retain the legacy size cap. The worker terminates on success/error/disposal; the pixel buffer stays available for context restoration.

An ImageBitmap-only trial still paused during main-thread pixel conversion, so decoding alone was insufficient. Moving decode, orientation and pixel extraction together into a worker removed that conversion from camera/input rendering. Preloading would add work before the user zooms; a permanent resolution reduction would lose detail. No scientific values, data files, imagery files, terrain geometry or index.html are changed.

## Results

Values are **medians of three runs**, with min–max in parentheses. Long-task zero means no task at least 50 ms was reported, not zero work. Raw evidence: [8K baseline](texture_stall/baseline.json), [8K worker](texture_stall/fixed.json), [4K baseline](texture_stall/baseline_4k.json), [4K worker](texture_stall/fixed_4k.json), [machine-readable summary](texture_stall/summary.json).

| Profile | Texture / loader | Upload ms | Max first-zoom frame gap ms | Max long task ms | Settled drag FPS | Initial transfer MB |
|---|---|---:|---:|---:|---:|---:|
| Desktop | 8K legacy | 198.9 (198.4–219.2) | 195.6 (194.0–228.8) | 216 (214–234) | 30.2 (30.0–30.4) | 4.942 |
| Desktop | **8K worker** | **39.4 (37.1–42.4)** | **64.7 (33.7–65.8)** | 60 (57–60) | 30.1 (30.1–30.3) | 4.944 |
| Limited laptop profile | 8K legacy | 786.2 (784.4–787.2) | 781.5 (780.5–811.8) | 810 (809–811) | 29.2 (28.8–29.5) | 4.942 |
| Limited laptop profile | **8K worker** | **67.0 (66.6–67.8)** | **98.1 (97.6–98.4)** | 95 (92–104) | 29.3 (29.3–29.6) | 4.944 |
| Desktop | 4K legacy (diagnostic) | 53.0 (52.4–53.2) | 65.9 (64.9–66.2) | 67 (67–69) | 30.3 (30.2–30.3) | 4.942 |
| Desktop | 4K worker (diagnostic) | 12.1 (12.1–12.3) | 33.4 (33.2–33.6) | None | 30.2 (30.2–30.2) | 4.944 |
| Limited laptop profile | 4K legacy (diagnostic) | 183.5 (180.9–184.8) | 227.5 (194.4–227.7) | 237 (190–240) | 30.0 (29.3–30.1) | 4.942 |
| Limited laptop profile | 4K worker (diagnostic) | 28.0 (27.7–28.6) | 98.5 (98.4–131.2) | 102 (97–119) | 29.2 (29.0–29.4) | 4.944 |

The production 8K worker reduces median synchronous upload time by **80% desktop / 91% limited profile**, preserving imagery detail. Measured initial transfer increases about **2.1 KB**; this includes 837 bytes of Windows CRLF versus baseline Git LF line endings. The committed LF globe module increases by **1,297 bytes**, and the worker is requested only on zoom. The 6.574 MB close-view image remains lazy and unchanged. Sustained FPS stays approximately the same: this fixes a first-use pause rather than increasing the steady display cadence. All 24 timed runs completed without recorded page/request/HTTP errors. Both worker resolutions passed the <100 ms desktop first-zoom gap/long-task and <100 ms texture-upload checks on both profiles. This does **not** claim all laptop-profile tasks are below 100 ms (observed up to 104 ms for 8K and 119 ms for 4K).

The 4K diagnostic JPEG is **1,680,000 bytes**, versus **6,574,251 bytes** for production 8K (about 74% smaller), with one quarter of the pixels. It substantially reduces the legacy pause, confirming pixel preparation as the major original bottleneck. After the worker fix, 4K reduces upload time further but does not improve the limited profile's maximum frame gap or steady FPS. Keep the exact 8K production asset for this fix; a future low-memory/bandwidth option would trade colour detail for savings, without altering the DEM or scientific calculations.

Scene readiness also matters: 8K first-South-pole settled time is 8.227 → 8.068 s desktop and 22.319 → 22.101 s limited profile. These include camera flight, all requested terrain/colour loading and quiet polls, **not continuous freezing**. Cold initial readiness is 1.483 → 1.440 s desktop and 7.054 → 7.134 s limited profile. This fix does not claim a large reduction in overall download/scene-readiness time.

All 8K runs stayed at adaptive quality level 0. One 4K worker limited run reached the existing level 2 (2048 shadow map); the other two stayed at 0. Thus the 4K low-power comparison also contains this adaptive-quality difference and should not be interpreted as a precise constant-quality FPS ranking.

### Remaining limited-profile pause

A separate **profiled diagnostic**, excluded from the table, tested the improved 4K loader under the limited profile. Upload was 28.8 ms while the maximum frame gap remained 98.4 ms. Browser-only timing of synchronous `buildMesh` recorded 157 terrain builds, **6.675 s combined and 59.3 ms for the slowest individual build**. The CPU profile identifies coordinate generation, normals/vector work and mesh construction. Reducing colour resolution cannot remove that terrain work. The existing six-millisecond build-queue budget checks between meshes, so it cannot interrupt an individual long build. A future geometry-worker or incremental mesh-building task would address this separate bottleneck; this PR preserves all geometry algorithms and numbers.

Diagnostic evidence and exact timing wrapper: [diagnostic.json](texture_stall/diagnostic.json), [CPU profile](texture_stall/diagnostic_cpu.json), benchmark `--cpu-profile --texture-size 4096 --profiles laptop --runs 1 --out data/processed/texture_stall/diagnostic`. No universal “zero stutter” claim is made.

## Measurement protocol

- Base module: main `64e3bee`; fixed module and worker SHA256 are recorded per result file. All other local app/data assets are identical for each comparison.
- Main `7e7964e` was incorporated before the PR, followed by `115d285` to include the team's submission/documentation updates and resolve the appended SI-log conflict. Since the measured base, these are documentation, offline validation scripts and version metadata changes. Globe modules, index.html, core.js and globe data are unchanged, so the measured application paths remain the same.
- Windows desktop: Ryzen 5 5600X / 32 GB / RTX 5060; installed Chrome, **headed**, hardware ANGLE D3D11 (full browser/GPU metadata in raw results).
- Desktop: 1920×1080, DPR 1, native CPU/network. Laptop profile: 1366×768, DPR 1, **4× main-thread CPU slowdown**, 10 Mbps download / 1 Mbps upload / 70 ms latency.
- The worker CPU and physical GPU are **not laptop hardware emulations**. Chrome does not support worker-target CPU throttling. Page network emulation does apply to worker fetches: [isolated check](texture_stall/network_check.json) measured the same 6,574,251-byte JPEG at 32 ms native versus 5,349.8 ms limited. Worker target network events and server payload accounting are included; a page-only CDP counter misses worker bytes.
- Three fresh browser/cache runs per implementation, resolution and profile. OS cache/local server and external CDN conditions are not cold-machine or deployed-site measurements. Browser stays foregrounded. No other benchmark browser runs concurrently.
- Cold initial scene → set time index 7619 → first South pole button → wait for terrain/colour and five quiet polls → four-second mouse drag. No prewarming before the measured first zoom.
- Upload duration measures the synchronous WebGL call. Maximum long task and rAF gap cover the full first-zoom phase (including terrain streaming). FPS is the application render counter during the settled drag; it is not physical display presentation. This desktop session runs around 30–31 rAF Hz even on a blank page (original audit).
- Initial transfer is completed page-CDP encoded bytes through initial scene readiness. No 8K/4K image request has occurred at that point, checked against **server requests as well as page resources**. Later local payload accounting includes worker requests; CDN bytes/HTTP headers are not included in that separate local payload figure.

## 4K diagnostic

The test server alone replaces the close-view JPEG response with a 4096×2048 image, Lanczos-resampled from the shipped 8K JPEG and re-encoded at JPEG quality 88 with optimize enabled. It exists only in server memory. It is a diagnostic asset, not a production dataset or a new source image. Resampling plus JPEG re-encoding changes detail; its byte size is not a pure resolution-only compression experiment. Runtime/worker code is otherwise identical. This refers to **texture resolution, not a 4K display viewport**.

## Verification and limits

- All six browser correctness cases pass; both JavaScript modules pass `node --check`. The unchanged data contract passes with **0 errors / 0 warnings** using Git LF source bytes. A direct Windows checkout run first reported 33 provenance mismatches because `build_windows.mjs` and `core.js` are checked out as CRLF; the isolated LF check keeps the actual-byte validator intact and reads the same data through a directory link. No source/data file was normalized in the working checkout. Reproduce with `python docs/texture_stall/check_contract_lf.py`; [log](texture_stall/contract_lf.log).
- GPU texture sampling compared the final worker texture with the legacy HTML-image texture over four 512×256 views: whole map, south-pole crop, north-pole crop, longitude-seam crop. All sampled RGBA channels matched exactly, including mipmaps; same result after forced WebGL context loss/restoration. This is sampled rendering parity, not a full-image proof.
- Browser checks cover initial 2K, final 8K, HTTP failure, invalid JPEG, termination of an in-flight worker, legacy path when Worker is absent, and a simulated 4096 maximum texture size. Errors retain the working 2K colour. If worker creation/decoding fails, the app does not retry a blocking 8K upload automatically. Browsers without Worker use the original loader and may retain the original pause.
- The retained RGBA buffer is 128 MiB at 8K (32 MiB at 4K), before GPU mipmaps and temporary decode/canvas memory. Peak memory and other browser engines/real low-power laptop GPUs were not measured. The worker does not reduce total image work or network bytes; it keeps image preparation off the interaction thread.
- Primary implementation references: [Three.js r170 texture upload](https://github.com/mrdoob/three.js/blob/r170/src/renderers/webgl/WebGLTextures.js), [r170 ImageBitmapLoader options](https://github.com/mrdoob/three.js/blob/r170/src/loaders/ImageBitmapLoader.js). Existing image source remains [NASA SVS CGI Moon Kit](https://svs.gsfc.nasa.gov/4720).

## Reproduce

Use the existing Python Playwright environment, Pillow and installed Chrome. From the repository root:

```powershell
python docs/texture_stall/benchmark.py --variant baseline --runs 3
python docs/texture_stall/benchmark.py --variant fixed --runs 3 --check
python docs/texture_stall/benchmark.py --variant baseline --texture-size 4096 --runs 3
python docs/texture_stall/benchmark.py --variant fixed --texture-size 4096 --runs 3 --check
python docs/texture_stall/check_network.py
python docs/texture_stall/verify.py
```

Outputs default to ignored `data/processed/texture_stall/`. The baseline module is served directly from Git; no checkout switch, data mutation or index.html edit is needed.
