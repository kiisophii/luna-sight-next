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

## Independent review supplied by user (2026-11-14)
The user reported independent review of commit d89c42a065eea5d478f4e03b56e15585c02635b6: 1,452 fresh Horizons observations passed 0.01 degrees (maximum azimuth 0.000444751 degrees; elevation 0.000033929 degrees), and full 43,824-row regeneration had zero float32 mismatches. These are user-supplied independent results, separate from the author's original cached comparisons. No required correction was found. The optional practice goal of 0.0001 degrees was NOT met in maximum azimuth.

The exported az_el geometry is an approximation: subtract the observer position from a Moon-center apparent vector. It passed the stated direct observer comparison; it is not an exact topocentric apparent calculation. South pole and Shackleton coordinates are representative validation points with zero terrain elevation and a 2 m observer, not measured terrain-height validations.

The independent review did not check the saved 18.6-year NPZ, interrupted generation/resume, fractional interpolation or real-browser core.js. The following author follow-up checks cover those items without changing the production implementation or regenerating production data; they do not expand the independent review's scope.

## Supplemental checks (implementation assistant, 2026-11-14)
See ephem_followup_check.json for exact hashes and results.
- Actual saved 18.6-year NPZ: 81,444 x 6 float32, exact metadata and regular two-hour indices, all rows finite. Five rows including both ends were recomputed and matched exactly. This is not complete 18.6-year numerical revalidation.
- Actual Skyfield interruption/resume: a disposable 12-hour fixture stopped after three flushed rows and resumed at hour 3, computing only nine more rows. All 12 rows matched the existing production binary. This controlled exception does not simulate power loss, OS termination or interrupted network downloads.
- Fractional interpolation: the 240 seeded fractional hours across five years, four site/height cases and two bodies passed the 0.01-degree 3D angular criterion; maximum separation 0.00013176342594160888 degrees. Reference is direct topocentric Skyfield, not independent Horizons; heights are synthetic.
- Actual Chrome 158 executed unchanged web/js/core.js, loaded 43,824 rows with mock=false ephemeris metadata, and passed 1,452 cached Horizons comparisons: maximum azimuth 0.00044475140953181835 degrees, elevation 0.00003392945949221016 degrees. These reuse original cached queries, not the independent review's fresh requests. Terrain and other mock app data are outside this ephemeris check.
- Production ephem.bin and ephem.json SHA-256 hashes were identical before and after follow-up. No precision change or production data regeneration was performed.

Reproduce supplemental checks with existing kernels, NPZ and Horizons cache:

```sh
python pipeline/check_ephem_remaining.py
python pipeline/check_ephem_remaining.py --serve
# Open http://127.0.0.1:8765/tmp/ephem-browser.html and read PASS/JSON.
```

The script writes the numerical report and prepares the browser harness. A rerun resets browser status to pending; record the actual browser result separately. The server binds only to localhost and sets an explicit JavaScript MIME type for Windows.
