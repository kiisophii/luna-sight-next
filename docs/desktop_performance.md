# Desktop performance audit — 2026-11-14

The deployed [Lunar Landing Site Navigator](https://kiisophii.github.io/lunar-landing-site-navigator/) loads and rotates successfully on Jiyong's desktop. The first south-pole transition has a reproducible approximately 0.2 s main-thread stall. No production application or scientific data was changed in this audit.

## Environment and evidence

- Windows 11 Pro; Ryzen 5 5600X (6 cores / 12 threads), 32 GB RAM, NVIDIA RTX 5060.
- Installed Chrome 157.0.8103.40, **headed**, 1920×1080 viewport, device pixel ratio 1. CDP confirms NVIDIA D3D11 ANGLE and hardware WebGL/compositing.
- Live version 20. Saved deployed index.html, globe3d.js, globe_app.js and core.js match main `30d7877` after CRLF/LF normalization. Initial local checkout was `c799395` (version 19); its same four source files also match. This is a live-site audit, not a claim that all assets of the two versions are identical.
- Three fresh-browser runs, each with cleared browser cache, followed by a warm reload. No network or CPU throttling. Cold means empty browser cache, not cold DNS/CDN/OS caches.
- [Raw runs and source hashes](desktop_performance/results.json), [blank-screen/revisit diagnostic](desktop_performance/diagnostics.json), [controlled experiments](desktop_performance/controlled.json), [CPU profile](desktop_performance/south_cpu_profile.json).
- AI-operated measurements and screenshot inspection; human sign-off remains pending in SI_USAGE.md.

## Measured results

| Check | Run 1 | Run 2 | Run 3 |
|---|---:|---:|---:|
| Cold first contentful paint | 0.492 s | 0.332 s | 0.300 s |
| Cold first rendered terrain | 2.474 s | 1.374 s | 1.210 s |
| Cold initial terrain settled | 3.306 s | 2.253 s | 2.022 s |
| Warm initial terrain settled | 1.130 s | 1.093 s | 1.075 s |
| First South pole transition settled | 8.441 s | 8.169 s | 7.561 s |
| Main-thread long task during South pole transition | 220 ms | 232 ms | 213 ms |
| Largest frame interval during South pole transition | 194.6 ms | 227.2 ms | 195.1 ms |
| Shackleton 2 km transition settled | 8.316 s | 8.299 s | 8.337 s |

"Settled" includes camera animation and the application's five consecutive 100 ms no-pending checks. It is a conservative scene-readiness measure, **not a continuous freeze** or the first visible content time. Progressive terrain appears during the transition.

Whole-Moon and close-terrain mouse drags were each exercised for eight seconds per run. Actual render-counter rates were approximately 30–31 fps; neither drag phase had a >50 ms rAF gap or a main-thread long task. The 2 km transition also had no >50 ms gap. No page exceptions, failed requests or HTTP errors were recorded in the three runs; adaptive quality remained at its initial level (0).

A blank headed browser itself measured **30.57 rAF fps**. Thus this session does not establish a site-imposed 30 fps limit, and it cannot validate 60 fps capability. rAF and application render counters are proxies, not physical frame presentation or video-encoder measurements. The exact cause of the desktop's approximately 31 Hz baseline was not established.

## Reproducible first-transition stall

1. Open the deployed URL in a fresh Chrome profile and wait for the whole Moon.
2. Click **South pole** for the first time.
3. Observe the brief pause as the closer-view colour texture first becomes available. Record a Performance trace to quantify it.
4. Return to **Whole Moon**, then **South pole** again: in the diagnostic run this took 2.752 s including animation/quiet checks, with no >50 ms gap or long task.

The extra profiling run measured a 219 ms long task. Its CPU profile attributes approximately **207 ms of self samples to `texSubImage2D`** across the transition. `globe3d.js` lazily replaces the 2k colour map with the 8k map below 3000 km camera range. A browser-only controlled experiment retained the 2k texture: the normal run had a 209 ms long task, while the no-hires run had none. Disabling shadow maps still produced a 209 ms task.

This strongly implicates the first high-resolution texture upload rather than sustained terrain rendering. Candidate improvements to investigate are prewarming the upload before an interactive camera transition or using a suitably prepared/compressed GPU texture. Do not permanently downgrade imagery just to hide the stall. Acceptance proposal: no >100 ms main-thread task or frame gap on the first South pole transition in three comparable runs, with high-resolution imagery still present; report cold readiness time separately.

The no-shadow experiment is diagnostic only. Although the camera/time match, tile counts differ (93 versus 63 at the close view), so its screenshots are **not** a controlled pixel comparison of terrain geometry. Fine vertical striping in the distant wall is visible in the [normal close-view screenshot](desktop_performance/shackleton_2km.png); its cause and correctness are unverified and were not classified as a confirmed terrain defect.

## Recording preparation

Use the measured 1920×1080 view as the starting point. Visit the south pole and intended close-ups once and wait for loading before starting the 30-second recording. This avoids the measured first-upload pause. An actual encoder/dropped-frame test is still needed when recording is requested; 4K and 60 fps were not tested. No final video was recorded in this task.

## Reproduction and scope

Install Playwright in the chosen Python environment (`python -m pip install playwright`), with Google Chrome installed at the path used by the script, then from the repository root:

```powershell
python pipeline/desktop_performance.py --runs 3
python pipeline/desktop_performance_control.py
```

Outputs default to ignored `data/processed/desktop_perf/`. Keep the test browser foregrounded. The control script alters responses only inside its disposable browser sessions, never files or the deployed site. Each run closes its own browser.

The requested five-site near-field comparison is already in merged [PR #27](https://github.com/kiisophii/lunar-landing-site-navigator/pull/27) and [near_field_check.md](near_field_check.md). All five centres and their 300 m neighbourhoods lie outside the original PGDA AVGVISIB rasters, so numerical PGDA values and a closer-method ranking remain unavailable. No fabricated comparison was added.
