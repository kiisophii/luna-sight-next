# Independent 3.8 km map and custom south-polar checks

Jiyong, 2026-11-14. This extends the historical verification ledger from PR #53. Tested inputs are main `6829725`; the polar Worker, sampler and polar index are unchanged from `s4-custom-polar-sua` (`33831da`). No production code or data is modified.

## Independence and definitions

[The new reference](../pipeline/independent_map_polar_check.py) implements its own PDS/PGDA/tile readers, four-corner interpolation, spherical ray march without early stopping, topocentric Sun/Earth projections and time aggregation. It does not import `horizon.py`, `hterrain.js`, a producer's validation script or export routine for the reference computation. The original `global_maps.py` engine is run only as an additional **system under test**. The actual `custom_horizon_worker.js` executes in Chrome; `core.js` is also checked against the separate Python time loop.

Definitions are intentionally preserved: `gmaps` Sun is the **mean visible solar-disk fraction**, while `core.metrics().sun_frac` for custom points is the **fraction of hours with at least half the Sun visible**. Both use radius 0.2666°, a 2 m observer, MOON_ME ephemeris and lunar curvature. Earth is centre-above-horizon; both is sunlit AND Earth visible. Changing this existing distinction is outside this verification.

## 1. Published 3.8 km map

Ten source cells sampled uniformly without replacement from the 1440 × 2880, 8 px/degree grid, NumPy seed **53142026**. The sample includes 86.1875° N and 87.5625° S. Coordinates are pixel centres. Settings match `web/data/gmaps/index.json`: LDEM_64 to 150 km, LDEM_16 to 300 km, 360 azimuths, 283 distances starting at half the near-DEM pixel spacing, step=max(DEM spacing, 1% of distance), and 21,912 ephemeris samples at 2-hour intervals across 2026–2030.

- Independent full march/time loop versus original CPU engine: **maximum absolute metric difference 9.4147 × 10⁻¹² percentage points** over 10 × 3 values. Maximum mask difference **3.4912 × 10⁻¹¹°**. These measure implementation agreement, not physical lunar-model accuracy.
- Published `sun/earth/both_values.png`: **30/30 DN values identical** to independent recomputation plus export interpolation and quantization. Maximum difference after identical encoding is **0 percentage points**.
- Before quantization, the largest residual against the decoded PNG is **0.198773 percentage points**, within the expected 0.2 pp half-step for its 0.4 pp encoding.

The producer's original float32 grid is **not locally available**. Thus this is not a direct comparison against its original raw cell array. For each of the ten random source cells, the verifier also selects the nearest published 4096 × 2048 overview pixel, independently computes its four supporting source cells, interpolates at the correct pixel centre and encodes the result. **40 unique cells total** are recomputed; this includes the ten randomly selected centres. A direct source-cell value versus a blended overview pixel would be an invalid comparison. Lossy colour JPEGs are not used as numerical truth.

All selected coordinates, full masks, values, CPU comparisons, overview coordinates, support cells and errors are in [map_check.json](crosscheck_maps_polar/map_check.json); individually resumable computations are in [map_nodes](crosscheck_maps_polar/map_nodes).

## 2. Custom-point south-polar terrain

Three deliberate test points use existing card-8 caches: the published Shackleton rim point, the previously flagged Peak Near Shackleton region, and Malapert. They are not a random sample and do not bound the worst case across the polar region. All 720 azimuths are fully marched at each point over **8,001 geometric distances, 5 m–300 km**; each time loop uses all **43,824 hourly** ephemeris rows.

The card-8 chain is PGDA 5 m within 3 km where available, then 10/20 m to 25 km, 60/80 m to 60 km, 240 m to 200 km, then original LDEM_64/LDEM_16 to 300 km. Malapert has no 5 m cache and begins at 10 m. The Worker instead uses its published 20/60 m near levels to 3 km, 240 m to 150 km, followed by browser global grids (948/1895 m); tiles also have 0.25/0.5/1 m height quantization. Each method uses 2 m above **its own** local terrain height. This comparison includes the complete product-chain difference, not only one resolution parameter.

### Worker versus independently recomputed card-8 chain

Positive Sun difference means Worker minus card-8. RMS and maximum use all 720 azimuths, including azimuths that may not affect solar visibility.

