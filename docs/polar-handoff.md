# Card 2 handoff — Jiyong

Status: phase-1 implementation and verification complete for the permitted
three-placeholder scope; ready for integration review. Team acceptance wording
is an open discussion, not a reason to alter source elevations.

## Delivered

- `pipeline/fetch_polar.py`: partial HTTP Range downloads, persistent block
  resume, six resolutions, source/CRS checks, atomic NPZ terrain caches.
- Three synthetic test sites × six full-radius windows downloaded successfully.
  Repeating all 18 reused the caches without additional terrain payload bytes.
- 11 offline tests passed; independent review completed; GDAL reproduced
  30 sampled pixel values and their georeferencing.
- Source-backed Shackleton Rim region-center check completed.
- The 240 m discrepancy was traced to resolution/averaging, with fresh source
  bytes, independent interpolation and 1,728 area-matched cells checked.
- Sources, commands, cache schema, measurements and SI usage are documented.
  Human SI check fields remain `TO CHECK`.

No source DEM was shifted or downsampled for production use. The 240 m averaging
experiment is diagnostic only; the original 5 m cache retains its full resolution.
Web display zoom/level-of-detail switching and phase-2 horizon calculations are
not part of this delivered downloader.

## Reproduce from a fresh checkout

Run in the repository root:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r pipeline/requirements-polar.txt
.venv/Scripts/python -m pytest pipeline/tests/test_fetch_polar.py -q
.venv/Scripts/python pipeline/fetch_polar.py --sites pipeline/tests/fixtures/polar_sites.json
.venv/Scripts/python pipeline/verify_polar.py --site TEST_POLAR_1
.venv/Scripts/python pipeline/check_polar_landmark.py
.venv/Scripts/python pipeline/diagnose_polar_resolution.py --fresh
.venv/Scripts/python pipeline/check_contract.py
```

Repeat the same fetch command to verify cache reuse. The fixture is synthetic,
not an authoritative landing-site catalog. For the team catalog, omit `--sites`:
the program reads `web/data/sites.json`, and warns when selected entries are mock.
Downloads require network access and local disk space; see [polar.md](polar.md)
for dependencies and the Windows sparse-file requirement for independent checks.

Local raw caches: `data/raw/polar/`; machine-readable reports:
`data/processed/polar_verification.json`, `polar_landmark.json`, and
`polar_resolution_diagnosis.json`. These are intentionally excluded from Git.
The report documents below preserve reviewable results in the repository.

## Open team discussion: resolution-specific validation

**Question:** Should the card's blanket “heights agree within a few metres”
wording apply to different-resolution point samples, or should validation depend
on the intended use and distinguish data integrity from terrain resolution?

Evidence: the original pointwise difference is 8.988411 m. Comparing the same
240 m footprints reduces the discrepancy at that point to 0.121970 m for the
5 m mosaic. Original source bytes, coordinates and interpolation are correct in
the tested path. [Full diagnosis](polar-resolution-diagnosis.md).

Proposed discussion points (not adopted project policy):

1. Data integrity: source-byte/value consistency, correct coordinates/units,
   nodata and coverage handling, and interruption recovery.
2. Cross-resolution diagnostics: report pointwise differences; optionally use
   same-footprint comparisons to identify processing mistakes. Do not force
   different-resolution elevations to agree or replace fine data with averages.
3. Fitness for use: broad-view rendering and horizon calculations need different
   checks. For phase-2 calculations, assess the effect of coarse terrain on
   occlusion and retain fine terrain near the observer, including lunar curvature.

Jiyong requested that this topic remain for team discussion while phase-1 work
is handed off. The original card and shared data contract have not been rewritten.
There is no claim that a revised criterion has been approved by the team.

## Integration and follow-up

- Sua reviews and merges PR #1; no automatic merge is requested.
- A human fills in the SI verification fields.
- Once the card 4 source-backed catalog is integrated, rerun for its actual sites;
  handle out-of-coverage high-resolution requests explicitly and review results.
  Current placeholder success does not establish actual landing-site accuracy.
- Record the team's decision on the discussion above, then apply the agreed
  criteria to the next run and phase-2 work.

References: [download guide](polar.md), [validation](polar-validation.md),
[resolution diagnosis](polar-resolution-diagnosis.md), [sources](../data/DATASETS.md).
