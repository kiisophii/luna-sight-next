// Comparison tray: approved four-category reference, using production visibility bits,
// relay interval masks and terrain horizon profiles. No scientific definitions changed.
import { t, getLang } from './i18n.js';
import { addStrings, whenReady, fmtHours, LLSN } from './ui_shared.js';
import { hourBits, gapStats, relayPeriod } from './values.js';
import { iconSvg } from './icons.js';
import { relayFor } from './diff_data.js';
import { cumulative, relayMasks, horizonPoints } from './tray_series.js';

const trayStyle = document.createElement('link');
trayStyle.rel = 'stylesheet';
trayStyle.href = new URL('../css/tray_reference.css', import.meta.url).href;
document.head.append(trayStyle);

addStrings({teBoth:'With the Sun',tdBoth:'How the share of time with both the Sun and Earth in view builds up.',trAdded:'Gaps filled',trCurve:'Earth view via tower',tdAdded:'Hours added through the tower, as a running share of the selected period.',tdCurve:'Direct Earth view plus the hours added through the tower, as a running share.',tdProfile:'Which directions block the Sun and Earth. The higher the line, the more sky the terrain hides there.',tProfile:'Horizon profile',tDistance:'Tower distance'},
 {teBoth:'태양과 함께',tdBoth:'태양과 지구가 함께 보이는 시간 비율이 어떻게 쌓이는지 봅니다.',trAdded:'메운 빈틈',trCurve:'탑 경유 지구 가시',tdAdded:'탑으로 추가되는 시간을 고른 기간의 누적 비율로 봅니다.',tdCurve:'직접 지구 가시에 탑으로 추가되는 시간을 더한 누적 비율입니다.',tdProfile:'어느 방향에서 지형이 태양과 지구를 가리는지 봅니다. 선이 높을수록 그 방향의 하늘을 더 많이 가립니다.',tProfile:'지평선 윤곽',tDistance:'중계탑 거리'});

addStrings({
  tcRelayTab: 'Relay', tcSun: 'Sunlight', tcEarth: 'Earth view', tcRelay: 'Relay', tcTerrain: 'Terrain',
  tsRate: 'Sunlit time', tsDark: 'Longest dark', teRate: 'Earth view', teGap: 'Longest Earth gap', trMix: 'Earth view + tower', trGap: 'Longest gap',
  ttSlope: 'Slope', ttHz: 'Horizon',
  tdSunRate: 'How the sunlit share builds up over the analysis period.',
  tdSunDark: 'Longest continuous stretch without sunlight in the period.',
  tdEarthRate: 'How the share of hours with the Earth in view builds up over the period.',
  tdEarthGap: 'Longest continuous stretch with the Earth below the terrain horizon.',
  tdRelayMix: 'Direct-to-Earth plus the hours a 15 m relay tower bridges (geometric line of sight).',
  tdRelayGap: 'Longest stretch with no Earth view, even via the tower.',
  tdSlope: 'Slope at the site and the share of ground at most 8° / 15° within 500 m (reference values, not landing criteria).',
  tdHz: 'Highest terrain horizon around the site, any direction (from the site’s LOLA horizon).',
  tiSun: 'Sunlit = at least half of the solar disc above the local terrain horizon (hourly, this period).',
  tiEarth: 'Earth in view = Earth centre above the local terrain horizon (direct-to-Earth geometry, hourly).',
  tiRelay: 'Assumed relay towers 15 m tall from data/relay; geometric line of sight only, no radio budget.',
  tiTerrain: 'Terrain horizon elevation by azimuth, from the site’s production horizon mask. North is 0°, east 90°. This is not a landing-safety assessment.',
  tRelayAll: 'No tower needed: the Earth is in view the whole period', tRelayNone: 'No tower data for this site', tRelayFar: 'No direct-to-Earth here; a tower near the site does not help',
  tDirect: 'direct', tVia: 'via tower', tFine: 'detailed', tCoarse: 'coarse 250 m', tFlat: '≤ 8° / ≤ 15° within 500 m', tRough: 'roughness (median, 500 m)', tRef: 'reference',
  tNoTerrain: 'No terrain file', tHzMax: 'max horizon', tLoading: 'loading…',
}, {
  tcRelayTab: '중계탑', tcSun: '일조', tcEarth: '지구 가시', tcRelay: '중계탑', tcTerrain: '지형',
  tsRate: '일조율', tsDark: '최장 어둠', teRate: '지구 가시율', teGap: '최장 지구 안 보임', trMix: '탑 포함 가시율', trGap: '최장 끊김',
  ttSlope: '경사', ttHz: '지평선',
  tdSunRate: '분석 기간 동안 일조율이 시간에 따라 어떻게 쌓이는지 봅니다.',
  tdSunDark: '기간 중 햇빛이 없는 가장 긴 연속 시간입니다.',
  tdEarthRate: '분석 기간 동안 지구가 보이는 시간 비율이 어떻게 쌓이는지 봅니다.',
  tdEarthGap: '지구가 지형 지평선 아래에 있는 가장 긴 연속 시간입니다.',
  tdRelayMix: '직접 가시에 15 m 중계탑으로 이어지는 시간을 더한 비율입니다 (기하학적 가시선).',
  tdRelayGap: '탑이 있어도 지구가 안 보이는 가장 긴 시간입니다.',
  tdSlope: '착륙 지점 경사와 500 m 안에서 8° / 15° 이하인 땅의 비율입니다 (참고값, 착륙 기준 아님).',
  tdHz: '착륙지 주변 지형 지평선의 가장 높은 고도입니다 (모든 방향, LOLA 지평선).',
  tiSun: '햇빛 = 태양 원반의 절반 이상이 지형 지평선 위 (기간 중 1시간마다).',
  tiEarth: '지구 보임 = 지구 중심이 지형 지평선 위 (직접 교신 기하, 1시간마다).',
  tiRelay: 'data/relay의 15 m 중계탑을 가정합니다. 기하학적 가시선만 보며 전파 성능은 아닙니다.',
  tiTerrain: '착륙지의 실제 지평선 마스크에서 방향별 지형 고도각을 표시합니다. 북쪽 0°, 동쪽 90°이며 착륙 안전성 판정은 아닙니다.',
  tRelayAll: '탑 없이도 지구가 계속 보임', tRelayNone: '이 착륙지는 탑 자료 없음', tRelayFar: '이곳은 직접 교신이 없어 근처 탑으로도 이어지지 않음',
  tDirect: '직접', tVia: '탑 경유', tFine: '정밀', tCoarse: '거친 250 m', tFlat: '500 m 안 8° / 15° 이하', tRough: '거칠기 (중앙값, 500 m)', tRef: '참고값',
  tNoTerrain: '지형 파일 없음', tHzMax: '최고 지평선', tLoading: '불러오는 중…',
});