| Point (latitude, east longitude) | Horizon RMS ° | Horizon max abs ° | Card-8 sunlit time % | Worker sunlit time % | Difference pp |
|---|---:|---:|---:|---:|---:|
| SHACKLETON_RIM (−89.6866, −162.81) | 0.105267 | 0.519843 | 84.825666 | 86.046459 | +1.220792 |
| PEAK_NEAR_SHACKLETON (−88.811, 123.6901) | 0.140531 | 0.413379 | 66.780759 | 69.210935 | +2.430175 |
| ARTEMIS_MALAPERT (−85.942, −0.944) | 0.063066 | 0.327241 | 45.043812 | 45.242333 | +0.198521 |

This independently confirms a material resolution/product sensitivity, especially at Peak Near Shackleton. It **does not support claiming that custom points reproduce high-resolution card-8 results within 1 pp everywhere**, or that all horizon angles agree within 0.5°. No claim is made that card-8 is error-free ground truth.

### Same browser terrain inputs: implementation control

The reference separately decodes the exact published compressed tiles with its own prefix sums and interpolation, then marches every distance without the Worker's early-stop shortcut. This isolates numerical implementation from the terrain-product difference above.

| Point | Horizon RMS ° | Max abs ° | Sunlit-time difference pp | Independent loop vs browser core Sun difference pp |
|---|---:|---:|---:|---:|
| SHACKLETON_RIM | 0.000028714 | 0.000049993 | 0 | 0 |
| PEAK_NEAR_SHACKLETON | 0.000029249 | 0.000049985 | 0 | 0 |
| ARTEMIS_MALAPERT | 0.000029081 | 0.000049970 | 0 | 0 |

All **2,160 angles are identical after the Worker's four-decimal-degree rounding**. The unrounded comparison is within its ±0.00005° storage-rounding bound. Therefore, at these three points, the larger card-8 difference is attributable to the different terrain inputs/observer elevations, not a detected Worker ray-marching error. Rounding happened not to change the hourly sunlit classification in this sample; it is not a general guarantee near a threshold.

Evidence: [polar_check.json](crosscheck_maps_polar/polar_check.json) contains all three masks per point, chain settings, heights and metrics; [browser_worker.json](crosscheck_maps_polar/browser_worker.json) records actual Worker responses and browser core metrics. [Input manifest](crosscheck_maps_polar/inputs_all.json) pins source code, ephemeris, labels, raw DEM/cache files and every compressed tile read by the reference.

## Reproduction and checks

Run from the repository root with NumPy, Pillow, Playwright and the CPU pipeline dependencies installed, and Chrome available. Raw card-2/card-3 files must be present; no download or production write is performed:

```powershell
python -m pytest pipeline/tests/test_independent_map_polar_check.py -q
python pipeline/independent_map_polar_check.py --raw <path-to-data/raw> --mode all --cpu-comparator
python pipeline/verify_ledger.py
```

The reference has analytic controls for interpolation/wrapping, a flat spherical horizon, the distinction between disk mean and sunlit time, and both predictor encodings. All four tests pass. Original ledger verification passes. The run asserts matching published DN values, the PNG half-step bound, CPU agreement below 10⁻⁶ pp, same-tile mask agreement after rounding and identical Sun fractions for the same-input control. No artificial pass threshold is applied to the different-resolution card-8 comparison; its differences are reported explicitly.

An independent read-only AI reviewer checked the formulas and raw evidence. It identified missing resume-input signatures; these were added and both checks were rerun with the final verifier. The reviewer found no remaining critical/important issue. NumPy and JavaScript have different exact-tie rounding rules; all 2,160 actual samples were separately checked with JavaScript's `floor(x*10000+0.5)/10000` rule and match. This is AI-assisted review, not human sign-off.

Sources: [LOLA PDS global DEM archive](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/), [NASA PGDA south-polar DEM products](https://pgda.gsfc.nasa.gov/products/90), and the repository's [dataset provenance](../data/DATASETS.md) / [data contract](data_contract.md), particularly sections 2, 6, 9, 10 and 14b. Ephemeris is the existing production NAIF-derived `ephem.bin`; this check does not independently regenerate ephemeris or validate absolute DEM accuracy.
