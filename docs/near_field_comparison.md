# Five-site near-field sensitivity experiment

Historical first comparison. The requested follow-up, original raster footprint checks and native-pixel diagnostics are in [near_field_check.md](near_field_check.md). Its footprint analysis supersedes the simplified 65-degree coverage description below.

Catalogue horizons and metrics remain unchanged. This experiment compares independently recomputed legacy centres with a 5 m minimum ray-distance / 8000-step alternative, on the same DEM chain and hourly production core.js.

| Site | Legacy sun % | Near-field sun % | Change pp | Legacy / near longest dark h | PGDA sun value | Closer to PGDA |
|---|---:|---:|---:|---:|---|---|
| APOLLO11 | 49.6577 | 49.3748 | -0.2829 | 357 / 359 | N/A: outside coverage | Not determinable |
| APOLLO12 | 49.9293 | 49.6805 | -0.2487 | 356 / 358 | N/A: outside coverage | Not determinable |
| LUNA20 | 47.8436 | 47.7227 | -0.1209 | 371 / 371 | N/A: outside coverage | Not determinable |
| CHANGE5 | 50.1552 | 49.3565 | -0.7986 | 360 / 366 | N/A: outside coverage | Not determinable |
| IM3_REINER_GAMMA | 49.5277 | 49.1534 | -0.3742 | 361 / 363 | N/A: outside coverage | Not determinable |

Earth visibility remains 100% at all five sites; both_frac equals sun_frac in both versions. Full metrics, parameters and baseline hashes are in `near_field_comparison.json`.

NASA PGDA source: [Lunar Polar Illumination](https://pgda.gsfc.nasa.gov/products/69). Published grids extend from 65 degrees latitude to each pole; all five coordinates above fall outside those products. Consequently neither version has a PGDA reference value or an error score here. Do not substitute a polar pixel or extrapolate a reference value.

Even in coverage, a controlled PGDA comparison must align the time window, observer height, spatial support and solar/Earth disk definitions. PGDA documentation describes ~18.6-year averages and any-part-of-Earth-disk visibility.

The test isolates inclusion of nearby terrain. SLDEM pixel spacing remains approximately 59 m; interpolating rays from 5 m does not create 5 m terrain accuracy. The team can review the method separately; these alternative values are not used in Card 23 uncertainty grids.

Reproduce: `python pipeline/compare_near_field.py`.
