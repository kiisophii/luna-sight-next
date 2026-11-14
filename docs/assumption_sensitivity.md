# Sensitivity to observer height and nonpolar terrain product

**All six recomputed 2 m production cases match both the production horizon mask and all four metrics exactly.** This experiment changes one assumption at a time and leaves production files unchanged.

## Submission Limits — two lines

> Across six tested sites, changing observer height from the assumed 2 m to 1–10 m changed sunlight availability by up to 10.69 percentage points, Earth visibility by 9.40 points and the longest sampled darkness by 273 hours; these are sensitivity results, not calibrated error bounds.
> Replacing the 59 m near-field DEM with a native ~237 m product at three nonpolar sites changed sunlight by at most 0.13 percentage points (Earth visibility unchanged), so these tests do not establish global accuracy or resolve subpixel terrain.

## Controlled method

- Requested sites: SHACKLETON_RIM, ARTEMIS_HAWORTH, ARTEMIS_MALAPERT, APOLLO17, CHANGE4, SLIM; heights 1, 2, 3 and 10 m above the same local DEM surface.
- Same production horizon.py engine, 720 azimuths at 0.5 degrees, curvature and 300 km reach. Per-site original ray grids: polar 0.005–300 km/8000 steps; nonpolar 0.2–300 km/4000 steps. The production nonpolar omission of terrain within 200 m is preserved.
- All 43,824 hourly ephemeris samples, 2026–2030, with actual unmodified core.js metrics: sunlit = at least half the solar disc visible, Earth centre above mask, both = conjunction. Longest darkness is the longest sampled run within this five-year window, in integer hours; no sub-hour claim.
- The horizon is recalculated at the tested height. Because core.js hardcodes observer position as DEM h0 + 2 m, only the diagnostic adapter input uses h0 + (tested height - 2); unmodified core.js then sees the correct physical observer radius. True DEM h0 is separately retained in the evidence. This temporary equivalent input is never written to web/data. Both terrain horizon and topocentric Sun/Earth positions therefore use the tested height.
- Horizon serialization uses the production four-decimal mask and two-decimal h0 precision, so the 2 m control can be compared exactly with metrics/<ID>.json. The baseline equality check happens before accepting alternative results.
- In the DEM experiment, observer height remains 2 m above each product's own surface. Native LDEM_128 replaces only SLDEM2015 within 150 km. The actual production far field remains LDEM_64 followed by LDEM_16 as fallback; it is not silently replaced by a different far-field chain.

## Height results

