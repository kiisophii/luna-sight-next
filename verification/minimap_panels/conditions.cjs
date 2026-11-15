const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),http=require('http'),cp=require('child_process');
const repo=path.resolve(process.env.REPO_ROOT||path.join(__dirname,'../..')),root=path.join(repo,'web'),out=path.resolve(process.env.QA_OUT||path.join(repo,'docs/design_sync/minimap_panels/conditions-rerun'));fs.mkdirSync(out,{recursive:true});
const baseline='13010bc515a15a578f7c838eef29574749b6d8fe';
const oldJs=cp.execFileSync('git',['show',baseline+':web/js/minimap_drag.js'],{cwd:repo,maxBuffer:1000000}).toString();
const mime={'.html':'text/html','.js':'application/javascript','.json':'application/json','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp'};
const server=http.createServer((req,res)=>{let p=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));if(!p.startsWith(root)){res.writeHead(403);return res.end();}if(fs.existsSync(p)&&fs.statSync(p).isDirectory())p=path.join(p,'index.html');fs.stat(p,(e,s)=>{if(e){res.writeHead(404);return res.end();}res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream','Content-Length':s.size});fs.createReadStream(p).pipe(res);});});
const checks=[],failures=[];let browser;const save=()=>{fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(checks,null,2));fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({baseline,cases:checks.length,failures},null,2));};
(async()=>{await new Promise(r=>server.listen(8791,'127.0.0.1',r));browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--enable-unsafe-swiftshader']});
for(const state of ['after'])for(const width of (state==='before'?[1920,1280]:[1920,1440,1280,1100]))for(const lang of (state==='before'?['en']:['en','ko'])){
const context=await browser.newContext({viewport:{width,height:width===1920?1080:width===1440?900:800},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('requestfailed',r=>requests.push({url:r.url(),error:r.failure()}));
const fontdir=process.env.QA_CACHE,manifest=fontdir?JSON.parse(fs.readFileSync(path.join(fontdir,'manifest.json'),'utf8')):{};
await page.route('https://**/*',async r=>{if(!fontdir)return r.continue();const u=r.request().url(),headers={'access-control-allow-origin':'*'};
if(u.includes('fonts.googleapis.com/css2'))return r.fulfill({headers,contentType:'text/css',body:fs.readFileSync(path.join(fontdir,'google.css'),'utf8')});
if(u.includes('pretendardvariable-dynamic-subset.min.css'))return r.fulfill({headers,contentType:'text/css',body:fs.readFileSync(path.join(fontdir,'pretendard.css'),'utf8')});
if(manifest[u])return r.fulfill({headers,contentType:'font/woff2',body:fs.readFileSync(path.join(fontdir,manifest[u]))});
if(u==='https://cdnjs.cloudflare.com/ajax/libs/three.js/0.170.0/three.module.min.js')return r.fulfill({headers,contentType:'application/javascript',body:fs.readFileSync(path.join(fontdir,'three.module.min.js'),'utf8')});return r.continue();});
if(state==='before')await page.route('**/js/minimap_drag.js*',r=>r.fulfill({contentType:'application/javascript',body:oldJs}));
await page.goto('http://127.0.0.1:8791/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&d=2026-11-14&p=29.5&t=7620',{waitUntil:'domcontentloaded',timeout:120000});await page.locator('.tc-row').first().waitFor({timeout:120000});
await page.waitForFunction(()=>!!window.LLSN?.globe?._internal?.camera,null,{timeout:120000});await page.locator('.pn-resize').first().waitFor({state:'attached'});await page.locator('.lang-seg [data-lang="'+lang+'"]').click();await page.evaluate(()=>document.fonts.ready);
const actions=[];const folded=()=>page.locator('#ls-cond').evaluate(e=>e.classList.contains('folded'));
if(!await folded())await page.locator('.c1-tog').click();
for(let i=0;i<3;i++){
await page.locator('.c1-add').click();await page.waitForTimeout(150);
const open=!await folded();actions.push({action:'add condition',open});if(!open)failures.push({width,lang,reason:'Add Condition did not open on first click'});
await page.locator('.fl-done').click();await page.waitForTimeout(100);if(!await folded())failures.push({width,lang,reason:'Done did not close'});
await page.locator('.c1-tog').click();await page.waitForTimeout(100);const headerOpen=!await folded();actions.push({action:'header toggle',open:headerOpen});if(!headerOpen)failures.push({width,lang,reason:'header did not open on first click'});
await page.locator('.c1-tog').click();await page.waitForTimeout(100);
}
if(errors.length||requests.length)failures.push({width,lang,errors,requests});
checks.push({width,lang,actions,errors,requests});save();console.log('CONDITIONS',width,lang,JSON.stringify({errors,requests,failures:failures.length}));await context.close();
}
await browser.close();server.close();save();console.log('DONE',JSON.stringify(failures));if(failures.length)process.exitCode=1;
})().catch(async e=>{console.error(e);save();if(browser)await browser.close();server.close();process.exitCode=1;});
