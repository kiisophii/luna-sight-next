# First-zoom texture stall implementation plan

> **For agentic workers:** Use superpowers:executing-plans for this scoped fix.

**Goal:** Remove the first 8K colour upload pause without changing scientific data, imagery files, index.html or the final texture resolution.

**Architecture / short design:** Keep the existing lazy 2K-to-8K transition and prepare its RGBA pixels in a dedicated worker. Transfer the buffer into a DataTexture, retaining the 2K image until ready. Initial ImageBitmap-only preparation still stalled during main-thread pixel conversion; the worker moves this conversion as well as decode/orientation away from input/rendering. User explicitly delegated selection based on profiling, so no additional design approval is needed.

**Tech stack:** Three.js r170, browser ImageBitmap/WebGL2, headed Chrome, Playwright/CDP.

**Spec:** User request and docs/desktop_performance.md / issue #37.

## Alternatives and constraints

- Preloading the whole image shifts work and adds 6.6 MB before anyone zooms; avoid unless measurements justify it.
- Keeping a lower-resolution placeholder permanently loses detail; retain the exact 8K asset.
- Splitting uploads needs more WebGL state/resource handling; only use if asynchronous preparation is insufficient.
- Production changes confined to globe JS modules. Benchmark/review documentation is separate. No data or index.html changes; PR only, Sua merges.
- Compare the same local assets with base 64e3bee globe module versus the changed module, 3 cold runs per desktop and throttled laptop profile (4x CPU, 10 Mbps down / 1 Mbps up, 70 ms latency). This emulates CPU/network, not a laptop GPU.

## Review focus

Image orientation/colour/mipmaps and full resolution; cancellation during download/decode; failure retains 2K; no high-res request before zoom; GPU resource cleanup/context restoration.

## Task 1: Measure and fix texture preparation

- [x] Baseline benchmark reproduces >100 ms large texture upload / first-zoom pause before edits (230.8 ms desktop, 683.8 ms throttled).
- [x] Add explicit acceptance check for large upload <100 ms, 8K final image, no early 8K request, and no page errors.
- [x] Change only globe3d.js loading/disposal and new globe_color_worker.js as justified by measurement.
- [x] Verify initial 2K, full 8K, orientation/colour against legacy texture, context restore, HTTP/decode failure, termination, no-worker legacy path and 4K hardware texture cap. Cap test failed at 8192 before adding capability limit; passed at 4096 after.

## Task 2: Before/after evidence and handoff

- [x] Run desktop/laptop profiles three times for both variants, record max task/frame interval, rotation FPS and transfer bytes (24 final runs, no recorded request/page/HTTP errors).
- [x] User follow-up: also compare a 4K diagnostic JPEG, both implementations and profiles. Server-only resampling; original files unchanged. Additional 4K worker profile identifies remaining terrain build cost, 59.3 ms slowest mesh.
- [x] Keep raw results, runnable benchmark, limitations and source references in docs/texture_stall/ and docs/texture_stall_fix.md.
- [x] Independent read-only review found no production blockers; fixed worker-download accounting and documented main-thread-only CPU throttle. Incorporated main 7e7964e; relevant runtime/data unchanged. Browser correctness and JS syntax checks pass; data/index diff empty.
- [x] Append SI log and final staged checks. Full unchanged contract passes with Git LF sources; raw Windows CRLF provenance mismatch documented, no checkout/data normalization.
- [x] Commit and open [PR #52](https://github.com/kiisophii/lunar-landing-site-navigator/pull/52) with measurement table. PR remains unmerged for Sua. Main 115d285 incorporated, preserving all incoming SI rows plus this task's row; no measured runtime/data change.
