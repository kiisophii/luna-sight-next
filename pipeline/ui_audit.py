"""UI <-> data audit: read the numbers the live site shows for every catalogue site and compare them with
reference values from web/data/*.json + actual core.js (pipeline/ui_audit_ref.mjs).
    python audit.py ref_10086.json ref_4614.json   -> findings.json, shots/*.png
"""
import asyncio, json, math, re, sys
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://kiisophii.github.io/lunar-landing-site-navigator/"
OUT = Path(__file__).resolve().parents[1] / "docs" / "ui_audit"
SHOTS = OUT / "shots"; SHOTS.mkdir(parents=True, exist_ok=True)
PANELS = ['cards', 'llsn-window', 'llsn-horizon', 'llsn-local', 'llsn-story', 'llsn-relay', 'llsn-korea', 'llsn-dates', 'llsn-slip', 'llsn-seasons']
NUM = r'([−+\-]?\d+(?:\.\d+)?)'


def jround(x, nd=0):
    f = 10 ** nd
    return math.floor(x * f + 0.5) / f


def num(s):
    return float(s.replace('−', '-').replace('+', ''))


def fmt_hours(h):
    if h is None or (isinstance(h, float) and not math.isfinite(h)):
        return '—'
    if h < 48:
        return f"{jround(h, 1):.1f} h"
    d = math.floor(h / 24); r = jround(h - d * 24)
    return f"{d} d {int(r)} h"


def pct(x):
    return f"{int(jround(x * 100))}%"


class Audit:
    def __init__(self):
        self.findings, self.checks = [], 0

    def eq(self, site, T, panel, what, shown, expected, elem):
        self.checks += 1
        if str(shown) != str(expected):
            self.findings.append(dict(site=site, T=T, panel=panel, what=what, shown=str(shown), expected=str(expected), element=elem))
            return False
        return True

    def near(self, site, T, panel, what, shown, expected, tol, elem):
        self.checks += 1
        if shown is None or expected is None or abs(shown - expected) > tol + 1e-9:
            self.findings.append(dict(site=site, T=T, panel=panel, what=what, shown=shown, expected=expected, tol=tol, element=elem))
            return False
        return True


def card_block(text, name):
    i = text.find(name + "\n")
    if i < 0:
        return None
    j = text.find("Horizon shown below", i)
    return text[i:j if j > 0 else None]


