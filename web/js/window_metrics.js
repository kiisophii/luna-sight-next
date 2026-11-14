// window_metrics.js — analysis-window selector (7 / 30 / 90 days / custom) and per-site metrics table (phase 3 UI).
// Metrics come only from core.metrics(site, i0, i1) (hourly samples, inclusive).
// Publishes LLSN.window = { i0, i1, hours, days, clipped, mode, metrics: Map(id -> {sun_frac, earth_frac, both_frac, longest_dark_h}) }
// and fires 'llsn:window' after every recompute (horizon_chart.js and filters.js listen).
import * as core from './core.js';
import { t } from './i18n.js';
import { addStrings, whenReady, mountSection, translate, siteName, setFocus, fmtHours, throttle, LLSN } from './ui_shared.js';

addStrings({
  wmTitle: 'Analysis window', wmAria: 'Analysis window and site metrics',
  wm7: '7 days', wm30: '30 days', wm90: '90 days', wmCustom: 'Custom',
  wmStart: 'Start (UTC)', wmLen: 'Length (days)',
  wmFromNow: 'Starts at the current slider time and moves with it.',
  wmFixed: 'Fixed window: does not move with the slider.',
  wmClipped: 'Clipped to the end of the loaded data.',
  wmSite: 'Site', wmSun: 'Sunlight', wmEarth: 'Earth link', wmBoth: 'Both', wmDark: 'Longest dark',
  wmOf: 'of', wmDays: 'days',
  wmHint: 'Sunlight = ≥ 50% of the solar disk above the terrain horizon. Earth link = Earth centre above the terrain horizon. Both = at the same hour. Longest dark = longest continuous run without sunlight inside the window. Hourly samples.',
  wmFocus: 'Click a row to show the site in the horizon panorama.',
}, {
  wmTitle: '분석 기간', wmAria: '분석 기간과 착륙지별 지표',
  wm7: '7일', wm30: '30일', wm90: '90일', wmCustom: '직접 입력',
  wmStart: '시작 (UTC)', wmLen: '길이 (일)',
  wmFromNow: '슬라이더의 현재 시각에서 시작하고 같이 움직인다.',
  wmFixed: '고정 기간: 슬라이더를 움직여도 바뀌지 않는다.',
  wmClipped: '불러온 데이터의 끝에서 잘림.',
  wmSite: '착륙지', wmSun: '햇빛', wmEarth: '지구 통신', wmBoth: '둘 다', wmDark: '가장 긴 어둠',
  wmOf: '/', wmDays: '일',
  wmHint: '햇빛 = 태양 원반 50% 이상이 지형 지평선 위. 지구 통신 = 지구 중심이 지형 지평선 위. 둘 다 = 같은 시각에 둘 다. 가장 긴 어둠 = 기간 안에서 햇빛 없이 이어진 가장 긴 시간. 1시간 간격.',
  wmFocus: '줄을 누르면 지평선 파노라마에 그 착륙지가 나온다.',
});

let sec, tbody, note, customBox, startIn, lenIn;
let mode = '30';                       // '7' | '30' | '90' | 'custom'
let customStart = 0, customDays = 30;

