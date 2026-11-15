import {chromium} from 'playwright';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const dir='docs/design_sync/bundle10';fs.mkdirSync(dir,{recursive:true});
const base='490c0248990709c098a9c6fff28771c23255844e';
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
 await page.setViewportSize({width,height:width===1920?1080:width===1440?900:844});
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
 for(const b of metrics.buttons.filter(b=>['light','sun','earth','relief','whole','focus','play'].includes(b.id))){
 if(width>=1100&&(b.x<metrics.dock.x-.1||b.x+b.width>metrics.dock.x+metrics.dock.width+.1||b.y<metrics.dock.y-.1||b.y+b.height>metrics.dock.y+metrics.dock.height+.1))failures.push({width,lang,reason:'button outside dock',b});
 }
 }
 }
 await context.close();
}
await browser.close();fs.writeFileSync(dir+'/result.json',JSON.stringify({checks:checks.length,failures},null,2));if(failures.length)process.exitCode=1;
