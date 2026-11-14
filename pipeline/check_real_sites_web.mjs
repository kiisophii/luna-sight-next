/** Confirm actual unchanged core.js matches the new six-site Horizons run. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { ROOT, actualCore, loadEphemeris, atomicJSON } from './cache_metrics.mjs';
const { core, hash } = await actualCore(ROOT);
await loadEphemeris(ROOT, core);
const cases = JSON.parse(await fs.readFile(path.join(ROOT, 'data/processed/card10_horizons_cases.json')));
const report = { passed: true, n_comparisons: cases.length, core_sha256: hash,
  max_az_deg: 0, max_el_deg: 0, max_js_python_az_deg: 0, max_js_python_el_deg: 0,
  scope: 'Actual core.js in Node; zero terrain height and +2 m observer, no horizon obstruction. References from the fresh card 10 queries.' };
for (const c of cases) {
  const site = { id: c.id, lat: c.lat, lon: c.lon, elev_m: 0 };
  const value = (c.body === 'sun' ? core.sunAzEl : core.earthAzEl)(site, c.hour);
  const azDiff = (a, b) => Math.abs(((a - b + 540) % 360) - 180);
  report.max_az_deg = Math.max(report.max_az_deg, azDiff(value.az, c.az));
  report.max_el_deg = Math.max(report.max_el_deg, Math.abs(value.el - c.el));
  report.max_js_python_az_deg = Math.max(report.max_js_python_az_deg, azDiff(value.az, c.python_az));
  report.max_js_python_el_deg = Math.max(report.max_js_python_el_deg, Math.abs(value.el - c.python_el));
}
report.passed = cases.length === 1452 && report.max_az_deg < 0.01 && report.max_el_deg < 0.01 &&
  report.max_js_python_az_deg < 1e-9 && report.max_js_python_el_deg < 1e-9;
await atomicJSON(path.join(ROOT, 'docs/real_sites_web_check.json'), report);
console.log(report); assert(report.passed);
