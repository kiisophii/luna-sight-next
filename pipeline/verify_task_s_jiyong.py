"""Recompare manually re-read primary-source coordinates; no producer audit imports.

This checks transcription, not absolute geolocation. Run from any directory.
Source acquisition and visual PDF reading are documented in the evidence JSONs.
"""
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/task_s_jiyong'
R_M = 1737400


def normalize_lon(value):
    lon = Decimal(str(value))
    return ((lon + 180) % 360 + 360) % 360 - 180


def distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = map(math.radians, (float(lat1), float(lat2)))
    dp = p2 - p1
    dl = math.radians(float(normalize_lon(Decimal(str(lon2)) - Decimal(str(lon1)))))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_M * math.asin(math.sqrt(min(1, max(0, a))))


def main():
    catalogue_file = ROOT / 'web/data/sites.json'
    catalogue = {s['id']: s for s in json.loads(catalogue_file.read_text(encoding='utf8'), parse_float=Decimal)}
    evidence_rows = {}
    hashes = {}
    for name in ('historical', 'robotic', 'polar', 'artemis'):
        path = EVIDENCE / (name + '.json')
        payload = path.read_bytes()
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(payload).hexdigest()
        for row in json.loads(payload)['rows']:
            if row['id'] in evidence_rows:
                raise ValueError('Duplicate evidence: ' + row['id'])
            if not row.get('locator') or not row.get('source_url'):
                raise ValueError('Missing primary source locator: ' + row['id'])
            evidence_rows[row['id']] = row
    if set(evidence_rows) != set(catalogue) or len(catalogue) != 33:
        raise ValueError('Evidence must cover exactly all 33 catalogue IDs')
    results = []
    for id, site in catalogue.items():
        row = evidence_rows[id]
        lat = Decimal(row['source_lat_decimal'])
        lon = normalize_lon(row['source_lon_decimal'])
        same = lat == site['lat'] and lon == normalize_lon(site['lon'])
        results.append(dict(id=id, source_lat=str(lat), source_lon_normalized=str(lon),
                            match=same, delta_m=distance_m(lat, lon, site['lat'], site['lon']),
                            evidence_url=row['source_url'], locator=row['locator']))
    alternatives = []
    for id, lat, lon, url in (
        ('CHANGE3', '44.1214', '-19.5117', 'https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html'),
        ('CHANGE4', '-45.4561', '177.5885', 'https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html'),
        ('BLUE_GHOST1', '18.5623', '61.8103', 'https://lroc.im-ldi.com/images/1407'),
    ):
        site = catalogue[id]
        alternatives.append(dict(id=id, source_lat=lat, source_lon=lon, url=url,
                                 delta_m=distance_m(lat, lon, site['lat'], site['lon'])))
    report = dict(scope='All 33 cited coordinate pairs; not physical accuracy or exhaustive alternate-source search',
                  catalogue_sha256=hashlib.sha256(catalogue_file.read_bytes()).hexdigest(),
                  evidence_sha256=hashes, reference_radius_m=R_M, matches=sum(r['match'] for r in results),
                  max_delta_m=max(r['delta_m'] for r in results), rows=results, alternate_source_differences=alternatives)
    (EVIDENCE / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: report[k] for k in ('matches', 'max_delta_m', 'alternate_source_differences')}, indent=2))
    if report['matches'] != 33:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
