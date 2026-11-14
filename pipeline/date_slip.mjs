/** Card 19 - landing-date slip table: "how much changes if the landing slips 1-2 weeks?"
 *
 * For every catalogue site with a real horizon and every landing day 2026-01-01 .. 2027-12-31 (00:00 UTC),
 * the metrics of the first 14 days after landing, with the ACTUAL web/js/core.js definitions, hourly
 * (exactly what the app's landing-date scan computes: core.sunlit / core.earthVisible per hour, then a
 * sliding 14 x 24 h window; best/worst ranking = highest/lowest both_frac, ties -> shorter longest dark).
 *
 *   node pipeline/date_slip.mjs            -> web/data/date_slip/<ID>.json, docs/date_slip.md, docs/date_slip_summary.json
 *
 * Contract: docs/data_contract.md section 15 (proposal).
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { ROOT, sha, atomicJSON, actualCore, loadEphemeris, validateHorizon } from './cache_metrics.mjs';

const N_DAYS_AFTER = 14;
const FIRST_DAY = '2026-01-01', LAST_DAY = '2027-12-31';
const SLIPS = [7, 14];
const METRICS = ['sun_frac', 'earth_frac', 'both_frac', 'longest_dark_h'];
const T0 = Date.UTC(2026, 0, 1);
const dayIndex = iso => Math.round((Date.parse(iso + 'T00:00:00Z') - T0) / 86400e3);
const isoDay = d => new Date(T0 + d * 86400e3).toISOString().slice(0, 10);
const r4 = x => Math.round(x * 1e4) / 1e4;

function median(a) {
  const s = [...a].sort((x, y) => x - y), n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

/** Same maths as web/js/landing_scan.js compute(): hourly flags, sliding window per landing day. */
export function scanSite(core, site, d0, d1, nDays) {
  const win = nDays * 24, start = d0 * 24, last = d1 * 24, nh = last - start + win;
  if (start + nh - 1 > core.state.n - 1) throw Error('window runs past the ephemeris');
  const sun = new Uint8Array(nh), earth = new Uint8Array(nh);
  for (let k = 0; k < nh; k++) { sun[k] = core.sunlit(site, start + k) ? 1 : 0; earth[k] = core.earthVisible(site, start + k) ? 1 : 0; }
  const cs = new Int32Array(nh + 1), ce = new Int32Array(nh + 1), cb = new Int32Array(nh + 1);
  for (let k = 0; k < nh; k++) { cs[k + 1] = cs[k] + sun[k]; ce[k + 1] = ce[k] + earth[k]; cb[k + 1] = cb[k] + (sun[k] & earth[k]); }
  const days = [];
  for (let d = start; d <= last; d += 24) {
    const k0 = d - start, k1 = k0 + win;
    let run = 0, longest = 0;
    for (let k = k0; k < k1; k++) { run = sun[k] ? 0 : run + 1; if (run > longest) longest = run; }
    days.push({ sun_frac: (cs[k1] - cs[k0]) / win, earth_frac: (ce[k1] - ce[k0]) / win,
                both_frac: (cb[k1] - cb[k0]) / win, longest_dark_h: longest });
  }
  let best = 0, worst = 0;
  days.forEach((x, k) => {
    const B = days[best], W = days[worst];
    if (x.both_frac > B.both_frac + 1e-9 || (Math.abs(x.both_frac - B.both_frac) < 1e-9 && x.longest_dark_h < B.longest_dark_h)) best = k;
    if (x.both_frac < W.both_frac - 1e-9 || (Math.abs(x.both_frac - W.both_frac) < 1e-9 && x.longest_dark_h > W.longest_dark_h)) worst = k;
  });
  return { days, best, worst };
}

