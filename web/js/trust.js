// trust.js — "Can I trust this?" pieces (design spec v65 §3.9 validation badge + popover, §5.3-6, §5.6).
// Numbers come only from web/data/validation.json (PGDA comparison) and web/data/hindcast.json (mission hindcast).
// Headline = Sun MAE with the default definition (mean visible disc fraction); alternative definitions only in details.
import { t, getLang } from './i18n.js';
import { addStrings, whenReady, LLSN } from './ui_shared.js';
import { popover } from './shell.js';
import { validation, hindcast } from './values.js';

addStrings({
  vBadge: 'Mean error {v} pp', vBadgeAria: 'Validation against NASA PGDA maps: mean absolute error {v} percentage points. Open details.',
  vpTitle: 'How close is this to NASA’s data?', vpLead: 'At {n} random points near the south pole (85–90°S) this tool’s 18.6-year averages ({w}) were compared with NASA’s PGDA average illumination and Earth-visibility maps.', vpAvg: 'Average difference · pp = percentage points', vpSun: 'Sunlit time', vpEarth: 'Earth visibility', vpSmall: 'Smaller numbers mean the two results agree more closely.',
  vTitle: 'Compared with NASA PGDA maps', vRef: 'Reference', vRefTxt: 'PGDA AVGVISIB 18.6-year average illumination and Earth-visibility maps (Mazarico et al. 2011, Icarus 211; 2016 update), 60 m south-polar grid.',
  vMethod: 'Method', vMethodTxt: 'Over the same 18.6 years ({w}) this tool’s average at each point is compared with the PGDA pixel.',
  vMetric: 'Metric', vMetricTxt: 'Sunlight MAE {s} pp (r {sr}) · Earth MAE {e} pp (r {er})',
  vScope: 'Scope', vScopeTxt: 'Mean over {n} random points at 85–90°S (seed {seed}). This is not the error of a particular landing site.',
  vSite: 'This site', vSiteTxt: 'ours {o} · PGDA {p} (±300 m range {a}–{b}), difference {d} pp',
  vSiteNone: 'No PGDA point comparison for this site (outside the south-polar map).', vSiteUser: 'Your own point — no PGDA point comparison.',
  vLinks: 'PGDA product 69 · Mazarico et al. 2011 · About → validation',
  vNotNasa: 'A comparison with public data — not a NASA approval or endorsement.',
  vAlt: 'Other definitions (details)', vAltRow: '{k}: MAE {m} pp, r {r}',
  alt_sun_mean_disc_fraction: 'Sun, mean disc fraction (headline)', alt_sun_any_part: 'Sun, any part of the disc', alt_sun_half_disc: 'Sun, ≥ half disc',
  alt_earth_centre: 'Earth, center above the horizon', alt_earth_any_part: 'Earth, any part of the disc (headline)',
  hcApollo: 'Sun elevation at landing: recorded {r}° · this tool {o}° (difference {d}°)',
  hcRobot: '{txt}', hcProxy: 'End of operations is only an approximate proxy for local sunset.', hcNoSrc: 'No public source for this event.',
  hcEphem: 'Ephemeris check: max difference {d}° over {n} samples', hcTitle: 'Mission hindcast',
}, {
  vBadge: '평균 오차 {v}%p', vBadgeAria: 'NASA PGDA 지도와 비교한 검증: 평균 절대 오차 {v}%p. 자세히 열기.',
  vpTitle: 'NASA 자료와 얼마나 가까운가요?', vpLead: '남극 근처(남위 85–90°) 무작위 {n}곳에서 이 도구의 18.6년 평균({w})을 NASA PGDA 평균 조명·지구 가시 지도와 비교했습니다.', vpAvg: '평균 차이 · pp = 퍼센트포인트', vpSun: '일조 시간', vpEarth: '지구 가시', vpSmall: '숫자가 작을수록 두 결과가 더 가깝습니다.',
  vTitle: 'NASA PGDA 지도와 비교', vRef: '기준 자료', vRefTxt: 'PGDA AVGVISIB 18.6년 평균 조명·지구 가시 지도(Mazarico et al. 2011, Icarus 211; 2016 갱신), 남극 60 m 격자.',
  vMethod: '방법', vMethodTxt: '같은 18.6년({w}) 동안 이 도구로 계산한 각 지점의 평균을 PGDA 픽셀과 비교.',
  vMetric: '지표', vMetricTxt: '일조 MAE {s}%p (r {sr}) · 지구 MAE {e}%p (r {er})',
  vScope: '범위', vScopeTxt: '남위 85–90° 무작위 {n}점(시드 {seed})의 평균. 특정 착륙지의 오차가 아닙니다.',
  vSite: '이 착륙지', vSiteTxt: '우리 {o} · PGDA {p} (±300 m 범위 {a}–{b}), 차이 {d}%p',
  vSiteNone: '이 착륙지는 PGDA 지점 비교 없음 (남극 정밀 지도 범위 밖).', vSiteUser: '사용자 지점 — PGDA 지점 비교 없음.',
  vLinks: 'PGDA 제품 69 · Mazarico et al. 2011 · About → 검증',
  vNotNasa: '공개 자료와 비교한 결과이며 NASA의 승인이나 보증이 아닙니다.',
  vAlt: '다른 정의 (자세히)', vAltRow: '{k}: MAE {m}%p, r {r}',
  alt_sun_mean_disc_fraction: '태양, 원반 평균 비율 (대표값)', alt_sun_any_part: '태양, 원반 일부라도', alt_sun_half_disc: '태양, 원반 절반 이상',
  alt_earth_centre: '지구, 중심이 지평선 위', alt_earth_any_part: '지구, 원반 일부라도 (대표값)',
  hcApollo: '착륙 순간 태양 고도: 기록 {r}° · 이 도구 {o}° (차 {d}°)',
  hcRobot: '{txt}', hcProxy: '운용 종료는 일몰의 대략적인 대리값일 뿐입니다.', hcNoSrc: '공개 출처 없음.',
  hcEphem: '천체력 확인: {n}개 표본에서 최대 차 {d}°', hcTitle: '실제 임무 되짚기',
});

