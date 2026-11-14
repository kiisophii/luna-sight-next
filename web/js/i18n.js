// i18n.js — English default, Korean toggle. Add keys here; elements use data-i18n="key".
export const STR = {
  en: {
    title: 'Lunar Landing Site Navigator',
    tagline: 'Compare landing sites and dates: can a lander see the Sun (power) and the Earth (direct-to-Earth link)?',
    mock: 'MOCK DATA — placeholder files for building the interface. Do not quote these numbers.',
    play: 'Play', pause: 'Pause', speed: 'Speed', time: 'Time (UTC)',
    sunEl: 'Sun elevation', earthEl: 'Earth elevation',
    untilSunset: 'Until sunset', untilSunrise: 'Until sunrise',
    untilEarthset: 'Until Earthset', untilEarthrise: 'Until Earthrise',
    sunlit: 'Sunlit', dark: 'In shadow', earthUp: 'Earth visible', earthDown: 'Earth hidden',
    notInWindow: 'not within data window', az: 'az', sunFrac: 'Sunlight', earthFrac: 'Earth visible', bothFrac: 'Both',
    longestDark: 'Longest shadow', windowStats: 'Over the data window',
    assumptions: 'Assumptions: observer 2 m above terrain · no atmosphere (no refraction) · sunlit = ≥ 50% of the solar disk above the local horizon · Earth visible = Earth centre above the horizon · azimuth 0° = north, clockwise · times in UTC.',
    loading: 'Loading data…', error: 'Could not load data',
    lang: '한국어', h: 'h', d: 'd',
  },
  ko: {
    title: '달 착륙지 내비게이터',
    tagline: '착륙지와 날짜를 비교한다: 착륙선이 해(전력)와 지구(직접 통신)를 볼 수 있나?',
    mock: '가짜 데이터 — 화면을 만들기 위한 임시 파일이다. 이 숫자를 인용하지 말 것.',
    play: '재생', pause: '정지', speed: '속도', time: '시각 (UTC)',
    sunEl: '태양 고도', earthEl: '지구 고도',
    untilSunset: '해 지기까지', untilSunrise: '해 뜨기까지',
    untilEarthset: '지구 지기까지', untilEarthrise: '지구 뜨기까지',
    sunlit: '햇빛 받음', dark: '그늘', earthUp: '지구 보임', earthDown: '지구 안 보임',
    notInWindow: '데이터 기간 안에 없음', az: '방위', sunFrac: '햇빛', earthFrac: '지구 보임', bothFrac: '둘 다',
    longestDark: '가장 긴 그늘', windowStats: '데이터 기간 전체',
    assumptions: '가정: 관측자는 지면 위 2 m · 대기 없음(굴절 없음) · 햇빛 받음 = 태양 원반 50% 이상이 지평선 위 · 지구 보임 = 지구 중심이 지평선 위 · 방위 0° = 북쪽, 시계 방향 · 시각은 UTC.',
    loading: '데이터 불러오는 중…', error: '데이터를 불러오지 못함',
    lang: 'English', h: '시간', d: '일',
  },
};

let lang = 'en';
try { const q = new URLSearchParams(location.search).get('lang'); lang = q || localStorage.getItem('llsn.lang') || 'en'; } catch (e) { /* storage blocked */ }
if (!STR[lang]) lang = 'en';

export const getLang = () => lang;
export const t = key => STR[lang][key] ?? STR.en[key] ?? key;

export function applyI18n(root = document) {
  document.documentElement.lang = lang;
  root.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
}

export function toggleLang() {
  lang = lang === 'en' ? 'ko' : 'en';
  try { localStorage.setItem('llsn.lang', lang); } catch (e) { /* ignore */ }
  applyI18n();
  window.dispatchEvent(new CustomEvent('llsn:lang', { detail: { lang } }));
}
