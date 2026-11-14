/** Card 15-B: hourly, half-open visibility windows using unchanged core.js.
 * node pipeline/build_windows.mjs
 * Results are atomic per site; input/output hashes allow safe resume.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ROOT, sha, atomicJSON, actualCore, loadEphemeris, validateHorizon } from './cache_metrics.mjs';

export const START = '2026-01-01T00:00:00Z';
export const END = '2031-01-01T00:00:00Z';
export const hourUTC = hour => new Date(Date.parse(START) + hour * 3600000).toISOString().replace('.000Z', 'Z');
export function interval(a, b, n) {
  return { start_utc: hourUTC(a), end_utc: hourUTC(b), duration_h: b - a,
    clipped_start: a === 0, clipped_end: b === n };
}
export function splitRuns(states) {
  const visible = [], gaps = [];
  let a = 0;
  for (let b = 1; b <= states.length; b++) {
    if (b === states.length || states[b] !== states[a]) {
      (states[a] ? visible : gaps).push(interval(a, b, states.length)); a = b;
    }
  }
  const longest = [...gaps].sort((x, y) => y.duration_h - x.duration_h || x.start_utc.localeCompare(y.start_utc)).slice(0, 10);
  return { visible, longest_gaps: longest, visible_hours: visible.reduce((sum, w) => sum + w.duration_h, 0) };
}
export async function generate(root = ROOT) {
  const { core, hash: coreHash } = await actualCore(root);
  const ephem = await loadEphemeris(root, core);
  const sites = JSON.parse(await fs.readFile(path.join(root, 'web/data/sites.json')));
  const producerHash = sha(await fs.readFile(fileURLToPath(import.meta.url)));
  const reportFile = path.join(root, 'docs/windows_generation.json');
  let previous = {};
  try { previous = JSON.parse(await fs.readFile(reportFile)); } catch { /* First run. */ }
  const report = { base_main: 'ef2b2dad9e768af79e88f97b9c43ad35a8623de3',
    generated_utc: new Date().toISOString(), complete_for_available_horizons: false,
    start_utc: START, end_utc: END, n: ephem.n, computed: [], skipped: [],
    interpretation: 'Hourly states held over [hour, hour+1); not sub-hour astronomical rise/set times.' };
  const index = { format: 'site-windows-v1', start_utc: START, end_utc: END,
    step_h: 1, n: ephem.n, ids: [], skipped: {}, mock: false };
  for (const site of sites) {
    if (!/^[A-Z][A-Z0-9_]*$/.test(site.id)) throw Error('Invalid site ID');
    const output = path.join(root, `web/data/windows/${site.id}.json`);
    let h, bytes;
    try {
      bytes = await fs.readFile(path.join(root, `web/data/horizon/${site.id}.json`));
      h = JSON.parse(bytes); validateHorizon(site, h);
      if (site.id === 'SHACKLETON_RIM' &&
          (Math.abs(site.lat + 89.6866) > 1e-9 || Math.abs(site.lon + 162.81) > 1e-9))
        throw Error('Skip Shackleton until its corrected site and matching new horizon are on main');
    } catch (error) {
      await fs.rm(output, { force: true });
      const reason = error.code === 'ENOENT' ? 'missing horizon' : error.message;
      report.skipped.push({ id: site.id, reason }); index.skipped[site.id] = reason;
      await atomicJSON(reportFile, report); continue;
    }
    const inputs = { core_sha256: coreHash, ephem_sha256: ephem.ephem_sha256,
      ephem_meta_sha256: ephem.metadata_sha256, site_sha256: sha(JSON.stringify(site)),
      horizon_sha256: sha(bytes), producer_sha256: producerHash };
    const prior = previous.computed?.find(x => x.id === site.id && JSON.stringify(x.inputs) === JSON.stringify(inputs));
    if (prior) {
      try {
        if (sha(await fs.readFile(output)) === prior.output_sha256) {
          report.computed.push({ ...prior, resumed: true }); index.ids.push(site.id);
          await atomicJSON(reportFile, report); continue;
        }
      } catch { /* Recompute a missing or modified result. */ }
    }
    core.state.horizons.set(site.id, h);
    const sun = new Uint8Array(ephem.n), earth = new Uint8Array(ephem.n);
    for (let i = 0; i < ephem.n; i++) {
      sun[i] = +core.sunlit(site, i); earth[i] = +core.earthVisible(site, i);
    }
    const result = { format: 'site-windows-v1', id: site.id, lat: site.lat, lon: site.lon,
      h0_m: h.h0_m, obs_height_m: 2, start_utc: START, end_utc: END,
      step_h: 1, n: ephem.n, sun: splitRuns(sun), earth: splitRuns(earth), source: inputs, mock: false };
    await atomicJSON(output, result);
    report.computed.push({ id: site.id, inputs, output_sha256: sha(await fs.readFile(output)), resumed: false,
      sun_windows: result.sun.visible.length, earth_windows: result.earth.visible.length,
      sun_visible_hours: result.sun.visible_hours, earth_visible_hours: result.earth.visible_hours });
    index.ids.push(site.id); await atomicJSON(reportFile, report);
    console.log(site.id, 'Sun windows', result.sun.visible.length, 'Earth windows', result.earth.visible.length);
  }
  report.complete_for_available_horizons = report.skipped.every(x => x.id === 'SHACKLETON_RIM');
  await atomicJSON(path.join(root, 'web/data/windows/index.json'), index);
  await atomicJSON(reportFile, report);
  console.log(JSON.stringify({ computed: index.ids.length, skipped: index.skipped }));
  if (!report.complete_for_available_horizons) process.exitCode = 2;
  return report;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await generate();
