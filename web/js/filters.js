// filters.js — mission-condition filters for the candidate list: the copy's 2 x 2 cells
// (Sunlight · Earth view / Slope · Longest dark), a reset icon button and a "Done" button (tracker bundle 11).
// Sunlight / Earth view / Longest dark use the per-site metrics of the current analysis window (LLSN.window,
// core.metrics). Slope uses web/data/terrain/<ID>.json (contract §23): the lander-scale slope at the landing
// point for the 16 southern sites (PGDA LOLA 5–20 m), the coarse 250 m box slope for the other 17 sites.
// 'Sun + Earth' and 'Ground link' are not conditions in the base version (kept as "any").
// Publishes LLSN.filterPass (Set of ids) and fires 'llsn:filter'.
import * as core from './core.js';
import { t } from './i18n.js';
import { addStrings, whenReady, mountSection, translate, LLSN } from './ui_shared.js';
import { getJSON } from './values.js';

addStrings({
  flTitle: 'Filter sites', flAria: 'Mission conditions: filter the candidate list',
  fcSun: 'Sunlight', fcEarth: 'Earth view', fcSlope: 'Slope', fcDark: 'Longest dark',
  fiSun: 'Share of hours in the period with at least half of the solar disc above the local terrain horizon. Minimum.',
  fiEarth: 'Share of hours with the Earth centre above the local terrain horizon (geometric visibility, not a working link). Minimum.',
  fiSlope: 'Slope at the landing point, maximum. 16 southern sites: lander-scale slope from 5–20 m PGDA LOLA terrain. Other 17 sites: coarse slope over a 250 m box (SLDEM2015). Your own points have no slope value and drop out when this condition is set. 8° and 15° are reference values only, not landing criteria.',
  fiDark: 'Longest continuous stretch without sunlight in the period. Maximum.',
  flAny: 'any', flDayUnit: 'd', flReset: 'Reset all', flDone: 'Done', flNone: 'No site matches. Loosen a condition.', flEdit: 'Type a value',
}, {
  flTitle: '착륙지 거르기', flAria: '미션 조건: 후보 목록 거르기',
  fcSun: '일조', fcEarth: '지구 가시', fcSlope: '경사', fcDark: '최장 어둠',
  fiSun: '기간 중 태양 원반의 절반 이상이 지형 지평선 위에 있는 시간 비율. 최솟값.',
  fiEarth: '지구 중심이 지형 지평선 위에 있는 시간 비율 (기하학적 가시, 실제 교신 보장 아님). 최솟값.',
  fiSlope: '착륙 지점 경사, 최댓값. 남쪽 16곳은 5–20 m PGDA LOLA 지형의 착륙선 규모 경사, 나머지 17곳은 250 m 상자의 거친 경사(SLDEM2015)입니다. 사용자 지점은 경사 값이 없어 이 조건을 걸면 빠집니다. 8°·15°는 참고값이며 착륙 기준이 아닙니다.',
  fiDark: '기간 중 햇빛이 없는 가장 긴 연속 시간. 최댓값.',
  flAny: '상관없음', flDayUnit: '일', flReset: '모두 초기화', flDone: '완료', flNone: '맞는 착륙지가 없습니다. 조건을 풀어 보세요.', flEdit: '값 직접 입력',
});

const IC = {
  sun: '<circle cx="8" cy="8" r="2.8" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M3.4 12.6l1.3-1.3M11.3 4.7l1.3-1.3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
  earth: '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12" fill="none" stroke="currentColor" stroke-width="1.1"/>',
  slope: '<path d="M2 13h12L14 5z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>',
  dark: '<path d="M3 13L13 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2 1.6"/>',
};
// kind: 'ge' = minimum % (0 = any), 'le' = maximum (slider at max = any)
const DEFS = [
  { key: 'sun', label: 'fcSun', info: 'fiSun', field: 'sun_frac', kind: 'ge', col: 'var(--sun)' },
  { key: 'earth', label: 'fcEarth', info: 'fiEarth', field: 'earth_frac', kind: 'ge', col: 'var(--earth)' },
  { key: 'slope', label: 'fcSlope', info: 'fiSlope', kind: 'le', col: '#EDEDED', min: 1, step: 0.5, unit: '°' },
  { key: 'dark', label: 'fcDark', info: 'fiDark', field: 'longest_dark_h', kind: 'le', col: '#EDEDED', min: 2, step: 1, unit: 'd' },   // days
];
let sec, inputs = {};
const max = { dark: 30, slope: 15 };      // 'le' slider maxima = 'any' (the copy: longest dark 2–30 d, slope 1–15 deg)
let slopes = new Map();                    // id -> landing-point slope in degrees (terrain/<ID>.json)

