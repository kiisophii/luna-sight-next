# Terrain build and zoom-transition follow-up

This extends the colour-upload fix in [PR #52](https://github.com/kiisophii/lunar-landing-site-navigator/pull/52). The comparison baseline is **d5e2dd7, already using the 8K colour worker**. It does not count the earlier texture improvement again.

## Exact-result optimization

Band tiles repeated the same longitude trigonometry down every column and latitude trigonometry across every row. `makeLayout().directions()` computes these once per column/row as Float64, then performs the same multiplication, normalization and Float32 storage. Polar direction formulas remain unchanged.

Every tile also recreated the same surface/skirt triangle indices. A globe now creates those immutable CPU arrays once, using Three's original index-type selection. Each tile still owns separate BufferAttributes/GPU buffers, so disposing one mesh does not invalidate another. Normals, UVs, positions, heights, skirt geometry, LOD thresholds, mesh stride, terrain resolution and scientific algorithms are unchanged. No geometry worker, delayed build state or permanent resolution reduction was needed.

## Verification

`python docs/mesh_stall/verify.py --variant baseline`, then `--variant fixed`, generates **64 complete meshes**: 16 real band/north/south tiles across low/middle/high available LOD, each at exaggeration 3, 1, 5, then 3 again. All seven typed-array hash/type/length records (height, position, vertex normal, UV, normal-map pixels, surface indices and skirt indices), mesh centres and bounding spheres match exactly. Evidence: baseline_geometry.json / fixed_geometry.json in this folder's companion evidence directory. This verifies representative output equality, not the absolute accuracy of NASA terrain.

Independent read-only review confirmed the recorded comparisons, Float64 arithmetic, per-globe immutable topology and separate GPU-attribute ownership. A minor unused polar-row trig/allocation cost remains; it does not change results and was not expanded into another optimization during this measurement.

## Measurement scope

- Same desktop, headed Chrome, hardware GPU and harness as [the texture report](texture_stall_fix.md). Full production 8K stays enabled.
- Desktop 1920×1080 native; limited profile 1366×768, 4× **main-thread** CPU, 10 Mbps / 1 Mbps / 70 ms latency. Physical GPU/worker hardware is still the desktop, not a real laptop.
- Three cold runs per variant/profile (12 runs). Each measures initial scene, first South pole transition, four-second drag, first 2 km detail view, zoom out to 6500 km, then return to the same 2 km view.
- Revisit means a real zoom-out/in sequence, **not a guaranteed full cache hit**: camera travel and LRU/LOD selection can create additional geometry. Older baseline raw records call this `detail_cached`; that name does not establish cache-only work. Report it as detail revisit.
- No data files or index.html edits. The 2K/8K image paths and scientific calculations remain unchanged. All source hashes and per-run quality/tile counts are retained with timing data.

## Separate mesh-cost diagnostic

To separate mesh construction from the remaining 8K upload, a profiled limited-profile run uses the same **server-only 4K diagnostic JPEG** as the earlier report. The two runs each built 157 meshes during first South pole loading:

| Diagnostic | Colour-worker baseline | Additional mesh optimization |
|---|---:|---:|
| Combined synchronous mesh build time | 6,675.4 ms | 3,308.4 ms |
| Slowest individual mesh build | 59.3 ms | 45.9 ms |
| First-transition maximum frame gap | 98.4 ms | 65.9 ms |
| First-transition p95 frame gap | 65.4 ms | 33.6 ms |
| Long tasks ≥50 ms during transition | 155 | 24 |

Combined mesh CPU time falls about **50% in this diagnostic**. This is not a claim that complete map downloads or all zooms become twice as fast. Profile overhead and environment variance apply; headline interaction comparisons use separate unprofiled runs. The six-millisecond queue budget still cannot preempt a single build, so remaining long frames are possible.

## Production 8K zoom-cycle measurements

Each entry is the median of three runs; values are before → after this mesh change. Frame gaps measure rendering intervals, not network wait. Settled time includes camera animation, downloads, builds and quiet polls, so it is **not continuous freezing time**.

| Profile / transition | Settled time (s) | p95 frame gap (ms) | Maximum frame gap (ms) | Tasks ≥50 ms |
|---|---:|---:|---:|---:|
| Desktop / first South pole | 8.06 → 6.19 | 33.1 → 33.1 | 33.6 → 33.6 | 0 → 1 |
| Desktop / first 2 km detail | 8.97 → 8.36 | 33.1 → 33.0 | 33.6 → 33.5 | 0 → 0 |
| Desktop / zoom out | 4.98 → 3.96 | 33.1 → 33.0 | 33.5 → 33.4 | 0 → 0 |
| Desktop / detail revisit | 7.04 → 5.62 | 33.1 → 33.1 | 33.6 → 33.6 | 0 → 0 |
| Limited / first South pole | 21.94 → 21.99 | 64.8 → 61.3 | 97.3 → 97.7 | 150 → 40 |
| Limited / first 2 km detail | 13.81 → 12.79 | 97.3 → 65.7 | 98.7 → 97.7 | 156 → 151 |
| Limited / zoom out | 4.34 → 3.35 | 97.8 → 65.4 | 130.6 → 97.8 | 36 → 12 |
| Limited / detail revisit | 5.17 → 4.21 | 97.2 → 33.6 | 98.7 → 65.4 | 36 → 7 |

Desktop first-South readiness improves 23%, zoom-out 21% and revisit 20%; desktop frame spacing was already near this session's 30 Hz cadence. Limited first-South long tasks fall 73%, but its readiness and maximum frame gap do **not** improve. Detail-first long-task counts barely change and fixed runs still contain 98 ms gaps. This is a reduction in repeated work and some transition delays, not elimination of all LOD stutter. Fixed first-South maximum task reaches 115 ms in one limited run (baseline maximum 102 ms); medians do not guarantee lower worst-case pauses.

All twelve runs had zero recorded page/request/HTTP errors and zero frames with no rendered terrain during the zoom cycles. Final tile/triangle counts match between variants: South desktop 114 / 2,646,016, limited 108 / 2,715,648; detail desktop 81 / 870,400, limited 84 / 1,183,744; zoom-out both 11 / 382,976. Existing adaptive quality is 0 except the third baseline limited run's detail/out/revisit phases (2). All fixed phases remain 0; no reduced quality was introduced to obtain the improvement. This environmental variation limits precision of the three-run comparisons.

Evidence: [summary with medians, ranges and all three samples](mesh_stall/summary.json), [baseline runs](mesh_stall/baseline.json), [fixed runs](mesh_stall/fixed.json), [baseline mesh hashes](mesh_stall/baseline_geometry.json), [fixed mesh hashes](mesh_stall/fixed_geometry.json), [new diagnostic](mesh_stall/diagnostic.json), [baseline diagnostic](texture_stall/diagnostic.json), [review](mesh_stall/review.md).

Further reduction of occasional long frames would require profiling and splitting/offloading the remaining per-tile normal/mesh work and GPU uploads. Network waiting also remains. This change keeps the existing incremental tile replacement and LOD selection intact; it does not implement a new LOD scheduler, preloader or cross-fade.

Settled drag FPS medians are desktop 30.26 → 30.18 and limited 29.18 → 30.60, consistent with the session's roughly 30 Hz cadence. Initial local response payload is 4,787,332 → 4,789,495 bytes in both profiles (server accounting, excludes HTTP overhead/CDN resources); the small increase is JavaScript text, not a new data download. These numbers use a different accounting boundary from the original report's page-CDP initial transfer. No extra terrain or colour asset was introduced.

## Reproduce

```powershell
python docs/mesh_stall/verify.py --variant baseline
python docs/mesh_stall/verify.py --variant fixed
python docs/mesh_stall/benchmark.py --variant baseline --runs 3
python docs/mesh_stall/benchmark.py --variant fixed --runs 3 --check
python docs/mesh_stall/benchmark.py --variant fixed --runs 1 --profiles laptop --texture-size 4096 --cpu-profile --out data/processed/mesh_stall/profile
```

The benchmark reuses the existing server/measurement code and adds zoom cycles; the original texture-only benchmark defaults are unchanged. Scientific inputs remain the existing [LOLA/SLDEM/PGDA sources](../data/DATASETS.md). Index format follows the pinned [Three.js r170 BufferGeometry](https://github.com/mrdoob/three.js/blob/r170/src/core/BufferGeometry.js).
