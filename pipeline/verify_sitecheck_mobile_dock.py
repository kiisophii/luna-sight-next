import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path('docs/design_sync/sitecheck_mobile_dock');OUT.mkdir(parents=True,exist_ok=True)
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  for width in (390,1100,1280,1440):
   for lang in ('en','ko'):
    page=await browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce');errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    await page.goto(f'http://127.0.0.1:8021/?nointro=1&lang={lang}');await page.wait_for_function('window.LLSN?.globe?.flyTo');await page.wait_for_timeout(500)
    button=page.locator('#utc-chip');assert await button.is_visible();assert await button.get_attribute('aria-label')
    await button.focus();await page.keyboard.press('Enter');await page.locator('#utc-pop').wait_for(state='visible')
    old=await page.evaluate('LLSN.now()');await page.locator('#t-tod').fill('13:15');await page.locator('#t-tod').dispatch_event('change');await page.wait_for_timeout(150)
    assert abs((await page.evaluate('LLSN.now()'))%24-13.25)<1e-6
    pop=await page.locator('#utc-pop').bounding_box();assert pop['x']>=0 and pop['x']+pop['width']<=width
    await page.screenshot(path=str(OUT/f'dock_{width}_{lang}.png'));await page.keyboard.press('Escape');assert await page.locator('#utc-pop').is_hidden()
    await page.locator('#ls-compare .detail-see').first.click();await page.wait_for_selector('#blk-time .sc-kpis');await page.wait_for_timeout(500)
    labels=await page.locator('#blk-time .sc-kv > span').evaluate_all("els=>els.map(e=>({text:e.textContent,title:e.title,h:e.getBoundingClientRect().height,scroll:e.scrollHeight,w:e.clientWidth,scrollW:e.scrollWidth,white:getComputedStyle(e).whiteSpace}))")
    assert labels and all(l['text']==l['title'] for l in labels)
    if width==390:assert all(l['h']<=32.1 and l['scroll']<=33 and l['scrollW']<=l['w']+1 and l['white']=='normal' for l in labels),labels
    ticks=await page.locator('#blk-time .sc-axis span:visible').evaluate_all("els=>els.map(e=>({left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}))")
    assert len(ticks)==(3 if width==390 else 5),ticks
    assert all(a['right']+2<=b['left'] for a,b in zip(ticks,ticks[1:])),ticks
    await page.locator('#blk-time').evaluate('e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-64)');await page.screenshot(path=str(OUT/f'time_{width}_{lang}.png'))
    await page.wait_for_function("document.querySelector('#blk-time').textContent.includes('43,824')||document.querySelector('#blk-time .mini-tbl')")
    text=await page.locator('#ls-brief').inner_text();assert not any(x in text for x in ['member check pending','integrator re-check','팀원 검증 대기','통합 담당 재계산'])
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');assert not errors,errors
    results.append(dict(width=width,language=lang,errors=errors,overflow=False,labels=labels,ticks=ticks,utcPicker=True,preciseTime=13.25,internalStatusRemoved=True));print(width,lang,'PASS',flush=True);await page.close()
  await browser.close()
 (OUT/'checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
asyncio.run(main())
