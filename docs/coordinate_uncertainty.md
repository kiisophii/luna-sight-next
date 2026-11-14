# Coordinate uncertainty — Card 23

Each of 33 catalogue locations has 121 geodesic nodes on an 11x11 grid, ±500 m in east/north offsets at 100 m spacing. Statistics use circular radii 100/300/500 m (5/29/81 nodes). They describe sampled spatial sensitivity, not statistical confidence intervals or actual coordinate-error probabilities.

Every site uses its unchanged main horizon method and terrain chain: polar sites already start rays at 5 m with 8000 steps; nonpolar sites retain 200 m / 4000 steps. All use 720 azimuths, lunar curvature, 2 m observer and 2026–2030 hourly production core.js. Every independently recomputed centre equals its existing metrics file.

## Within 300 m

| Site | Sunlit % range | Earth-visible % range | Both % range | Longest dark h range | Ground DEM m/px |
|---|---:|---:|---:|---:|---:|
| APOLLO11 | 49.24–49.78 | 100.00–100.00 | 49.24–49.78 | 356–360 | 59.2253 |
| APOLLO12 | 49.26–50.09 | 100.00–100.00 | 49.26–50.09 | 355–361 | 59.2253 |
| APOLLO14 | 47.97–49.22 | 100.00–100.00 | 47.97–49.22 | 361–370 | 59.2253 |
| APOLLO15 | 46.84–47.44 | 100.00–100.00 | 46.84–47.44 | 376–380 | 59.2253 |
| APOLLO16 | 49.19–49.57 | 100.00–100.00 | 49.19–49.57 | 358–361 | 59.2253 |
| APOLLO17 | 46.90–47.81 | 100.00–100.00 | 46.90–47.81 | 371–378 | 59.2253 |
| LUNA16 | 48.68–49.73 | 100.00–100.00 | 48.68–49.73 | 357–364 | 59.2253 |
| LUNA20 | 46.99–47.92 | 100.00–100.00 | 46.99–47.92 | 370–376 | 59.2253 |
| LUNA24 | 48.82–49.75 | 100.00–100.00 | 48.82–49.75 | 358–364 | 59.2253 |
| CHANGE3 | 43.53–50.15 | 100.00–100.00 | 43.53–50.15 | 360–406 | 59.2253 |
| CHANGE4 | 48.74–49.48 | 0.00–0.00 | 0.00–0.00 | 365–371 | 59.2253 |
| CHANGE5 | 49.27–50.19 | 100.00–100.00 | 49.27–50.19 | 360–366 | 59.2253 |
| CHANGE6 | 48.92–50.03 | 0.00–0.00 | 0.00–0.00 | 361–369 | 59.2253 |
| CHANDRAYAAN3 | 47.79–48.01 | 100.00–100.00 | 47.79–48.01 | 383–385 | 473.802 |
| SLIM | 46.55–47.81 | 100.00–100.00 | 46.55–47.81 | 371–381 | 59.2253 |
| IM1 | 33.11–41.50 | 99.76–100.00 | 33.07–41.50 | 443–499 | 20 |
| IM2 | 36.25–45.60 | 64.21–81.69 | 24.47–37.96 | 455–492 | 10 |
| BLUE_GHOST1 | 49.26–49.87 | 100.00–100.00 | 49.26–49.87 | 357–361 | 59.2253 |
| ARTEMIS_CABEUS_B | 23.61–46.46 | 17.40–35.19 | 3.69–15.99 | 460–3401 | 10 |
| ARTEMIS_HAWORTH | 14.34–55.88 | 44.67–67.31 | 11.81–35.87 | 414–4929 | 5 |
| ARTEMIS_MALAPERT | 34.00–46.23 | 66.02–100.00 | 24.01–46.23 | 397–527 | 10 |
| ARTEMIS_MOUTON_PLATEAU | 17.06–40.97 | 49.97–62.54 | 14.07–27.20 | 497–3464 | 10 |
| ARTEMIS_MOUTON | 15.93–72.04 | 36.43–73.85 | 6.53–39.22 | 315–2801 | 10 |
| ARTEMIS_NOBILE_RIM1 | 8.50–72.89 | 40.41–70.09 | 4.43–45.71 | 336–4927 | 10 |
| ARTEMIS_NOBILE_RIM2 | 5.52–45.37 | 26.24–77.43 | 0.73–35.37 | 406–3527 | 10 |
| ARTEMIS_DE_GERLACHE_RIM2 | 32.12–70.13 | 0.00–57.68 | 0.00–39.61 | 336–656 | 5 |
| ARTEMIS_SLATER_PLAIN | 25.55–43.69 | 0.00–44.34 | 0.00–19.39 | 544–676 | 5 |
| SHACKLETON_RIM | 29.89–84.83 | 0.00–49.94 | 0.00–44.36 | 75–621 | 5 |
| CONNECTING_RIDGE | 31.69–83.49 | 4.00–54.14 | 1.74–46.66 | 156–3469 | 5 |
| PEAK_NEAR_SHACKLETON | 38.92–79.03 | 38.42–56.66 | 19.61–45.08 | 291–619 | 5 |
| DE_GERLACHE_RIM1 | 21.71–63.01 | 40.87–57.23 | 8.66–36.17 | 324–2121 | 5 |
| SHOEMAKER_RIM_A | 17.76–24.75 | 43.05–43.76 | 10.47–13.90 | 2119–2820 | 5 |
| IM3_REINER_GAMMA | 48.67–50.00 | 100.00–100.00 | 48.67–50.00 | 357–367 | 59.2253 |

