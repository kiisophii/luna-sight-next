// Focused real-browser check. Requires Playwright via NODE_PATH and installed browsers.
// Usage: node pipeline/verify_cluster_first_click.cjs [--baseline COMMIT] [--out DIR] [--quick]
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {chromium, webkit} = require('playwright');
const repo = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const option = key => args.includes(key) ? args[args.indexOf(key) + 1] : null;
const baseline = option('--baseline');
const out = path.resolve(option('--out') || path.join(repo, 'docs/qa/cluster-first-click', baseline ? 'baseline' : 'fixed'));
fs.mkdirSync(out, {recursive:true});
const original = baseline ? execFileSync('git', ['-c', `safe.directory=${repo.replaceAll('\\','/')}`, '-C', repo, 'show', `${baseline}:web/js/globe3d.js`]) : null;
const web = path.join(repo, 'web');
const mime = {'.html':'text/html', '.js':'text/javascript', '.json':'application/json', '.css':'text/css', '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml', '.bin':'application/octet-stream'};
const server = http.createServer((req,res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const file = path.resolve(web, '.' + pathname, pathname.endsWith('/') ? 'index.html' : '');
  if (!file.startsWith(web + path.sep)) {res.writeHead(403).end();return;}
  if (original && pathname === '/js/globe3d.js') {res.writeHead(200, {'content-type':'text/javascript'});res.end(original);return;}
  fs.stat(file, (error, stat) => {
    if (error || !stat.isFile()) {res.writeHead(404).end();return;}
    res.writeHead(200, {'content-type':mime[path.extname(file)] || 'application/octet-stream'});
    fs.createReadStream(file).pipe(res);
  });
});
const scenarios = baseline ? [{width:1440,height:900,lang:'en',layer:'light',fold:false}] : [
  {width:1440,height:900,lang:'en',layer:'light',fold:false},
  {width:1440,height:900,lang:'ko',layer:'elev',fold:false},
  {width:1280,height:800,lang:'en',layer:'elev',fold:false},
  {width:1280,height:800,lang:'ko',layer:'light',fold:false},
  {width:1440,height:900,lang:'en',layer:'elev',fold:true},
];
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const results = [];
  try {
    for (const [engine, type] of [['chromium',chromium], ['webkit',webkit]]) {
      const browser = await type.launch({headless:true,...(engine === 'chromium' ? {args:['--enable-unsafe-swiftshader']} : {})});
      try {
        for (const scenario of scenarios.filter(s => !args.includes('--quick') || (s.width === 1280 && s.lang === 'en'))) {
          const name = `${engine}-${scenario.width}-${scenario.lang}-${scenario.layer}${scenario.fold?'-folded':''}`;
          const result = {name,engine,browserVersion:browser.version(),...scenario,status:'FAIL',pageErrors:[],consoleErrors:[],warnings:[]};
          const page = await browser.newPage({viewport:{width:scenario.width,height:scenario.height}});
          page.on('pageerror', e => result.pageErrors.push(e.message));
          page.on('console', m => {if(m.type()==='error')result.consoleErrors.push(m.text());if(m.type()==='warning')result.warnings.push(m.text());});
          try {
            await page.addInitScript(() => localStorage.setItem('ls.introSeen','1'));
            await page.goto(`http://127.0.0.1:${server.address().port}/?gv=-30,20,6500,0,0&lang=${scenario.lang}`, {waitUntil:'load'});
            await page.waitForFunction(() => window.LLSN?.globe, {timeout:45000});
            if (scenario.fold) await page.locator('#pn-fold-l').click();
            if (scenario.layer === 'elev') {
              await page.locator('[data-layer="elev"]').click();
              await page.locator('#map-legend').waitFor({state:'visible'});
            }
            const button = page.locator('.g3-cluster').filter({hasText:/^\+16$/});
            await button.waitFor({state:'visible',timeout:10000});
            await page.waitForTimeout(800); // allow layout and 400 ms declutter cycles to settle
            const before = await button.evaluate(b => {
              window.__clusterProbe = {button:b,node:b.firstChild,mutations:0};
              window.__clusterObserver = new MutationObserver(records => window.__clusterProbe.mutations += records.filter(r=>r.type==='childList').length);
              window.__clusterObserver.observe(b,{childList:true});
              const r=b.getBoundingClientRect(), legend=document.querySelector('#map-legend');
              const l=legend && !legend.hidden ? legend.getBoundingClientRect() : null;
              const overlap=!!l && r.left<l.right && l.left<r.right && r.top<l.bottom && l.top<r.bottom;
              const hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
              return {button:r.toJSON(),legend:l?.toJSON()||null,legendOverlap:overlap,hitTargetIsButton:!!hit?.closest('.g3-cluster')};
            });
            result.before=before;
            assert.equal(before.legendOverlap,false,'+16 overlaps the elevation legend');
            assert.equal(before.hitTargetIsButton,true,'+16 is covered at its click point');
            await page.mouse.move(before.button.x+before.button.width/2,before.button.y+before.button.height/2);
            await page.mouse.down();
            await page.waitForTimeout(650); // press spans at least one scheduled declutter cycle
            result.nodeDuringPress=await page.evaluate(()=>({sameButton:window.__clusterProbe.button.isConnected,sameTextNode:window.__clusterProbe.node===window.__clusterProbe.button.firstChild,childReplacements:window.__clusterProbe.mutations}));
            await page.mouse.up();
            await page.waitForTimeout(100);
            result.firstClickOpened=await page.locator('.g3-cluster-panel').isVisible();
            await page.evaluate(()=>window.__clusterObserver.disconnect());
            if(!baseline){assert.equal(result.nodeDuringPress.sameTextNode,true,'text node replaced during press');assert.equal(result.nodeDuringPress.childReplacements,0);assert.equal(result.firstClickOpened,true,'first click did not open list');}
            if(result.firstClickOpened){
              result.panel=await page.locator('.g3-cluster-panel').evaluate(panel=>{
                const p=panel.getBoundingClientRect(), b=window.__clusterProbe.button.getBoundingClientRect();
                const blockers=['.ls-toolbar','.ls-head','#map-legend'].map(s=>{const e=document.querySelector(s);if(!e||e.hidden)return null;const r=e.getBoundingClientRect();return r.width&&r.height?{selector:s,...r.toJSON()}:null;}).filter(Boolean);
                const overlaps=blockers.filter(r=>p.left<r.right&&r.left<p.right&&p.top<r.bottom&&r.top<p.bottom).map(r=>r.selector);
                const rows=[...panel.querySelectorAll('[data-site-id]')];
                return {rect:p.toJSON(),button:b.toJSON(),rows:rows.length,overlaps,direction:p.bottom<=b.top?'above':p.top>=b.bottom?'below':'beside',minRowHeight:Math.min(...rows.map(r=>r.getBoundingClientRect().height)),scrollable:panel.scrollHeight>panel.clientHeight};
              });
              assert.deepEqual(result.panel.overlaps,[],'list overlaps dock/header/legend');
              assert.equal(result.panel.rows,16);
              assert.ok(result.panel.minRowHeight>=32);
              assert.ok(result.panel.rect.top>=0 && result.panel.rect.bottom<=scenario.height);
              await page.screenshot({path:path.join(out,name+'.png')});
              const last=page.locator('.g3-cluster-panel [data-site-id]').last();
              result.expectedSelection=await last.getAttribute('data-site-id');
              await last.scrollIntoViewIfNeeded();
              result.lastRowHit=await last.evaluate(e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!hit && e.contains(hit);});
              assert.equal(result.lastRowHit,true,'last row is covered');
              await last.click();
              await page.waitForFunction(id=>window.LLSN.focus===id,result.expectedSelection);
              result.selected=await page.evaluate(()=>window.LLSN.focus);
              assert.equal(await page.locator('.g3-cluster-panel').isVisible(),false);
            }
            assert.deepEqual(result.pageErrors,[]);
            assert.deepEqual(result.consoleErrors,[]);
            result.status=baseline?'OBSERVED':'PASS';
          } catch(error){result.error=error.message;if(!baseline)process.exitCode=1;await page.screenshot({path:path.join(out,name+'-failure.png')}).catch(()=>{});}
          finally {await page.close();}
          results.push(result);
          console.log(JSON.stringify({name,status:result.status,firstClickOpened:result.firstClickOpened,nodeDuringPress:result.nodeDuringPress,error:result.error}));
        }
      } finally {await browser.close();}
    }
  } finally {await new Promise(resolve=>server.close(resolve));}
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({testedAt:new Date().toISOString(),baseline,scope:'Local integration app, fixed camera; Windows WebKit is not actual Safari/iOS hardware',results},null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
