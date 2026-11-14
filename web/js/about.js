// about.js — About view (#about, design spec v65 §6): how to use, definitions, validation, Korea links,
// sources (required by the rules), assumptions, team and SI (AI) use disclosure. Loaded on first visit to #about.
// Numbers: validation.json, hindcast.json (no other numbers on this page).
import { t, getLang } from './i18n.js';
import { addStrings, LLSN } from './ui_shared.js';
import { headline, PGDA_URL, PAPER_URL } from './trust.js';
import { hindcast, validation } from './values.js';
import { RULE } from './compare_view.js';

addStrings({
  abExplore: 'Explore the Moon', abKicker: 'Lunar Landing Site Navigator',
  abH1: 'Where can a lander see the Sun and the Earth?', abLead: 'Luna Sight compares lunar landing sites and dates side by side: sunlight for power, a direct line to Earth for the radio link, and how long the dark lasts — from NASA terrain and ephemeris data, hour by hour. A comparison tool, not a “best site” picker.',
  abArtCap: 'The Moon is drawn by this tool’s 3D view (NASA SVS CGI Moon Kit colour, LOLA terrain). Not to scale.',
  abWhy: 'Why the lunar south pole?', abW1: 'There is ice', abW1t: 'Crater floors that never see the Sun can keep water ice — a resource for future crews.',
  abW2: 'The Sun stays low', abW2t: 'Near the pole the Sun skims the horizon, so a few hundred metres of height or a ridge decide between light and long shadows.',
  abW3: 'The Earth hides', abW3t: 'Libration makes the Earth bob around the horizon, so the direct radio link comes and goes.',
  abHow: 'How to use', abH1s: 'Set the conditions', abH1t: '① Landing date and operating period; optional minimum sunlight / Earth link and maximum shadow.',
  abH2s: 'Compare sites', abH2t: '② Sort by one value and pin any number of sites; the tray and the section below compare them over the same period.',
  abH3s: 'Read the evidence', abH3t: '“Why this site ↓” opens the decision brief: horizon, date slip, nearby spots, relay tower, ground stations, validation.',
  abKeys: 'Detailed controls', abKeysT: 'Drag = move the 3D Moon · right-drag or Shift-drag = rotate/tilt · wheel or pinch = zoom (click the globe first) · scrubber: ←/→ = 1 hour, Shift = 1 day · Esc closes pop-ups · ⌖ in the toolbar places your own point · mini map accepts “−89.45, −136.2” or “89.45S 136.2W” · “Copy link” shares the exact view.',
  abDefs: 'How to read the numbers',
  df1: 'Sunlight', df1t: 'Share of hours in the period when at least half of the solar disc (radius 0.2666°) is above the local terrain horizon, seen from 2 m above the ground.',
  df2: 'Direct Earth link', df2t: 'Share of hours when the Earth’s centre is above the terrain horizon (conservative). Geometry only — not radio performance.',
  df3: 'Sun + Earth together', df3t: 'Sunlit and Earth in view at the same hour.', df4: 'Longest shadow', df4t: 'Longest continuous run of hours without sunlight inside the period.',
  df5: 'Margin', df5t: 'Body elevation minus the terrain horizon in that direction; positive = visible.',
  df6: 'Via relay tower', df6t: 'Hours when the lander sees a tower (line of sight, up to 3 towers within 10 km on slopes ≤ 15°) and the tower sees the Earth.',
  df7: 'Yeoju KDSA can receive', df7t: 'The site sees the Earth AND the Moon is at least 10° above the Korea Deep Space Antenna in Yeoju.',
  df8: 'Analysis period vs long-term', df8t: 'Period values (chip “this period”) come from the dates you chose. Long-term values (chip “long-term”) are 2026–2030 or 18.6-year averages. Do not mix them.',
  df9: 'Example verdict thresholds', df9t: 'Caution: longest shadow > {dark} h, direct link < {lo} %, or last among the compared sites. Strength: direct link ≥ {hi} % or first. These are published examples for discussion, not mission requirements. No hidden scores.',
  abVal: 'Can I trust these numbers?', abValLead: 'Average sunlight over 18.6 years at {n} random points (85–90°S) compared with NASA PGDA maps: mean absolute error',
  abVc1: 'Sunlight', abVc2: 'Earth visibility', abVc3: 'Named sites inside PGDA’s ±300 m range', abVc3t: '{a} of {b} catalogue sites (sunlight)',
  abEph: 'Ephemeris check against an independent run: max difference {d}° over {n} samples.',
  abHind: 'Mission hindcast', abNotNasa: 'Comparisons with public data — not a NASA approval or endorsement.',
  abKorea: 'Korea links', abK1: 'ShadowCam on Danuri', abK1t: 'A NASA camera on Korea’s Danuri orbiter images inside permanently shadowed craters (NASA / KARI / ASU). Links only — Danuri does not relay for landers.',
  abK2: 'Yeoju deep-space antenna', abK2t: 'KDSA (35 m): for every site the decision brief counts the hours when the site sees the Earth and the Moon is ≥ 10° above Yeoju. Coordinates: KARI kdsa01.tf via NASA NAIF.',
  abK3: 'KASA partner', abK3t: 'The Korea AeroSpace Administration is a 2026 Space Apps partner.', abKMore: 'Ground-station block →',
  abMore: 'Team, sources and AI use', abSrc: 'Data sources', abSrcLead: 'Every dataset and number on this site comes from these sources (full list with sizes and checks: data/DATASETS.md).',
  sName: 'Data', sOrg: 'From', sUse: 'Used for', sLic: 'Terms',
  abLim: 'Assumptions and limits', abLimT: 'Observer 2 m above the ground · hourly steps · no atmosphere / refraction · link = geometric visibility · tower heights 5/15/30/50 m, up to 3 towers · data window 2026-01-01 to 2030-12-31 UTC · your own points use coarser browser terrain (~948 m north of 75°S; PGDA terrain near the south pole) · slope not computed.',
  abTeam: 'Team and SI (AI) use', abTeamLead: 'Team Ginkgo Orbit, NASA Space Apps Challenge 2026 (Seoul).',
  abSI: 'All solution ideas and design decisions came from our six team members. SI tools (Claude Code with Claude Opus 5.5; OpenAI Codex) helped with code, data processing, documentation and verification. Every SI task is logged in docs/SI_USAGE.md. No AI-generated images or video are used; any added later must carry a visible “AI-generated” watermark.',
  abCTA: 'Find your own landing site', abCTAb: 'Find my landing site →',
}, {
  abExplore: '달 살펴보기', abKicker: 'Lunar Landing Site Navigator',
  abH1: '착륙선이 해와 지구를 볼 수 있는 곳은?', abLead: 'Luna Sight는 달 착륙지와 날짜를 나란히 비교합니다: 전력을 위한 햇빛, 지구와 직접 교신할 수 있는 시간, 어둠이 얼마나 오래 가는지 — NASA 지형·천체력 자료로 1시간 간격으로 계산합니다. "최고의 착륙지"를 고르는 도구가 아니라 비교 도구입니다.',
  abArtCap: '달은 이 도구의 3D 보기(NASA SVS CGI Moon Kit 색, LOLA 지형)로 그린 것. 실제 비율 아님.',
  abWhy: '왜 달 남극인가', abW1: '얼음이 있다', abW1t: '해가 들지 않는 분화구 바닥에 물 얼음이 남아 있을 수 있습니다 — 미래 탐사의 자원.',
  abW2: '해가 낮게 뜬다', abW2t: '극 근처에서는 해가 지평선을 스치듯 움직여서, 몇백 m의 높이나 능선 하나가 빛과 긴 그늘을 가릅니다.',
  abW3: '지구가 숨는다', abW3t: '칭동 때문에 지구가 지평선 근처에서 오르내려 직접 교신이 생겼다 끊겼다 합니다.',
  abHow: '사용법', abH1s: '조건 정하기', abH1t: '① 착륙 날짜와 운용 기간, 필요하면 최소 일조·교신과 최대 그늘.',
  abH2s: '후보 비교', abH2t: '② 한 가지 값으로 정렬하고 원하는 만큼 핀으로 고정 — 트레이와 아래 섹션이 같은 기간으로 비교합니다.',
  abH3s: '근거 보기', abH3t: '"이 후보 따져 보기 ↓"로 선택 근거를 엽니다: 지평선, 날짜 밀림, 주변 위치, 중계탑, 지상국, 검증.',
  abKeys: '자세한 조작법', abKeysT: '드래그 = 3D 달 이동 · 오른쪽 드래그 또는 Shift 드래그 = 회전·기울이기 · 휠/핀치 = 확대(먼저 지구본 클릭) · 스크러버: ←/→ = 1시간, Shift = 1일 · Esc = 팝업 닫기 · 도구 막대 ⌖ = 내 지점 찍기 · 미니맵 좌표 형식 "−89.45, −136.2" 또는 "89.45S 136.2W" · "링크 복사"로 지금 화면 공유.',
  abDefs: '숫자 읽는 법',
  df1: '일조율', df1t: '기간 중 태양 원반(반지름 0.2666°)의 절반 이상이 지형 지평선 위에 있는 시간 비율, 지면 2 m 높이 기준.',
  df2: '지구 직접 교신', df2t: '지구 중심이 지형 지평선 위에 있는 시간 비율(보수적). 기하만 — 전파 성능 아님.',
  df3: '해+지구 동시', df3t: '같은 시각에 햇빛도 있고 지구도 보임.', df4: '최장 그늘', df4t: '기간 안에서 햇빛 없이 이어진 가장 긴 시간.',
  df5: '여유각', df5t: '천체 고도 − 그 방향 지형 지평선 높이. 양수면 보임.',
  df6: '중계탑 경유', df6t: '착륙선이 탑을 보고(시선, 10 km 안 경사 15° 이하 자리에 최대 3기) 탑이 지구를 보는 시간.',
  df7: '여주 KDSA 수신 가능', df7t: '착륙지에서 지구가 보이고 여주 심우주 안테나에서 달이 10° 이상 떠 있는 시간.',
  df8: '분석 기간 vs 장기 평균', df8t: '기간 값(칩 "이 기간")은 고른 날짜의 값, 장기 값(칩 "장기 평균")은 2026–2030 또는 18.6년 평균. 섞지 않습니다.',
  df9: '예시 판정 기준값', df9t: '주의: 최장 그늘 > {dark}시간, 직접 교신 < {lo} %, 또는 비교 중 꼴찌. 강점: 직접 교신 ≥ {hi} % 또는 1위. 토론용으로 공개한 예시이며 임무 요구 조건이 아닙니다. 숨은 점수 없음.',
  abVal: '이 숫자 믿어도 되나', abValLead: '남위 85–90° 무작위 {n}점의 18.6년 평균 일조를 NASA PGDA 지도와 비교한 평균 절대 오차',
  abVc1: '일조', abVc2: '지구 가시', abVc3: 'PGDA ±300 m 범위 안에 든 이름 있는 착륙지', abVc3t: '카탈로그 {b}곳 중 {a}곳 (일조)',
  abEph: '독립 계산과 천체력 비교: {n}개 표본에서 최대 차 {d}°.',
  abHind: '실제 임무 되짚기', abNotNasa: '공개 자료와 비교한 결과이며 NASA의 승인이나 보증이 아닙니다.',
  abKorea: '한국과의 연결', abK1: '다누리의 ShadowCam', abK1t: '한국 다누리 궤도선에 실린 NASA 카메라가 영구음영 분화구 안을 찍습니다(NASA / KARI / ASU). 링크만 — 다누리는 착륙선을 중계하지 않습니다.',
  abK2: '여주 심우주 안테나', abK2t: 'KDSA(35 m): 선택 근거에서 착륙지가 지구를 보고 여주에서 달이 10° 이상인 시간을 셉니다. 좌표: KARI kdsa01.tf (NASA NAIF).',
  abK3: 'KASA 파트너', abK3t: '우주항공청(KASA)은 2026 Space Apps 파트너입니다.', abKMore: '지상국 블록 →',
  abMore: '만든 사람 · 데이터 출처 · AI 사용', abSrc: '데이터 출처', abSrcLead: '이 사이트의 모든 자료와 숫자는 아래 출처에서 왔습니다 (크기·확인 포함 전체 목록: data/DATASETS.md).',
  sName: '자료', sOrg: '기관', sUse: '쓴 곳', sLic: '조건',
  abLim: '가정과 한계', abLimT: '관측 높이 2 m · 1시간 간격 · 대기·굴절 없음 · 교신 = 기하학적 가시성 · 탑 높이 5/15/30/50 m, 최대 3기 · 자료 기간 2026-01-01 ~ 2030-12-31 UTC · 사용자 지점은 더 거친 브라우저 지형(남위 75° 북쪽 약 948 m, 남극 근처는 PGDA 지형) · 경사 미계산.',
  abTeam: '팀과 SI(AI) 사용', abTeamLead: 'Team Ginkgo Orbit, NASA Space Apps Challenge 2026 (서울).',
  abSI: '해결 아이디어와 설계 결정은 모두 6명 팀원이 냈습니다. SI 도구(Claude Code · Claude Opus 5.5, OpenAI Codex)는 코드, 자료 처리, 문서, 검증을 도왔습니다. 모든 SI 작업은 docs/SI_USAGE.md에 기록합니다. AI가 만든 그림·영상은 쓰지 않았고, 나중에 넣으면 눈에 보이는 "AI-generated" 표시를 붙입니다.',
  abCTA: '내 착륙지를 직접 찾아보세요', abCTAb: '내 착륙지 찾아보기 →',
});

