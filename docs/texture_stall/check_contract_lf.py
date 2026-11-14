"""Run unchanged contract checks with Git's LF producer bytes, no checkout edits.

Windows checkout CRLF changes build_windows.mjs/core.js SHA256; committed window
files record LF. Export the two checkers and producer/core from HEAD, leave other
imports/data at their original paths, and retain the full byte check.
"""
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[2]
out=root/'data/processed/texture_stall/lf_contract'
out.mkdir(parents=True,exist_ok=True)
for name in ['check_contract.py','check_windows.py','build_windows.mjs']:
    (out/name).write_bytes(subprocess.check_output(['git','show',f'HEAD:pipeline/{name}'],cwd=root))
env=dict(os.environ,PYTHONPATH=str(root/'pipeline'))
(out/'web/js').mkdir(parents=True,exist_ok=True)
(out/'web/js/core.js').write_bytes(subprocess.check_output(['git','show','HEAD:web/js/core.js'],cwd=root))
data=out/'web/data'
if not data.exists():
    if os.name=='nt':
        link_env=dict(env,LLSN_LF_LINK=str(data),LLSN_LF_TARGET=str(root/'web/data'))
        subprocess.run(['powershell','-NoProfile','-Command','New-Item -ItemType Junction -Path $env:LLSN_LF_LINK -Target $env:LLSN_LF_TARGET | Out-Null'],env=link_env,check=True)
    else: data.symlink_to(root/'web/data',target_is_directory=True)
result=subprocess.run([sys.executable,'-X','utf8',str(out/'check_contract.py'),'--data',str(data)],env=env,capture_output=True,text=True,encoding='utf-8')
(out.parent/'contract_lf.log').write_text(result.stdout+result.stderr,encoding='utf-8')
print(result.stdout,end='');print(result.stderr,end='')
raise SystemExit(result.returncode)
