import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path('docs/design_sync/detail_visibility');OUT.mkdir(parents=True,exist_ok=True)
async def main():
 results=[]
 async with async_playwright() as p:
  for width in (1440,1280,390):
   for lang in ('en','ko'):
    browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce');errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    await page.goto('http://127.0.0.1:8021/');await page.wait_for_selector('.sc-hidden-toggle',state='attached');await page.wait_for_timeout(500)
    if lang=='ko':await page.locator('[data-lang="ko"]').click();await page.wait_for_timeout(500)
    await page.locator('#ls-compare [data-tab="alt"]').click();await page.wait_for_selector('#ls-compare .alt-geometry')
    await page.evaluate("()=>{const e=document.querySelector('#ls-compare .alt-card');window.scrollTo(0,e.getBoundingClientRect().top+scrollY-60)}")
    assert await page.locator('#ls-compare [data-visibility="sun"]').count()>=1
    assert await page.locator('#ls-compare .alt-needle').first.get_attribute('stroke-width')=='2.5'
    # Cross-check visible SVG run hours against the existing hourly geometry bits.
    data=await page.evaluate('''async()=>{const {hourBits}=await import('./js/values.js');const w=LLSN.window;const site=LLSN.state.sites.find(s=>s.id===document.querySelector('#ls-compare .alt-now').dataset.id);const bits=hourBits(site,w.i0,w.i1);const svg=document.querySelector('#ls-compare .alt-geometry');return ['sun','earth'].map((key,j)=>({key,expected:[...bits].filter(b=>b&(1<<j)).length,actual:[...svg.querySelectorAll(`[data-visibility="${key}"] [data-len]`)].reduce((s,e)=>s+Number(e.dataset.len),0)}))}''')
    assert all(x['expected']==x['actual'] for x in data),data
    await page.screenshot(path=str(OUT/f'alt_{width}_{lang}.png'))
    await page.locator('.big-cmp .r-why .why-btn').first.click();await page.wait_for_timeout(500)
    toggle=page.locator('.sc-hidden-toggle');await toggle.click();assert await page.locator('#sc-unavailable').is_visible()
    assert await page.locator('#sc-unavailable .sc-chip').count()>=2
    await toggle.click();assert await page.locator('#sc-unavailable').is_hidden()
    await page.locator('[data-chip="gs"]').click();await page.locator('[data-chip="relay"]').click()
    for block in ['gs','relay']:
     await page.locator(f'#blk-{block} .geometry-strip').wait_for(state='visible')
     await page.evaluate('(id)=>{const e=document.getElementById(id);window.scrollTo(0,e.getBoundingClientRect().top+scrollY-60)}',f'blk-{block}')
     await page.screenshot(path=str(OUT/f'{block}_{width}_{lang}.png'))
    assert await page.locator('#blk-relay .geometry-strip').get_attribute('preserveAspectRatio')=='none'
    blocked=await page.evaluate("""async()=>{const {hourBits}=await import('./js/values.js');const w=LLSN.window,s=LLSN.state.sites.find(s=>s.id===LLSN.focus),bits=hourBits(s,w.i0,w.i1);return {expected:[...bits].filter(b=>!(b&2)).length,actual:[...document.querySelectorAll('#blk-gs .geometry-strip,#blk-relay .geometry-strip')].map(svg=>[...svg.querySelectorAll('[data-len]')].reduce((n,e)=>n+Number(e.dataset.len),0))}}""")
    assert len(blocked['actual'])==2 and all(n==blocked['expected'] for n in blocked['actual']),blocked
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    results.append(dict(width=width,lang=lang,errors=errors,overflow=False,runs=data,blocked=blocked));print(width,lang,'PASS',flush=True);await browser.close()
 (OUT/'checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
asyncio.run(main())
