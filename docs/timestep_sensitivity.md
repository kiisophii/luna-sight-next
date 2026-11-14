# Time-step sensitivity: 1 h vs 10 min (2026–2030, 6 sites)

Soyun Jeong, 2026-11-14 (KST), requested by the team lead (Sua Kim). Work by Claude Code; human-check cells in `docs/SI_USAGE.md` are `TO CHECK`.
**Docs-only check.** The production ephemeris (`web/data/ephem.bin`), the metrics cache (`web/data/metrics/`), `web/js/core.js` and the engines are only read, never changed.
Script: `pipeline/timestep_sensitivity.py` (`ephem`, then `run`) → `docs/timestep_sensitivity.json` (every number below).

## Result in one paragraph
Over the whole 2026–2030 window, going from the production 1-hour step to a 10-minute step changes the six sites':
- sunlight fraction by at most **0.029 pp** (mean 0.013 pp);
- Earth-visibility fraction by at most **0.008 pp** (mean 0.002 pp);
- longest dark period by at most **0.5 h** (mean 0.19 h).

Almost all of this is the hourly *sampling* of visibility, not the hourly ephemeris: linear interpolation of the hourly rows changes the fractions by at most 0.0004 pp. "Time until sunset / Earthset" from `core.js` differs from a 10-minute reference by at most **0.24 min** (mean 0.12 min). This is the `core.js` bisection resolution (1/128 h); the hourly-ephemeris part is at most 0.04 min. With the 1-hour data, the cached metrics are reproduced **exactly** for all 6 sites.

## 1. Ephemeris (inputs)
| | Production | 10-minute (this check) |
|---|---|---|
| File | `web/data/ephem.bin` (float32, 43,824 rows), SHA256 `c0a22639…` | `data/processed/ephem_2026-2030_10min_f64.npy` (float64, 262,944 rows, 12.6 MB, git-ignored) |
| Window | 2026-01-01T00Z – 2031-01-01T00Z (exclusive), 1 h | same, 10 min (6 per hour) |
| Generator | `pipeline/ephem.py` `generate()` → `Ephemeris.vectors()` | `Ephemeris.vectors()` from the unchanged `pipeline/ephem.py`, called with `EPOCH + timedelta(minutes=10 k)` (exact datetimes) |
| Frame, corrections | MOON_ME_DE421; Skyfield `observe().apparent()` (light time, aberration, deflection); UTC from `naif0012.tls` | identical code path |
| Software | Skyfield 1.54 (provenance: numpy 2.3.5) | Skyfield 1.54, numpy 2.5.4 |

Kernels (NAIF generic_kernels; SHA256 identical to `docs/ephem_provenance.json`): `de440s.bsp` (32,726,016 B, `c1c7feea…`), `moon_pa_de421_1900-2050.bpc` (1,770,496 B, `656f9061…`), `moon_080317.tf` (21,437 B, `78732477…`), `pck00008.tpc` (111,586 B, `ca07df56…`), `naif0012.tls` (5,257 B, `678e32bd…`).

**Consistency at the whole hours:**
- every 6th 10-minute row, rounded to float32, is **bit-identical to `ephem.bin` in all 43,824 rows** (max difference 0.0 km);
- in float64 the difference is the float32 rounding of the file only: max 8.0 km on a 1.5 × 10⁸ km Sun vector, relative 6.0 × 10⁻⁸.

**Error of the hourly ephemeris when `core.js` interpolates it linearly** (`bodyVec`), against the 10-minute truth:
- Sun: max 1,510 km chord error, i.e. **0.057″** in direction;
- Earth: max 0.87 km, **0.48″** in direction.

Both are far below the 0.5° horizon-mask bin.

## 2. Metrics: 1 h vs 10 min
Definitions as in `web/js/core.js`:
- sunlit = visible solar-disc fraction ≥ 0.5 (radius 0.2666°);
- Earth visible = Earth **centre** above the mask;
- the mask is the site's 720-bin horizon (`web/data/horizon/<ID>.json`), interpolated linearly between bins;
- observer 2 m above `h0_m`;
- longest dark = the longest run of consecutive not-sunlit samples (10-minute runs converted to hours, × 1/6).

The sites and masks are the existing ones (main at `48a0ad0`). The Python port follows `core.js` line by line; Node.js, which `pipeline/cache_metrics.mjs` uses, is not installed on this laptop.

