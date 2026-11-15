"""Z4 nearest historical landers; stdlib only, one CPU, no network at build time."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

RADIUS_M = 1737400.0
REFERENCE_UTC = '2026-11-15T00:00:00Z'
ROOT = Path(__file__).resolve().parents[1]


def normalized_sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def geometry(lat1, lon1, lat2, lon2):
    """Short spherical arc and initial bearing; undefined bearings are explicit."""
    for lat, lon in ((lat1, lon1), (lat2, lon2)):
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('Coordinates must be finite degrees within latitude/longitude bounds')
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians((lon2 - lon1 + 180) % 360 - 180)
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    a = min(1.0, max(0.0, a))
    angle = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    east = math.sin(dl) * math.cos(p2)
    north = math.cos(p1)*math.sin(p2) - math.sin(p1)*math.cos(p2)*math.cos(dl)
    if angle <= 1e-14:
        return 0.0, None, 'coincident'
    # Haversine loses precision near a=1: detect antipodes from sin(angle).
    if a > .5 and math.hypot(east, north) <= 1e-14:
        return RADIUS_M * math.pi, None, 'antipodal'
    if abs(lat1) == 90:
        return RADIUS_M * angle, None, 'origin_pole'
    bearing = math.degrees(math.atan2(east, north)) % 360
    return RADIUS_M * angle, bearing, 'defined'


def nearest_landings(site, missions, reference_utc=REFERENCE_UTC):
    reference = datetime.fromisoformat(reference_utc.replace('Z', '+00:00'))
    candidates = []
    for mission in missions:
        landed = datetime.fromisoformat(mission['landing_utc'].replace('Z', '+00:00'))
        if mission['id'] == site['id'] or landed > reference:
            continue
        distance, bearing, status = geometry(site['lat'], site['lon'], mission['lat'], mission['lon'])
        candidates.append(dict(id=mission['id'], distance_m=distance, bearing_deg=bearing,
                               bearing_status=status, official_source_url=mission['official_source_url']))
    candidates.sort(key=lambda candidate: (candidate['distance_m'], candidate['id']))
    return [dict(rank=rank, **candidate) for rank, candidate in enumerate(candidates[:3], 1)]


def build_history(root=ROOT):
    started = time.perf_counter()
    sites = json.loads((root / 'web/data/sites.json').read_text(encoding='utf-8'))
    official = json.loads((root / 'docs/detail_z4_sources.json').read_text(encoding='utf-8'))['missions']
    catalogue = {s['id']: s for s in sites}
    if len(catalogue) != len(sites):
        raise ValueError('Duplicate catalogue IDs')
    with (root / 'docs/task_r_landings.csv').open(encoding='utf-8', newline='') as stream:
        landings = list(csv.DictReader(stream))
    missions = []
    for record in landings:
        sid = record['id']
        if catalogue[sid]['group'] in ('future', 'custom', 'artemis3_region', 'polar_peak'):
            raise ValueError(f'Target/non-landing ID in actual landing input: {sid}')
        source = official[sid]
        missions.append(dict(id=sid, name=catalogue[sid]['name'], lat=float(record['lat']),
                             lon=float(record['lon']), landing_utc=record['landing_utc'],
                             coordinate_source=record['coordinate_source'], time_source=record['time_source'],
                             official_source_url=source['url'], official_source_agency=source['agency'],
                             note=record['note']))
    if len({m['id'] for m in missions}) != len(missions):
        raise ValueError('Duplicate historical landing IDs')
    rows = [dict(id=s['id'], lat=s['lat'], lon=s['lon'],
                 nearest=nearest_landings(s, missions)) for s in sites]
    if any(len(row['nearest']) != 3 for row in rows):
        raise ValueError('Fewer than three eligible other landings')
    paths = ['web/data/sites.json', 'docs/task_r_landings.csv', 'docs/detail_z4_sources.json',
             'pipeline/detail_history.py']
    return dict(schema_version=1, product='nearest_historical_landings', radius_m=RADIUS_M,
                frame='MOON_ME_DE421', nearest_count=3, reference_utc=REFERENCE_UTC,
                mission_count=len(missions), site_count=len(rows),
                distance_definition='Shortest great-circle surface distance on a sphere; no terrain or elevation correction.',
                bearing_definition='Initial bearing from true north, clockwise [0,360); null for coincident, antipodal or polar origin.',
                tie_break='Unrounded distance_m ascending, then mission ID lexicographically for exact ties.',
                caveat='Historical proximity within the 18 Task R landers only; not infrastructure, accessibility, route length, or an exhaustive lunar landing inventory. Source coordinate precision limits accuracy.',
                provenance=dict(sha256_normalization='CRLF_to_LF',
                                inputs=[dict(path=p, sha256=normalized_sha256(root / p)) for p in paths],
                                generated_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                                elapsed_s=time.perf_counter()-started, workers=1),
                missions=missions, sites=rows, mock=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'web/data/detail/history.json')
    args = parser.parse_args()
    product = build_history()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(product, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    print(json.dumps(dict(output=str(args.output), sites=product['site_count'], missions=product['mission_count'],
                          elapsed_s=product['provenance']['elapsed_s'], workers=1)))


if __name__ == '__main__':
    main()
