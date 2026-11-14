"""Validate the actual saved 18.6-year product; preserve all production bytes."""
from datetime import datetime, timedelta, timezone
import json

import numpy as np

from ephem import ROOT, COLUMNS, EPOCH, Ephemeris, digest, write_json, generate


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--generate-if-missing', action='store_true',
                    help='Create only the ignored validation NPZ if absent; never regenerate the web binary')
    args = ap.parse_args()
    file = ROOT / 'data/processed/ephem_2020-2038_2h.npz'
    if not file.exists() and args.generate_if_missing:
        engine = Ephemeris()
        generate(engine, datetime(2020, 1, 1, tzinfo=timezone.utc),
                 datetime(2038, 8, 1, tzinfo=timezone.utc), 2, file, engine.manifest())
    binary = ROOT / 'web/data/ephem.bin'
    before = {str(p.relative_to(ROOT)): digest(p) for p in [file, binary, ROOT / 'web/data/ephem.json']}
    with np.load(file, allow_pickle=False) as product:
        assert set(product.files) == {'vectors', 'hour_index', 'start', 'stop_exclusive', 'step_h', 'frame', 'units', 'columns'}
        v, hours = product['vectors'], product['hour_index']
        assert v.shape == (81444, 6) and v.dtype == np.dtype('<f4') and np.isfinite(v).all()
        assert hours.shape == (81444,) and hours[0] == -52608 and hours[-1] == 110278
        assert np.all(np.diff(hours) == 2)
        assert str(product['frame']) == 'MOON_ME_DE421' and str(product['units']) == 'km'
        assert str(product['start']) == '2020-01-01T00:00:00Z'
        assert str(product['stop_exclusive']) == '2038-08-01T00:00:00Z'
        assert int(product['step_h']) == 2 and product['columns'].tolist() == COLUMNS
        production = np.fromfile(binary, dtype='<f4').reshape(-1, 6)
        overlap = (hours >= 0) & (hours < len(production))
        assert np.array_equal(v[overlap], production[hours[overlap]])
        sample = np.array([0, 1, len(v) // 2, len(v) - 2, len(v) - 1])
        engine = Ephemeris()
        dates = [EPOCH + timedelta(hours=int(h)) for h in hours[sample]]
        exact = engine.vectors(dates).astype('<f4')
        assert np.array_equal(v[sample], exact)
        report = dict(generated_utc=datetime.now(timezone.utc).isoformat(), passed=True,
                      file='data/processed/ephem_2020-2038_2h.npz', sha256=digest(file), bytes=file.stat().st_size,
                      shape=list(v.shape), dtype='little-endian float32', frame='MOON_ME_DE421', columns=COLUMNS,
                      start=str(product['start']), stop_exclusive=str(product['stop_exclusive']), step_h=2,
                      overlap_rows_compared=int(overlap.sum()), overlap_float32_mismatches=0,
                      engine_sample_indices=sample.tolist(), engine_sample_float32_mismatches=0,
                      note='Reused existing generated file; all time/schema/finite checks and every overlapping 2026-2030 row checked. Only five rows independently recomputed with the same Skyfield engine; not complete external 18.6-year validation.')
    after = {str(p.relative_to(ROOT)): digest(p) for p in [file, binary, ROOT / 'web/data/ephem.json']}
    assert before == after
    report['production_and_npz_unchanged'] = True
    report['input_hashes'] = before
    write_json(ROOT / 'docs/card10_npz_check.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
