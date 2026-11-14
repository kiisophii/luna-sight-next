# Assumption and polar-product sensitivity plan

**Goal:** A docs-only PR with six-site height/near-DEM sensitivity, then sixteen-site polar DEM-chain sensitivity. No production changes.

**Method:** Reuse horizon.py and actual core.js metrics over all 43,824 hours of 2026–2030. Preserve each site's production ray grid and chain, verify 2 m masks/metrics exactly before alternatives, change one assumption per comparison. Six sites: SHACKLETON_RIM, ARTEMIS_HAWORTH, ARTEMIS_MALAPERT, APOLLO17, CHANGE4, SLIM. Heights 1/2/3/10 m. For the three nonpolar sites replace only SLDEM2015 within 150 km with native LDEM_128 windows fetched through validated/resumable HTTP Range requests. Keep actual production far-field fallbacks (LDEM_64 then LDEM_16).

For sixteen polar sites, replace the near chain with PGDA 20 m to 3 km and 60 m to 60 km; retain 80/240 m and global fallbacks. Report actual source use, site-height differences, mask RMS over all 720 azimuths, visibility differences and limitations. Product choice includes changed spatial support and reference surface; do not label differences absolute error or assume independent surveys.

Core observer position is hardcoded to terrain h0+2 m. In the diagnostic adapter only, supply h0+(tested height-2) while retaining the tested-height horizon. This is algebraically the desired observer position in unmodified core.js; store the true DEM h0 separately. Verify with an independent vector/time loop. Never write diagnostic h0 to production files.

- [x] Baseline hashes, source labels, original DEM metadata and 2 m equality checks.
- [x] Six-site height and nonpolar near-DEM computations; resumable per case; tables and two-line Limits conclusion.
- [x] Sixteen-site alternative polar chain computations; RMS and visibility tables.
- [x] Separate review/recomputations, sources and SI log. Docs-only diff verification and PR submission follow the completed checks.

Separate verification passed all 56 unique metric cases, six independent scalar cases, nineteen exact baseline controls, two full brute-force masks, independent geometry and fifteen original-server pixel reads. Final review found no numerical/scientific blocker; the CSV/JSON provenance wording was clarified. The task follows the user's docs-only constraint: new source URLs/hashes are recorded in docs/sensitivity_sources.json rather than editing data/DATASETS.md. No production code or data was changed.

Review focus: one-hour sampled longest dark interval; percentage points versus percent; true observer position changes with height; native LDEM window units/pixel registration; far-field preservation; alternate DEM observer elevation is not held artificially fixed; product dependence is not a calibrated uncertainty interval.
