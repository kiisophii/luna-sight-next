# Data contract v1 (fixed 2026-11-14 09:40 KST)

Every card writes or reads these files. **Do not change a format without telling the team** (post in chat + edit this file in a PR).
Card 6 adds fake (mock) versions of every file by 09:40 (`"mock": true`), so UI work can start immediately. Real data overwrites them with the same names.

## 0. Conventions (all files)
| Item | Rule |
|---|---|
| Body frame | `MOON_ME` (DE421 mean-Earth / polar axis) — same frame as LOLA DEMs and PGDA maps |
| Latitude / longitude | degrees; lat −90…90; **lon −180…180, east positive** |
| Heights | metres above the reference sphere **R = 1737.4 km** |
| Azimuth | degrees, **0 = north, clockwise** (90 = east) |
| Elevation | degrees above the local horizontal plane (no refraction; the Moon has no air) |
| Time | **UTC**. Hour index `i` = hours since `2026-01-01T00:00:00Z` |
| Observer | 2 m above terrain |
| Binary | little-endian `float32`, row-major |
| IDs | `UPPER_SNAKE` (e.g. `APOLLO17`, `SHACKLETON_RIM`), unique; file names lowercase except IDs |
| Text | English in data files; Korean labels only in `name_ko` |

## 1. `web/data/sites.json` — owner: card 4
Array of objects:
```json
{
  "id": "APOLLO17", "name": "Apollo 17", "name_ko": "아폴로 17호", "short": "Apollo 17",
  "group": "apollo",
  "lat": 20.1908, "lon": 30.7717, "elev_m": null,
  "source_url": "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html",
  "coord_quality": "primary",
  "note": ""
}
```
- `group` ∈ `apollo, luna, change, chandrayaan, slim, clps, artemis3_region, polar_peak, future, custom`
- `coord_quality` ∈ `primary` (official/paper value) · `secondary` (derived from imagery) · `estimated` (measured by us; explain in `note`)
- `short` ≤ 14 characters (fits a card). Artemis III regions: `note` = "region representative point".

## 2. `web/data/ephem.bin` + `ephem.json` — owner: card 1
- `ephem.bin`: `float32[N][6]` = `sun_x, sun_y, sun_z, earth_x, earth_y, earth_z` (km, Moon centre → body, MOON_ME, light-time-corrected apparent).
- 2026-01-01T00Z … 2030-12-31T23Z, 1-hour step → **N = 43,824** (≈1.05 MB).
- `ephem.json`:
```json
{"start": "2026-01-01T00:00:00Z", "step_h": 1, "n": 43824, "frame": "MOON_ME_DE421", "units": "km",
 "columns": ["sun_x","sun_y","sun_z","earth_x","earth_y","earth_z"],
 "source": "NAIF de440s.bsp + moon_pa_de421_1900-2050.bpc via Skyfield", "mock": false}
```
- Validation file (not shipped to web): `data/processed/ephem_2020-2038_2h.npz` (same columns) for the 18.6-year PGDA comparison.

## 3. `web/data/horizon/<ID>.json` — owners: cards 2 & 3 (DEMs), computed in phase 2
```json
{
  "id": "APOLLO17", "lat": 20.1908, "lon": 30.7717,
  "h0_m": -1820.5, "obs_height_m": 2,
  "az_step_deg": 0.5, "mask": [720 numbers, degrees, index k ↔ azimuth k*0.5],
  "max_range_km": 300,
  "dem_sources": [{"name": "SLDEM2015", "res_m": 59, "to_km": 150}, {"name": "LDEM_16", "res_m": 1895, "to_km": 300}],
  "mock": false
}
```
- Mask = maximum elevation angle of terrain along each azimuth, **lunar curvature included**. Between bins: linear interpolation.

## 4. `web/data/metrics/<ID>.json` (optional cache, phase 2)
`{"id", "window": "2026-01-01..2030-12-31", "sun_frac", "earth_frac", "both_frac", "longest_dark_h", "slope_deg"}` — fractions 0…1.

## 5. `web/data/validation.json` — owner: card 5
```json
{
  "window": "2020-01-01..2038-08-01", "step_h": 2, "n_points": 240, "seed": 42,
  "sun":   {"mae_pp": 0, "rmse_pp": 0, "r": 0, "within_pgda_60m_spread_pct": 0},
  "earth": {"mae_pp": 0, "rmse_pp": 0, "r": 0, "within_pgda_60m_spread_pct": 0},
  "points": [{"lat": -86.1, "lon": 12.3, "ours_sun": 0.41, "pgda_sun": 0.43, "pgda_sun_min60": 0.40, "pgda_sun_max60": 0.47,
              "ours_earth": 0.55, "pgda_earth": 0.56}],
  "named": [{"id": "SHACKLETON_RIM", "ours_sun": 0.0, "pgda_sun": 0.0, "pgda_sun_min300": 0.0, "pgda_sun_max300": 0.0}],
  "pgda_files": ["AVGVISIB_85S_060M_201608.TIF", "AVGVISIB_85S_060M_201608_EARTH.TIF"], "mock": false
}
```

## 6. `web/js/core.js` API — owners: card 6 (+ card 1 checks the maths)
| Function | Returns |
|---|---|
| `loadData()` | Promise; loads sites, ephem, horizons on demand |
| `siteFrame(site)` | local east/north/up unit vectors at the site |
| `sunAzEl(site, i)` / `earthAzEl(site, i)` | `{az, el}` degrees at hour index `i` (Earth with topocentric parallax) |
| `horizonAt(site, az)` | mask elevation (deg), linear interpolation |
| `sunVisibleFraction(site, i)` | 0…1, solar disk radius 0.2666° above the mask |
| `earthVisible(site, i)` | boolean, Earth **centre** above the mask |
| `untilSunset(site, i)` / `untilEarthset(site, i)` | hours until the next transition to not-visible (`null` if none within the window); `untilSunrise`, `untilEarthrise` likewise |
| `metrics(site, i0, i1)` | `{sun_frac, earth_frac, both_frac, longest_dark_h}` |
- "Sunlit" = `sunVisibleFraction ≥ 0.5`. "Both" = sunlit AND Earth visible.

## 7. Other shared files
- `web/version.json` `{"v": <int>}` — integrator bumps on every merge (TV auto-reload).
- `web/css/theme.css` — owner: card 7 (CSS custom properties only; everyone uses the variables).
- `data/DATASETS.md`, `docs/SI_USAGE.md` — everyone appends, never edits others' rows.

## 8. Check
Card 6 adds `python pipeline/check_contract.py`, which validates every file in `web/data/` against this contract (shapes, ranges, required keys). Run it before opening a PR that touches data.
