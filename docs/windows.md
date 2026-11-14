# Card 15-B: Sun and Earth visibility windows

Implementation base: main 82cd7f59737b6aa6034d767beace9ba9bfe250f0. Branch: s3-windows-minchul.

## Outputs

web/data/windows/index.json lists 32 computed site files and the explicit SHACKLETON_RIM skip. Each <ID>.json contains chronological Sun-visible and Earth-visible intervals, integer durations in hours, total visible hours, and each body's 10 longest gaps (or fewer if fewer exist). New format proposal: docs/data_contract.md section 15. Existing sections 0–14 and core.js are unchanged.

The current main has merged the corrected Shackleton coordinate and removed its stale horizon. That site remains excluded while the new horizon is pending. The runner includes it only after both catalogue and matching real horizon use the corrected (-89.6866, -162.81) coordinate on main. Do not substitute the old point or a flat horizon.

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

Node executes the actual current core.js module, without porting its geometry. Only standard Node/Python libraries are needed for these commands. Existing real ephemeris and horizon JSON files must be present.

Results: docs/windows_verification.md (table), docs/windows_verification.json (60 individual edge checks), docs/windows_generation.json (all computed IDs/input hashes/skips).

Independent edge-check logic in Node reads the serialized UTC intervals, picks 20 genuine internal transitions per site across the five-year window, and re-evaluates core.js at the reported edge and preceding hour. For Apollo 17, Chang'e 4 and Haworth, all 60 edges matched the exact hour, within the requested one-hour tolerance. All 43,824 memberships per body at each of these three sites were also checked, along with visible fractions and longest Sun gaps. Constant Earth visibility/invisibility cases are verified by membership, without inventing rise/set edges. No independent DEM-accuracy or sub-hour timing claim is made.

check_contract.py now calls pipeline/check_windows.py. It checks ordered maximal windows, duration/clipping, the exact complement's top-10 gaps, ID/coordinate/height consistency, real terrain, input hashes and index coverage. The local full JSON snapshot passes with 0 errors. Warnings are the required Shackleton skip and unrelated hterrain tiles omitted from this local verification copy; this PR does not modify or validate those large global tiles.

The second generation run resumed all 32 unchanged site outputs. Historic metric/Horizons reports and source assumptions retain their own original scope. A separate reviewer can verify this PR without accepting its recorded PASS as truth.
