from playwright.sync_api import sync_playwright
from pathlib import Path
import json
O=Path(__file__).resolve().parents[1]/'docs/design_sync/tray_reference';O.mkdir(exist_ok=True)
checks=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True)
 for w,lang in [(1440,'en'),(1440,'ko'),(1280,'en'),(1280,'ko'),(390,'en'),(390,'ko')]:
  p=b.new_page(viewport={'width':w,'height':900},reduced_motion='reduce');errors=[]
  p.on('pageerror',lambda e:errors.append(str(e)))
  p.goto('http://127.0.0.1:8021/?sites=SHACKLETON_RIM,ARTEMIS_HAWORTH,APOLLO17&pn=1,2,3&focus=SHACKLETON_RIM&d=2026-11-15&p=29.5&open=time',wait_until='networkidle')
  p.locator('.tc-row').first.wait_for(timeout=60000);p.locator('#ls-intro').wait_for(state='hidden',timeout=20000)
  p.locator('.lang-seg [data-lang="'+lang+'"]').click();p.evaluate('document.fonts.ready')
  for cat in ['sun','earth','relay','terrain']:
   p.locator('.tc-tabs [data-c="'+cat+'"]').click();p.wait_for_timeout(300)
   if cat=='terrain':p.locator('.tc-horizon').wait_for()
   else:p.locator('.tc-subs button').first.click()
   p.locator('.tc-row').first.wait_for();p.locator('#ls-tray').scroll_into_view_if_needed()
   p.locator('#ls-tray').screenshot(path=str(O/f'tray_{w}_{lang}_{cat}.png'))
   checks.append({'w':w,'lang':lang,'cat':cat,'values':p.locator('.tc-val').all_text_contents(),'errors':list(errors),'layout':p.evaluate('''()=>{let q=s=>{let r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}};return {tray:q('#ls-tray'),tabs:q('.tc-tabs'),heading:q('.tc-h'),rows:q('.tc-rows'),footer:q('.tray-more'),overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,desc:document.querySelector('.tc-desc').textContent}}''')})
  if w==1440 and lang=='en':
   p.locator('.tc-tabs [data-c=earth]').click();p.locator('.tc-subs [data-s=both]').click();p.wait_for_timeout(100)
   checks.append({'both':p.locator('.tc-val').all_text_contents(),'expected':p.evaluate("['SHACKLETON_RIM','ARTEMIS_HAWORTH','APOLLO17'].map(id=>window.LLSN.window.metrics.get(id).both_frac)")})
   p.locator('.tc-tabs [data-c=relay]').click();p.locator('.tc-subs [data-s=added]').click();p.wait_for_timeout(150)
   checks.append({'added':p.locator('.tc-val').all_text_contents()})
  if w==1440 and lang=='en':
   actual=p.evaluate("""async()=>{const {relayFor}=await import('/js/diff_data.js');const {relayPeriod,hourBits}=await import('/js/values.js');const {relayMasks,cumulative}=await import('/js/tray_series.js');const W=LLSN.window;return await Promise.all(['SHACKLETON_RIM','ARTEMIS_HAWORTH','APOLLO17'].map(async id=>{const rel=await relayFor(id);const net=rel.networks[rel.params.heights_m.indexOf(15)];const m=relayMasks(net.timeline.segments,W.i0,W.i1);const r=await relayPeriod(id,W.i0,W.i1);return {id,curve:cumulative(m.total,1).end,metric:r.pct,added:cumulative(m.added,1).end,expectedAdded:r.via/r.total}}));}""")
   assert all(abs(x['curve']-x['metric'])<1e-12 and abs(x['added']-x['expectedAdded'])<1e-12 for x in actual),actual
   checks.append({'relay_parity':actual})
  assert not errors,errors
  assert p.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'), 'page overflow'
  p.close();print(w,lang,'done',flush=True)
 b.close()
(O/'tray_checks.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False),encoding='utf8')
