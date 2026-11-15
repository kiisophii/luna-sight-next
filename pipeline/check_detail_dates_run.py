"""Author-side full aggregation checks on fresh core.js hourly bits, not independent member verification."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text())
sites=load(ROOT/'web/data/sites.json');records=[];legacy_max=0;windows=0
for site in sites:
    sid=site['id'];obj=load(ROOT/'web/data/detail/dates'/f'{sid}.json')
    raw=np.fromfile(ROOT/'data/processed/detail_dates'/f'{sid}.bits',dtype=np.uint8)
    assert raw.size==43824 and np.all(raw<4)
    s=raw&1;e=(raw>>1)&1;b=s&e
    prefixes=[np.r_[0,np.cumsum(a,dtype=np.int64)] for a in [s,e,b]]
    nchecks=0
    for stay in obj['stays']:
        h=stay['stay_h']
        for day,row in enumerate(stay['rows']):
            start=day*24;end=start+h
            if end>len(s):
                assert row==['out_of_range']+[None]*9;continue
            counts=[int(p[end]-p[start]) for p in prefixes]
            dark=1-s[start:end].astype(int)
            transitions=np.diff(np.r_[0,dark,0])
            starts=np.flatnonzero(transitions==1);ends=np.flatnonzero(transitions==-1)
            longest=int(max(ends-starts,default=0))
            left=not bool(s[start]) and (start==0 or not bool(s[start-1]))
            right=not bool(s[end-1]) and (end==len(s) or not bool(s[end]))
            expected=['ok',*counts,*[v/h for v in counts],longest,left,right]
            assert row==expected,(sid,h,day,row,expected)
            nchecks+=1
    # Read legacy rounded arrays only here, never in the producer.
    old=load(ROOT/'web/data/date_slip'/f'{sid}.json')
    baseline=next(t for t in obj['stays'] if t['stay_h']==336)['rows']
    assert old['n_landings']==730
    for metric,index in [('sun_frac',4),('earth_frac',5),('both_frac',6),('longest_dark_h',7)]:
        for d,v in enumerate(old['series'][metric]):
            diff=abs(baseline[d][index]-v)
            if index==7:assert diff==0
            else:assert diff<=.000050000001;legacy_max=max(legacy_max,diff)
    records.append(dict(id=sid,valid_base_windows_checked=nchecks,out_of_range_base_rows=5478-nchecks,
      legacy_rows_checked=730*4))
    windows+=nchecks
summary=dict(author_checks_only=True,sites=33,valid_base_windows_checked=windows,failures=0,
  legacy_comparisons=33*730*4,max_legacy_fraction_rounding_difference=legacy_max,records=records)
(ROOT/'docs/z3_dates_author_check.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='records'}))
lines=['# Z3 full-period landing-date extension','',
  'Author-produced data; independent team verification by Jiyong is pending. No existing date_slip, ephemeris, horizon, metrics or UI values were changed.','',
  'All 33 catalogue sites, all 1,826 UTC-midnight landing days in 2026–2030, stays of 7/14/29.5 days (168/336/708 hours), signed shifts -7/-3/-1/+1/+3/+7 days. Actual core.js hourly Sun/Earth flags feed integer cumulative sums; no rounded legacy array feeds generation.','',
  'A stay includes exactly its requested [start,end) hourly cells. The final observed cell is [2030-12-31 23:00,2031-01-01 00:00). An end-exclusive boundary at 2031-01-01 00:00 is allowed; no later cell is used. Invalid base/shifted stays are explicitly marked, never shortened.','',
  '| Stay | Hours | Valid landing days per site | Out-of-range daily starts | Last valid landing |',
  '|---|---:|---:|---:|---|',
  '| 7 days | 168 | 1820 | 6 | 2030-12-25 |',
  '| 14 days | 336 | 1813 | 13 | 2030-12-18 |',
  '| 29.5 days | 708 | 1797 | 29 | 2030-12-02 |','',
  'Stored base fractions are unrounded IEEE-754 double divisions of integer visible-hour counts. Slip fraction changes use exact signed hour numerators and the fixed stay-hour denominator: delta_frac = delta_sun_h / stay_h (similarly Earth/both); multiply by 100 for percentage points. Shifted fractions themselves are at rows[target_day_index]. This avoids repeating the same metrics and losing precision through subtraction of rounded floats.','',
  'Rows and delta rows use column definitions embedded in every file. All 1,826 days remain present, including invalid tails. A valid target with an invalid base is base_out_of_range; an invalid target with a valid base is target_out_of_range; both invalid is both_out_of_range. All four delta numerators are null when a comparison is invalid. Negative shifts are earlier arrivals, not delays.','',
  'Longest darkness is the longest run within each stay. Dark runs continuing across a stay edge are marked censored; a global dataset edge without an adjacent observation is censored, not an asserted sunrise.','',
  'Author validation: '+str(windows)+' valid base windows independently re-aggregated from saved fresh core.js bits with NumPy cumulative counts and run-transition scans, zero discrepancies. All signed deltas/range flags are checked by the contract. '+str(33*730*4)+' legacy comparisons reproduce the existing 2026–2027 14-day data within its documented 4-decimal rounding (hours exact). This is author-side verification on shared bits, not another member\'s independent geometry.','',
  'Reproduce from the repository root:','~~~sh','node --test pipeline/test_detail_dates.mjs','node pipeline/build_detail_dates.mjs','python pipeline/check_detail_dates_run.py','python pipeline/check_contract.py','~~~','',
  'Generation checkpoints per site, signatures and full-content hashes reject stale/tampered reuse. A complete discovery index is written only after all 33 sites. Raw hourly-bit checkpoints are ignored under data/processed/detail_dates.','',
  'Independent handoff: a different member should derive hourly flags from ephem.bin and original horizon files using their own code, then compare 3 sites including a polar site, a near-side and a far-side site, all stays and six shifts. Include 2028-02-29, final valid dates, out-of-range dates, and negative shifts at 2026-01-01. Acceptance: fraction <=0.1 percentage point and durations <=1 hour; all range statuses should agree exactly. Do not import this producer or use its cached bits as independent truth.','',
  'Limits: fixed catalogue terrain, hourly classification, midnight arrival, no fractional-cell interpolation, no operational power/communication guarantee. Source files are unchanged existing NASA NAIF ephemerides and LOLA/SLDEM horizon inputs; see data/DATASETS.md and each product input SHA-256.']
(ROOT/'docs/z3_dates.md').write_text('\n'.join(lines)+'\n')
