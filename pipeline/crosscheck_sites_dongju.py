"""Cross-check of web/data/sites.json (producer Minchul Kim) by Dongju Kim.

5 sites drawn at random (random.Random(20261114).sample(sites, 5)); for each, the coordinate was read
again from the original source page on 2026-11-14 (KST) in a browser / PDF text extraction, not from
docs/sites_source_audit.json. The quoted source text is stored below and compared with sites.json.

    python pipeline/crosscheck_sites_dongju.py
Writes docs/crosscheck_sites_dongju.json.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# id -> (source URL, quoted text as read on the source, lat, lon (east-positive) read from it)
READ = {
    "APOLLO16": ("https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html",
                 "Apollo 16 ... Lunar Module -8.9734 15.5011", -8.9734, 15.5011),
    "IM1": ("https://lroc.im-ldi.com/images/1360",
            "Odysseus came to rest at 80.13°S, 1.44°E, 2579 m elevation", -80.13, 1.44),
    "DE_GERLACHE_RIM1": ("https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf",
                         "Table A2-2 (p. 58 of 70): R11 or Site11 de Gerlache Rim 1 -88.6834 -67.9321", -88.6834, -67.9321),
    "IM3_REINER_GAMMA": ("https://www.frontiersin.org/journals/astronomy-and-space-sciences/articles/10.3389/fspas.2022.926018/full",
                         "The targeted LVx landing site (7.585°N, 58.725°W)", 7.585, -58.725),
    "LUNA24": ("https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html",
               "Luna 24 Soft Landing 18 August 1976 12.7142 N, 62.2129 E", 12.7142, 62.2129),
}


def main():
    sites = json.loads((ROOT / "web" / "data" / "sites.json").read_text(encoding="utf-8"))
    sites = sites["sites"] if isinstance(sites, dict) else sites
    pick = [s["id"] for s in random.Random(20261114).sample(sites, 5)]
    assert sorted(pick) == sorted(READ), (pick, sorted(READ))
    by = {s["id"]: s for s in sites}
    rows, worst = [], 0.0
    for sid in pick:
        url, quote, lat, lon = READ[sid]
        s = by[sid]
        d = max(abs(s["lat"] - lat), abs(s["lon"] - lon))
        worst = max(worst, d)
        rows.append({"id": sid, "source_url": url, "source_matches_sites_json_url": s["source_url"] == url,
                     "quoted": quote, "read_lat": lat, "read_lon": lon,
                     "catalogue_lat": s["lat"], "catalogue_lon": s["lon"], "max_abs_diff_deg": d})
        print(f"{sid:<18} source {lat}, {lon}  catalogue {s['lat']}, {s['lon']}  diff {d}")
    ok = worst == 0 and all(r["source_matches_sites_json_url"] for r in rows)
    out = {"product": "web/data/sites.json", "producer": "Minchul Kim", "checker": "Dongju Kim",
           "method": "coordinates re-read from the original source pages (browser text / PDF text), compared to sites.json",
           "sample": pick, "seed": 20261114, "rows": rows, "max_abs_diff_deg": worst,
           "criterion": "identical to the published precision", "passed": ok}
    (ROOT / "docs" / "crosscheck_sites_dongju.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("max abs diff", worst, "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
