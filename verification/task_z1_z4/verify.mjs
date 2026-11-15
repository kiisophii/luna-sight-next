// Independent Z1/Z4 member verification. Imports Node standard library only.
import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const root=process.argv[2]||'target', out='docs/task_z1_z4_independent';
fs.mkdirSync(out,{recursive:true});
const hashes={};
function read(p,binary=false){const b=fs.readFileSync(root+'/'+p);hashes[p]=crypto.createHash('sha256').update(binary?b:b.toString().replace(/\r\n/g,'\n')).digest('hex');return binary?b:JSON.parse(b);}
const start=performance.now(), failures=[], comparisons=[];
function check(site,field,actual,stored,tolerance=0){const numeric=typeof actual==='number'&&typeof stored==='number'; const delta=numeric?actual-stored:null;const pass=numeric?Math.abs(delta)<=tolerance:JSON.stringify(actual)===JSON.stringify(stored);comparisons.push({site,field,actual,stored,delta,tolerance,pass});if(!pass)failures.push({site,field,actual,stored,delta});}
const sites=read('web/data/sites.json'), meta=read('web/data/ephem.json'), ephem=read('web/data/ephem.bin',true), station=read('web/data/korea/stations.json');
assert.equal(meta.n,43824);assert.equal(ephem.length,meta.n*24);assert.equal(meta.mock,false);assert.equal(meta.step_h,1);assert.equal(meta.frame,'MOON_ME_DE421');
assert.equal(station.n,meta.n);assert.equal(station.min_el_deg,10);assert.equal(station.mock,false);
assert.deepEqual(station.stations.map(s=>s.id).sort(),['DSN_CANBERRA','DSN_GOLDSTONE','DSN_MADRID','KDSA']);
const bits=station.stations.map(s=>({id:s.id,b:Buffer.from(s.bits_b64,'base64')}));
bits.forEach(s=>assert.equal(s.b.length,Math.ceil(meta.n/8)));
const rad=Math.PI/180, deg=180/Math.PI, N=meta.n;
function summarize(a) {
 const spans=[];let opening=null;
 for(let i=0;i<=a.length;i++){
  if(i<a.length&&a[i]){if(opening===null)opening=i;}
  else if(opening!==null){spans.push({start_i:opening,end_i:i,duration_h:i-opening,clipped_start:opening===0,clipped_end:i===a.length});opening=null;}
 }
 const complete=spans.filter(s=>s.start_i>0&&s.end_i<a.length);
 const sum=rs=>rs.reduce((n,s)=>n+s.duration_h,0),long=rs=>rs.reduce((n,s)=>Math.max(n,s.duration_h),0);
 return {count:spans.length,total_h:sum(spans),mean_h:spans.length?sum(spans)/spans.length:null,longest_h:long(spans),complete_count:complete.length,complete_mean_h:complete.length?sum(complete)/complete.length:null,complete_longest_h:long(complete),clipped_runs:spans.filter(s=>s.clipped_start||s.clipped_end)};
}
assert.equal(summarize([0,0]).mean_h,null);assert.equal(summarize([1,1]).complete_mean_h,null);assert.equal(summarize([1,1]).clipped_runs.length,1);
const z1=[];
for(const id of ['APOLLO17','CHANGE4','SHACKLETON_RIM']){
 const s=sites.find(s=>s.id===id),h=read('web/data/horizon/'+id+'.json'),published=read('web/data/detail/time_stats/'+id+'.json');
 assert.equal(h.obs_height_m,2);assert.equal(h.mock,false);assert.equal(h.mask.length,720);
 assert.equal(h.lat,s.lat);assert.equal(h.lon,s.lon);
 const a=s.lat*rad,b=s.lon*rad;
 const up=[Math.cos(a)*Math.cos(b),Math.cos(a)*Math.sin(b),Math.sin(a)];
 const east=[-Math.sin(b),Math.cos(b),0],north=[-Math.sin(a)*Math.cos(b),-Math.sin(a)*Math.sin(b),Math.cos(a)];
 const rr=1737.4+(h.h0_m+2)/1000;
 const dot=(x,y)=>x.reduce((n,v,j)=>n+v*y[j],0);
 function margin(i,col) {
  const v=up.map((v,j)=>ephem.readFloatLE((i*6+col+j)*4)-rr*v);
  const e=dot(v,east),n=dot(v,north),u=dot(v,up);
  const az=(Math.atan2(e,n)*deg+360)%360,el=Math.atan2(u,Math.hypot(e,n))*deg;
  const p=az/h.az_step_deg,k=Math.floor(p),f=p-k;
  return el-(h.mask[k%720]*(1-f)+h.mask[(k+1)%720]*f);
 }
 const sun=[],earth=[];let both=0;const links={kdsa_h:0,at_least_1_h:0,at_least_2_h:0};
 for(let i=0;i<N;i++){
  const y=-margin(i,0)/0.2666;
  const fraction=y<=-1?1:y>=1?0:(Math.acos(y)-y*Math.sqrt(1-y*y))/Math.PI;
  sun.push(Number(fraction>=.5));earth.push(Number(margin(i,3)>0));both+=sun[i]*earth[i];
  if(earth[i]){
   let count=0;for(const st of bits){const active=(st.b[Math.floor(i/8)]>>i%8)&1;count+=active;if(st.id==='KDSA')links.kdsa_h+=active;}
   links.at_least_1_h+=Number(count>=1);links.at_least_2_h+=Number(count>=2);
  }
 }
 const actual={sunlit_h:sun.reduce((a,b)=>a+b,0),earth_visible_h:earth.reduce((a,b)=>a+b,0),both_h:both,dark_runs:summarize(sun.map(x=>1-x)),no_earth_runs:summarize(earth.map(x=>1-x)),sunlit_runs:summarize(sun),station_link_h:links};
 for(const k of ['sunlit_h','earth_visible_h','both_h']){check(id,k,actual[k],published[k],1);check(id,k+'_fraction_pp',actual[k]/N*100,published[k]/N*100,.1);}
 for(const k of ['dark_runs','no_earth_runs','sunlit_runs'])for(const [key,val]of Object.entries(actual[k]))check(id,k+'.'+key,val,published[k][key],key.endsWith('_h')?1:0);
 for(const [k,v]of Object.entries(links))check(id,'station_link_h.'+k,v,published.station_link_h[k],1);
 // Independent baseline parity at the three reviewed sites.
 const metrics=read('web/data/metrics/'+id+'.json'),windows=read('web/data/windows/'+id+'.json');
 for(const [k,v]of Object.entries({sun_frac:actual.sunlit_h/N,earth_frac:actual.earth_visible_h/N,both_frac:both/N,longest_dark_h:actual.dark_runs.longest_h}))check(id,'baseline_metrics.'+k,v,metrics[k]);
 function visible(a){let spans=[];let k=0;while(k<N){if(!a[k]){k++;continue;}let j=k;while(j<N&&a[j])j++;const utc=i=>new Date(Date.parse(meta.start)+i*3600000).toISOString().replace('.000Z','Z');spans.push({start_utc:utc(k),end_utc:utc(j),duration_h:j-k,clipped_start:k===0,clipped_end:j===N});k=j;}return spans;}
 for(const [key,a]of [['sun',sun],['earth',earth]]){check(id,'baseline_windows.'+key+'.visible',visible(a),windows[key].visible);const gaps=visible(a.map(x=>1-x)).sort((a,b)=>b.duration_h-a.duration_h||a.start_utc.localeCompare(b.start_utc)).slice(0,10);check(id,'baseline_windows.'+key+'.longest_gaps',gaps,windows[key].longest_gaps);}
 z1.push({id,...actual});
}
// RFC4180 CSV parser, including quoted source notes.
const csvBytes=fs.readFileSync(root+'/docs/task_r_landings.csv');hashes['docs/task_r_landings.csv']=crypto.createHash('sha256').update(csvBytes.toString().replace(/\r\n/g,'\n')).digest('hex');
function csv(text){const rows=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(!quoted&&(c===','||c==='\n')){row.push(cell.replace(/\r$/,''));cell='';if(c==='\n'){rows.push(row);row=[];}}else cell+=c;}if(cell||row.length){row.push(cell);rows.push(row);}const header=rows.shift();return rows.filter(r=>r.length>1).map(r=>Object.fromEntries(header.map((h,i)=>[h,r[i]])));}
const history=read('web/data/detail/history.json'), sources=read('docs/detail_z4_sources.json');
const candidates=csv(csvBytes.toString()).filter(m=>Date.parse(m.landing_utc)<=Date.parse('2026-11-15T00:00:00Z'));
assert.equal(candidates.length,18);
assert.equal(history.radius_m,1737400);assert.equal(history.mission_count,18);assert.equal(history.site_count,33);assert.equal(history.mock,false);
for(const m of candidates){
 const s=sites.find(s=>s.id===m.id),p=history.missions.find(x=>x.id===m.id);
 assert(s&&!['future','custom','artemis3_region','polar_peak'].includes(s.group));
 for(const k of ['lat','lon'])check(m.id,'mission.'+k,Number(m[k]),p[k]);
 for(const k of ['landing_utc','coordinate_source','time_source','note'])check(m.id,'mission.'+k,m[k],p[k]);
 check(m.id,'mission.official_source_url',sources.missions[m.id].url,p.official_source_url);
}
assert.deepEqual(history.sites.map(s=>s.id).sort(),sites.map(s=>s.id).sort());
function geodesic(p,q){
 // Independent vector cross/dot central angle, rather than producer haversine.
 const unit=s=>[Math.cos(s.lat*rad)*Math.cos(s.lon*rad),Math.cos(s.lat*rad)*Math.sin(s.lon*rad),Math.sin(s.lat*rad)];
 const u=unit(p),v=unit(q),cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
 const angle=Math.atan2(Math.hypot(...cross),u.reduce((s,x,j)=>s+x*v[j],0));
 const east=-Math.sin(p.lon*rad)*v[0]+Math.cos(p.lon*rad)*v[1];
 const north=-Math.sin(p.lat*rad)*Math.cos(p.lon*rad)*v[0]-Math.sin(p.lat*rad)*Math.sin(p.lon*rad)*v[1]+Math.cos(p.lat*rad)*v[2];
 const status=angle<1e-14?'coincident':Math.PI-angle<1e-14?'antipodal':Math.abs(p.lat)===90?'origin_pole':'defined';
 return {distance_m:status==='coincident'?0:1737400*angle,bearing_status:status,bearing_deg:status==='defined'?(Math.atan2(east,north)*deg+360)%360:null};
}
assert.equal(geodesic({lat:12,lon:34},{lat:-12,lon:-146}).bearing_deg,null);
assert.equal(geodesic({lat:90,lon:34},{lat:0,lon:0}).bearing_status,'origin_pole');
assert.equal(geodesic({lat:0,lon:0},{lat:0,lon:0}).distance_m,0);
const z4=[];
for(const id of ['APOLLO11','CHANGE4','SHACKLETON_RIM']){
 const s=sites.find(s=>s.id===id),p=history.sites.find(s=>s.id===id);
 check(id,'history.lat',s.lat,p.lat);check(id,'history.lon',s.lon,p.lon);
 const nearest=candidates.filter(m=>m.id!==id).map(m=>({id:m.id,...geodesic(s,{lat:Number(m.lat),lon:Number(m.lon)})})).sort((a,b)=>a.distance_m-b.distance_m||a.id.localeCompare(b.id)).slice(0,3);
 nearest.forEach((m,i)=>{const x=p.nearest[i];check(id,'nearest'+(i+1)+'.id',m.id,x.id);check(id,'nearest'+(i+1)+'.rank',i+1,x.rank);check(id,'nearest'+(i+1)+'.distance_m',m.distance_m,x.distance_m,x.distance_m*.01);check(id,'nearest'+(i+1)+'.bearing_status',m.bearing_status,x.bearing_status);check(id,'nearest'+(i+1)+'.bearing_deg',m.bearing_deg,x.bearing_deg,1e-9);check(id,'nearest'+(i+1)+'.official_url',sources.missions[m.id].url,x.official_source_url);});
 z4.push({id,nearest});
}
const summary={reviewed_head:'beedb67e7993258720ebfc9219e140636f6e4b11',main_base:'b085c298ac8f1b9ff2a2f0fb8e99093c52ee9ef9',reviewer:'Minchul Kim',producer:'Jiyong Sung',generated_utc:new Date().toISOString(),elapsed_s:(performance.now()-start)/1000,checks:comparisons.length,failures,z1,z4,hashes,source_urls:['https://naif.jpl.nasa.gov/pub/naif/generic_kernels/',...new Set(Object.values(sources.missions).map(m=>m.url))],limitations:['Three sites per product, not all 33 numerical outputs.','Ephemeris, horizons and station bits are independent-verifier inputs, not rederived from kernels/DEMs here.','Task R coordinates/source metadata preserved and cross-checked; official pages not re-fetched in this run.','One CPU worker; no production numerical imports; no production data modified.','No physical link availability or usable landing infrastructure is certified.']};
fs.writeFileSync(out+'/summary.json',JSON.stringify(summary,null,2)+'\n');
fs.writeFileSync(out+'/comparisons.json',JSON.stringify(comparisons,null,2)+'\n');
let report='# Independent member verification: PR #80 Z1 and Z4\n\nPinned head: '+summary.reviewed_head+'. Reviewer: Minchul Kim; producer: Jiyong Sung. Result: **'+(failures.length?'FAIL':'PASS')+'** ('+comparisons.length+' comparisons, '+failures.length+' failures).\n\nReproduce: \x60node verification/task_z1_z4/verify.mjs target\x60, where target is a checkout of the pinned head. No imports from pipeline/ or web/js/. See summary.json for input hashes and comparisons.json for every result, including failures.\n\n## Z1\n\n43,824 hourly cells per site, independent topocentric ENU geometry and cyclic mask interpolation; solar disk >=50%, Earth centre strictly above mask, 2 m observer; LSB-first station bits gated by Earth visibility. Run counts, means, longest and clipped/complete spans checked. Baseline metrics and every Sun/Earth interval/top-10 gap checked separately at these three sites.\n\n|Site|Sun h|Earth h|Both h|Longest dark h|Longest sunlight h|KDSA h|>=1 h|>=2 h|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n';
for(const s of z1)report+='|'+[s.id,s.sunlit_h,s.earth_visible_h,s.both_h,s.dark_runs.longest_h,s.sunlit_runs.longest_h,s.station_link_h.kdsa_h,s.station_link_h.at_least_1_h,s.station_link_h.at_least_2_h].join('|')+'|\n';
const z1comp=comparisons.filter(x=>!x.field.startsWith('nearest')&&!x.field.startsWith('mission.')&&!x.field.startsWith('history.'));
report+='\nMaximum numeric Z1 difference: '+Math.max(...z1comp.filter(x=>x.delta!==null).map(x=>Math.abs(x.delta)))+'. Criteria: fractions <=0.1 percentage points, durations <=1 h; counts, null cases and clipping lists exact. APOLLO17 no-Earth mean is null (no outage); CHANGE4 whole-window outage is clipped at both ends and complete mean is null. These are distinct.\n\n## Z4\n\nAll 18 Task R candidates evaluated separately for each query with atan2(norm(cross),dot) spherical arcs (R=1737400 m), rather than producer haversine. Self excluded by ID; future/target groups and reference date checked. Rank, distance, initial bearing and official-context URL checked. Analytical coincident/antipodal/polar null cases checked.\n\n|Query|Rank|Lander|Distance m|Bearing deg|\n|---|---:|---|---:|---:|\n';
for(const s of z4)for(const [i,m]of s.nearest.entries())report+='|'+[s.id,i+1,m.id,m.distance_m,m.bearing_deg].join('|')+'|\n';
const d=comparisons.filter(x=>x.field.endsWith('.distance_m'));
report+='\nMax relative distance difference: '+Math.max(...d.map(x=>Math.abs(x.delta)/x.stored*100))+'% (criterion <=1%).\n\n## Sources and limits\n\n'+summary.limitations.map(x=>'- '+x).join('\n')+'\n\n'+summary.source_urls.map(x=>'- '+x).join('\n')+'\n\n## Failures\n\n'+(failures.length?JSON.stringify(failures,null,2):'None.')+'\n';
fs.writeFileSync(out+'/report.md',report);
const ledger='\n\n## Z1 / Z4 independent member verification — PR #80\n\nMinchul Kim independently checked producer Jiyong Sung head '+summary.reviewed_head+'. Three sites each, full 43,824 hourly cells for Z1; all 18 eligible mission distances ranked per query for Z4. '+(failures.length?'FAIL':'PASS')+'; '+comparisons.length+' comparisons, '+failures.length+' failures. [Report](task_z1_z4_independent/report.md), [hashes and numbers](task_z1_z4_independent/summary.json), [every comparison](task_z1_z4_independent/comparisons.json). Own Node standard-library code; no production numerical imports. This verifies the requested three-site scope, not all 33 numerical outputs. Raw ephemeris/horizons/station bits are inputs; official Z4 source metadata checked against Task R/manifest, pages not re-fetched. Existing author-only records remain historical snapshots.\n';
fs.appendFileSync('docs/verification_ledger.md',ledger);
const kst=new Date(Date.now()+9*3600000).toISOString().slice(0,16).replace('T',' ');
fs.appendFileSync('docs/SI_USAGE.md','\n| '+kst+' (KST) | Minchul Kim | Independent Z1/Z4 verification of PR #80 | ChatGPT Codex (GPT-6) | Pin head; recompute three complete hourly time series and three nearest-lander rankings with own Node-only geometry; compare counts, runs, means, clipping, station gating, source metadata and all failures | verification/task_z1_z4/, .github/workflows/verify-task-z1-z4-member.yml, docs/task_z1_z4_independent/, docs/verification_ledger.md, docs/SI_USAGE.md | TO CHECK | TO CHECK |\n');
console.log(JSON.stringify({checks:comparisons.length,failures,z1,z4}));
if(failures.length)process.exitCode=1;
