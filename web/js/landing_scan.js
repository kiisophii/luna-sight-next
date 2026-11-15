// landing_scan.js — landing-date comparison (challenge objective 2: "explore date changes / schedule slips").
// For the focused site and every candidate landing day (00:00 UTC) in a chosen range, compute the metrics of the
// first N days after landing with the same definitions as core.metrics (hourly samples): sunlight %, Earth %,
// both %, longest dark. Chart with the best / worst dates and the current analysis-period start; clicking a date
// starts the analysis period there (LLSN.setPeriod).
import * as core from './core.js';
import { t } from './i18n.js';
import { addStrings, whenReady, translate, siteName, getFocus, cssVar, fmtHours, LLSN } from './ui_shared.js';

addStrings({
  lsTitle: 'Landing-date scan', lsAria: 'Landing-date scan for the focused site',
  lsWhy: 'The launch slipped — how do conditions change? Each point is one landing date; values cover the first N days on the surface.',
  lsFrom: 'First landing date (UTC)', lsRange: 'Scan', lsN: 'Days after landing (N)',
  lsM3: '3 months', lsM6: '6 months', lsM12: '12 months', lsM24: '24 months',
  lsSun: 'Sunlight', lsEarth: 'Direct-to-Earth', lsBoth: 'Sun + Earth together', lsDark: 'Longest shadow',
  lsBest: 'Best', lsWorst: 'Worst', lsNow: 'Current period', lsRank: 'Best / worst = highest / lowest "Both" % (ties: shorter longest dark).',
  lsClick: 'Click (or ←/→ then Enter) to start the analysis period on that date.',
  lsFor: 'Site', lsLanding: 'Landing', lsDays: 'days', lsClipped: 'Dates after {d} are not scanned (ephemeris ends 2030-12-31).',
  lsFlat: 'Terrain pending for this site: no real LOLA horizon yet, so the landing-date scan is not computed (no flat-horizon results).',
}, {
  lsTitle: '착륙 날짜 훑어보기', lsAria: '선택한 착륙지의 착륙 날짜 비교',
  lsWhy: '발사가 밀리면 조건은 어떻게 바뀔까? 점 하나가 착륙 날짜 하나이고, 값은 착륙 후 첫 N일 동안이다.',
  lsFrom: '첫 착륙 날짜 (UTC)', lsRange: '범위', lsN: '착륙 후 일수 (N)',
  lsM3: '3개월', lsM6: '6개월', lsM12: '12개월', lsM24: '24개월',
  lsSun: '햇빛', lsEarth: '직접 교신', lsBoth: '해·지구 동시', lsDark: '최장 그늘',
  lsBest: '최고', lsWorst: '최악', lsNow: '현재 기간', lsRank: '최고/최악 = "둘 다" 비율이 가장 높은/낮은 날 (같으면 최장 그늘이 짧은 쪽).',
  lsClick: '날짜를 누르면(또는 ←/→ 후 Enter) 분석 기간이 그날부터 시작한다.',
  lsFor: '착륙지', lsLanding: '착륙', lsDays: '일', lsClipped: '{d} 이후 날짜는 계산하지 않는다(천문력이 2030-12-31에 끝남).',
  lsFlat: '이 착륙지는 지형 계산 전: 실제 LOLA 지평선이 없어서 착륙일 비교를 계산하지 않는다 (평평한 지평선 결과 없음).',
});

let sec, svg, readout, fromIn, nIn, rangeSel, noteEl, siteEl;
let scan = null, cursor = -1;


