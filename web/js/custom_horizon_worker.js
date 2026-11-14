// custom_horizon_worker.js — module Web Worker: horizon mask of a user-defined point from web/data/hterrain/.
// Message in:  {id, lat, lon, base}        (base = URL of the data folder, e.g. 'https://…/data/')
// Messages out: {id, type:'progress', text} … then {id, type:'done', mask:[720], h0_m, dem_sources, tiles, ms}
//               or {id, type:'error', message}
import { computeHorizon, decodeTile, tilesFor } from './hterrain.js';

let index = null, indexBase = null;
const cache = { near: new Map(), far: new Map() };    // decoded tiles stay in memory for later points

async function gunzip(buf) {
  const u8 = new Uint8Array(buf);
  if (u8[0] !== 0x1f || u8[1] !== 0x8b) return buf;  // server already removed the gzip layer
  const ds = new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip')));
  return ds.arrayBuffer();
}

async function fetchTiles(base, want) {
  const jobs = [];
  for (const g of ['near', 'far']) for (const key of want[g]) {
    if (cache[g].has(key)) continue;
    const url = base + 'hterrain/' + index.url.replace('{grid}', g).replace('{ty}_{tx}', key);
    jobs.push(fetch(url).then(r => { if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.arrayBuffer(); })
      .then(gunzip).then(raw => cache[g].set(key, decodeTile(raw, index.grids[g].n))));
  }
  await Promise.all(jobs);
  return jobs.length;
}

self.onmessage = async ev => {
  const { id, lat, lon, base } = ev.data;
  try {
    const t0 = performance.now();
    if (!index || indexBase !== base) {
      const r = await fetch(base + 'hterrain/index.json');
      if (!r.ok) throw new Error('hterrain/index.json: HTTP ' + r.status);
      index = await r.json(); indexBase = base;
    }
    let fetched = await fetchTiles(base, tilesFor(index, lat, lon));
    self.postMessage({ id, type: 'progress', text: 'march' });
    let res;
    for (let round = 0; round < 4; round++) {
      res = computeHorizon(index, cache, lat, lon);
      if (!res.need.near.size && !res.need.far.size) break;
      fetched += await fetchTiles(base, res.need);
    }
    if (res.need.near.size || res.need.far.size || !res.mask) throw new Error('terrain tiles missing');
    self.postMessage({ id, type: 'done', mask: Array.from(res.mask, v => Math.round(v * 1e4) / 1e4), h0_m: res.h0_m,
      dem_sources: res.dem_sources, grids: { near: index.grids.near.res_m, far: index.grids.far.res_m },
      tiles: fetched, ms: Math.round(performance.now() - t0) });
  } catch (e) {
    self.postMessage({ id, type: 'error', message: String(e && e.message || e) });
  }
};
