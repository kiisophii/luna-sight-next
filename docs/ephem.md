# Card 1: real ephemerides and verification

## Outputs
- `web/data/ephem.bin`: 43,824 x 6 little-endian float32 values, 1051776 bytes.
- `web/data/ephem.json`: exact contract metadata; `mock: false`.
- Hour 0: 2026-01-01T00:00:00Z; final hour: 2030-12-31T23:00:00Z.
- `data/processed/ephem_2020-2038_2h.npz`: 81,444 rows, 2020-01-01T00Z inclusive to 2038-08-01T00Z exclusive (last 2038-07-31T22Z). Ignored by git; regenerate with the same command.
- NPZ keys: `vectors` (N x 6), `hour_index` (hours since 2026-01-01 UTC, including negatives), `start`, `stop_exclusive`, `step_h`, `frame`, `units`, `columns`.

## Method
Skyfield `moon.at(t).observe(body).apparent().frame_xyz(frame)` includes light-time, aberration and gravitational deflection. Orientation is the explicit `MOON_ME_DE421` frame, evaluated at reception time. DE440s translations are intentionally combined with the DE421 lunar orientation required by the contract. Source: https://rhodesmill.org/skyfield/planetary.html and https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf .

The local frame uses east/north/up, east-positive longitude and north-clockwise azimuth. `az_el()` subtracts the 1737.4 km sphere + terrain height + 2 m observer from both exported body vectors, exactly like core.js. The separate `direct_az_el()` computes a fully topocentric observation for quantifying that approximation; it does not use the exported geometry helper. No refraction or terrain obstruction is applied here.

UTC uses the downloaded naif0012.tls. Unknown future leap seconds are not predicted. Update the LSK and regenerate if announced leap seconds affect the requested future interval. Raw kernel hashes and package versions are in `ephem_provenance.json`.

## Reproduce
Use Python 3.11 or 3.12 and Node.js with ES module support. From repository root:

```sh
python -m pip install -r pipeline/requirements-ephem.txt
python pipeline/ephem.py
python pipeline/check_contract.py
python -m unittest discover -s pipeline -p test_ephem.py -v
python pipeline/validate_ephem.py
node pipeline/check_ephem_web.mjs
```

Downloads skip existing kernels and resume `.part` files. Computation saves flushed 2,048-row checkpoints with input hashes under ignored `data/processed/`; rerun the same command after interruption. Final files are replaced only after each array has been computed. `validate_ephem.py --offline` reuses the cached, URL-checked Horizons responses. All raw data are ignored by git.

## Verification (automated; human review still pending)
- Contract checker: PASS, 0 errors. Nine warnings are the pre-existing mock sites/horizons/PGDA validation, which card 1 does not replace.
- Python: six tests passed (UTC and output endpoints, NPZ time indices, analytical cardinal rays/parallax, site validation, interrupted-run resume, and fractional-hour interpolation).
- Horizons: 6 sites x 2 bodies x 121 samples = 1,452 comparisons, every 12 UTC hours from 2026-01-01 through 2026-03-02.
- Exported float32 maximum wrapped azimuth difference: 0.00044475140950339664 degrees.
- Exported float32 maximum elevation difference: 0.00003392945949176607 degrees. Both pass the card threshold of 0.01 degrees.
- Actual unchanged `web/js/core.js` repeats the 1,452 comparisons and passes; see `ephem_web_check.json`.
- Additional interpolation check: 240 seeded fractional hours over all five years, four synthetic height/site cases x two bodies. Maximum 3D separation from direct topocentric Skyfield: 0.00013176342594160888 degrees.
- Detailed per-site max/mean errors, query URLs, response hashes and Horizons API version: `ephem_validation.json`.

## Scope of this verification
Horizons reports DE441 and a high-precision MEAN_ME frame; the requested production files use DE440s and DE421 orientation. The comparison is independent but only covers the stated 60-day external-reference window. The five-year interpolation check is against Skyfield, not an independent five-year Horizons dataset. Azimuth is ill-conditioned near zenith/nadir, so interpolation uses 3D angular separation. Test heights are explicitly synthetic/zero, not measured terrain elevations. The Chang'e-4 paper coordinate is a validation point, not a choice for card 4 catalogue coordinates. Terrain horizons and PGDA validation remain separate work.

## Sources
- Skyfield planetary frames and lunar observers: https://rhodesmill.org/skyfield/planetary.html
- JPL Horizons API: https://ssd-api.jpl.nasa.gov/doc/horizons.html
- Individual kernels, coordinate sources and citations: `data/DATASETS.md`.
