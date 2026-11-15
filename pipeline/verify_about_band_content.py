import asyncio,json,subprocess
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path('docs/design_sync/jiyong_about_band')
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://127.0.0.1:8020/#about');await page.wait_for_selector('#heroJourney canvas');await page.wait_for_timeout(400)
  shots=[]
  for progress in [0,.35,.6,1]:
   await page.locator('#abScroll').evaluate('(e,p)=>e.scrollTop=p*(e.scrollHeight-e.clientHeight)',progress);await page.wait_for_timeout(1200)
   await page.screenshot(path=str(OUT/f'flight_{progress}.png'))
   shots.append(await page.locator('canvas').last.evaluate('(e)=>e.toDataURL().length'))
  await page.locator('[data-lang="ko"]').click();await page.wait_for_timeout(800)
  assert await page.locator('#heroJourney canvas').count()==1
  await page.screenshot(path=str(OUT/'about_1440_ko.png'))
  await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(300);await page.screenshot(path=str(OUT/'about_390_ko.png'))
  await page.locator('[data-act="how"]').click();await page.wait_for_timeout(1000)
  assert abs((await page.locator('#about-steps').bounding_box())['y']-(await page.locator('#abScroll').bounding_box())['y']-32)<2
  assert await page.evaluate('window.scrollY')==0
  await page.locator('[data-act="explore"]').first.click();await page.wait_for_timeout(200)
  assert await page.locator('#heroJourney canvas').count()==0
  assert not errors,errors
  print('normal motion, Korean, resize, How it works, exit: PASS')
  await b.close()
base=subprocess.check_output(['git','show','9ce8b52:web/js/about.js']).decode('utf-8');now=Path('web/js/about.js').read_text(encoding='utf-8')
a=base[base.index('  <section class="ab-sec" id="about-why"'):base.index('\n`;')]
b=now[now.index('  <section class="ab-sec" id="about-why"'):now.index('\n  </div>\n`;')]
assert a==b,'Body markup changed'
assert subprocess.check_output(['git','diff','--','web/js/about_copy.js'])==b''
print('Body markup and team copy unchanged: PASS')
asyncio.run(main())
