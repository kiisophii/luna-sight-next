// app.js — page wiring (integrator). Owns: site picker, 3-card comparison, selected time, analysis period, play.
// Feature modules (web/js/modules.json) are imported after 'llsn:ready' and listen to these events:
//   'llsn:ready'   detail: { state }                         after data is loaded
//   'llsn:time'    detail: { i, date }                       selected time changed (slider, play, time inputs)
//   'llsn:window'  detail: LLSN.window                       analysis period changed (period results recomputed)
//   'llsn:focus'   detail: { id }                            focused site changed (ui_shared.setFocus)
//   'llsn:filter'  detail: { pass }                          filters changed (filters.js)
//   'llsn:lang'    detail: { lang }                          language toggled
// LLSN.window = { i0, i1, hours, days, clipped, mode, metrics: Map(id -> core.metrics) }.
// The period results depend ONLY on [i0, i1]: the selected time and the play speed never change them.
import * as core from './core.js';
import { t, applyI18n, toggleLang, getLang } from './i18n.js';
import { setFocus } from './ui_shared.js';

const $ = sel => document.querySelector(sel);
const params = new URLSearchParams(location.search);
if (params.get('tv') === '1') document.documentElement.classList.add('tv');

const MAX_CMP = 3;
const DEFAULT_CMP = ['APOLLO17', 'SHACKLETON_RIM', 'CHANGE4'];
const GROUPS = ['apollo', 'luna', 'change', 'chandrayaan', 'slim', 'clps', 'artemis3_region', 'polar_peak', 'future', 'custom'];

let now = 0;                   // selected time (hour index, fractional)
let i0 = 0, i1 = 0;            // analysis period (inclusive hour indices)
let periodDays = 30;
let playing = false, timer = null;
let compare = [];              // ids in the comparison cards (≤ 3)
let query = '', group = 'all';