const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fill = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k] ?? '');
const E = k => esc(t(k));

// [name, organisation, URL, terms, used for] — the same sources as data/DATASETS.md, shortened for reading
const SOURCES = [
  ['LOLA LDEM_16 / LDEM_64 global terrain, SLDEM2015 (LOLA + SELENE TC)', 'NASA LRO LOLA / PDS Geosciences', 'https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/', 'NASA PDS public archive', 'Terrain horizons, 3D Moon, whole-Moon 948 m maps'],
  ['PGDA LOLA south-polar DEMs 5–240 m', 'NASA GSFC PGDA (Barker et al. 2021, 2023)', 'https://pgda.gsfc.nasa.gov/products/90', 'NASA public distribution, attribution requested', 'South-polar horizons, local grids, relay towers'],
  ['PGDA average illumination / Earth visibility (AVGVISIB)', 'NASA GSFC PGDA (Mazarico et al. 2011)', 'https://pgda.gsfc.nasa.gov/products/69', 'NASA data, public domain', 'Validation'],
  ['NAIF kernels de440s.bsp, moon_pa_de421, moon_080317.tf, naif0012.tls', 'NASA JPL NAIF', 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/', 'JPL/NAIF distribution terms', 'Sun / Earth positions (ephemeris)'],
  ['JPL Horizons API', 'NASA JPL SSD', 'https://ssd.jpl.nasa.gov/api/horizons.api', 'JPL service terms', 'Ephemeris cross-check'],
  ['CGI Moon Kit colour map (LROC)', 'NASA SVS 4720', 'https://svs.gsfc.nasa.gov/4720', 'NASA media guidelines', '3D Moon colour, mini map'],
  ['Landing-site coordinates (NSSDCA, LROC posts, NASA data books, papers)', 'NASA NSSDCA / LROC (ASU) / NTRS', 'https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html', 'see each source (data/sites.json source_url)', 'Site catalogue'],
  ['KDSA station kernel kdsa01.tf', 'KARI via NASA NAIF', 'https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf', 'NASA NAIF public file (coordinates cited as published)', 'Yeoju ground-station hours'],
  ['DSN 810-005 module 301 (station coordinates)', 'NASA JPL DSN', 'https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf', 'NASA/JPL public document', 'Goldstone / Madrid / Canberra hours'],
  ['BEACON lunar relay concept', 'NASA Glenn (NTRS 20240014584)', 'https://ntrs.nasa.gov/citations/20240014584', 'NASA NTRS', 'Relay-tower concept (15 m boom)'],
  ['Apollo Lunar Surface Journal — Sun elevation at landing', 'NASA History (ALSJ)', 'https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html', 'public', 'Mission hindcast'],
  ['ShadowCam data archive (doi:10.17189/y89z-kt98)', 'NASA / KARI / ASU (NASA PDS)', 'https://pds.shadowcam.asu.edu/', 'PDS public archive; links and label metadata only (no images copied)', 'Korea links (About)'],
  ['Pretendard (UI font)', 'Kil Hyung-jin (orioncactus)', 'https://github.com/orioncactus/pretendard', 'SIL Open Font License 1.1', 'All UI text'],
  ['Oxanium (number font)', 'Severin Meyer / Google Fonts', 'https://fonts.google.com/specimen/Oxanium', 'SIL Open Font License 1.1', 'Measured numbers'],
  ['three.js 0.170', 'three.js authors', 'https://threejs.org/', 'MIT', '3D Moon rendering'],
];
const TEAM = [['Dongju Kim', 'team lead · validation'], ['Sua Kim', 'integrator · Korea links · custom points'], ['Minchul Kim', 'ephemeris · site catalogue'],
  ['Jiyong Sung', 'terrain · horizons · local grids'], ['Soyun Jeong', 'whole-Moon maps'], ['Chaei Oh', 'visual design']];

async function render() {
  const root = document.getElementById('view-about');
  const H = await headline(), v = await validation(), h = await hindcast();
  const inRange = v?.named ? v.named.filter(n => n.ours_sun >= n.pgda_sun_min300 && n.ours_sun <= n.pgda_sun_max300).length : null;
  const ap = h?.apollo_sun_elevation || [], rb = h?.robotic_sunset || [];
  root.innerHTML = `
  <div class="ab-hero">
    <div><div class="ab-kicker">${E('abKicker')}</div><h1 tabindex="-1">${E('abH1')}</h1><p>${E('abLead')}</p>
      <p style="margin-top:20px"><a class="ls-btn primary" href="#" data-explore style="height:40px;border-radius:999px;padding:0 1.4em">${E('abExplore')} →</a></p></div>
    <figure style="margin:0"><div class="ab-art"><canvas class="ab-moon" width="360" height="360" style="width:62%;aspect-ratio:1"></canvas>
      <svg viewBox="0 0 100 100" style="position:absolute;inset:0;width:100%;height:100%" aria-hidden="true"><path d="M70 6 C64 20 60 30 56 38" stroke="#fff" stroke-dasharray="2 2" fill="none" stroke-width=".5"/><g transform="translate(51 36) scale(.25)" fill="none" stroke="#fff" stroke-width="2"><path d="M10 4h14l3 10H7z M7 14h20v4H7z M9 18l-5 10M25 18l5 10M17 18v4"/></g></svg></div>
      <figcaption class="ls-caption"><span class="chip-st">${getLang() === 'ko' ? '그림' : 'Picture'}</span> ${E('abArtCap')}</figcaption></figure>
  </div>
  <section class="ab-sec" id="about-why"><h2>${E('abWhy')}</h2><div class="ab-cards">${[1, 2, 3].map(k => `<div class="ls-panel"><h3>${E('abW' + k)}</h3><p>${E('abW' + k + 't')}</p></div>`).join('')}</div></section>
  <section class="ab-sec" id="about-how"><h2>${E('abHow')}</h2><div><div class="ab-cards">${[1, 2, 3].map(k => `<div class="ls-panel"><h3><span class="circ">${k}</span> ${E('abH' + k + 's')}</h3><p>${E('abH' + k + 't')}</p></div>`).join('')}</div>
    <details><summary>${E('abKeys')}</summary><p class="muted">${E('abKeysT')}</p></details></div></section>
  <section class="ab-sec" id="about-defs"><h2>${E('abDefs')}</h2><dl class="defs">${[1, 2, 3, 4, 5, 6, 7, 8, 9].map(k => `<dt>${E('df' + k)}</dt><dd>${esc(fill(t('df' + k + 't'), { dark: RULE.darkH, lo: RULE.directLow * 100, hi: RULE.directHigh * 100 }))}</dd>`).join('')}</dl></section>
  <section class="ab-sec" id="about-validation"><h2>${E('abVal')}</h2><div>
    ${H ? `<p>${esc(fill(t('abValLead'), { n: v.n_points }))}</p><div class="ab-big" style="color:var(--sun)">${H.sun}<small style="font-size:.4em"> pp</small></div>
    <div class="ab-cards" style="margin-top:12px">
      <div class="ls-panel"><h3>${E('abVc1')}</h3><p class="num" style="font-size:18px;color:var(--sun)">MAE ${H.sun} pp · r ${H.sunR}</p></div>
      <div class="ls-panel"><h3>${E('abVc2')}</h3><p class="num" style="font-size:18px;color:var(--earth)">MAE ${H.earth} pp · r ${H.earthR}</p></div>
      <div class="ls-panel"><h3>${E('abVc3')}</h3><p class="num" style="font-size:18px">${esc(fill(t('abVc3t'), { a: inRange, b: v.named.length }))}</p></div></div>` : ''}
    ${h?.ephemeris_check ? `<p class="muted">${esc(fill(t('abEph'), { d: h.ephemeris_check.max_deg.toExponential(1), n: h.ephemeris_check.sample_hours }))}</p>` : ''}
    <h3 style="margin-top:20px">${E('abHind')}</h3>
    <table class="src-tbl"><thead><tr><th></th><th>UTC</th><th>ALSJ</th><th>Luna Sight</th><th>Δ</th></tr></thead><tbody>${ap.map(a => `<tr><td>${esc(a.mission)}</td><td class="num">${a.landing_utc.slice(0, 16).replace('T', ' ')}</td><td class="num">${a.reported_sun_el_deg.toFixed(2)}°</td><td class="num">${a.ours_sun_el_deg_catalogue_point.toFixed(2)}°</td><td class="num">${a.difference_deg_catalogue.toFixed(2)}°</td></tr>`).join('')}</tbody></table>
    <table class="src-tbl" style="margin-top:10px"><tbody>${rb.map(r => `<tr><td>${esc(r.mission)}</td><td>${r.difference_text ? esc(r.difference_text) : esc(t('hcNoSrc'))}${r.source_url ? ` · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">source</a>` : ''}</td></tr>`).join('')}</tbody></table>
    <p class="muted">${E('hcProxy')} · <a href="${PGDA_URL}" target="_blank" rel="noopener">PGDA</a> · <a href="${PAPER_URL}" target="_blank" rel="noopener">Mazarico et al. 2011</a> · ${E('abNotNasa')}</p></div></section>
  <section class="ab-sec" id="about-korea"><h2>${E('abKorea')}</h2><div><div class="ab-cards">${[1, 2, 3].map(k => `<div class="ls-panel"><h3>${E('abK' + k)}</h3><p>${E('abK' + k + 't')}</p></div>`).join('')}</div>
    <p><a href="#" data-gs>${E('abKMore')}</a></p></div></section>
  <section class="ab-sec" id="about-more"><h2>${E('abMore')}</h2><div>
    <details id="about-sources" open><summary>${E('abSrc')}</summary><p class="muted">${E('abSrcLead')}</p>
      <div style="overflow-x:auto"><table class="src-tbl"><thead><tr><th>${E('sName')}</th><th>${E('sOrg')}</th><th>${E('sLic')}</th><th>${E('sUse')}</th></tr></thead><tbody>${SOURCES.map(([n, o, u, l, us]) =>
        `<tr><td><a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)}</a></td><td>${esc(o)}</td><td>${esc(l)}</td><td>${esc(us)}</td></tr>`).join('')}</tbody></table></div></details>
    <details><summary>${E('abLim')}</summary><p class="muted">${E('abLimT')}</p></details>
    <details id="about-team"><summary>${E('abTeam')}</summary><p>${E('abTeamLead')}</p><ul>${TEAM.map(([n, r]) => `<li><b>${esc(n)}</b> — <span class="muted">${esc(r)}</span></li>`).join('')}</ul>
      <p>${E('abSI')}</p><p><a href="https://github.com/kiisophii/lunar-landing-site-navigator/blob/main/docs/SI_USAGE.md" target="_blank" rel="noopener">docs/SI_USAGE.md</a> · <a href="https://github.com/kiisophii/lunar-landing-site-navigator" target="_blank" rel="noopener">source (Apache-2.0)</a></p></details>
  </div></section>
  <section class="ab-sec"><h2>${E('abCTA')}</h2><div><a class="ls-btn primary" href="#" data-mine style="height:40px;border-radius:999px;padding:0 1.4em">${E('abCTAb')}</a></div></section>`;
  drawMoon(root.querySelector('.ab-moon'));
  root.querySelector('[data-explore]').addEventListener('click', e => { e.preventDefault(); leave(); });
  root.querySelector('[data-mine]').addEventListener('click', e => { e.preventDefault(); leave(); setTimeout(() => LLSN().openAdd?.('coord'), 100); });
  root.querySelector('[data-gs]').addEventListener('click', e => { e.preventDefault(); leave(); setTimeout(() => { document.querySelector('#ls-brief [data-open="gs"]')?.click(); }, 200); });
}
function leave() { history.pushState(null, '', location.pathname + location.search); window.dispatchEvent(new HashChangeEvent('hashchange')); }
/** The hero picture: the same colour map as the 3D view, orthographic, lit from the side. */
function drawMoon(cv) {
  const im = new Image();
  im.onload = () => {
    const IW = 512, IH = 256, c = document.createElement('canvas'); c.width = IW; c.height = IH;
    const g0 = c.getContext('2d'); g0.drawImage(im, 0, 0, IW, IH); const px = g0.getImageData(0, 0, IW, IH).data;
    const W = cv.width, R = W / 2, g = cv.getContext('2d'), out = g.createImageData(W, W), la = -0.5;
    for (let j = 0; j < W; j++) for (let i = 0; i < W; i++) {
      const x = (i + .5) / R - 1, y = 1 - (j + .5) / R, rr = x * x + y * y; if (rr > 1) continue;
      const z = Math.sqrt(1 - rr), lat = Math.asin(z * Math.sin(la) + y * Math.cos(la)), lon = Math.atan2(x, z * Math.cos(la) - y * Math.sin(la));
      const u = ((lon / (2 * Math.PI) + .5) % 1 + 1) % 1, v = .5 - lat / Math.PI, si = (Math.floor(v * IH) * IW + Math.floor(u * IW)) * 4, di = (j * W + i) * 4;
      const sh = Math.max(0.06, 0.15 + 0.85 * (0.75 * x + 0.35 * y + 0.55 * z));
      out.data[di] = px[si] * sh; out.data[di + 1] = px[si + 1] * sh; out.data[di + 2] = px[si + 2] * sh; out.data[di + 3] = 255;
    }
    g.putImageData(out, 0, 0);
  };
  im.src = 'data/globe/moon_color_2k.jpg';
}

window.addEventListener('llsn:lang', () => { if (document.body.classList.contains('on-about')) render(); });
render();
