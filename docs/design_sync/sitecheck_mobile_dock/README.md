# Site check mobile readability and compact UTC picker

Base: integ-1915 at 13010bc. No data or calculation changes.

- Phone time KPI labels wrap at word boundaries with space for two lines; every label has a localized full-name title.
- Phone time-bar axes show start / middle / end (three ticks); larger screens retain five.
- At 1100–1599 px, the existing UTC picker uses a calendar button above the dock. The existing popup moves with it so it also remains usable on the time-independent map layers. Outside this range both return to their original time-control container.
- Internal team review badges are removed from Site check rendering. Source data, the verification ledger, and scientific limitations remain unchanged.

## Verification

Serve web/ on port 8021 with JavaScript MIME types, then run:

```
python pipeline/verify_sitecheck_mobile_dock.py
python pipeline/verify_utc_dock_responsive.py
node --check web/js/brief.js
node --check web/js/shell.js
```

390 / 1100 / 1280 / 1440, EN and KR: zero console/page errors and no horizontal overflow. Tests verify full label titles, no clipped phone label text, three non-overlapping phone ticks, keyboard opening and Escape closing, and a real change to 13:15 UTC. The popup remains within the viewport.

Additional checks cover all four map layers, resizing through 1920 / 1100 / 390 / 1440, and clearance between the compact calendar button and the dock. See checks.json, responsive.json, and the dock/time screenshots for all eight cases.
