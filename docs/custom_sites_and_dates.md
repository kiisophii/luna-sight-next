# User-defined sites and landing-date scan (S3, 2026-11-14)

Owner: Sua Kim (integrator). Branch `s3-custom-point-dates-sua`. Challenge objectives 1 (user-defined coordinates) and 2 (dates / schedule slips).

## 1. Your own landing point (`web/js/custom_site.js`)
- Type latitude / longitude (degrees, lon east +) or click the mini map (double-click computes at once; arrow keys move 1°, Shift 10°).
  Other views call `LLSN.pickPoint(lat, lon, {compute})` or fire `llsn:pickpoint`; a globe at `LLSN.globe` with `on('pick')` is hooked automatically.
- The horizon is computed in a module Web Worker (`custom_horizon_worker.js` → `hterrain.js`) with the same definitions as
  `pipeline/horizon.py`: 720 azimuths, 0.2–300 km geometric grid (4000 steps), exact sphere R = 1737.4 km, observer 2 m, early stop.
  Terrain: LDEM_64 at 948 m to 150 km, LDEM_16 at 1.9 km to 300 km (`web/data/hterrain/`, contract §12). Only the needed tiles are fetched
  (mid latitudes 4–8 tiles ≈ 1–2 MB; near the poles up to 36 tiles ≈ 8 MB because 150 km spans every longitude). ~0.3–0.5 s per point after download.
- The point joins the picker ("Your sites"), the comparison cards (tag "Browser terrain ~948 m"), the period table, filters, the horizon panorama
  and the landing-date scan. URL: `?u=lat,lon;lat,lon` (recomputed on load).

## 2. Validation (`pipeline/check_custom_horizon.mjs` + `pipeline/validate_custom_horizon.py` → `docs/custom_horizon_validation.json`)
| Check | Result |
|---|---|
| A. Browser JS vs Python `horizon.py` on the same tiles (19 sites) | RMS ≤ 5.3e-11°, max 1.0e-9° (identical) |
| B. Browser vs catalogue pipeline horizons, 16 south-polar sites (card 8, PGDA 5–240 m, branch `s2-polar-horizon-jiyong` a31e1bf) | mask RMS median 0.96°, max 4.87° (ARTEMIS_NOBILE_RIM2); 3 named: ARTEMIS_MALAPERT 1.38°, ARTEMIS_HAWORTH 0.75°, SHACKLETON_RIM 0.99°. Sunlight 2026–2030 differs by median 3.3 pp, max 33.7 pp; Earth median 1.6 pp, max 23.7 pp |
| C. Browser (948 m) vs full LDEM_64 (474 m), APOLLO17 / CHANGE4 / APOLLO15 | RMS 0.155 / 0.023 / 0.106°, sunlight change ≤ 0.05 pp |
Non-polar catalogue horizons (card 9) did not exist yet; rerun B with `--pipeline-dir web/data/horizon` once they are merged.
Large polar differences come from peaks and rims whose height the 948 m grid smooths (h₀ differs by hundreds of metres), so the UI says
"screening, not final siting".

Reproduce:
```bash
python pipeline/build_custom_terrain.py --ldem64 <ldem_64_float.img> --ldem16 <ldem_16_float.img>
node pipeline/check_custom_horizon.mjs data/processed/custom_horizon/browser.json APOLLO17 CHANGE4 APOLLO15 ARTEMIS_MALAPERT ARTEMIS_HAWORTH SHACKLETON_RIM
python pipeline/validate_custom_horizon.py --browser data/processed/custom_horizon/browser.json --pipeline-dir <dir with horizon/<ID>.json> --ldem64 … --ldem16 … --full APOLLO17,CHANGE4,APOLLO15
```

## 3. Landing-date scan (`web/js/landing_scan.js`)
For the focused site, every landing day (00:00 UTC) from the chosen first date over 3/6/12/24 months: sunlight %, Earth %, both % and longest dark
over the first N days (default 14, 1–120), hourly, same definitions as `core.metrics`. Best / worst = highest / lowest "Both" (ties: shorter longest dark).
Dashed line = current analysis-period start. Click (or ←/→ + Enter) starts the analysis period on that date with length N (`LLSN.setPeriod`).
Scans stop at the end of the ephemeris (2030-12-31) and say so.
