// values.js — period values shared by the 3-column layout (left list, comparison tray, compare section, decision brief).
// No new maths: every number is read from LLSN.window (core.metrics), core.js instant functions, or the data files
// via diff_data.js (relay, ground stations). Results are cached per (site, period).
import * as core from './core.js';
import { relayIndex, relayFor, segmentHours, longestNone, siteStationLink } from './diff_data.js';

export const TOWER_H = 15;                       // default tower height (m) for the "assume a relay tower" switch

const relayCache = new Map();                    // `${id}|${i0}|${i1}|${h}` -> Promise
const settled = new Map();                       // same key -> resolved value (for synchronous rendering)
/** Link share with the relay-tower network of height h (m) over [i0, i1], from data/relay/<ID>.json.
 *  {state: 'ok', pct, direct, via, none, total, towers, distKm, longestNoneH} | {state: 'none'} (no file: custom point,
 *  pending terrain) — never a flat-horizon value. */
export async function relayPeriod(id, i0, i1, h = TOWER_H) {
  const key = `${id}|${i0}|${i1}|${h}`;
  if (relayCache.has(key)) return relayCache.get(key);
  const p = (async () => {
    const idx = await relayIndex();
    if (!idx.ids.includes(id)) return { state: 'none' };
    const rel = await relayFor(id);
    const j = rel.params.heights_m.findIndex(x => Number(x) === h);
    if (j < 0) return { state: 'none' };
    const net = rel.networks[j];
    const seg = segmentHours(net.timeline.segments, i0, i1);
    const near = net.towers.length ? Math.min(...net.towers.map(t => t.dist_m)) : null;
    return { state: 'ok', ...seg, pct: seg.total ? (seg.direct + seg.via) / seg.total : null, towers: net.towers.length,
      distKm: near == null ? null : near / 1000, longestNoneH: longestNone(net.timeline.segments, i0, i1), height: h };
  })().catch(e => { console.warn('relay', id, e); return { state: 'none', error: true }; });
  relayCache.set(key, p);
  p.then(v => settled.set(key, v));
  return p;
}
/** Synchronous peek (undefined while loading). */
export function relayPeek(id, i0, i1, h = TOWER_H) {
  const key = `${id}|${i0}|${i1}|${h}`;
  if (settled.has(key)) return settled.get(key);
  relayPeriod(id, i0, i1, h).then(v => settled.set(key, v));
  return undefined;
}

const gsCache = new Map();
/** Hours in [i0, i1] when the site sees the Earth AND the Moon is ≥ 10° above KDSA / any DSN station (diff_data.js). */
export function stationPeriod(site, i0, i1) {
  const key = `${site.id}|${i0}|${i1}`;
  if (!gsCache.has(key)) gsCache.set(key, siteStationLink(site, i0, i1).catch(e => { console.warn('stations', e); return { error: true }; }));
  return gsCache.get(key);
}

/** Instant state at hour i plus hours to the next change (null = no change before the end of the data). */
export function instant(site, i) {
  if (core.terrainPending(site)) return { pending: true, sunEl: core.sunAzEl(site, i).el, earthEl: core.earthAzEl(site, i).el };
  const lit = core.sunlit(site, i), up = core.earthVisible(site, i);
  return {
    lit, up,
    sunNext: lit ? core.untilSunset(site, i) : core.untilSunrise(site, i),
    earthNext: up ? core.untilEarthset(site, i) : core.untilEarthrise(site, i),
    sun: core.sunAzEl(site, i), earth: core.earthAzEl(site, i),
  };
}

/** Hour-by-hour state over [i0, i1] (Uint8Array: bit0 sunlit, bit1 Earth visible). Cached per site + period. */
const bitsCache = new Map();
export function hourBits(site, i0, i1) {
  const key = `${site.id}|${i0}|${i1}`;
  if (bitsCache.has(key)) return bitsCache.get(key);
  if (core.terrainPending(site)) return null;
  const n = i1 - i0 + 1, out = new Uint8Array(n);
  for (let k = 0; k < n; k++) out[k] = (core.sunlit(site, i0 + k) ? 1 : 0) | (core.earthVisible(site, i0 + k) ? 2 : 0);
  if (bitsCache.size > 200) bitsCache.clear();
  bitsCache.set(key, out);
  return out;
}

