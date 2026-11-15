import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path('docs/design_sync/jiyong_minimap13');OUT.mkdir(parents=True,exist_ok=True)
async def check(p,width,lang):
 browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:(errors.append(str(e)),print(width,lang,'ERROR',e)))
 page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 await page.goto('http://127.0.0.1:8020/');await page.wait_for_selector('.mm-grip');await page.wait_for_function('window.LLSN?.globe?.flyTo');await page.wait_for_timeout(300)
 if lang=='ko':await page.locator('[data-lang="ko"]').click();await page.wait_for_timeout(250)
 box=page.locator('#ls-minimap');ball=page.locator('.mm-ball');closed=await box.bounding_box()
 assert closed['width']==222 and closed['height']==228,closed
 assert (await ball.bounding_box())['width']==200
 print(width,lang,'closed PASS',flush=True)
 await page.screenshot(path=str(OUT/f'closed_{width}_{lang}.png'))
 await page.locator('.mm-exp').click();await page.wait_for_timeout(300);opened=await box.bounding_box()
 assert opened['height']==358
 assert opened['x']+opened['width']==closed['x']+closed['width'] and opened['y']==closed['y']
 if width==1440:assert opened['width']==580 and (await ball.bounding_box())['width']==330
 print(width,lang,'open PASS',flush=True)
 await page.screenshot(path=str(OUT/f'open_{width}_{lang}.png'))
 assert await page.locator('.mm-destination').count()>=7
 assert await page.locator('.mm-list-title').inner_text()==('⌖ 이동 목록' if lang=='ko' else '⌖ Go to')
 await page.evaluate('''()=>{window.__flights=[];const g=LLSN.globe;g.flyTo=x=>{window.__flights.push(x);return undefined;};}''')
 await page.locator('#mm-lat').fill('91');await page.locator('#mm-lon').fill('15');await page.locator('#mm-lon').press('Enter')
 assert await page.locator('.mm-err').inner_text();assert await page.evaluate('__flights.length')==0
 await page.locator('#mm-lat').fill('12.5');await page.locator('[data-hemi="N"]').click();await page.locator('[data-hemi="W"]').click();await page.locator('#mm-lon').press('Enter');await page.wait_for_timeout(100)
 flight=await page.evaluate('__flights.at(-1)');assert flight['lat']==12.5 and flight['lon']==-15,flight
 await page.locator('[data-pole="-90"]').click();assert (await page.evaluate('__flights.at(-1)'))['lat']==-90
 await page.locator('.mm-destination[data-site]').first.click();assert await page.evaluate('__flights.length')>=3
 await page.locator('.mm-exp').press('Escape');await page.wait_for_timeout(150);assert (await box.bounding_box())['width']==222
 # Every edge and corner changes the appropriate dimension and saves closed state.
 for edge in ['n','s','e','w','ne','nw','se','sw']:
  before=await box.bounding_box();r=await page.locator('.mm-'+edge).bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
  dx=10 if 'w' in edge else -10 if 'e' in edge else 0;dy=10 if 'n' in edge else -10 if 's' in edge else 0
  await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,steps=3);await page.mouse.up();await page.wait_for_timeout(130)
  after=await box.bounding_box();assert after['width']<before['width'] or after['height']<before['height'],(edge,before,after)
 saved=await box.bounding_box()
 await page.locator('.mm-exp').click();await page.wait_for_timeout(150);assert (await box.bounding_box())['height']==358
 # Open size stored independently.
 await page.locator('.mm-s').focus();await page.locator('.mm-s').press('ArrowUp');await page.wait_for_timeout(150)
 assert (await box.bounding_box())['height']==348
 await page.locator('.mm-exp').press('Escape');await page.wait_for_timeout(150);assert (await box.bounding_box())['width']==saved['width']
 await page.reload();await page.wait_for_selector('.mm-grip');await page.wait_for_timeout(300)
 assert (await box.bounding_box())['width']==saved['width']
 await page.locator('.mm-exp').click();await page.wait_for_timeout(200);assert (await box.bounding_box())['height']==348
 await page.locator('.mm-exp').press('Escape');await page.locator('.mm-grip').focus();await page.locator('.mm-grip').press('Home');await page.wait_for_timeout(150)
 before=await box.bounding_box();await page.locator('.mm-grip').press('ArrowLeft');await page.wait_for_timeout(150);after=await box.bounding_box();assert after['x']==before['x']-10
 assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 result={'width':width,'language':lang,'closed':closed,'expanded':opened,'page_errors':errors,'checks':'8 pointer resize handles, independent size persistence, coordinate validation/hemispheres, flyTo arguments, poles/catalogue, Escape, keyboard move/reset, no overflow'}
 await browser.close();return result
async def main():
 async with async_playwright() as p:
  results=[await check(p,w,lang) for w,lang in [(1440,'en'),(1440,'ko'),(1280,'en'),(1280,'ko')]]
  (OUT/'checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results,indent=2))
asyncio.run(main())

