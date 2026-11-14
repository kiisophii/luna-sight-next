/** UI audit reference values (docs/ui_data_audit.md): for every catalogue site, the numbers the UI should show
 * at selected hour T with a P-day analysis period starting at the day of T, computed from web/data/*.json and the
 * actual web/js/core.js (Node) - not from the running page.
 *   node pipeline/ui_audit_ref.mjs <T hour index> <P days>  > ref.json
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { ROOT, actualCore, loadEphemeris } from './cache_metrics.mjs';

const T = Number(process.argv[2] ?? 10086), P = Number(process.argv[3] ?? 30);
const read = async f => JSON.parse(await fs.readFile(path.join(ROOT, 'web/data', f), 'utf8'));
const { core } = await actualCore(ROOT);
await loadEphemeris(ROOT, core);
const sites = await read('sites.json');
const i0 = Math.floor(T / 24) * 24, i1 = Math.min(i0 + P * 24 - 1, core.state.n - 1);

function bits(b64, n) {
  const bin = Buffer.from(b64, 'base64'), out = new Uint8Array(n);
  for (let k = 0; k < n; k++) out[k] = (bin[k >> 3] >> (k & 7)) & 1;
  return out;
}
const st = await read('korea/stations.json');
const SB = Object.fromEntries(st.stations.map(s => [s.id, bits(s.bits_b64, st.n)]));

function segHours(segs, a, b) {
  const r = { direct: 0, via: 0, none: 0, total: 0 };
  for (const [s, len, code] of segs) {
    const lo = Math.max(s, a), hi = Math.min(s + len - 1, b);
    if (hi < lo) continue;
    const h = hi - lo + 1; r.total += h;
    r[code === 1 ? 'direct' : code === 2 ? 'via' : 'none'] += h;
  }
  return r;
}
function longestNone(segs, a, b) {
  let best = 0, run = 0, prevEnd = null;
  for (const [s, len, code] of segs) {
    const lo = Math.max(s, a), hi = Math.min(s + len - 1, b);
    if (hi < lo) continue;
    if (code === 0) { run += hi - lo + 1; best = Math.max(best, run); } else run = 0;
  }
  return best;
}

const out = { T, P, i0, i1, sites: {} };
for (const site of sites) {
  const r = { id: site.id, name: site.name };
  let h = null;
  try { h = await read(`horizon/${site.id}.json`); } catch { /* pending */ }
  core.state.horizons.clear();
  if (h) core.state.horizons.set(site.id, h);
  const s = core.sunAzEl(site, T), e = core.earthAzEl(site, T);
  r.inst = { sun_el: s.el, sun_az: s.az, earth_el: e.el, earth_az: e.az,
    sun_mask: core.horizonAt(site, s.az), earth_mask: core.horizonAt(site, e.az),
    sunlit: core.sunlit(site, T), earth_visible: core.earthVisible(site, T),
    until_sunset: core.untilSunset(site, T), until_sunrise: core.untilSunrise(site, T),
    until_earthset: core.untilEarthset(site, T), until_earthrise: core.untilEarthrise(site, T) };
  r.period = core.metrics(site, i0, i1);
  r.first14 = core.metrics(site, i0, i0 + 14 * 24 - 1);
  // Korea / DSN over the period
  let k = 0, g = 0, m = 0, c = 0, any = 0, only = 0, ev = 0, evK = 0, evD = 0;
  for (let i = i0; i <= i1; i++) {
    const kd = SB.KDSA[i], d = SB.DSN_GOLDSTONE[i] | SB.DSN_MADRID[i] | SB.DSN_CANBERRA[i];
    k += kd; g += SB.DSN_GOLDSTONE[i]; m += SB.DSN_MADRID[i]; c += SB.DSN_CANBERRA[i]; any += d; only += kd & !d;
    if (core.earthVisible(site, i)) { ev++; evK += kd; evD += d; }
  }
  r.korea = { hours: i1 - i0 + 1, KDSA: k, DSN_GOLDSTONE: g, DSN_MADRID: m, DSN_CANBERRA: c, any_dsn: any, only_kdsa: only,
    site_earth: ev, site_earth_kdsa: evK, site_earth_dsn: evD };
  // relay (15 m, as the story panel)
  try {
    const rel = await read(`relay/${site.id}.json`);
    r.relay = {};
    rel.params.heights_m.forEach((hm, j) => {
      const net = rel.networks[j], sh = segHours(net.timeline.segments, i0, i1);
      r.relay[String(Number(hm))] = { ...sh, longest_none: longestNone(net.timeline.segments, i0, i1), n_towers: net.towers.length,
        link_frac_by_n: net.link_frac_by_n, best: net.towers[0] || null };
    });
    r.relay_lander_earth_frac = rel.lander.earth_frac;
  } catch { r.relay = null; }
  // local map, catalogue node and radial ranges of "both"
  try {
    const loc = await read(`local/${site.id}.json`);
    const c0 = loc.points[220];
    r.local = { centre: { sun_frac: c0.sun_frac, earth_frac: c0.earth_frac, both_frac: c0.both_frac, longest_dark_h: c0.longest_dark_h, h0_m: c0.h0_m } };
    for (const km of [1, 3, 5, 10]) {
      const sel = loc.points.filter(p => Math.hypot(p.e_m, p.n_m) <= km * 1000 + 1e-6).map(p => p.both_frac);
      r.local[`r${km}`] = [Math.min(...sel), Math.max(...sel)];
    }
  } catch { r.local = null; }
  try { r.slip = (await read(`date_slip/${site.id}.json`)).slip; } catch { r.slip = null; }
  try {
    const mo = await read(`monthly/${site.id}.json`);
    const L = mo.lunation.sun_frac, lat = mo.subsolar_lat_deg.min.map((a, j) => (a + mo.subsolar_lat_deg.max[j]) / 2);
    const S = [], N = [];
    lat.forEach((v, j) => { if (v <= -1) S.push(L[j]); else if (v >= 1) N.push(L[j]); });
    const mean = a => a.reduce((p, q) => p + q, 0) / a.length;
    let kb = 0, kw = 0; L.forEach((v, j) => { if (v > L[kb]) kb = j; if (v < L[kw]) kw = j; });
    r.seasons = { min: L[kw], max: L[kb], best: mo.months[kb], worst: mo.months[kw], dS_pp: (mean(S) - mean(N)) * 100,
      dark_min: Math.min(...mo.series.longest_dark_h), dark_max: Math.max(...mo.series.longest_dark_h) };
  } catch { r.seasons = null; }
  out.sites[site.id] = r;
}
process.stdout.write(JSON.stringify(out));