function init() {
  sec = document.getElementById('llsn-dates');
  if (!sec) { sec = document.createElement('section'); sec.id = 'llsn-dates'; sec.className = 'panel'; document.getElementById('llsn-window')?.after(sec); }
  sec.dataset.i18nAria = 'lsAria';
  sec.innerHTML = `
    <h2><span data-i18n="lsTitle"></span> <span class="ls-site muted"></span></h2>
    <p class="ls-why" data-i18n="lsWhy"></p>
    <div class="ctl">
      <label><span data-i18n="lsFrom"></span> <input class="ls-from" type="date"></label>
      <label><span data-i18n="lsRange"></span> <select class="ls-range">
        <option value="3" data-i18n="lsM3"></option><option value="6" data-i18n="lsM6"></option>
        <option value="12" data-i18n="lsM12"></option><option value="24" data-i18n="lsM24"></option></select></label>
      <label><span data-i18n="lsN"></span> <input class="ls-n" type="number" min="1" max="120" step="1" value="14"></label>
    </div>
    <div class="ls-legend">
      <span class="sun" data-i18n="lsSun"></span><span class="earth" data-i18n="lsEarth"></span><span class="both" data-i18n="lsBoth"></span><span class="dark" data-i18n="lsDark"></span>
    </div>
    <svg class="ls-chart" tabindex="0" role="img" preserveAspectRatio="none"></svg>
    <p class="ls-read num" aria-live="polite"></p>
    <p class="hint ls-note"></p>
    <p class="hint"><span data-i18n="lsRank"></span> <span data-i18n="lsClick"></span></p>`;
  const st = document.createElement('style');
  st.dataset.owner = 'landing_scan.js';
  st.textContent = `
    #llsn-dates .ls-why { margin: 0 0 .6em; }
    #llsn-dates .ls-site { font-weight: 400; font-size: .95rem; }
    #llsn-dates select, #llsn-dates input[type=date] { font: inherit; }
    #llsn-dates .ls-legend { display: flex; flex-wrap: wrap; gap: .3em 1.2em; margin: .7em 0 .2em; font-size: .85rem; color: var(--muted); }
    #llsn-dates .ls-legend span::before { content: ''; display: inline-block; width: 14px; height: 4px; border-radius: 2px; margin-right: .4em; vertical-align: middle; }
    #llsn-dates .ls-legend .sun::before { background: var(--sun); }
    #llsn-dates .ls-legend .earth::before { background: var(--earth); }
    #llsn-dates .ls-legend .both::before { background: var(--relay); height: 6px; }
    #llsn-dates .ls-legend .dark::before { background: var(--off); height: 10px; }
    #llsn-dates .ls-chart { display: block; width: 100%; height: 240px; cursor: pointer; touch-action: pan-y; }
    html.tv #llsn-dates .ls-chart { height: 360px; }
    #llsn-dates .ls-chart:focus-visible { outline: 3px solid var(--text); outline-offset: 2px; border-radius: 6px; }
    #llsn-dates .ls-read { min-height: 1.4em; margin: .3em 0 0; font-family: var(--font-num); font-size: .9rem; }
    #llsn-dates .ls-read b.sun { color: var(--sun); } #llsn-dates .ls-read b.earth { color: var(--earth); }
    #llsn-dates .ls-read b.both { color: var(--relay); }`;
  document.head.appendChild(st);
  svg = sec.querySelector('svg'); readout = sec.querySelector('.ls-read'); noteEl = sec.querySelector('.ls-note');
  fromIn = sec.querySelector('.ls-from'); nIn = sec.querySelector('.ls-n'); rangeSel = sec.querySelector('.ls-range');
  siteEl = sec.querySelector('.ls-site');
  rangeSel.value = '12';
  const [a, b] = core.hourRange();
  const today = Math.min(Math.max(Math.floor(core.dateToHour(new Date()) / 24) * 24, a), b - 24);
  fromIn.value = iso(today); fromIn.min = iso(a); fromIn.max = iso(b - 24);
  translate(sec);

  fromIn.addEventListener('change', run); rangeSel.addEventListener('change', run);
  nIn.addEventListener('change', () => { const v = Math.round(Number(nIn.value)); nIn.value = Math.min(120, Math.max(1, v || 14)); run(); });
  svg.addEventListener('pointermove', e => { if (scan) { cursor = idxAt(e); drawCursor(); } });
  svg.addEventListener('pointerleave', () => { cursor = -1; drawCursor(); });
  svg.addEventListener('click', e => { if (scan) apply(idxAt(e)); });
  svg.addEventListener('keydown', e => {
    if (!scan) return;
    const n = scan.days.length;
    const mv = { ArrowLeft: -1, ArrowRight: 1, PageUp: -30, PageDown: 30, Home: -n, End: n }[e.key];
    if (mv) { e.preventDefault(); cursor = Math.min(n - 1, Math.max(0, (cursor < 0 ? scan.cur ?? 0 : cursor) + mv)); drawCursor(); }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (cursor >= 0) apply(cursor); }
  });
  window.addEventListener('llsn:focus', run);
  window.addEventListener('llsn:sites', run);
  window.addEventListener('llsn:window', () => { if (scan) { markCurrent(); draw(); } });
  window.addEventListener('llsn:lang', () => { translate(sec); draw(); });
  new ResizeObserver(() => draw()).observe(svg);
  run();
}

