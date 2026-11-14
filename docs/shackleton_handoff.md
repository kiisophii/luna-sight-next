# Card 15: Shackleton rim coordinate correction

Base main: ef2b2dad9e768af79e88f97b9c43ad35a8623de3.

## Point and evidence

Keep ID SHACKLETON_RIM. Replace the old regional polygon centre (-89.7668, -171.87) by latitude -89.6866 and east-positive longitude -162.81. Name: Shackleton Rim (S). Terrain elev_m remains null; no measured height is invented.

Primary source: Glaser et al., *Illumination Conditions at the Lunar Poles: Implications for Future Exploration*, DOI 10.1016/j.pss.2017.07.006, NASA NTRS 20170007365:

- Record: https://ntrs.nasa.gov/citations/20170007365
- Accessible accepted manuscript: https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf
- Table 2, printed p.12 (PDF page 12), FIRST row labelled Shackleton, S: -89.6866 latitude, 197.19 east longitude. Contract conversion: 197.19 - 360 = -162.81. Do not use the second S row, which is a different study point.
- Section 3 identifies the Shackleton area on the crater rim; the discussion of clusters S0/S1/S2 and Figure 6c place the study locations on that rim. Table 2 uses an observer 2 m above ground, consistent with the app observer convention.

This is a published rim sample, not a surveyed summit, official future touchdown decision or claim of metre-level accuracy. Source coordinates are preserved at their published precision. The exact MOON_ME_DE421 datum is still UNVERIFIED in the inspected paper; no transformation was invented.

The old R04 value was faithfully transcribed from a named regional polygon centre in the NASA data book. The new point is intentionally a different sample. The stage-3 assignment reports sun_frac about 0.087 at the old point; that is not evidence that the old transcription was incorrect or that the geometry engine is faulty. The replacement is chosen from published rim coordinates, not selected by changing the point until our metric becomes large. No new illumination fraction has been computed in this coordinate task. The paper's study window and illumination definitions differ from ours; do not copy its percentages into app caches.

## Cache invalidation in this PR

The old SHACKLETON_RIM horizon, metrics and relay files describe the old coordinate and are removed. The horizon and relay index entries are removed; the relay index explicitly lists this point as pending terrain after coordinate correction. The Danuri cache row for SHACKLETON_RIM is replaced with the new coordinates and status pending_terrain, without old pass statistics. Other sites' data are preserved. This prevents the unchanged app from presenting the old cached results under the new coordinates. The interim flat/pending horizon is an app placeholder, not measured terrain or a new visibility result.

Historical validation, Horizons and provenance reports retain their original coordinates. They remain records of those original calculations; their SHACKLETON_RIM rows must not be relabelled as validation of this new point. Previously published aggregates and named-point validation need fresh owner runs.

## Handoff order (no merge or teammate messaging performed)

1. Integrator reviews and merges this coordinate PR.
2. Jiyong (card 13): refetch or check that polar DEM windows cover the new coordinates; never reuse an old per-ID window merely because the filename matches. Recompute this site's real horizon and relay products, including requested sensitivity, then restore their index entries. Check horizon/relay embedded lat/lon equals (-89.6866, -162.81) and inspect local rim topography. Actual height must come from DEM above the 1737.4 km sphere.
3. Regenerate this site's 2026-2030 metric cache from the new horizon using the current team's metrics runner/core.js. Clear the old per-site provenance/checkpoint before resuming if it does not hash coordinates. Do not copy the old 0.087 fraction.
4. Dongju (cards 11/16): rerun named-site PGDA checks at the NEW coordinate, including required local spread fields and Korea-link checks that depend on the site's horizon. Update validation reports/provenance and the team validation table. Keep the historic old-point reports clearly scoped.
5. Integrator checks the app shows the new position and only the recomputed results; this task does not claim a new terrain-based numerical PASS.

Typical horizon/relay commands (check current owner CLI options first):

```sh
python pipeline/run_horizons.py --site SHACKLETON_RIM --force
python pipeline/run_relay.py --site SHACKLETON_RIM --force
```

## Human source check

Use docs/source_link_checklist.md. Every human cell remains TO CHECK. AI source access is separate from the required human visual review. Confirmed broken links should become Issues with the original URL and affected locations; a transient access block alone does not establish breakage.

## Implementation checks

The rebuilt catalogue and source audit each change only SHACKLETON_RIM; the other 32 entries are identical. The Danuri JSON changes only this site's row, leaving all other 33 rows unchanged. All catalogue elevations remain null. The source inventory covers 65 unique URLs and all 33 source_url references. Rebuilding the catalogue/checklist is repeatable.

The current check_contract.py passes with 0 errors on the full sites/ephemeris/horizon/metrics/validation/relay/Korea JSON snapshot after this change. Warnings in the local verification copy are the intentionally pending Shackleton horizon and omitted unrelated hterrain tile files; this PR does not modify or validate those global height tiles. No DEM or illumination recalculation is claimed.
