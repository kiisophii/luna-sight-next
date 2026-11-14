# South-polar sensitivity to the PGDA product chain

All **16 south-polar catalogue sites** were recomputed with both their production chain and an alternative near-field PGDA chain. Every production 2 m control exactly matches its existing mask, surface height and four metrics. All cases have zero missing terrain samples. No production data was changed.

## Comparison definition

Production chooses the first covering 5 m (to 3 km), 10 m (to 25 km), 20 m (to 25 km), 60 m (to 60 km), 80 m (to 60 km), 240 m (to 200 km), then LDEM_64 and LDEM_16 (to 300 km). Some sites lack 5 m or 10 m coverage; the table identifies the finest actual production source.

Alternative chain: **PGDA 20 m to 3 km, then PGDA 60 m to 60 km**, followed by the unchanged 80 m/240 m/global fallbacks. Thus 3–25 km also changes from the actual 10/20 m production source to 60 m. The same 720 azimuths, 5 m ray start, 8000 geometric steps, lunar curvature, 2 m above local terrain, 300 km reach and actual hourly core.js definitions over 2026–2030 are retained. No unavailable product is silently manufactured.

The observer remains 2 m above the alternative product's own surface. Δh0 is reported because smoothing/product registration can change the ground elevation as well as surrounding relief. This is full product-chain sensitivity; it does not isolate just distant obstacles or fixed-height smoothing. These PGDA products share LOLA observations and are **not independent ground truth**.

Mask RMS = sqrt(mean((alternative mask - production mask)^2)) across all 720 equally spaced azimuths, in degrees, using production four-decimal serialization. Signed differences below are alternative minus production. Visibility changes are percentage points, not relative percent. Darkness changes are sampled hours.

| Site | Finest production m | Mask RMS ° | Δ Sun pp | Δ Earth pp | Δ Both pp | Δ longest dark h | Δh0 m |
|---|---:|---:|---:|---:|---:|---:|---:|
| IM1 | 20 | 0.0030 | +0.0091 | +0.0000 | +0.0091 | +0 | +0.00 |
| IM2 | 10 | 0.0131 | +0.0365 | +0.0411 | +0.0525 | +0 | +0.16 |
| ARTEMIS_CABEUS_B | 10 | 0.0563 | +0.0068 | +0.0388 | +0.0160 | +0 | -0.09 |
| ARTEMIS_HAWORTH | 5 | 0.1543 | +0.3651 | +2.6994 | +1.6224 | -1 | +0.06 |
| ARTEMIS_MALAPERT | 10 | 0.0550 | +0.1574 | +0.0000 | +0.1574 | -5 | -0.09 |
| ARTEMIS_MOUTON_PLATEAU | 10 | 0.0118 | -0.0228 | -0.1255 | -0.0479 | +2 | -0.09 |
| ARTEMIS_MOUTON | 10 | 0.0170 | +0.0274 | -0.1164 | -0.0776 | +0 | -0.12 |
| ARTEMIS_NOBILE_RIM1 | 10 | 0.0532 | +0.0570 | -0.1529 | -0.0844 | -1 | -0.08 |
| ARTEMIS_NOBILE_RIM2 | 10 | 0.0158 | +0.0091 | -0.2350 | -0.1072 | +0 | -0.05 |
| ARTEMIS_DE_GERLACHE_RIM2 | 5 | 0.0715 | -0.0319 | +0.1141 | +0.0707 | +4 | -0.02 |
| ARTEMIS_SLATER_PLAIN | 5 | 0.0379 | +0.0479 | -0.0023 | +0.0046 | +0 | +0.08 |
| SHACKLETON_RIM | 5 | 0.1108 | +1.1113 | +0.0479 | +0.4221 | +0 | +0.34 |
| CONNECTING_RIDGE | 5 | 0.0709 | -0.5431 | +0.3856 | -0.1164 | +0 | -0.10 |
| PEAK_NEAR_SHACKLETON | 5 | 0.1330 | +2.3343 | +0.4358 | +1.7045 | -199 | +0.08 |
| DE_GERLACHE_RIM1 | 5 | 0.0939 | +0.4199 | +0.0000 | +0.1438 | +1 | -0.06 |
| SHOEMAKER_RIM_A | 5 | 0.0639 | +0.0867 | +0.0000 | +0.0023 | +0 | +0.11 |

## Interpretation and Limits text

Across these 16 sites, mask RMS differences span **0.0030–0.1543°**. The largest absolute sunlit-time change is **2.3343 pp at PEAK_NEAR_SHACKLETON**; the largest Earth-visibility change is **2.6994 pp at ARTEMIS_HAWORTH**. At PEAK_NEAR_SHACKLETON the longest sampled dark interval shortens by **199 h**, showing why mean illumination alone is insufficient for power-storage planning. These values describe this specific alternative chain and sample, not confidence bounds or accuracy against truth.

> At 16 south-polar sites, changing the near-field PGDA product chain produced 0.003–0.154° horizon RMS differences and shifts up to 2.34 percentage points in sunlit time and 2.70 points in Earth visibility.
> The longest sampled darkness changed by up to 199 hours; these related LOLA products test model sensitivity rather than independently establish physical accuracy.

## Sources and verification

- [PGDA product 90](https://pgda.gsfc.nasa.gov/products/90): [20 m DEM](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF), [60 m DEM](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF). Other unchanged products and their actual source use/gates/hashes are in [sensitivity_sources.json](sensitivity_sources.json) and the case records.
- [Full-precision JSON](polar_dem_sensitivity.json) includes production and alternative metrics, differences, ground elevations, mask hashes, actual sampled sources, ray settings and core/ephemeris identities. The [CSV](polar_dem_sensitivity.csv) provides the compact metrics/differences table.
- Local polar phase took 27.449 s including 13 new production controls and 16 alternatives; three controls from the height phase were reused after matching inputs. Reproduction is resumable per case.
- [Exact reproduction](sensitivity_reproduce.md); [separate verification](sensitivity_verification.md).
