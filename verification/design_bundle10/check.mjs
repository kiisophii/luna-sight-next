import {chromium} from 'playwright';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const dir='docs/design_sync/bundle10';fs.mkdirSync(dir,{recursive:true});
const base='9ce8b528d8e95018198e87df4132a8ca521c1646';
const oldCss=execFileSync('git',['show',base+':web/css/layout.css'],{maxBuffer:2000000}).toString();
const browser=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const checks=[],failures=[];
for(const state of ['before','after']){
 const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 if(state==='before')await page.route('**/css/layout.css',r=>r.fulfill({contentType:'text/css',body:oldCss}));
 await page.goto('http://127.0.0.1:8788/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&focus=SHACKLETON_RIM&d=2026-11-14&p=29.5&t=7620',{waitUntil:'domcontentloaded'});
 await page.locator('#tray-cat .tc-row').first().waitFor({timeout:120000});
 for(const width of [1920,1440,1280,1100,390])for(const lang of ['en','ko']){
 await page.setViewportSize({width,height:width===1920?1080:width===1440?900:width===390?844:800});
 await page.locator('.lang-seg [data-lang="'+lang+'"]').click();
 await page.evaluate(()=>document.fonts.ready);await page.keyboard.press('Control+Home');await page.waitForTimeout(250);
 const metrics=await page.evaluate(()=>{
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};
 const dock=document.querySelector('.ls-toolbar'),s=getComputedStyle(dock);
 return {dock:rect(dock),bottom:innerHeight-dock.getBoundingClientRect().bottom,gap:s.gap,padding:s.padding,
 buttons:[...dock.querySelectorAll('button')].filter(e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden').map(e=>({id:e.id||e.dataset.layer||e.dataset.view||e.dataset.sp,...rect(e)})),
 tabs:[...document.querySelectorAll('.tc-tabs button')].map(rect),
 minimap:rect(document.querySelector('.ls-minimap')),legend:rect(document.querySelector('.ls-hud #hud-1')),
 documentWidth:document.documentElement.scrollWidth,viewport:innerWidth,
 values:[...document.querySelectorAll('#tray-cat .tc-val')].map(e=>e.textContent)};
 });
 await page.screenshot({path:dir+'/'+state+'_'+width+'_'+lang+'.png'});
 checks.push({state,width,lang,metrics,errors:[...errors]});
 fs.writeFileSync(dir+'/checks.json',JSON.stringify(checks,null,2));
 console.log(state,width,lang,JSON.stringify(metrics));
 if(state==='after'){
 const before=checks.find(c=>c.state==='before'&&c.width===width&&c.lang===lang).metrics;
 if(errors.length||metrics.documentWidth>width)failures.push({width,lang,reason:'errors/overflow',errors});
 if(JSON.stringify(before.values)!==JSON.stringify(metrics.values))failures.push({width,lang,reason:'values changed'});
 if(JSON.stringify(before.minimap)!==JSON.stringify(metrics.minimap)||JSON.stringify(before.legend)!==JSON.stringify(metrics.legend))failures.push({width,lang,reason:'minimap/legend changed'});
 const target=width===1920?[800,52]:width===1280?[512,94]:width===1100?[352,85]:null;
 if(target&&(Math.abs(metrics.dock.width-target[0])>.1||Math.abs(metrics.dock.height-target[1])>.1||Math.abs(metrics.bottom-20)>.1))failures.push({width,lang,reason:'dock dimensions',metrics});
 if(width===390&&JSON.stringify(before.dock)!==JSON.stringify(metrics.dock))failures.push({width,lang,reason:'mobile changed'});
 if(width===1100&&metrics.buttons.some(b=>['light','sun','earth','relief','whole','focus','play'].includes(b.id)&&(Math.abs(b.width-32)>.1||Math.abs(b.height-32)>.1)))failures.push({width,lang,reason:'narrow button size'});
 for(const b of metrics.buttons.filter(b=>['light','sun','earth','relief','whole','focus','play'].includes(b.id))){
 if(width>=1100&&(b.x<metrics.dock.x-.1||b.x+b.width>metrics.dock.x+metrics.dock.width+.1||b.y<metrics.dock.y-.1||b.y+b.height>metrics.dock.y+metrics.dock.height+.1))failures.push({width,lang,reason:'button outside dock',b});
 }
 }
 }
 await context.close();
}
// Simulate the still-unmerged PR #97 tray, pinned to its reviewed head.
const integration=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'reduce'});
const ip=await integration.newPage(),ie=[];
ip.on('pageerror',e=>ie.push(e.message));ip.on('console',m=>{if(m.type()==='error')ie.push(m.text())});
const currentCss=fs.readFileSync('web/css/layout.css','utf8');
await ip.route('**/css/layout.css',r=>r.fulfill({contentType:'text/css',body:currentCss+'\n'+fs.readFileSync('verification/design_bundle10/pr97_tray.css','utf8')}));
await ip.route('**/js/tray_cat.js*',r=>r.fulfill({contentType:'application/javascript',body:fs.readFileSync('verification/design_bundle10/pr97_tray.js','utf8')}));
await ip.goto('http://127.0.0.1:8788/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&d=2026-11-14&p=29.5&t=7620',{waitUntil:'domcontentloaded'});
await ip.locator('#tray-cat .tc-row').first().waitFor({timeout:120000});
const tabs=[];
for(const width of [1920,1440,1280,1100])for(const lang of ['en','ko']){
 await ip.setViewportSize({width,height:width===1920?1080:width===1440?900:800});
 await ip.locator('.lang-seg [data-lang="'+lang+'"]').click();await ip.evaluate(()=>document.fonts.ready);
 const m=await ip.evaluate(()=>({tabs:[...document.querySelectorAll('.tc-tabs button')].map(e=>({text:e.textContent,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height})),overflow:document.documentElement.scrollWidth>innerWidth}));
 tabs.push({width,lang,...m,errors:[...ie]});
 if(ie.length||m.overflow||m.tabs.some(t=>Math.abs(t.height-39)>.1))failures.push({width,lang,reason:'PR97 integration',...m,errors:ie});
 if(width===1280||width===1100)await ip.locator('#ls-tray').screenshot({path:dir+'/pr97_'+width+'_'+lang+'_tray.png'});
}
fs.writeFileSync(dir+'/pr97-tabs.json',JSON.stringify({sha:'c147c21e5e747e9fca9fd41b4aa0629c0c2b9c9a',tabs},null,2));
await integration.close();
await browser.close();fs.writeFileSync(dir+'/result.json',JSON.stringify({checks:checks.length,failures},null,2));if(failures.length)process.exitCode=1;