const CATS = {
  sun: { tab: 'tcSun', info: 'tiSun', subs: [['rate', 'tsRate', 'tdSunRate'], ['dark', 'tsDark', 'tdSunDark']], col: 'var(--sun)' },
  earth: { tab: 'tcEarth', info: 'tiEarth', subs: [['rate', 'teRate', 'tdEarthRate'], ['gap', 'teGap', 'tdEarthGap'], ['both', 'teBoth', 'tdBoth']], col: 'var(--earth)' },
  relay: { tab: 'tcRelay', info: 'tiRelay', subs: [['mix', 'trCurve', 'tdCurve'], ['added', 'trAdded', 'tdAdded']], col: 'var(--relay)' },
  terrain: { tab: 'tcTerrain', info: 'tiTerrain', subs: [['hz', 'ttHz', 'tdProfile']], col: 'var(--n-text)' },
};
let cat = 'sun', sub = { sun: 'rate', earth: 'rate', relay: 'mix', terrain: 'hz' }, seq = 0;
try { const s = JSON.parse(localStorage.getItem('ls.trayCat') || 'null'); if (s?.cat in CATS) { cat = s.cat; Object.assign(sub, s.sub || {}); } } catch (e) { /* ignore */ }
const save = () => { try { localStorage.setItem('ls.trayCat', JSON.stringify({ cat, sub })); } catch (e) { /* ignore */ } };

const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = f => (f == null || !isFinite(f) ? '—' : `${Math.round(f * 100)}`);
const nameOf = s => (getLang() === 'ko' && s.name_ko ? s.name_ko.replace(/^아르테미스 후보:\s*/, '').replace(/\s*\([^)]*\)\s*$/, '') : (s.short || s.name));
const p2 = n => String(n).padStart(2, '0');
const chip = n => `<span class="tc-chip num" style="--sc:var(--c${n})">${p2(n)}</span>`;
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const H0 = Date.UTC(2026, 0, 1), md = i => { const d = new Date(H0 + i * 3600e3); return getLang() === 'ko' ? `${p2(d.getUTCMonth() + 1)}.${p2(d.getUTCDate())}` : `${MON[d.getUTCMonth()]} ${d.getUTCDate()}`; };
const sites = () => {
  const L = LLSN(); const st = L.state?.sites || [];
  return (L.pins?.() || []).map(p => ({ s: st.find(x => x.id === (p.id || p)), n: p.n || L.pinNo?.(p.id || p) })).filter(x => x.s);
};

