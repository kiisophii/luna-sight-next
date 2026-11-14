# Card 13 — relay towers across the 33-site catalogue

Owner: Jiyong. Computation date: 2026-11-14. Status: computation and independent checks in progress.

This analysis compares geometric direct-to-Earth visibility with a fixed-height single tower
and a greedy network of up to three towers. It does not guarantee a radio service, an available
Earth station, or the structural feasibility of a tower.

## Method and changes

- Real 2026–2030 MOON_ME ephemeris: 43,824 hourly samples; the lander antenna is 2 m above terrain.
- Per site: 5,025 candidate positions on a 250 m lattice within 10 km; heights 5, 15, 30 and 50 m.
- Tower horizons: 720 bins at 0.5°, marching 5 m to 300 km on 8,001 logarithmic distances with lunar curvature.
- Local paths: interior samples at most 5 m apart; first-Fresnel clearance for S=2.2 GHz and Ka=26 GHz.
- The default link rule remains geometric LOS. Fresnel clearance is reported separately; geometric link fractions do not enforce the 60% Fresnel rule unless that rule is explicitly selected.
- Candidate slope is a 250 m plane fit, screened at 15°. Sunlight uses the existing solar-disk definition.
- Corrected off-centre DEM selection, removed the arbitrary high-Earth clear-sky shortcut, rejected missing terrain, and invalidated resumes when terrain file identity or ephemeris content changes.
- Optional height curves and 15×15 km Artemis coverage grids preserve existing contract fields. See [contract section 12](data_contract.md#121-optional-card-13-additions-2026-11-14-jiyong).
- Network records now retain clearance to the actual parent tower in addition to the existing lander-path fields.

## Results

Measured height, coverage, sensitivity, independent-check and runtime tables will be filled after computation.

## Resolution sensitivity

The 80 m and 240 m cases replace only terrain within 3 km of the lander. The selected single
tower positions remain fixed and the far field remains unchanged. Each antenna stays its stated
height above the variant terrain. This isolates resolution effects; it does not rerank candidates
or re-optimise a network. Differences are sensitivity measurements, not errors against ground truth.
No adjustment forces the coarse and fine DEMs to agree.

## Independent verification

The verifier imports no production geometry. It uses PROJ geodesics and independent 3D rays,
reads the original DEMs, and checks IM2, Apollo 17 and Apollo 11 at 15 m. It compares the entire
window using the same distance sampling and separately traces 30 reproducible hourly epochs
with an additional 2.5 m radial grid. Local LOS/Fresnel paths are sampled at 1 m. Same-position
best towers are explicitly degenerate; a non-coincident candidate is checked as well.

The criterion is ≤1 percentage point for matching fractions and no more than 1% mismatched
states in the 30 samples (therefore zero mismatches for 30 samples). Thirty samples alone cannot
establish a statistical 1% error bound. This is implementation and sampling verification against
the same DEMs, not verification of the Moon's true terrain. Passing three sites does not establish a universal 1%p truth-error bound for the entire catalogue.

## Reproduce

```powershell
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:NUMBA_NUM_THREADS='1'
python pipeline/fetch_global.py --skip-global --workers 2
python pipeline/run_relay.py --jobs 4
python pipeline/card13_relay.py --output docs/card13_sensitivity.json
python pipeline/verify_card13_relay.py --output docs/card13_independent.json
python pipeline/check_contract.py
python -m pytest -q
```

Use the existing `.venv\Scripts\python.exe` if Python packages are not installed globally.
The run resumes per candidate; raw data and checkpoints remain git-ignored. For a full test run,
the existing ephemeris generation workflow must also supply `data/processed/ephem_2020-2038_2h.npz`.

## Sources and limits

- [PGDA LOLA terrain](https://pgda.gsfc.nasa.gov/products/90), [SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), and [LOLA global grids](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/). Exact available resolutions are retained in each result's `dem_sources`.
- [NAIF kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/) and the repository's existing ephemeris provenance.
- [NASA BEACON concept](https://ntrs.nasa.gov/citations/20240014584) motivates the 15 m / approximately 10 km scenario. Other heights, frequency and budget parameters are modelling choices, not BEACON specifications.
- Terrain inside the 5 m horizon cutoff and features missed by the 0.5° azimuth sampling are not resolved by this model.
- DEM resolution is not a promise of vertical accuracy. A 5 m path sampling interval does not create 5 m terrain where only a coarser DEM exists.
- Coverage areas count 250 m cells in a local map; they are approximate represented areas and not precise terrain surface areas.
- Greedy selection can miss a zero-immediate-gain bridge and is not a proof of optimality. Construction, RF interference, terrain below DEM resolution, and Earth-station schedules are outside this calculation.
- Shackleton's coordinate correction is a card-15 dependency; its status will be recorded at final verification.
