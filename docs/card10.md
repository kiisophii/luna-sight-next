# Card 10: site metrics and validation handoff

Base main: c264135515828a0ef588a7f29927a0c286a0cd2c. Owner branch: s2-metrics-minchul.
Requirements: docs/2단계_분배.md, card 10; data contract v1.1, sections 0, 2, 3, 4 and 6.

## Status and dependencies

- The actual saved two-hour 2020-01-01T00Z inclusive through 2038-08-01T00Z exclusive NPZ exists and passes schema, times, finite-value, overlap and sample checks. It is reused without regenerating either the NPZ or production ephemeris.
- The metrics runner is implemented and tested against a separate Python port. It directly executes the unchanged current web/js/core.js, rather than replacing its definitions.
- This base main has 33 catalogue entries and ZERO horizon files. No real site metric cache can be produced yet. docs/metrics_cache_report.json lists every missing site and complete=false. This is an upstream card 8/9 dependency, not a claim that metrics are complete or that visibility is zero. No synthetic or flat-fallback metric files were added to web/data.
- Fresh Horizons queries at the six requested real catalogue points passed the 0.01-degree criterion. No synthetic equator/pole point is substituted for SLIM or IM-1. Shackleton R04 is a published south-polar study point, not a landed spacecraft.
- Human review is pending; this is implementation-assistant verification, not an independent review or human sign-off.

## Two-hour NPZ for card 11

File: data/processed/ephem_2020-2038_2h.npz (git-ignored, transfer this file separately).
SHA-256: 358526e031babbe9944695b253ad36f2f63f15cb0175225dfcf04c62886ccabe.
Size: 1,969,747 bytes; vectors shape 81,444 x 6, little-endian float32; frame MOON_ME_DE421; units km.
Columns: sun_x, sun_y, sun_z, earth_x, earth_y, earth_z.
UTC hour_index is relative to 2026-01-01T00Z: first -52,608, last 110,278, step 2.
Final time is 2038-07-31T22Z. The stop is exclusive.

Use the stored hour_index for negative pre-2026 times. Do NOT index the five-year production array with those hours or use core.js bodyVec clamping for the 18.6-year validation. The NPZ contains the required independent time coverage.

Every overlapping two-hour sample (21,912 rows) equals the corresponding float32 ephem.bin row exactly. All NPZ rows were checked for schema/time/finite values; five rows were recomputed with Skyfield and matched. This is not a complete independent 18.6-year astronomical accuracy check. See docs/card10_npz_check.json.

```sh
python -m pip install -r pipeline/requirements-ephem.txt
python pipeline/check_validation_npz.py
# If the separately transferred NPZ is unavailable, generate only that file:
python pipeline/check_validation_npz.py --generate-if-missing
```

The missing-file generation route uses existing ephem.generate checkpoints and can resume after interruption. It does not regenerate the web ephemeris. Raw kernels remain ignored. Sources, frame and leap-second assumptions remain those in docs/ephem.md and data/DATASETS.md.

## Metrics: exact app definitions

```sh
node pipeline/cache_metrics.mjs
# Fail with exit code 2 when any catalogue site still lacks eligible real terrain:
node pipeline/cache_metrics.mjs --require-all
```

When card 8/9 horizon files are merged, update this branch from main, rerun the command and commit web/data/metrics/<ID>.json together with docs/metrics_cache_report.json. No code edits are needed to discover newly available horizon files.

For each site with an eligible real horizon, the runner calls actual core.metrics(site, 0, 43823): 43,824 inclusive hourly samples, 2026-01-01 through 2030-12-31. sun_frac is the fraction of samples where the visible solar disk fraction is at least 0.5, not the average visible disk area. earth_frac uses Earth centre strictly above the interpolated horizon mask. both_frac counts the intersection. longest_dark_h counts the longest consecutive hourly not-sunlit run, clipped to this window; it does not refine transitions within an hour or wrap December into January.

