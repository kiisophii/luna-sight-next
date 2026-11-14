# Card 2: explanation of the 240 m discrepancy

Computed 2026-11-14 by Jiyong's Codex session. These are empirical checks of the
downloaded test regions, not a claim about global terrain accuracy.

## Conclusion

The previously reported -8.988411 m difference is explained by mismatched spatial
support: a finely resolved point was compared with interpolation of 240 m cell
averages. No downloader, pixel-registration or interpolation error was found in
the implicated data path. Do not add a height offset or replace the original DEM.

## Reproduction at the original worst point

Projected coordinates: x=2113.934737877599 m, y=16850.279401134027 m.
All values are heights above the 1737.4 km reference sphere in the prescribed
lunar south-polar stereographic / MOON_ME DE421 frame.

| Calculation | Height (m) |
|---|---:|
| Original 5 m bilinear point sample | -439.1328622951494 |
| Original 240 m bilinear point sample | -448.12127351161024 |
| 5 m pixels averaged into the exact four 240 m footprints, then interpolated | -448.2432437508139 |
| 60 m pixels averaged 4×4 into those footprints, then interpolated | -448.1212726236373 |

The observed difference decomposes as:

`-8.988411 m = -9.110381 m (averaging + coarse-grid interpolation) + 0.121970 m (remaining cross-product difference)`.

The 60 m area-matched result differs from 240 m by approximately 0.000000888 m at
this point. That near-equality is numerical product consistency, **not** a claim
of micrometre physical elevation accuracy. The cause of the remaining 0.122 m
cross-product difference has not been isolated; different product generations
and adjustment/interpolation methods are possible contributors.

## Checks that distinguish data scale from a code error

1. Fetched the implicated compressed 5 m and 240 m TIFF tiles again directly
   from NASA, without using the disk block cache. Both matched cached bytes
   exactly (SHA-256 hashes and source validators recorded in the JSON report).
2. GDAL/Rasterio independently decoded **all four contributing pixels** at each
   resolution. Values match the NPZ exactly. GDAL affine coordinates plus an
   independent bilinear calculation reproduce both point values within 1e-8 m.
   This rules out a half-pixel, sign, unit or local bilinear bug for this case.
3. Compared aligned cell averages over 576 complete 240 m cells per synthetic
   site, three sites in total (1,728 cells). There is no partial-cell averaging,
   upsampling or fitted elevation offset in this comparison.
4. Repeated the averaging independently with GDAL `Resampling.average` for each
   of the five fine resolutions and all three sites. It agrees with the explicit
   pixel-mean implementation within 1e-7 m (asserted by the diagnostic).

| Fine DEM averaged to 240 m | Maximum absolute residual versus native 240 m, over all 1,728 cells (m) |
|---|---:|
| 5 m | 1.276243 |
| 10 m | 0.065145 |
| 20 m | 2.022096 |
| 60 m | 0.000122071 |
| 80 m | 0.000122071 |

The near-exact 60/80 m averaging relationship is observed in these regions; the
diagnostic does not establish the unpublished production history of every pixel
in the NASA products. Pointwise discrepancies can be larger on unresolved relief,
so a universal few-metre pointwise criterion across 5–240 m is inappropriate.

## Card 2 completion recommendation

- Retain the original DEM values and the existing cache/web contracts. The
  downloader and the implicated coordinate/interpolation path need no correction.
- Ask the team to accept **same-footprint, resolution-matched comparison** for
  the cross-resolution acceptance check, while retaining pointwise differences
  as a reported resolution limitation. The tested regions then satisfy agreement
  within a few metres across all six products (largest residual 2.022096 m).
  This interpretation must be agreed with the team, not silently substituted
  for the original literal pointwise wording.
- Card 2 permits three placeholders until the real site list exists; those
  18 full-radius windows have passed. When card 4 supplies source-backed sites,
  rerun downloads and validation for those sites. Current integrator mock
  coordinates are not evidence about actual landing-site accuracy.
- Human reviewer fills the SI log checks, and Sua reviews/merges the PR. Keep
  draft status pending the acceptance-method decision; the original 9 m value
  remains in the historical report and is now explained.
- In phase 2, use fine terrain nearby and coarse terrain farther away, include
  lunar curvature, and test horizon sensitivity to resolution. Cell averaging
  can suppress local peaks; these checks do not prove a horizon is conservative.

## Reproduce

From the repository root with the previous full-radius caches and verification
sparse TIFFs present:

```powershell
.venv/Scripts/python pipeline/diagnose_polar_resolution.py --fresh
```

Report: `data/processed/polar_resolution_diagnosis.json` (ignored local artifact).
No original data are changed. Computation uses one GDAL thread; only the two
implicated tiles are fetched afresh.

## Sources

- [PGDA product 81](https://pgda.gsfc.nasa.gov/products/81): 5 m south-pole mosaic,
  Barker et al. 2021, DOI 10.1016/j.pss.2020.105119.
- [PGDA product 90](https://pgda.gsfc.nasa.gov/products/90): 10/20/60/80/240 m DEMs,
  Barker et al. 2023, DOI 10.3847/PSJ/acf3e1. NASA documents the MOON_ME DE421
  south-polar stereographic coordinates and surface-height units.
- Exact source URLs are in `data/DATASETS.md`; fresh tile hashes, sample weights,
  decoded values, per-site statistics and source URLs are in the diagnosis JSON.