// ------------------------------------------------------------ formatting
const byId = id => core.state.sites.find(s => s.id === id);
const nameOf = s => (getLang() === 'ko' && s.name_ko ? s.name_ko : s.name);
const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function fmtHours(h) {
  if (h === null || h === undefined || !isFinite(h)) return null;
  if (h < 48) return `${h.toFixed(1)} ${t('h')}`;
  const d = Math.floor(h / 24), r = Math.round(h - d * 24);
  return `${d} ${t('d')} ${r} ${t('h')}`;
}
const fmtDeg = x => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(1)}°`;
const fmtUTC = i => core.hourToDate(i).toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
const isoDay = i => core.hourToDate(i).toISOString().slice(0, 10);
const dayStart = i => Math.floor(i / 24) * 24;
const fmtDaysShort = d => (Math.abs(d - Math.round(d)) < 0.05 ? String(Math.round(d)) : d.toFixed(1));
const coordText = s => `${Math.abs(s.lat).toFixed(3)}°${s.lat >= 0 ? 'N' : 'S'}, ${Math.abs(s.lon).toFixed(3)}°${s.lon >= 0 ? 'E' : 'W'}`;

function siteTags(s, withFilter = true) {
  const out = [];
  const hz = core.state.horizons.get(s.id);
  if (hz && hz.browser) out.push(`<span class="tag" title="${esc(t('browserTerrainTip'))}">${t('browserTerrain')}</span>`);
  if (core.horizonMock(s)) out.push(`<span class="tag warn">${t('mockTerrain')}</span>`);
  else if (core.terrainPending(s)) out.push(`<span class="tag warn" title="${esc(t('terrainPendingTip'))}">${t('terrainPending')}</span>`);
  if (s.coord_quality && s.coord_quality !== 'primary') out.push(`<span class="tag">${esc(s.coord_quality)}</span>`);
  const pass = window.LLSN.filterPass;
  if (withFilter && pass && !pass.has(s.id)) out.push(`<span class="tag warn">${t('filteredOut')}</span>`);
  return out.join('');
}

// ------------------------------------------------------------ picker
function fillGroups() {
  const sel = $('#pk-group'), present = new Set(core.state.sites.map(s => s.group));
  sel.innerHTML = `<option value="all">${t('pkAll')}</option>` +
    GROUPS.filter(g => present.has(g)).map(g => `<option value="${g}">${t('g_' + g)}</option>`).join('');
  sel.value = group;
}

function matches(s) {
  if (group !== 'all' && s.group !== group) return false;
  if (!query) return true;
  const hay = `${s.name} ${s.name_ko || ''} ${s.short || ''} ${s.id} ${t('g_' + s.group)} ${s.note || ''}`.toLowerCase();
  return query.toLowerCase().split(/\s+/).every(w => hay.includes(w));
}

function renderPicker() {
  const pass = window.LLSN.filterPass;
  const list = core.state.sites.filter(s => matches(s) && (!pass || pass.has(s.id) || compare.includes(s.id)));
  const focus = window.LLSN.focus;
  $('#pk-list').innerHTML = list.length ? list.map(s => `<li><button type="button" class="pk-item${compare.includes(s.id) ? ' in' : ''}${s.id === focus ? ' focus' : ''}"
      data-id="${s.id}" aria-pressed="${compare.includes(s.id)}">
      <span class="pk-name">${esc(nameOf(s))}</span>
      <span class="pk-meta">${t('g_' + s.group)} · ${coordText(s)}</span>
      <span class="pk-tags">${siteTags(s)}</span></button></li>`).join('')
    : `<li class="muted">${t('pkNone')}</li>`;
  $('#pk-count').textContent = `${list.length} ${t('pkOf')} ${core.state.sites.length} ${t('pkShown')}`;
}

function pick(id) {
  if (!byId(id)) return;
  if (!compare.includes(id)) {
    compare.push(id);
    if (compare.length > MAX_CMP) {                           // drop the oldest card that is not focused
      const k = compare.findIndex(x => x !== window.LLSN.focus && x !== id);
      compare.splice(k < 0 ? 0 : k, 1);
    }
    buildCards();
  }
  setFocus(id);
  saveURL();
}

function unpick(id) {
  compare = compare.filter(x => x !== id);
  buildCards();
  if (window.LLSN.focus === id && compare.length) setFocus(compare[0]);
  renderPicker();
  saveURL();
}

// ------------------------------------------------------------ comparison cards
function cardHTML(s) {
  return `<article class="card" data-id="${s.id}" tabindex="0">
    <header class="card-head">
      <div><h3 class="site-name">${esc(nameOf(s))}</h3><p class="coords">${t('g_' + s.group)} · ${coordText(s)}</p>
        <p class="tags v-tags">${siteTags(s)}</p></div>
      <button type="button" class="rm" aria-label="${esc(t('cmpRemove'))}" title="${esc(t('cmpRemove'))}">×</button>
    </header>
    <div class="blk instant">
      <h4><span>${t('instTitle')}</span> <span class="num v-time"></span></h4>
      <div class="big sun"><span class="label">${t('sunEl')}</span><span class="value v-sunel"></span><span class="sub v-sunaz"></span></div>
      <div class="row">
        <div class="big sun"><span class="label v-sunlbl"></span><span class="value v-sunt"></span></div>
        <div class="big earth"><span class="label v-earthlbl"></span><span class="value v-eartht"></span></div>
      </div>
      <div class="chips"><span class="chip v-sunchip"></span><span class="chip v-earthchip"></span></div>
      <p class="small v-earthel"></p>
    </div>
    <div class="blk period">
      <h4><span>${t('perTitle')}</span> <span class="num v-range"></span></h4>
      <div class="pgrid">
        <div class="pm sun"><span class="label">${t('perSun')}</span><span class="value v-psun"></span><span class="sub v-psund"></span></div>
        <div class="pm earth"><span class="label">${t('perEarth')}</span><span class="value v-pearth"></span><span class="sub v-pearthd"></span></div>
        <div class="pm both"><span class="label">${t('perBoth')}</span><span class="value v-pboth"></span><span class="sub v-pbothd"></span></div>
        <div class="pm dark"><span class="label">${t('perDark')}</span><span class="value v-pdark"></span><span class="sub v-pdarkd"></span></div>
      </div>
    </div>
    <p class="focus-note">${t('cmpFocus')}</p>
  </article>`;
}

function buildCards() {
  const cards = compare.map(byId).filter(Boolean);
  const empty = Math.max(0, MAX_CMP - cards.length);
  $('#cards').innerHTML = cards.map(cardHTML).join('') +
    `<div class="card empty"><p>${t('cmpEmpty')}</p></div>`.repeat(empty);
  markFocus();
  renderPeriodCards();
  renderInstant();
}

function markFocus() {
  const f = window.LLSN.focus;
  document.querySelectorAll('#cards .card[data-id]').forEach(c => c.classList.toggle('is-focus', c.dataset.id === f));
}

function setDur(node, h) {
  const txt = fmtHours(h);
  node.classList.toggle('na', txt === null);
  node.textContent = txt ?? t('notInWindow');
}

/** core.untilX scans hour by hour to the next flip (up to 5 years when Earth never sets). While the selected time
 *  stays before that flip and in the same state, the flip time is unchanged, so remember its absolute hour per site
 *  and kind. Exact: core.js bisects inside the hour of the flip independently of the start time. */
const flipCache = new WeakMap();        // site object -> Map(kind -> { from, at })  (at = Infinity for "none")
function untilCached(fn, kind, s, i) {
  let m = flipCache.get(s); if (!m) flipCache.set(s, m = new Map());
  const c = m.get(kind);
  if (c && i >= c.from && i < c.at - 1e-6) return c.at === Infinity ? null : c.at - i;
  const h = fn(s, i);
  if (h === null) m.set(kind, { from: i, at: Infinity });
  else if (h > 0) m.set(kind, { from: i, at: i + h });
  return h;
}

/** Instant values at the selected time (cheap; runs every animation frame for ≤ 3 sites). */
function renderInstant() {
  $('#time-label').textContent = fmtUTC(now);
  $('#now-short').textContent = fmtUTC(now);
  for (const el of document.querySelectorAll('#cards .card[data-id]')) {
    const s = byId(el.dataset.id);
    const sun = core.sunAzEl(s, now), earth = core.earthAzEl(s, now);
    const lit = core.sunlit(s, now), eUp = core.earthVisible(s, now);
    el.querySelector('.v-time').textContent = fmtUTC(now);
    el.querySelector('.v-sunel').textContent = fmtDeg(sun.el);
    el.querySelector('.v-sunaz').textContent = `${t('az')} ${sun.az.toFixed(0)}°`;
    el.querySelector('.v-sunlbl').textContent = t(lit ? 'untilSunset' : 'untilSunrise');
    setDur(el.querySelector('.v-sunt'), lit ? untilCached(core.untilSunset, 'set', s, now) : untilCached(core.untilSunrise, 'rise', s, now));
    el.querySelector('.v-earthlbl').textContent = t(eUp ? 'untilEarthset' : 'untilEarthrise');
    setDur(el.querySelector('.v-eartht'), eUp ? untilCached(core.untilEarthset, 'eset', s, now) : untilCached(core.untilEarthrise, 'erise', s, now));
    const sc = el.querySelector('.v-sunchip'), ec = el.querySelector('.v-earthchip');
    sc.textContent = (lit ? '☀ ' : '◐ ') + t(lit ? 'sunlit' : 'dark'); sc.className = 'chip v-sunchip ' + (lit ? 'on sun' : 'off');
    ec.textContent = (eUp ? '● ' : '○ ') + t(eUp ? 'earthUp' : 'earthDown'); ec.className = 'chip v-earthchip ' + (eUp ? 'on earth' : 'off');
    el.querySelector('.v-earthel').textContent = `${t('earthEl')} ${fmtDeg(earth.el)} · ${t('az')} ${earth.az.toFixed(0)}°`;
  }
}

/** Period values on the cards (from LLSN.window; changes only with the period). */
function renderPeriodCards() {
  const w = window.LLSN.window; if (!w) return;
  const rng = `${isoDay(w.i0)} → ${isoDay(w.i1)} · ${fmtDaysShort(w.days)} ${t('days')}`;
  for (const el of document.querySelectorAll('#cards .card[data-id]')) {
    const m = w.metrics.get(el.dataset.id); if (!m) continue;
    el.querySelector('.v-range').textContent = rng;
    const put = (k, frac) => {
      el.querySelector(`.v-p${k}`).textContent = `${Math.round(frac * 100)}%`;
      el.querySelector(`.v-p${k}d`).textContent = `${(frac * w.days).toFixed(1)} ${t('dOf')} ${fmtDaysShort(w.days)} ${t('days')}`;
    };
    put('sun', m.sun_frac); put('earth', m.earth_frac); put('both', m.both_frac);
    el.querySelector('.v-pdark').textContent = fmtHours(m.longest_dark_h) ?? '—';
    el.querySelector('.v-pdarkd').textContent = `${(m.longest_dark_h / 24).toFixed(1)} ${t('days')}`;
    el.querySelector('.v-tags').innerHTML = siteTags(byId(el.dataset.id));
  }
}

// ------------------------------------------------------------ time + period
/** Recompute the period results for every site. Called only when the period start or length changes. */
function setPeriod(start, days) {
  const [a, b] = core.hourRange();
  periodDays = Math.max(1, Math.round(days));
  i0 = Math.min(Math.max(dayStart(start), a), b);
  const want = i0 + periodDays * 24 - 1;
  i1 = Math.min(b, want);
  const metrics = new Map();
  for (const s of core.state.sites) metrics.set(s.id, core.metrics(s, i0, i1));
  const hours = i1 - i0 + 1;
  window.LLSN.window = { i0, i1, hours, days: hours / 24, clipped: want > b, mode: String(periodDays), metrics };
  const sl = $('#slider');
  sl.min = i0; sl.max = i1;
  $('#t-date').value = isoDay(i0);
  $('#t-days').value = periodDays;
  document.querySelectorAll('#t-period button').forEach(btn => btn.setAttribute('aria-pressed', String(Number(btn.dataset.days) === periodDays)));
  $('#period-label').textContent = `· ${t('periodIs')} ${isoDay(i0)} → ${isoDay(i1)} (${fmtDaysShort(hours / 24)} ${t('days')})` +
    (want > b ? ` · ${t('clipped')}` : '');
  renderPeriodCards();
  window.dispatchEvent(new CustomEvent('llsn:window', { detail: window.LLSN.window }));
  setTime(Math.min(Math.max(now, i0), i1));
  saveURL();
}

export function setTime(i) {
  now = Math.min(Math.max(i, i0), i1);
  $('#slider').value = now;
  const tod = now - dayStart(now), hh = Math.floor(tod), mm = Math.round((tod - hh) * 60);
  if (document.activeElement !== $('#t-tod')) $('#t-tod').value = `${String(hh + (mm === 60 ? 1 : 0)).padStart(2, '0')}:${String(mm % 60).padStart(2, '0')}`;
  renderInstant();
  window.dispatchEvent(new CustomEvent('llsn:time', { detail: { i: now, date: core.hourToDate(now) } }));
}

/** Slider drags fire 'input' several times per frame: apply only the latest value once per animation frame. */
let pendingTime = null;
function setTimeSoon(i) {
  if (pendingTime === null) requestAnimationFrame(() => { const x = pendingTime; pendingTime = null; setTime(x); });
  pendingTime = i;
}

function setPlaying(on) {
  playing = on;
  $('#play').dataset.i18n = on ? 'pause' : 'play';
  $('#play').textContent = t(on ? 'pause' : 'play');
  $('#play').setAttribute('aria-pressed', String(on));
  clearInterval(timer);
  if (on) timer = setInterval(() => {
    const step = Number($('#speed').value);                // hours per frame — only the animation speed
    setTime(now + step > i1 ? i0 : now + step);             // loop inside the analysis period
  }, 100);
}

// ------------------------------------------------------------ URL state (shareable links for the TV)
let urlTimer = null;
function saveURL() {
  clearTimeout(urlTimer);
  urlTimer = setTimeout(() => {
    const p = new URLSearchParams(location.search);
    p.set('sites', compare.join(','));
    if (window.LLSN.focus) p.set('focus', window.LLSN.focus);
    p.set('d', isoDay(i0)); p.set('p', String(periodDays));
    const user = core.state.sites.filter(s => s.group === 'custom' && s.user);
    if (user.length) p.set('u', user.map(s => `${s.lat.toFixed(4)},${s.lon.toFixed(4)}`).join(';')); else p.delete('u');
    p.delete('t');
    history.replaceState(null, '', `${location.pathname}?${p.toString().replace(/%2C/g, ',')}${location.hash}`);
  }, 300);
}

// ------------------------------------------------------------ boot
function relabel() {
  applyI18n();
  fillGroups();
  renderPicker();
  buildCards();
  setPeriodLabelsOnly();
}
function setPeriodLabelsOnly() {
  const w = window.LLSN.window; if (!w) return;
  $('#period-label').textContent = `· ${t('periodIs')} ${isoDay(w.i0)} → ${isoDay(w.i1)} (${fmtDaysShort(w.days)} ${t('days')})` +
    (w.clipped ? ` · ${t('clipped')}` : '');
}

async function main() {
  applyI18n();
  $('#lang').addEventListener('click', () => toggleLang());
  window.addEventListener('llsn:lang', relabel);
  try {
    await core.loadData('data/');
  } catch (e) {
    $('#cards').innerHTML = `<p class="error">${t('error')}: ${esc(e.message)}</p>`;
    throw e;
  }
  document.body.classList.toggle('is-mock', core.state.mock);

  // initial state from the URL: ?sites=A,B,C&focus=A&d=YYYY-MM-DD&p=30 (old ?t=<hour|ISO> still works)
  const ids = new Set(core.state.sites.map(s => s.id));
  compare = (params.get('sites') || DEFAULT_CMP.join(',')).split(',').filter(id => ids.has(id)).slice(0, MAX_CMP);
  if (!compare.length) compare = core.state.sites.slice(0, MAX_CMP).map(s => s.id);
  const focus0 = ids.has(params.get('focus')) ? params.get('focus') : compare[0];
  const [a, b] = core.hourRange();
  let start, t0;
  const tp = params.get('t'), dp = params.get('d');
  if (tp) t0 = isNaN(tp) ? core.dateToHour(new Date(tp)) : Number(tp);
  else if (dp) t0 = core.dateToHour(new Date(dp + 'T00:00:00Z')) + 12;
  else t0 = Math.floor(core.dateToHour(new Date()));       // default: today, current UTC hour
  if (!isFinite(t0)) t0 = 0;
  t0 = Math.min(Math.max(t0, a), b);
  start = dayStart(t0);
  const p0 = Number(params.get('p')); periodDays = p0 > 0 ? p0 : 30;

  window.LLSN.now = () => now;
  window.LLSN.setTime = setTime;
  window.LLSN.setTimeSoon = setTimeSoon;
  window.LLSN.pick = pick;                                 // globe marker click -> comparison + focus (globe_app.js)
  window.LLSN.compare = () => compare.slice();
  window.LLSN.initialParams = new URLSearchParams(params);       // URL at page load (before saveURL rewrites it)
  /** Start the analysis period on day `startHour` (hour index), keeping the time of day; `days` = period length. */
  window.LLSN.setPeriod = (startHour, days = periodDays) => { now = dayStart(startHour) + (now - dayStart(now)); setPeriod(startHour, days); };
  /** Add (or replace) a site computed in the browser (custom_site.js): joins the picker, cards, tables and filters. */
  window.LLSN.addSite = (site, horizon, { focus = true } = {}) => {
    const k = core.state.sites.findIndex(x => x.id === site.id);
    if (k >= 0) core.state.sites[k] = site; else core.state.sites.push(site);
    core.state.horizons.set(site.id, horizon);
    const w = window.LLSN.window;
    if (w) w.metrics.set(site.id, core.metrics(site, w.i0, w.i1));
    fillGroups();
    if (focus) pick(site.id); else { buildCards(); renderPicker(); }
    window.dispatchEvent(new CustomEvent('llsn:sites', { detail: { id: site.id } }));
    if (w) window.dispatchEvent(new CustomEvent('llsn:window', { detail: w }));
    saveURL();
  };
  window.LLSN.focus = focus0;
  fillGroups();
  now = t0;
  setPeriod(start, periodDays);
  buildCards();
  renderPicker();
  setTime(t0);

  // picker
  $('#pk-q').addEventListener('input', e => { query = e.target.value.trim(); renderPicker(); });
  $('#pk-group').addEventListener('change', e => { group = e.target.value; renderPicker(); });
  $('#pk-list').addEventListener('click', e => { const b2 = e.target.closest('.pk-item'); if (b2) pick(b2.dataset.id); });
  // cards (the horizon module also listens for card clicks)
  $('#cards').addEventListener('click', e => {
    const rm = e.target.closest('.rm');
    if (rm) { e.stopPropagation(); unpick(rm.closest('.card').dataset.id); return; }
    const c = e.target.closest('.card[data-id]'); if (c) setFocus(c.dataset.id);
  }, true);
  $('#cards').addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.card[data-id]')) { e.preventDefault(); setFocus(e.target.dataset.id); }
  });
  window.addEventListener('llsn:focus', () => { markFocus(); renderPicker(); saveURL(); });
  window.addEventListener('llsn:filter', () => { renderPicker(); renderPeriodCards(); });

  // time + period controls
  $('#slider').addEventListener('input', e => setTimeSoon(Number(e.target.value)));
  $('#t-date').addEventListener('change', e => {
    if (!e.target.value) return;
    const d = core.dateToHour(new Date(e.target.value + 'T00:00:00Z'));
    if (!isFinite(d)) return;
    now = d + (now - dayStart(now));                       // keep the time of day
    setPeriod(d, periodDays);
  });
  $('#t-tod').addEventListener('change', e => {
    const [hh, mm] = (e.target.value || '0:0').split(':').map(Number);
    setTime(dayStart(now) + hh + (mm || 0) / 60);
  });
  $('#t-period').addEventListener('click', e => { const b2 = e.target.closest('button'); if (b2) setPeriod(i0, Number(b2.dataset.days)); });
  $('#t-days').addEventListener('change', e => { const v = Number(e.target.value); if (v > 0) setPeriod(i0, v); });
  $('#play').addEventListener('click', () => setPlaying(!playing));

  window.dispatchEvent(new CustomEvent('llsn:ready', { detail: { state: core.state } }));
  loadExtraModules();
}

async function loadExtraModules() {
  try {
    const list = await (await fetch('js/modules.json', { cache: 'no-cache' })).json();
    for (const m of list) import(`./${m}`).catch(e => console.error('module failed:', m, e));
  } catch (e) { /* no extra modules */ }
}

main();
