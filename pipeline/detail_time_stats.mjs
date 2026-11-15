/** Z1: exact hourly statistics from unchanged core.js; one CPU, atomic per-site resume. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { ROOT, sha, atomicJSON, actualCore, loadEphemeris, validateHorizon } from './cache_metrics.mjs';

const START = '2026-01-01T00:00:00Z', END = '2031-01-01T00:00:00Z';
const textHash = bytes => sha(bytes.toString('utf8').replace(/\r\n/g, '\n'));
const utc = i => new Date(Date.parse(START) + i * 3600000).toISOString().replace('.000Z', 'Z');

export function runs(states) {
  const result = [];
  for (let a = 0; a < states.length;) {
    let b = a + 1;
    while (b < states.length && states[b] === states[a]) b++;
    if (states[a]) result.push({ start_i: a, end_i: b, duration_h: b - a,
      clipped_start: a === 0, clipped_end: b === states.length });
    a = b;
  }
  return result;
}
export function runStats(states) {
  const observed = runs(states), complete = observed.filter(r => !r.clipped_start && !r.clipped_end);
  const total = rs => rs.reduce((n, r) => n + r.duration_h, 0);
  const longest = rs => rs.reduce((n, r) => Math.max(n, r.duration_h), 0);
  return { count: observed.length, total_h: total(observed),
    mean_h: observed.length ? total(observed) / observed.length : null, longest_h: longest(observed),
    complete_count: complete.length, complete_mean_h: complete.length ? total(complete) / complete.length : null,
    complete_longest_h: longest(complete), clipped_runs: observed.filter(r => r.clipped_start || r.clipped_end) };
}
export function stationHours(earth, stations) {
  const ids = ['KDSA', 'DSN_GOLDSTONE', 'DSN_MADRID', 'DSN_CANBERRA'];
  if (stations.length !== 4 || !ids.every(id => stations.filter(s => s.id === id).length === 1))
    throw Error('Exactly four stations including KDSA required');
  const buffers = ids.map(id => Buffer.from(stations.find(s => s.id === id).bits_b64, 'base64'));
  if (buffers.some(b => b.length !== Math.ceil(earth.length / 8))) throw Error('Station bit length mismatch');
  const result = { kdsa_h: 0, at_least_1_h: 0, at_least_2_h: 0 };
  for (let i = 0; i < earth.length; i++) {
    if (!earth[i]) continue;
    const bits = buffers.map(b => (b[i >> 3] >> (i & 7)) & 1);
    const count = bits.reduce((a, b) => a + b, 0);
    result.kdsa_h += bits[0]; result.at_least_1_h += +(count >= 1); result.at_least_2_h += +(count >= 2);
  }
  return result;
}
export function canResume(prior, inputs, outputHash) {
  return !!prior && prior.output_sha256 === outputHash &&
    Object.keys(inputs).length === Object.keys(prior.inputs).length &&
    Object.keys(inputs).every(k => prior.inputs[k] === inputs[k]);
}
function compareWindows(states, existing, label) {
  const interval = r => ({ start_utc: utc(r.start_i), end_utc: utc(r.end_i), duration_h: r.duration_h,
    clipped_start: r.clipped_start, clipped_end: r.clipped_end });
  const visible = runs(states).map(interval);
  const gaps = runs(states.map(v => 1 - v)).map(interval)
    .sort((a, b) => b.duration_h - a.duration_h || a.start_utc.localeCompare(b.start_utc)).slice(0, 10);
  assert.deepEqual(visible, existing.visible, `${label} every visible interval/clipping`);
  assert.deepEqual(gaps, existing.longest_gaps, `${label} top10 gaps/clipping`);
  assert.equal(states.reduce((a, b) => a + b, 0), existing.visible_hours, `${label} hours`);
}

export async function generate(root = ROOT, force = false) {
  const start = performance.now(), cpuStart = process.cpuUsage();
  const read = rel => fs.readFile(path.join(root, rel));
  const hashTextFile = async rel => textHash(await read(rel));
  const reportFile = path.join(root, 'docs/detail_z1_generation.json');
  const indexFile = path.join(root, 'web/data/detail/time_stats/index.json');
  let previous = {};
  try { previous = JSON.parse(await fs.readFile(reportFile)); } catch { /* First run. */ }
  // Unpublish before even validating input headers; an invalid source must not leave a fresh-looking index.
  await fs.rm(indexFile, { force: true });
  const report = { format: 'detail-time-stats-generation-v1', started_utc: new Date().toISOString(), complete: false,
    cpu_workers: 1, gpu_used: false, hash_convention: 'SHA256; UTF-8 text CRLF normalized to LF; ephem binary unchanged',
    verification_scope: 'Author-side exact core/metrics/windows parity; independent team-member verification pending',
    computed: [], failures: [] };
  await atomicJSON(reportFile, report);
  try {
  const { core } = await actualCore(root);
  const ephem = await loadEphemeris(root, core);
  const sites = JSON.parse(await read('web/data/sites.json'));
  assert.equal(sites.length, 33, 'Complete 33-site catalogue required');
  assert.equal(new Set(sites.map(s => s.id)).size, 33);
  const stationsBytes = await read('web/data/korea/stations.json'), stations = JSON.parse(stationsBytes);
  assert.equal(stations.mock, false); assert.equal(stations.start, START);
  assert.equal(stations.step_h, 1); assert.equal(stations.n, ephem.n); assert.equal(stations.min_el_deg, 10);
  assert(stations.bit_order.startsWith('LSB-first'));
  const shared = { core_sha256: await hashTextFile('web/js/core.js'), ephem_sha256: ephem.ephem_sha256,
    ephem_meta_sha256: await hashTextFile('web/data/ephem.json'), sites_sha256: await hashTextFile('web/data/sites.json'),
    stations_sha256: textHash(stationsBytes), producer_sha256: textHash(await fs.readFile(fileURLToPath(import.meta.url))),
    helper_sha256: await hashTextFile('pipeline/cache_metrics.mjs') };
    for (const site of sites) {
      const siteStart = performance.now();
      const horizonBytes = await read(`web/data/horizon/${site.id}.json`), h = JSON.parse(horizonBytes);
      validateHorizon(site, h);
      const metricsBytes = await read(`web/data/metrics/${site.id}.json`);
      const windowsBytes = await read(`web/data/windows/${site.id}.json`);
      const inputs = { ...shared, horizon_sha256: textHash(horizonBytes),
        metrics_sha256: textHash(metricsBytes), windows_sha256: textHash(windowsBytes) };
      const output = path.join(root, `web/data/detail/time_stats/${site.id}.json`);
      const prior = previous.computed?.find(r => r.id === site.id);
      let outputHash;
      try { outputHash = textHash(await fs.readFile(output)); } catch { /* Missing result. */ }
      if (!force && canResume(prior, inputs, outputHash)) {
        report.computed.push({ ...prior, resumed: true });
        await atomicJSON(reportFile, report); continue;
      }
      core.state.horizons.set(site.id, h);
      const sun = new Uint8Array(ephem.n), earth = new Uint8Array(ephem.n);
      let both = 0;
      for (let i = 0; i < ephem.n; i++) {
        sun[i] = +core.sunlit(site, i); earth[i] = +core.earthVisible(site, i); both += sun[i] & earth[i];
      }
      const sunRuns = runStats(sun), earthRuns = runStats(earth);
      const dark = runStats(sun.map(v => 1 - v)), noEarth = runStats(earth.map(v => 1 - v));
      const metrics = JSON.parse(metricsBytes), windows = JSON.parse(windowsBytes);
      const measured = { sun_frac: sunRuns.total_h / ephem.n, earth_frac: earthRuns.total_h / ephem.n,
        both_frac: both / ephem.n, longest_dark_h: dark.longest_h };
      for (const [key, value] of Object.entries(measured)) assert.equal(value, metrics[key], `${site.id} metrics ${key}`);
      assert.equal(windows.n, ephem.n); assert.equal(windows.start_utc, START); assert.equal(windows.end_utc, END);
      compareWindows(sun, windows.sun, `${site.id} Sun`); compareWindows(earth, windows.earth, `${site.id} Earth`);
      const result = { format: 'detail-time-stats-v1', id: site.id, lat: site.lat, lon: site.lon,
        window: { start_utc: START, end_utc: END, step_h: 1, n: ephem.n },
        sunlit_h: sunRuns.total_h, earth_visible_h: earthRuns.total_h, both_h: both,
        dark_runs: dark, no_earth_runs: noEarth, sunlit_runs: sunRuns,
        station_link_h: stationHours(earth, stations.stations),
        parity: { metrics_exact: true, windows_exact: true }, source: inputs, complete: true, mock: false };
      await atomicJSON(output, result);
      report.computed.push({ id: site.id, inputs, output_sha256: textHash(await fs.readFile(output)),
        resumed: false, compute_elapsed_s: (performance.now() - siteStart) / 1000, ...measured });
      await atomicJSON(reportFile, report);
      console.log(`${site.id}: sun ${result.sunlit_h} h; Earth ${result.earth_visible_h} h; exact parity PASS`);
    }
    const index = { format: 'detail-time-stats-v1', window: { start_utc: START, end_utc: END, step_h: 1, n: ephem.n },
      ids: report.computed.map(r => r.id), sha256: Object.fromEntries(report.computed.map(r => [r.id, r.output_sha256])),
      hash_convention: report.hash_convention, station_ids: stations.stations.map(s => s.id),
      definitions: { sunlit: 'core.sunVisibleFraction >= 0.5', earth: 'Earth centre strictly above terrain horizon',
        cells: 'Hour i represents [i,i+1); no sub-hour transitions', station_link: 'Earth visible AND station Moon elevation >= 10 degrees',
        runs: 'count/mean_h/longest_h include window-clipped observed runs; complete_* exclude clipped runs; means null when count=0',
        clipping: 'clipped_runs contains each edge-cut run once; its observed duration is only a lower bound on its full duration' },
      source_urls: [...new Set(['https://naif.jpl.nasa.gov/pub/naif/generic_kernels/', ...stations.stations.map(s => s.source_url)])],
      verification: 'Author-side exact parity for all 33 sites; independent team-member verification pending', complete: true, mock: false };
    assert.equal(index.ids.length, 33);
    await atomicJSON(indexFile, index); report.complete = true;
  } catch (e) {
    report.failures.push({ message: e.message }); throw e;
  } finally {
    const cpu = process.cpuUsage(cpuStart);
    report.elapsed_s = (performance.now() - start) / 1000;
    report.cpu_s = (cpu.user + cpu.system) / 1e6; report.peak_rss_mb = process.resourceUsage().maxRSS / 1024;
    report.finished_utc = new Date().toISOString(); await atomicJSON(reportFile, report);
    console.log(JSON.stringify({ complete: report.complete, sites: report.computed.length, elapsed_s: report.elapsed_s,
      resumed: report.computed.filter(r => r.resumed).length, failures: report.failures }));
  }
  return report;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.slice(2).some(a => a !== '--force')) throw Error('Only --force is accepted');
  await generate(ROOT, process.argv.includes('--force'));
}