const iso = i => core.hourToDate(i).toISOString().slice(0, 10);

/** Hourly sunlit / Earth flags once, then a sliding N-day window per landing day (same maths as core.metrics). */
function compute(site, start, nDays, months) {
  const [, b] = core.hourRange();
  const win = nDays * 24;
  const endDay = new Date(core.hourToDate(start)); endDay.setUTCMonth(endDay.getUTCMonth() + months);
  let last = Math.min(Math.floor(core.dateToHour(endDay) / 24) * 24, Math.floor((b - win + 1) / 24) * 24);
  const clipped = last < Math.floor(core.dateToHour(endDay) / 24) * 24;
  if (last < start) last = start;
  const nh = last - start + win;
  const sun = new Uint8Array(nh), earth = new Uint8Array(nh);
  for (let k = 0; k < nh; k++) {
    const i = start + k; if (i > b) break;
    sun[k] = core.sunlit(site, i) ? 1 : 0; earth[k] = core.earthVisible(site, i) ? 1 : 0;
  }
  const cs = new Int32Array(nh + 1), ce = new Int32Array(nh + 1), cb = new Int32Array(nh + 1);
  for (let k = 0; k < nh; k++) { cs[k + 1] = cs[k] + sun[k]; ce[k + 1] = ce[k] + earth[k]; cb[k + 1] = cb[k] + (sun[k] & earth[k]); }
  const days = [];
  for (let d = start; d <= last; d += 24) {
    const k0 = d - start, k1 = Math.min(k0 + win, nh), n = k1 - k0;
    let run = 0, longest = 0;
    for (let k = k0; k < k1; k++) { run = sun[k] ? 0 : run + 1; if (run > longest) longest = run; }
    days.push({ i: d, sun: (cs[k1] - cs[k0]) / n, earth: (ce[k1] - ce[k0]) / n, both: (cb[k1] - cb[k0]) / n, dark: longest });
  }
  let best = 0, worst = 0;
  days.forEach((x, k) => {
    const B = days[best], Wd = days[worst];
    if (x.both > B.both + 1e-9 || (Math.abs(x.both - B.both) < 1e-9 && x.dark < B.dark)) best = k;
    if (x.both < Wd.both - 1e-9 || (Math.abs(x.both - Wd.both) < 1e-9 && x.dark > Wd.dark)) worst = k;
  });
  return { site, start, last, nDays, days, best, worst, clipped, maxDark: Math.max(24, ...days.map(x => x.dark)) };
}

function run() {
  const site = getFocus(); if (!site || !core.state.n) return;
  const [a, b] = core.hourRange();
  let start = fromIn.value ? core.dateToHour(new Date(fromIn.value + 'T00:00:00Z')) : a;
  if (!isFinite(start)) start = a;
  start = Math.min(Math.max(Math.floor(start / 24) * 24, a), b - 24);
  const nDays = Math.min(120, Math.max(1, Math.round(Number(nIn.value) || 14)));
  if (core.terrainPending(site)) {
    scan = null; cursor = -1; geom = null;
    svg.innerHTML = ''; readout.textContent = '';
    siteEl.textContent = `· ${siteName(site)}`; noteEl.textContent = t('lsFlat');
    return;
  }
  const t0 = performance.now();
  scan = compute(site, start, nDays, Number(rangeSel.value));
  scan.ms = performance.now() - t0;
  cursor = -1;
  markCurrent();
  draw();
}

