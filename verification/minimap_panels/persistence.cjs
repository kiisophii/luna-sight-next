const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),http=require('http'),cp=require('child_process');
const repo=path.resolve(process.env.REPO_ROOT||path.join(__dirname,'../..')),root=path.join(repo,'web'),out=path.resolve(process.env.QA_OUT||path.join(repo,'docs/design_sync/minimap_panels/rerun'));fs.mkdirSync(out,{recursive:true});
const baseline='13010bc515a15a578f7c838eef29574749b6d8fe';
const oldJs=cp.execFileSync('git',['show',baseline+':web/js/minimap_drag.js'],{cwd:repo,maxBuffer:1000000}).toString();
const mime={'.html':'text/html','.js':'application/javascript','.json':'application/json','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp'};
const server=http.createServer((req,res)=>{let p=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));if(!p.startsWith(root)){res.writeHead(403);return res.end();}if(fs.existsSync(p)&&fs.statSync(p).isDirectory())p=path.join(p,'index.html');fs.stat(p,(e,s)=>{if(e){res.writeHead(404);return res.end();}res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Content-Length':s.size});fs.createReadStream(p).pipe(res);});});
const checks=[],failures=[];let browser;const save=()=>{fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(checks,null,2));fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({baseline,cases:checks.length,failures},null,2));};
(async()=>{await new Promise(r=>server.listen(8789,'127.0.0.1',r));browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-unsafe-swiftshader']});
for(const state of ['after'])for(const width of (state==='before'?[1920,1280]:[1920]))for(const lang of (state==='before'?['en']:['en'])){
const context=await browser.newContext({viewport:{width,height:width===1920?1080:width===1440?900:800},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('requestfailed',r=>requests.push({url:r.url(),error:r.failure()}));
const fontdir=process.env.QA_CACHE,manifest=fontdir?JSON.parse(fs.readFileSync(path.join(fontdir,'manifest.json'),'utf8')):{};
await page.route('https://**/*',async r=>{if(!fontdir)return r.continue();const u=r.request().url(),headers={'access-control-allow-origin':'*'};
if(u.includes('fonts.googleapis.com/css2'))return r.fulfill({headers,contentType:'text/css',body:fs.readFileSync(path.join(fontdir,'google.css'),'utf8')});
if(u.includes('pretendardvariable-dynamic-subset.min.css'))return r.fulfill({headers,contentType:'text/css',body:fs.readFileSync(path.join(fontdir,'pretendard.css'),'utf8')});
if(manifest[u])return r.fulfill({headers,contentType:'font/woff2',body:fs.readFileSync(path.join(fontdir,manifest[u]))});
if(u==='https://cdnjs.cloudflare.com/ajax/libs/three.js/0.170.0/three.module.min.js')return r.fulfill({headers,contentType:'application/javascript',body:fs.readFileSync(path.join(fontdir,'three.module.min.js'),'utf8')});return r.continue();});
if(state==='before')await page.route('**/js/minimap_drag.js*',r=>r.fulfill({contentType:'application/javascript',body:oldJs}));
await page.goto('http://127.0.0.1:8789/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&d=2026-11-14&p=29.5&t=7620',{waitUntil:'domcontentloaded',timeout:120000});await page.locator('.tc-row').first().waitFor({timeout:120000});
await page.waitForFunction(()=>!!window.LLSN?.globe?._internal?.camera,null,{timeout:120000});await page.locator('.pn-resize').first().waitFor();await page.locator('.lang-seg [data-lang="'+lang+'"]').click();await page.evaluate(()=>document.fonts.ready);
const states=[];let initial;
const snapshot=async name=>{
await page.waitForFunction(()=>['#ls-left','#ls-tray'].every(s=>document.querySelector(s).getAnimations().every(a=>a.playState!=='running')),null,{timeout:20000});
await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await page.waitForTimeout(100);
const m=await page.evaluate(()=>{const rect=e=>{if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom,visible:!e.hidden&&getComputedStyle(e).visibility!=='hidden'&&!!e.getClientRects().length}};const q=s=>document.querySelector(s);return{offL:document.documentElement.classList.contains('lp-off'),offR:document.documentElement.classList.contains('rp-off'),left:rect(q('#ls-left')),tray:rect(q('#ls-tray')),mini:rect(q('#ls-minimap')),dock:rect(q('.ls-toolbar')),hud:rect(q('.hud-t')),legend:rect(q('#hud-1')),note:rect(q('#globe-stage .g3-dock')),edgeL:rect(q('#pn-edge-l')),edgeR:rect(q('#pn-edge-r')),projection:(()=>{const g=window.LLSN?.globe,cam=g?._internal?.camera,st=q('#globe-stage')?.getBoundingClientRect();if(!cam||!st)return null;const v=cam.position.clone().set(0,0,0).project(cam);return{centre:st.left+st.width/2-(cam.view?.enabled?cam.view.offsetX:0),sphere:st.left+(v.x+1)*st.width/2};})(),labels:[q('#pn-edge-l'),q('#pn-edge-r')].map(e=>{const range=document.createRange();range.selectNodeContents(e);const z=range.getBoundingClientRect();return{text:e.textContent,rect:rect(e),ink:{x:z.x,y:z.y,right:z.right,bottom:z.bottom}};}),docWidth:document.documentElement.scrollWidth,viewport:innerWidth};});
if(!initial)initial=m;const l=m.offL?48:m.left.right+20,r=m.offR?width-48:m.tray.x-20;
const bad=[];if(m.mini.x<l-.6||m.mini.right>r+.6)bad.push('minimap outside logical map bounds');
for(const e of [m.edgeL,m.edgeR])if(e?.visible)for(const [key,b]of [['minimap',m.mini],['height note',m.note]])if(b?.visible&&Math.min(e.right,b.right)>Math.max(e.x,b.x)+.5&&Math.min(e.bottom,b.bottom)>Math.max(e.y,b.y)+.5)bad.push(key+' overlaps edge tab');
if(name.includes('restored')&&!name.startsWith('restored_resize'))for(const k of ['mini','dock','hud'])if(['x','y','width','height'].some(d=>Math.abs(m[k][d]-initial[k][d])>.6))bad.push(k+' did not restore');
if(m.docWidth>width)bad.push('document horizontal overflow');
for(const label of m.labels)if(label.rect.visible&&(label.ink.x<label.rect.x-1||label.ink.right>label.rect.right+1||label.ink.y<label.rect.y-1||label.ink.bottom>label.rect.bottom+1))bad.push('edge label clipped');
const expected=(l+r)/2;if(!m.projection||Math.abs(m.projection.centre-expected)>1)bad.push('3D projection centre incorrect');
if(initial.projection&&m.projection&&Math.abs((m.projection.sphere-expected)-(initial.projection.sphere-(initial.left.right+20+initial.tray.x-20)/2))>1)bad.push('3D sphere moved incorrectly');
const entry={name,map:{l,r},metrics:m,bad};states.push(entry);if(state==='after'&&bad.length)failures.push({width,lang,...entry});return m;};
await snapshot('baseline');
for(let cycle=0;cycle<0;cycle++){
await page.locator('#pn-fold-l').click();await snapshot(cycle+'_left_off');
await page.locator('#pn-edge-l').click();await snapshot(cycle+'_restored_left');
await page.locator('#pn-fold-r').click();await snapshot(cycle+'_right_off');
if(cycle===0&&width===1280&&lang==='en')await page.screenshot({path:path.join(out,state+'_1280_right.jpg'),type:'jpeg',quality:90,clip:{x:width-450,y:50,width:450,height:430}});
await page.locator('#pn-edge-r').click();await snapshot(cycle+'_restored_right');
if(cycle===0&&width===1920&&lang==='en')await page.screenshot({path:path.join(out,state+'_1920_restored.jpg'),type:'jpeg',quality:90,clip:{x:width-700,y:50,width:700,height:450}});
await page.locator('#pn-fold-l').click();await page.locator('#pn-fold-r').click();await snapshot(cycle+'_both_off');
await page.locator('#pn-edge-l').click();await snapshot(cycle+'_right_only');
await page.locator('#pn-edge-r').click();await snapshot(cycle+'_restored_both');
}
if(state==='after'){await page.locator('#pn-fold-r').click();await page.locator('#pn-edge-r').click();await snapshot('rapid_restored');if(errors.length||requests.length)failures.push({width,lang,reason:'browser errors',errors,requests});}
const resizeResults=[];
for(const side of ['l','r']){
const selector=side==='l'?'#ls-left':'#ls-tray',handle=page.locator('.pn-resize.'+side);
const original=(await page.locator(selector).boundingBox()).width;
const dragBy=async pixels=>{const h=await handle.boundingBox();await page.mouse.move(h.x+h.width/2,h.y+35);await page.mouse.down();await page.mouse.move(h.x+h.width/2+pixels,h.y+35,{steps:5});await page.mouse.up();};
await dragBy(side==='l'?24:-24);const grown=(await page.locator(selector).boundingBox()).width;
if(grown<original+8)failures.push({width,lang,side,reason:'panel did not grow',original,grown});await snapshot('resize_'+side+'_grown');
await dragBy(side==='l'?-48:48);const shrunk=(await page.locator(selector).boundingBox()).width;
if(shrunk>original-8)failures.push({width,lang,side,reason:'panel did not shrink',original,shrunk});await snapshot('resize_'+side+'_shrunk');
await handle.press('Home');const reset=(await page.locator(selector).boundingBox()).width;
if(Math.abs(reset-original)>.5)failures.push({width,lang,side,reason:'panel width reset failed',original,reset});await snapshot('restored_resize_'+side);resizeResults.push({side,original,grown,shrunk,reset});
}
await page.locator('.pn-resize.l').press('Shift+ArrowRight');await page.locator('.pn-resize.l').press('Shift+ArrowRight');await page.locator('.pn-resize.r').press('Shift+ArrowLeft');
await snapshot('custom_widths');const saved={l:(await page.locator('#ls-left').boundingBox()).width,r:(await page.locator('#ls-tray').boundingBox()).width};
await page.reload({waitUntil:'domcontentloaded'});await page.locator('.pn-resize').first().waitFor();await page.waitForFunction(()=>!!window.LLSN?.globe?._internal?.camera);await page.evaluate(()=>document.fonts.ready);
const loaded={l:(await page.locator('#ls-left').boundingBox()).width,r:(await page.locator('#ls-tray').boundingBox()).width};if(JSON.stringify(saved)!==JSON.stringify(loaded))failures.push({reason:'width persistence',saved,loaded});
await snapshot('loaded_widths');await page.locator('#ls-left').screenshot({path:path.join(out,'resized-left.jpg'),type:'jpeg',quality:88});await page.locator('#ls-tray').screenshot({path:path.join(out,'resized-right.jpg'),type:'jpeg',quality:88});
await page.locator('#pn-fold-l').click();await page.locator('#pn-fold-r').click();await snapshot('custom_both_off');await page.locator('#pn-edge-l').screenshot({path:path.join(out,'conditions-label.jpg'),type:'jpeg',quality:95});await page.locator('#pn-edge-r').screenshot({path:path.join(out,'compare-label.jpg'),type:'jpeg',quality:95});
await page.locator('#pn-edge-l').click();await page.locator('#pn-edge-r').click();await snapshot('custom_open');await page.locator('.pn-resize.l').press('Home');await page.locator('.pn-resize.r').press('Home');await snapshot('restored_persistence');
resizeResults.push({persistence:{saved,loaded}});
checks.push({state,width,lang,states,errors,requests,resizeResults});save();console.log('CHECK',state,width,lang,'states',states.length,'failures',failures.length);await context.close();
}
await browser.close();server.close();save();console.log('DONE',JSON.stringify(failures));if(failures.length)process.exitCode=1;
})().catch(async e=>{console.error(e);save();if(browser)await browser.close();server.close();process.exitCode=1;});
