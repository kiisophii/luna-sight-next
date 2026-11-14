# Card 15-B: Sun and Earth visibility windows

Implementation base: a832d22490211ee3d6806778569447f4b0d82efb.

## Outputs

web/data/windows/index.json lists all 33 computed site files, including corrected SHACKLETON_RIM, with no skipped IDs. Each <ID>.json contains chronological Sun-visible and Earth-visible intervals, integer durations in hours, total visible hours, and each body's 10 longest gaps (or fewer if fewer exist). New format proposal: docs/data_contract.md section 18. Existing sections 0–17 and core.js are unchanged.

The latest main now supplies the corrected Shackleton coordinate and its matching new real horizon: (-89.6866, -162.81), h0_m=1729.62, observer +2 m. SHACKLETON_RIM is included. The old R04 point and any flat fallback are not used.

## Meaning for the timeline

- Every interval is [start_utc, end_utc), start included and end excluded, with whole UTC hours. The domain is 2026-01-01T00Z through 2031-01-01T00Z exclusive (43,824 hour bins).
- The state sampled at hour i is held over [i,i+1). Physical rise/set may occur inside that hour; these are sampled timeline windows, not sub-hour ephemeris events. The final bin represents the last 2030 sample; no additional 2031 ephemeris vector is needed.
- Sun follows actual core.sunlit: at least half of the 0.2666-degree-radius solar disk visible. Earth follows actual core.earthVisible: centre strictly above the interpolated real terrain mask. h0_m comes from that site's real horizon, with observer +2 m.
- sun.visible and earth.visible contain maximal true runs. longest_gaps contains false runs, sorted by decreasing duration then increasing start UTC. clipped_start/clipped_end indicate domain censorship, not measured transitions. A never-visible body has no visible intervals and one full-domain gap; an always-visible body has one clipped full-domain visible interval and no gaps. The time domain does not wrap cyclically.
- Use windows/index.json to discover available sites. A skipped ID means unavailable, not zero visibility. Sum duration_h / 43824 for the same visible fractions as core.metrics. The longest Sun gap equals its sampled longest_dark_h.

Each site records SHA-256 values for core.js, ephemeris binary/metadata, catalogue entry, real horizon and generator. Outputs and progress reports are atomic per site. Reruns reuse only input-matching, output-hash-matching results; missing/invalid horizons remove stale output. No source coordinates, ephemeris vectors, real horizon masks or UI code are changed by this task.

## Reproduce and verify

```sh
node pipeline/build_windows.mjs
node pipeline/test_windows.mjs
python pipeline/check_contract.py
```

Node executes the actual current core.js module, without porting its geometry. The windows producer/tests use standard Node/Python libraries. The merged full contract checker also validates Card 18 local maps and therefore requires NumPy (see the repository dependencies). Existing real ephemeris and horizon JSON files must be present.

Results: docs/windows_verification.md (table), docs/windows_verification.json (80 individual edge checks), docs/windows_generation.json (all computed IDs/input hashes/skips).

Independent edge-check logic in Node reads the serialized UTC intervals, picks 20 genuine internal transitions per site across the five-year window, and re-evaluates core.js at the reported edge and preceding hour. For Apollo 17, Chang'e 4, Haworth and Shackleton, all 80 edges matched the exact hour, within the requested one-hour tolerance. All 43,824 memberships per body at each of these four sites were also checked, along with visible fractions and longest Sun gaps. Constant Earth visibility/invisibility cases are verified by membership, without inventing rise/set edges. No independent DEM-accuracy or sub-hour timing claim is made.

check_contract.py now calls pipeline/check_windows.py. It checks ordered maximal windows, duration/clipping, the exact complement's top-10 gaps, ID/coordinate/height consistency, real terrain, input hashes and index coverage. The full input snapshot, including the hterrain index, all 360 global tile payloads and 1,502 south-polar tile payloads, passes with 0 errors and 0 warnings. Tile payloads are fetched from pinned main and byte-checked against their Git blob hashes; this is presence/integrity checking, not new terrain-truth validation. With the index present, a missing required tile is an ERROR, not a warning. An entirely missing index triggers the separate index-missing WARN path; that earlier partial-copy result did not validate tile completeness.

The rerun resumes all 33 outputs. The existing 32 sites have exactly unchanged Sun/Earth interval/gap structures compared with branch commit fd2b2c3440da2178ac0f4029f568a4eac6676574; only provenance hashes reflecting the updated generator may differ. Historic metric/Horizons reports and source assumptions retain their own original scope. A separate reviewer can verify this PR without accepting its recorded PASS as truth.

## Corrected Shackleton result

The new point has 226 Sun-visible intervals and 68 Earth-visible intervals across 2026-2030. Sun-visible hours: 37,174; Earth-visible hours: 21,887. Longest Sun gap: 75 h (2028-04-17T16Z to 2028-04-20T19Z); longest Earth gap: 353 h (2027-01-23T10Z to 2027-02-07T03Z). Each is an hourly sampled interval, not a sub-hour event. All four-site checks and the contract pass with zero errors. Independent review is still requested separately.

For provenance, set LLSN_INPUT_COMMIT to the exact input main SHA when running the generator. If unset, base_main is null; input hashes still identify the exact files. The report no longer hardcodes an outdated main commit.

Latest main merged before publication: a832d22490211ee3d6806778569447f4b0d82efb. New local maps, landing-date slips, monthly seasons and polar browser tiles are preserved. Core ephemeris/catalogue/horizon input hashes remain unchanged; the windows proposal is section 18 because 15-17 are occupied.

## Independent-review corrections

The user-relayed independent review found zero scientific mismatches across the original 32 site products at fd2b2c3440da2178ac0f4029f568a4eac6676574. Those are retained as correct scientific outputs; their Sun/Earth lists, gaps and durations remain exactly identical. Adding the corrected real Shackleton point gives 33 eligible sites and no pending index entries. Generator provenance updates may change metadata hashes; the old 32 numerical payloads are not treated as erroneous.

The checker now invokes Node once to compute SHA-256 over the EXACT JSON.stringify(site) strings from sites.json, rather than assuming Python JSON formatting is equivalent. Node is therefore required when checking windows (LLSN_NODE may specify its executable). producer_sha256 is compared with the actual bytes of pipeline/build_windows.mjs. All six provenance fields are checked for valid syntax, and these two formerly syntax-only fields are now verified against actual input identity. Failure to compute exact hashes is a contract error, not a skipped check.

Run the regression suite with:

```sh
python -m unittest discover -s pipeline -p test_windows_contract.py -v
```

All four full-checker cases pass: normal 33-site inputs succeed; site_sha256=64 zeros is rejected; producer_sha256=64 zeros is rejected; and removing a required near-terrain tile with its index present is rejected as ERROR. Mutations occur only in a disposable copy, with the original files restored. Exact observed exit/error results and checker/producer byte hashes are in docs/windows_hash_check.json. The new Shackleton and original three verification sites each pass 43,824 Sun/Earth states, full visible lists, top-10 gaps and clipping comparisons, plus core.metrics consistency and 20 internal edge checks (80 total). These are author follow-up checks; do not automatically expand the scope of the earlier independent review to the new commit.
