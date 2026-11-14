// app.js — page wiring for the comparison cards and the time slider (card 6).
// Other features: add web/js/<feature>.js, list it in web/js/modules.json, and listen to the events below.
//   'llsn:ready'  detail: { state }          after data is loaded
//   'llsn:time'   detail: { i, date }        whenever the time changes (slider, play)
//   'llsn:lang'   detail: { lang }           after the language toggle
// Current time is also readable as window.LLSN.now().
import * as core from './core.js';
import { t, applyI18n, toggleLang, getLang } from './i18n.js';

const $ = sel => document.querySelector(sel);
const params = new URLSearchParams(location.search);
if (params.get('tv') === '1') document.documentElement.classList.add('tv');

let now = 0, playing = false, timer = null;

function fmtHours(h) {
  if (h === null || h === undefined) return null;
  if (h < 48) return `${h.toFixed(1)} ${t('h')}`;
  const d = Math.floor(h / 24), r = Math.round(h - d * 24);
  return `${d} ${t('d')} ${r} ${t('h')}`;
}
const fmtDeg = x => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(1)}°`;
const pct = x => `${Math.round(x * 100)}%`;
const fmtDate = d => d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';

function cardHTML(site) {
  return `<article class="card" data-id="${site.id}">
    <header><h2 class="site-name"></h2><p class="coords"></p></header>
    <div class="big sun"><span class="label" data-i18n="sunEl"></span><span class="value v-sunel"></span><span class="sub v-sunaz"></span></div>
    <div class="row">
      <div class="big sun"><span class="label v-sunlbl"></span><span class="value v-sunt"></span></div>
      <div class="big earth"><span class="label v-earthlbl"></span><span class="value v-eartht"></span></div>
    </div>
    <div class="chips"><span class="chip v-sunchip"></span><span class="chip v-earthchip"></span></div>
    <p class="small v-earthel"></p>
    <dl class="stats"><dt data-i18n="windowStats"></dt><dd class="v-stats"></dd></dl>
  </article>`;
}

function renderStatic() {
  const L = getLang();
  for (const s of core.state.sites) {
    const el = document.querySelector(`.card[data-id="${s.id}"]`);
    el.querySelector('.site-name').textContent = L === 'ko' ? s.name_ko : s.name;
    const q = s.coord_quality === 'primary' ? '' : ` · ${s.coord_quality}`;
    el.querySelector('.coords').textContent = `${Math.abs(s.lat).toFixed(4)}°${s.lat >= 0 ? 'N' : 'S'}, ${Math.abs(s.lon).toFixed(4)}°${s.lon >= 0 ? 'E' : 'W'}${q}`;
    const m = core.metrics(s);
    el.querySelector('.v-stats').textContent =
      `${t('sunFrac')} ${pct(m.sun_frac)} · ${t('earthFrac')} ${pct(m.earth_frac)} · ${t('bothFrac')} ${pct(m.both_frac)} · ${t('longestDark')} ${fmtHours(m.longest_dark_h)}`;
  }
  applyI18n();
}

function setDur(node, h) {
  const txt = fmtHours(h);
  node.classList.toggle('na', txt === null);
  node.textContent = txt ?? t('notInWindow');
}

function render() {
  const date = core.hourToDate(now);
  $('#time-label').textContent = fmtDate(date);
  for (const s of core.state.sites) {
    const el = document.querySelector(`.card[data-id="${s.id}"]`);
    const sun = core.sunAzEl(s, now), earth = core.earthAzEl(s, now);
    const lit = core.sunlit(s, now), eUp = core.earthVisible(s, now);
    el.querySelector('.v-sunel').textContent = fmtDeg(sun.el);
    el.querySelector('.v-sunaz').textContent = `${t('az')} ${sun.az.toFixed(0)}°`;
    el.querySelector('.v-sunlbl').textContent = t(lit ? 'untilSunset' : 'untilSunrise');
    setDur(el.querySelector('.v-sunt'), lit ? core.untilSunset(s, now) : core.untilSunrise(s, now));
    el.querySelector('.v-earthlbl').textContent = t(eUp ? 'untilEarthset' : 'untilEarthrise');
    setDur(el.querySelector('.v-eartht'), eUp ? core.untilEarthset(s, now) : core.untilEarthrise(s, now));
    const sc = el.querySelector('.v-sunchip'), ec = el.querySelector('.v-earthchip');
    sc.textContent = (lit ? '☀ ' : '◐ ') + t(lit ? 'sunlit' : 'dark'); sc.className = 'chip v-sunchip ' + (lit ? 'on sun' : 'off');
    ec.textContent = (eUp ? '● ' : '○ ') + t(eUp ? 'earthUp' : 'earthDown'); ec.className = 'chip v-earthchip ' + (eUp ? 'on earth' : 'off');
    el.querySelector('.v-earthel').textContent = `${t('earthEl')} ${fmtDeg(earth.el)} · ${t('az')} ${earth.az.toFixed(0)}°`;
  }
  window.dispatchEvent(new CustomEvent('llsn:time', { detail: { i: now, date } }));
}

export function setTime(i) {
  const [a, b] = core.hourRange();
  now = Math.min(Math.max(i, a), b);
  $('#slider').value = now;
  render();
}

function setPlaying(on) {
  playing = on;
  $('#play').textContent = t(on ? 'pause' : 'play');
  $('#play').dataset.i18n = on ? 'pause' : 'play';
  clearInterval(timer);
  if (on) timer = setInterval(() => {
    const step = Number($('#speed').value);           // hours per frame
    const [a, b] = core.hourRange();
    setTime(now + step > b ? a : now + step);
  }, 100);
}

async function main() {
  $('#lang').addEventListener('click', () => { toggleLang(); renderStatic(); render(); });
  applyI18n();
  try {
    await core.loadData('data/');
  } catch (e) {
    $('#cards').innerHTML = `<p class="error">${t('error')}: ${e.message}</p>`;
    throw e;
  }
  document.body.classList.toggle('is-mock', core.state.mock);
  delete $('#time-label').dataset.i18n;
  $('#cards').innerHTML = core.state.sites.map(cardHTML).join('');
  const sl = $('#slider');
  sl.min = 0; sl.max = core.state.n - 1; sl.step = 0.25;
  sl.addEventListener('input', () => setTime(Number(sl.value)));
  $('#play').addEventListener('click', () => setPlaying(!playing));
  const t0 = params.get('t');                         // ?t=<hour index> or ISO date
  renderStatic();
  setTime(t0 ? (isNaN(t0) ? core.dateToHour(new Date(t0)) : Number(t0)) : 0);
  window.LLSN.now = () => now;
  window.LLSN.setTime = setTime;
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
