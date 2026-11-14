// window_metrics.js — period results table for every site (phase 3 UI).
// The analysis window itself (start date, length, clipping) is owned by app.js, which computes
// LLSN.window = { i0, i1, hours, days, clipped, metrics: Map(id -> {sun_frac, earth_frac, both_frac, longest_dark_h}) }
// with core.metrics(site, i0, i1) (hourly samples, inclusive) and fires 'llsn:window'. This module only renders it,
// so the numbers depend on the period alone — never on the play speed or the selected time inside the period.
import * as core from './core.js';
import { t } from './i18n.js';
import { addStrings, whenReady, mountSection, translate, siteName, setFocus, fmtHours, LLSN } from './ui_shared.js';

addStrings({
  wmTitle: 'Period results — all sites', wmAria: 'Period results for every site',
  wmSite: 'Site', wmSun: 'Sunlight', wmEarth: 'Earth link', wmBoth: 'Both', wmDark: 'Longest dark',
  wmOf: 'of', wmDays: 'days',
  wmHint: 'Sunlight = ≥ 50% of the solar disk above the horizon. Earth link = Earth centre above the horizon. Both = at the same hour. Longest dark = longest continuous run without sunlight inside the period. Hourly samples; days = fraction × period length.',
  wmFocus: 'Click a row to show that site in the horizon panorama.',
}, {
  wmTitle: '기간 결과 — 전체 착륙지', wmAria: '착륙지별 기간 결과',
  wmSite: '착륙지', wmSun: '햇빛', wmEarth: '지구 통신', wmBoth: '둘 다', wmDark: '가장 긴 어둠',
  wmOf: '/', wmDays: '일',
  wmHint: '햇빛 = 태양 원반 50% 이상이 지평선 위. 지구 통신 = 지구 중심이 지평선 위. 둘 다 = 같은 시각에 둘 다. 가장 긴 어둠 = 기간 안에서 햇빛 없이 이어진 가장 긴 시간. 1시간 간격, 일수 = 비율 × 기간 길이.',
  wmFocus: '줄을 누르면 지평선 파노라마에 그 착륙지가 나온다.',
});

let root, tbody, rangeEl;

function build() {
  root = document.getElementById('wm-body') || mountSection('llsn-window', 'wmAria');
  mountSection('llsn-window');                                   // makes sure the shared panel styles exist
  root.innerHTML = `
    <h3 class="wm-h"><span data-i18n="wmTitle"></span> <span class="wm-range"></span></h3>
    <div style="overflow-x:auto">
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
    .wm-h { margin: calc(var(--gap) * .8) 0 .4em; font-size: 1.05rem; }
    .wm-range { font-family: var(--font-num); color: var(--muted); font-weight: 400; font-size: .9rem; }
    .wm-table th { text-align: left; color: var(--muted); font-weight: 600; font-size: .85rem; padding: .3em .5em; border-bottom: 1px solid var(--border); }
    .wm-table td, .wm-table tbody th { padding: .45em .5em; border-bottom: 1px solid var(--border); vertical-align: middle; }
    .wm-table tbody tr { cursor: pointer; }
    .wm-table tbody tr:hover, .wm-table tbody tr:focus { background: var(--surface-2); outline: none; }
    .wm-table tr.is-focus th { box-shadow: inset 4px 0 0 var(--text); }
    .wm-table tr.wm-out { opacity: .38; }
    .wm-pct { font-family: var(--font-num); font-weight: 700; font-size: 1.1rem; }
    .wm-days { display: block; white-space: nowrap; font-family: var(--font-num); color: var(--muted); font-size: .85rem; }
    .wm-dark .wm-pct { white-space: nowrap; }
    .wm-bar { height: 6px; border-radius: 3px; background: var(--off); margin-top: 3px; max-width: 160px; }
    .wm-bar > i { display: block; height: 100%; border-radius: 3px; }
    .wm-sun .wm-pct { color: var(--sun); } .wm-sun .wm-bar > i { background: var(--sun); }
    .wm-earth .wm-pct { color: var(--earth); } .wm-earth .wm-bar > i { background: var(--earth); }
    .wm-both .wm-pct { color: var(--relay); } .wm-both .wm-bar > i { background: var(--relay); }
    .wm-dark .wm-pct { color: var(--text); }
    .wm-tag { display: inline-block; margin-left: .4em; font-size: .7rem; font-weight: 700; padding: .05em .5em; border-radius: 999px;
      border: 1px solid var(--warn); color: var(--warn); vertical-align: middle; }`;
  root.appendChild(st);
  tbody = root.querySelector('tbody'); rangeEl = root.querySelector('.wm-range');

  tbody.addEventListener('click', e => { const tr = e.target.closest('tr'); if (tr) setFocus(tr.dataset.id); });
  tbody.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { const tr = e.target.closest('tr'); if (tr) { e.preventDefault(); setFocus(tr.dataset.id); } } });
  window.addEventListener('llsn:window', render);
  window.addEventListener('llsn:lang', () => { translate(root); render(); });
  window.addEventListener('llsn:focus', markRows);
  window.addEventListener('llsn:filter', markRows);
  translate(root);
  render();
}

const fmtUTC = i => core.hourToDate(i).toISOString().replace('T', ' ').slice(0, 16);
const fmtDaysShort = d => (Math.abs(d - Math.round(d)) < 0.05 ? String(Math.round(d)) : d.toFixed(1));

function cell(cls, frac, days) {
  const pct = Math.round(frac * 100);
  return `<td class="${cls}"><span class="wm-pct">${pct}%</span> <span class="wm-days">${(frac * days).toFixed(1)} ${t('wmOf')} ${fmtDaysShort(days)} ${t('wmDays')}</span>
    <div class="wm-bar"><i style="width:${pct}%"></i></div></td>`;
}

function tags(s) {
  if (core.horizonMock(s)) return `<span class="wm-tag">${t('mockTerrain')}</span>`;
  if (core.terrainPending(s)) return `<span class="wm-tag" title="${t('terrainPendingTip')}">${t('terrainPending')}</span>`;
  return '';
}

function render() {
  const w = LLSN().window; if (!w || !tbody) return;
  rangeEl.textContent = `${fmtUTC(w.i0)} → ${fmtUTC(w.i1)} UTC · ${fmtDaysShort(w.days)} ${t('wmDays')}` + (w.clipped ? ` · ${t('clipped')}` : '');
  rangeEl.style.color = w.clipped ? 'var(--warn)' : '';
  tbody.innerHTML = core.state.sites.map(s => {
    const m = w.metrics.get(s.id);
    if (!m) return '';
    return `<tr data-id="${s.id}" tabindex="0">
      <th scope="row" style="text-align:left;font-weight:600">${siteName(s)}${tags(s)}</th>
      ${cell('wm-sun', m.sun_frac, w.days)}${cell('wm-earth', m.earth_frac, w.days)}${cell('wm-both', m.both_frac, w.days)}
      <td class="wm-dark"><span class="wm-pct">${fmtHours(m.longest_dark_h)}</span></td></tr>`;
  }).join('');
  markRows();
}

function markRows() {
  if (!tbody) return;
  const pass = LLSN().filterPass, f = LLSN().focus;
  tbody.querySelectorAll('tr').forEach(tr => {
    tr.classList.toggle('is-focus', tr.dataset.id === f);
    tr.classList.toggle('wm-out', !!pass && !pass.has(tr.dataset.id));
  });
}

whenReady(build);