function build() {
  sec = mountSection('llsn-window', 'wmAria');
  sec.innerHTML = `
    <h2 data-i18n="wmTitle"></h2>
    <div class="ctl">
      <span class="seg wm-mode" role="group">
        <button type="button" data-mode="7" data-i18n="wm7"></button><button type="button" data-mode="30" data-i18n="wm30"></button><button type="button" data-mode="90" data-i18n="wm90"></button><button type="button" data-mode="custom" data-i18n="wmCustom"></button>
      </span>
      <span class="wm-custom ctl" style="display:none">
        <label><span data-i18n="wmStart"></span> <input type="date" class="wm-start"></label>
        <label><span data-i18n="wmLen"></span> <input type="number" class="wm-len" min="1" step="1" value="30"></label>
      </span>
      <span class="wm-range" style="font-family:var(--font-num)"></span>
    </div>
    <p class="hint wm-note"></p>
    <div style="overflow-x:auto;margin-top:calc(var(--gap)*.5)">
      <table class="wm-table" style="width:100%;border-collapse:collapse;min-width:560px">
        <thead><tr>
          <th scope="col" data-i18n="wmSite"></th><th scope="col" data-i18n="wmSun"></th><th scope="col" data-i18n="wmEarth"></th>
          <th scope="col" data-i18n="wmBoth"></th><th scope="col" data-i18n="wmDark"></th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <p class="hint" data-i18n="wmHint"></p>
    <p class="hint" data-i18n="wmFocus"></p>`;
  const st = document.createElement('style');
  st.textContent = `
    .wm-table th { text-align: left; color: var(--muted); font-weight: 600; font-size: .85rem; padding: .3em .5em; border-bottom: 1px solid var(--border); }
    .wm-table td { padding: .45em .5em; border-bottom: 1px solid var(--border); vertical-align: middle; }
    .wm-table tbody tr { cursor: pointer; }
    .wm-table tbody tr:hover, .wm-table tbody tr:focus { background: var(--surface-2); outline: none; }
    .wm-table tr.is-focus td:first-child { box-shadow: inset 4px 0 0 var(--text); }
    .wm-table tr.wm-out { opacity: .38; }
    .wm-pct { font-family: var(--font-num); font-weight: 700; font-size: 1.1rem; }
    .wm-days { display: block; white-space: nowrap; font-family: var(--font-num); color: var(--muted); font-size: .85rem; }
    .wm-dark .wm-pct { white-space: nowrap; }
    .wm-bar { height: 6px; border-radius: 3px; background: var(--off); margin-top: 3px; max-width: 160px; }
    .wm-bar > i { display: block; height: 100%; border-radius: 3px; }
    .wm-sun .wm-pct { color: var(--sun); } .wm-sun .wm-bar > i { background: var(--sun); }
    .wm-earth .wm-pct { color: var(--earth); } .wm-earth .wm-bar > i { background: var(--earth); }
    .wm-both .wm-pct { color: var(--relay); } .wm-both .wm-bar > i { background: var(--relay); }
    .wm-dark .wm-pct { color: var(--text); }`;
  sec.appendChild(st);
  tbody = sec.querySelector('tbody'); note = sec.querySelector('.wm-note');
  customBox = sec.querySelector('.wm-custom'); startIn = sec.querySelector('.wm-start'); lenIn = sec.querySelector('.wm-len');

  const [a, b] = core.hourRange();
  startIn.min = isoDay(a); startIn.max = isoDay(b);
  sec.querySelector('.wm-mode').addEventListener('click', e => {
    const btn = e.target.closest('button'); if (!btn) return;
    mode = btn.dataset.mode;
    if (mode === 'custom') {                       // start the custom window where the slider is now
      customStart = Math.floor(LLSN().now() / 24) * 24;
      startIn.value = isoDay(customStart); lenIn.value = customDays;
    }
    recompute();
  });
  startIn.addEventListener('change', () => { if (startIn.value) { customStart = core.dateToHour(new Date(startIn.value + 'T00:00:00Z')); recompute(); } });
  lenIn.addEventListener('change', () => { customDays = Math.max(1, Number(lenIn.value) || 1); recompute(); });
  tbody.addEventListener('click', e => { const tr = e.target.closest('tr'); if (tr) setFocus(tr.dataset.id); });
  tbody.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { const tr = e.target.closest('tr'); if (tr) { e.preventDefault(); setFocus(tr.dataset.id); } } });

  const onTime = throttle(() => { if (mode !== 'custom') recompute(); }, 300);
  window.addEventListener('llsn:time', onTime);
  window.addEventListener('llsn:lang', () => { translate(sec); render(); });
  window.addEventListener('llsn:focus', markRows);
  window.addEventListener('llsn:filter', markRows);
  translate(sec);
  recompute();
}

const isoDay = i => core.hourToDate(i).toISOString().slice(0, 10);
const fmtUTC = i => core.hourToDate(i).toISOString().replace('T', ' ').slice(0, 16);

function recompute() {
  const [a, b] = core.hourRange();
  let i0, days;
  if (mode === 'custom') { i0 = customStart; days = customDays; }
  else { i0 = Math.floor(LLSN().now()); days = Number(mode); }
  i0 = Math.min(Math.max(a, i0), b);
  const want = i0 + days * 24 - 1;
  const i1 = Math.min(b, want);
  const metrics = new Map();
  for (const s of core.state.sites) metrics.set(s.id, core.metrics(s, i0, i1));
  const hours = i1 - i0 + 1;
  window.LLSN.window = { i0, i1, hours, days: hours / 24, clipped: want > b, mode, metrics };
  render();
  window.dispatchEvent(new CustomEvent('llsn:window', { detail: window.LLSN.window }));
}

function cell(cls, frac, days) {
  const pct = Math.round(frac * 100);
  return `<td class="${cls}"><span class="wm-pct">${pct}%</span> <span class="wm-days">${(frac * days).toFixed(1)} ${t('wmOf')} ${fmtDaysShort(days)} ${t('wmDays')}</span>
    <div class="wm-bar"><i style="width:${pct}%"></i></div></td>`;
}
const fmtDaysShort = d => (Math.abs(d - Math.round(d)) < 0.05 ? String(Math.round(d)) : d.toFixed(1));

function render() {
  const w = LLSN().window; if (!w) return;
  sec.querySelectorAll('.wm-mode button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
  customBox.style.display = mode === 'custom' ? '' : 'none';
  sec.querySelector('.wm-range').textContent = `${fmtUTC(w.i0)} → ${fmtUTC(w.i1)} UTC · ${fmtDaysShort(w.days)} ${t('wmDays')}`;
  note.textContent = t(mode === 'custom' ? 'wmFixed' : 'wmFromNow') + (w.clipped ? ' ' + t('wmClipped') : '');
  note.style.color = w.clipped ? 'var(--warn)' : '';
  tbody.innerHTML = core.state.sites.map(s => {
    const m = w.metrics.get(s.id);
    if (!m) return '';
    return `<tr data-id="${s.id}" tabindex="0">
      <th scope="row" style="text-align:left;font-weight:600">${siteName(s)}</th>
      ${cell('wm-sun', m.sun_frac, w.days)}${cell('wm-earth', m.earth_frac, w.days)}${cell('wm-both', m.both_frac, w.days)}
      <td class="wm-dark"><span class="wm-pct">${fmtHours(m.longest_dark_h)}</span></td></tr>`;
  }).join('');
  markRows();
}

function markRows() {
  const pass = LLSN().filterPass, f = LLSN().focus;
  tbody.querySelectorAll('tr').forEach(tr => {
    tr.classList.toggle('is-focus', tr.dataset.id === f);
    tr.classList.toggle('wm-out', !!pass && !pass.has(tr.dataset.id));
  });
}

whenReady(build);
