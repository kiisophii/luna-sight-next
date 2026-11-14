// core.js — shared geometry API (docs/data_contract.md section 6). Owner: card 6; maths check: card 1.
// Plain ES module, no build step. Conventions: MOON_ME frame, lon east-positive, azimuth 0 = north clockwise,
// elevation above the local horizontal plane (no refraction), time = UTC hour index from 2026-01-01T00Z.
// Hour index `i` may be fractional: ephemeris vectors are linearly interpolated between hourly rows.

export const R_MOON_KM = 1737.4;
export const SUN_RADIUS_DEG = 0.2666;      // solar disk angular radius used for the visible fraction
export const SUNLIT_FRACTION = 0.5;        // "sunlit" = visible fraction >= 0.5
export const T0_MS = Date.UTC(2026, 0, 1, 0, 0, 0);
const D2R = Math.PI / 180, R2D = 180 / Math.PI;

export const state = { sites: [], ephem: null, ephemMeta: null, n: 0, horizons: new Map(), mock: false, base: 'data/' };

// ---------------------------------------------------------------- loading
async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

/** Load sites + ephemeris, then every site's horizon in parallel (missing horizon => flat 0° mask). */
export async function loadData(base = 'data/') {
  state.base = base;
  const [sites, meta, buf] = await Promise.all([
    getJSON(base + 'sites.json'),
    getJSON(base + 'ephem.json'),
    fetch(base + 'ephem.bin', { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error('ephem.bin: HTTP ' + r.status); return r.arrayBuffer(); }),
  ]);
  const dv = new DataView(buf);
  const f = new Float32Array(buf.byteLength / 4);
  for (let k = 0; k < f.length; k++) f[k] = dv.getFloat32(k * 4, true);   // little-endian regardless of CPU
  if (f.length !== meta.n * 6) throw new Error(`ephem.bin has ${f.length / 6} rows, ephem.json says ${meta.n}`);
  state.sites = sites; state.ephemMeta = meta; state.ephem = f; state.n = meta.n;
  await Promise.all(sites.map(loadHorizon));
  state.mock = !!meta.mock || sites.some(s => s.mock) || [...state.horizons.values()].some(h => h.mock);
  return state;
}

/** Fetch (once) the horizon mask of a site. Exposed so added/custom sites can load on demand. */
export async function loadHorizon(site) {
  if (state.horizons.has(site.id)) return state.horizons.get(site.id);
  let h;
  try { h = await getJSON(`${state.base}horizon/${site.id}.json`); }
  catch (e) { console.warn('no horizon for', site.id, '- using flat 0° mask'); h = flatHorizon(site); }
  state.horizons.set(site.id, h);
  return h;
}

export function flatHorizon(site) {
  return { id: site.id, lat: site.lat, lon: site.lon, h0_m: site.elev_m ?? 0, obs_height_m: 2,
           az_step_deg: 0.5, mask: new Array(720).fill(0), max_range_km: 0, dem_sources: [], mock: true, flat: true };
}

// ---------------------------------------------------------------- time helpers
export const hourToDate = i => new Date(T0_MS + i * 3600e3);
export const dateToHour = d => (d.getTime() - T0_MS) / 3600e3;
export const hourRange = () => [0, state.n - 1];

// ---------------------------------------------------------------- vectors
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/** Local east / north / up unit vectors (MOON_ME) at the site. */
export function siteFrame(site) {
  if (site._frame) return site._frame;
  const la = site.lat * D2R, lo = site.lon * D2R;
  const sl = Math.sin(la), cl = Math.cos(la), so = Math.sin(lo), co = Math.cos(lo);
  const fr = { east: [-so, co, 0], north: [-sl * co, -sl * so, cl], up: [cl * co, cl * so, sl] };
  Object.defineProperty(site, '_frame', { value: fr, enumerable: false });
  return fr;
}

/** Observer position (km, MOON_ME): R + terrain height + 2 m along local up. */
function observerPos(site) {
  const h = state.horizons.get(site.id);
  const h0 = h ? h.h0_m : (site.elev_m ?? 0);
  const r = R_MOON_KM + (h0 + 2) / 1000;
  const up = siteFrame(site).up;
  return [up[0] * r, up[1] * r, up[2] * r];
}

/** Interpolated ephemeris row at (fractional) hour i; clamped to the window. col0 = 0 (Sun) or 3 (Earth). */
function bodyVec(i, col0) {
  const e = state.ephem, n = state.n;
  const x = Math.min(Math.max(i, 0), n - 1);
  const k = Math.min(Math.floor(x), n - 2 < 0 ? 0 : n - 2), t = x - k;
  const a = k * 6 + col0, b = Math.min(k + 1, n - 1) * 6 + col0;
  return [e[a] + (e[b] - e[a]) * t, e[a + 1] + (e[b + 1] - e[a + 1]) * t, e[a + 2] + (e[b + 2] - e[a + 2]) * t];
}

