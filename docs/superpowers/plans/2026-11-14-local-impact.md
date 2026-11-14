# Card 18 local impact implementation plan

> Execute inline with executing-plans and TDD. The user supplied the scope, methods, branch and independent-check requirement and authorized execution.

**Goal:** show measured local variation around six southern sites and quantify Card 13 tower benefits without inventing an impact claim.
**Spec:** user's Card 18 handoff: start s3-local-jiyong from s3-relay-full-jiyong; six ±10 km grids at 1 km; 2026–2030 exact core.js metrics; radial 1/3/5/10 km min/max/IQR; striking separated pair; direct<50% relay summary; resumable all cores; independent five random point checks within 1 pp; merge latest main before PR.
**Architecture:** horizon.py computes each point's 720-bin mask from expanded source windows with range gates relative to that point. A persistent Node helper evaluates the actual production core.js, avoiding another metrics implementation. Per-point atomic checkpoints feed six compact public JSON maps and reports. NumPy memory maps share expanded rasters across workers.
**Tech stack:** existing Python/NumPy/Numba, Node, PGDA fetcher and production ephemeris.

## Global constraints
- Six IDs: SHACKLETON_RIM, ARTEMIS_HAWORTH, ARTEMIS_MALAPERT, CONNECTING_RIDGE, PEAK_NEAR_SHACKLETON, DE_GERLACHE_RIM1.
- 21×21 points, row-major south to north, west to east; spherical geodesic offsets; exact coordinates retained. Radial statistics include grid nodes within each radius, not the entire square.
- Observer 2 m, R=1737400 m, MOON_ME_DE421, 720 azimuths, minimum ray distance 5 m, maximum 300 km, 8001 logarithmic distances, curvature. Original range gates 3/25/25/60/60/200 km for 5/10/20/60/80/240 m sources; global fallback. Expanded windows add 16 km of spatial margin, not extra gate radius.
- Actual hourly core.js definitions, all 43824 samples; fractions 0..1, darkest run in hours. Earth visibility is geometric DTE availability, not station coverage.
- Original Card 13 raw/output files unchanged. Missing 5 m source coverage falls back explicitly, never extrapolates or becomes zero terrain. No missing final rays.
- All logical CPU workers allowed, BelowNormal and single numerical thread each. Resume fingerprints include source hashes, core/ephemeris/engine code, parameters and coordinates. No raw/checkpoint files in git.
- No main merge by this agent; merge origin/main INTO this feature branch before PR. Only Sua edits web/index.html.

## Review focus
- Shifted observers must not inherit original-center radial gates or silently lose 5 m coverage at cache edges.
- Changed DEM, ephemeris, core or geometry must invalidate stale checkpoints.
- Longitude wrapping/polar crossing and row order must remain correct.
- Pair selection must use actual separation and expose adjacent-point contrast rather than imply arbitrary extrema are neighbours.
- Relay threshold counts and single-tower outages must come from each height's single tower, not the multi-tower network.

### Task 1: resumable local grids
Files: pipeline/local_maps.py, pipeline/local_metrics.mjs, pipeline/test_local_maps.py, docs/data_contract.md.
Interfaces: horizon.py samplers/compute_horizon, actualCore/loadEphemeris; per-point checkpoints {index,e_m,n_m,lat,lon,horizon,metrics,input_key}; public {id,center,grid,window,params,provenance,points,complete,mock}.
- [ ] RED: geodesic grid centre/wrap and ordering; range gates independent of expanded-window radius; memory-map sampling equal to original sampler; changed fingerprints invalidate resume; reject incomplete maps.
- [ ] GREEN: generate masks, persistent Node metrics, atomic per-point resume, validated six map files. Add proposed contract section.
- [ ] Compare actual core helper on a synthetic horizon and catalogue centre. Benchmark before all-core run; commit.

### Task 2: impact summaries
Files: pipeline/local_impact.py, pipeline/test_local_impact.py, docs/location_sensitivity.md, docs/relay_impact.md.
Interfaces: Task 1 public JSON and Card 13 relay records; report provenance identifies exact hashes.
- [ ] RED: circular-radius membership/IQR, geodesic pair distance, adjacent-pair selection; one-tower outage excludes other network towers; strict<50 and >=50 threshold counts.
- [ ] GREEN: reproducible min/max/Q1/Q3/IQR for four metrics and four radii, strongest pair by metric plus nearest-neighbour contrasts; full-catalogue low-direct tower counts and remaining outages. Commit.

### Task 3: production, independent evidence and integration
Files: six web/data/local/*.json, docs/card18_validation.json, runtime/source/SI records; separate-session verifier.
- [ ] Complete expanded terrain, all-core calculation and unchanged-input resume check.
- [ ] Independent session draws five points uniformly without replacement with fixed seed20261114; PROJ/ECEF brute-force720-ray calculation and independent full-window metric evaluation; all fraction differences <=1 pp, report darkest-run differences.
- [ ] Merge latest origin/main; rerun affected outputs if core/ephem/horizon/source inputs changed. Run contract and full tests, independent artifact review, commit/push PR with measured timings. Do not merge PR.
