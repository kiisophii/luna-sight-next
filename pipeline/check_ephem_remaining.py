"""Supplemental card 1 checks, preserving production ephemeris bytes.

python pipeline/check_ephem_remaining.py
python pipeline/check_ephem_remaining.py --serve
Open http://127.0.0.1:8765/tmp/ephem-browser.html in a real browser.

Uses existing kernels, NPZ, binary and cached Horizons responses. It does not
regenerate production datasets. Its actual-engine interruption test generates
only a disposable 12-hour fixture, then compares it to the stored binary.
"""
from datetime import datetime, timedelta, timezone
import csv
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import numpy as np
import ephem
from ephem import ROOT, EPOCH, Ephemeris, digest, write_json


def main():
    production_paths = [ROOT / "web/data/ephem.bin", ROOT / "web/data/ephem.json"]
    before = {str(p.relative_to(ROOT)): digest(p) for p in production_paths}
    engine = Ephemeris()
    npz_path = ROOT / "data/processed/ephem_2020-2038_2h.npz"
    with np.load(npz_path, allow_pickle=False) as series:
        v = series["vectors"]
        hours = series["hour_index"]
        assert v.shape == (81444, 6) and v.dtype == np.dtype("<f4")
        assert str(series["frame"]) == "MOON_ME_DE421" and str(series["units"]) == "km"
        assert int(series["step_h"]) == 2
        assert str(series["start"]) == "2020-01-01T00:00:00Z"
        assert str(series["stop_exclusive"]) == "2038-08-01T00:00:00Z"
        assert series["columns"].tolist() == ephem.COLUMNS
        assert hours.shape == (81444,) and hours[0] == -52608 and hours[-1] == 110278
        assert np.all(np.diff(hours) == 2) and np.isfinite(v).all()
        sun_range, earth_range = np.linalg.norm(v[:, :3], axis=1), np.linalg.norm(v[:, 3:], axis=1)
        assert np.all((sun_range > 1.40e8) & (sun_range < 1.60e8))
        assert np.all((earth_range > 3.50e5) & (earth_range < 4.10e5))
        ix = np.array([0, 1, len(v) // 2, len(v) - 2, len(v) - 1])
        dates = [EPOCH + timedelta(hours=int(hours[i])) for i in ix]
        exact = engine.vectors(dates).astype("<f4")
        assert np.array_equal(v[ix], exact)
        npz_report = {"passed": True, "sha256": digest(npz_path), "bytes": npz_path.stat().st_size,
                      "shape": list(v.shape), "dtype": "little-endian float32", "all_rows_finite": True,
                      "all_hour_indices_regular": True, "sample_indices_recomputed": ix.tolist(),
                      "sample_float32_mismatches": int(np.count_nonzero(v[ix] != exact)),
                      "note": "Actual saved NPZ checked; five rows recomputed, not the complete 18.6-year series"}

    class InterruptOnce:
        calls = 0

        def vectors(self, dates):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("intentional interruption after first actual-engine chunk")
            return engine.vectors(dates)

    class Resume:
        calls = []

        def vectors(self, dates):
            self.calls.append([d.isoformat() for d in dates])
            return engine.vectors(dates)

    with tempfile.TemporaryDirectory(prefix="llsn-actual-resume-") as temp:
        with patch.object(ephem, "ROOT", Path(temp)):
            destination = Path(temp) / "fixture.bin"
            stop = EPOCH + timedelta(hours=12)
            try:
                ephem.generate(InterruptOnce(), EPOCH, stop, 1, destination, {"test": "actual engine"}, 3)
            except RuntimeError as error:
                if "intentional interruption" not in str(error):
                    raise
            else:
                raise AssertionError("Interruption did not occur")
            assert not destination.exists()
            checkpoint = json.loads((Path(temp) / "data/processed/fixture_1h.state.json").read_text())
            assert checkpoint["done"] == 3
            resumed = Resume()
            ephem.generate(resumed, EPOCH, stop, 1, destination, {"test": "actual engine"}, 3)
            fixture = np.fromfile(destination, dtype="<f4").reshape(-1, 6)
            production = np.fromfile(production_paths[0], dtype="<f4", count=12 * 6).reshape(-1, 6)
            assert resumed.calls[0][0] == (EPOCH + timedelta(hours=3)).isoformat()
            assert sum(map(len, resumed.calls)) == 9
            assert np.array_equal(fixture, production)
            resume_report = {"passed": True, "fixture_hours": 12, "chunk_rows": 3,
                             "checkpoint_rows_before_interrupt": checkpoint["done"],
                             "rows_computed_after_resume": 9, "resumed_at_utc": resumed.calls[0][0],
                             "float32_mismatches_vs_existing_binary": int(np.count_nonzero(fixture != production)),
                             "scope": "Intentional exception between actual Skyfield chunks; not an OS kill, power loss or network interruption test"}

    cases = []
    for query in json.loads((ROOT / "data/raw/horizons/requests.json").read_text(encoding="utf-8")):
        cached = json.loads((ROOT / "data/raw/horizons" / query["file"]).read_text(encoding="utf-8"))
        assert cached["url"] == query["url"]
        lon, lat, height_km = map(float, parse_qs(urlparse(query["url"]).query)["SITE_COORD"][0].strip("'").split(","))
        assert height_km == 0.002
        table = cached["response"]["result"].split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
        for row in csv.reader(table.splitlines()):
            cases.append({"site_id": query["site"], "body": query["body"], "lat": lat, "lon": lon,
                          "hour": round((float(row[0]) - 2461041.5) * 24),
                          "az": float(row[3]), "el": float(row[4])})
    assert len(cases) == 1452
    temporary = ROOT / "tmp"
    temporary.mkdir(exist_ok=True)
    write_json(temporary / "ephem-browser-cases.json", cases)
    (temporary / "ephem-browser.html").write_text(BROWSER_HTML, encoding="utf-8")
    after = {str(p.relative_to(ROOT)): digest(p) for p in production_paths}
    assert before == after
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "original_implementation_commit": "d89c42a065eea5d478f4e03b56e15585c02635b6",
              "verification_owner": "Implementation assistant follow-up; separate from the user-reported independent review",
              "production_hashes_before": before, "production_hashes_after": after,
              "production_unchanged": True, "npz": npz_report, "actual_engine_resume": resume_report,
              "interpolation": json.loads((ROOT / "docs/ephem_interpolation_check.json").read_text()),
              "browser": {"status": "pending", "prepared_cases": len(cases),
                          "harness": "tmp/ephem-browser.html", "reference": "Existing cached Horizons responses, not new queries"}}
    write_json(ROOT / "docs/ephem_followup_check.json", report)
    print(json.dumps({"npz": npz_report, "resume": resume_report, "production_unchanged": True}, indent=2))


BROWSER_HTML = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Card 1 browser verification</title>
<style>body{max-width:1000px;margin:40px auto;padding:20px;background:#101621;color:#e7edf7;font:18px system-ui}pre{white-space:pre-wrap}h1{color:#ffd45b}</style>
<h1>Card 1 browser verification</h1><p id="status">Running actual core.js...</p><pre id="result"></pre>
<script type="module">
try {
  const core = await import('/web/js/core.js');
  await core.loadData('/web/data/');
  const cases = await (await fetch('ephem-browser-cases.json')).json();
  let maxAz=0, maxEl=0;
  for(const c of cases){
    // Isolate the zero-terrain reference sites from the app's mock horizons.
    const site={id:'CHECK_'+c.site_id,lat:c.lat,lon:c.lon,elev_m:0};
    const value=(c.body==='sun'?core.sunAzEl:core.earthAzEl)(site,c.hour);
    maxAz=Math.max(maxAz,Math.abs(((value.az-c.az+540)%360)-180));
    maxEl=Math.max(maxEl,Math.abs(value.el-c.el));
  }
  const results={passed:cases.length===1452&&core.state.n===43824&&maxAz<0.01&&maxEl<0.01,
    n_comparisons:cases.length,loaded_ephem_rows:core.state.n,metadata_mock:core.state.ephemMeta.mock,
    max_az_deg:maxAz,max_el_deg:maxEl,threshold_deg:0.01,
    actual_module:'web/js/core.js',reference:'Original cached Horizons tables, not a new independent query',
    terrain_height_m:0,obs_height_m:2,user_agent:navigator.userAgent};
  document.getElementById('status').textContent=results.passed?'PASS':'FAIL';
  document.getElementById('result').textContent=JSON.stringify(results,null,2);
}catch(error){document.getElementById('status').textContent='FAIL';document.getElementById('result').textContent=String(error.stack||error);}
</script></html>'''


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--serve"]:
        from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
        from functools import partial
        SimpleHTTPRequestHandler.extensions_map[".js"] = "text/javascript"
        handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
        print("Open http://127.0.0.1:8765/tmp/ephem-browser.html")
        ThreadingHTTPServer(("127.0.0.1", 8765), handler).serve_forever()
    else:
        main()