function markCurrent() {
  const w = LLSN().window; scan.cur = null;
  if (!w) return;
  const k = Math.round((w.i0 - scan.start) / 24);
  if (k >= 0 && k < scan.days.length) scan.cur = k;
}

let geom = null;
function draw() {
  if (!scan || !svg) return;
  const W = svg.clientWidth || 600, H = svg.clientHeight || 240;
  const fs = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const padL = fs * 2.6, padR = fs * 5.4, padT = fs * 1.4, padB = fs * 1.5;
  const darkH = (H - padT - padB) * 0.26, gap = fs * 0.5;
  const topH = H - padT - padB - darkH - gap;
  const n = scan.days.length, pw = W - padL - padR;
  const X = k => padL + (n <= 1 ? pw / 2 : k / (n - 1) * pw);
  const Y = f => padT + (1 - f) * topH;
  const yD0 = padT + topH + gap, YD = h => yD0 + (h / scan.maxDark) * darkH;
  geom = { X, padL, pw, n, H, padT };
  const C = { sun: cssVar('--sun'), earth: cssVar('--earth'), relay: cssVar('--relay'), off: cssVar('--off'), text: cssVar('--text'),
    muted: cssVar('--muted'), border: cssVar('--border'), warn: cssVar('--warn'), num: cssVar('--font-num'), bg: cssVar('--bg') };
  const line = key => scan.days.map((d, k) => `${k ? 'L' : 'M'}${X(k).toFixed(1)},${Y(d[key]).toFixed(1)}`).join('');
  const bw = Math.max(1, pw / Math.max(n, 1) * 0.8);
  let out = `<g font-family="${C.num}" font-size="${fs * 0.7}" fill="${C.muted}">`;
  for (const f of [0, 0.5, 1]) out += `<line x1="${padL}" x2="${padL + pw}" y1="${Y(f)}" y2="${Y(f)}" stroke="${C.border}" stroke-dasharray="${f === 0 ? '' : '2 4'}"/>
    <text x="${padL - 4}" y="${Y(f) + fs * 0.25}" text-anchor="end">${f * 100}%</text>`;
  out += `<text x="${padL + pw + 4}" y="${yD0 + fs * 0.6}">${t('lsDark')}</text>
    <text x="${padL + pw + 4}" y="${yD0 + darkH}">${(scan.maxDark / 24).toFixed(1)} ${t('d')}</text>`;
  // month ticks
  let prevM = -1;
  scan.days.forEach((d, k) => {
    const dt = core.hourToDate(d.i), m = dt.getUTCMonth();
    if (m !== prevM && dt.getUTCDate() <= 1 + (n > 400 ? 3 : 0)) {
      out += `<line x1="${X(k)}" x2="${X(k)}" y1="${padT}" y2="${yD0 + darkH}" stroke="${C.border}" stroke-dasharray="1 5"/>
        <text x="${X(k) + 2}" y="${H - fs * 0.35}">${m === 0 || k === 0 ? dt.getUTCFullYear() + '-' : ''}${String(m + 1).padStart(2, '0')}</text>`;
    }
    prevM = m;
  });
  out += '</g>';
  out += `<g fill="${C.off}">${scan.days.map((d, k) => d.dark ? `<rect x="${(X(k) - bw / 2).toFixed(1)}" y="${yD0}" width="${bw.toFixed(1)}" height="${(YD(d.dark) - yD0).toFixed(1)}"/>` : '').join('')}</g>`;
  out += `<path d="${line('sun')}" fill="none" stroke="${C.sun}" stroke-width="1.6"/>
    <path d="${line('earth')}" fill="none" stroke="${C.earth}" stroke-width="1.6"/>
    <path d="${line('both')}" fill="none" stroke="${C.relay}" stroke-width="2.6"/>`;
  const mark = (k, label, col, up) => {
    const x = X(k), y = Y(scan.days[k].both);
    const anchor = x > padL + pw * 0.85 ? 'end' : x < padL + pw * 0.15 ? 'start' : 'middle';
    return `<line x1="${x}" x2="${x}" y1="${padT}" y2="${yD0 + darkH}" stroke="${col}" stroke-width="1.5"/>
      <circle cx="${x}" cy="${y}" r="${fs * 0.32}" fill="${col}" stroke="${C.bg}" stroke-width="1.5"/>
      <text x="${x}" y="${up ? padT - fs * 0.35 : padT - fs * 0.35}" text-anchor="${anchor}" font-family="${C.num}" font-size="${fs * 0.72}" font-weight="700" fill="${col}">${label} ${iso(scan.days[k].i).slice(5)}</text>`;
  };
  out += mark(scan.best, '▲ ' + t('lsBest'), C.relay, true);
  if (scan.worst !== scan.best) out += mark(scan.worst, '▼ ' + t('lsWorst'), C.warn, true);
  if (scan.cur !== null) {
    const x = X(scan.cur);
    out += `<line x1="${x}" x2="${x}" y1="${padT}" y2="${yD0 + darkH}" stroke="${C.text}" stroke-width="2" stroke-dasharray="5 3"/>
      <text x="${x + 4}" y="${padT + topH * 0.5}" font-size="${fs * 0.7}" fill="${C.text}" font-family="${C.num}">${t('lsNow')}</text>`;
  }
  out += `<g class="ls-cursor"></g>`;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = out;
  const site = scan.site;
  siteEl.textContent = `· ${siteName(site)}`;
  svg.setAttribute('aria-label', `${t('lsTitle')}: ${siteName(site)}, ${iso(scan.start)} → ${iso(scan.last)}, N = ${scan.nDays} ${t('lsDays')}. ` +
    `${t('lsBest')} ${iso(scan.days[scan.best].i)} (${t('lsBoth')} ${pct(scan.days[scan.best].both)}), ${t('lsWorst')} ${iso(scan.days[scan.worst].i)} (${pct(scan.days[scan.worst].both)}).`);
  const notes = [];
  if (core.terrainPending(site)) notes.push(t('lsFlat'));
  if (scan.clipped) notes.push(t('lsClipped').replace('{d}', iso(scan.last)));
  noteEl.textContent = notes.join(' ');
  drawCursor();
}

