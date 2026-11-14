// story_arc.js — the four-step story for the focused site over the analysis period:
//   1 the direct link fails → 2 orbiters are not enough → 3 a tower fixes it → 4 Korea's antenna also receives.
// Numbers come from the same files as relay_panel.js / korea_panel.js (no new computation, no flat-horizon results).
import * as core from './core.js';
import { t } from './i18n.js';
import { addStrings, whenReady, translate, siteName, getFocus, fmtHours, LLSN } from './ui_shared.js';
import { relayFor, segmentHours, danuriPeriod, stationHours } from './diff_data.js';

addStrings({
  saTitle: 'The communication story for this site', saAria: 'Communication story: direct link, orbiter, tower, Korea',
  sa1: '1 · Direct link to Earth', sa2: '2 · An orbiter overhead?', sa3: '3 · A relay tower', sa4: '4 · Korea receives too',
  sa1fail: 'Earth is hidden by terrain or libration for {x} of the period.', sa1ok: 'Earth is in view for the whole period — the direct link works here.',
  sa2txt: 'Danuri-like orbiter: at most {x} of the no-Earth hours (geometric upper bound, {w}).', sa2na: 'Not needed: no hours without Earth in the Danuri window.',
  sa3txt: 'With {n} tower(s) of {h} m: link {a} → {b} of the period.', sa3none: 'No buildable tower within 10 km improves this site at {h} m.',
  sa4txt: 'Yeoju (KDSA, 35 m) sees the Moon {x} of the period ({hrs}); the 3 NASA DSN 70 m sites together: {d}.',
  saPending: 'Terrain pending', saPendingTip: 'Real LOLA terrain for this site is still being computed; this step is shown only from real terrain.',
  saPeriod: 'Period', saChange: 'change in Analysis window ↓',
}, {
  saTitle: '이 착륙지의 통신 이야기', saAria: '통신 이야기: 직접 통신, 궤도선, 타워, 한국',
  sa1: '1 · 지구와 직접 통신', sa2: '2 · 궤도선이 있으면?', sa3: '3 · 중계 타워', sa4: '4 · 한국도 받는다',
  sa1fail: '기간의 {x} 동안 지형이나 칭동 때문에 지구가 가려진다.', sa1ok: '기간 내내 지구가 보인다 — 여기서는 직접 통신이 된다.',
  sa2txt: '다누리 같은 궤도선: 지구가 안 보이는 시간의 최대 {x} (기하학적 상한, {w}).', sa2na: '필요 없음: 다누리 기간에 지구가 안 보이는 시간이 없다.',
  sa3txt: '{h} m 타워 {n}기: 통신 {a} → {b} (기간 대비).', sa3none: '{h} m에서는 10 km 안에 세울 수 있는 타워로 개선되지 않는다.',
  sa4txt: '여주(KDSA, 35 m)는 기간의 {x} 동안 달을 본다 ({hrs}). NASA DSN 70 m 세 곳 합계: {d}.',
  saPending: '지형 대기 중', saPendingTip: '이 착륙지의 실제 LOLA 지형을 아직 계산 중이다. 이 단계는 실제 지형으로만 보여 준다.',
  saPeriod: '기간', saChange: '분석 기간에서 바꾸기 ↓',
});

let sec, seq = 0;
const pct = (x, d = 0) => `${(100 * x).toFixed(d)}%`;
const fill = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k]);
const isoDay = i => core.hourToDate(i).toISOString().slice(0, 10);
const pend = () => `<span class="tag warn" title="${t('saPendingTip')}">${t('saPending')}</span>`;