async def run(refs):
    A = Audit()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1400, 'height': 1000})
        for ref in refs:
            T, P = ref['T'], ref['P']
            for sid, r in ref['sites'].items():
                await pg.goto(f"{URL}?sites={sid}&focus={sid}&t={T}&p={P}", wait_until='networkidle')
                await pg.wait_for_timeout(2500)
                tx = await pg.evaluate("(ids) => Object.fromEntries(ids.map(id => [id, (document.getElementById(id)||{}).innerText||'']))", PANELS)
                fails_before = len(A.findings)
                inst, per = r['inst'], r['period']
                # ---------------- cards
                c = card_block(tx['cards'], r['name']) or ''
                m = re.search(r'SUN ELEVATION\n' + NUM + r'°\naz (\d+)°', c)
                if m:
                    A.near(sid, T, 'cards', 'Sun elevation (°)', num(m[1]), jround(inst['sun_el'], 1), 0.05, '#cards .card[data-id] .v-sunel')
                    A.near(sid, T, 'cards', 'Sun azimuth (°)', num(m[2]), jround(inst['sun_az']), 0.5, '.v-sunaz')
                else:
                    A.eq(sid, T, 'cards', 'Sun elevation block present', 'missing', 'present', '.v-sunel')
                m = re.search(r'UNTIL (SUNSET|SUNRISE)\n(.+)\nUNTIL (EARTHSET|EARTHRISE)\n(.+)\n', c)
                if m:
                    sk = 'until_sunset' if m[1] == 'SUNSET' else 'until_sunrise'
                    ek = 'until_earthset' if m[3] == 'EARTHSET' else 'until_earthrise'
                    A.eq(sid, T, 'cards', 'Sun label (set vs rise)', m[1], 'SUNSET' if inst['sunlit'] else 'SUNRISE', '.v-sunlbl')
                    A.eq(sid, T, 'cards', 'Earth label (set vs rise)', m[3], 'EARTHSET' if inst['earth_visible'] else 'EARTHRISE', '.v-earthlbl')
                    for shown, key, el in ((m[2], sk, '.v-sunt'), (m[4], ek, '.v-eartht')):
                        if not shown.startswith('no change'):
                            A.eq(sid, T, 'cards', f'{key} (time)', shown, fmt_hours(inst[key]), el)
                        else:
                            A.eq(sid, T, 'cards', f'{key} (no change)', 'no change', 'no change' if inst[key] is None else fmt_hours(inst[key]), el)
                A.eq(sid, T, 'cards', 'Sun chip', '☀ Sunlit' in c, inst['sunlit'], '.v-sunchip')
                A.eq(sid, T, 'cards', 'Earth chip', '● Earth visible' in c, inst['earth_visible'], '.v-earthchip')
                m = re.search(r'Earth elevation ' + NUM + r'° · az (\d+)°', c)
                if m:
                    A.near(sid, T, 'cards', 'Earth elevation (°)', num(m[1]), jround(inst['earth_el'], 1), 0.05, '.v-earthel')
                for lab, key in (('Sunlight', 'sun_frac'), ('Earth link', 'earth_frac'), ('Both', 'both_frac')):
                    m = re.search(lab + r'\n(\d+)%\n([\d.]+) of (\d+) days', c)
                    if m:
                        A.eq(sid, T, 'cards', f'period {lab} %', m[1] + '%', pct(per[key]), '.blk.period')
                        A.near(sid, T, 'cards', f'period {lab} days', float(m[2]), jround(per[key] * P, 1), 0.05, '.blk.period')
                m = re.search(r'Longest dark\n(.+)\n([\d.]+) days', c)
                if m:
                    A.eq(sid, T, 'cards', 'period longest dark', m[1], fmt_hours(per['longest_dark_h']), '.blk.period')
                # ---------------- window table row
                m = re.search(re.escape(r['name']) + r'\t(\d+)%\n([\d.]+) of \d+ days\n\t(\d+)%\n([\d.]+) of \d+ days\n\t(\d+)%\n([\d.]+) of \d+ days\n\t(.+)', tx['llsn-window'])
                if m:
                    A.eq(sid, T, 'window', 'table Sunlight %', m[1] + '%', pct(per['sun_frac']), '#llsn-window table tr')
                    A.eq(sid, T, 'window', 'table Earth %', m[3] + '%', pct(per['earth_frac']), '#llsn-window table tr')
                    A.eq(sid, T, 'window', 'table Both %', m[5] + '%', pct(per['both_frac']), '#llsn-window table tr')
                    A.eq(sid, T, 'window', 'table longest dark', m[7].strip(), fmt_hours(per['longest_dark_h']), '#llsn-window table tr')
                else:
                    A.eq(sid, T, 'window', 'table row present', 'missing', 'present', '#llsn-window table')
                # ---------------- horizon readout
                m = re.search(r'\nSun\n' + NUM + r'°\naz ' + NUM + r'° · terrain mask ' + NUM + r'°\n(.+)\nEarth\n' + NUM + r'°\naz ' + NUM + r'° · terrain mask ' + NUM + r'°\n(.+)\n', tx['llsn-horizon'])
                if m:
                    A.near(sid, T, 'horizon', 'Sun el', num(m[1]), jround(inst['sun_el'], 1), 0.05, '#llsn-horizon readout')
                    A.near(sid, T, 'horizon', 'Sun mask at az', num(m[3]), jround(inst['sun_mask'], 1), 0.05, '#llsn-horizon readout')
                    A.near(sid, T, 'horizon', 'Earth el', num(m[5]), jround(inst['earth_el'], 1), 0.05, '#llsn-horizon readout')
                    A.near(sid, T, 'horizon', 'Earth mask at az', num(m[7]), jround(inst['earth_mask'], 1), 0.05, '#llsn-horizon readout')
                    A.eq(sid, T, 'horizon', 'Earth visible label', 'Visible' in m[8] or '✓' in m[8], inst['earth_visible'], '#llsn-horizon readout')
                # ---------------- story
                s = tx['llsn-story']
                m = re.search(r'1 · Direct link to Earth\n\n(\d+)%', s)
                if m:
                    A.eq(sid, T, 'story', 'direct link %', m[1] + '%', pct(per['earth_frac']), '#llsn-story step 1')
                m = re.search(r'Yeoju \(KDSA, 35 m\) for (\d+)% of the period \((.+?)\).*?With the 3 NASA DSN 70 m sites: (\d+)%', s, re.S)
                k = r['korea']
                if m:
                    A.eq(sid, T, 'story', 'Korea %', m[1] + '%', pct(k['site_earth_kdsa'] / k['hours']), '#llsn-story step 3')
                    A.eq(sid, T, 'story', 'Korea hours', m[2], fmt_hours(k['site_earth_kdsa']), '#llsn-story step 3')
                    A.eq(sid, T, 'story', 'DSN %', m[3] + '%', pct(k['site_earth_dsn'] / k['hours']), '#llsn-story step 3')
                # ---------------- korea panel
                kt = tx['llsn-korea']
                for lab, key in (('Korea Deep Space Antenna (Yeoju), 35 m', 'KDSA'), ('NASA DSN Goldstone (DSS-14, 70 m)', 'DSN_GOLDSTONE'),
                                 ('NASA DSN Madrid (DSS-63, 70 m)', 'DSN_MADRID'), ('NASA DSN Canberra (DSS-43, 70 m)', 'DSN_CANBERRA'),
                                 ('Any NASA DSN 70 m', 'any_dsn'), ('Only Yeoju (no DSN 70 m)', 'only_kdsa')):
                    m = re.search(re.escape(lab) + r'\n(.+) · (\d+)%', kt)
                    if m:
                        A.eq(sid, T, 'korea', f'{key} hours', m[1], fmt_hours(k[key]), '#llsn-korea .bars')
                        A.eq(sid, T, 'korea', f'{key} %', m[2] + '%', pct(k[key] / k['hours']), '#llsn-korea .bars')
                for lab, key in (('Site sees Earth', 'site_earth'), ('Site sees Earth + Yeoju sees the Moon', 'site_earth_kdsa'),
                                 ('Site sees Earth + any NASA DSN 70 m', 'site_earth_dsn')):
                    m = re.search('\n' + re.escape(lab) + r'\n(.+) · (\d+)%', kt)
                    if m:
                        A.eq(sid, T, 'korea', f'{key} hours', m[1], fmt_hours(k[key]), '#llsn-korea site link')
                        A.eq(sid, T, 'korea', f'{key} %', m[2] + '%', pct(k[key] / k['hours']), '#llsn-korea site link')
                # ---------------- relay panel (default 15 m)
                rt = tx['llsn-relay']
                if r['relay']:
                    hm = re.search(r'Added via tower \((\d+) towers?, (\d+) m\)', rt)
                    H = hm[2] if hm else '15'
                    rr = r['relay'].get(H)
                    m = re.search(r'Direct to Earth\n(\d+)%\n(.+)\nAdded via tower \(\d+ towers?, \d+ m\)\n\+(\d+)%\n(.+)\nLink with tower\(s\)\n(\d+)%\n(.+)\nNo link\n(\d+)%\nLongest no-link stretch: (.+)\n', rt)
                    if m and rr:
                        Tt = rr['total']
                        A.eq(sid, T, 'relay', 'direct %', m[1] + '%', pct(rr['direct'] / Tt), '#llsn-relay .kpi.direct')
                        A.eq(sid, T, 'relay', 'direct hours', m[2], fmt_hours(rr['direct']), '#llsn-relay .kpi.direct')
                        A.eq(sid, T, 'relay', 'via %', m[3] + '%', pct(rr['via'] / Tt), '#llsn-relay .kpi.via')
                        A.eq(sid, T, 'relay', 'total %', m[5] + '%', pct((rr['direct'] + rr['via']) / Tt), '#llsn-relay .kpi.total')
                        A.eq(sid, T, 'relay', 'no link %', m[7] + '%', pct(rr['none'] / Tt), '#llsn-relay .kpi.none')
                        A.eq(sid, T, 'relay', 'longest no-link', m[8], fmt_hours(rr['longest_none']), '#llsn-relay .kpi.none')
                        # displayed parts should add up to 100 %
                        tot = int(m[5]) + int(m[7])
                        if tot != 100:
                            A.findings.append(dict(site=sid, T=T, panel='relay', what='Link with tower(s) % + No link % (rounded separately)',
                                                   shown=f"{m[5]}% + {m[7]}% = {tot}%", expected='100%', element='#llsn-relay .rl-kpis', kind='rounding'))
                        A.checks += 1
                    m2 = re.search(r'0: ([\d.]+)% · 1: ([\d.]+)% · 2: ([\d.]+)% · 3: ([\d.]+)%', rt)
                    if m2 and rr:
                        for n_, v_ in enumerate(m2.groups()):
                            if n_ < len(rr['link_frac_by_n']):
                                A.near(sid, T, 'relay', f'whole-window link with {n_} towers', float(v_), jround(rr['link_frac_by_n'][n_] * 100, 1), 0.05, '#llsn-relay .num')
                # ---------------- landing-date scan readout (landing = period start, 14 days)
                m = re.search(r'Landing (\d{4}-\d\d-\d\d) · 14 days: Sunlight (\d+)% · Earth link (\d+)% · Both (\d+)% · Longest dark (.+)', tx['llsn-dates'])
                if m:
                    # the readout describes the date it names (the period start when it is inside the scan, else the best day)
                    from datetime import date as _d
                    k = (_d.fromisoformat(m[1]) - _d(2026, 1, 1)).days
                    ser = r.get('slip_series')
                    if m[1] == ref.get('period_start_iso'):
                        f = r['first14']
                    elif ser and 0 <= k < len(ser['sun_frac']):
                        f = {key: ser[key][k] for key in ('sun_frac', 'earth_frac', 'both_frac', 'longest_dark_h')}
                    else:
                        f = None
                if m and f:
                    A.eq(sid, T, 'dates', 'scan Earth %', m[3] + '%', pct(f['earth_frac']), '#llsn-dates .ls-read')
                    A.eq(sid, T, 'dates', 'scan Both %', m[4] + '%', pct(f['both_frac']), '#llsn-dates .ls-read')
                    A.eq(sid, T, 'dates', 'scan longest dark', m[5].strip(), fmt_hours(f['longest_dark_h']), '#llsn-dates .ls-read')
                # ---------------- slip table
                if r['slip']:
                    st_ = tx['llsn-slip']
                    for lab, key in (('Sunlight', 'sun_frac'), ('Earth link', 'earth_frac'), ('Both', 'both_frac')):
                        m = re.search('\n' + lab + r'\t' + NUM + r' pp\t' + NUM + r' pp\n.*?\n\t' + NUM + r' pp\t' + NUM + r' pp\n.*?\n\t(\d+)%', st_)
                        if m:
                            s7, s14 = r['slip']['+7d'][key], r['slip']['+14d'][key]
                            A.near(sid, T, 'slip', f'{lab} +7 typical', num(m[1]), s7['median_abs_change'], 0.05, '#llsn-slip table')
                            A.near(sid, T, 'slip', f'{lab} +7 worst', num(m[2]), s7['worst_change'], 0.05, '#llsn-slip table')
                            A.near(sid, T, 'slip', f'{lab} +14 typical', num(m[3]), s14['median_abs_change'], 0.05, '#llsn-slip table')
                            A.near(sid, T, 'slip', f'{lab} +14 worst', num(m[4]), s14['worst_change'], 0.05, '#llsn-slip table')
                            A.near(sid, T, 'slip', f'{lab} +14 share worse', float(m[5]), jround(s14['share_of_days_worse'] * 100), 0.5, '#llsn-slip table')
                # ---------------- seasons summary
                if r['seasons']:
                    se = r['seasons']
                    m = re.search(r'Sunlight ([\d.]+)%–([\d.]+)% \(best (\S+), worst (\S+)\)\. Months with the Sun south vs north: ([−+])([\d.]+) pp', tx['llsn-seasons'])
                    if m:
                        A.near(sid, T, 'seasons', 'min sunlight %', float(m[1]), float(f"{se['min'] * 100:.1f}"), 0.05, '#llsn-seasons summary')
                        A.near(sid, T, 'seasons', 'max sunlight %', float(m[2]), float(f"{se['max'] * 100:.1f}"), 0.05, '#llsn-seasons summary')
                        A.eq(sid, T, 'seasons', 'best month', m[3], se['best'], '#llsn-seasons summary')
                        A.eq(sid, T, 'seasons', 'worst month', m[4], se['worst'], '#llsn-seasons summary')
                        A.near(sid, T, 'seasons', 'south-north pp', (1 if m[5] == '+' else -1) * float(m[6]), jround(se['dS_pp'], 1), 0.05, '#llsn-seasons summary')
                    m = re.search(r'Longest darkness per month: (.+?)–(.+?)\.', tx['llsn-seasons'])
                    if m:
                        # this summary prints whole hours ("176 h"), not the d/h format used elsewhere: compare the number
                        A.near(sid, T, 'seasons', 'dark min (h)', num(m[1].replace(' h', '')), se['dark_min'], 0.5, '#llsn-seasons summary')
                        A.near(sid, T, 'seasons', 'dark max (h)', num(m[2].replace(' h', '')), se['dark_max'], 0.5, '#llsn-seasons summary')
                # ---------------- local map (only if the panel shows this site)
                lt = tx['llsn-local']
                A.checks += 1
                if r['local'] and ('No local map for the focused site' in lt):
                    A.findings.append(dict(site=sid, T=T, panel='local', what='local map for the focused site',
                                           shown='"No local map for the focused site — showing Malapert …"',
                                           expected=f'web/data/local/{sid}.json exists (card 20)', element='#llsn-local note', kind='integration'))
                elif r['local']:
                    m = re.search(r'Sunlight ([\d.]+)% · Earth link ([\d.]+)% · Both ([\d.]+)% · Longest dark (.+)\n', lt)
                    lc = r['local']['centre']
                    if m:
                        A.near(sid, T, 'local', 'centre Sunlight %', float(m[1]), jround(lc['sun_frac'] * 100, 1), 0.05, '#llsn-local readout')
                        A.near(sid, T, 'local', 'centre Earth %', float(m[2]), jround(lc['earth_frac'] * 100, 1), 0.05, '#llsn-local readout')
                        A.near(sid, T, 'local', 'centre Both %', float(m[3]), jround(lc['both_frac'] * 100, 1), 0.05, '#llsn-local readout')
                        A.eq(sid, T, 'local', 'centre longest dark', m[4].strip(), fmt_hours(lc['longest_dark_h']), '#llsn-local readout')
                    for km in (1, 3, 5, 10):
                        m = re.search(rf'Within {km} km of the catalogue point: ([\d.]+)% – ([\d.]+)%', lt)
                        if m:
                            lo, hi = r['local'][f'r{km}']
                            A.near(sid, T, 'local', f'within {km} km min Both %', float(m[1]), jround(lo * 100, 1), 0.05, '#llsn-local ranges')
                            A.near(sid, T, 'local', f'within {km} km max Both %', float(m[2]), jround(hi * 100, 1), 0.05, '#llsn-local ranges')
                # screenshots of panels with new findings
                new = A.findings[fails_before:]
                for pnl in sorted({f['panel'] for f in new}):
                    pid = {'cards': 'cards', 'window': 'llsn-window', 'horizon': 'llsn-horizon', 'story': 'llsn-story', 'korea': 'llsn-korea',
                           'relay': 'llsn-relay', 'dates': 'llsn-dates', 'slip': 'llsn-slip', 'seasons': 'llsn-seasons', 'local': 'llsn-local'}[pnl]
                    shot = SHOTS / f"{sid}_{T}_{pnl}.png"
                    try:
                        await pg.locator('#' + pid).screenshot(path=str(shot))
                        for f in new:
                            if f['panel'] == pnl:
                                f['screenshot'] = shot.name
                    except Exception as e:  # noqa: BLE001
                        pass
                print(sid, T, 'findings', len(new), flush=True)
        await b.close()
    (OUT / 'findings.json').write_text(json.dumps(dict(checks=A.checks, findings=A.findings), indent=1, ensure_ascii=False), encoding='utf-8')
    print('checks', A.checks, 'findings', len(A.findings))


refs = [json.loads(Path(f).read_text(encoding='utf-8')) for f in sys.argv[1:]]
import datetime as _dt
REPO = Path(__file__).resolve().parents[1] / "web" / "data"
for ref in refs:
    ref['period_start_iso'] = (_dt.date(2026, 1, 1) + _dt.timedelta(days=ref['i0'] // 24)).isoformat()
    for sid, r in ref['sites'].items():
        try:
            r['slip_series'] = json.loads((REPO / 'date_slip' / f'{sid}.json').read_text(encoding='utf-8'))['series']
        except FileNotFoundError:
            r['slip_series'] = None
asyncio.run(run(refs))
