// hterrain.js — horizon mask for a user-defined point, computed from the browser height tiles in web/data/hterrain/
// (written by pipeline/build_custom_terrain.py). Pure maths, no DOM: used by custom_horizon_worker.js and by the
// Node check pipeline/check_custom_horizon.mjs.
//
// Same definitions as pipeline/horizon.py (contract section 3 / 9):
//   720 azimuths (0.5°, 0 = north, clockwise), geometric distance grid 0.2 → 300 km (4000 steps), exact sphere
//   R = 1737.4 km (lunar curvature included), observer 2 m above the terrain at the site, elevation
//   = atan2(r_t cos θ − r_o, r_t sin θ), per-azimuth early stop once a +10.8 km peak could no longer win.
// DEM chain: "near" grid (LDEM_64 → 32 px/deg, ~948 m) to 150 km, "far" grid (LDEM_16, ~1895 m) to 300 km.

export const R_M = 1737400;
export const OBS_HEIGHT_M = 2;
export const HMAX_M = 10800;
export const N_AZ = 720;
export const AZ_STEP_DEG = 0.5;
const D2R = Math.PI / 180, R2D = 180 / Math.PI;

/** Decode one tile: gzip(int16 LE row-delta) → Float32Array(n*n). `raw` = ArrayBuffer already gunzipped. */
export function decodeTile(raw, n) {
  const dv = new DataView(raw), out = new Float32Array(n * n);
  if (raw.byteLength !== n * n * 2) throw new Error(`tile has ${raw.byteLength} bytes, expected ${n * n * 2}`);
  for (let r = 0; r < n; r++) {
    let acc = 0;
    for (let c = 0; c < n; c++) { acc += dv.getInt16((r * n + c) * 2, true); out[r * n + c] = acc; }
  }
  return out;
}

/** Tile key and in-tile bilinear position for (lat, lon) on a grid {ppd, tile_deg, n}. */
export function locate(grid, lat, lon) {
  const P = grid.ppd, H = 180 * P, W = 360 * P, tp = grid.n - 1;
  let r = (90 - lat) * P - 0.5;
  r = Math.min(Math.max(r, 0), H - 1);
  const r0 = Math.min(Math.floor(r), H - 2), fr = r - r0;
  const c = (lon + 180) * P - 0.5, c0f = Math.floor(c), fc = c - c0f;
  const c0 = ((c0f % W) + W) % W;
  const ty = Math.floor(r0 / tp), tx = Math.floor(c0 / tp);
  return { ty, tx, lr: r0 - ty * tp, lc: c0 - tx * tp, fr, fc };
}

/** Bilinear height (m) from a decoded tile, or NaN if the tile is not loaded. */
export function sampleGrid(grid, tiles, lat, lon, need) {
  const p = locate(grid, lat, lon), key = p.ty + '_' + p.tx;
  const t = tiles.get(key);
  if (!t) { if (need) need.add(key); return NaN; }
  const n = grid.n, k = p.lr * n + p.lc;
  return (1 - p.fr) * ((1 - p.fc) * t[k] + p.fc * t[k + 1]) + p.fr * ((1 - p.fc) * t[k + n] + p.fc * t[k + n + 1]);
}

/** Distance grid identical to numpy.geomspace(0.2, 300, 4001) (km). */
export function distancesKm(minKm = 0.2, maxKm = 300, nSteps = 4000) {
  const out = new Float64Array(nSteps + 1), a = Math.log(minKm), b = Math.log(maxKm);
  for (let k = 0; k <= nSteps; k++) out[k] = Math.exp(a + (b - a) * k / nSteps);
  out[0] = minKm; out[nSteps] = maxKm;
  return out;
}

/** Tiles touched by a coarse pre-scan (so most points need a single fetch round). Returns {near:Set, far:Set}. */
export function tilesFor(index, lat, lon) {
  const want = { near: new Set(), far: new Set() };
  const { up, east, north } = frame(lat, lon);
  for (let a = 0; a < 360; a += 2) {
    const dir = dirVec(up, east, north, a);
    for (let s = 0; s <= 300; s += 2) {
      const g = s <= index.grids.near.to_km ? 'near' : 'far';
      const [la, lo] = dest(up, dir, s / (R_M / 1000));
      const p = locate(index.grids[g], la, lo); want[g].add(p.ty + '_' + p.tx);
      if (s === 150) { const q = locate(index.grids.far, la, lo); want.far.add(q.ty + '_' + q.tx); }
    }
  }
  return want;
}

