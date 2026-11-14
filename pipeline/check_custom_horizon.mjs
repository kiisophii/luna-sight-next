// Run the browser horizon code (web/js/hterrain.js) in Node on the same tiles the browser fetches.
//   node pipeline/check_custom_horizon.mjs <out.json> ID1 ID2 ...  (or lat,lon pairs like -85.9,-0.9)
// Writes {sites: [{id, lat, lon, h0_m, mask[720], ms, tiles}]}. Compared against Python by validate_custom_horizon.py.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { computeHorizon, decodeTile, tilesFor } from '../web/js/hterrain.js';

const root = new URL('../web/data/', import.meta.url);
const index = JSON.parse(readFileSync(new URL('hterrain/index.json', root), 'utf8'));
const sites = JSON.parse(readFileSync(new URL('sites.json', root), 'utf8'));
const cache = { near: new Map(), far: new Map() };
let nTiles = 0;
function load(want) {
  for (const g of ['near', 'far']) for (const key of want[g]) {
    if (cache[g].has(key)) continue;
    const f = new URL(`hterrain/tiles/${g}/${key}.i16.gz`, root);
    if (!existsSync(f)) throw new Error('missing ' + f);
    const raw = gunzipSync(readFileSync(f));
    cache[g].set(key, decodeTile(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength), index.grids[g].n));
    nTiles++;
  }
}
const [out, ...args] = process.argv.slice(2);
const res = [];
for (const a of args) {
  const s = a.includes(',') ? { id: a, lat: +a.split(',')[0], lon: +a.split(',')[1] } : sites.find(x => x.id === a);
  if (!s) throw new Error('unknown site ' + a);
  const t0 = performance.now(); nTiles = 0;
  load(tilesFor(index, s.lat, s.lon));
  let r;
  for (let k = 0; k < 4; k++) { r = computeHorizon(index, cache, s.lat, s.lon); if (!r.need.near.size && !r.need.far.size) break; load(r.need); }
  const ms = Math.round(performance.now() - t0);
  res.push({ id: s.id, lat: s.lat, lon: s.lon, h0_m: r.h0_m, mask: Array.from(r.mask), dem_sources: r.dem_sources, ms, tiles: nTiles });
  console.log(s.id, `h0 ${r.h0_m.toFixed(1)} m`, `mask ${Math.min(...r.mask).toFixed(2)}..${Math.max(...r.mask).toFixed(2)}°`, `${ms} ms`, `${nTiles} tiles`);
}
writeFileSync(out, JSON.stringify({ sites: res }));
