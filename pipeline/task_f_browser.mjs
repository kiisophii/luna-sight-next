// Evaluate actual browser terrain + core modules with old tiles or an ignored candidate overlay.
import fs from 'node:fs';
import path from 'node:path';
import {gunzipSync} from 'node:zlib';
import {fileURLToPath} from 'node:url';
import {computeHorizon, decodeTile, decodePolarTile, tilesFor, needCount} from '../web/js/hterrain.js';
import {actualCore,loadEphemeris} from './cache_metrics.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const [pointsFile,outFile,candidate]=process.argv.slice(2);
const points=JSON.parse(fs.readFileSync(pointsFile,'utf8'));
const index=JSON.parse(fs.readFileSync(path.join(root,'web/data/hterrain/index.json'),'utf8'));
// Keep the old comparison reproducible after the candidate is promoted.
const savedBaseline=path.join(root,'docs/task_f/baseline_index.json');
const polarIndex=candidate?path.join(candidate,'index.json'):
  (fs.existsSync(savedBaseline)?savedBaseline:path.join(root,'web/data/hterrain/polar_s/index.json'));
index.polar=JSON.parse(fs.readFileSync(polarIndex,'utf8'));
const {core}=await actualCore(root);await loadEphemeris(root,core);
const ab=b=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
const results=[];
for(const point of points){
  const started=performance.now();let bytes=0,count=0;
  const tiles={near:new Map(),far:new Map(),polar:{}};
  const load=need=>{
    for(const grid of ['near','far'])for(const key of need[grid]){
      if(tiles[grid].has(key))continue;
      const blob=fs.readFileSync(path.join(root,`web/data/hterrain/tiles/${grid}/${key}.i16.gz`));
      tiles[grid].set(key,decodeTile(ab(gunzipSync(blob)),index.grids[grid].n));bytes+=blob.length;count++;
    }
    for(const level of index.polar.levels){
      const cache=tiles.polar[level.name]??(tiles.polar[level.name]=new Map());
      for(const key of need.polar[level.name]??[]){
        if(cache.has(key))continue;
        const overlay=candidate?path.join(candidate,level.name,key+'.bin.gz'):null;
        const file=overlay&&fs.existsSync(overlay)?overlay:path.join(root,'web/data/hterrain',level.url.replace('{ty}_{tx}',key));
        const blob=fs.readFileSync(file);cache.set(key,decodePolarTile(ab(gunzipSync(blob)),level.n,level.q_m));bytes+=blob.length;count++;
      }
    }
  };
  load(tilesFor(index,point.lat,point.lon));let result;
  for(let round=0;round<6;round++){result=computeHorizon(index,tiles,point.lat,point.lon);if(!needCount(result.need))break;load(result.need);}
  if(needCount(result.need))throw Error(point.id+': incomplete terrain');
  const mask=Array.from(result.mask,v=>Math.round(v*1e4)/1e4),h0=Math.round(result.h0_m*100)/100;
  core.state.horizons.set(point.id,{id:point.id,lat:point.lat,lon:point.lon,h0_m:h0,obs_height_m:2,az_step_deg:.5,mask});
  const metrics=core.metrics(point);
  results.push({...point,h0_m:h0,mask,metrics,dem_sources:result.dem_sources,cold_local_ms:performance.now()-started,compressed_bytes:bytes,tile_count:count});
  fs.writeFileSync(outFile,JSON.stringify({candidate:!!candidate,complete:results.length===points.length,points:results})+'\n');
  console.log(point.id,metrics.sun_frac,'bytes',bytes,'ms',Math.round(results.at(-1).cold_local_ms));
}
