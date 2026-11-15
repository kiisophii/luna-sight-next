// filters.js — mission-condition filters for the site list, drawn as the copy's 2 x 3 cell grid (measured spec 11/15).
// Uses the per-site metrics of the current analysis window (LLSN.window from app.js / core.metrics) and, for the
// ground-station cell, the hourly station bits in data/korea/stations.json (values.stationPeriod -> diff_data).
// Publishes LLSN.filterPass (Set of ids) and fires 'llsn:filter'.
import * as core from './core.js';
import { t } from './i18n.js';
import { addStrings, whenReady, mountSection, translate, fmtHours, LLSN } from './ui_shared.js';
import { stationPeriod } from './values.js';

addStrings({
  flTitle: 'Filter sites', flAria: 'Mission conditions: filter the candidate list',
  fcSun: 'Sunlight', fcEarth: 'Direct-to-Earth', fcBoth: 'Sun + Earth', fcDark: 'Longest shadow', fcGs: 'Station in view', fcMatch: 'Matching',
  fiSun: 'Share of hours in the period with at least half of the solar disc above the local terrain horizon. Minimum.',
  fiEarth: 'Share of hours with the Earth centre above the local terrain horizon (direct-to-Earth geometry). Minimum.',
  fiBoth: 'Share of hours when the Sun disc is ≥ 50 % above the terrain horizon AND the Earth centre is above it. Geometry only. Minimum.',
  fiDark: 'Longest continuous stretch without sunlight in the period. Maximum.',
  fiGs: 'Share of hours with the Earth centre above the site horizon AND the Moon ≥ 10° above at least one of 4 ground stations (Yeoju KDSA, DSN Goldstone, Madrid, Canberra). Geometry only — no radio link budget. Minimum.',
  fiMatch: 'Sites that pass every condition, out of all catalogue sites.',
  flAny: 'any', flReset: 'Reset all', flMatch: 'sites match', flOf: 'of', flMin: 'at least', flMax: 'at most',
  flNone: 'No site matches. Loosen a condition.', flFoot: 'Changing a condition recalculates the candidate list right away.',
}, {
  flTitle: '착륙지 거르기', flAria: '미션 조건: 후보 목록 거르기',
  fcSun: '일조', fcEarth: '직접 교신', fcBoth: '해·지구 동시', fcDark: '최장 그늘', fcGs: '지상국 가시', fcMatch: '맞는 곳',
  fiSun: '기간 중 태양 원반의 절반 이상이 지형 지평선 위에 있는 시간 비율. 최솟값.',
  fiEarth: '지구 중심이 지형 지평선 위에 있는 시간 비율(직접 교신 기하). 최솟값.',
  fiBoth: '태양 원반 50 % 이상과 지구 중심이 함께 지형 지평선 위에 있는 시간 비율. 기하만. 최솟값.',
  fiDark: '기간 중 햇빛이 없는 가장 긴 연속 시간. 최댓값.',
  fiGs: '착륙지에서 지구 중심이 지평선 위에 있고, 지상국 4곳(여주 KDSA, DSN 골드스톤·마드리드·캔버라) 중 한 곳 이상에서 달이 10° 이상 떠 있는 시간 비율. 기하만 — 전파 성능은 아님. 최솟값.',
  fiMatch: '모든 조건을 통과한 착륙지 수 / 전체 카탈로그.',
  flAny: '상관없음', flReset: '모두 초기화', flMatch: '곳이 맞음', flOf: '/', flMin: '이상', flMax: '이하',
  flNone: '맞는 착륙지가 없습니다. 조건을 풀어 보세요.', flFoot: '조건을 바꾸면 후보 목록을 바로 다시 계산합니다.',
});

