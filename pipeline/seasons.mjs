/** Seasons 2026-2030: monthly (calendar month, UTC) metrics for every catalogue site.
 *
 * Uses the ACTUAL web/js/core.js: core.metrics(site, i0, i1) over the hours of each month (hourly samples,
 * core.sunlit = >= 50 % of the solar disc above the terrain mask, core.earthVisible = Earth centre above the mask,
 * longest_dark_h = longest run of not-sunlit hours INSIDE the month). Per month it also records the range of the
 * subsolar and sub-Earth latitude (selenographic, MOON_ME) from web/data/ephem.bin, which explains the season.
 *
 *   node pipeline/seasons.mjs   -> web/data/monthly/<ID>.json, docs/seasons_summary.json
 *
 * Contract: docs/data_contract.md section 17 (proposal). Independent check: pipeline/verify_seasons.py.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { ROOT, sha, atomicJSON, actualCore, loadEphemeris, validateHorizon } from './cache_metrics.mjs';

const T0 = Date.UTC(2026, 0, 1);
const R2D = 180 / Math.PI;
const r4 = x => Math.round(x * 1e4) / 1e4;
const r3 = x => Math.round(x * 1e3) / 1e3;
export const LUN_HALF_H = 354;   // lunation window = 2*354+1 = 709 h ~ 29.54 d (synodic month 29.53 d = 708.7 h)
/** Centre hour of a month (first hour + half its length, floored) - shared with pipeline/verify_seasons.py. */
export const monthMid = (i0, i1) => i0 + Math.floor((i1 - i0 + 1) / 2);

/** 60 calendar months 2026-01 .. 2030-12 as [label, first hour, last hour] (hour index from 2026-01-01T00Z). */
export function months(n) {
  const out = [];
  for (let y = 2026; y <= 2030; y++) for (let m = 0; m < 12; m++) {
    const i0 = (Date.UTC(y, m, 1) - T0) / 3600e3, i1 = (Date.UTC(y, m + 1, 1) - T0) / 3600e3 - 1;
    out.push([`${y}-${String(m + 1).padStart(2, '0')}`, i0, i1]);
  }
  if (out[0][1] !== 0 || out.at(-1)[2] !== n - 1) throw Error('months do not tile the ephemeris window');
  return out;
}

/** Selenographic latitude (deg) of the Sun (col0 = 0) or Earth (col0 = 3) direction at hour row i. */
const subLat = (e, i, c) => Math.asin(e[i * 6 + c + 2] / Math.hypot(e[i * 6 + c], e[i * 6 + c + 1], e[i * 6 + c + 2])) * R2D;

