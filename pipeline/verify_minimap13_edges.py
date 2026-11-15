import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://127.0.0.1:8020/');await page.wait_for_selector('.mm-grip');await page.wait_for_timeout(350)
  result=await page.evaluate('''async()=>{const box=document.getElementById('ls-minimap');const before=box.getBoundingClientRect().width;box.querySelector('.mm-exp').click();await new Promise(r=>setTimeout(r,80));const middle=box.getBoundingClientRect().width;await new Promise(r=>setTimeout(r,350));return {before,middle,after:box.getBoundingClientRect().width,duration:getComputedStyle(box).transitionDuration};}''')
  assert result['before']==222 and 222<result['middle']<580 and result['after']==580,result
  await page.locator('.mm-exp').press('Escape');await page.wait_for_timeout(400)
  r=await page.locator('.mm-grip').bounding_box();await page.mouse.move(r['x']+r['width']/2,r['y']+9);await page.mouse.down();await page.mouse.move(r['x']+r['width']/2-50,r['y']+89,steps=5);await page.mouse.up();await page.wait_for_timeout(400)
  moved=await page.locator('#ls-minimap').bounding_box();assert moved['x']<798 and moved['y']>64,moved
  await page.locator('.mm-grip').dblclick();await page.wait_for_timeout(600);reset=await page.locator('#ls-minimap').bounding_box();assert abs(reset['x']-798)<1 and abs(reset['y']-64)<1,reset
  result['pointer_drag_and_reset']='pass'
  await page.evaluate('''()=>{localStorage.setItem('ls.minimapSizes.v13',JSON.stringify({closed:{w:500,h:450},open:{w:304,h:228}}));localStorage.setItem('ls.minimapPos',JSON.stringify({fx:1,fy:0}));}''')
  await page.emulate_media(reduced_motion='reduce');await page.reload();await page.wait_for_selector('.mm-grip');await page.locator('.mm-exp').click();await page.wait_for_timeout(200)
  await page.locator('.mm-grip').focus()
  for _ in range(20): await page.locator('.mm-grip').press('Shift+ArrowLeft')
  left=await page.locator('#ls-minimap').bounding_box();panel=await page.locator('.ls-left').bounding_box();assert left['x']==panel['x']+panel['width']+20,left
  for _ in range(20): await page.locator('.mm-grip').press('Shift+ArrowDown')
  bottom=await page.locator('#ls-minimap').bounding_box();dock=await page.locator('.ls-toolbar').bounding_box();assert abs(bottom['y']+bottom['height']-(dock['y']-8))<1,(bottom,dock)
  result['closed_larger_than_open']='left and bottom edges reachable';result['page_errors']=errors;assert not errors,errors
  Path('docs/design_sync/jiyong_minimap13/motion_check.json').write_text(json.dumps(result,indent=2));print(result);await b.close()
asyncio.run(main())
