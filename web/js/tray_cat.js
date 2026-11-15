// tray_cat.js — the comparison tray's category view (Chaei's copy after 11:49): four category tabs
// Sunlight / Earth view / Relay tower / Terrain, each with two sub-views, a chart and one row per compared site.
// Every value comes from this build's data and core.js definitions:
//   Sunlight  : cumulative sunlit share (hour k: sunlit hours so far / hours so far; core.sunlit = >= half the disc)
//               and the longest continuous stretch without sunlight (gapStats on the same bits).
//   Earth view: the same for core.earthVisible (Earth centre above the terrain horizon).
//   Relay     : direct + via a 15 m tower over the period (data/relay, values.relayPeriod) and the longest stretch still
//               without any link.
//   Terrain   : data/terrain/<ID>.json (contract §23; 5 m polar detail for 16 southern sites, 250 m box slope for the
//               rest) and the highest terrain-horizon elevation (data/horizon mask). 8 / 15 deg are reference values only.
import { t, getLang } from './i18n.js';
import { addStrings, whenReady, fmtHours, LLSN } from './ui_shared.js';
import { hourBits, gapStats, relayPeriod, getJSON, TOWER_H } from './values.js';
import { relayFor, relayIndex } from './diff_data.js';
import * as core from './core.js';
import { iconSvg } from './icons.js';

addStrings({
  tcRelayTab: 'Relay', tcSun: 'Sunlight', tcEarth: 'Earth view', tcRelay: 'Relay', tcTerrain: 'Terrain',
  tsRate: 'Sunlit time', tsDark: 'Longest dark', teRate: 'Earth view', teGap: 'Longest Earth gap', trMix: 'Earth view + tower', trGap: 'Longest gap',
  ttSlope: 'Slope', ttHz: 'Horizon', ttProfile: 'Horizon profile', teBoth: 'With the Sun', trFill: 'Gaps filled',
  tdEarthBoth: 'How the share of hours with both the Sun and the Earth in view builds up over the period.',
  tdProfile: 'Which directions block the Sun and Earth. The higher the line, the more sky the terrain hides there.',
  tdRelayFill: 'Which Earth gaps the 15 m tower fills over the period (geometric line of sight).',
  kOn: 'Sun up', kOff: 'Dark', kLong: 'Longest dark', kEOn: 'Earth in view', kEOff: 'Hidden', kELong: 'Longest gap', kHidden: 'Hidden', kLongestGap: 'longest gap',
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
  tiTerrain: 'data/terrain: 16 southern sites from 5–20 m PGDA LOLA (detailed; the tag shows each site’s resolution), others only the 250 m box slope (coarse). 8° and 15° are reference values, not landing-safety criteria.',
  tRelayAll: 'No tower needed: the Earth is in view the whole period', tRelayNone: 'No tower data for this site', tRelayFar: 'No direct-to-Earth here; a tower near the site does not help',
  tDirect: 'direct', tVia: 'via tower', tFine: 'detailed', tCoarse: 'coarse 250 m', tFlat: '≤ 8° / ≤ 15° within 500 m', tRough: 'roughness (median, 500 m)', tRef: 'reference',
  tNoTerrain: 'No terrain file', tHzMax: 'max horizon', tLoading: 'loading…',
}, {
  tcRelayTab: '중계탑', tcSun: '일조', tcEarth: '지구 가시', tcRelay: '중계탑', tcTerrain: '지형',
  tsRate: '일조율', tsDark: '최장 어둠', teRate: '지구 가시율', teGap: '최장 지구 안 보임', trMix: '탑 포함 가시율', trGap: '최장 끊김',
  ttSlope: '경사', ttHz: '지평선', ttProfile: '지평선 단면', teBoth: '해와 함께', trFill: '메워진 끊김',
  tdEarthBoth: '분석 기간 동안 해와 지구가 함께 보이는 시간 비율이 어떻게 쌓이는지 봅니다.',
  tdProfile: '어느 방향의 지형이 해와 지구를 가리는지 봅니다. 선이 높을수록 그 방향 하늘이 더 많이 가려집니다.',
  tdRelayFill: '기간 중 15 m 중계탑이 메워 주는 지구 안 보임 구간입니다 (기하학적 가시선).',
  kOn: '해 보임', kOff: '어둠', kLong: '최장 어둠', kEOn: '지구 보임', kEOff: '안 보임', kELong: '최장 끊김', kHidden: '안 보임', kLongestGap: '최장 끊김',
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
  tiTerrain: 'data/terrain: 남쪽 16곳은 5–20 m PGDA LOLA 정밀값(꼬리표에 착륙지별 해상도 표시), 나머지는 250 m 범위 경사만 있는 거친 값입니다. 8°·15°는 참고값이며 착륙 안전 기준이 아닙니다.',
  tRelayAll: '탑 없이도 지구가 계속 보임', tRelayNone: '이 착륙지는 탑 자료 없음', tRelayFar: '이곳은 직접 교신이 없어 근처 탑으로도 이어지지 않음',
  tDirect: '직접', tVia: '탑 경유', tFine: '정밀', tCoarse: '거친 250 m', tFlat: '500 m 안 8° / 15° 이하', tRough: '거칠기 (중앙값, 500 m)', tRef: '참고값',
  tNoTerrain: '지형 파일 없음', tHzMax: '최고 지평선', tLoading: '불러오는 중…',
});

