"""Check that page network emulation also limits a dedicated worker fetch."""
import json
from benchmark import ROOT,serve
from playwright.sync_api import sync_playwright

server=serve((ROOT/'web/js/globe3d.js').read_bytes())
url=f'http://127.0.0.1:{server.server_port}/'
result={}
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    c=b.new_context();p=c.new_page()
    p.goto(url+'version.json')
    d=c.new_cdp_session(p);d.send('Network.enable');d.send('Network.setCacheDisabled',dict(cacheDisabled=True))
    for label,rate in [('native',-1),('10_mbps',10_000_000/8)]:
        d.send('Network.emulateNetworkConditions',dict(offline=False,latency=70 if rate>0 else 0,downloadThroughput=rate,uploadThroughput=rate))
        result[label]=p.evaluate('''async () => {
          const source=`self.onmessage=async({data:url})=>{const t=performance.now();const r=await fetch(url,{cache:'no-store'});const b=await r.arrayBuffer();postMessage({ms:performance.now()-t,bytes:b.byteLength});};`;
          const u=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
          const w=new Worker(u);const result=await new Promise((resolve,reject)=>{w.onmessage=e=>resolve(e.data);w.onerror=reject;w.postMessage(location.origin+'/data/globe/moon_color_8k.jpg');});
          w.terminate();URL.revokeObjectURL(u);return result;
        }''')
        print(label,result[label],flush=True)
    b.close()
server.shutdown()
assert result['10_mbps']['ms']>=5000, result
out=ROOT/'data/processed/texture_stall/network_check.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