function build() {
  sec = document.getElementById('llsn-story');
  sec.dataset.i18nAria = 'saAria';
  sec.innerHTML = `<div class="panel-head"><h2><span data-i18n="saTitle"></span> — <span class="sa-site"></span></h2><a class="now-link" href="#llsn-window"><span data-i18n="saPeriod"></span> <span class="sa-period num"></span></a></div>
    <ol class="sa-steps">
      <li class="s1"><h3 data-i18n="sa1"></h3><p class="big num"></p><p class="txt"></p></li>
      <li class="s2"><h3 data-i18n="sa2"></h3><p class="big num"></p><p class="txt"></p></li>
      <li class="s3"><h3 data-i18n="sa3"></h3><p class="big num"></p><p class="txt"></p></li>
      <li class="s4"><h3 data-i18n="sa4"></h3><p class="big num"></p><p class="txt"></p></li>
    </ol>`;
  const st = document.createElement('style');
  st.dataset.owner = 'story_arc.js';
  st.textContent = `
    #llsn-story .sa-steps { list-style: none; padding: 0; margin: .4em 0 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--gap); }
    @media (max-width: 960px) { #llsn-story .sa-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 520px) { #llsn-story .sa-steps { grid-template-columns: 1fr; } }
    #llsn-story li { background: var(--surface-2); border-radius: var(--radius); padding: .7em .9em; border-top: 5px solid var(--off); position: relative; }
    #llsn-story li.s1 { border-top-color: var(--earth); } #llsn-story li.s2 { border-top-color: var(--warn); }
    #llsn-story li.s3 { border-top-color: var(--relay); } #llsn-story li.s4 { border-top-color: var(--earth); }
    #llsn-story h3 { margin: 0; font-size: .95rem; color: var(--muted); }
    #llsn-story .big { margin: .2em 0; font-size: var(--fs-big); font-weight: 700; line-height: 1.1; }
    #llsn-story .s1 .big { color: var(--earth); } #llsn-story .s2 .big { color: var(--warn); }
    #llsn-story .s3 .big { color: var(--relay); } #llsn-story .s4 .big { color: var(--earth); }
    #llsn-story .txt { margin: 0; font-size: .9rem; }
  `;
  document.head.appendChild(st);
  translate(sec);
}

async function render() {
  const my = ++seq;
  const w = LLSN().window, site = getFocus();
  const h = LLSN().relayHeight || 15;
  sec.querySelector('.sa-site').textContent = siteName(site);
  sec.querySelector('.sa-period').textContent = `${isoDay(w.i0)} → ${isoDay(w.i1)} · ${t('saChange')}`;
  const [rel, dn, st] = await Promise.all([relayFor(site.id).catch(() => null), danuriPeriod(site.id, w.i0, w.i1), stationHours(w.i0, w.i1)]);
  if (my !== seq) return;
  const put = (cls, big, txt) => { const li = sec.querySelector('.' + cls); li.querySelector('.big').innerHTML = big; li.querySelector('.txt').innerHTML = txt; };
  // 1 + 3 from the relay timeline (real terrain only)
  if (rel) {
    const j = rel.params.heights_m.findIndex(x => Number(x) === h);
    const net = rel.networks[j];
    const s = segmentHours(net.timeline.segments, w.i0, w.i1), T = s.total || 1;
    const d = s.direct / T, a = (s.direct + s.via) / T;
    put('s1', pct(d), d >= 0.999 ? t('sa1ok') : fill(t('sa1fail'), { x: pct(1 - d) }));
    put('s3', net.towers.length ? pct(a) : '—', net.towers.length
      ? fill(t('sa3txt'), { n: net.towers.length, h, a: pct(d), b: pct(a) })
      : (rel.lander.earth_frac >= 0.9999 ? t('sa3ok') : fill(t('sa3none'), { h })));
  } else {
    put('s1', pend(), t('saPendingTip')); put('s3', pend(), t('saPendingTip'));
  }
  // 2 Danuri
  if (!dn || dn.pending) put('s2', pend(), t('saPendingTip'));
  else if (dn.site.no_direct_hours <= 0) put('s2', '—', t('sa2na'));
  else put('s2', `≤ ${pct(dn.site.relay_upper_bound)}`, fill(t('sa2txt'), { x: pct(dn.site.relay_upper_bound, 1), w: `${dn.window[0].slice(0, 7)} → ${dn.window[1].slice(0, 7)}` }));
  // 4 Korea
  const H = st.hours || 1;
  put('s4', pct(st.byStation.KDSA / H), fill(t('sa4txt'), { x: pct(st.byStation.KDSA / H), hrs: fmtHours(st.byStation.KDSA), d: pct(st.anyDsn / H) }));
}

whenReady(() => {
  build();
  render();
  for (const ev of ['llsn:focus', 'llsn:window', 'llsn:relayheight']) window.addEventListener(ev, () => render());
  window.addEventListener('llsn:lang', () => { translate(sec); render(); });
});