/** Change when the landing slips by s days: delta = metric(d + s) - metric(d) for every d with d + s in range. */
function slipStats(days, s, d0) {
  const out = {};
  for (const m of METRICS) {
    const deltas = [];
    for (let k = 0; k + s < days.length; k++) deltas.push(days[k + s][m] - days[k][m]);
    const adverseSign = m === 'longest_dark_h' ? 1 : -1;            // worse = more dark / less visibility
    let wk = 0;
    deltas.forEach((v, k) => { if (v * adverseSign > deltas[wk] * adverseSign) wk = k; });
    const scale = m === 'longest_dark_h' ? 1 : 100;                    // fractions -> percentage points
    out[m] = { unit: m === 'longest_dark_h' ? 'h' : 'pp',
               median_abs_change: r4(median(deltas.map(Math.abs)) * scale),
               worst_change: r4(deltas[wk] * scale), worst_from: isoDay(d0 + wk), worst_to: isoDay(d0 + wk + s),
               share_of_days_worse: r4(deltas.filter(v => v * adverseSign > 1e-12).length / deltas.length) };
  }
  return out;
}

async function main() {
  const { core, hash } = await actualCore(ROOT);
  const eph = await loadEphemeris(ROOT, core);
  const sitesBytes = await fs.readFile(path.join(ROOT, 'web/data/sites.json'));
  const sites = JSON.parse(sitesBytes);
  const d0 = dayIndex(FIRST_DAY), d1 = dayIndex(LAST_DAY);
  const summary = { generated_utc: new Date().toISOString(), core_sha256: hash, ephem_sha256: eph.ephem_sha256,
                    sites_sha256: sha(sitesBytes), first_landing: FIRST_DAY, last_landing: LAST_DAY,
                    days_after_landing: N_DAYS_AFTER, sites: [], skipped: [] };
  for (const site of sites) {
    let h, hb;
    try { hb = await fs.readFile(path.join(ROOT, `web/data/horizon/${site.id}.json`)); h = JSON.parse(hb); validateHorizon(site, h); }
    catch (e) { summary.skipped.push({ id: site.id, reason: e.code === 'ENOENT' ? 'missing horizon' : e.message }); continue; }
    core.state.horizons.clear(); core.state.horizons.set(site.id, h);
    const t = Date.now();
    const { days, best, worst } = scanSite(core, site, d0, d1, N_DAYS_AFTER);
    const pick = k => ({ landing: isoDay(d0 + k), ...Object.fromEntries(METRICS.map(m => [m, r4(days[k][m])])) });
    const rec = {
      id: site.id, first_landing: FIRST_DAY, last_landing: LAST_DAY, n_landings: days.length,
      days_after_landing: N_DAYS_AFTER, step_h: 1,
      definition: 'actual web/js/core.js sunlit (solar disc >= 50 % above the mask) and earthVisible (Earth centre above the mask), hourly, first 14 x 24 h after 00:00 UTC of the landing day',
      series: Object.fromEntries(METRICS.map(m => [m, days.map(x => (m === 'longest_dark_h' ? x[m] : r4(x[m])))])),
      best: pick(best), worst: pick(worst),
      range: Object.fromEntries(METRICS.map(m => [m, [r4(Math.min(...days.map(x => x[m]))), r4(Math.max(...days.map(x => x[m])))]])),
      slip: Object.fromEntries(SLIPS.map(s => [`+${s}d`, slipStats(days, s, d0)])),
      horizon_sha256: sha(hb), core_sha256: hash, mock: false,
    };
    await atomicJSON(path.join(ROOT, `web/data/date_slip/${site.id}.json`), rec);
    summary.sites.push({ id: site.id, name: site.name, group: site.group, best: rec.best, worst: rec.worst, range: rec.range, slip: rec.slip });
    console.log(`${site.id}: best ${rec.best.landing} both ${rec.best.both_frac}, worst ${rec.worst.landing} both ${rec.worst.both_frac}, ` +
                `+14d worst dark ${rec.slip['+14d'].longest_dark_h.worst_change} h (${((Date.now() - t) / 1000).toFixed(1)} s)`);
  }
  await atomicJSON(path.join(ROOT, 'docs/date_slip_summary.json'), summary);
  console.log(JSON.stringify({ computed: summary.sites.length, skipped: summary.skipped.length }));
}

if (process.argv[1] && import.meta.url.endsWith(path.basename(process.argv[1]))) main();