Output keys are exactly id, window, sun_frac, earth_frac, both_frac, longest_dark_h, slope_deg. window is 2026-01-01..2030-12-31. slope_deg is null because no measured slope is supplied; no slope is invented from a horizon mask. Fractions are stored at full numeric precision.

The runner refuses missing, mock/flat, coordinate-mismatched, nonfinite, wrong-shape, wrong-observer-height and incomplete-DEM horizons. It requires the 720-bin, 0.5-degree mask, observer 2 m, finite h0_m, real DEM provenance and no reported missing samples. An existing cache is removed if its source horizon becomes unavailable or invalid. No app flatHorizon fallback is called.

All catalogue elev_m values remain null (unknown). With a real horizon, core.js uses its h0_m for observer height; that is the height the runner uses. Without real terrain, the app's height zero and flat mask are mock assumptions; they are never exported as a real cache by this pipeline. Non-Apollo/Luna exact source datums remain unverified as documented in docs/sites.md.

Results are written atomically after each site, with per-site input and output SHA-256 values in the separate report. A rerun skips previously completed sites only if the core, ephemeris, site, horizon and saved output hashes match. One process is used; no all-core job is started.

## JS/Python equivalence and cache behavior checks

```sh
node pipeline/test_metrics.mjs
```

Requires Python with NumPy; set PYTHON to the Python executable if needed. The test runs actual core.js and a separate vectorized Python port over the complete five-year real ephemeris at three synthetic terrain fixtures (equatorial, south-polar and signed-longitude/height cases), plus every eligible real horizon currently present. In this base there are no real horizons; all four aggregate values match exactly on the three fixtures, exceeding the requested agreement to four decimals. Rerun after terrain arrives to check the real sites as well. Synthetic fixtures exist only in a disposable directory and are never written as app data. The test also exercises atomic per-site caching, resume, stale-cache removal, and rejection of mock, coordinate-mismatched and incomplete-DEM inputs. See docs/metrics_equivalence_check.json. The test does not establish the accuracy of a real terrain mask.

## Six real points versus JPL Horizons

```sh
python pipeline/validate_real_sites.py --prepare-requests
python pipeline/validate_real_sites.py
# Or reuse the URL-checked raw cache:
python pipeline/validate_real_sites.py --offline
node pipeline/check_real_sites_web.mjs
```

Six points are read from current sites.json: APOLLO17, CHANGE4, SHACKLETON_RIM, CHANDRAYAAN3, SLIM, IM1. There are 121 times per body/site at 12-hour spacing over 60 days, 2026-01-01T00Z to 2026-03-02T00Z inclusive: 1,452 comparisons. Apollo 17 and Chang'e 4 use the current catalogue coordinates, not the older card 1 test coordinates.

Fresh response URLs, retrieval times, hashes, API signatures and per-point max/mean errors are recorded in docs/real_sites_horizons_check.json. Raw responses are isolated in ignored data/raw/horizons_card10. Actual unchanged core.js in Node also passes: maximum azimuth difference 0.000029621078624586517 degrees, maximum elevation difference 0.000033907861642923365 degrees. Python/JS azimuth agreement is exact for this set; maximum elevation difference is 1.4210854715202004e-14 degrees. See docs/real_sites_web_check.json. This is a new point set, so its smaller maximum error does not supersede the older test's 0.000444751-degree result.

All six terrain heights are explicitly zero for this geometry comparison, with observer +2 m above the 1737.4 km sphere in both systems. Heights are not measured, and the Shackleton point is not a terrain-height validation. Horizons reports DE441/high-precision MEAN_ME; production follows required DE440s/DE421. Moon-centred apparent vectors minus observer remain an approximation; direct topocentric Skyfield comparisons are recorded separately. This test does not validate terrain obstruction, independent five-year interpolation, or all 18.6 years.

Sources: JPL Horizons API https://ssd.jpl.nasa.gov/api/horizons.api and documentation https://ssd-api.jpl.nasa.gov/doc/horizons.html ; exact point sources and datum limits: docs/sites.md and docs/sites_source_audit.json ; NAIF sources and package hashes: data/DATASETS.md and docs/ephem_provenance.json.