## Ranges exceeding 10 percentage points

- IM2: earth_frac 17.48pp, both_frac 13.49pp
- ARTEMIS_CABEUS_B: sun_frac 22.85pp, earth_frac 17.79pp, both_frac 12.30pp
- ARTEMIS_HAWORTH: sun_frac 41.54pp, earth_frac 22.64pp, both_frac 24.06pp
- ARTEMIS_MALAPERT: sun_frac 12.23pp, earth_frac 33.98pp, both_frac 22.23pp
- ARTEMIS_MOUTON_PLATEAU: sun_frac 23.90pp, earth_frac 12.57pp, both_frac 13.13pp
- ARTEMIS_MOUTON: sun_frac 56.11pp, earth_frac 37.42pp, both_frac 32.69pp
- ARTEMIS_NOBILE_RIM1: sun_frac 64.39pp, earth_frac 29.68pp, both_frac 41.29pp
- ARTEMIS_NOBILE_RIM2: sun_frac 39.84pp, earth_frac 51.19pp, both_frac 34.64pp
- ARTEMIS_DE_GERLACHE_RIM2: sun_frac 38.01pp, earth_frac 57.68pp, both_frac 39.61pp
- ARTEMIS_SLATER_PLAIN: sun_frac 18.14pp, earth_frac 44.34pp, both_frac 19.39pp
- SHACKLETON_RIM: sun_frac 54.94pp, earth_frac 49.94pp, both_frac 44.36pp
- CONNECTING_RIDGE: sun_frac 51.80pp, earth_frac 50.14pp, both_frac 44.93pp
- PEAK_NEAR_SHACKLETON: sun_frac 40.11pp, earth_frac 18.23pp, both_frac 25.47pp
- DE_GERLACHE_RIM1: sun_frac 41.30pp, earth_frac 16.37pp, both_frac 27.51pp

## Interpretation and verification

- `sun_frac` counts hours with at least half the solar disk visible; Earth visibility uses its centre. These are geometric metrics, not delivered power or RF-link availability.
- Fine-source coverage varies. Reported DEM resolution is the actual finest available source at each node, not vertical accuracy. Windows can fall back to coarser sources near their edges.
- A 100 m node grid can miss smaller features. Min/max and quantiles describe these sampled nodes only.
- The independent verifier uses full brute-force rays and a separate hourly metric loop on 5 random nodes each at polar, mid-latitude and equatorial sites; see `coordinate_uncertainty_check.json`.
- The five-site alternative near-field experiment is separate: see `near_field_comparison.md`. Existing baseline files are unchanged; PGDA values are unavailable at those nonpolar coordinates.

Reproduce: `python pipeline/coordinate_uncertainty.py --workers 6`, then `python pipeline/coordinate_uncertainty_report.py` and `python pipeline/verify_coordinate_uncertainty.py`.

Sources: [PGDA terrain](https://pgda.gsfc.nasa.gov/products/90), [LOLA/SLDEM PDS](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/), [NAIF kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/). Per-output source/code hashes record provenance.

Measured final production run: 409.16 seconds (6 min 49 s), six workers, 33 sites / 3,993 nodes. Independent verification: 58.53 seconds, 15/15 nodes passed, maximum fraction difference 0.0 percentage points and maximum longest-dark difference 0 hours. All 33 centres match unchanged catalogue metrics exactly. Fourteen sites exceed a 10 percentage-point range in at least one fraction metric within 300 m. This is numerical consistency on the same DEMs, not a claim of ground-truth accuracy.
