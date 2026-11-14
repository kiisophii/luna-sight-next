"""Headed Chrome/GPU audit of the deployed app; no app code is modified.

Requires playwright and an installed Chrome. Results are timing observations on this
machine/network, not universal performance guarantees. rAF intervals are a proxy,
not physical display presentation or a video-encoder benchmark.
"""
import argparse
import hashlib
import json
import math
import statistics
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""(() => {
  const p = window.__desktopProbe = {frames:[], renders:[], longTasks:[], firstTerrainMs:null};
  new PerformanceObserver(list => {
    for (const e of list.getEntries()) p.longTasks.push({start:e.startTime,duration:e.duration});
  }).observe({type:'longtask',buffered:true});
  let last=null, count=0;
  function frame(t) {
    if (last!==null) p.frames.push({t,dt:t-last}); last=t;
    const s=window.LLSN?.globe?.stats;
    if(s && s.renders!==count) {
      p.renders.push({t,count:s.renders,tiles:s.tiles,pending:s.pending,quality:s.quality});
      count=s.renders;
      if(p.firstTerrainMs===null && s.tiles>0) p.firstTerrainMs=t;
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();"""


def quantile(values, p):
    if not values: return None
    a=sorted(values); i=(len(a)-1)*p; lo=int(i)
    return a[lo]+(a[min(lo+1,len(a)-1)]-a[lo])*(i-lo)


def phase(page, name, action):
    start=page.evaluate('performance.now()')
    before=page.evaluate('({...LLSN.globe.stats})')
    action()
    end=page.evaluate('performance.now()')
    raw=page.evaluate('({frames:__desktopProbe.frames,longTasks:__desktopProbe.longTasks})')
    frames=[f['dt'] for f in raw['frames'] if start<=f['t']<=end]
    tasks=[f for f in raw['longTasks'] if start<=f['start']<=end]
    after=page.evaluate('({...LLSN.globe.stats})')
    return dict(name=name,start_ms=start,end_ms=end,duration_s=(end-start)/1000,
        raf_fps=(1000/statistics.mean(frames) if frames else None),
        interval_median_ms=quantile(frames,.5),interval_p95_ms=quantile(frames,.95),
        interval_p99_ms=quantile(frames,.99),interval_max_ms=max(frames,default=0),
        gaps_over_50ms=sum(v>50 for v in frames),gaps_over_100ms=sum(v>100 for v in frames),
        frames=len(frames),long_tasks=tasks,
        actual_render_rate=(after['renders']-before['renders'])/((end-start)/1000),
        before=before,after=after,view=page.evaluate('LLSN.globe.getView()'))


def drag(page, seconds=8):
    box=page.locator('#globe-stage canvas').bounding_box()
    x=box['x']+box['width']*.5; y=box['y']+box['height']*.45
    page.mouse.move(x,y);page.mouse.down()
    start=time.monotonic()
    try:
        while time.monotonic()-start<seconds:
            t=time.monotonic()-start
            page.mouse.move(x+math.sin(t*.7)*box['width']*.23,y+math.sin(t*.45)*box['height']*.1)
            page.wait_for_timeout(16)
    finally:page.mouse.up()


def idle(page, timeout=60000):
    return page.evaluate('(t)=>LLSN.globe.waitIdle(t)',timeout)


def capture_load(page, url, reload=False):
    if reload:page.reload(wait_until='domcontentloaded',timeout=60000)
    else:page.goto(url,wait_until='domcontentloaded',timeout=60000)
    page.wait_for_function('window.LLSN?.globe?.stats?.tiles>0',timeout=60000)
    settled=idle(page)
    result=page.evaluate('''({atMs:performance.now(),firstTerrainMs:__desktopProbe.firstTerrainMs,
        paint:performance.getEntriesByType('paint').map(e=>({name:e.name,time:e.startTime})),
        navigation:performance.getEntriesByType('navigation')[0].toJSON(),
        stats:{...LLSN.globe.stats},screen:{width:screen.width,height:screen.height,dpr:devicePixelRatio,
        innerWidth,innerHeight,visibility:document.visibilityState},
        resources:performance.getEntriesByType('resource').map(e=>({name:e.name,start:e.startTime,
        duration:e.duration,transferSize:e.transferSize,decodedBodySize:e.decodedBodySize})),
        longTasks:__desktopProbe.longTasks})''')
    result['settled']=settled
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--url',default='https://kiisophii.github.io/lunar-landing-site-navigator/')
    ap.add_argument('--runs',type=int,default=3)
    ap.add_argument('--width',type=int,default=1920);ap.add_argument('--height',type=int,default=1080)
    ap.add_argument('--out',type=Path,default=ROOT/'data/processed/desktop_perf')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    result=dict(url=a.url,viewport=[a.width,a.height],runs=[],source_checks={})
    for relative in ['index.html','js/globe3d.js','js/globe_app.js','js/core.js','version.json']:
        with urllib.request.urlopen(a.url+relative,timeout=30) as response:data=response.read()
        local=ROOT/'web'/relative
        result['source_checks'][relative]=dict(remote_sha256=hashlib.sha256(data).hexdigest(),
            local_sha256=hashlib.sha256(local.read_bytes()).hexdigest(),match=data==local.read_bytes(),
            normalized_text_equal=data.decode('utf-8-sig').splitlines()==local.read_text(encoding='utf-8-sig').splitlines())
    with sync_playwright() as pw:
        for i in range(a.runs):
            browser=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',
                headless=False,args=[f'--window-size={a.width},{a.height}','--force-device-scale-factor=1'])
            context=browser.new_context(viewport={'width':a.width,'height':a.height},device_scale_factor=1)
            context.add_init_script(PROBE)
            page=context.new_page();page.bring_to_front()
            cdp=context.new_cdp_session(page);cdp.send('Network.clearBrowserCache')
            errors=[];failures=[];http_errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('requestfailed',lambda request:failures.append(dict(url=request.url,failure=request.failure)))
            page.on('response',lambda response:http_errors.append(dict(url=response.url,status=response.status)) if response.status>=400 else None)
            gpu=browser.new_browser_cdp_session().send('SystemInfo.getInfo')['gpu']
            result['browser']=browser.version
            result['gpu']=dict(devices=gpu['devices'],renderer=gpu['auxAttributes'].get('glRenderer'),features=gpu['featureStatus'])
            run=dict(index=i+1)
            try:
                run['cold']=capture_load(page,a.url)
                print('COLD',i+1,round(run['cold']['atMs']/1000,3),'settled',run['cold']['settled'],flush=True)
                if i==0:page.screenshot(path=str(a.out/'whole_moon.png'))
                run['warm']=capture_load(page,a.url,reload=True)
                run['rotation']=phase(page,'whole_moon_mouse_drag',lambda:drag(page))
                def south():
                    page.locator('[data-view="south"]').click();idle(page)
                run['south']=phase(page,'south_pole_button_to_idle',south)
                if i==0:page.screenshot(path=str(a.out/'south_pole.png'))
                def zoom():
                    page.evaluate("LLSN.globe.focusSite('SHACKLETON_RIM',{range:2,tilt:55})")
                    idle(page)
                run['zoom']=phase(page,'shackleton_2km_to_idle',zoom)
                if i==0:page.screenshot(path=str(a.out/'shackleton_2km.png'))
                run['close_rotation']=phase(page,'close_terrain_mouse_drag',lambda:drag(page))
                run['final_resources']=page.evaluate("performance.getEntriesByType('resource').map(e=>({name:e.name,duration:e.duration,transferSize:e.transferSize}))")
                run['final_stats']=page.evaluate('({...LLSN.globe.stats})')
            except Exception as error:
                run['test_error']=str(error)
                page.screenshot(path=str(a.out/f'failure_{i+1}.png'))
            run.update(page_errors=errors,request_failures=failures,http_errors=http_errors)
            result['runs'].append(run)
            (a.out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print('RUN',i+1,'phases',{k:round(run[k]['duration_s'],2) for k in ['rotation','south','zoom','close_rotation'] if k in run},'errors',len(errors),len(failures),len(http_errors),flush=True)
            browser.close()


if __name__=='__main__':main()
