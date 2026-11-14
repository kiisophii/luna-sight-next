// Run the browser horizon code (web/js/hterrain.js) in Node on the same tiles the browser fetches.
//   node pipeline/check_custom_horizon.mjs <out.json> ID1 ID2 ...  (or lat,lon pairs like -85.9,-0.9,
//   or @points.json = a JSON list of {id, lat, lon})
//   --no-polar  ignore web/data/hterrain/polar_s/ (the phase-3 global path only)
// Writes {sites: [{id, lat, lon, h0_m, mask[720], ms, tiles, polar, params}]}. Compared by validate_custom_horizon.py.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { computeHorizon, decodeTile, decodePolarTile, tilesFor, needCount } from '../web/js/hterrain.js';

const root = new URL('../web/data/', import.meta.url);
const index = JSON.parse(readFileSync(new URL('hterrain/index.json', root), 'utf8'));
const argv = process.argv.slice(2);
const noPolar = argv.includes('--no-polar');
const [out, ...args] = argv.filter(a => a !== '--no-polar');
const pIdx = new URL('hterrain/polar_s/index.json', root);
if (!noPolar && existsSync(pIdx)) index.polar = JSON.parse(readFileSync(pIdx, 'utf8'));
const sites = JSON.parse(readFileSync(new URL('sites.json', root), 'utf8'));
const cache = { near: new Map(), far: new Map(), polar: {} };
let nTiles = 0;
const ab = b => b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
function load(want) {
  for (const g of ['near', 'far']) for (const key of want[g]) {
    if (cache[g].has(key)) continue;
    const f = new URL(`hterrain/tiles/${g}/${key}.i16.gz`, root);
    if (!existsSync(f)) throw new Error('missing ' + f);
    cache[g].set(key, decodeTile(ab(gunzipSync(readFileSync(f))), index.grids[g].n));
    nTiles++;
  }
  for (const lv of (index.polar ? index.polar.levels : [])) {
    const m = cache.polar[lv.name] || (cache.polar[lv.name] = new Map());
    for (const key of (want.polar && want.polar[lv.name]) || []) {
      if (m.has(key)) continue;
      const f = new URL('hterrain/' + lv.url.replace('{ty}_{tx}', key), root);
      if (!existsSync(f)) throw new Error('missing ' + f);
      m.set(key, decodePolarTile(ab(gunzipSync(readFileSync(f))), lv.n, lv.q_m));
      nTiles++;
    }
  }
}
let list = [];
for (const a of args) {
  if (a.startsWith('@')) list.push(...JSON.parse(readFileSync(a.slice(1), 'utf8')));
  else if (a.includes(',')) list.push({ id: a, lat: +a.split(',')[0], lon: +a.split(',')[1] });
  else { const s = sites.find(x => x.id === a); if (!s) throw new Error('unknown site ' + a); list.push(s); }
}
const res = [];
for (const s of list) {
  const t0 = performance.now(); nTiles = 0;
  load(tilesFor(index, s.lat, s.lon));
  let r;
  for (let k = 0; k < 6; k++) { r = computeHorizon(index, cache, s.lat, s.lon); if (!needCount(r.need)) break; load(r.need); }
  if (needCount(r.need)) throw new Error(s.id + ': tiles still missing');
  const ms = Math.round(performance.now() - t0);
  res.push({ id: s.id, lat: s.lat, lon: s.lon, h0_m: r.h0_m, mask: Array.from(r.mask), dem_sources: r.dem_sources,
    polar: r.polar, params: r.params, ms, tiles: nTiles });
  console.log(s.id, `h0 ${r.h0_m.toFixed(1)} m`, `mask ${Math.min(...r.mask).toFixed(2)}..${Math.max(...r.mask).toFixed(2)}°`,
    `${ms} ms`, `${nTiles} tiles`, r.polar ? 'polar' : 'global');
}
writeFileSync(out, JSON.stringify({ sites: res }));