const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fill = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k] ?? '');
const pp = x => (Math.round(x * 100) / 100).toFixed(2);
const pc = f => `${(f * 100).toFixed(1)}%`;
export const PGDA_URL = 'https://pgda.gsfc.nasa.gov/products/69';
export const PAPER_URL = 'https://doi.org/10.1016/j.icarus.2010.10.030';

/** Headline numbers (default definitions in validation.json). */
export async function headline() {
  const v = await validation(); if (!v) return null;
  return { v, sun: pp(v.sun.mae_pp), sunR: v.sun.r.toFixed(3), earth: pp(v.earth.mae_pp), earthR: v.earth.r.toFixed(3) };
}
/** PGDA point comparison for a catalogue site (validation.json named), or null. */
export async function namedFor(id) {
  const v = await validation(); return v?.named?.find(n => n.id === id) || null;
}
/** One line for "this site" (HTML-escaped text). */
export async function siteLine(site) {
  if (!site) return '';
  if (site.user) return esc(t('vSiteUser'));
  const n = await namedFor(site.id);
  if (!n) return esc(t('vSiteNone'));
  return esc(fill(t('vSiteTxt'), { o: pc(n.ours_sun), p: pc(n.pgda_sun), a: pc(n.pgda_sun_min300), b: pc(n.pgda_sun_max300),
    d: `${n.ours_sun >= n.pgda_sun ? '+' : '−'}${Math.abs((n.ours_sun - n.pgda_sun) * 100).toFixed(1)}` }));
}
/** Hindcast lines for a site (Apollo Sun elevation or robotic sunset), [] if none. */
export async function hindcastFor(id) {
  const h = await hindcast(); if (!h) return [];
  const out = [];
  const a = h.apollo_sun_elevation?.find(x => x.id === id);
  if (a) out.push({ kind: 'apollo', html: esc(fill(t('hcApollo'), { r: a.reported_sun_el_deg.toFixed(2), o: a.ours_sun_el_deg_catalogue_point.toFixed(2), d: a.difference_deg_catalogue.toFixed(2) })), src: a.reported_source, row: a });
  const r = h.robotic_sunset?.find(x => x.id === id);
  if (r) out.push({ kind: 'robot', html: r.difference_text ? `${esc(r.difference_text)} <span class="muted">— ${esc(t('hcProxy'))}</span>` : esc(t('hcNoSrc')), src: r.source_url, row: r });
  return out;
}

