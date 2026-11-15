import {chromium} from 'playwright';
import fs from 'node:fs';
const browser=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),errors=[],checks=[],failures=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
await page.goto('http://127.0.0.1:8788/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&d=2026-11-14&p=29.5&t=7620',{waitUntil:'domcontentloaded'});
await page.locator('#tray-cat .tc-row').first().waitFor({timeout:120000});
for(const width of [1920,1440,1280,1100,390])for(const lang of ['en','ko']){
await page.setViewportSize({width,height:width===1920?1080:width===1440?900:width===390?844:800});
await page.locator('.lang-seg [data-lang="'+lang+'"]').click();await page.evaluate(()=>document.fonts.ready);await page.keyboard.press('Control+Home');
const m=await page.evaluate(()=>{const d=document.querySelector('.ls-toolbar').getBoundingClientRect();return {width:d.width,height:d.height,bottom:innerHeight-d.bottom,overflow:document.documentElement.scrollWidth>innerWidth,buttons:[...document.querySelectorAll('.ls-toolbar button')].filter(e=>e.getClientRects().length&&e.id!=='utc-chip').map(e=>{const r=e.getBoundingClientRect();return {inside:r.left>=d.left-.1&&r.right<=d.right+.1&&r.top>=d.top-.1&&r.bottom<=d.bottom+.1}})}});
const target=width===1920?[800,52]:width===1280?[512,94]:width===1100?[352,85]:null;
if(errors.length||m.overflow||(width>=1100&&m.buttons.some(b=>!b.inside))||(target&&(m.width!==target[0]||m.height!==target[1]||m.bottom!==20)))failures.push({width,lang,...m,errors:[...errors]});
checks.push({width,lang,...m,errors:[...errors]});
}
await browser.close();fs.writeFileSync('docs/design_sync/bundle10/integration-smoke.json',JSON.stringify({checks,failures},null,2));if(failures.length)process.exitCode=1;