function frame(lat, lon) {
  const la = lat * D2R, lo = lon * D2R;
  const up = [Math.cos(la) * Math.cos(lo), Math.cos(la) * Math.sin(lo), Math.sin(la)];
  const east = [-Math.sin(lo), Math.cos(lo), 0];
  const north = [up[1] * east[2] - up[2] * east[1], up[2] * east[0] - up[0] * east[2], up[0] * east[1] - up[1] * east[0]];
  return { up, east, north };
}
const dirVec = (up, east, north, azDeg) => {
  const ca = Math.cos(azDeg * D2R), sa = Math.sin(azDeg * D2R);
  return [north[0] * ca + east[0] * sa, north[1] * ca + east[1] * sa, north[2] * ca + east[2] * sa];
};
function dest(up, dir, th) {
  const ct = Math.cos(th), st = Math.sin(th);
  const x = up[0] * ct + dir[0] * st, y = up[1] * ct + dir[1] * st, z = up[2] * ct + dir[2] * st;
  return [Math.asin(Math.max(-1, Math.min(1, z))) * R2D, Math.atan2(y, x) * R2D];
}

/**
 * Horizon mask at (lat, lon). `tiles` = {near: Map(key → Float32Array), far: Map}. Returns
 * {mask: Float64Array(720) degrees, h0_m, need: {near:Set, far:Set}} — if `need` is non-empty some samples hit
 * tiles that were not loaded: fetch them and call again (the result is only valid when need is empty).
 */
export function computeHorizon(index, tiles, lat, lon, { minKm = 0.2, maxKm = 300, nSteps = 4000, block = 128 } = {}) {
  const near = index.grids.near, far = index.grids.far, nearTo = near.to_km;
  const need = { near: new Set(), far: new Set() };
  const h0 = sampleGrid(near, tiles.near, lat, lon, need.near);
  if (!isFinite(h0)) return { mask: null, h0_m: NaN, need };
  const ro = R_M + h0 + OBS_HEIGHT_M, rTop = R_M + HMAX_M;
  const s = distancesKm(minKm, maxKm, nSteps), ns = s.length, Rk = R_M / 1000;
  const th = new Float64Array(ns), ct = new Float64Array(ns), st = new Float64Array(ns);
  for (let k = 0; k < ns; k++) { th[k] = s[k] / Rk; ct[k] = Math.cos(th[k]); st[k] = Math.sin(th[k]); }
  const { up, east, north } = frame(lat, lon);
  const mask = new Float64Array(N_AZ);
  let usedNear = 0, usedFar = 0;
  for (let j = 0; j < N_AZ; j++) {
    const d = dirVec(up, east, north, j * AZ_STEP_DEG);
    let best = -Infinity;
    for (let i0 = 0; i0 < ns; i0 += block) {
      const i1 = Math.min(ns, i0 + block);
      for (let k = i0; k < i1; k++) {
        const x = up[0] * ct[k] + d[0] * st[k], y = up[1] * ct[k] + d[1] * st[k], z = up[2] * ct[k] + d[2] * st[k];
        const la = Math.asin(Math.max(-1, Math.min(1, z))) * R2D, lo = Math.atan2(y, x) * R2D;
        let h;
        if (s[k] <= nearTo) { h = sampleGrid(near, tiles.near, la, lo, need.near); if (isFinite(h)) usedNear = Math.max(usedNear, s[k]); }
        else { h = sampleGrid(far, tiles.far, la, lo, need.far); if (isFinite(h)) usedFar = Math.max(usedFar, s[k]); }
        if (!isFinite(h)) continue;
        const rt = R_M + h, el = Math.atan2(rt * ct[k] - ro, rt * st[k]);
        if (el > best) best = el;
      }
      if (i1 < ns) {                                              // early stop (bound only decreases with distance)
        const bound = Math.atan2(rTop * ct[i1] - ro, rTop * st[i1]);
        if (best > bound) break;
      }
    }
    mask[j] = best * R2D;
  }
  const dem_sources = [];
  if (usedNear) dem_sources.push({ name: 'LDEM_64 (32 px/deg, browser)', res_m: near.res_m, to_km: Math.round(usedNear * 100) / 100 });
  if (usedFar) dem_sources.push({ name: 'LDEM_16 (browser)', res_m: far.res_m, to_km: Math.round(usedFar * 100) / 100 });
  return { mask, h0_m: h0, need, dem_sources };
}
