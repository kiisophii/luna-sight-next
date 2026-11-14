/** Independent Node edge checks: read exported UTC edges and rerun actual core predicates. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { ROOT, actualCore, loadEphemeris, validateHorizon, atomicJSON } from './cache_metrics.mjs';
import { splitRuns } from './build_windows.mjs';

// Run grouping, clipped boundaries and UTC year crossing have exact expectations.
assert.equal(splitRuns(new Uint8Array([0, 0, 1, 1, 0])).visible[0].duration_h, 2);
assert.equal(splitRuns(new Uint8Array([0, 0, 1, 1, 0])).longest_gaps[0].duration_h, 2);
assert.deepEqual(splitRuns(new Uint8Array([1, 1])).longest_gaps, []);
assert.equal(splitRuns(new Uint8Array([0, 0])).longest_gaps[0].clipped_end, true);
assert.equal(splitRuns(new Uint8Array([1, 1])).visible[0].end_utc, '2026-01-01T02:00:00Z');

const { core } = await actualCore(ROOT);
await loadEphemeris(ROOT, core);
const sites = JSON.parse(await fs.readFile(path.join(ROOT, 'web/data/sites.json')));
const report = { passed: true, tolerance_h: 0, requested_tolerance_h: 1,
  definition: 'Actual core.js predicates re-evaluated at each reported edge and the preceding hour; clipped domain boundaries are not treated as transitions.',
  site_checks: [] };
const rows = ['# Card 15-B verification', '',
  'Actual unchanged core.js in Node is the reference. Twenty internal visible-window edges per site are checked independently of the production run-grouping loop. The hourly transition must occur at the exact reported UTC hour; domain-clipped edges are not physical rise/set assertions.', '',
  '| Site | Edges checked | Maximum difference (h) | Whole-series membership | Fraction / longest Sun gap | Result |',
  '|---|---:|---:|---|---|---|'];
for (const id of ['APOLLO17', 'CHANGE4', 'ARTEMIS_HAWORTH', 'SHACKLETON_RIM']) {
  const site = sites.find(s => s.id === id);
  const h = JSON.parse(await fs.readFile(path.join(ROOT, `web/data/horizon/${id}.json`)));
  validateHorizon(site, h); core.state.horizons.set(id, h);
  const doc = JSON.parse(await fs.readFile(path.join(ROOT, `web/data/windows/${id}.json`)));
  const t0 = Date.parse(doc.start_utc), hour = text => (Date.parse(text) - t0) / 3600000;
  const pool = [], checked = [];
  for (const body of ['sun', 'earth']) {
    const predicate = body === 'sun' ? core.sunlit : core.earthVisible;
    const membership = new Uint8Array(core.state.n);
    for (const w of doc[body].visible) {
      const a = hour(w.start_utc), b = hour(w.end_utc);
      membership.fill(1, a, b);
      if (!w.clipped_start) pool.push({ body, hour: a, kind: 'start', utc: w.start_utc });
      if (!w.clipped_end) pool.push({ body, hour: b, kind: 'end', utc: w.end_utc });
    }
    const actual = new Uint8Array(core.state.n);
    for (let i = 0; i < core.state.n; i++) {
      actual[i] = +predicate(site, i);
      assert.equal(membership[i], actual[i], `${id} ${body} ${i}`);
    }
    assert.equal(membership.reduce((a, b) => a + b, 0), doc[body].visible_hours);
    // Independent traversal of actual states, not the production splitRuns function.
    const expectedVisible = [], expectedGaps = [];
    let cursor = 0;
    while (cursor < actual.length) {
      const start = cursor, state = actual[cursor];
      do { cursor++; } while (cursor < actual.length && actual[cursor] === state);
      const utc = i => new Date(t0 + i * 3600000).toISOString().replace('.000Z', 'Z');
      const expected = { start_utc: utc(start), end_utc: utc(cursor), duration_h: cursor - start,
        clipped_start: start === 0, clipped_end: cursor === actual.length };
      (state ? expectedVisible : expectedGaps).push(expected);
    }
    expectedGaps.sort((a, b) => b.duration_h - a.duration_h || a.start_utc.localeCompare(b.start_utc));
    assert.deepEqual(doc[body].visible, expectedVisible, `${id} ${body} visible/clipping`);
    assert.deepEqual(doc[body].longest_gaps, expectedGaps.slice(0, 10), `${id} ${body} top-10 gaps/clipping`);
  }
  // Spread selections across time and include both bodies when their actual windows have edges.
  pool.sort((a, b) => a.hour - b.hour || a.body.localeCompare(b.body));
  assert(pool.length >= 20, `${id} must have at least 20 genuine transitions`);
  const chosen = new Set(Array.from({ length: 20 }, (_, i) => Math.floor(i * (pool.length - 1) / 19)));
  for (const ix of chosen) {
    const edge = pool[ix], predicate = edge.body === 'sun' ? core.sunlit : core.earthVisible;
    const before = predicate(site, edge.hour - 1), after = predicate(site, edge.hour);
    assert.equal(before, edge.kind === 'end'); assert.equal(after, edge.kind === 'start');
    checked.push({ ...edge, before, after, edge_difference_h: 0, passed: true });
  }
  const metrics = core.metrics(site);
  assert.equal(doc.sun.visible_hours / core.state.n, metrics.sun_frac);
  assert.equal(doc.earth.visible_hours / core.state.n, metrics.earth_frac);
  assert.equal(doc.sun.longest_gaps[0]?.duration_h ?? 0, metrics.longest_dark_h);
  report.site_checks.push({ id, edges_checked: checked.length, max_edge_difference_h: 0,
    all_43824_hour_memberships_match_each_body: true,
    full_visible_lists_and_top10_gaps_and_clipping_match_each_body: true,
    metric_summary_matches: true, edges: checked });
  rows.push(`| ${id} | ${checked.length} | 0 | PASS (43,824 hours per body; lists/gaps/clipping) | PASS | PASS |`);
}
report.n_edges_checked = report.site_checks.reduce((n, s) => n + s.edges_checked, 0);
rows.push('', 'Scope: sampled hourly visibility, not sub-hour rise/set accuracy or independent DEM accuracy. SHACKLETON_RIM is included with its corrected-coordinate real horizon from main.', '',
  'Reproduce:', '', '```sh', 'node pipeline/build_windows.mjs', 'node pipeline/test_windows.mjs', 'python pipeline/check_contract.py', '```', '');
await atomicJSON(path.join(ROOT, 'docs/windows_verification.json'), report);
await fs.writeFile(path.join(ROOT, 'docs/windows_verification.md'), rows.join('\n'));
console.log('PASS:', report.n_edges_checked, 'edges; four complete five-year membership/metric checks');
