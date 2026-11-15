# Independent member verification: PR #80 Z1 and Z4

Pinned head: beedb67e7993258720ebfc9219e140636f6e4b11. Reviewer: Minchul Kim; producer: Jiyong Sung. Result: **PASS** (309 comparisons, 0 failures).

Reproduce: `node verification/task_z1_z4/verify.mjs target`, where target is a checkout of the pinned head. No imports from pipeline/ or web/js/. See summary.json for input hashes and comparisons.json for every result, including failures.

## Z1

43,824 hourly cells per site, independent topocentric ENU geometry and cyclic mask interpolation; solar disk >=50%, Earth centre strictly above mask, 2 m observer; LSB-first station bits gated by Earth visibility. Run counts, means, longest and clipped/complete spans checked. Baseline metrics and every Sun/Earth interval/top-10 gap checked separately at these three sites.

|Site|Sun h|Earth h|Both h|Longest dark h|Longest sunlight h|KDSA h|>=1 h|>=2 h|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|APOLLO17|20925|43824|20925|371|341|18213|43246|25717|
|CHANGE4|21594|0|0|367|355|0|0|0|
|SHACKLETON_RIM|37174|21887|19441|75|2817|9986|21807|13940|

Maximum numeric Z1 difference: 0. Criteria: fractions <=0.1 percentage points, durations <=1 h; counts, null cases and clipping lists exact. APOLLO17 no-Earth mean is null (no outage); CHANGE4 whole-window outage is clipped at both ends and complete mean is null. These are distinct.

## Z4

All 18 Task R candidates evaluated separately for each query with atan2(norm(cross),dot) spherical arcs (R=1737400 m), rather than producer haversine. Self excluded by ID; future/target groups and reference date checked. Rank, distance, initial bearing and official-context URL checked. Analytical coincident/antipodal/polar null cases checked.

|Query|Rank|Lander|Distance m|Bearing deg|
|---|---:|---|---:|---:|
|APOLLO11|1|APOLLO16|378912.88555971294|219.28275358175577|
|APOLLO11|2|SLIM|427581.76075248857|172.88158622755577|
|APOLLO11|3|APOLLO17|630177.9216390504|19.637732743379786|
|CHANGE4|1|CHANGE6|631954.719810226|89.61979373578657|
|CHANGE4|2|IM2|1487064.1004418796|183.61277195338778|
|CHANGE4|3|IM1|1649428.4991273186|180.81142116434583|
|SHACKLETON_RIM|1|IM2|167273.58101304556|191.3305051466442|
|SHACKLETON_RIM|2|IM1|308448.68607853213|164.7243535429883|
|SHACKLETON_RIM|3|CHANDRAYAAN3|634624.9449593567|194.91589028002673|

Max relative distance difference: 1.1052879408375406e-13% (criterion <=1%).

## Sources and limits

- Three sites per product, not all 33 numerical outputs.
- Ephemeris, horizons and station bits are independent-verifier inputs, not rederived from kernels/DEMs here.
- Task R coordinates/source metadata preserved and cross-checked; official pages not re-fetched in this run.
- One CPU worker; no production numerical imports; no production data modified.
- No physical link availability or usable landing infrastructure is certified.

- https://naif.jpl.nasa.gov/pub/naif/generic_kernels/
- https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html
- https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html
- https://www.cnsa.gov.cn/n6758968/n6758972/c6798565/content.html
- https://www.cnsa.gov.cn/english/n6465652/n6465653/c6805049/content.html
- https://www.cnsa.gov.cn/english/n6465719/c6810898/content.html
- https://www.cnsa.gov.cn/n6758823/n6758838/c10541444/content.html
- https://www.isro.gov.in/Chandrayaan3.html
- https://darts.isas.jaxa.jp/en/missions/slim
- https://www.nasa.gov/missions/lro/nasas-lro-images-intuitive-machines-odysseus-lander/
- https://ntrs.nasa.gov/api/citations/20260003150/downloads/MSolo%20PRIME-1%20overview%20and%20results%20-%20LSSW.pdf
- https://www.nasa.gov/blogs/missions/2025/03/02/nasa-science-touches-down-on-moon-aboard-firefly-aerospace-lander/

## Failures

None.
