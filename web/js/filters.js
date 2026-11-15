// filters.js — threshold sliders that filter the site list (phase 3 UI).
// Uses the per-site metrics of the current analysis window (LLSN.window from window_metrics.js).
// Publishes LLSN.filterPass (Set of ids) and fires 'llsn:filter'.
import * as core from './core.js';
import { t } from './i18n.js';
import { addStrings, whenReady, mountSection, translate, siteName, fmtHours, LLSN } from './ui_shared.js';

addStrings({
  flTitle: 'Filter sites', flAria: 'Filter sites by sunlight, direct-to-Earth and shadow',
  flSun: 'Sunlight ≥', flEarth: 'Direct-to-Earth ≥', flBoth: 'Sun + Earth together ≥', flDark: 'Longest shadow ≤',
  flAny: 'any', flReset: 'Reset filters', flMatch: 'sites match', flOf: 'of',
  flNone: 'No site matches. Loosen a slider.',
  flHint: 'Thresholds apply to the period results of the analysis window above. Sites that fail are removed from the site list; compared cards stay but are marked. Reset brings everything back.',
}, {
  flTitle: '착륙지 거르기', flAria: '햇빛·직접 교신·어둠으로 착륙지 거르기',
  flSun: '햇빛 ≥', flEarth: '직접 교신 ≥', flBoth: '해·지구 동시 ≥', flDark: '최장 그늘 ≤',
  flAny: '상관없음', flReset: '거르기 초기화', flMatch: '곳이 맞음', flOf: '/',
  flNone: '맞는 착륙지가 없다. 슬라이더를 풀어 보자.',
  flHint: '기준은 위 분석 기간의 기간 결과에 적용된다. 맞지 않는 곳은 착륙지 목록에서 빠지고, 비교 카드는 남지만 표시가 붙는다. 초기화하면 모두 돌아온다.',
});

// key -> metric field, unit, comparison
const DEFS = [
  { key: 'sun', label: 'flSun', field: 'sun_frac', ge: true, col: 'var(--sun)' },
  { key: 'earth', label: 'flEarth', field: 'earth_frac', ge: true, col: 'var(--earth)' },
  { key: 'both', label: 'flBoth', field: 'both_frac', ge: true, col: 'var(--relay)' },
  { key: 'dark', label: 'flDark', field: 'longest_dark_h', ge: false, col: 'var(--text)' },
];
let sec, countEl, listEl, inputs = {};
let maxDark = 24;                       // slider max = window length in hours (set on llsn:window)

function build() {
  sec = mountSection('llsn-filters', 'flAria');
  sec.innerHTML = `
    <h2 data-i18n="flTitle"></h2>
    <div class="fl-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.6em calc(var(--gap)*1.5)">
      ${DEFS.map(d => `<label class="fl-item" style="display:flex;flex-direction:column;gap:.2em">
        <span style="display:flex;justify-content:space-between;gap:.5em"><span data-i18n="${d.label}"></span>
          <output class="fl-val" data-k="${d.key}" style="white-space:nowrap;font-family:var(--font-num);font-weight:700;color:${d.col}"></output></span>
        <input type="range" data-k="${d.key}" style="width:100%;accent-color:${d.col}"></label>`).join('')}
    </div>
    <div class="ctl" style="margin-top:calc(var(--gap)*.6)">
      <button type="button" class="fl-reset" data-i18n="flReset"></button>
      <span class="fl-count" aria-live="polite" style="font-weight:700"></span>
      <span class="fl-list" style="color:var(--muted)"></span>
    </div>
    <p class="hint" data-i18n="flHint"></p>`;
  countEl = sec.querySelector('.fl-count'); listEl = sec.querySelector('.fl-list');
  for (const d of DEFS) {
    const el = sec.querySelector(`input[data-k="${d.key}"]`);
    inputs[d.key] = el;
    if (d.ge) { el.min = 0; el.max = 100; el.step = 1; el.value = 0; }
    el.setAttribute('aria-label', t(d.label));
    el.addEventListener('input', apply);
  }
  sec.querySelector('.fl-reset').addEventListener('click', reset);
  window.addEventListener('llsn:window', onWindow);
  window.addEventListener('llsn:lang', () => { translate(sec); apply(); });
  translate(sec);
  if (LLSN().window) onWindow(); else setDarkMax(24 * 30, true);
}

function setDarkMax(h, atMax) {
  const el = inputs.dark;
  maxDark = Math.max(1, Math.ceil(h));
  el.min = 0; el.max = maxDark; el.step = 1;
  if (atMax || Number(el.value) > maxDark) el.value = maxDark;
}

function onWindow() {
  const w = LLSN().window; if (!w) return;
  const wasAtMax = Number(inputs.dark.value) >= maxDark;     // "any" stays "any" when the window length changes
  setDarkMax(w.hours, wasAtMax);
  apply();
}

function reset() {
  for (const d of DEFS) inputs[d.key].value = d.ge ? 0 : maxDark;
  apply();
}

function apply() {
  const w = LLSN().window;
  const v = Object.fromEntries(DEFS.map(d => [d.key, Number(inputs[d.key].value)]));
  for (const d of DEFS) {
    const out = sec.querySelector(`output[data-k="${d.key}"]`);
    if (d.ge) out.textContent = v[d.key] === 0 ? t('flAny') : `${v[d.key]}%`;
    else out.textContent = v.dark >= maxDark ? t('flAny') : fmtHours(v.dark);
    inputs[d.key].setAttribute('aria-valuetext', out.textContent);
  }
  if (!w) return;
  const active = DEFS.some(d => (d.ge ? v[d.key] > 0 : v[d.key] < maxDark));
  const pass = new Set();
  for (const s of core.state.sites) {
    const m = w.metrics.get(s.id);
    if (!m) continue;
    if (m.pending) { if (!active) pass.add(s.id); continue; }
    const ok = DEFS.every(d => d.ge ? m[d.field] * 100 >= v[d.key] - 1e-9 : (v.dark >= maxDark || m[d.field] <= v.dark));
    if (ok) pass.add(s.id);
  }
  const n = core.state.sites.length;
  // app.js hides non-matching sites in the picker and marks compared cards "Outside filters" on 'llsn:filter'.
  countEl.textContent = pass.size ? `${pass.size} ${t('flOf')} ${n} ${t('flMatch')}` : t('flNone');
  countEl.style.color = pass.size ? '' : 'var(--warn)';
  listEl.textContent = active && pass.size ? core.state.sites.filter(s => pass.has(s.id)).map(siteName).join(' · ') : '';
  window.LLSN.filterPass = active ? pass : null;
  window.dispatchEvent(new CustomEvent('llsn:filter', { detail: { pass: window.LLSN.filterPass } }));
}

whenReady(build);