async function main() {
  const { core, hash } = await actualCore(ROOT);
  const eph = await loadEphemeris(ROOT, core);
  const sitesBytes = await fs.readFile(path.join(ROOT, 'web/data/sites.json'));
  const sites = JSON.parse(sitesBytes);
  const M = months(core.state.n), e = core.state.ephem;

  // per-month subsolar / sub-Earth latitude range (site-independent)
  const lat = { sun_min: [], sun_max: [], earth_min: [], earth_max: [] };
  for (const [, i0, i1] of M) {
    let smin = 99, smax = -99, emin = 99, emax = -99;
    for (let i = i0; i <= i1; i++) {
      const s = subLat(e, i, 0), g = subLat(e, i, 3);
      smin = Math.min(smin, s); smax = Math.max(smax, s); emin = Math.min(emin, g); emax = Math.max(emax, g);
    }
    lat.sun_min.push(r3(smin)); lat.sun_max.push(r3(smax)); lat.earth_min.push(r3(emin)); lat.earth_max.push(r3(emax));
  }

  const summary = { generated_utc: new Date().toISOString(), core_sha256: hash, ephem_sha256: eph.ephem_sha256,
                    sites_sha256: sha(sitesBytes), months: M.map(m => m[0]),
                    subsolar_lat_deg: { min: lat.sun_min, max: lat.sun_max }, sites: [], skipped: [] };
  for (const site of sites) {
    let h, hb;
    try { hb = await fs.readFile(path.join(ROOT, `web/data/horizon/${site.id}.json`)); h = JSON.parse(hb); validateHorizon(site, h); }
    catch (err) { summary.skipped.push({ id: site.id, reason: err.code === 'ENOENT' ? 'missing horizon' : err.message }); continue; }
    core.state.horizons.clear(); core.state.horizons.set(site.id, h);
    const s = { hours: [], sun_h: [], earth_h: [], both_h: [], sun_frac: [], earth_frac: [], both_frac: [], longest_dark_h: [] };
    const lun = { window_h: 2 * LUN_HALF_H + 1, sun_frac: [], earth_frac: [], both_frac: [] };
    for (const [, i0, i1] of M) {
      const c = monthMid(i0, i1), a = c - LUN_HALF_H, b = c + LUN_HALF_H;
      if (a < 0 || b > core.state.n - 1) throw Error('lunation window outside the ephemeris');
      const L = core.metrics(site, a, b);
      lun.sun_frac.push(r4(L.sun_frac)); lun.earth_frac.push(r4(L.earth_frac)); lun.both_frac.push(r4(L.both_frac));
      const m = core.metrics(site, i0, i1), n = i1 - i0 + 1;
      const cnt = f => { const c = Math.round(f * n); if (Math.abs(c - f * n) > 1e-6) throw Error('non-integer count'); return c; };
      s.hours.push(n); s.sun_h.push(cnt(m.sun_frac)); s.earth_h.push(cnt(m.earth_frac)); s.both_h.push(cnt(m.both_frac));
      s.sun_frac.push(r4(m.sun_frac)); s.earth_frac.push(r4(m.earth_frac)); s.both_frac.push(r4(m.both_frac));
      s.longest_dark_h.push(m.longest_dark_h);
    }
    const N = s.hours.reduce((a, b) => a + b, 0), sum = k => s[k].reduce((a, b) => a + b, 0);
    const rec = {
      id: site.id, first_month: M[0][0], last_month: M.at(-1)[0], n_months: M.length, step_h: 1,
      lunation_definition: 'same metrics over 709 h (one synodic month) centred on each month (centre = first hour + floor(hours/2)); removes the day/night aliasing of 28-31-day calendar months',
      definition: 'actual web/js/core.js metrics(site, i0, i1) over each calendar month (UTC), hourly: sunlit = solar disc >= 50 % above the mask, earthVisible = Earth centre above the mask; longest_dark_h = longest not-sunlit run inside the month (runs are cut at month boundaries)',
      months: M.map(m => m[0]), series: s, lunation: lun,
      subsolar_lat_deg: { min: lat.sun_min, max: lat.sun_max }, subearth_lat_deg: { min: lat.earth_min, max: lat.earth_max },
      total: { hours: N, sun_frac: sum('sun_h') / N, earth_frac: sum('earth_h') / N, both_frac: sum('both_h') / N,
               longest_dark_h_max_month: Math.max(...s.longest_dark_h) },
      horizon_sha256: sha(hb), core_sha256: hash, mock: false,
    };
    await atomicJSON(path.join(ROOT, `web/data/monthly/${site.id}.json`), rec);
    summary.sites.push({ id: site.id, name: site.name, group: site.group, lat: site.lat, lon: site.lon,
                         sun_frac: s.sun_frac, lun_sun_frac: lun.sun_frac, lun_earth_frac: lun.earth_frac, earth_frac: s.earth_frac, both_frac: s.both_frac, longest_dark_h: s.longest_dark_h, total: rec.total });
    console.log(`${site.id}: sun ${r4(Math.min(...s.sun_frac))}..${r4(Math.max(...s.sun_frac))}, dark ${Math.min(...s.longest_dark_h)}..${Math.max(...s.longest_dark_h)} h`);
  }
  await atomicJSON(path.join(ROOT, 'docs/seasons_summary.json'), summary);
  console.log(JSON.stringify({ computed: summary.sites.length, skipped: summary.skipped.length }));
}

if (process.argv[1] && import.meta.url.endsWith(path.basename(process.argv[1]))) main();
