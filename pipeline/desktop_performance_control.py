"""Browser-only diagnostic controls; run from the repository root after desktop_performance.py."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('pipeline').resolve()))
from desktop_performance import PROBE,phase,capture_load,idle
from playwright.sync_api import sync_playwright
out=Path('data/processed/desktop_perf');results={}
with sync_playwright() as pw:
 for case in ['normal','no_hires','no_shadow']:
  b=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=False,args=['--window-size=1920,1080','--force-device-scale-factor=1'])
  c=b.new_context(viewport={'width':1920,'height':1080});c.add_init_script(PROBE);p=c.new_page();p.bring_to_front()
  def override(route):
   response=route.fetch();source=response.text()
   old,new = ('if (view.range < HIRES_RANGE) loadHires();','/* diagnostic: retain 2k */') if case=='no_hires' else ('renderer.shadowMap.enabled = true;','renderer.shadowMap.enabled = false;')
   assert source.count(old)==1
   route.fulfill(response=response,body=source.replace(old,new))
  if case!='normal':p.route('**/js/globe3d.js',override)
  capture_load(p,'https://kiisophii.github.io/lunar-landing-site-navigator/')
  p.evaluate('LLSN.globe.setTime(7619)')
  def south():p.locator('[data-view="south"]').click();idle(p)
  results[case]=phase(p,case,south)
  print(case,results[case]['long_tasks'],flush=True)
  if case!='no_hires':
   p.evaluate("LLSN.globe.focusSite('SHACKLETON_RIM',{range:2,tilt:55})");idle(p);p.wait_for_timeout(1000);idle(p)
   p.screenshot(path=str(out/f'controlled_{case}.png'))
   results[case]['close_view']=p.evaluate('LLSN.globe.getView()');results[case]['close_stats']=p.evaluate('({...LLSN.globe.stats})')
  (out/'controlled.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
  b.close()
