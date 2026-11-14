# Card 8 — south-polar horizons (Jiyong)

Scope: all catalog sites with latitude < -80 degrees, using the card-2 terrain caches and Sua's merged horizon engine. Base commit: `c264135`. All 16 production masks were generated from real terrain; numerical checks and sensitivity results are recorded below. These are terrain masks, not completed sunlight/communication statistics.

## Method and source coverage

- 720 directions, azimuth 0 = north clockwise, 0.5-degree spacing.
- Moon radius 1737.4 km; observer 2 m above each site's terrain; spherical curvature included.
- Finest available terrain: PGDA 5 m within 3 km, 10 m within 25 km, 20 m within 25 km, 60/80 m within 60 km, 240 m within 200 km, then LOLA LDEM_64/16 to 300 km.
- Source coverage is geographic, not a promise that every site has a 5 m product. The 5 m mosaic covers eight of the sixteen requested windows. IM-1 has no 5/10 m window; its 20/80 m windows intersect a source boundary. Their available original pixels are retained and the existing sampler falls back to the next resolution outside them.
- No source elevation shift, resampling of the production caches, or forced agreement between resolutions.
- Production inner radius is **5 m**, not the engine's default 200 m. The default would omit nearby terrain that card 8 is intended to include. Terrain inside 5 m and subpixel obstacles remain unresolved.
- The independent verifier checks convergence of the distance sampling, not the observational accuracy of the NASA DEMs.

