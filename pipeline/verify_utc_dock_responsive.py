import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1280,'height':900},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://127.0.0.1:8021/?nointro=1');await page.wait_for_function('window.LLSN?.globe?.flyTo')
  for layer in ['light','sun','earth','elev']:
   await page.locator(f'[data-layer="{layer}"]').click();await page.wait_for_timeout(300);await page.locator('#utc-chip').click();assert await page.locator('#utc-pop').is_visible();await page.keyboard.press('Escape')
  await page.locator('[data-layer="light"]').click()
  for w in [1920,1100,390,1440]:
   await page.set_viewport_size({'width':w,'height':900});await page.wait_for_timeout(350);btn=page.locator('#utc-chip');assert await btn.is_visible();await btn.click();assert await page.locator('#utc-pop').is_visible();await page.keyboard.press('Escape');assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   if w>=1100 and w<1600:
    r=await btn.bounding_box();toolbar=await page.locator('.ls-toolbar').bounding_box();assert r['y']+r['height']<=toolbar['y']
  assert not errors,errors
  Path('docs/design_sync/sitecheck_mobile_dock/responsive.json').write_text(json.dumps({'layers':['light','sun','earth','elev'],'resizeWidths':[1920,1100,390,1440],'errors':errors,'pickerUsable':True,'buttonClearOfToolbar':True},indent=2));print('Layer switching, responsive reparenting, picker and clearance PASS')
  await b.close()
asyncio.run(main())
