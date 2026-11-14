# Reproduce Card 18

Run from the repository root using the project Python environment and Node. Production uses 12 CPU workers; lower `--jobs` if needed. Raw data and checkpoints are deliberately not in Git.

## Terrain prerequisites

Reuse the original LOLA LDEM_64 and LDEM_16 `.img`/`.lbl` pairs under `data/processed/card18/raw/global/` (a local junction to `data/raw/global/` is sufficient). Source URLs and acquisition methods are in [DATASETS](../data/DATASETS.md) and the Card 13 documentation. The existing polar HTTP block cache can also be reused through `data/processed/card18/raw/polar/_blocks`; it is not necessary to download a full TIFF.

The following Python snippet creates the expanded polar windows using the existing resumable fetcher. Save it to a local file at the repository root and run it. It records genuine absent 5 m coverage; do not hand-mark failed downloads as unavailable. The production run used six independent resolution workers to run these loops concurrently; this sequential version has the same input contract and avoids concurrent writers for one source URL.

```python
import json
import sys
from pathlib import Path
sys.path.insert(0, 'pipeline')
import fetch_polar as fetcher
from local_maps import IDS, GATES

work = Path('data/processed/card18')
work.mkdir(parents=True, exist_ok=True)
sites = json.loads(Path('web/data/sites.json').read_text(encoding='utf-8'))
for resolution, gate_km in GATES.items():
    rows = []
    for sid in IDS:
        site = next(s for s in sites if s['id'] == sid)
        try:
            fetcher.fetch(site, resolution, (gate_km + 16) * 1000,
                          work / 'raw/polar', allow_partial=True)
            status = 'ok'
        except fetcher.SourceCoverageError:
            if resolution != 5:
                raise
            status = 'outside_source_coverage'
        rows.append(dict(id=sid, res_m=resolution, status=status))
        (work / f'download_{resolution}.json').write_text(
            json.dumps(dict(rows=rows)), encoding='utf-8')
```

Storage radii are 19/41/41/76/76/216 km for 5/10/20/60/80/240 m rasters. The analysis still gates them at 3/25/25/60/60/200 km from each observer. Malapert has no 5 m overlap; Haworth includes both 5 m and 10 m ground samples. No source is extrapolated.

## Compute and inspect

```text
python pipeline/local_maps.py --jobs 12
python pipeline/local_impact.py --locations
python pipeline/plot_local_maps.py
python pipeline/local_impact.py --relay
python pipeline/verify_card18_local.py
python pipeline/check_contract.py
python -m pytest pipeline -q
```

The relay report requires matching Card 13 `data/processed/relay/<ID>/` visibility checkpoints. Public `docs/relay_impact.json` retains exact single-tower timelines and input hashes so the published counts/outages can also be audited without those raw checkpoints.

Re-run `local_maps.py` after interruption. Valid points resume by source/code/ephemeris/parameter fingerprints; incomplete points are recalculated and no incomplete public map is exported. A completed map contains 441 ordered nodes; six maps contain 2,646. `--limit` is for a benchmark and never publishes a partial map.

Independent validation uses seed 20261114 to select five nodes uniformly without replacement, independently traces all 720 azimuths at all 8,001 distances, and evaluates all 43,824 hours. Each fraction must differ by at most 1 percentage point. Longest-darkness differences are reported separately. This checks implementation consistency against the same terrain, not absolute physical accuracy.

Measured timing is in [card18_runtime.json](card18_runtime.json). Download, coding, and compute phases overlap; their durations must not be summed into total elapsed time.