Sources: [PGDA products](https://pgda.gsfc.nasa.gov/products/90), [PGDA 5 m mosaic](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/ldem_87s_5mpp.tif), [LOLA global grids](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/). Every NPZ retains its source URL, source validators, full-resolution grid and site coordinates.

## Reproduce

Use Python with the packages in `pipeline/requirements-polar.txt`. Numba is optional for horizon interpolation. Full repository tests also need Skyfield/JPL ephemeris packages and Pillow for other task owners' modules. The Windows verification environment uses Python 3.10 with numpy 2.2.6; the unrelated ephemeris requirements pin numpy 2.3.5, which requires a newer Python.

```powershell
python pipeline/fetch_polar.py --clip-coverage --skip-unavailable
python pipeline/fetch_global.py --skip-sites
python pipeline/card8_horizons.py compute
python pipeline/run_horizons.py --index-only
python pipeline/card8_horizons.py sensitivity
python pipeline/verify_card8_horizons.py
python pipeline/check_contract.py
python -m pytest -q
```

The first command reports `UNAVAILABLE` only for geographic coverage; transport errors and invalid source data still fail. Omit the two options to retain the original strict downloader behavior. Completed blocks and windows survive restarts. Do not run two writers against the same resolution's block cache concurrently. Independent resolutions may run concurrently; this run uses at most two download jobs and below-normal process priority.

Production masks are written atomically to `web/data/horizon/<ID>.json`. Rerunning `compute` reuses a mask only when site coordinates, engine parameters and DEM-chain signatures match, and the saved mask has 720 finite angles and zero missing samples. `--force` recomputes it. Raw TIFF blocks, NPZ windows and global IMG files remain git-ignored.

The phase-3 UI reads `web/data/horizon_index.json`. After computing masks or merging another horizon branch, regenerate it with `run_horizons.py --index-only`; this includes every horizon file present, including other owners' sites. Integration was checked against main `ad945de`.

## Sensitivity definition

For SHACKLETON_RIM, CONNECTING_RIDGE and ARTEMIS_DE_GERLACHE_RIM2, compare the full-resolution baseline with two variants: replace only the 0–3 km near field with the original 80 m or 240 m DEM. All sources outside 3 km are unchanged. The observer remains 2 m above the **variant's own** terrain elevation, so reported differences include the change in sampled observer elevation; that height change is reported separately.

This measures the effect of using coarse terrain for the near field. It does not correct one DEM to match another and does not test the website's visual zoom transitions.

## Independent verification

`verify_card8_horizons.py` does not import the production engine. It reads the original cached elevation arrays, independently interpolates them, uses PROJ geodesics for ray locations and Cartesian line-of-sight vectors for elevation. No early stopping is used.

For two sites, ten azimuths are evaluated twice:

1. At the same distance samples as production: distinguish geometry/interpolation mistakes from sampling effects. The numerical check is 0.0001 degree, allowing for the production JSON's four-decimal angle rounding; this is **not a physical accuracy claim**.
2. At the union of production samples and uniform 2.5 m spacing from 5 m to 300 km: report maximum differences and peak distances to assess sampling convergence. Keeping production samples matters because the geometric grid is already finer than 2.5 m close to the observer.

The verifier and engine have analytic flat-sphere tests. Additional tests cover near-field obstacles, true coarse-resolution replacement, missing data, partial source coverage and transport failures.

## Run results (2026-11-14 KST)

87 full-resolution polar windows were acquired: 5 m x 8, 10 m x 15, and 20/60/80/240 m x 16 each. LDEM_16/64 global grids were also acquired. Cache metadata coordinates match the catalog; see [input manifest](polar-horizon-inputs.json). Original block caches were reused where windows overlap.

All 16 masks contain 720 finite angles, have `mock=false`, and report zero missing terrain samples. The observer height is 2 m and the radial grid has 8,001 geometric samples from 5 m to 300 km, with the engine's conservative early stop. A second production run reused all 16 results. Changed coordinates, sample count or DEM-chain signature invalidates resume; incomplete saved masks were rejected.

| Site | Finest cached DEM (m) | Horizon range (deg) |
|---|---:|---:|
| IM1 | 20 | -0.2416 to 11.1390 |
| IM2 | 10 | -1.4690 to 4.0663 |
| ARTEMIS_CABEUS_B | 10 | -4.0932 to 8.7239 |
| ARTEMIS_HAWORTH | 5 | -2.5972 to 4.0299 |
| ARTEMIS_MALAPERT | 10 | -4.1353 to 5.7754 |
| ARTEMIS_MOUTON_PLATEAU | 10 | -0.5213 to 5.5121 |
| ARTEMIS_MOUTON | 10 | -4.7632 to 2.1381 |
| ARTEMIS_NOBILE_RIM1 | 10 | -5.4635 to 1.6290 |
| ARTEMIS_NOBILE_RIM2 | 10 | -2.1889 to 7.8841 |
| ARTEMIS_DE_GERLACHE_RIM2 | 5 | -2.4879 to 2.2804 |
| ARTEMIS_SLATER_PLAIN | 5 | -1.1703 to 3.4200 |
| SHACKLETON_RIM | 5 | 0.0927 to 32.2337 |
| CONNECTING_RIDGE | 5 | -3.2166 to 2.2716 |
| PEAK_NEAR_SHACKLETON | 5 | -3.1464 to 1.3596 |
| DE_GERLACHE_RIM1 | 5 | -2.8786 to 3.2527 |
| SHOEMAKER_RIM_A | 5 | -0.4103 to 6.3564 |

### Near-field resolution sensitivity

All values are angular changes relative to each site's full-resolution baseline. RMS uses all 720 directions. These are **resolution effects, not corrections to apply to the DEM**.

| Site | 80 m RMS (deg) | 240 m RMS (deg) | 80 m max abs (deg) | 240 m max abs (deg) |
|---|---:|---:|---:|---:|
| ARTEMIS_DE_GERLACHE_RIM2 | 0.205409 | 0.452934 | 0.652571 | 1.616107 |
| SHACKLETON_RIM | 0.425283 | 0.452594 | 1.570372 | 1.634760 |
| CONNECTING_RIDGE | 0.388243 | 0.456228 | 0.922412 | 1.113477 |

The largest observed change is 1.634760 degrees in one direction. The unchanged far field and explicit observer-height policy make the comparison reproducible. It supports preserving fine near-field terrain; it does not establish a single cross-resolution height tolerance. Full observer-height changes and signed differences: [sensitivity JSON](polar-horizon-sensitivity.json).

### Independent numerical verification

| Site | Directions | Same-grid max abs (deg) | Refined-grid max abs vs stored (deg) |
|---|---:|---:|---:|
| ARTEMIS_DE_GERLACHE_RIM2 | 10 | 0.00003425 | 0.00053332 |
| SHACKLETON_RIM | 10 | 0.00004395 | 0.00051490 |

Same-grid differences are within four-decimal output rounding. Refinement retains the production samples and adds a uniform 2.5 m grid; the largest change across the 20 checked directions is 0.00053332 degrees. This supports the chosen distance sampling for the checked rays, not a physical accuracy guarantee for all terrain or a proof for untested azimuths. Full ray angles and peak distances: [verification JSON](polar-horizon-verification.json).

### Runtime and scope limits

On this Windows machine, using one calculation process, all 16 production masks took 24.86 seconds including input loading. Three-site sensitivity took 9.87 seconds. These are offline processing times, not browser or cloud response-time measurements.

`check_contract.py`: PASS, zero errors. Its two warnings are outside card 8: the 17 non-polar masks are not in this branch yet, and the inherited validation.json is still mock. Final app illumination validation depends on the other cards. The catalog includes representative region coordinates; these masks do not turn those coordinates into a certified landing point.

Full repository pytest after integrating the phase-3 index: 56 passed, 3 skipped (ephemeris kernel checks without local kernels), 2 upstream rasterio deprecation warnings. The index contains exactly the 16 generated masks.

Inputs are real NASA terrain, while geospatial sampling/physical resolution and source uncertainties still limit accuracy. No 5 m terrain was invented for uncovered sites, and terrain inside 5 m or between the 0.5-degree azimuth rays is not resolved by this product.

Independent whole-branch review found no critical or important issues. Resume invalidation was exercised on real records, but permanent automated regression coverage for those resume checks remains a minor follow-up. The review does not establish NASA DEM vertical accuracy, registration accuracy, or whether catalog representative coordinates are suitable landing points; ephemeris, non-polar horizons and PGDA illumination validation remain separate work.