function azEl(site, v) {
  const { east, north, up } = siteFrame(site);
  const e = dot(v, east), nn = dot(v, north), u = dot(v, up);
  let az = Math.atan2(e, nn) * R2D; if (az < 0) az += 360;
  return { az, el: Math.atan2(u, Math.hypot(e, nn)) * R2D };
}

/** Sun azimuth/elevation (deg) at hour i, topocentric. */
export function sunAzEl(site, i) {
  const s = bodyVec(i, 0), o = observerPos(site);
  return azEl(site, [s[0] - o[0], s[1] - o[1], s[2] - o[2]]);
}

/** Earth azimuth/elevation (deg) at hour i, with topocentric parallax (observer offset from Moon centre). */
export function earthAzEl(site, i) {
  const g = bodyVec(i, 3), o = observerPos(site);
  return azEl(site, [g[0] - o[0], g[1] - o[1], g[2] - o[2]]);
}

/** Horizon mask elevation (deg) at azimuth az, linear interpolation between bins, wraps at 360°. */
export function horizonAt(site, az) {
  const h = state.horizons.get(site.id);
  if (!h) return 0;
  const m = h.mask, nb = m.length, x = (((az % 360) + 360) % 360) / h.az_step_deg;
  const k = Math.floor(x) % nb, t = x - Math.floor(x);
  return m[k] + (m[(k + 1) % nb] - m[k]) * t;
}

/** Visible fraction (0..1) of the solar disk (radius 0.2666°) above the horizon mask (mask treated as locally flat). */
export function sunVisibleFraction(site, i) {
  const { az, el } = sunAzEl(site, i);
  const y = (horizonAt(site, az) - el) / SUN_RADIUS_DEG;   // mask line position relative to disk centre, in radii
  if (y <= -1) return 1;
  if (y >= 1) return 0;
  return (Math.acos(y) - y * Math.sqrt(1 - y * y)) / Math.PI;
}

export const sunlit = (site, i) => sunVisibleFraction(site, i) >= SUNLIT_FRACTION;

/** Earth CENTRE above the mask (conservative). */
export function earthVisible(site, i) {
  const { az, el } = earthAzEl(site, i);
  return el > horizonAt(site, az);
}

// Signed margins used for sub-hour transition refinement (positive = visible).
const sunMargin = (s, i) => sunVisibleFraction(s, i) - SUNLIT_FRACTION;
const earthMargin = (s, i) => { const { az, el } = earthAzEl(s, i); return el - horizonAt(s, az); };

/** Hours from i until the visible state flips (hourly scan + bisection to ~0.5 min); null if no flip within the window. */
function untilFlip(site, i, margin) {
  const now = margin(site, i) > 0;
  let a = i;
  for (let t = Math.floor(i) + 1; t <= state.n - 1; t++) {
    if ((margin(site, t) > 0) !== now) {
      let b = t;
      for (let k = 0; k < 7; k++) { const c = (a + b) / 2; if ((margin(site, c) > 0) === now) a = c; else b = c; }
      return (a + b) / 2 - i;
    }
    a = t;
  }
  return null;
}

/** Hours until the next transition to not-visible. 0 if not visible now; null if no transition within the window. */
export const untilSunset = (site, i) => (sunMargin(site, i) > 0 ? untilFlip(site, i, sunMargin) : 0);
export const untilEarthset = (site, i) => (earthMargin(site, i) > 0 ? untilFlip(site, i, earthMargin) : 0);
/** Hours until the next transition to visible. 0 if visible now; null if none within the window. */
export const untilSunrise = (site, i) => (sunMargin(site, i) > 0 ? 0 : untilFlip(site, i, sunMargin));
export const untilEarthrise = (site, i) => (earthMargin(site, i) > 0 ? 0 : untilFlip(site, i, earthMargin));

/** Hourly statistics over [i0, i1]: fractions 0..1 and the longest continuous not-sunlit run in hours. */
export function metrics(site, i0 = 0, i1 = state.n - 1) {
  let ns = 0, ne = 0, nb = 0, n = 0, run = 0, longest = 0;
  for (let i = Math.max(0, Math.ceil(i0)); i <= Math.min(i1, state.n - 1); i++) {
    const s = sunlit(site, i), e = earthVisible(site, i);
    n++; if (s) ns++; if (e) ne++; if (s && e) nb++;
    run = s ? 0 : run + 1; if (run > longest) longest = run;
  }
  return n ? { sun_frac: ns / n, earth_frac: ne / n, both_frac: nb / n, longest_dark_h: longest } : null;
}

// For non-module scripts and console debugging.
if (typeof window !== 'undefined') {
  window.LLSN = { state, loadData, loadHorizon, siteFrame, sunAzEl, earthAzEl, horizonAt, sunVisibleFraction, sunlit,
    earthVisible, untilSunset, untilEarthset, untilSunrise, untilEarthrise, metrics, hourToDate, dateToHour };
}
