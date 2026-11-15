# Independent Z2 verification of PR #80

Reviewed head: beedb67e7993258720ebfc9219e140636f6e4b11 (unchanged at final lookup). Latest main: 564fac3b92e2781e12fedb038c684f65688bf471.
Checker: Minchul Kim; producer: Jiyong Sung. Scope: Z2 only, not Z1/Z4.

Original NASA LPSR_80S_20MPP_ADJ.TIF byte windows were independently decoded; no pipeline modules imported. The HTTP transport is this checker's previous task-Y/task-A reader, not the PSR producer reader. Own raster classification and exposed-edge enumeration; PROJ inverse stereographic, spherical Geod centre distances/bearings, scipy scalar minimization along exposed edges.

| Site | Own centre m | Own boundary m | Own centre/boundary bearing deg |
|---|---:|---:|---|
| Haworth |104.56034555847415|94.50507843195801|198.52174862146006 / 200.5140373154369|
| Shackleton Rim |164.66084073147894|150.876148561831|220.15586113512916 / 221.30421428145152|
| IM1 |559.2821210252947|545.5340435297463|302.0570251452242 / 301.76298858849725|

PASS: all three centre and boundary relative differences <=1%; maximum relative difference 7.6537505302e-12 (7.6537505302e-10 percent). Bearings differ <0.01 degree. All three containing pixels are finite class 0, matching inside_psr=false.

Independent source header confirms float32, 20 m pixel-area, NaN NoData, polar stereographic latitude -90/longitude 0, axes R=1737400 m and native tiepoint (-304000,304000). All fetched analysis pixels are finite 0 or 1. The original NASA PSR polygon CSV gid=1 was independently parsed with Shapely; its representative interior point (42420,41720) samples raster code 1, corroborating 1=PSR. See class proof and source metadata JSON.

Nearest-guarantee check: own independent unsearched-domain lower bounds are 11193.6563/11200.5900/4029.9995 m, all beyond the candidates. IM1's raster-edge limitation is preserved; its missing coverage cannot beat the 559.282/545.534 m results. The bound differs slightly from the producer's 4030.0126 m because the independently selected rectangle differs. No claim of equal rectangle bounds. All current selected records have found results, so '> radius' absence-case output is not exercised by these real samples; the distinction was reviewed: missing/unknown coverage must not assert an unsupported radius lower bound.

PSR is not confirmed ice. This is shared-source numerical agreement, not physical terrain/ice accuracy, obstacle clearance, traverse distance or a full 16-site recomputation. No production files changed, no automatic merge.

Reproduction: install numpy scipy rasterio pyproj tifffile imagecodecs requests shapely; sparse-check out pinned PR head to z2-review/ with web/data/detail/psr and sites.json; from the verification repository root run python verification/z2/check_z2.py and python verification/z2/class_check.py. Raw ranges/CSV remain ignored outside submitted evidence. Initial rasterio HTTP decoding failed; switching to checked original byte ranges resolved acquisition. Source metadata, decoded-window hashes, outputs and standalone code are included.
