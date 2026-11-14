# Card 8 Polar Horizon Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, followed by a fresh whole-branch review. The user authorized execution on 2026-11-14.

**Goal:** Deliver verified 720-direction horizon masks for all 16 catalog sites south of -80 degrees, plus three-site resolution sensitivity.
**Architecture:** Reuse the merged horizon engine and existing resumable PGDA/PDS fetchers. Preserve original elevations and finest available terrain; explicitly record missing high-resolution coverage. Generate small contract-compatible files offline, never move this workload into the browser.
**Tech Stack:** Python, numpy, tifffile, pyproj, requests; existing venv; two workers maximum initially.
**Spec:** docs/2단계_분배.md card 8; docs/data_contract.md sections 0-3 and proposed section 9.

## Global Constraints
- Observer 2 m, R=1737400 m, MOON_ME, east-positive longitude, 720 azimuths, curvature included, radius 300 km.
- Preserve source resolution. 5 m within 3 km where available, 10 m within 25 km where available; existing intermediate windows and 240 m within 200 km, LDEM beyond.
- No raw terrain in git. No main merge or index.html edits. SI log appended with human fields TO CHECK.

## Review Focus
- Sources not covering a site: explicit absent/partial coverage, never invented 5 m data.
- The engine default 200 m inner cutoff can omit nearby terrain: use and test a documented 5 m inner radius for card 8; independently check finer sampling.
- Missing/no-data samples and cache reuse: require zero missing samples for production and coordinate/parameter matching.
- Sensitivity must actually replace the near field with 80/240 m, including the observer height, without mutating the original chain.
- Independent verification must use separate spherical geometry and DEM interpolation, no early stop, finer distance sampling.

## Task 1: Real-site terrain acquisition
Files: pipeline/fetch_polar.py; pipeline/tests/test_fetch_polar.py; ignored data/raw and data/processed.
- [x] Add failing tests for opt-in clipped windows and non-overlap rejection; retain strict default.
- [x] Implement minimum optional coverage clipping and record requested/clipped extent in cache metadata.
- [x] Fetch full windows resumably by resolution with at most two concurrent independent source readers; fetch LDEM_16/64 for far field.
- [x] Save coverage manifest and verify finite data at all sites. Expected: 16 usable chains, unavailable 5/10 m sources explicit.

## Task 2: Production masks and sensitivity
Files: pipeline/card8_horizons.py, pipeline/tests/test_card8_horizons.py, web/data/horizon/*.json.
- [x] Test selection, true 80/240 m near-field replacement, unchanged far field, completeness; exercise resume identity on real saved records (permanent resume regression tests remain a minor follow-up).
- [x] Implement a small CLI using run_horizons.build_chain and horizon.compute_horizon, min_km=0.005, max_km=300, n_steps chosen after convergence check.
- [x] Run all 16 masks with zero missing samples, atomic output and resume.
- [x] Three sites with full 5 m coverage: SHACKLETON_RIM, CONNECTING_RIDGE, ARTEMIS_DE_GERLACHE_RIM2; baseline versus 80 m and 240 m over the same 3 km near field; report RMS/max angular change and observer-height change.

## Task 3: Independent verification and delivery
Files: pipeline/verify_card8_horizons.py, docs/polar-horizons.md, data/DATASETS.md, docs/SI_USAGE.md.
- [x] Separate verifier: two sites x ten azimuths, independent geometry and bilinear sampling, no early stop. Compare identical distance grids (numerical consistency) and finer grids (sampling convergence), recording observed differences rather than asserting an invented scientific tolerance.
- [x] Run engine/fetch/card8 tests and full repo pytest; inspect any unrelated failures. Run check_contract.py and ensure 16 production files.
- [x] Fresh reviewer verifies numerical method and final diff; fix material issues with regression tests.
- [x] Document coverage, computation parameters, measured validation/sensitivity, limitations and reproducible commands; append SI log.
- [ ] Push feature branch and open PR for Sua (no merge).