/** Runs of equal bits: [{start, len}] for bit mask m set. */
export function runs(bits, m) {
  const out = []; let s = -1;
  for (let k = 0; k <= bits.length; k++) {
    const on = k < bits.length && (bits[k] & m) === m;
    if (on && s < 0) s = k; else if (!on && s >= 0) { out.push({ start: s, len: k - s }); s = -1; }
  }
  return out;
}
/** Gaps (bit off) inside the period: count, longest, mean (hours). Gaps cut by the period ends count with their clipped length. */
export function gapStats(bits, m) {
  const g = []; let run = 0;
  for (let k = 0; k <= bits.length; k++) {
    const off = k < bits.length && (bits[k] & m) !== m;
    if (off) run++; else if (run) { g.push(run); run = 0; }
  }
  const on = bits.reduce((a, b) => a + ((b & m) === m ? 1 : 0), 0);
  return { on, count: g.length, longest: g.length ? Math.max(...g) : 0, mean: g.length ? g.reduce((a, b) => a + b, 0) / g.length : 0 };
}

const jsonCache = new Map();
export function getJSON(url) {
  if (!jsonCache.has(url)) jsonCache.set(url, fetch(url, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); }));
  return jsonCache.get(url);
}
/** Per-site long-term files (null when the file does not exist, e.g. custom points). */
export const siteFile = (dir, id) => getJSON(`${core.state.base}${dir}/${id}.json`).catch(() => null);
export const validation = () => getJSON(`${core.state.base}validation.json`).catch(() => null);
export const hindcast = () => getJSON(`${core.state.base}hindcast.json`).catch(() => null);

// ------------------------------------------------------------ neighbourhood grid (local250 → local fallback)
// Contract §22: web/data/local250/<ID>.json (41 x 41 nodes, 250 m apart, ±5 km), listed in local250/index.json
// (all 33 catalogue sites since v37). A site missing from the index, or a failed/missing 250 m file, falls back to
// §15 web/data/local/<ID>.json (21 x 21 nodes, 1 km apart, ±10 km). Same fields and metric definitions in both.
let index250 = null;
const local250Ids = () => (index250 ||= fetch(`${core.state.base}local250/index.json`, { cache: 'no-cache' })
  .then(r => (r.ok ? r.json() : null)).then(j => new Set((j?.sites || []).map(s => s.id))).catch(() => new Set()));
const gridCache = new Map();
/** {data, dir, spacing_m, half_km, fine, fellBack, ms} or null (no grid at all, e.g. a custom point). */
export function localGrid(id) {
  if (!gridCache.has(id)) gridCache.set(id, (async () => {
    const site = core.state.sites?.find(s => s.id === id);
    if (!site || site.user || site.group === 'custom') return null;
    const want250 = (await local250Ids()).has(id);
    const t0 = performance.now();
    for (const dir of want250 ? ['local250', 'local'] : ['local']) {
      try {
        const r = await fetch(`${core.state.base}${dir}/${id}.json`, { cache: 'no-cache' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (!data?.grid || !Array.isArray(data.points) || data.points.length !== data.grid.rows * data.grid.cols) throw new Error('bad grid');
        const ms = Math.round(performance.now() - t0);
        const G = data.grid;
        const out = { data, dir, spacing_m: G.spacing_m, half_km: -G.origin_e_m / 1000, fine: dir === 'local250', fellBack: want250 && dir !== 'local250', ms };
        (window.__llsnGridLoads ||= []).push({ id, dir, ms, bytes: Number(r.headers.get('content-length')) || null });
        return out;
      } catch (e) { if (dir === 'local250') console.warn(`local250/${id}.json unavailable, using 1 km grid:`, e.message); }
    }
    return null;
  })());
  return gridCache.get(id);
}
/** "250 m" / "1 km" */
export const spacingText = m => (m >= 1000 ? `${m / 1000} km` : `${m} m`);
