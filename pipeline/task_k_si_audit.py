"""Recount Jiyong's SI rows without editing historical or human-review cells."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=[('main snapshot','274e676665d71e56a9fb7ddc7ead13e65d15aecf',None),
         ('PR 66','dc140bbd24eff9c1869adda4097f812cdd5ae208',66),
         ('PR 67','e50d4362f769ff811c8c85509abb027c4f22842a',67),
         ('PR 68','cf37fb7db6f758bc0b6a5ecd9bab842685dd58bf',68),
         ('this PR','WORKTREE',None)]


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8')


def main():
    rows={};snapshots=[]
    for label,ref,pr in SOURCES:
        commit=git('rev-parse',ref).strip() if ref!='WORKTREE' else None
        text=git('show',f'{commit}:docs/SI_USAGE.md') if commit else (ROOT/'docs/SI_USAGE.md').read_text(encoding='utf-8')
        snapshot=dict(label=label,ref=ref,commit=commit,si_utf8_lf_sha256=hashlib.sha256(text.replace('\r\n','\n').encode()).hexdigest(),jiyong_rows=0,new_unique_rows=0)
        for n,line in enumerate(text.splitlines(),1):
            if not line.startswith('| 2026-'):continue
            cells=[s.strip() for s in line.strip('|').split('|')]
            if cells[1] not in ('Jiyong','Jiyong Sung','성지용'):continue
            snapshot['jiyong_rows']+=1
            # Keep complete rows as keys. Unescaped pipes in prose do not split records.
            key=line.strip()
            loc=dict(source=label,line=n,commit=commit,pr=pr)
            if key not in rows:
                rows[key]=dict(time=cells[0],member=cells[1],role=cells[2],tool=cells[3],
                    human_check=cells[-2],human_changed=cells[-1],locations=[],raw=line)
                snapshot['new_unique_rows']+=1
            rows[key]['locations'].append(loc)
        snapshots.append(snapshot)
    values=list(rows.values())
    pending=[r for r in values if r['human_check'] in ('','TO CHECK') or r['human_changed'] in ('','TO CHECK')]
    report=dict(scope='Jiyong only; pinned main + three pending branches + current worktree',
                snapshots=snapshots,unique_rows=len(values),pending_human_cells_rows=len(pending),rows=values)
    out=ROOT/'docs/task_k_si_audit.json'
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['# Task K — Jiyong SI record audit','',
           'This is a dated administrative recount, not a new scientific verification or a human sign-off. Historical log rows and the submission disclosure are unchanged. Exact inherited rows are counted once across branches; distinct rows for stages of one task remain distinct log entries. Counts are **entries, not unique tasks, prompts, calls or hours**.','',
           '| Snapshot | Commit | Jiyong rows | Additional unique entries |','|---|---|---:|---:|']
    lines += [f"| {s['label']} | `{s['commit'] or 'current SI file (hash in JSON)'}` | {s['jiyong_rows']} | {s['new_unique_rows']} |" for s in snapshots]
    lines += ['',f"**{len(values)} unique Jiyong entries**, of which **{len(pending)}** still have an empty/`TO CHECK` human-review or human-change cell. The remaining nonempty cells are reproduced as written; AI does not infer or add human approval. Older `Confirmed by Jiyong — ... relayed by Sua` cells are historical attributions, not reconfirmed by this audit.",'',
              'The current four R/U/V/K rows are included. C, D and X/P/Q live in pending PR branches and must be merged before a main-only final submission recount. The existing `submission/si_disclosure_en.md` is pinned to an older commit; its historical count must not be presented as this latest total.','',
              '## Entries still requiring human cells','',
              '| First listed source / line | Time | Role | Human check | Human changed? |','|---|---|---|---|---|']
    for r in pending:
        loc=r['locations'][0]
        url=f"https://github.com/kiisophii/lunar-landing-site-navigator/blob/{loc['commit']}/docs/SI_USAGE.md#L{loc['line']}" if loc['commit'] else f"SI_USAGE.md#L{loc['line']}"
        lines.append(f"| [{loc['source']} L{loc['line']}]({url}) | {r['time']} | {r['role']} | {r['human_check']} | {r['human_changed']} |")
    lines += ['','## Reproduce','', '`python pipeline/task_k_si_audit.py`','',
              'Each input snapshot has a normalized-LF SHA256 and every counted row retains its raw text and locations in [JSON](task_k_si_audit.json). Member names are matched exactly, so mentions of Jiyong in another member\'s request are excluded. No other member\'s entries or human-only H/L work are certified here.']
    (ROOT/'docs/task_k_si_audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))


if __name__=='__main__':main()
