/** Card 10: cache the actual core.js hourly metrics, never flat/mock fallbacks.
 * node pipeline/cache_metrics.mjs [--root REPO] [--require-all]
 * Each site and its provenance are saved atomically; reruns reuse matching inputs.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import crypto from 'node:crypto';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
export async function atomicJSON(file, value) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file + '.tmp', JSON.stringify(value, null, 2) + '\n');
  await fs.rename(file + '.tmp', file);
}
export async function actualCore(root) {
  const bytes = await fs.readFile(path.join(root, 'web/js/core.js'));
  const core = await import('data:text/javascript;base64,' + bytes.toString('base64'));
  return { core, hash: sha(bytes) };
}
export async function loadEphemeris(root, core) {
  const data = path.join(root, 'web/data');
  const bytes = await fs.readFile(path.join(data, 'ephem.bin'));
  const metaBytes = await fs.readFile(path.join(data, 'ephem.json'));
  const meta = JSON.parse(metaBytes);
  const columns = ['sun_x', 'sun_y', 'sun_z', 'earth_x', 'earth_y', 'earth_z'];
  if (meta.mock !== false || meta.n !== 43824 || meta.step_h !== 1 ||
      meta.frame !== 'MOON_ME_DE421' || meta.units !== 'km' ||
      meta.start !== '2026-01-01T00:00:00Z' || JSON.stringify(meta.columns) !== JSON.stringify(columns) ||
      bytes.length !== meta.n * 24) throw Error('Complete real contract ephemeris required');
  const values = new Float32Array(meta.n * 6);
  for (let i = 0; i < values.length; i++) values[i] = bytes.readFloatLE(i * 4);
  if (!values.every(Number.isFinite)) throw Error('Nonfinite ephemeris');
  core.state.ephem = values; core.state.n = meta.n; core.state.ephemMeta = meta;
  core.state.horizons.clear();
  return { ephem_sha256: sha(bytes), metadata_sha256: sha(metaBytes), n: meta.n };
}
export function validateHorizon(site, h) {
  if (!/^[A-Z][A-Z0-9_]*$/.test(site.id) || !Number.isFinite(site.lat) || !Number.isFinite(site.lon))
    throw Error('invalid catalogue site');
  if (site.mock || h.mock !== false || h.flat || h.site_coords_mock) throw Error('mock or flat input');
  if (h.id !== site.id || Math.abs(h.lat - site.lat) > 1e-9 ||
      Math.abs(((h.lon - site.lon + 540) % 360) - 180) > 1e-9 ||
      !Number.isFinite(h.lat) || !Number.isFinite(h.lon)) throw Error('horizon/site coordinate mismatch');
  if (!Number.isFinite(h.h0_m) || h.obs_height_m !== 2 || h.az_step_deg !== 0.5 ||
      !Array.isArray(h.mask) || h.mask.length !== 720 || !h.mask.every(v => Number.isFinite(v) && Math.abs(v) <= 90))
    throw Error('invalid horizon geometry');
  if (!(h.max_range_km > 0) || !Array.isArray(h.dem_sources) || !h.dem_sources.length)
    throw Error('real DEM provenance required');
  if (h.engine?.n_missing_samples > 0) throw Error('DEM coverage gaps require terrain-owner review');
}
export async function run(root, requireAll = false) {
  const { core, hash } = await actualCore(root);
  const ephem = await loadEphemeris(root, core);
  const sitesBytes = await fs.readFile(path.join(root, 'web/data/sites.json'));
  const sites = JSON.parse(sitesBytes);
  const reportFile = path.join(root, 'docs/metrics_cache_report.json');
  let previous;
  try { previous = JSON.parse(await fs.readFile(reportFile, 'utf8')); } catch { previous = {}; }
  const report = { generated_utc: new Date().toISOString(), complete: false,
    definition: 'Actual web/js/core.js metrics(site, 0, 43823); inclusive hourly sample counts',
    window: '2026-01-01..2030-12-31', core_sha256: hash, ...ephem,
    sites_sha256: sha(sitesBytes), computed: [], skipped: [],
    notes: ['No mock, missing, coordinate-mismatched or incomplete-DEM horizons are exported.',
      'slope_deg is null: no measured slope is provided by the horizon contract.',
      'longest_dark_h is the longest sampled dark run clipped to the five-year window; no sub-hour refinement.'] };
  for (const site of sites) {
    const output = path.join(root, `web/data/metrics/${site.id}.json`);
    let h, bytes;
    try {
      bytes = await fs.readFile(path.join(root, `web/data/horizon/${site.id}.json`));
      h = JSON.parse(bytes); validateHorizon(site, h);
    } catch (error) {
      // A previously generated cache must not survive when its terrain disappears.
      await fs.rm(output, { force: true });
      report.skipped.push({ id: site.id, reason: error.code === 'ENOENT' ? 'missing horizon' : error.message });
      await atomicJSON(reportFile, report);
      continue;
    }
    const inputs = { core_sha256: hash, ephem_sha256: ephem.ephem_sha256,
      metadata_sha256: ephem.metadata_sha256, site_sha256: sha(JSON.stringify(site)), horizon_sha256: sha(bytes) };
    const prior = previous.computed?.find(x => x.id === site.id && JSON.stringify(x.inputs) === JSON.stringify(inputs));
    if (prior) {
      try {
        const cached = await fs.readFile(output);
        if (sha(cached) === prior.output_sha256) {
          report.computed.push({ ...prior, resumed: true });
          await atomicJSON(reportFile, report); continue;
        }
      } catch { /* Recompute an absent or changed output. */ }
    }
    core.state.horizons.set(site.id, h);
    const values = core.metrics(site, 0, ephem.n - 1);
    const record = { id: site.id, window: report.window, ...values, slope_deg: null };
    if (!['sun_frac', 'earth_frac', 'both_frac'].every(k => Number.isFinite(record[k]) && record[k] >= 0 && record[k] <= 1) ||
        !Number.isInteger(record.longest_dark_h) || record.longest_dark_h < 0 || record.longest_dark_h > ephem.n)
      throw Error('Invalid core metric output: ' + site.id);
    await atomicJSON(output, record);
    report.computed.push({ id: site.id, inputs, output_sha256: sha(await fs.readFile(output)), resumed: false });
    await atomicJSON(reportFile, report);
    console.log(site.id, values);
  }
  report.complete = report.skipped.length === 0 && report.computed.length === sites.length;
  await atomicJSON(reportFile, report);
  console.log(JSON.stringify({ complete: report.complete, computed: report.computed.length, skipped: report.skipped.length }));
  if (requireAll && !report.complete) process.exitCode = 2;
  return report;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2), at = args.indexOf('--root');
  const root = at < 0 ? ROOT : path.resolve(args[at + 1]);
  if (at >= 0 && !args[at + 1]) throw Error('--root requires a path');
  if (args.some((a, i) => a !== '--require-all' && a !== '--root' && !(at >= 0 && i === at + 1))) throw Error('Unknown argument');
  await run(root, args.includes('--require-all'));
}
