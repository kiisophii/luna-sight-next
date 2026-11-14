# Card 23 Coordinate Uncertainty Implementation Plan

**Goal:** Deliver 33 site neighbourhood grids (121 nodes each), radial statistics and independently verified uncertainty ranges in a reviewable PR.

**Architecture:** Reuse horizon.py and the actual core.js JSON-lines bridge. Six single-threaded worker processes handle sites, checkpoint every node and skip valid cached work. Export only complete sites with matching catalogue-centre metrics. A separate verifier uses PROJ/ECEF full-ray geometry and an independent hourly metric loop.

**Tech Stack:** Python/NumPy, existing Numba sampling, Node/core.js, pytest, Windows.

**Spec:** User's Card23 assignment in this thread (2026-11-14), with explicit follow-up authorization to start on CPU using six threads after timing showed about9–10minutes of computation. Branch s3-uncert-jiyong from main a3f3fd5.

## Global constraints
- 11x11 offsets -500..500m in100m steps; spherical geodesic mapping; 2m observer,720azimuths,curvature,2026–2030 hourly ephemeris.
- Retain each site's existing main DEM chain, including LDEM64/LDEM16 far field, and legacy horizon sampling. Polar sites use finest available PGDA data; nonpolar sites use their existing SLDEM/Card9 coverage. Record fallback resolution.
- Circular radii100/300/500m, min/max/p10/median/p90 for all4metrics. Quantiles are spatial empirical summaries, not confidence probabilities.
- Node60 at centre must match existing metrics; do not silently substitute copied values for a mismatched recomputation.
- No baseline changes: five near-field alternatives are a separate experiment only. PGDA69 has no coverage for those nonpolar centres, so reference values and closeness rankings must be marked unavailable.
- Keep948mGPU task separate. No UI files; PR for integrator review, no merge.

## Tasks
- [x] Tests: grid ordering/distances, circle counts, quantiles, centre mismatch rejection, invalid/stale checkpoint rejection.
- [x] Implement resumable CPU pipeline and provenance; execute polar sites then remaining sites with6workers.
- [x] Propose uncertainty contract section; generate300m summary table and >10percentage-point list.
- [x] Independent session verifies5random nodes per site for3sites (polar/midlatitude/equatorial), full horizons and independent hourly metrics;1pp fraction tolerance, report dark-hour differences.
- [x] Verify all33centres and JSON/contracts, review code, merge latestmain, rerun affected checks and open/attach PR.

## Review focus
No radius/square confusion; no source holes hidden by fallbacks; valid centre comparison; cache identity changes when code/data/coords change; no public partial output. Shared raw data junction is read-only by policy. Card23 processed outputs stay in this worktree.

## Execution ledger
CPU timing measured99points across all33sites with6workers; extrapolated546–600seconds, allowing15–20minutes for practical compute overhead. Existing13local-map/impact tests passed. Native worktree creation failed host path validation twice; manual Git worktree created without changing active Card14 checkout. Raw data junction points to existing verified inputs; no raw data edits/downloads yet.

## Accepted steering

User explicitly chose unchanged current-main methods and baseline values. Main polar16 sites already use5m/8000steps, nonpolar17 use200m/4000steps; each site's own horizon parameters and complete legacy chain are now used. No baseline updates. Five separate near-field experiments will compare old/new and show PGDA reference N/A: all five are below65degrees absolute latitude and outside product69. It is impossible to rank closeness to missing PGDA values; this limitation goes in the PR table. Initial polar computations passed, and final provenance-consistent all33run is underway with6workers.

Completed 2026-11-14 19:17 KST: final computation 409.16s, independent audit 58.53s; all33centres exact, all15independent nodes exact in fraction/dark-hour metrics. Full suite159passed; contract checker0errors/0warnings. Latest main a832d22 merged, preserving seasons section17 and uncertainty section18. PR: https://github.com/kiisophii/lunar-landing-site-navigator/pull/27 . No baseline horizon/metrics changes. Worktree retained for integrator feedback.
