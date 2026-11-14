# UI ↔ data audit (live site, version 21)

**What:** every number the live site (https://kiisophii.github.io/lunar-landing-site-navigator/, `web/version.json` = 21, main `f4705c0`)
shows for all **33 catalogue sites** was read from the DOM in a headless browser (Playwright/Chromium) and compared with the value
computed independently from `web/data/*.json` and the actual `web/js/core.js` in Node (not from the running page).
**No code was changed.**

- Reference values: `node pipeline/ui_audit_ref.mjs <T> <P>` (actual `core.js` + data files).
- Reader/comparer: `python pipeline/ui_audit.py ref_T1.json ref_T2.json` → `docs/ui_audit/findings.json`, screenshots in `docs/ui_audit/shots/`.
- Each site was opened as `?sites=<ID>&focus=<ID>&t=<T>&p=30` at **two selected times**:
  T = 10086 (2027-02-25 06:00 UTC, period 2027-02-25 → 2027-03-26) and T = 4614 (2026-07-12 06:00 UTC, period 2026-07-12 → 2026-08-10).
- Comparison rule: the shown text must equal the reference formatted the way the UI formats it (integer % with JS `Math.round`,
  one-decimal % with JS `toFixed`, hours with the app's `fmtHours`: `x.x h` below 48 h, else `d d h h`; degrees to 0.1°).

## Result

**5,520 values checked (33 sites × 2 times × 10 panels). 0 numeric mismatches.** Rounding, units (%, h, d, °), sign, the field shown
(Sun vs Both, Earth centre vs any part) and the labels (sunset vs sunrise, Earthset vs Earthrise, sunlit / in shadow, Earth visible / hidden)
all match the data.

Two problems were found, neither a wrong number:

| # | Severity | Panel / element | What is shown | What the data has | Sites | Issue |
|---|---|---|---|---|---|---|
| 1 | **Real bug (integration)** | `#llsn-local` (How much does the exact spot matter?) — `web/js/local_map.js:8` hard-codes 6 IDs | "No local map for the focused site — showing Malapert Massif (region). Local maps exist for six south-polar areas." | `web/data/local/<ID>.json` exists for **all 33 sites** since card 20 (PR #26) | 27: APOLLO11–17, LUNA16/20/24, CHANGE3–6, CHANDRAYAAN3, SLIM, IM1, IM2, BLUE_GHOST1, IM3_REINER_GAMMA, ARTEMIS_CABEUS_B, ARTEMIS_MOUTON(_PLATEAU), ARTEMIS_NOBILE_RIM1/2, ARTEMIS_DE_GERLACHE_RIM2, ARTEMIS_SLATER_PLAIN, SHOEMAKER_RIM_A | [#43](https://github.com/kiisophii/lunar-landing-site-navigator/issues/43) |
| 2 | Cosmetic (rounding) | `#llsn-relay .rl-kpis` | SHACKLETON_RIM, T = 10086: "Link with tower(s) 48 %" + "No link 53 %" = 101 % | 342 h + 378 h = 720 h (47.5 % + 52.5 %); each part is rounded half-up on its own | 1 (of 66 site-times) | [#44](https://github.com/kiisophii/lunar-landing-site-navigator/issues/44) |

Screenshots: `docs/ui_audit/shots/<ID>_10086_local.png` (27 sites) and `docs/ui_audit/shots/SHACKLETON_RIM_10086_relay.png`.

## Checked panels and fields

| Panel | Values compared (per site and time) | Reference |
|---|---|---|
| Comparison card (`#cards`) | Sun elevation, Sun azimuth, until sunset/sunrise (label + value), until Earthset/Earthrise, sunlit / Earth-visible chips, Earth elevation; period Sunlight / Earth link / Both % and "x of 30 days", longest dark | `core.sunAzEl`, `earthAzEl`, `until*`, `sunlit`, `earthVisible`, `metrics(i0, i1)` |
| Analysis-window table (`#llsn-window`) | Sunlight %, Earth link %, Both %, longest dark for the site's row | `core.metrics(i0, i1)` |
| Horizon panorama readout (`#llsn-horizon`) | Sun elevation, terrain mask at the Sun azimuth, Earth elevation, mask at the Earth azimuth, Earth visible label | `core.horizonAt` |
| Communication story (`#llsn-story`) | direct link %, Korea (Yeoju) % and hours, DSN % | metrics + `korea/stations.json` bits |
| Korea panel (`#llsn-korea`) | hours and % for KDSA, Goldstone, Madrid, Canberra, any DSN, only Yeoju; site sees Earth, + Yeoju, + any DSN | `korea/stations.json` + `core.earthVisible` |
| Relay panel (`#llsn-relay`) | direct %/hours, added via tower %, link with towers %, no link %, longest no-link stretch, whole-window link % with 0–3 towers | `relay/<ID>.json` timeline segments over the period |
| Landing-date scan readout (`#llsn-dates`) | Sunlight, Earth link, Both %, longest dark for the date the readout names | `date_slip/<ID>.json` series (or `core.metrics` for 14 days) |
| Slip table (`#llsn-slip`) | +7 / +14 d typical and worst change for Sunlight, Earth link, Both; share of days that get worse | `date_slip/<ID>.json` `slip` |
| Seasons summary (`#llsn-seasons`) | sunlight min–max, best and worst month, south-vs-north pp, longest darkness min–max | `monthly/<ID>.json` (lunation series) |
| Local map readout (`#llsn-local`) | catalogue node Sunlight / Earth / Both / longest dark; Both min–max within 1/3/5/10 km | `local/<ID>.json` (only for the 6 sites the panel shows; see finding 1) |

## Notes (not mismatches)

- **Landing-date scan:** the scan starts at today's date by default. When the selected period is earlier (e.g. T = 4614, July 2026),
  the readout describes the scan's best day and names it ("Landing 2026-12-15 …"); the numbers are correct for that named date.
  It may still surprise a judge who expects the readout to follow the selected period.
- **Seasons summary** prints whole hours ("176 h") while the other panels use `d h` ("7 d 8 h"). Same value, different format.
- **One-decimal %:** the app uses JS `toFixed(1)` (e.g. 0.4965 → "49.6 %", because 49.65 is stored as 49.6499…). The audit follows the same rule.
- Not covered: tower-network table rows and link-budget table in the relay panel, the 3D globe overlay text, the custom-point panel,
  chart pixel positions.

## Issues opened (#43, #44)

1. **Local map panel shows only the six card-18 areas.** `web/js/local_map.js:8` lists six IDs and the note says "Local maps exist for six
   south-polar areas", but card 20 added `web/data/local/<ID>.json` for the other 27 sites. Fix: build the area list from the catalogue
   (all 33) or from `web/data/local/` and update the note text.
2. **Relay KPIs can add up to 101 %.** "Link with tower(s)" and "No link" are rounded separately (47.5 % → 48 %, 52.5 % → 53 %).
   Fix: show "No link" as 100 − the rounded link %, or use one decimal.