function chartSVG(series, n, i0) {
  const W = 301, H = 100, L = 26, R = 30, T = 8, B = 20, pw = W - L - R, ph = H - T - B;
  const X = k => L + (k / Math.max(1, n - 1)) * pw, Y = v => T + (1 - v / 100) * ph;
  let g = [0, 50, 100].map(v => `<line x1="${L}" x2="${L + pw}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--n-line)" ${v === 50 ? 'stroke-dasharray="2 3"' : ''}/><text x="${L - 5}" y="${Y(v) + 3}" text-anchor="end">${v}</text>`).join('');
  g += Array.from({ length: 5 }, (_, j) => { const k = Math.round((n - 1) * j / 4); return `<text x="${X(k)}" y="${H - 5}" text-anchor="${j === 0 ? 'start' : j === 4 ? 'end' : 'middle'}">${md(i0 + k)}</text>`; }).join('');
  // end labels: spread so they do not overlap
  const ends = series.map(s => ({ n: s.n, y: Y(s.pts[s.pts.length - 1][1]) })).sort((a, b) => a.y - b.y);
  for (let j = 1; j < ends.length; j++) if (ends[j].y - ends[j - 1].y < 10) ends[j].y = ends[j - 1].y + 10;
  g += series.map(s => `<polyline points="${s.pts.map(([k, v]) => `${X(k).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')}" fill="none" stroke="var(--c${s.n})" stroke-width="1.6" stroke-linejoin="round"/>`).join('');
  g += ends.map(e => `<text x="${L + pw + 4}" y="${e.y + 3}" fill="var(--c${e.n})" font-weight="600">${p2(e.n)}</text>`).join('');
  return `<svg class="tc-chart" viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
}
const bar = (f, col, n) => `<span class="tc-bar"><i style="width:${Math.max(0, Math.min(100, f * 100)).toFixed(1)}%;background:${col}"></i></span>`;
const row = (it, val, extra = '', col = 'var(--n-text)') => `<li class="tc-row"><svg class="tc-sw" viewBox="0 0 24 6" aria-hidden="true"><line x1="0" y1="3" x2="24" y2="3" stroke="var(--c${it.n})" stroke-width="2"/></svg>${chip(it.n)}<span class="tc-nm" title="${esc(it.s.name)}">${esc(nameOf(it.s))}</span>${extra}<span class="tc-val num" style="color:${col}">${val}</span></li>`;

async function render() {
  const root = document.getElementById('tray-cat'), W = LLSN().window; if (!root || !W) return;
  const my = ++seq, list = sites(), C = CATS[cat], sk = sub[cat], subDef = C.subs.find(x => x[0] === sk) || C.subs[0];
  root.dataset.category = cat;
  root.querySelectorAll('.tc-tabs button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.c === cat)));
  root.querySelector('.tc-h').innerHTML = `<h4>${esc(t(C.tab))}</h4><button type="button" class="tc-i" aria-label="${esc(t(C.info))}" title="${esc(t(C.info))}">${iconSvg('info')}</button>
    ${cat === 'terrain' ? '' : `<span class="tc-subs" role="group">${C.subs.map(([k, lab]) => `<button type="button" data-s="${k}" aria-pressed="${k === subDef[0]}">${esc(t(lab))}</button>`).join('')}</span>`}`;
  root.querySelector('.tc-desc').textContent = t(subDef[2]);
  const body = root.querySelector('.tc-body');
  if (!list.length) { body.innerHTML = ''; return; }
  const n = W.i1 - W.i0 + 1;
  let html = '';
  if (cat === 'sun' || cat === 'earth') {
    const m = subDef[0] === 'both' ? 3 : cat === 'sun' ? 1 : 2, col = C.col;
    const data = list.map(it => { const bits = hourBits(it.s, W.i0, W.i1); return { it, bits, cum: bits ? cumulative(bits, m) : null, gap: bits ? gapStats(bits, m).longest : null }; });
    if (subDef[0] === 'rate' || subDef[0] === 'both') {
      html = chartSVG(data.filter(d => d.cum).map(d => ({ n: d.it.n, pts: d.cum.pts })), n, W.i0)
        + `<ul class="tc-rows">${data.map(d => row(d.it, d.cum ? `${pct(d.cum.end)}<small>%</small>` : '—', '', col)).join('')}</ul>`;
    } else {
      const mx = Math.max(1, ...data.map(d => d.gap || 0));
      html = `<ul class="tc-rows bars">${data.map(d => row(d.it, d.gap == null ? '—' : esc(fmtHours(d.gap)), d.gap == null ? '' : bar(d.gap / mx, 'var(--n-mute)'))).join('')}</ul>`;
    }
  } else if (cat === 'relay') {
    const data = await Promise.all(list.map(async it => {
      const [r, rel] = await Promise.all([relayPeriod(it.s.id, W.i0, W.i1), relayFor(it.s.id).catch(() => null)]);
      const j = rel?.params.heights_m.findIndex(h => Number(h) === 15) ?? -1;
      const masks = j >= 0 ? relayMasks(rel.networks[j].timeline.segments, W.i0, W.i1) : null;
      const cum = masks ? cumulative(subDef[0] === 'added' ? masks.added : masks.total, 1) : null;
      return { it, r, cum };
    }));
    if (my !== seq) return;
    html = chartSVG(data.filter(d => d.cum).map(d => ({ n: d.it.n, pts: d.cum.pts })), n, W.i0)
      + `<ul class="tc-rows relay-rows">${data.map(({it,r,cum}) => {
        const note = r.state !== 'ok' ? t('tRelayNone') : r.distKm != null ? `${t('tDistance')} ${r.distKm.toFixed(1)} km` : r.direct === r.total ? t('tRelayAll') : t('tRelayFar');
        return row(it, cum ? `${pct(cum.end)}<small>%</small>` : '—', `<span class="tc-note">${esc(note)}</span>`, C.col);
      }).join('')}</ul>`;
  } else {
    const data = list.map(it => ({it, pts:horizonPoints(LLSN().state?.horizons?.get(it.s.id))}));
    const all = data.flatMap(d => d.pts.map(p => p[1]));
    const low = Math.min(0, Math.floor(Math.min(0, ...all) / 3) * 3), high = Math.max(6, Math.ceil(Math.max(0, ...all) / 3) * 3);
    const X = az => 18 + az / 360 * 277, Y = el => 8 + (high - el) / (high - low) * 72;
    const ticks = [low, (low + high) / 2, high];
    let g = ticks.map(v => `<line x1="18" x2="295" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--n-line)" stroke-dasharray="2 3"/><text x="14" y="${Y(v)+3}" text-anchor="end">${v}°</text>`).join('');
    g += [0,90,180,270,360].map((az,j) => `<text x="${X(az)}" y="98" text-anchor="${j===0?'start':j===4?'end':'middle'}">${['N','E','S','W','N'][j]} ${az}°</text>`).join('');
    g += data.map(({it,pts}) => `<polyline points="${pts.map(([az,el])=>`${X(az).toFixed(2)},${Y(el).toFixed(2)}`).join(' ')}" fill="none" stroke="var(--c${it.n})" stroke-width="1"/>`).join('');
    html = `<svg class="tc-chart tc-horizon" viewBox="0 0 301 104" role="img" aria-label="${esc(t('tProfile'))}">${g}</svg><ul class="tc-rows horizon-rows">${data.map(({it,pts})=>row(it,pts.length?esc(t('tProfile')):'—')).join('')}</ul>`;
  }
  if (my === seq) body.innerHTML = html;
}

