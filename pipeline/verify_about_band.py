import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path('docs/design_sync/jiyong_about_band');OUT.mkdir(parents=True,exist_ok=True)
async def case(browser,w,h):
 page=await browser.new_page(viewport={'width':w,'height':h},reduced_motion='reduce'); errors=[];page.on('pageerror',lambda e: errors.append(str(e)))
 await page.goto('http://127.0.0.1:8020/#about');await page.wait_for_selector('#heroJourney canvas');await page.wait_for_timeout(700)
 band=await page.locator('.ab-hero').bounding_box();copy=await page.locator('.abh-text').bounding_box();header=await page.locator('.ls-head').bounding_box()
 assert abs(band['height']-h*.25)<1
 assert band['y']>=header['y']+header['height']-1
 assert copy['y']>=band['y'] and copy['y']+copy['height']<=band['y']+band['height']
 assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 print(w,'25% band, header clearance, text bounds, no overflow: PASS')
 await page.screenshot(path=str(OUT/f'about_{w}.png'))
 await page.locator('.ab-next').click();await page.wait_for_timeout(200)
 assert await page.locator('#abScroll').evaluate('(e)=>e.scrollTop')>0
 assert await page.evaluate('window.scrollY')==0
 assert not await page.locator('#abScroll').evaluate('(e)=>e.classList.contains("at-top")')
 await page.locator('#abScroll').evaluate('(e)=>e.scrollTop=e.scrollHeight');await page.wait_for_timeout(100)
 assert await page.locator('.ab-next').get_attribute('aria-label')=='Back to top'
 await page.locator('.ab-next').click();await page.wait_for_timeout(100)
 assert await page.locator('#abScroll').evaluate('(e)=>e.scrollTop')==0
 await page.evaluate("location.hash='' ");await page.wait_for_timeout(200)
 assert await page.locator('#heroJourney canvas').count()==0
 await page.evaluate("location.hash='about'");await page.wait_for_selector('#heroJourney canvas')
 assert await page.locator('#heroJourney canvas').count()==1
 assert not errors,errors
 await page.close();return {'width':w,'checks':'band, internal scroll, fade, next/back, enter/leave, no errors'}
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();results=[await case(b,w,h) for w,h in [(1440,900),(1024,768),(390,844)]]
  (OUT/'checks.json').write_text(json.dumps(results,indent=2));await b.close()
asyncio.run(main())
