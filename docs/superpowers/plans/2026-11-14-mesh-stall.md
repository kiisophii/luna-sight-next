# Terrain build performance plan

**Goal:** Reduce the remaining synchronous terrain-build cost, preserving every terrain/output value and scientific dataset. Extend open PR #52; do not merge.

**Baseline:** PR #52 head d5e2dd7. Its 4K limited-profile diagnostic recorded a 59.3 ms mesh build and approximately 98 ms frame gap. Main 4fbdd63 contains no relevant runtime change.

**Approach:** First remove repeated work inside the existing algorithm: reuse exact Float64 longitude/latitude trigonometric values across a band tile's rows/columns, and compute identical immutable grid/skirt indices once per globe. Preserve per-tile BufferAttributes/GPU ownership. Keep all arithmetic expressions and output types unchanged. Compare bytes before accepting. If measurement is insufficient, consider a worker or incremental build; avoid async lifetime complexity without evidence.

**Alternatives:** A worker isolates CPU work but introduces copied heights, asynchronous generation/version handling and fallback paths. Chunking reduces individual pauses but delays completion and adds partial-build state. Neither is selected before measuring the simpler exact-result optimization.

**Review focus:** Identical band/polar outputs and boundary coordinates; Uint16/32 index selection; separate GPU-buffer ownership and disposal; exaggeration rebuilds; memory and cache lifetime.

- [x] Capture pre-change geometry/normal texture/index/height/bounds hashes for real band/north/south tiles and exaggeration rebuilds.
- [x] Implement exact-result caching in globe3d.js only; verify all 64 complete meshes are unchanged.
- [x] Measure before/after (PR52 colour fix retained), desktop and main-thread CPU/network-limited profiles, three runs each; separate profiling from timing. Keep 8K default, use 4K diagnostic to isolate mesh work.
- [x] Report observed improvements and remaining limitations, independent review and SI log; no data/index.html changes.

Latest integration target: origin/main 6829725. Changes since the timed baseline include documentation, gmaps z4 overlay tiles and Korea permission text; globe renderer, globe harness, terrain inputs and core.js are unchanged. Incorporate main before pushing the PR update. Measurements remain pinned to the source hashes in the evidence, not to subsequent unrelated metadata.