const IC = {
  sun: '<circle cx="8" cy="8" r="2.8" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M3.4 12.6l1.3-1.3M11.3 4.7l1.3-1.3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
  earth: '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12" fill="none" stroke="currentColor" stroke-width="1.1"/>',
  both: '<circle cx="5.5" cy="6" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="10.5" cy="10" r="3.5" fill="none" stroke="currentColor" stroke-width="1.2"/>',
  dark: '<path d="M3 13L13 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2 1.6"/>',
  gs: '<path d="M3.5 7a4.5 4.5 0 0 1 9 0z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><path d="M8 7v6.5M5.5 13.5h5M8 7l2.5-3.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
  match: '<path d="M3 4h10M5 8h6M7 12h2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
};
// key -> metric field, comparison, axis colour (icon / slider fill)
const DEFS = [
  { key: 'sun', label: 'fcSun', info: 'fiSun', field: 'sun_frac', ge: true, col: 'var(--sun)' },
  { key: 'earth', label: 'fcEarth', info: 'fiEarth', field: 'earth_frac', ge: true, col: 'var(--earth)' },
  { key: 'both', label: 'fcBoth', info: 'fiBoth', field: 'both_frac', ge: true, col: '#EDEDED' },
  { key: 'dark', label: 'fcDark', info: 'fiDark', field: 'longest_dark_h', ge: false, col: '#EDEDED' },
  { key: 'gs', label: 'fcGs', info: 'fiGs', field: 'gs_frac', ge: true, col: 'var(--kdsa)' },
];
let sec, countEl, inputs = {};
let maxDark = 24;                       // slider max = window length in hours (set on llsn:window)
let gs = new Map(), gsKey = '';         // id -> share of hours linked to >= 1 of 4 stations, for the current window

