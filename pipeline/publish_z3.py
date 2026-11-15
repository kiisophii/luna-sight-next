"""Preserve every existing SI row; record author checks without human sign-off claims."""
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
r=json.loads(Path('docs/z3_dates_generation.json').read_text())
c=json.loads(Path('docs/z3_dates_author_check.json').read_text())
assert r['complete'] and len(r['sites'])==33 and c['failures']==0
contract=Path('docs/z3_checks/contract.txt').read_text()
assert 'PASS: 0 errors, 0 warnings' in contract
stamp=datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
row='| '+stamp+' (KST) | Minchul Kim | Task Z3 full-period daily stays and slips | ChatGPT Codex (GPT-6) | Generate all 33 x 1826 daily starts, exact 168/336/708 hourly-cell stays and signed 1/3/7-day changes from actual core.js, explicit range/censor flags, resumable input/content hashes, full aggregation/boundary/legacy/contract checks; no old data changes | pipeline/build_detail_dates.mjs, pipeline/check_detail_dates*.py, pipeline/test_detail_dates.mjs, pipeline/publish_z3.py, pipeline/check_contract.py, pipeline/check_local250.py, pipeline/check_local250_portability.py, pipeline/test_local250_portability.py, web/data/detail/dates/, docs/z3*, docs/data_contract.md, docs/SI_USAGE.md, submission/checkin_update_2026-11-15_ko.md | User requested implementation and delegated evidence-based SI completion; AI author checks and full contract pass, independent member verification by Jiyong is pending. No human numerical rerun is claimed. | No direct human code/data edits reported; AI wrote and checked the requested extension. |'
with Path('docs/SI_USAGE.md').open('a') as f:f.write('\n'+row+'\n')
p=Path('docs/verification_ledger.md')
with p.open('a') as f:
    f.write('\n## Task Z3 full-period landing-date extension — author checks only\n\n')
    f.write('33 sites x 1,826 daily arrivals x 3 stays, 6 signed shifts; exact hourly core.js flags/cumulative counts; 179,190 valid base windows, 1,584 explicit out-of-range base rows. Every valid base window re-aggregated from fresh hourly bits, zero differences; 96,360 old 14-day comparisons consistent within old rounding; complete contract 0 errors/0 warnings. Fractions are exact count divisions; shift deltas are exact rational count changes, not rounded-array subtraction. [Report](z3_dates.md), [generation](z3_dates_generation.json), [checks](z3_dates_author_check.json). **Author-verified only; Jiyong independent 3-site check pending.** Existing products and status counts unchanged.\n')
p=Path('submission/checkin_update_2026-11-15_ko.md');p.parent.mkdir(exist_ok=True)
p.write_text('# 개인 작업 현황 답변 초안\n\nQ1~Q8 원문이 제공되지 않아 문항별 답을 추정하지 않았습니다. 아래는 작업 현황 질문에 사용할 수 있는 2문장 초안이며, 본인 경험·판단에 관한 답변은 직접 확인해야 합니다.\n\n태양·지구 방향 데이터와 착륙지 좌표·출처, 33곳 가시 구간의 생성·검증을 맡았고, A 지평선 전체 검증과 Y 지형 3곳의 독립 검증을 수행했습니다. 이번에는 Z3의 2026~2030년 날짜·체류·지연 분석 데이터를 시간별 원값으로 생성했으며 지용님의 독립 검증을 기다리고 있고, Z2 PR이 올라오면 PSR 거리 검증을 이어갈 예정입니다.\n',encoding='utf8')

port=json.loads(Path('docs/z3_checks/local250_portability.json').read_text())
with Path('docs/z3_dates.md').open('a') as f:
    f.write('\n## Existing coordinate-validator portability fix\n\n')
    f.write('The first full contract run failed on 33 unchanged local250 maps because it required bit-identical latitude/longitude regenerated on another platform. The pinned-main validator was rerun separately; all failures were the same coordinate check, with no grid-index/offset discrepancy. Observed maximum coordinate difference: '+format(port['max_abs_coordinate_difference_deg'],'.12g')+' degrees. Only lat/lon equality now permits 1e-9 degree (at most 0.031 mm on the reference sphere); node indices and offsets remain exact. Four focused tests reject meaningful coordinate changes, changed indices/offsets and nonfinite coordinates. Original maps/generating geometry were byte-compared against main and remain unchanged. Full contract after this fix passes 0 errors/0 warnings. Evidence: z3_checks/local250_portability.json.\n')
