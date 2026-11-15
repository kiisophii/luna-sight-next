import {chromium} from 'playwright';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const dir='docs/design_sync/bundle10/subtabs';fs.mkdirSync(dir,{recursive:true});
const baseline=process.env.BASELINE;
const oldCss=execFileSync('git',['show',baseline+':web/css/layout.css'],{maxBuffer:2000000}).toString();
const fix=fs.readFileSync('verification/design_bundle10/subtabs.css','utf8');
const browser=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const checks=[],failures=[];
for(const mode of ['production','pr97']){
const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'}),errors=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
await page.route('**/css/layout.css',r=>r.fulfill({contentType:'text/css',body:oldCss+(mode==='pr97'?'\n'+fs.readFileSync('verification/design_bundle10/pr97_tray.css','utf8'):'')}));
if(mode==='pr97')await page.route('**/js/tray_cat.js*',r=>r.fulfill({contentType:'application/javascript',body:fs.readFileSync('verification/design_bundle10/pr97_tray.js','utf8')}));
await page.goto('http://127.0.0.1:8788/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&d=2026-11-14&p=29.5&t=7620',{waitUntil:'domcontentloaded'});
await page.locator('#tray-cat .tc-row').first().waitFor({timeout:120000});
for(const width of [1440,1280])for(const lang of ['en','ko']){
await page.setViewportSize({width,height:width===1440?900:800});
await page.locator('.lang-seg [data-lang="'+lang+'"]').click();await page.evaluate(()=>document.fonts.ready);
for(const cat of ['sun','earth','relay','terrain']){
await page.locator('.tc-tabs [data-c="'+cat+'"]').click();
for(const state of ['before','after']){
let style;if(state==='after')style=await page.addStyleTag({content:fix});
const m=await page.evaluate(()=>{
const rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
const h=document.querySelector('.tc-h'),title=h.querySelector('h4'),info=h.querySelector('.tc-i'),subs=h.querySelector('.tc-subs');
return{header:rect(h),title:rect(title),info:rect(info),subs:rect(subs),buttons:[...subs.querySelectorAll('button')].map(e=>({...rect(e),font:getComputedStyle(e).fontSize,text:e.textContent})),scroll:{width:document.querySelector('.tc-scroll').scrollWidth,client:document.querySelector('.tc-scroll').clientWidth},overflow:document.documentElement.scrollWidth>innerWidth,values:[...document.querySelectorAll('.tc-val')].map(e=>e.textContent)};
});
checks.push({mode,width,lang,cat,state,metrics:m,errors:[...errors]});
if(width===1280&&lang==='en'&&state==='after'&&(cat==='sun'||cat==='earth'))await page.locator('.tc-h').screenshot({path:dir+'/'+mode+'_'+width+'_'+lang+'_'+cat+'_'+state+'.png'});
if(state==='after'){
const b=checks.at(-2).metrics;
if(errors.length||m.overflow||m.scroll.width>m.scroll.client)failures.push({mode,width,lang,cat,reason:'errors/overflow',errors});
if(width===1440&&JSON.stringify(m)!==JSON.stringify(b))failures.push({mode,width,lang,cat,reason:'1440 changed',before:b,after:m});
if(width===1280&&lang==='en'&&(Math.abs(m.title.y+m.title.height/2-m.subs.y-m.subs.height/2)>1||m.info.right>m.subs.x+.1||m.buttons.some(t=>t.font!=='14px'||t.right>m.header.right+.1)||m.subs.right>m.header.right+.1))failures.push({mode,width,lang,cat,reason:'inline/font/containment',metrics:m});
if(JSON.stringify(m.values)!==JSON.stringify(b.values))failures.push({mode,width,lang,cat,reason:'values changed'});
await style.evaluate(e=>e.remove());
}
}
}
}
await page.close();
}
await browser.close();fs.writeFileSync(dir+'/checks.json',JSON.stringify(checks,null,2));fs.writeFileSync(dir+'/result.json',JSON.stringify({baseline,cases:checks.length,failures},null,2));if(failures.length)process.exitCode=1;
