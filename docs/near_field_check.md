# Near-field terrain check — five nonpolar centres

No production horizon, metrics or raw DEM is changed. (a) is the current production method (200 m minimum ray distance, 4000 steps); (b) includes 5–200 m (5 m minimum, 8000 steps). Both use 720 azimuths, curvature, a 2 m observer and actual hourly core.js over 2026–2030. These alternatives do not enter Card 23 grids.

**These are not five 5 m DEM sites.** All five use SLDEM2015 at 512 pixels/degree (~59.23 m north–south, narrower east–west at higher latitude). A ray beginning at 5 m interpolates those existing pixels; it does not resolve new 5 m relief.

## Requested comparison

Entries show sun / Earth visibility percentages; PGDA neighbourhoods mean a geodesic radius of 300 m.

| Site | Ours (a), % | Ours (b), % | PGDA centre; ±300 m min/max | Closer |
|---|---:|---:|---|---|
| APOLLO11 | 49.6577 / 100.0000 | 49.3748 / 100.0000 | Sun and Earth: N/A — entire disc outside raster | Not determinable |
| APOLLO12 | 49.9293 / 100.0000 | 49.6805 / 100.0000 | Sun and Earth: N/A — entire disc outside raster | Not determinable |
| LUNA20 | 47.8436 / 100.0000 | 47.7227 / 100.0000 | Sun and Earth: N/A — entire disc outside raster | Not determinable |
| CHANGE5 | 50.1552 / 100.0000 | 49.3565 / 100.0000 | Sun and Earth: N/A — entire disc outside raster | Not determinable |
| IM3_REINER_GAMMA | 49.5277 / 100.0000 | 49.1534 / 100.0000 | Sun and Earth: N/A — entire disc outside raster | Not determinable |

## Direct original-product footprint check

[NASA PGDA product 69](https://pgda.gsfc.nasa.gov/products/69) links polar AVGVISIB maps. We downloaded and parsed the **four original PDS labels** for the broadest north/south Sun/Earth products, rather than treating a missing sample as zero. Their 6420×6420 rasters have 240 m pixels. Although named 65N/65S, the square raster corners reach approximately 55.2° latitude; using only the advertised 65° cutoff would be incomplete.
Every requested centre, and its entire 300 m disc, is outside **both** north and south raster rectangles. Projected row/column coordinates and conservative stereographic disc bounds are saved in `near_field_check.json`. No valid IMG address exists there, so no numerical PGDA centre or neighbourhood value can be read. We did not clamp, extrapolate or substitute a different location.

- [AVGVISIB_65S_240M_201608 original label](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_65S_240M_201608.LBL) (SHA256 in JSON).
- [AVGVISIB_65S_240M_201608_EARTH original label](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_65S_240M_201608_EARTH.LBL) (SHA256 in JSON).
- [AVGVISIB_65N_240M_201608 original label](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_65N_240M_201608.LBL) (SHA256 in JSON).
- [AVGVISIB_65N_240M_201608_EARTH original label](https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_65N_240M_201608_EARTH.LBL) (SHA256 in JSON).

Even at covered sites a physical accuracy comparison would need matching time windows (~18.6 years versus five years), observer heights and visibility definitions: the original Sun label counts any visible solar-disc part; our sunlit threshold is half the disc. PGDA Earth visibility accepts any visible part; ours uses the centre.

## Relief versus single-pixel noise

We traced the near-field maxima on the same 8000-step distance grid and inspected the native bilinear-support pixels plus the observer pixels. An isolated positive-spike **candidate** must exceed all eight neighbours and exceed their median by more than max(1 m, 3×1.4826×MAD). This is a diagnostic heuristic, not a calibrated DEM error threshold. Candidate pixels, when present, are replaced by their eight-neighbour median in memory and the full near-field horizon/observer are recomputed. Raw files remain untouched.

| Site | Near-field-dominant azimuth bins / 720 | Blocker distance min / median / max, m | Supporting + observer native pixels | Positive spike candidates | Interpretation |
|---|---:|---:|---:|---:|---|
| APOLLO11 | 482 | 44.3 / 99.5 / 198.3 | 34 | 0 | No isolated positive spike under the stated heuristic in the supporting/observer pixels. Near-field obstruction is present in the interpolated SLDEM surface; physical accuracy is unverified. |
| APOLLO12 | 255 | 91.7 / 147.5 / 199.4 | 29 | 0 | No isolated positive spike under the stated heuristic in the supporting/observer pixels. Near-field obstruction is present in the interpolated SLDEM surface; physical accuracy is unverified. |
| LUNA20 | 291 | 94.7 / 127.3 / 199.1 | 31 | 0 | No isolated positive spike under the stated heuristic in the supporting/observer pixels. Near-field obstruction is present in the interpolated SLDEM surface; physical accuracy is unverified. |
| CHANGE5 | 309 | 19.8 / 25.3 / 193.7 | 23 | 0 | No isolated positive spike under the stated heuristic in the supporting/observer pixels. Near-field obstruction is present in the interpolated SLDEM surface; physical accuracy is unverified. |
| IM3_REINER_GAMMA | 505 | 58.1 / 100.0 / 182.6 | 34 | 0 | No isolated positive spike under the stated heuristic in the supporting/observer pixels. Near-field obstruction is present in the interpolated SLDEM surface; physical accuracy is unverified. |

Native 12×12 pixel height patches and individual neighbour residuals are in the JSON. Multi-pixel support and absence of a flagged positive spike do **not** prove real relief: correlated DEM errors, observer-height interpolation errors, negative spikes and unresolved subpixel terrain remain possible. Independent local high-resolution elevation data would be needed to distinguish those cases. No 5 m DEM or PGDA accuracy claim is made.

The 200 m / 8000-step control isolates distance-grid density from near-field inclusion; its metric differences are recorded per site. These results support retaining current main baselines until the team decides on a consistent recalculation.

Reproduce: `python pipeline/near_field_check.py`; numerical evidence: `docs/near_field_check.json`. Terrain and code/ephemeris hashes are recorded there and in the existing dataset manifest.

## Fresh recheck for the GPU-validation PR

The existing five-site calculation was rerun on 2026-11-14: old/new values, step-only controls and native-pixel diagnostics remain unchanged. All four original PDS labels were fetched again (HTTP 200), with identical SHA256 values: [retrieval evidence](near_field_labels_recheck.json). Production horizon and metrics hashes still match the recorded baselines. PGDA centre and 300 m extrema remain **unavailable** because none of these discs has a valid address in those rasters. Real relief versus all possible DEM noise cannot be determined from this evidence alone.

The refreshed JSON records this run's 9.594 s elapsed time and the local script's SHA256. Its script hash differs from the previous record only because this Windows checkout uses CRLF: normalizing it to LF reproduces the previous hash `1cbd27d2430e62e5c3624dbf8b06580a83c98901d7545d21df2bfc49800cf72e`. No numerical method changed.
