"""Write the non-polar section of docs/coordinate_uncertainty.md from web/data/uncertainty/*.json.

Only the block between the NON-POLAR markers is replaced, so the south-polar part can live
in the same file. Rows are sorted by the 300 m Sun-fraction range (largest first).

    python pipeline/coord_uncertainty_doc.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs' / 'coordinate_uncertainty.md'
BEGIN, END = '<!-- NON-POLAR BEGIN -->', '<!-- NON-POLAR END -->'
HEAD = """# Coordinate uncertainty (card 23)

"If the landing-site coordinate is off by r metres, how much can the numbers change?"
Each catalogue site gets 121 nodes (11 × 11, 100 m spacing, ±500 m). For a radius r the
nodes with hypot(east, north) ≤ r are used (100 m: 5, 300 m: 29, 500 m: 81 nodes).
Format: `docs/data_contract.md` section 18. Values are 2026-01-01 … 2030-12-31 hourly,
computed with the actual `web/js/core.js`. Nodes are point samples on the same DEM; DEM
height errors are not included.

"""


def pp(x):
    return f'{100 * x:.1f}'


def section(rows):
    out = [BEGIN, '## Non-polar sites (lat > −75°, Sua, `pipeline/coord_uncertainty.py`)', '',
           'Chain = production card 9 horizons (SLDEM2015 59 m to 150 km, LDEM_64/LDEM_16 to 300 km; '
           'CHANDRAYAAN3 LDEM_64/16), 0.2 km start, 4000 steps, 720 azimuths, 2 m observer. '
           'Centre node = `web/data/metrics/<ID>.json` exactly.', '',
           '| Site | lat | Sun % centre | Sun % ±300 m (min–max) | Δ300 (pp) | Sun % ±500 m | Earth % ±300 m | Both % ±300 m | Longest dark h ±300 m |',
           '|---|---|---|---|---|---|---|---|---|']
    for u in rows:
        c = u['nodes'][60]
        r3, r5 = u['ranges']['300'], u['ranges']['500']
        s3 = r3['sun_frac']
        out.append(f"| {u['id']} | {u['center']['lat']:.2f} | {pp(c['sun_frac'])} | "
                   f"{pp(s3['min'])}–{pp(s3['max'])} | {pp(s3['max'] - s3['min'])} | "
                   f"{pp(r5['sun_frac']['min'])}–{pp(r5['sun_frac']['max'])} | "
                   f"{pp(r3['earth_frac']['min'])}–{pp(r3['earth_frac']['max'])} | "
                   f"{pp(r3['both_frac']['min'])}–{pp(r3['both_frac']['max'])} | "
                   f"{r3['longest_dark_h']['min']}–{r3['longest_dark_h']['max']} (centre {c['longest_dark_h']}) |")
    out += ['', 'Independent check: `python pipeline/verify_coord_uncertainty.py` → '
            '`docs/coord_uncertainty_validation.json` (VALIDATION.md row 19).', END]
    return '\n'.join(out)


def main():
    files = sorted((ROOT / 'web/data/uncertainty').glob('*.json'))
    rows = [json.loads(p.read_text(encoding='utf-8')) for p in files]
    rows = [u for u in rows if u['center']['lat'] > -75]
    rows.sort(key=lambda u: -(u['ranges']['300']['sun_frac']['max'] - u['ranges']['300']['sun_frac']['min']))
    text = DOC.read_text(encoding='utf-8') if DOC.exists() else HEAD
    block = section(rows)
    if BEGIN in text and END in text:
        text = text[:text.index(BEGIN)] + block + text[text.index(END) + len(END):]
    else:
        text = text.rstrip('\n') + '\n\n' + block + '\n'
    DOC.write_text(text, encoding='utf-8')
    print(f'{DOC.relative_to(ROOT)}: {len(rows)} non-polar rows')


if __name__ == '__main__':
    main()
