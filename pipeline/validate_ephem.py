"""Card 1 validation against cached JPL Horizons observer tables.

python pipeline/validate_ephem.py --prepare-requests  # optional prefetch plan
python pipeline/validate_ephem.py                     # fetch or reuse 12 queries
python pipeline/validate_ephem.py --offline           # require cached responses
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

import numpy as np
from ephem import ROOT, EPOCH, Ephemeris, az_el, digest, write_json

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
CACHE = ROOT / "data/raw/horizons"
# Heights here are deliberately zero (reference-sphere geometry tests, not DEM
# heights). Both implementations place the observer +2 m above this sphere.
SITES = [
    {"id": "POLAR_TEST", "lat": -89.5, "lon": 0.0,
     "source_url": "", "note": "Synthetic south-polar geometry test point"},
    {"id": "APOLLO17", "lat": 20.1908, "lon": 30.7717,
     "source_url": "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html"},
    {"id": "SHACKLETON_RIM", "lat": -89.7668, "lon": -171.87,
     "source_url": "https://ntrs.nasa.gov/citations/20230007818"},
    {"id": "CHANGE4", "lat": -45.4446, "lon": 177.5991,
     "source_url": "https://doi.org/10.1038/s41467-019-12278-3",
     "note": "2019 paper coordinate used as a test point; not a catalogue coordinate decision"},
    {"id": "CHANDRAYAAN3", "lat": -69.3741, "lon": 32.32,
     "source_url": "https://lroc.im-ldi.com/images/1314"},
    {"id": "EQUATOR_TEST", "lat": 0.0, "lon": 0.0,
     "source_url": "", "note": "Synthetic equatorial geometry test point"},
]


def request_url(site, body):
    options = {"format": "json", "COMMAND": f"'{10 if body == 'sun' else 399}'",
               "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
               "SITE_COORD": f"'{site['lon']},{site['lat']},0.002'",
               "START_TIME": "'2026-01-01'", "STOP_TIME": "'2026-03-02'",
               "STEP_SIZE": "'12 h'", "QUANTITIES": "'4'", "CSV_FORMAT": "'YES'",
               "EXTRA_PREC": "'YES'", "APPARENT": "'AIRLESS'", "TIME_DIGITS": "'SECONDS'",
               "CAL_FORMAT": "'JD'", "OBJ_DATA": "'NO'"}
    return API + "?" + urllib.parse.urlencode(options)


def plan():
    return [{"site": site["id"], "body": body, "url": request_url(site, body),
             "file": site["id"].lower() + "_" + body + ".json"}
            for site in SITES for body in ("sun", "earth")]


def response_for(query, offline):
    path = CACHE / query["file"]
    if path.exists():
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("url") != query["url"]:
            raise ValueError(f"Cached URL differs: {path}")
    elif offline:
        raise FileNotFoundError(path)
    else:
        with urllib.request.urlopen(query["url"], timeout=180) as response:
            data = json.load(response)
        item = {"url": query["url"], "response": data,
                "retrieved_utc": datetime.now(timezone.utc).isoformat()}
        write_json(path, item)
    payload = item["response"]
    if "error" in payload or "$$SOE" not in payload.get("result", ""):
        raise ValueError(payload)
    result = payload["result"]
    # Never silently compare an IAU analytic frame or a refracted table.
    for marker in ("MEAN_ME (high precision)", "NO (AIRLESS)"):
        if marker not in result:
            raise ValueError(f"Horizons response missing {marker}")
    rows = list(csv.reader(result.split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip().splitlines()))
    values = np.array([[float(row[0]), float(row[3]), float(row[4])] for row in rows])
    if values.shape != (121, 3):
        raise ValueError(f"Expected 121 observations, got {values.shape}")
    hours = np.rint((values[:, 0] - 2461041.5) * 24).astype(int)
    if not np.array_equal(hours, np.arange(0, 1441, 12)):
        raise ValueError("Horizons UTC sample times do not match the test window")
    return hours, values[:, 1:], digest(path), payload.get("signature", {})


def differences(ours, reference):
    az = np.abs((ours[:, 0] - reference[:, 0] + 180) % 360 - 180)
    el = np.abs(ours[:, 1] - reference[:, 1])
    # Stable angular separation, useful near the azimuth singularity at zenith.
    a1, e1 = np.deg2rad(ours.T)
    a2, e2 = np.deg2rad(reference.T)
    v1 = np.column_stack((np.cos(e1) * np.cos(a1), np.cos(e1) * np.sin(a1), np.sin(e1)))
    v2 = np.column_stack((np.cos(e2) * np.cos(a2), np.cos(e2) * np.sin(a2), np.sin(e2)))
    sky = np.rad2deg(2 * np.arcsin(np.minimum(1, np.linalg.norm(v1 - v2, axis=1) / 2)))
    return {"max_az_deg": float(az.max()), "mean_az_deg": float(az.mean()),
            "max_el_deg": float(el.max()), "mean_el_deg": float(el.mean()),
            "max_sky_deg": float(sky.max()), "mean_sky_deg": float(sky.mean())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prepare-requests", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    queries = plan()
    if args.prepare_requests:
        write_json(CACHE / "requests.json", queries)
        print(CACHE / "requests.json")
        return
    engine = Ephemeris()
    binary = ROOT / "web/data/ephem.bin"
    values = np.fromfile(binary, dtype="<f4").reshape(-1, 6)
    if values.shape != (43824, 6):
        raise ValueError("Validation requires the complete real web ephemeris")
    rows = []
    for site in SITES:
        for body in ("sun", "earth"):
            query = next(q for q in queries if q["site"] == site["id"] and q["body"] == body)
            hours, reference, sha, signature = response_for(query, args.offline)
            dates = [EPOCH + timedelta(hours=int(h)) for h in hours]
            web = az_el(values[hours], site["lat"], site["lon"], body=body)
            direct = engine.direct_az_el(site["lat"], site["lon"], 0, dates, body)
            web_diff, direct_diff = differences(web, reference), differences(direct, reference)
            row = {"site": site, "body": body, "n": len(hours), "terrain_height_m": 0,
                   "obs_height_m": 2, "web_float32_vs_horizons": web_diff,
                   "direct_topocentric_vs_horizons": direct_diff,
                   "web_vs_direct": differences(web, direct), "url": query["url"],
                   "response_sha256": sha, "signature": signature}
            rows.append(row)
            print(site["id"], body, web_diff, flush=True)
    passed = all(max(row["web_float32_vs_horizons"][k] for k in ("max_az_deg", "max_el_deg")) < 0.01
                 for row in rows)
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(), "passed": passed,
              "threshold_deg": 0.01, "n_sites": 6, "n_times_per_body_site": 121,
              "n_comparisons": sum(row["n"] for row in rows), "binary_sha256": digest(binary),
              "window": "2026-01-01T00Z..2026-03-02T00Z inclusive, 12h",
              "notes": ["Horizons uses DE441 / high-precision MEAN_ME; ours uses DE440s + DE421 orientation.",
                        "All test terrain heights are 0 m; observer is 2 m above the 1737.4 km sphere.",
                        "Web comparison reads the exported float32 binary, not only the generator's float64 values.",
                        "Terrain obstruction, future leap seconds, and all five years are not independently validated by this 60-day test."],
              "results": rows}
    write_json(ROOT / "docs/ephem_validation.json", report)
    print("PASS" if passed else "FAIL", report["n_comparisons"], "body/site/time comparisons")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
