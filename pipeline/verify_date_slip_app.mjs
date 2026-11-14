/** Card 19 cross-check: 3 (site, landing day) cells of web/data/date_slip/<ID>.json against the app's own
 * core.metrics(site, i0, i0 + 14*24 - 1) - the per-period metric the landing-date scan reproduces.
 *   node pipeline/verify_date_slip_app.mjs   -> adds "app_cells" to docs/date_slip_check.json */
import fs from 'node:fs/promises';
import path from 'node:path';
import { ROOT, actualCore, loadEphemeris } from './cache_metrics.mjs';

const CELLS = [['ARTEMIS_HAWORTH', '2026-11-20'], ['APOLLO17', '2027-03-01'], ['SHACKLETON_RIM', '2027-04-18']];
const { core } = await actualCore(ROOT); await loadEphemeris(ROOT, core);
const sites = JSON.parse(await fs.readFile(path.join(ROOT, 'web/data/sites.json')));
const out = [];
for (const [id, day] of CELLS) {
  const site = sites.find(s => s.id === id);
  const h = JSON.parse(await fs.readFile(path.join(ROOT, `web/data/horizon/${id}.json`)));
  core.state.horizons.clear(); core.state.horizons.set(id, h);
  const rec = JSON.parse(await fs.readFile(path.join(ROOT, `web/data/date_slip/${id}.json`)));
  const k = Math.round((Date.parse(day + 'T00:00:00Z') - Date.parse(rec.first_landing + 'T00:00:00Z')) / 86400e3);
  const i0 = (Date.parse(day + 'T00:00:00Z') - core.T0_MS) / 3600e3;
  const m = core.metrics(site, i0, i0 + rec.days_after_landing * 24 - 1);
  const app = Object.fromEntries(Object.entries(m).map(([key, v]) => [key, Math.round(v * 1e4) / 1e4]));
  const stored = Object.fromEntries(Object.keys(app).map(key => [key, rec.series[key][k]]));
  const match = Object.keys(app).every(key => app[key] === stored[key]);
  out.push({ id, landing: day, app, stored, match_4dp: match });
  console.log(id, day, JSON.stringify(app), JSON.stringify(stored), match ? 'MATCH' : 'DIFF');
}
const file = path.join(ROOT, 'docs/date_slip_check.json');
let prev = {}; try { prev = JSON.parse(await fs.readFile(file, 'utf8')); } catch {}
prev.app_cells = { method: 'actual web/js/core.js metrics(site, i0, i0 + 335)', all_match_4dp: out.every(x => x.match_4dp), cells: out };
await fs.writeFile(file, JSON.stringify(prev, null, 1));