Each cell is **value (difference from that site's production 2 m case)**. Visibility values are percentages; visibility differences are percentage points. Darkness and its difference are hours.

| Site | Height m | Sun % (Δ pp) | Earth % (Δ pp) | Both % (Δ pp) | Longest darkness h (Δ h) |
|---|---:|---:|---:|---:|---:|
| SHACKLETON_RIM | 1 | 79.370 (-5.456) | 49.859 (-0.084) | 41.931 (-2.430) | 146 (+71) |
| SHACKLETON_RIM | 2 | 84.826 (+0.000) | 49.943 (+0.000) | 44.362 (+0.000) | 75 (+0) |
| SHACKLETON_RIM | 3 | 86.131 (+1.305) | 50.030 (+0.087) | 44.811 (+0.450) | 75 (+0) |
| SHACKLETON_RIM | 10 | 86.546 (+1.721) | 50.602 (+0.659) | 45.484 (+1.123) | 72 (-3) |
| ARTEMIS_HAWORTH | 1 | 44.042 (-10.688) | 52.312 (-6.225) | 24.331 (-7.074) | 697 (+273) |
| ARTEMIS_HAWORTH | 2 | 54.730 (+0.000) | 58.536 (+0.000) | 31.405 (+0.000) | 424 (+0) |
| ARTEMIS_HAWORTH | 3 | 55.960 (+1.230) | 64.230 (+5.693) | 35.024 (+3.619) | 418 (-6) |
| ARTEMIS_HAWORTH | 10 | 57.204 (+2.474) | 67.935 (+9.399) | 37.340 (+5.935) | 414 (-10) |
| ARTEMIS_MALAPERT | 1 | 44.286 (-0.758) | 100.000 (+0.000) | 44.286 (-0.758) | 426 (+11) |
| ARTEMIS_MALAPERT | 2 | 45.044 (+0.000) | 100.000 (+0.000) | 45.044 (+0.000) | 415 (+0) |
| ARTEMIS_MALAPERT | 3 | 45.324 (+0.281) | 100.000 (+0.000) | 45.324 (+0.281) | 407 (-8) |
| ARTEMIS_MALAPERT | 10 | 45.607 (+0.564) | 100.000 (+0.000) | 45.607 (+0.564) | 402 (-13) |
| APOLLO17 | 1 | 47.748 (+0.000) | 100.000 (+0.000) | 47.748 (+0.000) | 371 (+0) |
| APOLLO17 | 2 | 47.748 (+0.000) | 100.000 (+0.000) | 47.748 (+0.000) | 371 (+0) |
| APOLLO17 | 3 | 47.750 (+0.002) | 100.000 (+0.000) | 47.750 (+0.002) | 371 (+0) |
| APOLLO17 | 10 | 47.757 (+0.009) | 100.000 (+0.000) | 47.757 (+0.009) | 371 (+0) |
| CHANGE4 | 1 | 49.238 (-0.037) | 0.000 (+0.000) | 0.000 (+0.000) | 367 (+0) |
| CHANGE4 | 2 | 49.274 (+0.000) | 0.000 (+0.000) | 0.000 (+0.000) | 367 (+0) |
| CHANGE4 | 3 | 49.299 (+0.025) | 0.000 (+0.000) | 0.000 (+0.000) | 367 (+0) |
| CHANGE4 | 10 | 49.532 (+0.258) | 0.000 (+0.000) | 0.000 (+0.000) | 365 (-2) |
| SLIM | 1 | 47.641 (-0.011) | 100.000 (+0.000) | 47.641 (-0.011) | 372 (+0) |
| SLIM | 2 | 47.652 (+0.000) | 100.000 (+0.000) | 47.652 (+0.000) | 372 (+0) |
| SLIM | 3 | 47.657 (+0.005) | 100.000 (+0.000) | 47.657 (+0.005) | 372 (+0) |
| SLIM | 10 | 47.688 (+0.037) | 100.000 (+0.000) | 47.688 (+0.037) | 372 (+0) |

Haworth is the largest height response in this sample: 2 m → 1 m changes sunlit time from 54.730% to 44.042% and longest darkness from 424 h to 697 h. At 10 m its Earth visibility rises from 58.536% to 67.935%. This is a consequence of the assumed observer geometry and current DEM surface, not evidence that either height is the actual spacecraft configuration. The earlier five-site near-field-inclusion limit of 0.8 pp describes a different experiment and cannot bound this height sensitivity.

## Nonpolar near-field product results

Native LDEM_128 is 128 pixels/degree (~236.9 m north–south; east–west spacing narrows with latitude). This comparison changes both product and spatial support; it does not isolate resampling alone. Windows of radius 150 km plus interpolation padding were fetched from the original PDS float raster through checked HTTP Range responses. No global raster download or averaged thumbnail was substituted.

| Site | Sun % (Δ pp) | Earth % (Δ pp) | Both % (Δ pp) | Longest darkness h (Δ h) | DEM surface Δ m |
|---|---:|---:|---:|---:|---:|
| APOLLO17 | 47.768 (+0.021) | 100.000 (+0.000) | 47.768 (+0.021) | 371 (+0) | -0.88 |
| CHANGE4 | 49.400 (+0.126) | 0.000 (+0.000) | 0.000 (+0.000) | 366 (-1) | -2.31 |
| SLIM | 47.673 (+0.021) | 100.000 (+0.000) | 47.673 (+0.021) | 372 (+0) | -4.50 |

## Sources, evidence and verification

- [LOLA LDEM_128 original PDS label](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ldem_128_float.lbl); [native image](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ldem_128_float.img). The label confirms 23,040 × 46,080 little-endian float32 samples, km above the 1737.4 km sphere, and MOON_ME / DE421 conventions. Remote size was 4,246,732,800 bytes; only ~22.74 MB of row segments were needed for the three windows.
- [SLDEM2015 source tiles](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [PGDA polar product family](https://pgda.gsfc.nasa.gov/products/90), [NAIF kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/). Existing baseline citations are in [DATASETS.md](../data/DATASETS.md).
- [Full-precision JSON](assumption_sensitivity.json), [CSV](assumption_sensitivity.csv), [input/source hashes and fetch metadata](sensitivity_sources.json), [exact reproduction blocks](sensitivity_reproduce.md). Inputs/outputs/checkpoints are separate from production files.
- Height phase: 13.386 s; nonpolar phase: 3.837 s (includes cached production controls). LDEM window fetches took ~24.5 s. These are local measurements with existing caches; not general runtime guarantees.
- Separate verification and review are recorded in [sensitivity_verification.md](sensitivity_verification.md).