function build() {
  document.getElementById('ls-tray')?.classList.add('tray-reference');
  const moreArrow = document.querySelector('#ls-tray .tray-more > span[aria-hidden="true"]');
  if (moreArrow) moreArrow.innerHTML = '<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 2v11m-4-4 4 4 4-4" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const host = document.getElementById('tray-cat'); if (!host) return;
  host.innerHTML = `<div class="tc-tabs" role="group">${Object.entries(CATS).map(([k, c]) => `<button type="button" data-c="${k}" aria-pressed="${k === cat}" style="--ul:${c.col}">${esc(t(k === 'relay' ? 'tcRelayTab' : c.tab))}</button>`).join('')}</div>
    <div class="tc-scroll"><div class="tc-h"></div><p class="tc-desc"></p><div class="tc-body"></div></div>`;
  // the middle part scrolls; fade its last 28 px only while more content is below
  const sc = host.querySelector('.tc-scroll');
  const fade = () => sc.classList.toggle('more', sc.scrollTop + sc.clientHeight < sc.scrollHeight - 2);
  sc.addEventListener('scroll', fade, { passive: true }); new ResizeObserver((f => { let q = 0; return () => { if (!q) q = requestAnimationFrame(() => { q = 0; f(); }); }; })(() => fade())).observe(sc); new MutationObserver(fade).observe(sc, { childList: true, subtree: true });
  host.addEventListener('click', e => {
    const c = e.target.closest('.tc-tabs button'); if (c) { cat = c.dataset.c; save(); render(); relabel(); return; }
    const s = e.target.closest('.tc-subs button'); if (s) { sub[cat] = s.dataset.s; save(); render(); }
  });
  const relabel = () => host.querySelectorAll('.tc-tabs button').forEach(b => { b.textContent = t(b.dataset.c === 'relay' ? 'tcRelayTab' : CATS[b.dataset.c].tab); b.title = t(CATS[b.dataset.c].tab); });
  ['llsn:pins', 'llsn:window', 'llsn:sites'].forEach(ev => window.addEventListener(ev, render));
  window.addEventListener('llsn:lang', () => { relabel(); render(); });
  render();
}
whenReady(build);