/** Landing-point slope (deg) for a catalogue site, or null (custom points have no terrain file). */
export const slopeOf = id => (slopes.has(id) ? slopes.get(id) : null);
async function loadSlopes() {
  const out = new Map();
  await Promise.all(core.state.sites.filter(s => !s.user && s.group !== 'custom').map(async s => {
    const d = await getJSON(`${core.state.base}terrain/${s.id}.json`).catch(() => null);
    const v = d ? (d.landing_slope_deg != null ? d.landing_slope_deg : d.relay_box?.slope_deg) : null;
    if (v != null && isFinite(v)) out.set(s.id, Number(v));
  }));
  slopes = out;
  apply();
}

const info = k => `<button type="button" class="fc-i" aria-label="${t(k)}" data-tip="${k}"><svg class="ic-i" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 7.3v3.9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="8" cy="4.9" r=".9" fill="currentColor"/></svg></button>`;
function build() {
  sec = mountSection('llsn-filters', 'flAria');
  sec.innerHTML = `
    <div class="fc-grid">
      ${DEFS.map(d => `<div class="fc-cell" data-k="${d.key}">
        <div class="fc-top"><svg class="fc-ic" viewBox="0 0 16 16" style="color:${d.col}" aria-hidden="true">${IC[d.key]}</svg><span class="fc-lbl" data-i18n="${d.label}"></span>${info(d.info)}</div>
        <button type="button" class="fc-val num" data-k="${d.key}"></button>
        <span class="fc-track"><i class="fc-mid" aria-hidden="true"></i><input type="range" class="fc-range" data-k="${d.key}" style="--ac:${d.col}"></span></div>`).join('')}
    </div>
    <div class="fc-foot">
      <button type="button" class="fl-reset" data-i18n-aria="flReset"><svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.2 8a4.8 4.8 0 1 0 1.5-3.5M3 2.5v2.6h2.6" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
      <button type="button" class="fl-done"><svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg><span data-i18n="flDone"></span></button>
    </div>
    <span class="fl-count sr" aria-live="polite"></span>
    <div class="fc-tip" role="tooltip" hidden></div>`;
  for (const d of DEFS) {
    const el = sec.querySelector(`input[data-k="${d.key}"]`);
    inputs[d.key] = el;
    if (d.kind === 'ge') { el.min = 0; el.max = 100; el.step = 1; el.value = 0; }
    else { el.min = d.min; el.max = max[d.key]; el.step = d.step; el.value = max[d.key]; }
    el.addEventListener('input', apply);
  }
  sec.querySelector('.fl-reset').addEventListener('click', reset);
  // Done closes the conditions (same as the title-row toggle) and returns focus there
  sec.querySelector('.fl-done').addEventListener('click', () => { const b = document.querySelector('.ls-fold[data-fold="ls-cond"]'); if (b) { b.dataset.userClick = '1'; b.click(); } });
  // value button: click to type a number (Enter applies, Esc cancels)
  sec.addEventListener('click', e => {
    const vb = e.target.closest('.fc-val'); if (vb && !vb.querySelector('input')) { editValue(vb); return; }
    const tip = sec.querySelector('.fc-tip'), b = e.target.closest('.fc-i');
    if (!b) { tip.hidden = true; return; }
    const open = !tip.hidden && tip.dataset.k === b.dataset.tip;
    tip.hidden = open; tip.dataset.k = b.dataset.tip; tip.textContent = t(b.dataset.tip);
    const r = b.getBoundingClientRect(), s = sec.getBoundingClientRect();
    tip.style.top = `${r.bottom - s.top + 6}px`; tip.style.left = `${Math.max(0, Math.min(s.width - 260, r.left - s.left - 120))}px`;
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') sec.querySelector('.fc-tip').hidden = true; });
  window.addEventListener('llsn:window', onWindow);
  window.addEventListener('llsn:sites', loadSlopes);
  window.addEventListener('llsn:lang', () => { translate(sec); sec.querySelectorAll('.fc-i').forEach(b => b.setAttribute('aria-label', t(b.dataset.tip))); sec.querySelector('.fl-reset').title = t('flReset'); apply(); });
  translate(sec);
  sec.querySelector('.fl-reset').title = t('flReset');
  apply();
  loadSlopes();
}

function editValue(vb) {
  const d = DEFS.find(x => x.key === vb.dataset.k), el = inputs[d.key];
  const any = d.kind === 'ge' ? Number(el.value) === 0 : Number(el.value) >= Number(el.max);
  vb.innerHTML = `<input type="number" class="fc-num" min="${el.min}" max="${el.max}" step="${el.step}" value="${any ? '' : el.value}" placeholder="${d.unit || '%'}" aria-label="${t(d.label)}: ${t('flEdit')}">`;
  const inp = vb.firstElementChild; inp.focus(); inp.select();
  const done = ok => {
    if (ok && inp.value !== '') el.value = Math.min(Number(el.max), Math.max(Number(el.min), Number(inp.value)));
    else if (ok) el.value = d.kind === 'ge' ? 0 : el.max;
    vb.textContent = '';                      // drop the input first so apply() writes the new label
    apply(); vb.focus();
  };
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); done(true); } else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(false); } });
  inp.addEventListener('blur', () => { if (inp.isConnected) done(true); });
  inp.addEventListener('click', e => e.stopPropagation());
}

