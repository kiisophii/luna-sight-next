// Actual app outputs are the comparison target, not the independent recomputation.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import * as core from '../web/js/core.js';
import {stationBits} from '../web/js/korea.js';
import {siteStationLink} from '../web/js/diff_data.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const inputs={};
const record=(p,b)=>{inputs[path.relative(root,p).replaceAll('\\','/')]=createHash('sha256').update(b).digest('hex');};
for(const name of ['web/js/core.js','web/js/korea.js','web/js/diff_data.js','pipeline/task_c_browser.mjs']){
 const p=path.join(root,name);record(p,fs.readFileSync(p));
}
globalThis.fetch=async url=>{
 const p=path.join(root,'web',url),b=fs.readFileSync(p);
 record(p,b);
 return {ok:true,json:async()=>JSON.parse(b),arrayBuffer:async()=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)};
};
const pack=b=>{const out=Buffer.alloc(Math.ceil(b.length/8));b.forEach((v,i)=>{if(v)out[i>>3]|=1<<(i&7);});return out.toString('base64');};
await core.loadData();const bits=await stationBits(),sites={};
for(const s of core.state.sites){
 const earth=Array.from({length:core.state.n},(_,i)=>core.earthVisible(s,i));
 const by_station={};
 for(const [id,station] of Object.entries(bits)){const link=earth.map((v,i)=>v&&!!station[i]);by_station[id]={hours:link.filter(Boolean).length,bits_b64:pack(link)};}
 sites[s.id]={by_station,earth_bits_b64:pack(earth),app_totals:await siteStationLink(s,0,core.state.n-1)};
}
const json_validity={};
for(const name of fs.readdirSync(path.join(root,'web/data/korea')).filter(n=>n.startsWith('windows_'))){
 const p=path.join(root,'web/data/korea',name),bytes=fs.readFileSync(p);record(p,bytes);
 try{JSON.parse(bytes);json_validity[name]={valid:true};}
 catch(e){json_validity[name]={valid:false,error:e.message};}
}
fs.mkdirSync(path.join(root,'data/processed/task_c'),{recursive:true});
fs.writeFileSync(path.join(root,'data/processed/task_c/browser_reference.json'),JSON.stringify({inputs,sites,json_validity})+'\n');
console.log('Actual app reference complete:',Object.keys(sites).length,'sites;',json_validity);