const CATS = {
  sun: { tab: 'tcSun', info: 'tiSun', subs: [['rate', 'tsRate', 'tdSunRate'], ['dark', 'tsDark', 'tdSunDark']], col: 'var(--sun)' },
  earth: { tab: 'tcEarth', info: 'tiEarth', subs: [['rate', 'teRate', 'tdEarthRate'], ['gap', 'teGap', 'tdEarthGap'], ['both', 'teBoth', 'tdEarthBoth']], col: 'var(--earth)' },
  relay: { tab: 'tcRelay', info: 'tiRelay', subs: [['mix', 'trMix', 'tdRelayMix'], ['gap', 'trFill', 'tdRelayFill']], col: 'var(--relay)' },
  terrain: { tab: 'tcTerrain', info: 'tiTerrain', subs: [['profile', 'ttProfile', 'tdProfile'], ['slope', 'ttSlope', 'tdSlope']], col: 'var(--n-text)' },
};
let cat = 'sun', sub = { sun: 'rate', earth: 'rate', relay: 'mix', terrain: 'profile' }, seq = 0;
try { const s = JSON.parse(localStorage.getItem('ls.trayCat') || 'null'); if (s?.cat in CATS) { cat = s.cat; Object.assign(sub, s.sub || {}); } } catch (e) { /* ignore */ }
const save = () => { try { localStorage.setItem('ls.trayCat', JSON.stringify({ cat, sub })); } catch (e) { /* ignore */ } };

const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = f => (f == null || !isFinite(f) ? '—' : `${Math.round(f * 100)}`);
const nameOf = s => (getLang() === 'ko' && s.name_ko ? s.name_ko.replace(/^아르테미스 후보:\s*/, '').replace(/\s*\([^)]*\)\s*$/, '') : (s.short || s.name));
const p2 = n => String(n).padStart(2, '0');
const chip = n => `<span class="tc-chip num${n > 3 ? ' muted' : ''}" style="--sc:${n > 3 ? '#4A4A50' : `var(--c${n})`}">${p2(n)}</span>`;
const lineAttr = n => (n > 3 ? `stroke="var(--c${n})" stroke-opacity=".55" stroke-dasharray="3 2"` : `stroke="var(--c${n})"`);
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const H0 = Date.UTC(2026, 0, 1), md = i => { const d = new Date(H0 + i * 3600e3); return getLang() === 'ko' ? `${p2(d.getUTCMonth() + 1)}.${p2(d.getUTCDate())}` : `${MON[d.getUTCMonth()]} ${d.getUTCDate()}`; };
const sites = () => {
  const L = LLSN(); const st = L.state?.sites || [];
  return (L.pins?.() || []).map(p => ({ s: st.find(x => x.id === (p.id || p)), n: p.n || L.pinNo?.(p.id || p) })).filter(x => x.s);
};

/** Cumulative share curve for one bit mask: points every `step` hours (k, %). The last point equals the period share. */
function cumulative(bits, m) {
  const n = bits.length, step = Math.max(1, Math.round(n / 160)), pts = []; let on = 0;
  for (let k = 0; k < n; k++) { if ((bits[k] & m) === m) on++; if (k % step === 0 || k === n - 1) pts.push([k, (on / (k + 1)) * 100]); }
  return { pts, end: on / n };
}

