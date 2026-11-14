"""Headed local before/after benchmark. No data or index.html modifications.

Run from repo root: python docs/texture_stall/benchmark.py --variant baseline --runs 3
The baseline serves only globe3d.js from the pinned base commit; all other assets
are identical. Laptop is a CPU/network simulation, NOT a real laptop GPU.
"""
import argparse
import functools
import hashlib
import io
import json
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'pipeline'))
from desktop_performance import PROBE, capture_load, phase, idle, drag
from playwright.sync_api import sync_playwright

BASE = '64e3bee'
UPLOAD_PROBE = r"""(() => {
  window.__uploads = [];
  for (const name of ['texImage2D', 'texSubImage2D']) {
    const original = WebGL2RenderingContext.prototype[name];
    WebGL2RenderingContext.prototype[name] = function(...args) {
      const image = args.find(a => a && typeof a === 'object' && a.width >= 2048)
        || (name==='texSubImage2D' && args.length>=9 && args[4]>=2048
          ? {width:args[4],height:args[5],constructor:{name:args[8]?.constructor?.name}} : null);
      const start = performance.now();
      const result = original.apply(this, args);
      if (image) __uploads.push({name, start, ms:performance.now()-start,
        width:image.width,height:image.height,type:image.constructor.name});
      return result;
    };
  }
})();"""


