/** Real ephemeris + synthetic terrain fixtures; none are exported as results. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { ROOT, actualCore, loadEphemeris, validateHorizon, atomicJSON, run } from './cache_metrics.mjs';

const { core, hash } = await actualCore(ROOT);
await loadEphemeris(ROOT, core);
const cases = [
  { id: 'TEST_EQUATOR', lat: 0, lon: 0, height: 0, base: 0, amplitude: 0 },
  { id: 'TEST_POLAR', lat: -89.7668, lon: -171.87, height: 1200, base: 2, amplitude: 5 },
  { id: 'TEST_WRAP', lat: 20.1911, lon: 30.7723, height: -1800, base: -0.5, amplitude: 1.2 },
].map(v => ({ site: { id: v.id, lat: v.lat, lon: v.lon, elev_m: null },
  horizon: { id: v.id, lat: v.lat, lon: v.lon, h0_m: v.height, obs_height_m: 2,
    az_step_deg: 0.5, mask: Array.from({ length: 720 }, (_, i) => v.base + v.amplitude * Math.sin(i * Math.PI / 360)),
    mock: false, max_range_km: 300, dem_sources: [{ name: 'TEST_ONLY', res_m: 1, to_km: 300 }] } }));
const realIds = [];
for (const site of JSON.parse(await fs.readFile(path.join(ROOT, 'web/data/sites.json')))) {
  try {
    const horizon = JSON.parse(await fs.readFile(path.join(ROOT, `web/data/horizon/${site.id}.json`)));
    validateHorizon(site, horizon);
    cases.push({ site, horizon }); realIds.push(site.id);
  } catch { /* Missing/invalid real terrain is explicitly reported by the cache runner. */ }
}
const js = cases.map(({ site, horizon }) => {
  validateHorizon(site, horizon); core.state.horizons.set(site.id, horizon);
  return core.metrics(site);
});
assert.throws(() => validateHorizon(cases[0].site, { ...cases[0].horizon, mock: true }));
assert.throws(() => validateHorizon(cases[0].site, { ...cases[0].horizon, lat: 1 }));
assert.throws(() => validateHorizon(cases[0].site, { ...cases[0].horizon, engine: { n_missing_samples: 1 } }));
const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'llsn-metrics-'));
try {
  const plan = path.join(temp, 'cases.json');
  await atomicJSON(plan, { binary: path.join(ROOT, 'web/data/ephem.bin'), cases });
  const result = spawnSync(process.env.PYTHON || 'python', [path.join(ROOT, 'pipeline/check_metrics_python.py'), plan], { encoding: 'utf8' });
  if (result.status !== 0) throw Error(result.stderr || result.error?.message);
  const python = JSON.parse(result.stdout);
  for (let i = 0; i < cases.length; i++) for (const key of Object.keys(js[i])) {
    assert.equal(js[i][key].toFixed(4), python[i][key].toFixed(4), `${cases[i].site.id} ${key}`);
    assert.equal(js[i][key], python[i][key], `${cases[i].site.id} exact ${key}`);
  }
  // Exercise real cache writing/resume and refuse stale/missing or mock terrain.
  const fixture = path.join(temp, 'repo');
  await fs.mkdir(path.join(fixture, 'web/js'), { recursive: true });
  await fs.mkdir(path.join(fixture, 'web/data/horizon'), { recursive: true });
  for (const name of ['ephem.bin', 'ephem.json']) await fs.copyFile(path.join(ROOT, 'web/data', name), path.join(fixture, 'web/data', name));
  await fs.copyFile(path.join(ROOT, 'web/js/core.js'), path.join(fixture, 'web/js/core.js'));
  await atomicJSON(path.join(fixture, 'web/data/sites.json'), cases.map(c => c.site));
  for (const c of cases) await atomicJSON(path.join(fixture, `web/data/horizon/${c.site.id}.json`), c.horizon);
  let report = await run(fixture); assert.equal(report.computed.length, cases.length); assert.equal(report.complete, true);
  report = await run(fixture); assert.equal(report.computed.filter(x => x.resumed).length, cases.length);
  await fs.rm(path.join(fixture, `web/data/horizon/${cases[0].site.id}.json`));
  await atomicJSON(path.join(fixture, `web/data/horizon/${cases[1].site.id}.json`), { ...cases[1].horizon, mock: true });
  report = await run(fixture); assert.equal(report.computed.length, cases.length - 2); assert.equal(report.skipped.length, 2);
  await assert.rejects(fs.access(path.join(fixture, `web/data/metrics/${cases[0].site.id}.json`)));
  const resultReport = { passed: true, core_sha256: hash, n_hours: 43824,
    n_fixtures: 3, real_horizon_sites_checked: realIds,
    fixture_scope: 'Three synthetic terrains solely in a disposable test directory, plus every eligible real horizon currently available; real production ephemeris',
    exact_metric_matches: true, matches_to_four_decimals: true,
    cache_resume_and_stale_removal_passed: true, mock_and_coordinate_mismatch_and_dem_gap_rejected: true,
    cases: cases.map((c, i) => ({ site: c.site, js: js[i], python: python[i] })) };
  await atomicJSON(path.join(ROOT, 'docs/metrics_equivalence_check.json'), resultReport);
  console.log(`PASS: actual JS / Python metrics identical on three five-year fixtures and ${realIds.length} real sites`);
} finally {
  assert(path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep));
  await fs.rm(temp, { recursive: true, force: true });
}
