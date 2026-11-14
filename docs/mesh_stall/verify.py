"""Compare complete generated terrain arrays with PR52, including rebuilds."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/texture_stall'))
from benchmark import serve
from playwright.sync_api import sync_playwright

ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['baseline','fixed'],required=True)
args=ap.parse_args()
source=subprocess.check_output(['git','show','d5e2dd7:web/js/globe3d.js'],cwd=ROOT) if args.variant=='baseline' else (ROOT/'web/js/globe3d.js').read_bytes()
needle=b'_internal: { scene, camera, renderer, tiles }'
assert source.count(needle)==1
source=source.replace(needle,b'_internal: { scene, camera, renderer, tiles, tileInfo, loadTile, buildMesh }')
server=serve(source)
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    c=b.new_context();p=c.new_page()
    p.goto(f'http://127.0.0.1:{server.server_port}/globe_test.html')
    p.wait_for_function('window.globe?.stats.tiles>0')
    p.evaluate('(t)=>globe.waitIdle(t)',60000)
    result=p.evaluate('''async () => {
      const idx=await fetch('data/globe/index.json').then(r=>r.json()), g=globe._internal;
      const chosen=[];
      for(const kind of ['band','north','south']) {
        const arr=idx.tiles[kind],zs=[...new Set(arr.map(x=>x[0]))].sort((a,b)=>a-b);
        for(const z of [...new Set([zs[0],zs[Math.floor(zs.length/2)],zs.at(-1)])]) {
          const tiles=arr.filter(x=>x[0]===z);
          for(const tile of [tiles[0],tiles.at(-1)]) {
            const key=[kind,...tile.slice(0,3)].join('/');if(!chosen.some(x=>x.key===key))chosen.push({kind,tile,key});
          }
        }
      }
      const hash=async a=>{const bytes=new Uint8Array(a.buffer,a.byteOffset,a.byteLength);
        return {type:a.constructor.name,length:a.length,sha256:[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('')};};
      const rows=[];
      for(const {kind,tile,key} of chosen) {
        const t=g.tileInfo(kind,...tile.slice(0,3));
        if(!t.h)await g.loadTile(t);
        for(const exag of [3,1,5,3]) {
          globe.setExaggeration(exag);const start=performance.now();g.buildMesh(t);const buildMs=performance.now()-start;
          const geo=t.mesh.geometry,tex=t.mesh.material.normalMap;
          const buffers={height:await hash(t.h),normalMap:await hash(tex.image.data),index:await hash(geo.index.array),skirt:await hash(t.mesh.children[0].geometry.index.array)};
          for(const name of ['position','normal','uv'])buffers[name]=await hash(geo.attributes[name].array);
          rows.push({key,exag,buildMs,buffers,center:t.mesh.position.toArray(),bounds:{center:geo.boundingSphere.center.toArray(),radius:geo.boundingSphere.radius}});
        }
      }
      return rows;
    }''')
    b.close()
server.shutdown()
out=ROOT/'data/processed/mesh_stall';out.mkdir(parents=True,exist_ok=True)
(out/f'{args.variant}_geometry.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(args.variant,len(result),'complete meshes; max build ms',max(x['buildMs'] for x in result),flush=True)
if args.variant=='fixed':
    expected=json.loads((out/'baseline_geometry.json').read_text())
    for a,b in zip(result,expected,strict=True):
        a.pop('buildMs');b.pop('buildMs');assert a==b,(a['key'],a['exag'])
    print('PASS all terrain buffers, heights, normals, indices, UVs, centres and bounds exactly equal',flush=True)
