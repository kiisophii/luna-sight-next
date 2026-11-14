"""Card 20 - fetch expanded terrain windows for the 27 catalogue sites without a card 18 local grid.

Same storage contract as card 18 (docs/card18_reproduce.md): windows are centred on the catalogue
point with radius = analysis gate + 16 km, so every node of the +-10 km grid keeps its full gate.

  * south-polar sites (lat <= -75): PGDA polar DEM chain 5/10/20/60/80/240 m (card 2 fetch_polar),
    partial source coverage is clipped and recorded (5 m and 10 m only reach 87 S / 83 S).
  * other sites with |lat| < 60: SLDEM2015 59 m window, radius 150 + 16 km (card 3 fetch_global).
  * CHANDRAYAAN3 (69 S): no SLDEM (|lat| >= 60) and outside the polar chain: LDEM_64 near field.
  * global LDEM_64 / LDEM_16 (far field, card 3 fetch_global).

  python pipeline/local_fetch27.py [--only polar|sldem|global]      (resumable)
Outputs under data/processed/card18/raw/ (git-ignored), status in data/processed/card18/fetch27_status.json.
"""
import argparse
import json
import sys

try:  # PDS Geosciences serves an incomplete chain; use the OS trust store when available
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_polar  # noqa: E402
import fetch_global  # noqa: E402
from local_maps import GATES, IDS as CARD18_IDS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/processed/card18/raw'
STATUS = ROOT / 'data/processed/card18/fetch27_status.json'
POLAR_LAT = -75.0
SLDEM_GATE_KM = 150.0


def sites27():
    sites = json.loads((ROOT / 'web/data/sites.json').read_text(encoding='utf-8'))
    return [s for s in sites if s['id'] not in CARD18_IDS]


def save(status):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=1), encoding='utf-8')


def main():
    global STATUS
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--only', choices=['polar', 'sldem', 'global'])
    ap.add_argument('--site', action='append', help='only these site ids (parallel polar workers)')
    a = ap.parse_args()
    todo = [s for s in sites27() if not a.site or s['id'] in a.site]
    if a.site:
        STATUS = STATUS.with_name('fetch27_status_' + '_'.join(a.site) + '.json')
    status = json.loads(STATUS.read_text(encoding='utf-8')) if STATUS.exists() else {}
    if a.only in (None, 'global'):
        fetch_global.fetch_global_grids([16, 64], RAW / 'global')
        status['global'] = 'ok'; save(status)
    if a.only in (None, 'polar'):
        rows = status.setdefault('polar', {})
        for s in [s for s in todo if s['lat'] <= POLAR_LAT]:
            for res, gate in GATES.items():
                key = f"{s['id']}/{res}"
                if rows.get(key, {}).get('status') in ('ok', 'outside_source_coverage'):
                    continue
                try:
                    fetch_polar.fetch(s, res, (gate + 16) * 1000, RAW / 'polar', allow_partial=True)
                    rows[key] = dict(id=s['id'], res_m=res, status='ok')
                except fetch_polar.SourceCoverageError as e:
                    rows[key] = dict(id=s['id'], res_m=res, status='outside_source_coverage', note=str(e))
                except ValueError as e:
                    if 'no valid elevations' not in str(e):
                        raise
                    # the clipped window overlaps the raster only where it holds no data (5/10 m edges)
                    rows[key] = dict(id=s['id'], res_m=res, status='outside_source_coverage', note=str(e))
                save(status)
                print(key, rows[key]['status'], flush=True)
    if a.only in (None, 'sldem'):
        rows = status.setdefault('sldem', {})
        for s in [s for s in todo if abs(s['lat']) < 60]:
            if rows.get(s['id']) == 'ok':
                continue
            fetch_global.fetch_site_window(s, SLDEM_GATE_KM + 16, RAW / 'sldem', workers=4)
            rows[s['id']] = 'ok'; save(status)
            print('sldem', s['id'], 'ok', flush=True)


if __name__ == '__main__':
    main()