const pct = f => `${Math.round(f * 100)}%`;
function describe(k) {
  const d = scan.days[k];
  return `${t('lsLanding')} ${iso(d.i)} · ${scan.nDays} ${t('lsDays')}: <b class="sun">${t('lsSun')} ${pct(d.sun)}</b> · ` +
    `<b class="earth">${t('lsEarth')} ${pct(d.earth)}</b> · <b class="both">${t('lsBoth')} ${pct(d.both)}</b> · ${t('lsDark')} ${fmtHours(d.dark)}`;
}

function drawCursor() {
  if (!scan || !geom) return;
  const g = svg.querySelector('.ls-cursor'); if (!g) return;
  const k = cursor >= 0 ? cursor : (scan.cur ?? scan.best);
  if (cursor >= 0) {
    const x = geom.X(cursor);
    g.innerHTML = `<line x1="${x}" x2="${x}" y1="${geom.padT}" y2="${geom.H - 4}" stroke="${cssVar('--text')}" stroke-width="1" opacity=".6"/>`;
  } else g.innerHTML = '';
  readout.innerHTML = describe(k);
}

function idxAt(e) {
  const r = svg.getBoundingClientRect();
  const x = (e.clientX - r.left) * ((svg.clientWidth || r.width) / r.width);
  return Math.min(geom.n - 1, Math.max(0, Math.round((x - geom.padL) / geom.pw * (geom.n - 1))));
}

function apply(k) {
  if (!scan || k < 0) return;
  if (typeof LLSN().setPeriod === 'function') LLSN().setPeriod(scan.days[k].i, scan.nDays);
}

whenReady(init);   // last: every const above is initialised before init runs
