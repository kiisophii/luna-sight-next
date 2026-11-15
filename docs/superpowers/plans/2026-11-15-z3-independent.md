# Z3 Independent Verification Plan

> **For agentic workers:** Use superpowers:executing-plans to execute this verification in this session.

**Goal:** Independently verify Minchul's PR #79 landing-date extension as Jiyong.
**Architecture:** A standalone Python/NumPy verifier reads the original ephemeris and stored horizons, reconstructs observer-relative Sun/Earth states without importing production code, and directly aggregates each requested stay. Compare all published values, signed shifts, bounds and censor flags; retain every discrepancy and input hash.
**Tech Stack:** Python, NumPy, pytest, Git; no GPU or new external data.
**Spec:** docs/data_contract.md (Z3), docs/z3_dates.md, PR #79.

## Global Constraints
- Main baseline aa1e1fb; PR head 3939a3b8323b3ddf74c4c62691f8d9318bd3c1f1.
- 2026–2030, 43,824 hourly cells; 1,826 midnight arrivals, stays 168/336/708 h; shifts -7/-3/-1/+1/+3/+7 days.
- Sun disk fraction >=0.5; Earth centre strictly above terrain; observer 2 m. Fraction <=0.1 pp, duration <=1 h; statuses/nulls/censor flags exact.
- All 33 sites (superset of required polar/near-side/far-side sample). No production/UI changes or producer numerical imports. Preserve existing ledger/SI rows.

## Review Focus
- Half-day stay: exactly 708 cells, never rounded to 30 days.
- Exclusive dataset endpoint, valid final cell, invalid shortened stays.
- Negative shifts at the first day and invalid base with valid target.
- Actual transition at an edge versus a censored run.
- Wrong stored values must be detected, including nulls, status and fractions.

## Task 1: Independent numerical verifier
- [x] Add analytic geometry, boundary/censor/shift and mutation tests in pipeline/tests/test_z3_independent_jiyong.py; run and observe missing implementation.
- [x] Implement pipeline/verify_z3_independent_jiyong.py with only standard-library/NumPy numerical dependencies. Use direct slice counts and dark-run boundaries, not producer cumulative sums or cached flags.
- [x] Run tests; all must pass. Record source hashes and compare PR data with current main.

## Task 2: Full computation and handoff
- [x] Recompute all 33 sites, every arrival/stay/shift. Save JSON summary, all discrepancies CSV and per-site CSV under docs/z3_independent_jiyong/.
- [x] Review maxima/medians, explicit leap-day/end-boundary evidence and any failures. Rerun existing focused checks, contract and ledger validation as applicable.
- [x] Write report, append ledger/SI, commit and open a PR. No merge.

## Execution record

- Task 1 complete: initial missing-module test failure observed, then 6 controls pass.
- Task 2 numerical work complete: 33 sites, 13.077 s, 8,315,604 fields, zero differences; 7 existing producer tests pass.
- Separate AI review: no actionable defects. No additional human verification claimed.
- Checkout ruling: preserve the production files and byte-hash policy; diagnose CRLF with direct Git blobs and rerun the full contract on an exact LF archive snapshot. Ordinary Windows checkout fails 66 hash checks; Git-LF snapshot passes 0 errors/0 warnings.
- Handoff complete: PR #85 opened from s8-z3-verify-jiyong; not merged. Final ledger check 0 failures and diff check clean.
