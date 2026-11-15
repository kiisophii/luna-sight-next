"""Render the task D evidence without recomputing or changing production data."""
import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs'


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main():
    result = json.loads((DOC / 'task_d_check.json').read_text(encoding='utf-8'))
    samples = result['samples']
    # Refuse success prose if a later run reports incomplete or failed evidence.
    assert result['complete'] and len(samples) == 160
    assert all(s['encoded_equal'] and s['passes'] for s in samples)
    assert max(abs(s['diff_m']) for s in samples) <= .25
    inv = result['inventory']
    assert not any(inv[k] for k in ('missing', 'bad', 'constants', 'seam_failures'))
    assert inv['indexed_tiles'] == 3294 and inv['decoded_target_tiles'] == 1638
    assert inv['seams_checked'] == 2549 and inv['seam_max_m'] == 0
    assert len(result['sources']) == 34
    assert len(result['albedo']['records']) == 2
    assert all(a['reencoded_byte_equal'] and a['reencoded_pixel_max_diff'] == 0
               and all(v > a['orientation_mae']['correct'] for k, v in a['orientation_mae'].items() if k != 'correct')
               for a in result['albedo']['records'])
    write_csv(DOC / 'task_d_vertices.csv', samples)
    windows = []
    for source in result['sources']:
        origin = source.get('original', {})
        metadata = source['metadata']
        windows.append(dict(name=source['name'], shape=str(origin.get('shape', source.get('shape'))),
            x0_m=origin.get('x0_m', ''), y0_m=origin.get('y0_m', ''),
            lat0=source.get('lat0', ''), lon0=source.get('lon0', ''),
            crop_row=source['crop_row'], crop_col=source['crop_col'],
            source_url=origin.get('source_url', '; '.join(metadata.get('tiles', []))),
            cache_sha256=source['cache_sha256']))
    write_csv(DOC / 'task_d_windows.csv', windows)
    lines = ['# Task D — independent fine globe terrain and albedo checks', '',
        'Checker: Jiyong Sung, OpenAI Codex-assisted; 2026-11-15. Production author: Sua Kim.',
        'Reference main: `8fd119b`; latest-main integration `3086143` does not change these globe inputs.', '',
        '**Result:** all 160 sampled vertices equal the independently predicted encoded height. '
        'Largest difference from the unquantized reference is '
        f"**{max(abs(s['diff_m']) for s in samples):.9f} m**, within the 0.5 m encoding step "
        '(and its 0.25 m half-step). This verifies encoding/resampling, not absolute lunar elevation accuracy.', '',
        '## Terrain samples', '',
        '| Region | Zoom | Random + catalogue controls | Mean absolute difference (m) | Median (m) | Max (m) | Encoded equality |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for kind, levels in [('band', range(4, 8)), ('south', range(3, 7))]:
        for zoom in levels:
            group = [s for s in samples if s['kind'] == kind and s['z'] == zoom]
            diff = np.array([abs(s['diff_m']) for s in group])
            lines.append(f'| {kind} | {zoom} | 10 + 10 | {diff.mean():.9f} | {np.median(diff):.9f} | {diff.max():.9f} | {sum(s["encoded_equal"] for s in group)}/20 |')
    counts = Counter('PGDA' if s['source'].startswith('polar') else 'SLDEM2015' if s['source'].startswith('sldem') else 'LDEM_64' for s in samples)
    inv = result['inventory']
    lines += ['', f'Seed `{result["seed"]}`. Source counts: {dict(counts)}. '
        'Band z4 random samples all fall on LDEM_64; the ten additional catalogue controls at that level cover SLDEM. '
        'No fallback samples were removed. All coordinates, signed differences and source choices: '
        '[160 vertices](task_d_vertices.csv). All 34 reconstructed windows: [window origins](task_d_windows.csv).', '',
        '## Full inventory and same-zoom shared vertices', '',
        f'- All **{inv["indexed_tiles"]:,}** indexed files exist.',
        f'- All **{inv["decoded_target_tiles"]:,}** requested-level PNGs decode as RGB 259 × 259, with zero blue channel; no constant tile.',
        f'- **{inv["seams_checked"]:,}** adjacent same-zoom shared-vertex edges: maximum difference **{inv["seam_max_m"]:.1f} m**, no failures. '
        'Includes four band z4 longitude-wrap edges (x79 → x0, y24–27).',
        '- Full failure lists and per-tile SHA256 are retained in [machine-readable evidence](task_d_check.json).', '',
        'Scope: file existence is checked for every indexed zoom. Height samples and PNG integrity/seams cover only '
        'band z4–z7 and south z3–z6. Normal-calculation border pixels, different-zoom joins, band–cap joins, '
        'browser rendering and south z7/z8 geometry are not checked here. No universal claim that the rendered globe has no gaps.', '',
        '## Albedo', '',
        'Original: [NASA SVS CGI Moon Kit](https://svs.gsfc.nasa.gov/4720), '
        '[8192 × 4096 TIFF](https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif). '
        'Credit: NASA’s Scientific Visualization Studio. Compare every RGB channel, then independently replay '
        'LANCZOS resize (2k only) and JPEG quality 88 with optimization.', '',
        '| Texture | TIFF/resize MAE (DN) | RMSE (DN) | Max (DN) | PSNR (dB) | Re-encoded bytes |',
        '|---|---:|---:|---:|---:|---|']
    for a in result['albedo']['records']:
        lines.append(f'| {Path(a["file"]).name} | {a["mae_dn"]:.6f} | {a["rmse_dn"]:.6f} | {a["max_abs_dn"]} | {a["psnr_db"]:.6f} | {"identical" if a["reencoded_byte_equal"] else "different"} |')
    lines += ['', 'Both full-image JPEG replays are byte-identical. The correct orientation has smaller strided MAE than '
        'latitude/longitude flips or a 180° shift (all scores in JSON). TIFF-to-JPEG differences are lossy display '
        'compression, not DEM height error. No independent landmark registration or photometric calibration was performed.', '',
        '## Independent method and provenance', '',
        'The checker imports no production builder, sampler or verifier. It reads original native DEM pixels from '
        'cached NASA sources, reconstructs the published original window origins, calculates vertices with PROJ, '
        'computes local hierarchical box means, bilinearly samples in source-priority order, and decodes PNG RG heights '
        'as `(256*R+G)/2-10000` m. Each pyramid level rounds to float32; final encoding uses float32 and nearest integer, '
        'matching the documented storage operations. Source geometry, window phase and production conventions are shared '
        'by design; the numerical implementation is separate.', '',
        'The [18 polar origins](globe_south_window_origins.json) identify 20/60/80 m PGDA windows. Expanded caches are '
        'cropped at integer native-pixel offsets, with spacing, shape, frame, radius and source URL assertions. '
        'SLDEM windows are reconstructed from the 62 km spherical bounds plus two native pixels at 512 ppd. '
        'Global fallback reads native LDEM_64 (km converted to m). Raw-cache, input-code, index, source-TIFF and tile '
        'SHA256 hashes are in the JSON; execution-byte hashes may differ on a checkout with different line endings. '
        'Existing HTTP readers are used only to acquire raw NASA data, not to evaluate terrain.', '',
        'Sources: [PGDA product 90](https://pgda.gsfc.nasa.gov/products/90), '
        '[SLDEM2015 float tiles](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), '
        '[LOLA global float grids](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/). '
        'Exact individual URLs and original-cache metadata are preserved in the JSON. Raw rasters stay ignored.', '',
        '## Reproduction and validation', '',
        'Requires Python, NumPy, Pillow, pyproj and pytest (requests/tifffile for raw acquisition). Run from the repository root. Existing raw caches: '
        '`data/processed/local250/raw/polar` (expanded PGDA), `data/raw/sldem` (151 km windows, 16 sites at abs(lat)<60), '
        '`data/processed/local250/raw/global/ldem_64_float.img`. Use checker flags `--polar-root`, `--sldem-root`, '
        '`--ldem64` to point to equivalent native caches. Missing 80 m cap and 60 m CHANDRAYAAN3 windows fall back to '
        '`data/processed/task_d/raw/polar`. Acquisition commands are below; original, larger caches may be reused.', '',
        '```powershell',
        'python pipeline/fetch_polar.py --res 20 --radius-m 41000 --output data/processed/local250/raw/polar --skip-unavailable',
        'python pipeline/fetch_polar.py --res 60 --radius-m 76000 --output data/processed/local250/raw/polar --skip-unavailable',
        'python pipeline/fetch_global.py --skip-global --radius-km 151 --workers 4',
        'python -c "import json; from pathlib import Path; p=Path(\'data/processed/task_d\'); p.mkdir(parents=True,exist_ok=True); (p/\'cap_site.json\').write_text(json.dumps([dict(id=\'SOUTH_CAP_80S\',lat=-90.,lon=0.)]))"',
        'python pipeline/fetch_polar.py --sites data/processed/task_d/cap_site.json --res 80 --radius-m 300000 --output data/processed/task_d/raw/polar',
        'python -c "import json; from pathlib import Path; from pipeline.fetch_polar import fetch; s=next(s for s in json.loads(Path(\'web/data/sites.json\').read_text(encoding=\'utf-8\')) if s[\'id\']==\'CHANDRAYAAN3\'); fetch(s,60,63000,Path(\'data/processed/task_d/raw/polar\'))"',
        'curl.exe -L --fail -C - -o data/processed/task_d/lroc_color_poles_8k.tif https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif',
        'python -m pytest pipeline/tests/test_task_d.py -q',
        'python pipeline/task_d_check.py',
        'python pipeline/task_d_report.py',
        'python pipeline/verify_ledger.py',
        '```', '',
        'Fetch LDEM_64 from the linked float-grid archive if absent; keep the original little-endian float32 IMG '
        '(11520 × 23040). Acquisition uses resumable HTTP blocks. The checker checkpoints its sample plan and '
        'completed sample rows, but reruns this short audit rather than skipping existing samples.', '',
        f'Final full-check computation: **{result["runtime_s"]:.2f} seconds** on Jiyong’s desktop; excludes downloads, '
        'development/review, and the final LDEM64 hash/output serialization. Four focused tests pass. '
        'A fresh AI review identified the missing dateline-wrap audit; a failing synthetic seam test reproduced it, '
        'then the fix passed and the full check was rerun (2,549 edges). No production data or browser code changed.']
    (DOC / 'task_d_check.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