def serve(source, texture_size=8192):
    texture=None
    if texture_size==4096:
        from PIL import Image
        with Image.open(ROOT/'web/data/globe/moon_color_8k.jpg') as im:
            buf=io.BytesIO()
            im.resize((4096,2048),Image.Resampling.LANCZOS).save(buf,format='JPEG',quality=88,optimize=True)
            texture=buf.getvalue()
    class Handler(SimpleHTTPRequestHandler):
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.js': 'text/javascript', '.mjs': 'text/javascript'}
        def log_message(self, *args): pass
        def copyfile(self, source, outputfile):
            size=0
            while chunk:=source.read(65536):
                outputfile.write(chunk);size+=len(chunk)
            self.server.payloads.append(dict(path=self.path,bytes=size))
        def do_GET(self):
            self.server.request_paths.append(self.path)
            if texture is not None and self.path.split('?')[0]=='/data/globe/moon_color_8k.jpg':
                self.send_response(200)
                self.send_header('Content-Type','image/jpeg')
                self.send_header('Content-Length',str(len(texture)))
                self.end_headers(); self.wfile.write(texture)
                self.server.payloads.append(dict(path=self.path,bytes=len(texture)))
                return
            if self.path.split('?')[0] == '/js/globe3d.js':
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript')
                self.send_header('Content-Length', str(len(source)))
                self.end_headers()
                self.wfile.write(source)
                self.server.payloads.append(dict(path=self.path,bytes=len(source)))
            else: super().do_GET()

    class Server(ThreadingHTTPServer):
        request_queue_size=128
    server = Server(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT/'web')))
    server.request_paths=[]
    server.payloads=[]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.texture_bytes=len(texture) if texture else (ROOT/'web/data/globe/moon_color_8k.jpg').stat().st_size
    server.texture_sha256=hashlib.sha256(texture or (ROOT/'web/data/globe/moon_color_8k.jpg').read_bytes()).hexdigest()
    return server


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--variant', choices=['baseline', 'fixed'], required=True)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--profiles', nargs='+', default=['desktop', 'laptop'])
    ap.add_argument('--out', type=Path, default=ROOT/'data/processed/texture_stall')
    ap.add_argument('--check', action='store_true', help='Assert upload and desktop first-zoom budgets')
    ap.add_argument('--texture-size',type=int,choices=[4096,8192],default=8192)
    ap.add_argument('--cpu-profile',action='store_true',help='Diagnostic only; exclude profiled run from timing table')
    ap.add_argument('--zoom-cycles',action='store_true',help='Measure cold detail zoom, zoom out and detail revisit')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    source = (subprocess.check_output(['git', 'show', f'{BASE}:web/js/globe3d.js'], cwd=ROOT)
              if args.variant == 'baseline' else (ROOT/'web/js/globe3d.js').read_bytes())
    if args.cpu_profile:
        needle=b'function buildMesh(t) {'
        assert source.count(needle)==1
        source=source.replace(needle,b'''function buildMesh(t) {
          const start=performance.now();
          try { return measuredBuildMesh(t); }
          finally { (window.__meshTimes ||= []).push({start,ms:performance.now()-start}); }
        }
        function measuredBuildMesh(t) {''')
    server = serve(source,args.texture_size)
    url = f'http://127.0.0.1:{server.server_port}/'
    results = dict(base=BASE, variant=args.variant, texture_size=args.texture_size,
        texture_bytes=server.texture_bytes,texture_sha256=server.texture_sha256,
        source_sha256=hashlib.sha256(source).hexdigest(), runs=[])
    results['worker_sha256']=hashlib.sha256((ROOT/'web/js/globe_color_worker.js').read_bytes()).hexdigest() if args.variant=='fixed' else None
    label=args.variant+('_4k' if args.texture_size==4096 else '')
    with sync_playwright() as pw:
        for profile in args.profiles:
            for i in range(args.runs):
                w,h = (1920,1080) if profile == 'desktop' else (1366,768)
                browser = pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',
                    headless=False, args=[f'--window-size={w},{h}', '--force-device-scale-factor=1'])
                context = browser.new_context(viewport=dict(width=w,height=h), device_scale_factor=1)
                context.add_init_script(PROBE)
                context.add_init_script(UPLOAD_PROBE)
                page = context.new_page(); page.bring_to_front()
                cdp = context.new_cdp_session(page)
                cdp.send('Network.enable'); cdp.send('Network.clearBrowserCache')
                network=dict(offline=False,latency=70,downloadThroughput=10_000_000/8,
                    uploadThroughput=1_000_000/8,connectionType='wifi')
                if profile == 'laptop':
                    cdp.send('Emulation.setCPUThrottlingRate', dict(rate=4))
                    cdp.send('Network.emulateNetworkConditions',network)
                transfers=[]; errors=[]; worker_commands={}; worker_replies=[]
                cdp.on('Network.loadingFinished', lambda e: transfers.append(e['encodedDataLength']))
                def attached(e):
                    sid=e['sessionId']
                    commands=[('Network.enable',{})]
                    # Dedicated workers inherit page network emulation (separately
                    # verified by check_network.py). Their own CPU throttle is not
                    # supported: laptop is explicitly a main-thread CPU profile.
                    commands += [('Runtime.runIfWaitingForDebugger',{})]
                    for ident,(method,params) in enumerate(commands,1):
                        worker_commands[(sid,ident)]=method
                        cdp.send('Target.sendMessageToTarget',dict(sessionId=sid,message=json.dumps(dict(id=ident,method=method,params=params))))
                def received(e):
                    message=json.loads(e['message'])
                    if message.get('method')=='Network.loadingFinished': transfers.append(message['params']['encodedDataLength'])
                    if 'id' in message: worker_replies.append(dict(method=worker_commands.get((e['sessionId'],message['id'])),response=message))
                cdp.on('Target.attachedToTarget',attached)
                cdp.on('Target.receivedMessageFromTarget',received)
                cdp.send('Target.setAutoAttach',dict(autoAttach=True,waitForDebuggerOnStart=True,flatten=False,
                    filter=[dict(type='worker',exclude=False),dict(exclude=True)]))
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('requestfailed', lambda r: errors.append(f'{r.url}: {r.failure}'))
                page.on('response', lambda r: errors.append(f'HTTP {r.status}: {r.url}') if r.status>=400 else None)
                run=dict(profile=profile, iteration=i+1)
                server.request_paths.clear()
                server.payloads.clear()
                page.on('console', lambda m: print('BROWSER',m.type,m.text[:300],flush=True) if m.type in ['error','warning'] else None)
                print('START',args.variant,profile,i+1,url,flush=True)
                try:
                    run['cold']=capture_load(page,url)
                    print('COLD',run['cold']['atMs'],flush=True)
                    run['cold_transfer_bytes']=sum(transfers)
                    run['cold_server_requests']=list(server.request_paths)
                    run['cold_local_payload_bytes']=sum(x['bytes'] for x in server.payloads)
                    page.evaluate('LLSN.globe.setTime(7619)')
                    def south():
                        page.locator('[data-view="south"]').click()
                        if not idle(page, 120000): raise RuntimeError('South transition did not settle')
                    if args.cpu_profile:
                        cdp.send('Profiler.enable');cdp.send('Profiler.start')
                    run['south']=phase(page,'first_south',south)
                    if args.cpu_profile:
                        cpu=cdp.send('Profiler.stop')['profile']
                        (args.out/f'{label}_{profile}_{i+1}_cpu.json').write_text(json.dumps(cpu),encoding='utf-8')
                        run['mesh_calls']=page.evaluate('window.__meshTimes || []')
                    run['zoom_local_payload_bytes']=sum(x['bytes'] for x in server.payloads)-run['cold_local_payload_bytes']
                    run['uploads']=page.evaluate('__uploads')
                    run['rotation']=phase(page,'south_drag',lambda:drag(page,4))
                    if args.zoom_cycles:
                        run['zoom_cycles']=[]
                        for name,view in [('detail_first',dict(lat=-89.66,lon=129.2,range=2,tilt=55,heading=0)),
                                          ('whole_again',dict(lat=-20,lon=20,range=6500,tilt=0,heading=0)),
                                          ('detail_revisit',dict(lat=-89.66,lon=129.2,range=2,tilt=55,heading=0))]:
                            def move(view=view):
                                page.evaluate('(v)=>LLSN.globe.flyTo(v)',view)
                                if not idle(page,120000):raise RuntimeError(name+' did not settle')
                            item=phase(page,name,move)
                            item['empty_rendered_frames']=page.evaluate('(s)=>__desktopProbe.renders.filter(r=>r.t>=s && r.tiles===0).length',item['start_ms'])
                            run['zoom_cycles'].append(item)
                    run['color']=page.evaluate('''() => {
                      const g=LLSN.globe._internal; const uniforms={uniforms:{},vertexShader:'#include <common>\\n#include <begin_vertex>',fragmentShader:'#include <common>\\n#include <map_fragment>'};
                      const tile=[...g.tiles.values()].find(t=>t.mesh);tile.mesh.material.onBeforeCompile(uniforms);
                      const t=uniforms.uniforms.uColor.value;
                      return {width:t.image.width,height:t.image.height,type:t.image.constructor.name,flipY:t.flipY,mipmaps:t.generateMipmaps,colorSpace:t.colorSpace};
                    }''')
                    if i == 0: page.screenshot(path=str(args.out/f'{label}_{profile}.png'))
                    run['final_stats']=page.evaluate('({...LLSN.globe.stats})')
                except Exception as e:
                    run['error']=str(e)
                    run['diagnostic']=page.evaluate('({state:document.readyState,globe:!!window.LLSN?.globe,stats:window.LLSN?.globe?.stats,text:document.body.innerText.slice(0,1000),resources:performance.getEntriesByType("resource").map(e=>e.name)})')
                    print('DIAGNOSTIC',run['diagnostic'],flush=True)
                    page.screenshot(path=str(args.out/f'{args.variant}_{profile}_failure.png'))
                run['errors']=errors
                run['worker_protocol']=worker_replies
                run['texture_responses']=[x for x in server.payloads if 'moon_color_8k' in x['path']]
                results['browser']=browser.version
                results['gpu']=browser.new_browser_cdp_session().send('SystemInfo.getInfo')['gpu']
                results['runs'].append(run)
                (args.out/f'{label}.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
                print(args.variant,profile,i+1,json.dumps(dict(error=run.get('error'),
                    uploads=run.get('uploads'),cold_bytes=run.get('cold_transfer_bytes'),
                    gap=run.get('south',{}).get('interval_max_ms'),max_task=max([t['duration'] for t in run.get('south',{}).get('long_tasks',[])],default=0),
                    fps=run.get('rotation',{}).get('actual_render_rate'),errors=errors)),flush=True)
                browser.close()
    server.shutdown()
    if args.check:
        for run in results['runs']:
            assert not run.get('error') and not run['errors'], run
            assert run['color']['width'] == args.texture_size and run['color']['height'] == args.texture_size//2
            assert not any('moon_color_8k' in r['name'] for r in run['cold']['resources'])
            assert not any('moon_color_8k' in path for path in run['cold_server_requests'])
            for command in run['worker_protocol']:
                assert 'error' not in command['response'], command
            assert len(run['texture_responses'])==1 and run['texture_responses'][0]['bytes']==results['texture_bytes']
            for cycle in run.get('zoom_cycles',[]):
                assert cycle['after']['tiles']>0 and cycle['empty_rendered_frames']==0,cycle
            uploads = [u['ms'] for u in run['uploads'] if u['width'] == args.texture_size]
            assert uploads and max(uploads) < 100, uploads
            if run['profile'] == 'desktop':
                assert run['south']['interval_max_ms'] < 100, run['south']['interval_max_ms']
                assert max([t['duration'] for t in run['south']['long_tasks']],default=0) < 100
        print('ACCEPTANCE PASS',len(results['runs']),'runs',flush=True)


if __name__ == '__main__': main()