function onWindow() { apply(); }

function reset() {
  for (const d of DEFS) inputs[d.key].value = d.kind === 'ge' ? 0 : max[d.key];
  apply();
}

function apply() {
  const w = LLSN().window;
  const v = Object.fromEntries(DEFS.map(d => [d.key, Number(inputs[d.key].value)]));
  const isAny = d => (d.kind === 'ge' ? v[d.key] === 0 : v[d.key] >= max[d.key]);
  for (const d of DEFS) {
    const out = sec.querySelector(`.fc-val[data-k="${d.key}"]`), el = inputs[d.key], any = isAny(d);
    const txt = any ? t('flAny') : d.kind === 'ge' ? `≥ ${v[d.key]} %` : d.key === 'slope' ? `≤ ${v.slope.toFixed(1)} °` : `≤ ${v.dark} ${t('flDayUnit')}`;
    if (!out.querySelector('input')) out.textContent = txt;
    out.classList.toggle('unset', any);
    out.setAttribute('aria-label', `${t(d.label)}: ${txt}. ${t('flEdit')}`);
    el.setAttribute('aria-label', t(d.label));
    el.setAttribute('aria-valuetext', txt);
    el.style.setProperty('--p', `${((Number(el.value) - Number(el.min)) / ((Number(el.max) - Number(el.min)) || 1)) * 100}%`);
  }
  if (!w) return;
  const active = DEFS.some(d => !isAny(d));
  const pass = new Set();
  for (const s of core.state.sites) {
    const m = w.metrics.get(s.id);
    if (!m) continue;
    if (m.pending) { if (!active) pass.add(s.id); continue; }
    const ok = DEFS.every(d => {
      if (isAny(d)) return true;
      if (d.key === 'slope') { const g = slopeOf(s.id); return g != null && g <= v.slope + 1e-9; }
      return d.kind === 'ge' ? m[d.field] * 100 >= v[d.key] - 1e-9 : m[d.field] <= v.dark * 24;   // longest dark: days -> hours
    });
    if (ok) pass.add(s.id);
  }
  const n = core.state.sites.length;
  // app.js hides non-matching sites in the picker and marks compared cards "Outside filters" on 'llsn:filter'.
  sec.querySelector('.fl-count').textContent = pass.size ? `${pass.size} / ${n}` : t('flNone');
  window.LLSN.filterPass = active ? pass : null;
  window.dispatchEvent(new CustomEvent('llsn:filter', { detail: { pass: window.LLSN.filterPass } }));
}

whenReady(build);
