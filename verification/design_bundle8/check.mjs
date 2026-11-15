import { chromium } from 'playwright';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const dir='docs/design_sync/bundle8';fs.mkdirSync(dir,{recursive:true});
const base='be9aeab5b18fbe3d8e86c6295b8af9e5247c8ce2';
const oldCss=execFileSync('git',['show',base+':web/css/layout.css'],{maxBuffer:2000000}).toString();
const oldJs=execFileSync('git',['show',base+':web/js/tray_cat.js'],{maxBuffer:2000000}).toString();
const browser=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const checks=[];
const url='http://127.0.0.1:8788/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&focus=SHACKLETON_RIM&d=2026-11-14&p=29.5&t=7620';
for(const state of ['before','after']){
 const width=1920,lang='en';
 const context=await browser.newContext({viewport:{width,height:width===1920?1080:width===1440?900:800},reducedMotion:'reduce',locale:lang});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push('pageerror: '+e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 if(state==='before'){
  await page.route('**/css/layout.css',r=>r.fulfill({contentType:'text/css',body:oldCss}));
  await page.route('**/js/tray_cat.js*',r=>r.fulfill({contentType:'application/javascript',body:oldJs}));
 }
 await page.goto(url+'&lang='+lang,{waitUntil:'domcontentloaded',timeout:60000});
 await page.locator('#tray-cat .tc-row').first().waitFor({timeout:120000});
 for(const width of [1920,1440,1280]) for(const lang of ['en','ko']) {
 await page.setViewportSize({width,height:width===1920?1080:width===1440?900:800});
 await page.locator('.tc-tabs [data-c="sun"]').click();
 await page.locator('.tc-subs [data-s="rate"]').click();
 await page.locator('.lang-seg [data-lang="'+lang+'"]').click();
 await page.evaluate(()=>document.fonts.ready);
 await page.keyboard.press('Control+Home');
 await page.waitForFunction(()=>window.scrollY<2);

 const metrics=await page.evaluate(()=>{
  const rect=s=>{const e=document.querySelector(s),r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
  return {tray:rect('#ls-tray'),header:rect('#ls-tray .ls-card-head'),main:rect('#ls-tray .tray-main'),title:rect('.tray-sub'),period:rect('#tray-period'),tabs:rect('.tc-tabs'),chart:rect('.tc-chart'),tab:rect('.tc-tabs button'),row:rect('.tc-row'),documentWidth:document.documentElement.scrollWidth,viewport:innerWidth,values:[...document.querySelectorAll('#tray-cat .tc-val')].map(e=>e.textContent)};
 });
 await page.screenshot({path:dir+'/'+state+'_'+width+'_'+lang+'.png'});
 await page.locator('#ls-tray').screenshot({path:dir+'/'+state+'_'+width+'_'+lang+'_tray.png'});
 const categories=[];
 for(const cat of ['sun','earth','relay','terrain']){
  await page.locator('.tc-tabs [data-c="'+cat+'"]').click();
  await page.locator('.tc-h h4').waitFor();
  for(const sub of await page.locator('.tc-subs button').all()){await sub.click();await page.locator('.tc-row').first().waitFor();categories.push(await page.locator('.tc-h h4').innerText());}
 }
 checks.push({width,lang,state,errors,metrics,categories});
 fs.writeFileSync(dir+'/checks.json',JSON.stringify(checks,null,2));
 console.log('Captured',state,width,lang,JSON.stringify(metrics));
 }
 await context.close();
}
await browser.close();
fs.writeFileSync(dir+'/checks.json',JSON.stringify(checks,null,2));
const valuesStable=checks.filter(c=>c.state==='after').every(c=>JSON.stringify(c.metrics.values)===JSON.stringify(checks.find(b=>b.state==='before'&&b.width===c.width&&b.lang===c.lang).metrics.values));
if(!valuesStable)throw Error('Contest values changed');
const failures=checks.filter(c=>c.state==='after'&&(c.errors.length||c.metrics.documentWidth>c.metrics.viewport||Math.abs(c.metrics.chart.height-100)>.1||Math.abs(c.metrics.row.height-42)>.1));
fs.writeFileSync(dir+'/result.json',JSON.stringify({failures,checks:checks.length},null,2));
if(failures.length)process.exitCode=1;