const info = k => `<button type="button" class="fc-i" aria-label="${t(k)}" data-tip="${k}">i</button>`;
function build() {
  sec = mountSection('llsn-filters', 'flAria');
  sec.innerHTML = `
    <div class="fc-grid">
      ${DEFS.map(d => `<div class="fc-cell" data-k="${d.key}">
        <div class="fc-top"><svg class="fc-ic" viewBox="0 0 16 16" style="color:${d.col === '#EDEDED' ? '#EDEDED' : d.col}" aria-hidden="true">${IC[d.key]}</svg><span class="fc-lbl" data-i18n="${d.label}"></span>${info(d.info)}</div>
        <output class="fc-val num" data-k="${d.key}"></output>
        <input type="range" class="fc-range" data-k="${d.key}" style="--ac:${d.col}"></div>`).join('')}
      <div class="fc-cell fc-match" data-k="match">
        <div class="fc-top"><svg class="fc-ic" viewBox="0 0 16 16" aria-hidden="true">${IC.match}</svg><span class="fc-lbl" data-i18n="fcMatch"></span>${info('fiMatch')}</div>
        <output class="fc-val num fl-count" aria-live="polite"></output>
      </div>
    </div>
    <div class="fc-foot"><p data-i18n="flFoot"></p><button type="button" class="fl-reset ls-link" data-i18n="flReset"></button></div>
    <div class="fc-tip" role="tooltip" hidden></div>`;
  countEl = sec.querySelector('.fl-count');
  for (const d of DEFS) {
    const el = sec.querySelector(`input[data-k="${d.key}"]`);
    inputs[d.key] = el;
    if (d.ge) { el.min = 0; el.max = 100; el.step = 1; el.value = 0; }
    el.addEventListener('input', apply);
  }
  sec.querySelector('.fl-reset').addEventListener('click', reset);
  // i buttons: definition bubble
  const tip = sec.querySelector('.fc-tip');
  sec.addEventListener('click', e => {
    const b = e.target.closest('.fc-i'); if (!b) { tip.hidden = true; return; }
    const open = !tip.hidden && tip.dataset.k === b.dataset.tip;
    tip.hidden = open; tip.dataset.k = b.dataset.tip; tip.textContent = t(b.dataset.tip);
    const r = b.getBoundingClientRect(), s = sec.getBoundingClientRect();
    tip.style.top = `${r.bottom - s.top + 6}px`; tip.style.left = `${Math.max(0, Math.min(s.width - 260, r.left - s.left - 120))}px`;
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') tip.hidden = true; });
  window.addEventListener('llsn:window', onWindow);
  window.addEventListener('llsn:lang', () => { translate(sec); sec.querySelectorAll('.fc-i').forEach(b => b.setAttribute('aria-label', t(b.dataset.tip))); apply(); });
  translate(sec);
  if (LLSN().window) onWindow(); else setDarkMax(24 * 30, true);
}

function setDarkMax(h, atMax) {
  const el = inputs.dark;
  maxDark = Math.max(1, Math.ceil(h));
  el.min = 0; el.max = maxDark; el.step = 1;
  if (atMax || Number(el.value) > maxDark) el.value = maxDark;
}

/** Ground-station share per site for the current window (hours with Earth up at the site AND >= 1 station). */
async function loadGs(w) {
  const key = `${w.i0}|${w.i1}`; if (key === gsKey) return;
  gsKey = key;
  const sites = core.state.sites, out = new Map();
  await Promise.all(sites.map(async s => {
    const r = await stationPeriod(s, w.i0, w.i1);
    if (r && !r.pending && !r.error && r.hours) out.set(s.id, r.any / r.hours);
  }));
  if (key === gsKey) { gs = out; apply(); }
}
/** Share for one site (or null while loading / not available). */
export const gsShare = id => (gs.has(id) ? gs.get(id) : null);

function onWindow() {
  const w = LLSN().window; if (!w) return;
  const wasAtMax = Number(inputs.dark.value) >= maxDark;     // "any" stays "any" when the window length changes
  setDarkMax(w.hours, wasAtMax);
  apply();
  loadGs(w);
}

function reset() {
  for (const d of DEFS) inputs[d.key].value = d.ge ? 0 : maxDark;
  apply();
}

function apply() {
  const w = LLSN().window;
  const v = Object.fromEntries(DEFS.map(d => [d.key, Number(inputs[d.key].value)]));
  for (const d of DEFS) {
    const out = sec.querySelector(`output[data-k="${d.key}"]`), el = inputs[d.key];
    const any = d.ge ? v[d.key] === 0 : v.dark >= maxDark;
    out.textContent = any ? t('flAny') : d.ge ? `≥ ${v[d.key]}%` : `≤ ${fmtHours(v.dark)}`;
    out.classList.toggle('unset', any);
    el.setAttribute('aria-label', `${t(d.label)} (${t(d.ge ? 'flMin' : 'flMax')})`);
    el.setAttribute('aria-valuetext', out.textContent);
    el.style.setProperty('--p', `${((Number(el.value) - Number(el.min)) / ((Number(el.max) - Number(el.min)) || 1)) * 100}%`);
  }
  if (!w) return;
  const active = DEFS.some(d => (d.ge ? v[d.key] > 0 : v[d.key] < maxDark));
  const pass = new Set();
  for (const s of core.state.sites) {
    const m = w.metrics.get(s.id);
    if (!m) continue;
    if (m.pending) { if (!active) pass.add(s.id); continue; }
    const ok = DEFS.every(d => {
      if (d.key === 'gs') { if (v.gs === 0) return true; const g = gsShare(s.id); return g != null && g * 100 >= v.gs - 1e-9; }
      return d.ge ? m[d.field] * 100 >= v[d.key] - 1e-9 : (v.dark >= maxDark || m[d.field] <= v.dark);
    });
    if (ok) pass.add(s.id);
  }
  const n = core.state.sites.length;
  // app.js hides non-matching sites in the picker and marks compared cards "Outside filters" on 'llsn:filter'.
  countEl.textContent = pass.size ? `${pass.size} / ${n}` : t('flNone');
  countEl.classList.toggle('warn', !pass.size);
  window.LLSN.filterPass = active ? pass : null;
  window.dispatchEvent(new CustomEvent('llsn:filter', { detail: { pass: window.LLSN.filterPass } }));
}

whenReady(build);
