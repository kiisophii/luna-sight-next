# Z3 independent verification — Jiyong Sung

**PASS: all 33 sites, every published daily stay and signed date shift agree exactly.** Maximum and median absolute fraction difference: **0 percentage points**. Maximum and median duration/count difference: **0 hours**. No range, null, target-index or censor-flag differences.

This is another team member's AI-assisted verification of Minchul's [PR #79](https://github.com/kiisophii/lunar-landing-site-navigator/pull/79), not another run of the producer. No human numerical rerun is claimed. The requested three-site check is exceeded: it includes SHACKLETON_RIM (polar), APOLLO17 (near side), CHANGE4 (far side), and the other 30 catalogue sites.

## Pinned inputs and independence

- Checked main: `aa1e1fb5f0d1a6216fe5453642374a70d14357c9` (web version 40).
- PR #79 head: `3939a3b8323b3ddf74c4c62691f8d9318bd3c1f1`.
- Git comparison finds **no changes** between that PR head and checked main in `detail/dates/`, horizons, ephemeris, sites or `core.js`.
- The independent checker imports only the Python standard library and NumPy. It does not import the producer, `core.js`, existing verifiers, or hourly-bit checkpoints.
- It rebuilds the local east/north/up frame, subtracts the observer position (terrain elevation + 2 m), interpolates the 720-bin horizon periodically, integrates the solar disk (radius 0.2666 degrees), and applies Sun fraction >=0.5 / Earth centre strictly above terrain.
- It counts each stay directly from its hourly slices. The longest dark run is reconstructed from gaps between lit indices; no producer cumulative-sum or run-count function is used. Every shifted window is compared against these independently recomputed base windows.
- Original source references: [NAIF/terrain inventory](../../data/DATASETS.md), [Z3 contract](../data_contract.md#z3-proposed--full-period-landing-date-extension-detail-dates-z3-v1-2026-11-15), [producer specification](../z3_dates.md). Input/checker SHA-256 and per-site independent flag hashes are in [summary.json](summary.json).

## Full coverage and results

| Check | Scope | Result |
|---|---:|---|
| Independent Sun/Earth states | 33 x 43,824 site-hours | Recomputed from ephemeris and horizon |
| Valid base stays | 179,190 | All stored values exact |
| Invalid base stays | 1,584 | All statuses/nulls exact |
| Valid signed shifts | 1,072,962 | All target indices and deltas exact |
| Invalid signed shifts | 11,682 | All three invalid-status cases/nulls exact |
| Scalar field comparisons | 8,315,604 | Zero discrepancies |
| Fraction comparisons (including shift deltas) | 3,756,456 | Max/median 0 pp; criterion <=0.1 pp |
| Count/duration comparisons | 5,008,608 | Max/median 0 h; criterion <=1 h |

Complete site-by-site table: [sites.csv](sites.csv). Every discrepancy would be retained, even below the acceptance threshold; [discrepancies.csv](discrepancies.csv) has a header and no rows. Summary boundary evidence retains 693 actual/reference rows, including 2028-02-28/29 and 2028-03-01 at every site/stay.

| Stay | Valid arrival days/site | Invalid days/site | Last valid midnight arrival | Last valid exclusive end |
|---|---:|---:|---|---|
| 7 d / 168 h | 1,820 | 6 | 2030-12-25 | 2031-01-01 00:00 UTC |
| 14 d / 336 h | 1,813 | 13 | 2030-12-18 | 2031-01-01 00:00 UTC |
| 29.5 d / 708 h | 1,797 | 29 | 2030-12-02 | 2030-12-31 12:00 UTC |

The half-day stay is exactly 708 cells. The final midnight arrival that fits it ends at noon; the following arrival cannot be shortened. Seven- and fourteen-day stays include the final observed cell [2030-12-31 23:00, 2031-01-01 00:00). Negative shifts before 2026-01-01 and invalid-base/valid-target cases are explicitly checked. A dark run is censored only when it continues outside the stay or its adjacent observation is unavailable; an actual transition on the boundary is not censored.

## Tests, runtime and checkout portability

- Independent analytic/control tests: **6 passed**. Controls include exact Sun-half/Earth-centre thresholds, circular interpolation, censored versus true-transition edges, 708-hour final-cell counting, all signed-shift statuses and deliberately corrupted stored values.
- Existing producer boundary tests: **7 passed** (regression only, not independent evidence).
- Independent full computation: **13.077 s**, four CPU worker threads, BLAS/OMP limited to one thread each. No GPU, terrain regeneration or new download was needed.
- Separate AI code review found no actionable defects; it inspected the checker/tests and evidence, without rerunning the full calculation. This is additional code review, not an additional human team verification.
- The ordinary Windows checkout's full contract reports **66 byte-hash errors**: 33 existing `windows/` producer hashes and 33 Z3 index file hashes. `core.autocrlf=true` converts LF to CRLF; normalized working bytes match Git blobs. **Do not interpret the checkout run as a numerical failure or claim it passed.**
- A separate snapshot exported with `git -c core.autocrlf=false archive` preserves original Git bytes. The complete contract there reports **0 errors / 0 warnings**. Evidence: [contract log](contract_git_lf.txt), [checkout/blob hash comparison](checkout_evidence.json). Production files and hash rules were not changed to make this pass.

## Reproduce

From the repository root, with Python/NumPy/pytest and Node installed:

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
python -m pytest pipeline/tests/test_z3_independent_jiyong.py -q
python pipeline/verify_z3_independent_jiyong.py --workers 4
node --test pipeline/test_detail_dates.mjs
python pipeline/verify_ledger.py
```

Run `python pipeline/check_contract.py` in a checkout that preserves LF bytes (set `core.autocrlf=false` before checking out), or in the exact-byte archive snapshot. The numerical checker itself records both raw and LF-normalized hashes where Windows newline conversion is relevant.

## Limits and integration

This establishes implementation and aggregation agreement with shared stored ephemeris/terrain inputs. It does **not** validate the physical accuracy of the DEM or ephemeris, sub-hour transitions, non-midnight arrival times, or browser/UI integration. Longest darkness is the observed run within each requested stay, not necessarily the complete physical night. Existing production metadata still says `author_verified_independent_member_pending`; this report and appended ledger entry supply the new independent evidence without changing hashed products. No scientific or UI data were changed.
