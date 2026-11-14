"""Browser correctness checks (separate from performance timings).

python docs/texture_stall/verify.py
"""
import argparse
import json
from benchmark import ROOT, serve
from playwright.sync_api import sync_playwright

COLOR = r"""() => {
  const g=LLSN.globe._internal;
  const sh={uniforms:{},vertexShader:'#include <common>\n#include <begin_vertex>',fragmentShader:'#include <common>\n#include <map_fragment>'};
  [...g.tiles.values()].find(t=>t.mesh).mesh.material.onBeforeCompile(sh);
  return sh.uniforms.uColor.value;
}"""

COMPARE = r"""async () => {
  const THREE=await import('https://cdnjs.cloudflare.com/ajax/libs/three.js/0.170.0/three.module.min.js');
  const renderer=LLSN.globe._internal.renderer;
  const actual=window.testColor();
  const expected=await new THREE.TextureLoader().loadAsync('data/globe/moon_color_8k.jpg');
  expected.colorSpace=THREE.SRGBColorSpace; expected.wrapS=THREE.RepeatWrapping;
  expected.anisotropy=renderer.capabilities.getMaxAnisotropy(); expected.generateMipmaps=true;
  const camera=new THREE.Camera(), scene=new THREE.Scene();
  const geometry=new THREE.PlaneGeometry(2,2);
  const material=new THREE.ShaderMaterial({uniforms:{map:{value:actual},area:{value:new THREE.Vector4(0,0,1,1)}},
    vertexShader:'varying vec2 vUv; uniform vec4 area; void main(){vUv=area.xy+uv*area.zw;gl_Position=vec4(position,1.);}',
    fragmentShader:'varying vec2 vUv; uniform sampler2D map; void main(){gl_FragColor=texture2D(map,vUv);}'});
  scene.add(new THREE.Mesh(geometry,material));
  const target=new THREE.WebGLRenderTarget(512,256);
  const saved=renderer.getRenderTarget(), a=new Uint8Array(512*256*4), b=new Uint8Array(a.length);
  const results=[];
  try {
    for(const area of [[0,0,1,1],[0,0,.0625,.0625],[.47,.92,.0625,.0625],[.96,.45,.0625,.0625]]) {
      material.uniforms.area.value.set(...area);
      for(const [texture,buffer] of [[actual,a],[expected,b]]) {
        material.uniforms.map.value=texture;renderer.setRenderTarget(target);renderer.render(scene,camera);
        renderer.readRenderTargetPixels(target,0,0,512,256,buffer);
      }
      let max=0,total=0,count=0;
      for(let i=0;i<a.length;i++){const d=Math.abs(a[i]-b[i]);max=Math.max(max,d);total+=d;if(d)count++;}
      results.push({area,max_channel_difference:max,mean_channel_difference:total/a.length,different_channels:count});
    }
  } finally {renderer.setRenderTarget(saved);target.dispose();geometry.dispose();material.dispose();expected.dispose();}
  return results;
}"""


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',nargs='+',default=['normal','http_error','decode_error','dispose_during_decode','legacy_fallback','texture_limit'])
    args=ap.parse_args()
    server=serve((ROOT/'web/js/globe3d.js').read_bytes())
    url=f'http://127.0.0.1:{server.server_port}/'
    results={}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        for case in args.cases:
            context=browser.new_context(viewport=dict(width=1280,height=900))
            page=context.new_page(); errors=[]
            page.on('pageerror',lambda e: errors.append(str(e)))
            if case in ['http_error','decode_error']:
                # Context routing includes the worker's fetch.
                context.route('**/moon_color_8k.jpg',lambda r: r.fulfill(status=503 if case=='http_error' else 200,body='invalid JPEG'))
            if case=='dispose_during_decode':
                # Use an unresolved worker job, not a fabricated successful decode.
                page.add_init_script('''window.workerTerminations=0;const original=Worker.prototype.terminate;
                    Worker.prototype.terminate=function(){workerTerminations++;return original.call(this);};''')
                context.route('**/globe_color_worker.js',lambda r: r.fulfill(content_type='text/javascript',body='self.onmessage=()=>{};'))
            if case=='legacy_fallback': page.add_init_script('window.Worker=undefined;')
            page.goto(url,wait_until='domcontentloaded')
            page.wait_for_function('window.LLSN?.globe?.stats?.tiles>0')
            assert page.evaluate('(t)=>LLSN.globe.waitIdle(t)',60000)
            page.evaluate('window.testColor='+COLOR)
            assert page.evaluate('testColor().image.width')==2048
            if case=='texture_limit': page.evaluate('LLSN.globe._internal.renderer.capabilities.maxTextureSize=4096')
            page.evaluate("LLSN.globe.flyTo({lat:-89,lon:0,range:420,tilt:35,heading:0},0)")
            if case=='dispose_during_decode':
                page.wait_for_function('LLSN.globe.getView().range<3000')
                page.evaluate('LLSN.globe.dispose()')
                page.wait_for_timeout(100)
                assert page.evaluate('workerTerminations')==1
                results[case]={'worker_terminated':True}
            else:
                assert page.evaluate('(t)=>LLSN.globe.waitIdle(t)',60000)
                width=page.evaluate('testColor().image.width')
                assert width==(2048 if 'error' in case else 4096 if case=='texture_limit' else 8192), (case,width)
                results[case]={'width':width}
                if case=='normal':
                    results[case]['pixels']=page.evaluate(COMPARE)
                    assert max(x['max_channel_difference'] for x in results[case]['pixels'])==0, results[case]['pixels']
                    page.evaluate('LLSN.globe._internal.renderer.forceContextLoss()')
                    page.wait_for_timeout(200)
                    page.evaluate('LLSN.globe._internal.renderer.forceContextRestore()')
                    page.wait_for_timeout(500)
                    results[case]['restored_pixels']=page.evaluate(COMPARE)
                    assert max(x['max_channel_difference'] for x in results[case]['restored_pixels'])==0
                page.evaluate('LLSN.globe.dispose()')
            assert not errors, errors
            print('PASS',case,results[case],flush=True)
            context.close()
        browser.close()
    server.shutdown()
    out=ROOT/'data/processed/texture_stall/verification.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': main()