function chartSVG(series, n, i0) {
  const W = 301, H = 100, L = 26, R = 30, T = 8, B = 20, pw = W - L - R, ph = H - T - B;
  const X = k => L + (k / Math.max(1, n - 1)) * pw, Y = v => T + (1 - v / 100) * ph;
  let g = [0, 50, 100].map(v => `<line x1="${L}" x2="${L + pw}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--n-line)" ${v === 50 ? 'stroke-dasharray="2 3"' : ''}/><text x="${L - 5}" y="${Y(v) + 3}" text-anchor="end">${v}</text>`).join('');
  g += Array.from({ length: 5 }, (_, j) => { const k = Math.round((n - 1) * j / 4); return `<text x="${X(k)}" y="${H - 5}" text-anchor="${j === 0 ? 'start' : j === 4 ? 'end' : 'middle'}">${md(i0 + k)}</text>`; }).join('');
  // end labels: spread so they do not overlap
  const ends = series.map(s => ({ n: s.n, y: Y(s.pts[s.pts.length - 1][1]) })).sort((a, b) => a.y - b.y);
  for (let j = 1; j < ends.length; j++) if (ends[j].y - ends[j - 1].y < 10) ends[j].y = ends[j - 1].y + 10;
  g += series.map(s => `<polyline points="${s.pts.map(([k, v]) => `${X(k).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')}" fill="none" ${lineAttr(s.n)} stroke-width="1.6" stroke-linejoin="round"/>`).join('');
  g += ends.map(e => `<text x="${L + pw + 4}" y="${e.y + 3}" fill="var(--c${e.n})" font-weight="600">${p2(e.n)}</text>`).join('');
  return `<svg class="tc-chart" viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
}
const bar = (f, col, n) => `<span class="tc-bar"><i style="width:${Math.max(0, Math.min(100, f * 100)).toFixed(1)}%;background:${col}"></i></span>`;
const row = (it, val, extra = '', col = 'var(--n-text)') => `<li class="tc-row"><svg class="tc-sw" viewBox="0 0 24 6" aria-hidden="true"><line x1="0" y1="3" x2="24" y2="3" ${lineAttr(it.n)} stroke-width="2"/></svg>${chip(it.n)}<span class="tc-nm" title="${esc(it.s.name)}">${esc(nameOf(it.s))}</span>${extra}<span class="tc-val num" style="color:${col}">${val}</span></li>`;

/** Hourly relay codes over the window (data/relay 15 m network timeline; 2 = Earth reached through the tower). */
async function relayCodes(id, i0, i1) {
  const idx = await relayIndex(); if (!idx?.ids?.includes(id)) return null;
  const rel = await relayFor(id); const j = rel.params.heights_m.findIndex(h => Number(h) === TOWER_H); if (j < 0) return null;
  const out = new Int8Array(i1 - i0 + 1).fill(-1);
  for (const [st, len, code] of rel.networks[j].timeline.segments) { const lo = Math.max(st, i0), hi = Math.min(st + len, i1 + 1); for (let k = lo; k < hi; k++) out[k - i0] = code; }
  return out;
}
const HM = i => { const d = new Date(H0 + i * 3600e3); return `${p2(d.getUTCMonth() + 1)}.${p2(d.getUTCDate())} ${p2(d.getUTCHours())}:00 UTC`; };
/** Longest run of hours where test(k) is false: [start, end) or null. */
function longestOff(n, test) { let best = null, st = -1; for (let k = 0; k <= n; k++) { const off = k < n && !test(k); if (off && st < 0) st = k; else if (!off && st >= 0) { if (!best || k - st > best[1] - best[0]) best = [st, k]; st = -1; } } return best; }
/** One period strip: runs of states (cls by hour) drawn as rects, the longest gap outlined. */
function strip(n, stateOf, colours, longest) {
  const W = 301, H = 10; let g = `<rect width="${W}" height="${H}" rx="2" fill="#26262A"/>`, st = 0, cur = stateOf(0);
  for (let k = 1; k <= n; k++) { const v = k < n ? stateOf(k) : null; if (v !== cur) { if (colours[cur]) g += `<rect x="${(st / n * W).toFixed(1)}" width="${Math.max(.6, (k - st) / n * W).toFixed(1)}" height="${H}" fill="${colours[cur]}"/>`; st = k; cur = v; } }
  if (longest) g += `<rect x="${(longest[0] / n * W).toFixed(1)}" y=".5" width="${Math.max(1, (longest[1] - longest[0]) / n * W).toFixed(1)}" height="${H - 1}" fill="none" stroke="#EDEDED" stroke-width="1"/>`;
  return `<svg class="tc-strip" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><defs><pattern id="tc-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="2" height="4" fill="#3CC6A0"/></pattern></defs>${g}</svg>`;
}
const stripAxis = (n, i0) => `<div class="tc-axis num">${Array.from({ length: 5 }, (_, j) => `<span>${md(i0 + Math.round((n - 1) * j / 4))}</span>`).join('')}</div>`;
const stripKey = items => `<div class="tc-key strip">${items.map(([c, l, outline]) => `<span><i style="${outline ? 'background:none;border:1px solid #EDEDED' : `background:${c}`}"></i>${esc(l)}</span>`).join('')}<span class="utc">UTC</span></div>`;
/** Horizon profile chart: terrain horizon elevation by azimuth for every compared site (data/horizon masks, 0.5 deg steps). */
function profileSVG(items) {
  const W = 301, H = 110, L = 26, R = 6, T = 8, B = 20, pw = W - L - R, ph = H - T - B;
  const top = Math.max(15, Math.ceil(Math.max(0, ...items.map(d => Math.max(...d.mask))) / 5) * 5);
  const X = a => L + (a / 360) * pw, Y = v => T + (1 - Math.max(0, Math.min(top, v)) / top) * ph;
  let g = [0, top / 2, top].map(v => `<line x1="${L}" x2="${L + pw}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--n-line)"/><text x="${L - 5}" y="${Y(v) + 3}" text-anchor="end">${Number.isInteger(v) ? v : v.toFixed(1)}°</text>`).join('');
  g += [['N 0°', 0], ['E 90°', 90], ['S 180°', 180], ['W 270°', 270], ['N 360°', 360]].map(([l, a], j) => `<text x="${X(a)}" y="${H - 5}" text-anchor="${j === 0 ? 'start' : j === 4 ? 'end' : 'middle'}">${l}</text>`).join('');
  g += items.map(d => { const step = 360 / d.mask.length, pts = []; for (let i = 0; i <= d.mask.length; i += 2) { const v = d.mask[i % d.mask.length]; pts.push(`${X(i * step).toFixed(1)},${Y(v).toFixed(1)}`); }
    return `<polyline points="${pts.join(' ')}" fill="none" ${lineAttr(d.n)} stroke-width="1.4" stroke-linejoin="round"/>`; }).join('');
  return `<svg class="tc-chart prof" viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
}

async function render() {
  const root = document.getElementById('tray-cat'), W = LLSN().window; if (!root || !W) return;
  const my = ++seq, list = sites(), C = CATS[cat], sk = sub[cat], subDef = C.subs.find(x => x[0] === sk) || C.subs[0];
  root.querySelectorAll('.tc-tabs button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.c === cat)));
  root.querySelector('.tc-h').classList.toggle('wide', C.subs.length > 2);
  root.querySelector('.tc-h').innerHTML = `<h4>${esc(t(C.tab))}</h4><button type="button" class="tc-i" aria-label="${esc(t(C.info))}" title="${esc(t(C.info))}">${iconSvg('info')}</button>
    <span class="tc-subs" role="group">${C.subs.map(([k, lab]) => `<button type="button" data-s="${k}" aria-pressed="${k === subDef[0]}">${esc(t(lab))}</button>`).join('')}</span>`;
  root.querySelector('.tc-desc').textContent = t(subDef[2]);
  const body = root.querySelector('.tc-body');
  if (!list.length) { body.innerHTML = ''; return; }
  const n = W.i1 - W.i0 + 1;
  let html = '';
  if (cat === 'sun' || cat === 'earth') {
    const m = cat === 'sun' ? 1 : subDef[0] === 'both' ? 3 : 2, col = C.col;
    const data = list.map(it => { const bits = hourBits(it.s, W.i0, W.i1); return { it, bits, cum: bits ? cumulative(bits, m) : null, gap: bits ? gapStats(bits, m).longest : null }; });
    if (subDef[0] === 'rate' || subDef[0] === 'both') {
      html = chartSVG(data.filter(d => d.cum).map(d => ({ n: d.it.n, pts: d.cum.pts })), n, W.i0)
        + `<ul class="tc-rows">${data.map(d => row(d.it, d.cum ? `${pct(d.cum.end)}<small>%</small>` : '—', '', col)).join('')}</ul>`;
    } else {
      const sun = cat === 'sun', onC = sun ? 'var(--sun)' : 'var(--earth)';
      html = stripKey([[onC, t(sun ? 'kOn' : 'kEOn')], ['#26262A', t(sun ? 'kOff' : 'kEOff')], ['', t(sun ? 'kLong' : 'kELong'), true]]) + stripAxis(n, W.i0)
        + `<ul class="tc-rows strips">${data.map(d => { if (!d.bits) return row(d.it, '—');
          const lg = longestOff(n, k => (d.bits[k] & m) === m);
          return row(d.it, d.gap == null ? '—' : esc(fmtHours(d.gap)), strip(n, k => ((d.bits[k] & m) === m ? 'on' : 'off'), { on: onC }, lg)
            + (lg ? `<span class="tc-sub2 num">${HM(W.i0 + lg[0])} — ${HM(W.i0 + lg[1])}</span>` : ''));
        }).join('')}</ul>`;
    }
  } else if (cat === 'relay') {
    const rs = await Promise.all(list.map(it => relayPeriod(it.s.id, W.i0, W.i1))); if (my !== seq) return;
    const met = list.map(it => W.metrics.get(it.s.id));
    const note = (r, m) => (!r || r.state !== 'ok' ? t('tRelayNone') : m && m.earth_frac >= 0.9999 ? t('tRelayAll') : r.direct === 0 && r.via === 0 ? t('tRelayFar') : '');
    const bitsL = list.map(it => hourBits(it.s, W.i0, W.i1)), codesL = await Promise.all(list.map(it => relayCodes(it.s.id, W.i0, W.i1).catch(() => null))); if (my !== seq) return;
    const linked = j => k => (bitsL[j] && (bitsL[j][k] & 2)) || (codesL[j] && codesL[j][k] === 2);
    if (subDef[0] === 'mix') {
      const series = list.map((it, j) => { if (!bitsL[j] || rs[j]?.state !== 'ok') return null; const f = linked(j), step = Math.max(1, Math.round(n / 160)), pts = []; let on = 0;
        for (let k = 0; k < n; k++) { if (f(k)) on++; if (k % step === 0 || k === n - 1) pts.push([k, (on / (k + 1)) * 100]); } return { n: it.n, pts }; }).filter(Boolean);
      html = (series.length ? chartSVG(series, n, W.i0) : '') + `<ul class="tc-rows bars">${list.map((it, j) => { const r = rs[j], x = note(r, met[j]);
        if (!r || r.state !== 'ok') return row(it, '—', `<span class="tc-note">${esc(x)}</span>`);
        const d = r.direct / r.total, v = r.via / r.total;
        return row(it, `${pct(d + v)}<small>%</small>`, `<span class="tc-bar" title="${esc(t('tDirect'))} ${pct(d)}% · ${esc(t('tVia'))} ${pct(v)}%"><i style="width:${(d * 100).toFixed(1)}%;background:var(--earth)"></i><i style="width:${(v * 100).toFixed(1)}%;background:var(--relay)"></i></span>${x ? `<span class="tc-note">${esc(x)}</span>` : ''}`, 'var(--relay)');
      }).join('')}</ul><div class="tc-key"><span><i style="background:var(--earth)"></i>${esc(t('tDirect'))}</span><span><i style="background:var(--relay)"></i>${esc(t('tVia'))} 15 m</span></div>`;
    } else {
      html = stripKey([['var(--earth)', t('tDirect')], ['url(#tc-hatch)', t('tVia')], ['#26262A', t('kHidden')]]).replace('background:url(#tc-hatch)', 'background:repeating-linear-gradient(45deg,#3CC6A0 0 2px,transparent 2px 4px)') + stripAxis(n, W.i0)
        + `<ul class="tc-rows strips">${list.map((it, j) => { const r = rs[j], x = note(r, met[j]);
        if (!r || r.state !== 'ok' || !bitsL[j]) return row(it, '—', `<span class="tc-note">${esc(x)}</span>`);
        const d = r.direct / r.total, v = r.via / r.total;
        const stOf = k => ((bitsL[j][k] & 2) ? 'd' : codesL[j] && codesL[j][k] === 2 ? 'v' : 'n');
        return row(it, `${pct(d + v)}<small>%</small>`, strip(n, stOf, { d: 'var(--earth)', v: 'url(#tc-hatch)' }, null)
          + `<span class="tc-sub2 num">${esc(t('kLongestGap'))} ${esc(fmtHours(r.longestNoneH || 0))}${x ? ` · ${esc(x)}` : ''}</span>`);
      }).join('')}</ul>`;
    }
  } else {
    if (subDef[0] === 'profile') {
      const items = list.map(it => ({ it, n: it.n, mask: LLSN().state?.horizons?.get(it.s.id)?.mask })).filter(d => d.mask?.length);
      html = (items.length ? profileSVG(items) : '') + `<ul class="tc-rows">${list.map(it => row(it, '', `<span class="tc-lbl">${esc(t('ttProfile'))}</span>`)).join('')}</ul>`;
    } else if (subDef[0] === 'slope') {
      const ts = await Promise.all(list.map(it => getJSON(`${core.state.base}terrain/${it.s.id}.json`).catch(() => null))); if (my !== seq) return;
      html = `<ul class="tc-rows terr">${list.map((it, j) => { const d = ts[j];
        if (!d) return row(it, '—', `<span class="tc-note">${esc(t('tNoTerrain'))}</span>`);
        if (d.kind === 'polar_detailed') {
          const r = d.slope_by_radius_m?.['500'], f = r?.flat_fraction || {}, rough = d.roughness_within_500m?.median_m;
          return row(it, `${d.landing_slope_deg.toFixed(1)}°`, `<span class="tc-tag fine">${esc(t('tFine'))} ${d.source?.resolution_m ?? '?'} m</span><span class="tc-sub2 num">${esc(t('tFlat'))}: ${pct(f['8'])}% / ${pct(f['15'])}% <em>${esc(t('tRef'))}</em> · ${esc(t('tRough'))} ${rough != null ? rough.toFixed(2) : '—'} m</span>`);
        }
        const s = d.relay_box?.slope_deg;
        return row(it, s != null ? `${Number(s).toFixed(1)}°` : '—', `<span class="tc-tag">${esc(t('tCoarse'))}</span>`);
      }).join('')}</ul>`;
    } else {
      const hz = list.map(it => LLSN().state?.horizons?.get(it.s.id)), vals = hz.map(h => (h?.mask?.length ? Math.max(...h.mask) : null));
      const mx = Math.max(1, ...vals.filter(v => v != null));
      html = `<ul class="tc-rows bars">${list.map((it, j) => row(it, vals[j] == null ? '—' : `${vals[j].toFixed(1)}°`, vals[j] == null ? '' : bar(Math.max(0, vals[j]) / mx, 'var(--n-mute)'))).join('')}</ul>`;
    }
  }
  if (my === seq) body.innerHTML = html;
}

function build() {
  const moreArrow = document.querySelector('#ls-tray .tray-more > span[aria-hidden="true"]');
  if (moreArrow) moreArrow.innerHTML = '<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 2v11m-4-4 4 4 4-4" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const host = document.getElementById('tray-cat'); if (!host) return;
  host.innerHTML = `<div class="tc-tabs" role="group">${Object.entries(CATS).map(([k, c]) => `<button type="button" data-c="${k}" aria-pressed="${k === cat}" style="--ul:${k === 'sun' ? 'var(--sun)' : k === 'earth' ? 'var(--earth)' : k === 'relay' ? 'var(--relay)' : 'var(--n-text)'}">${esc(t(k === 'relay' ? 'tcRelayTab' : c.tab))}</button>`).join('')}</div>
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
