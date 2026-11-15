# Comparison tray — approved four screenshots

Base: integ-1915 b1f813e, then integrated abb09f5 before final verification. Jiyong, 2026-11-15.

The main tray now has the reference's four categories, secondary choices, semantic number colors, candidate rows, and a fixed footer with an independently scrolling body. Earth adds “With the Sun”; Relay uses the existing 15 m network's hourly segments for total/added running shares; Terrain shows the actual azimuth horizon mask. Terrain bounds include negative and high elevations rather than clipping them to the example's 0–6°. Values, candidate names and dates follow production inputs, not screenshot numbers. Desktop tray height follows the existing resizable panel.

Only tray_cat.js, its scoped stylesheet and a pure series helper change production behavior. index.html, layout.css, scientific calculations and data files are untouched.

## Verification

Serve web on port 8021, then:

```
node --test verification/tray_reference.test.mjs
python verification/tray_reference_browser.py
```

48 category/subview screenshots: 1440, 1280, 390 × EN/KR × four categories plus four secondary views. Integrated longest-gap strips and 04+ dashed candidates are retained; Gaps filled uses the integrated interval strip and reports the added period share. Browser script asserts no page errors or horizontal document overflow. Three relay curve endpoints and added shares equal relayPeriod's existing totals (tolerance 1e-12). Unit checks cover AND visibility, clipped relay intervals, missing coverage and horizon closure/negative elevation. Browser suite requires Python Playwright with Chromium.

The separately requested interaction audit does not authorize other UI fixes; findings are recorded in the user's final_report.html outside the repository. Actual touch pinch and complete reference hover behavior were not verified; do not represent those as passing.
