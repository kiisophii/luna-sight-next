# Z3 full-period landing-date extension

Author-produced data; independent team verification by Jiyong is pending. No existing date_slip, ephemeris, horizon, metrics or UI values were changed.

All 33 catalogue sites, all 1,826 UTC-midnight landing days in 2026–2030, stays of 7/14/29.5 days (168/336/708 hours), signed shifts -7/-3/-1/+1/+3/+7 days. Actual core.js hourly Sun/Earth flags feed integer cumulative sums; no rounded legacy array feeds generation.

A stay includes exactly its requested [start,end) hourly cells. The final observed cell is [2030-12-31 23:00,2031-01-01 00:00). An end-exclusive boundary at 2031-01-01 00:00 is allowed; no later cell is used. Invalid base/shifted stays are explicitly marked, never shortened.

| Stay | Hours | Valid landing days per site | Out-of-range daily starts | Last valid landing |
|---|---:|---:|---:|---|
| 7 days | 168 | 1820 | 6 | 2030-12-25 |
| 14 days | 336 | 1813 | 13 | 2030-12-18 |
| 29.5 days | 708 | 1797 | 29 | 2030-12-02 |

Stored base fractions are unrounded IEEE-754 double divisions of integer visible-hour counts. Slip fraction changes use exact signed hour numerators and the fixed stay-hour denominator: delta_frac = delta_sun_h / stay_h (similarly Earth/both); multiply by 100 for percentage points. Shifted fractions themselves are at rows[target_day_index]. This avoids repeating the same metrics and losing precision through subtraction of rounded floats.

Rows and delta rows use column definitions embedded in every file. All 1,826 days remain present, including invalid tails. A valid target with an invalid base is base_out_of_range; an invalid target with a valid base is target_out_of_range; both invalid is both_out_of_range. All four delta numerators are null when a comparison is invalid. Negative shifts are earlier arrivals, not delays.

Longest darkness is the longest run within each stay. Dark runs continuing across a stay edge are marked censored; a global dataset edge without an adjacent observation is censored, not an asserted sunrise.

Author validation: 179190 valid base windows independently re-aggregated from saved fresh core.js bits with NumPy cumulative counts and run-transition scans, zero discrepancies. All signed deltas/range flags are checked by the contract. 96360 legacy comparisons reproduce the existing 2026–2027 14-day data within its documented 4-decimal rounding (hours exact). This is author-side verification on shared bits, not another member's independent geometry.

Reproduce from the repository root:
~~~sh
node --test pipeline/test_detail_dates.mjs
node pipeline/build_detail_dates.mjs
python pipeline/check_detail_dates_run.py
python pipeline/check_contract.py
~~~

Generation checkpoints per site, signatures and full-content hashes reject stale/tampered reuse. A complete discovery index is written only after all 33 sites. Raw hourly-bit checkpoints are ignored under data/processed/detail_dates.

Independent handoff: a different member should derive hourly flags from ephem.bin and original horizon files using their own code, then compare 3 sites including a polar site, a near-side and a far-side site, all stays and six shifts. Include 2028-02-29, final valid dates, out-of-range dates, and negative shifts at 2026-01-01. Acceptance: fraction <=0.1 percentage point and durations <=1 hour; all range statuses should agree exactly. Do not import this producer or use its cached bits as independent truth.

Limits: fixed catalogue terrain, hourly classification, midnight arrival, no fractional-cell interpolation, no operational power/communication guarantee. Source files are unchanged existing NASA NAIF ephemerides and LOLA/SLDEM horizon inputs; see data/DATASETS.md and each product input SHA-256.

## Existing coordinate-validator portability fix

The first full contract run failed on 33 unchanged local250 maps because it required bit-identical latitude/longitude regenerated on another platform. The pinned-main validator was rerun separately; all failures were the same coordinate check, with no grid-index/offset discrepancy. Observed maximum coordinate difference: 2.84217094304e-14 degrees. Only lat/lon equality now permits 1e-9 degree (at most 0.031 mm on the reference sphere); node indices and offsets remain exact. Four focused tests reject meaningful coordinate changes, changed indices/offsets and nonfinite coordinates. Original maps/generating geometry were byte-compared against main and remain unchanged. Full contract after this fix passes 0 errors/0 warnings. Evidence: z3_checks/local250_portability.json.