// ------------------------------------------------------------ tray badge + popover
let pop, badge;
async function mount() {
  const slot = document.getElementById('ls-valbadge'); if (!slot) return;
  const H = await headline(); if (!H) return;
  slot.innerHTML = `<button type="button" class="val-badge num" aria-expanded="false" aria-controls="val-pop"></button>`;
  badge = slot.firstElementChild;
  pop = document.createElement('div');
  pop.id = 'val-pop'; pop.className = 'ls-pop val-pop'; pop.hidden = true; pop.setAttribute('role', 'dialog');
  document.querySelector('.ls-screen').append(pop);
  popover(badge, pop);
  badge.addEventListener('click', () => { place(); render(); });
  window.addEventListener('resize', place);
  window.addEventListener('llsn:lang', () => { label(); render(); });
  window.addEventListener('llsn:focus', render);
  label(); render();
}
function label() {
  headline().then(H => { badge.textContent = fill(t('vBadge'), { v: H.sun }); badge.setAttribute('aria-label', fill(t('vBadgeAria'), { v: H.sun })); });
}
/** ≥ 1180 px: open to the left of the tray (over the 3D); narrower: below the badge. */
function place() {
  if (!pop || pop.hidden) return;
  const sc = document.querySelector('.ls-screen').getBoundingClientRect(), bd = badge.getBoundingClientRect();
  const w = Math.min(340, sc.width - 24), left = Math.max(12, Math.min(sc.width - w - 12, bd.right - sc.left - w));
  Object.assign(pop.style, { top: `${bd.bottom - sc.top + 8}px`, left: `${left}px`, right: 'auto', width: `${w}px`, maxHeight: `${Math.max(240, sc.height - (bd.bottom - sc.top) - 28)}px` });
}
async function render() {
  if (!pop) return;
  const H = await headline(); const v = H.v;
  const site = LLSN().state?.sites.find(s => s.id === LLSN().focus);
  const name = site ? (getLang() === 'ko' && site.name_ko ? site.name_ko : site.name) : '';
  pop.innerHTML = `<h3>${esc(t('vpTitle'))}</h3>
    <p class="vp-lead">${esc(fill(t('vpLead'), { n: v.n_points, w: v.window.replace('..', ' – ') }))}</p>
    <p class="vp-cap"><b>${esc(t('vpAvg').split(' · ')[0])}</b><span>${esc(t('vpAvg').split(' · ').slice(1).join(' · '))}</span></p>
    <div class="vp-rows">
      <div><svg class="vp-ic" viewBox="0 0 16 16" aria-hidden="true" style="color:var(--sun)"><circle cx="8" cy="8" r="2.6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M8 1.6v1.8M8 12.6v1.8M1.6 8h1.8M12.6 8h1.8M3.5 3.5l1.3 1.3M11.2 11.2l1.3 1.3M3.5 12.5l1.3-1.3M11.2 4.8l1.3-1.3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg><span>${esc(t('vpSun'))}</span><b class="num">${H.sun}<small> pp</small></b></div>
      <div><svg class="vp-ic" viewBox="0 0 16 16" aria-hidden="true" style="color:var(--earth)"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2 8h12M8 2c2.2 2 2.2 10 0 12M8 2c-2.2 2-2.2 10 0 12" fill="none" stroke="currentColor" stroke-width="1.3"/></svg><span>${esc(t('vpEarth'))}</span><b class="num">${H.earth}<small> pp</small></b></div>
    </div>
    <p class="vp-note">${esc(t('vpSmall'))}</p>
    <p class="vp-note">${esc(fill(t('vScopeTxt'), { n: v.n_points, seed: v.seed }))}</p>
    <p class="vp-note">r · ${esc(t('vpSun'))} ${H.sunR} · ${esc(t('vpEarth'))} ${H.earthR}</p>
    <div class="vp-site"><b>${esc(t('vSite'))}${name ? ` · ${esc(name)}` : ''}</b><span class="num">${await siteLine(site)}</span></div>
    <details><summary>${esc(t('vAlt'))}</summary><ul class="num">${Object.entries(v.alt_definitions || {}).map(([k, a]) =>
      `<li>${esc(fill(t('vAltRow'), { k: t('alt_' + k), m: pp(a.mae_pp), r: a.r.toFixed(3) }))}</li>`).join('')}</ul></details>
    <p class="vp-links"><a href="${PGDA_URL}" target="_blank" rel="noopener">PGDA</a> · <a href="${PAPER_URL}" target="_blank" rel="noopener">Mazarico et al. 2011</a> · <a href="#about-validation">About</a></p>
    <p class="vp-note">${esc(t('vNotNasa'))}</p>`;
  place();
}

whenReady(mount);
