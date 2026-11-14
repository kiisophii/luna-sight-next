# Card 8 — south-polar horizons (Jiyong)

Scope: all catalog sites with latitude < -80 degrees, using the card-2 terrain caches and Sua's merged horizon engine. Base commit: `c264135`. Numerical results below will be added after the real-data runs finish.

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
python pipeline/card8_horizons.py sensitivity
python pipeline/verify_card8_horizons.py
python pipeline/check_contract.py
python -m pytest -q
```

The first command reports `UNAVAILABLE` only for geographic coverage; transport errors and invalid source data still fail. Omit the two options to retain the original strict downloader behavior. Completed blocks and windows survive restarts. Do not run two writers against the same resolution's block cache concurrently. Independent resolutions may run concurrently; this run uses at most two download jobs and below-normal process priority.

Production masks are written atomically to `web/data/horizon/<ID>.json`. Rerunning `compute` reuses a mask only when site coordinates, engine parameters and DEM-chain signatures match, and the saved mask has 720 finite angles and zero missing samples. `--force` recomputes it. Raw TIFF blocks, NPZ windows and global IMG files remain git-ignored.

## Sensitivity definition

For SHACKLETON_RIM, CONNECTING_RIDGE and ARTEMIS_DE_GERLACHE_RIM2, compare the full-resolution baseline with two variants: replace only the 0–3 km near field with the original 80 m or 240 m DEM. All sources outside 3 km are unchanged. The observer remains 2 m above the **variant's own** terrain elevation, so reported differences include the change in sampled observer elevation; that height change is reported separately.

This measures the effect of using coarse terrain for the near field. It does not correct one DEM to match another and does not test the website's visual zoom transitions.

## Independent verification

`verify_card8_horizons.py` does not import the production engine. It reads the original cached elevation arrays, independently interpolates them, uses PROJ geodesics for ray locations and Cartesian line-of-sight vectors for elevation. No early stopping is used.

For two sites, ten azimuths are evaluated twice:

1. At the same distance samples as production: distinguish geometry/interpolation mistakes from sampling effects. The numerical check is 0.0001 degree, allowing for the production JSON's four-decimal angle rounding; this is **not a physical accuracy claim**.
2. At uniform 2.5 m spacing from 5 m to 300 km: report maximum differences and peak distances to assess sampling convergence.

The verifier and engine have analytic flat-sphere tests. Additional tests cover near-field obstacles, true coarse-resolution replacement, missing data, partial source coverage and transport failures.
