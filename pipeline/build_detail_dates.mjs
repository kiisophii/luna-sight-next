/** Z3: exact hourly landing-date statistics and rational slip deltas.
 * node pipeline/build_detail_dates.mjs [--root REPO] [--site ID]
 * Does not read rounded date_slip arrays and never changes existing products.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {actualCore,loadEphemeris,validateHorizon} from './cache_metrics.mjs';
import crypto from 'node:crypto';
const HERE=path.dirname(fileURLToPath(import.meta.url));
export const SCHEMA='detail-dates-z3-v1';
export const STAYS=[168,336,708],SHIFTS=[-7,-3,-1,1,3,7],N=43824,DAYS=1826;
export const ROW_COLUMNS=['status','sun_h','earth_h','both_h','sun_frac','earth_frac','both_frac','longest_dark_h','dark_left_censored','dark_right_censored'];
export const DELTA_COLUMNS=['status','target_day_index','delta_sun_h','delta_earth_h','delta_both_h','delta_longest_dark_h'];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
export function sorted(v){return Array.isArray(v)?v.map(sorted):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;}
export const canonical=v=>JSON.stringify(sorted(v));
const T0=Date.UTC(2026,0,1);
export const isoDay=i=>new Date(T0+i*86400000).toISOString().slice(0,10);
async function atom(file,obj){await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file+'.part',JSON.stringify(obj)+'\n');await fs.rename(file+'.part',file);}
export function prefix(bits){
  const out=new Int32Array(bits.length+1);
  for(let i=0;i<bits.length;i++){if(bits[i]!==0&&bits[i]!==1)throw Error('Non-binary hourly bit');out[i+1]=out[i]+bits[i];}
  return out;
}
export function makeStay(sun,earth,stay_h,step_h=24,day_count=Math.ceil(sun.length/step_h)){
  if(sun.length!==earth.length||!Number.isInteger(stay_h)||stay_h<=0)throw Error('Invalid series/stay');
  const ps=prefix(sun),pe=prefix(earth),both=Uint8Array.from(sun,(v,i)=>v&earth[i]),pb=prefix(both);
  const rows=[];
  for(let d=0;d<day_count;d++){
    const a=d*step_h,b=a+stay_h;
    if(a<0||b>sun.length){rows.push(['out_of_range',...Array(9).fill(null)]);continue;}
    const s=ps[b]-ps[a],e=pe[b]-pe[a],v=pb[b]-pb[a];
    let run=0,longest=0;
    for(let i=a;i<b;i++){run=sun[i]?0:run+1;if(run>longest)longest=run;}
    const left=!sun[a]&&(a===0||sun[a-1]===0);
    const right=!sun[b-1]&&(b===sun.length||sun[b]===0);
    rows.push(['ok',s,e,v,s/stay_h,e/stay_h,v/stay_h,longest,left,right]);
  }
  return rows;
}
export function makeSlip(rows,shift){
  return rows.map((base,d)=>{
    const j=d+shift,target=rows[j],b=base[0]==='ok',t=target?.[0]==='ok';
    const status=b&&t?'ok':!b&&!t?'both_out_of_range':!b?'base_out_of_range':'target_out_of_range';
    return status==='ok'?[status,j,target[1]-base[1],target[2]-base[2],target[3]-base[3],target[7]-base[7]]:[status,j,null,null,null,null];
  });
}
export function decodeSlip(row,stay_h){
  return row[0]==='ok'?{status:'ok',sun_frac:row[2]/stay_h,earth_frac:row[3]/stay_h,both_frac:row[4]/stay_h,longest_dark_h:row[5]}:{status:row[0],sun_frac:null,earth_frac:null,both_frac:null,longest_dark_h:null};
}
export function validCached(obj,signature){
  try{const {content_sha256,...content}=obj;return obj.schema===SCHEMA&&obj.inputs.signature===signature&&content_sha256===hash(canonical(content))&&obj.stays.length===3&&obj.stays.every(s=>s.rows.length===DAYS&&s.slips.length===6);}
  catch{return false;}
}
export function hourly(core,site){
  const sun=new Uint8Array(core.state.n),earth=new Uint8Array(core.state.n);
  for(let i=0;i<sun.length;i++){sun[i]=core.sunlit(site,i)?1:0;earth[i]=core.earthVisible(site,i)?1:0;}
  return {sun,earth};
}
function assertCoreParity(core,site,sun,earth,stays){
  let checks=0;
  for(const stay of stays){
    const valid=stay.rows.map((r,i)=>r[0]==='ok'?i:-1).filter(i=>i>=0);
    const selected=new Set([0,valid.at(-1),789,790,791,1095,1461]); // includes leap-day neighbourhood and later years
    for(const d of selected){
      const r=stay.rows[d];if(!r||r[0]!=='ok')continue;
      const m=core.metrics(site,d*24,d*24+stay.stay_h-1);
      if(m.sun_frac!==r[4]||m.earth_frac!==r[5]||m.both_frac!==r[6]||m.longest_dark_h!==r[7])throw Error(site.id+' core parity failed '+d);
      checks++;
    }
  }
  return checks;
}
export async function main(root=path.resolve(HERE,'..'),onlySite=null){
  const {core,hash:coreHash}=await actualCore(root),eph=await loadEphemeris(root,core);
  if(eph.n!==N)throw Error('Full 43824 hourly cells required');
  const bytes=await fs.readFile(path.join(root,'web/data/sites.json')),sites=JSON.parse(bytes);
  if(sites.length!==33)throw Error('33 sites required');
  if(onlySite&&!sites.some(s=>s.id===onlySite))throw Error('Unknown site');
  const producer=await fs.readFile(fileURLToPath(import.meta.url)),helper=await fs.readFile(path.join(HERE,'cache_metrics.mjs'));
  const destination=path.join(root,'web/data/detail/dates'),checkpoint=path.join(root,'data/processed/detail_dates');
  const manifest=[],report={schema:SCHEMA,sites:[],complete:false,created_utc:new Date().toISOString(),source_main:'300b8499e3ea4cadf1e9f2c36a267ba91e935aee',author_verification_only:true};
  for(const site of sites){
    if(onlySite&&site.id!==onlySite)continue;
    const hb=await fs.readFile(path.join(root,'web/data/horizon',site.id+'.json')),h=JSON.parse(hb);
    validateHorizon(site,h);core.state.horizons.clear();core.state.horizons.set(site.id,h);
    const inputs={ephem_sha256:eph.ephem_sha256,ephem_metadata_sha256:eph.metadata_sha256,sites_sha256:hash(bytes),site_sha256:hash(JSON.stringify(site)),horizon_sha256:hash(hb),core_sha256:coreHash,producer_sha256:hash(producer),cache_helper_sha256:hash(helper),params:{n:N,days:DAYS,stay_h:STAYS,slip_days:SHIFTS,start_utc:'2026-01-01T00:00:00Z',end_exclusive_utc:'2031-01-01T00:00:00Z'}};
    inputs.signature=hash(canonical(inputs));
    const file=path.join(destination,site.id+'.json');let obj,resumed=false;
    try{obj=JSON.parse(await fs.readFile(file,'utf8'));resumed=validCached(obj,inputs.signature);}catch{}
    let parity=0;
    if(!resumed){
      const {sun,earth}=hourly(core,site);
      const stays=STAYS.map(stay_h=>{
        const rows=makeStay(sun,earth,stay_h);
        return {stay_days:stay_h/24,stay_h,delta_fraction_denominator_h:stay_h,rows,slips:SHIFTS.map(shift_days=>({shift_days,rows:makeSlip(rows,shift_days)}))};
      });
      parity=assertCoreParity(core,site,sun,earth,stays);
      obj={schema:SCHEMA,id:site.id,lat:site.lat,lon:site.lon,mock:false,first_landing:'2026-01-01',last_landing:'2030-12-31',n_landings:DAYS,step_days:1,landing_time_utc:'00:00:00',hourly_cells:{start_utc:'2026-01-01T00:00:00Z',last_cell_start_utc:'2030-12-31T23:00:00Z',end_exclusive_utc:'2031-01-01T00:00:00Z',n:N,rule:'[i,i+1)'},row_columns:ROW_COLUMNS,delta_columns:DELTA_COLUMNS,delta_fraction_rule:'delta visibility fraction = signed delta_*_h / delta_fraction_denominator_h; multiply by 100 for percentage points. Exact integer rational, not rounded input-array subtraction.',out_of_range_rule:'Require every hourly cell of the original and shifted stay; do not clamp or shorten. Full final 23:00 cell is included; end-exclusive 2031-01-01T00:00Z is allowed.',dark_censor_rule:'Within-stay run lengths. A dark edge is censored when the adjacent out-of-stay cell is dark, or that adjacent cell is outside the ephemeris.',stays,inputs,verification_status:'author_verified_independent_member_pending'};
      obj.content_sha256=hash(canonical(obj));await atom(file,obj);
      await fs.mkdir(checkpoint,{recursive:true});
      const packed=Buffer.alloc(N);for(let i=0;i<N;i++)packed[i]=sun[i]|(earth[i]<<1);
      await fs.writeFile(path.join(checkpoint,site.id+'.bits'),packed);
    }
    const content=await fs.readFile(file);
    const counts=obj.stays.map(s=>({stay_h:s.stay_h,valid:s.rows.filter(r=>r[0]==='ok').length,out_of_range:s.rows.filter(r=>r[0]!=='ok').length,valid_slip_rows:s.slips.map(t=>({shift_days:t.shift_days,n:t.rows.filter(r=>r[0]==='ok').length}))}));
    manifest.push({id:site.id,file:site.id+'.json',sha256:hash(content),content_sha256:obj.content_sha256});
    report.sites.push({id:site.id,bytes:content.length,resumed,core_direct_windows_checked:parity,counts});
    await atom(path.join(checkpoint,'progress.json'),report);
    console.log(site.id,counts.map(x=>x.valid+'/'+x.out_of_range).join(' '),content.length,'bytes',resumed?'resumed':'computed');
  }
  if(!onlySite){
    if(manifest.length!==33)throw Error('Incomplete catalogue');
    const index={schema:SCHEMA,mock:false,first_landing:'2026-01-01',last_landing:'2030-12-31',n_landings:DAYS,stay_h:STAYS,slip_days:SHIFTS,sites:manifest};
    await atom(path.join(destination,'index.json'),index);report.complete=true;
  }
  report.total_bytes=report.sites.reduce((a,s)=>a+s.bytes,0);
  await atom(path.join(root,'docs/z3_dates_generation.json'),report);
  return report;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const args=process.argv.slice(2);let root=path.resolve(HERE,'..'),only=null;
  for(let i=0;i<args.length;i++){if(args[i]==='--root')root=path.resolve(args[++i]);else if(args[i]==='--site')only=args[++i];else throw Error('Unknown argument '+args[i]);}
  await main(root,only);
}
