# Detail products Z1 / Z2 / Z4 - integration and handoff

Jiyong, 2026-11-15. Implements the explicit new task-board requests for detail-page data. Z3 date expansion is owned by Minchul's existing `s7-z3-dates-minchul` branch and is not duplicated here. The current PR only adds optional data/builders/contracts; it does not wire new UI, change catalogue values or change existing scientific results.

| Product | Complete scope | Measured production time | Main result |
|---|---|---:|---|
| Z1 time statistics | 33 sites x43,824 hourly cells; outages, sunlight runs, Earth/Sun/both, station combinations | 0.696 s single CPU; resume0.097 s | Existing metrics and all visibility intervals match exactly; clipped runs and complete-only statistics separate |
| Z2 PSR proximity | 16 south-polar sites, native20m raster; nearest pixel centre and pixel-union boundary | Original acquisition+computation31.619 s; final cached recompute3.302 s | All nearest results guaranteed; IM1 entire10km disk not covered but nearest missing area>=4030m is beyond its nearest candidate |
| Z4 landing history | 33 queries, 18 actually landed mission pool,3 nearest other landers | 0.00348 s computation/assembly, excluding process startup/final serialization | 99 neighbour records; official context sources; self/targets excluded |

Each worker used one computation thread, with independent tasks run concurrently. No GPU was used: these are small aggregation/geodesic operations and bounded HTTP reads, not new expensive horizon marches. No speculative GPU speedup is claimed. Existing desktop preview servers were left running; raw PSR ranges and checkpoints stay in the existing D-backed ignored storage. New web JSON totals208,497bytes (before checkout newline conversion).

## Validation and status

- Z1: independent NumPy geometry and group-by/station loop reproduces **all33 records and every statistic exactly**; [evidence](detail_author_verification.json). Uses the same input ephemeris and masks, not external physical truth.
- Z2: independent closed-form stereographic chord formula and quadratic edge minimization searches **all16 original native windows**, not only three; maximum centre1.284e-8m / boundary1.093e-8m. [Evidence](detail_z2_author_verification.json). Pixel/geolocation accuracy is not established by this numerical agreement. A separate review session also checked bearing with a separate spherical formula (max1.586e-10deg).
- Z4: independent unit-vector great-circle geometry reproduces every nearest ranking over the full candidate pool; max difference6.985e-10m across99 exported pairs, bearing1.990e-13deg.
- Focused tests: Z1 Node5, PSR Python15, history Python6, contract Python7. Resume guards reject stale/tampered output and native windows; old PSR/time indexes are withdrawn before regeneration and atomically published only when complete.
- Two separate AI review sessions checked implementation/specification. A history-contract gap (missing mandatory provenance paths/frame/official-source agreement) was fixed with a failing regression followed by passing tests. Those reviews are **author verification only**; another team member still needs to check3sites per product with their own code. No independent-team ledger status is claimed.

Full repository checker passes0errors/0warnings when existing core/window producer text is read with its committed LF bytes. The normal Windows CRLF checkout has a pre-existing33-window producer-hash failure; the check uses a try/finally temporary byte restoration and restores the original working-copy bytes afterward. No stored scientific/source hash was rewritten to mask this issue. New product hashes explicitly normalize CRLF to LF.

The initial broad Python run had294passes/4skips/6failures: four window-contract fixture failures (pre-existing CRLF hash plus new optional-product source paths) and two existing Numba import-order/thread-pool conflicts. The detail checker now resolves code/docs beside itself while candidate data remains controlled by `--data`; the window regression checks its specific error rather than an obsolete global error count. Set NUMBA_NUM_THREADS=1 **before** Python imports for broad testing. Final rerun results are recorded below after integration.

## Meaning for the UI

Time-stat observed means include clipped intervals; use complete-only values when the question is the mean duration of fully observed runs. These are hourly geometric visibility opportunities, not RF throughput or guaranteed service. PSR must display **PSR != confirmed ice**; boundary distance is to a20m raster classification, not a traversable route. Historical proximity refers only to the18-task-defined actual landers, not an exhaustive mission inventory or usable infrastructure. Keep the uncertainty/role notes from the individual reports.

## Handoff commands

```powershell
node pipeline/detail_time_stats.mjs
python -X utf8 pipeline/detail_psr.py
python -X utf8 pipeline/detail_history.py
python -X utf8 pipeline/verify_detail_author.py
python -X utf8 pipeline/verify_detail_psr_author.py
python -X utf8 pipeline/check_contract.py
```

The PSR verification needs the original windows identified in each output. The other checks use committed ephemeris/catalogue/station data. Product schemas are proposed under named Z1/Z2/Z4 headings in data_contract.md so pending Y/Z3 section numbers are not overwritten. Sources and SI appended; human SI cells remain TO CHECK. Sua reviews and merges.

## Final integrated validation

Latest main `564fac3` (version38, including Y and its external verification, S and other audits) was merged before the PR. Shared source/SI/contract/ledger files preserve main and append the new detail material; both terrain-Y and detail checks are registered. The 52 web-file changes relative to main are all under `web/data/detail/`.

After fixing the fixture integration and setting NUMBA_NUM_THREADS=1 before imports, the latest-main full Python run completed in118.65s: **354passed,1skipped,2subtests passed**, plus one missing-input failure in the pre-existing ephemeris validation test. The missing ignored18.6-year NPZ was found in D-backed card8/card23 caches with identical SHA256 `358526e031babbe9944695b253ad36f2f63f15cb0175225dfcf04c62886ccabe`, copied into this checkout's ignored D-backed processed folder, and that test then **passed in0.41s**. Thus355 distinct Python tests and2subtests passed across the full run and targeted rerun; this is not represented as one clean full-suite invocation. One optional CuPy test skipped in the CPU environment. No production ephemeris was regenerated or modified. Earlier targeted window/Numba/detail rerun:20passed. Node detail tests:5passed.

Final contract was rerun with the documented committed-LF workaround; ledger verifier0failures. Final AI integration review found no blocking issue and confirmed append-only preservation and that arbitrary candidate `--data` roots retain provenance checks. SI human sign-off and independent other-member3site checks remain pending.