| Site | lat, lon | sun_frac 1 h → 10 min | Δ (pp) | earth_frac 1 h → 10 min | Δ (pp) | both Δ (pp) | longest_dark_h 1 h → 10 min | Δ (h) |
|---|---|---|---|---|---|---|---|---|
| SHACKLETON_RIM | −89.687, −162.810 | 0.848257 → 0.847983 | −0.0274 | 0.499430 → 0.499407 | −0.0023 | −0.0137 | 75 → 74.667 | −0.333 |
| ARTEMIS_HAWORTH | −86.768, −20.514 | 0.547303 → 0.547014 | **−0.0289** | 0.585364 → 0.585444 | **+0.0080** | −0.0110 | 424 → 424.000 | 0 |
| ARTEMIS_MALAPERT | −85.942, −0.944 | 0.450438 → 0.450423 | −0.0015 | 1 → 1 | 0 | −0.0015 | 415 → 415.167 | +0.167 |
| APOLLO17 | 20.191, 30.772 | 0.477478 → 0.477528 | +0.0049 | 1 → 1 | 0 | +0.0049 | 371 → 371.167 | +0.167 |
| CHANGE4 | −45.456, 177.589 | 0.492744 → 0.492649 | −0.0095 | 0 → 0 | 0 | 0 | 367 → 366.500 | **−0.500** |
| SLIM | −13.316, 25.251 | 0.476520 → 0.476554 | +0.0034 | 1 → 1 | 0 | +0.0034 | 372 → 372.000 | 0 |
| **max / mean \|Δ\|** | | | **0.0289 / 0.0126** | | **0.0080 / 0.0017** | 0.0137 / 0.0058 | | **0.5 / 0.19** |

Splitting the difference into its two parts:
- **ephemeris interpolation**: 10-min truth vs hourly rows interpolated to the same 10-min samples. At most 0.0004 pp on any fraction, 0 h on the longest dark.
- **hourly sampling**: hourly rows interpolated to 10 min vs hourly samples. This is the rest, e.g. Haworth Sun −0.0293 pp, CHANGE4 dark −0.5 h.
- A 1-hour count can only register darkness in whole hours. The 10-minute longest dark can therefore differ by up to about ±1 h at the start and end of the run; the observed maximum is 0.5 h.

## 3. Metrics cache check (1 h)
For all 6 sites, the port with `ephem.bin` gives `sun_frac`, `earth_frac`, `both_frac` and `longest_dark_h` **identical** to `web/data/metrics/<ID>.json`: absolute difference 0.0 in every field, so there is not even a floating-point rounding difference. The counts are over n = 43,824 hourly samples.
Node.js (the cache's own generator) could not be run here, so the check is against the cached values only.

## 4. Time until sunset / Earthset (50 times × 6 sites = 300 cases each)
- **Times**: 50 random times, `numpy.random.default_rng(20260101)`, uniform in [0, 43,823) h, rounded to the minute. The same 50 times are used at every site (listed in the JSON).
- **`core.js` behaviour, reproduced**:
  - 0 if the Sun is not sunlit / the Earth is not visible now;
  - otherwise an hourly scan from `floor(i)+1`, then 7 bisections (1/128 h = 0.47 min), returning the midpoint;
  - `null` if there is no flip before the last hour (2030-12-31T23Z).

Methods:
- **M1** = `core.js` exactly (hourly ephemeris).
- **M2** = hourly ephemeris, 10-min scan + 30 bisections. **M1 − M2** = error of estimating the transition time.
- **M3** = 10-min ephemeris, 10-min scan + 30 bisections (reference). **M2 − M3** = error from the hourly ephemeris interpolation.
- **M1 − M3** = total.

| | cases with a time | 0 in both | null in both | 0 / null / time disagree | M1 − M3 max / mean / p95 (min) | M1 − M2 max / mean (min) | M2 − M3 max / mean (min) |
|---|---|---|---|---|---|---|---|
| Until sunset | 164 | 136 | 0 | **0** | **0.232 / 0.118 / 0.220** | 0.232 / 0.117 | 0.043 / 0.004 |
| Until Earthset | 48 | 102 | 150 | **0** | **0.240 / 0.117 / 0.207** | 0.223 / 0.117 | 0.020 / 0.008 |

- Earthset `null` = the Earth is always above the mask (MALAPERT, APOLLO17, SLIM); 0 = never above it (CHANGE4, all 50 times). These agree in every case.
- Per site: sunset M1 − M3 max 0.217–0.232 min; Earthset max 0.185 (SHACKLETON_RIM) and 0.240 min (HAWORTH).
- The M1 − M3 maximum (0.24 min) is the half-width of the `core.js` bisection interval (0.234 min) plus up to 0.04 min from the hourly ephemeris.
- The hourly scan could in principle miss a flip and flip back within one hour. Among these 300 + 300 cases there was none: no 0 / null / time disagreement, and M1 − M2 never exceeded the bisection half-width.

## 5. Limitations
- 6 sites and 50 random times, not all 33 sites or every hour. The two polar sites with partial Earth visibility (SHACKLETON_RIM, HAWORTH) are included; the other four have Earth always or never visible.
- The 10-minute "truth" is itself sampled: events shorter than 10 minutes are not resolved.
- The metric port is Python, not the JavaScript in the browser; it reproduces the cache exactly. The masks themselves (terrain, 0.5° bins) are not part of this check.
- The window is the contract window 2026–2030 only.

## 6. Limits paragraph for the submission (English, 2 lines)
> Time step: our metrics use the hourly ephemeris; recomputing six sites at a 10-minute step for 2026–2030 changed sunlight fractions by ≤ 0.03 pp, Earth-visibility fractions by ≤ 0.01 pp and the longest dark period by ≤ 0.5 h.
> "Time until sunset/Earthset" is refined to about ±0.25 min (bisection), against a 10-minute reference; events shorter than one hour can be missed by the hourly scan (none occurred in our 300-case test).
