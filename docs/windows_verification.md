# Card 15-B verification

Actual unchanged core.js in Node is the reference. Twenty internal visible-window edges per site are checked independently of the production run-grouping loop. The hourly transition must occur at the exact reported UTC hour; domain-clipped edges are not physical rise/set assertions.

| Site | Edges checked | Maximum difference (h) | Whole-series membership | Fraction / longest Sun gap | Result |
|---|---:|---:|---|---|---|
| APOLLO17 | 20 | 0 | PASS (43,824 hours per body; lists/gaps/clipping) | PASS | PASS |
| CHANGE4 | 20 | 0 | PASS (43,824 hours per body; lists/gaps/clipping) | PASS | PASS |
| ARTEMIS_HAWORTH | 20 | 0 | PASS (43,824 hours per body; lists/gaps/clipping) | PASS | PASS |
| SHACKLETON_RIM | 20 | 0 | PASS (43,824 hours per body; lists/gaps/clipping) | PASS | PASS |

Scope: sampled hourly visibility, not sub-hour rise/set accuracy or independent DEM accuracy. SHACKLETON_RIM is included with its corrected-coordinate real horizon from main.

Reproduce:

```sh
node pipeline/build_windows.mjs
node pipeline/test_windows.mjs
python pipeline/check_contract.py
```
