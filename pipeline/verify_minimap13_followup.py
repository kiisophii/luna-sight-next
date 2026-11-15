import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path('docs/design_sync/jiyong_minimap13')
async def main():
 results=[]
 async with async_playwright() as p:
  for width in (390,768):
   for lang in ('en','ko'):
    browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce');errors=[]
    page.on('requestfailed',lambda r:print('FAILED',r.url,r.failure,flush=True));page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    await page.goto('http://127.0.0.1:8020/');await page.wait_for_selector('.mm-exp');await page.wait_for_function('window.LLSN?.globe?.flyTo');await page.wait_for_timeout(500)
    if lang=='ko':await page.locator('[data-lang="ko"]').click()
    box=page.locator('#ls-minimap');closed=await box.bounding_box();globe=await page.locator('#globe-stage canvas').first.bounding_box()
    assert closed['y']>=globe['y']+globe['height'],(closed,globe)
    await box.scroll_into_view_if_needed();await page.screenshot(path=str(OUT/f'followup_closed_{width}_{lang}.png'))
    await page.locator('.mm-exp').click();await page.wait_for_timeout(250)
    opened=await box.bounding_box();assert opened['width']<=width-32 and opened['x']>=0,opened
    assert await page.locator('.mm-dest-icon svg').count()==await page.locator('.mm-destination').count()
    assert await page.locator('[data-pole="-90"] small').inner_text()=='90.00°S'
    assert ',' in await page.locator('.mm-destination[data-site] small').first.inner_text()
    assert not any('#' in x for x in await page.locator('.mm-tag').all_text_contents())
    icon=await page.locator('.mm-dest-icon').first.bounding_box();assert icon['width']==28 and icon['height']==28
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    await page.screenshot(path=str(OUT/f'followup_open_{width}_{lang}.png'))
    await page.evaluate('document.activeElement.blur()');await page.keyboard.press('Escape');assert not await box.evaluate("e=>e.classList.contains('open')")
    assert not errors,errors
    results.append(dict(width=width,language=lang,closed=closed,globe=globe,opened=opened,errors=errors,overflow=False,checks='icon boxes, coordinates/categories, Escape with focus outside, separate minimap row'))
    print(width,lang,'PASS',flush=True);await browser.close()
 (OUT/'followup_checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
asyncio.run(main())
