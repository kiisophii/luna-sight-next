"""Render task B's complete evidence as a per-node CSV and concise Markdown."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KEYS=('sun_frac','earth_frac','both_frac','longest_dark_h')

def main():
    report=json.loads((ROOT/'docs/task_b_full_check.json').read_text())
    assert report['complete'] and report['n_sites']==17 and report['n_nodes']==2057
    expected={s['id'] for s in json.loads((ROOT/'web/data/sites.json').read_text()) if s['lat']>-75}
    assert {s['id'] for s in report['sites']}==expected
    assert {(p['id'],p['index']) for p in report['nodes']}=={(s,i) for s in expected for i in range(121)}
    code_hash=hashlib.sha256((ROOT/'pipeline/task_b_full_check.py').read_bytes()).hexdigest()
    for s in report['sites']:
        assert s['identity']['code_sha256']==code_hash
        assert s['identity']['record_sha256']==hashlib.sha256((ROOT/'web/data/uncertainty'/f"{s['id']}.json").read_bytes()).hexdigest()
        published=json.loads((ROOT/'web/data/uncertainty'/f"{s['id']}.json").read_text())
        original={Path(p['path']).name:p for p in published['provenance']['terrain_sources']}
        for source in s['identity']['sources']:
            if 'metadata' in source:
                meta=source['metadata']
                assert meta['frame']=='MOON_ME_DE421' and meta['res_ppd']==512 and meta['radius_km']==151
                assert meta['units']=='m above 1737.4 km sphere' and meta['id']==s['id']
            else:
                p=original[Path(source['path']).name]
                assert source['sha256']==p['sha256'] and source['label_sha256']==p['label_sha256']
    with (ROOT/'docs/task_b_nodes.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['id','index','e_m','n_m','lat','lon']+[f'{k}_{kind}' for k in KEYS for kind in ('published','independent','difference','unrounded_difference')]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for p in report['nodes']:
            row={k:p[k] for k in fields[:6]}
            for k in KEYS:
                for kind,source in [('published','published'),('independent','independent'),('difference','differences'),('unrounded_difference','unrounded_differences')]:row[f'{k}_{kind}']=p[source][k]
            writer.writerow(row)
    with (ROOT/'docs/task_b_ranges.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['id','radius_m','metric','statistic','published','independent','difference']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for s in report['sites']:
            for row in s['ranges']:writer.writerow(dict(id=s['id'],**row))
    controls=[p for s in report['sites'] for p in s['preflight']]
    max_angle=max(p['angle_max_abs_deg'] for p in controls)
    raw_dark=max(abs(p['unrounded_differences']['longest_dark_h']) for p in report['nodes'])
    range_max=max(abs(p['difference'])*100 for s in report['sites'] for p in s['ranges'] if p['metric']!='longest_dark_h')
    lines=['# Task B — full independent nonpolar coordinate-uncertainty check','',
        'Producer: Sua Kim. Checker: Jiyong Sung. Inputs: main `89a9af1`. No production data changed.','',
        f"**{report['n_sites']} sites / {report['n_nodes']:,} nodes / 1,020 radius statistics recomputed. Fraction failures: {len(report['failures'])}.**",'',
        '| Check | Measured result |','|---|---:|',
        f"| Maximum node fraction difference, matching production serialization | {report['max_fraction_abs_diff_pp']:.12g} pp |",
        f"| Maximum radius-statistic fraction difference | {range_max:.12g} pp |",
        f"| Maximum node fraction difference, unrounded independent horizons | {report['max_unrounded_fraction_abs_diff_pp']:.12g} pp |",
        f"| Longest-dark difference, production-rounded / unrounded | {report['max_dark_abs_diff_h']} / {raw_dark} h |",
        f'| GPU vs separate CPU PROJ/ECEF controls | {len(controls)} nodes; maximum {max_angle:.12g} degrees; all rounded metrics equal |',
        f"| Full-run wall time (includes source waits, initialization, controls and writing) | {report['elapsed_s']:.2f} s |",'',
        'Task B criterion: each Sun/Earth/both fraction and radius statistic within 1 percentage point. Longest darkness is also recomputed and every difference retained; task B gives no darkness pass threshold. CSV fraction differences are in fraction units (multiply by 100 for pp); darkness differences are hours.', '',
        '| Site | Nodes | Max Sun (pp) | Max Earth (pp) | Max both (pp) | Max dark (h) | Max unrounded fraction (pp) |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for s in report['sites']:
        rows=[p for p in report['nodes'] if p['id']==s['id']]
        delta=[max(abs(p['differences'][k]) for p in rows)*(100 if k!='longest_dark_h' else 1) for k in KEYS]
        lines.append(f"| {s['id']} | 121 | "+' | '.join(f'{x:.12g}' for x in delta)+f" | {s['max_unrounded_fraction_abs_diff_pp']:.12g} |")
    lines += ['', '## Independent method and scope','',
        '- No repository modules are imported by the verifier. It has its own SLDEM NPZ/PDS label reader, bilinear sampler, Cartesian great-circle directions, full horizon march and NumPy hourly visibility loop.',
        '- Every 11x11 grid is independently reconstructed with PROJ geodesics. All 720 azimuths and all 4,001 geometric distances (200 m to 300 km) are traced at every node without production early stopping. Observer height is 2 m; curvature is included.',
        '- SLDEM2015 is used to 150 km from each node, then LDEM_64 and LDEM_16. CHANDRAYAAN3 uses the global chain. Fresh 151 km source windows cover offset observers. Their download metadata, URLs, server validators and hashes are in the evidence. Global raster hashes match the published provenance. Fresh NPZ container hashes differ from producer containers, which contain acquisition metadata; this report does not claim byte-identical producer NPZ archives.',
        '- Source acquisition uses the existing fetch_global downloader only. The verifier does not call its reader or any production geometry. The same NASA source product is tested; this is not validation against the real lunar surface.',
        '- Independent hourly predicates over all 43,824 samples: solar centre on/above the horizon (equivalent to half of the solar disk visible), Earth centre strictly above; both is their conjunction. Longest darkness is a non-wrapping run of false hourly bins.',
        '- Both full-precision and production-serialized (4 decimal degree masks, 2 decimal metre ground) cases are retained. Production serialization is applied to independently computed values, never substituted from stored masks.',
        '- All min/max/p10/median/p90 statistics are recalculated for 100/300/500 m discs (5/29/81 nodes). All 121 nodes, including those outside the 500 m disc, are recomputed and compared.',
        '- GPU acceleration is CuPy FP64 array math. Centre and one corner at each site are additionally marched by a separate CPU PROJ/ECEF implementation. Two physical CPU cores are reserved; source/code/ephemeris/target hashes key each per-node checkpoint. Partial runs cannot overwrite the full evidence report.', '',
        '## Evidence and reproduction','',
        '- [Full evidence, inputs, preflights and all failures](task_b_full_check.json)',
        '- [All 2,057 node comparisons](task_b_nodes.csv)',
        '- [All 1,020 radius-statistic comparisons](task_b_ranges.csv)', '',
        '```powershell',
        'python -X utf8 pipeline/fetch_global.py --skip-global --radius-km 151 --workers 4',
        'python -X utf8 pipeline/task_b_full_check.py run --global-root <directory-with-original-LDEM64-and-LDEM16>',
        'python -X utf8 pipeline/task_b_report.py',
        'python -m pytest pipeline/tests/test_task_b_full_check.py -q',
        '```','',
        'GPU execution needs CuPy/CUDA; `--backend cpu` provides an independent NumPy full-march path. Raw sources and node checkpoints stay git-ignored. Source hashes identify exact execution bytes, including line endings.', '',
        'Sources: [NASA PDS SLDEM2015](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/), [NASA PDS LOLA global floats](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/), [NAIF kernel archive](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/), [project source register](../data/DATASETS.md), [contract section 18](data_contract.md).', '',
        'All numerical discrepancies, including those below tolerance, remain in the full CSV/JSON. No failed row is removed. Separate AI code review found one operational partial-report overwrite issue, fixed before the full run; human review remains TO CHECK in the SI log.']
    if report['failures']:lines+=['','## Failures','',json.dumps(report['failures'],indent=2)]
    (ROOT/'docs/task_b_full_check.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Full report and CSVs written; nodes',len(report['nodes']),'controls',len(controls),'range max pp',range_max)

if __name__=='__main__':main()
