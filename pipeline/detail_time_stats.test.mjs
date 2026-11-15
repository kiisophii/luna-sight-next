import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { ROOT } from './cache_metrics.mjs';
const api = await import('./detail_time_stats.mjs').catch(e => {
  if (e.code === 'ERR_MODULE_NOT_FOUND') return {};
  throw e;
});

test('observed runs retain both clipped edges and exclude them from complete means', () => {
  assert.equal(typeof api.runStats, 'function');
  const r = api.runStats(Uint8Array.from([1, 1, 0, 1, 1, 1, 0, 1]));
  assert.equal(r.count, 3); assert.equal(r.total_h, 6); assert.equal(r.mean_h, 2);
  assert.equal(r.longest_h, 3); assert.equal(r.complete_count, 1);
  assert.equal(r.complete_mean_h, 3); assert.equal(r.complete_longest_h, 3);
  assert.deepEqual(r.clipped_runs, [
    { start_i: 0, end_i: 2, duration_h: 2, clipped_start: true, clipped_end: false },
    { start_i: 7, end_i: 8, duration_h: 1, clipped_start: false, clipped_end: true },
  ]);
});
test('no outage gives null mean; whole-window outage is one doubly clipped run', () => {
  assert.equal(typeof api.runStats, 'function');
  const zero = api.runStats(Uint8Array.from([0, 0]));
  assert.equal(zero.count, 0); assert.equal(zero.mean_h, null); assert.equal(zero.longest_h, 0);
  const all = api.runStats(Uint8Array.from([1, 1]));
  assert.equal(all.count, 1); assert.equal(all.complete_count, 0); assert.equal(all.complete_mean_h, null);
  assert.deepEqual(all.clipped_runs, [{ start_i: 0, end_i: 2, duration_h: 2, clipped_start: true, clipped_end: true }]);
});
test('station bit decoding is LSB-first across bytes and requires lunar Earth visibility', () => {
  assert.equal(typeof api.stationHours, 'function');
  const earth = Uint8Array.from([1, 1, 0, 1, 1, 1, 1, 1, 1]);
  const stations = [
    { id: 'KDSA', bits_b64: Buffer.from([5, 1]).toString('base64') },
    { id: 'DSN_GOLDSTONE', bits_b64: Buffer.from([1, 1]).toString('base64') },
    { id: 'DSN_MADRID', bits_b64: Buffer.from([128, 0]).toString('base64') },
    { id: 'DSN_CANBERRA', bits_b64: Buffer.from([128, 0]).toString('base64') },
  ];
  assert.deepEqual(api.stationHours(earth, stations), { kdsa_h: 2, at_least_1_h: 3, at_least_2_h: 3 });
  assert.throws(() => api.stationHours(earth, stations.slice(1)), /four|KDSA/);
  assert.throws(() => api.stationHours(earth, stations.map(s => ({ ...s, bits_b64: 'AA==' }))), /length/);
});
test('resume rejects changed inputs and modified output, accepting exact cached result', () => {
  assert.equal(typeof api.canResume, 'function');
  const prior = { inputs: { core: 'a', stations: 'b' }, output_sha256: 'c' };
  assert.equal(api.canResume(prior, { stations: 'b', core: 'a' }, 'c'), true);
  assert.equal(api.canResume(prior, { core: 'a', stations: 'd' }, 'c'), false);
  assert.equal(api.canResume(prior, prior.inputs, 'd'), false);
});
test('complete real-data generation resumes, repairs modified output, and unpublishes invalid inputs', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'detail-z1-'));
  try {
    for (const rel of ['web/js/core.js', 'pipeline/cache_metrics.mjs', 'web/data/sites.json', 'web/data/ephem.json',
      'web/data/ephem.bin', 'web/data/korea/stations.json', 'web/data/horizon', 'web/data/metrics', 'web/data/windows']) {
      await fs.mkdir(path.dirname(path.join(root, rel)), { recursive: true });
      await fs.cp(path.join(ROOT, rel), path.join(root, rel), { recursive: true });
    }
    assert.equal((await api.generate(root)).computed.length, 33);
    assert.equal((await api.generate(root)).computed.filter(r => r.resumed).length, 33);
    await fs.appendFile(path.join(root, 'web/data/detail/time_stats/APOLLO17.json'), ' ');
    assert.equal((await api.generate(root)).computed.filter(r => r.resumed).length, 32);
    const stationFile = path.join(root, 'web/data/korea/stations.json');
    const stations = JSON.parse(await fs.readFile(stationFile)); stations.mock = true;
    await fs.writeFile(stationFile, JSON.stringify(stations));
    await assert.rejects(api.generate(root));
    await assert.rejects(fs.access(path.join(root, 'web/data/detail/time_stats/index.json')));
    const report = JSON.parse(await fs.readFile(path.join(root, 'docs/detail_z1_generation.json')));
    assert.equal(report.complete, false); assert.equal(report.failures.length, 1);
  } finally { await fs.rm(root, { recursive: true, force: true }); }
});
