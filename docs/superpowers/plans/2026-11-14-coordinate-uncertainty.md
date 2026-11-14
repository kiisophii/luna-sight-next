# Card 23 Coordinate Uncertainty Implementation Plan

**Current goal:** Deliver 16 south-polar site neighbourhood grids (121 nodes each), matching Sua's shared schema, plus the five-site near-field diagnostic. Sua owns the 17 nonpolar grids. The original 33-site run below is retained as execution history.

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

## Follow-up scope (2026-11-14 19:29 KST)
User reassigned nonpolar 17 outputs to Sua. This PR now delivers polar 16 only, adopts nodes/ranges/n_nodes plus common metadata from s3-uncert-nonpolar-sua 30c64f6, rechecks unchanged centre baselines, and adds docs/near_field_check.md with original-PGDA footprint checks and native-pixel near-field diagnostics. Baselines stay untouched; source support cannot be fabricated.

Follow-up verified: 16 sites / 1936 nodes in 288.11 s, all node values unchanged from prior run and all centres exactly match latest main a832d22. Sua's format-only validator passed all 16 outputs. Separate-session 15-node brute-force audit passed in 84.14 s: rounded records 0 pp/0 h; unrounded maximum 0.002281855 pp (one hourly Earth state), dark 0 h. Full suite 162 passed; contract 0 errors/0 warnings. Five centres recomputed, step-only controls unchanged, original PDS footprint checks exclude every 300 m disc; no isolated positive native-pixel spike candidates under the documented heuristic. Physical accuracy remains unverified.
