// minimap.js — where the 3D view is looking (design spec v65 §3.8). A small orthographic Moon drawn from the same
// colour map as the 3D globe (NASA SVS CGI Moon Kit, data/globe/moon_color_2k.jpg); white ring = current view,
// labels = pinned sites. Hover / focus / tap opens: bigger ball (drag = rotate the minimap only), coordinate search,
// pinned / top-5 (current sort) / recent lists. Click on the ball = fly the 3D view there.
import { t, getLang } from './i18n.js';
import { addStrings, whenReady, setFocus, LLSN } from './ui_shared.js';

addStrings({
  mmAria: 'Mini map: where the 3D view is looking. Open for coordinate search.', mmSearch: 'Coordinates', mmPh: 'e.g. −89.45, −136.2 or 89.45S 136.2W',
  mmGo: 'Go', mmAnalyse: 'Analyse this point', mmBadLat: 'Latitude must be −90…90', mmBadLon: 'Longitude must be −180…180', mmBad: 'Use “lat, lon” or “89.45S 136.2W”',
  mmPinned: 'Pinned', mmTop: 'Top 5 (current sort)', mmRecent: 'Recently viewed', mmHere: 'Moved to {c}. Press “Analyse this point” to compute its terrain horizon.',
}, {
  mmAria: '미니맵: 3D가 보고 있는 곳. 열면 좌표 검색.', mmSearch: '좌표', mmPh: '예: −89.45, −136.2 또는 89.45S 136.2W',
  mmGo: '이동', mmAnalyse: '이 지점 분석', mmBadLat: '위도는 −90~90', mmBadLon: '경도는 −180~180', mmBad: '"위도, 경도" 또는 "89.45S 136.2W" 형식',
  mmPinned: '고정한 후보', mmTop: '대표 후보 (지금 정렬 상위 5)', mmRecent: '최근 방문', mmHere: '{c}(으)로 이동했습니다. "이 지점 분석"을 누르면 지형 지평선을 계산합니다.',
});

const D2R = Math.PI / 180, R2D = 180 / Math.PI;
const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fill = (s, o) => s.replace(/\{(\w+)\}/g, (_, k) => o[k] ?? '');
const nameOf = s => (getLang() === 'ko' && s.name_ko ? s.name_ko : s.name);
let box, cv, img = null, pix = null, IW = 0, IH = 0, view = { lat: 0, lon: 0, range: 6000 }, own = null, recent = [], closeT = 0, lastPick = null;

/** "lat, lon" | "89.45S 136.2W" | with ° → {lat, lon} or {err}. */
export function parseCoords(str) {
  const s = String(str).trim().replace(/[°º]/g, ' ').replace(/−/g, '-');
  let m = s.match(/^([+-]?\d+(?:\.\d+)?)\s*([NSns])?[\s,;]+([+-]?\d+(?:\.\d+)?)\s*([EWew])?$/);
  if (!m) return { err: 'mmBad' };
  let lat = Number(m[1]), lon = Number(m[3]);
  if (m[2] && /s/i.test(m[2])) lat = -Math.abs(lat);
  if (m[4] && /w/i.test(m[4])) lon = -Math.abs(lon);
  if (!(lat >= -90 && lat <= 90)) return { err: 'mmBadLat' };
  if (!(lon >= -180 && lon <= 180)) return { err: 'mmBadLon' };
  return { lat, lon };
}

function build() {
  box = document.getElementById('ls-minimap'); if (!box) return;
  box.tabIndex = 0;
  box.setAttribute('role', 'region');
  box.innerHTML = `<canvas class="mm-ball" style="display:block;margin:6px auto 0;cursor:pointer;touch-action:none"></canvas>
    <div class="mm-side" hidden style="position:absolute;top:10px;right:10px;width:205px;bottom:10px;display:flex;flex-direction:column;gap:6px;font-size:12px;overflow:auto">
      <label class="sr" for="mm-q"></label>
      <div style="display:flex;gap:4px"><input id="mm-q" type="search" style="flex:1;min-width:0;height:28px;font-size:11.5px"><button type="button" class="ls-btn mm-go" style="height:28px;padding:0 .6em"></button></div>
      <p class="mm-err" style="margin:0;color:var(--bad);font-size:11px" aria-live="polite"></p>
      <button type="button" class="ls-btn mm-an" hidden style="height:28px"></button>
      <div class="mm-lists"></div></div>`;
  cv = box.querySelector('canvas');
  const im = new Image();
  im.onload = () => {
    const c = document.createElement('canvas'); IW = 512; IH = 256; c.width = IW; c.height = IH;
    const g = c.getContext('2d'); g.drawImage(im, 0, 0, IW, IH); pix = g.getImageData(0, 0, IW, IH).data; img = im; draw();
  };
  im.src = `${LLSN().state.base}globe/moon_color_2k.jpg`;
  relabel();
  // open / close
  const openIt = () => { clearTimeout(closeT); if (!box.classList.contains('open')) { box.classList.add('open'); own = null; box.querySelector('.mm-side').hidden = false; sizeBall(); lists(); } };
  const closeSoon = () => { clearTimeout(closeT); closeT = setTimeout(() => { if (box.contains(document.activeElement)) return; box.classList.remove('open'); box.querySelector('.mm-side').hidden = true; own = null; sizeBall(); }, 300); };
  box.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') openIt(); });
  box.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') closeSoon(); });
  box.addEventListener('focusin', openIt);
  box.addEventListener('focusout', closeSoon);
  box.addEventListener('click', e => { if (!box.classList.contains('open')) openIt(); });
  document.addEventListener('pointerdown', e => { if (!box.contains(e.target) && box.classList.contains('open')) { box.classList.remove('open'); box.querySelector('.mm-side').hidden = true; own = null; sizeBall(); } });
  // drag rotates the minimap only; a click flies the 3D view there
  let drag = null;
  cv.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, moved: false, c: own || { lat: view.lat, lon: view.lon } }; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.hypot(dx, dy) > 3) drag.moved = true;
    if (drag.moved && box.classList.contains('open')) { own = { lat: Math.max(-89, Math.min(89, drag.c.lat + dy * 0.8)), lon: drag.c.lon - dx * 0.8 }; draw(); }
  });
  cv.addEventListener('pointerup', e => {
    if (drag && !drag.moved) { const ll = ballToLatLon(e); if (ll) fly(ll.lat, ll.lon); }
    drag = null;
  });
  const side = box.querySelector('.mm-side');
  side.querySelector('.mm-go').addEventListener('click', go);
  side.querySelector('#mm-q').addEventListener('keydown', e => { if (e.key === 'Enter') go(); if (e.key === 'Escape') box.blur(); });
  side.querySelector('.mm-an').addEventListener('click', () => { if (lastPick) LLSN().pickPoint?.(lastPick.lat, lastPick.lon, { compute: true }); side.querySelector('.mm-an').hidden = true; });
  side.addEventListener('click', e => { const b = e.target.closest('[data-site]'); if (b) setFocus(b.dataset.site); });
  window.addEventListener('llsn:lang', () => { relabel(); lists(); });
  window.addEventListener('llsn:pins', () => { draw(); lists(); });
  window.addEventListener('llsn:sort', lists);
  window.addEventListener('llsn:focus', e => { recent = [e.detail.id, ...recent.filter(x => x !== e.detail.id)].slice(0, 5); lists(); draw(); });
  sizeBall();
  setInterval(() => { const g = LLSN().globe; if (!g) return; const v = g.getView(); if (Math.abs(v.lat - view.lat) + Math.abs(v.lon - view.lon) + Math.abs(v.range - view.range) / 50 > 0.05) { view = v; draw(); } }, 400);
}
function relabel() {
  box.setAttribute('aria-label', t('mmAria'));
  const s = box.querySelector('.mm-side');
  s.querySelector('label').textContent = t('mmSearch');
  s.querySelector('#mm-q').placeholder = t('mmPh'); s.querySelector('#mm-q').setAttribute('aria-label', t('mmSearch'));
  s.querySelector('.mm-go').textContent = t('mmGo'); s.querySelector('.mm-an').textContent = t('mmAnalyse');
}
function sizeBall() {
  const open = box.classList.contains('open'), phone = window.matchMedia('(max-width: 899px)').matches;
  const d = open ? (phone ? 220 : 200) : (phone ? 86 : 114), dpr = Math.min(2, window.devicePixelRatio || 1);
  cv.width = d * dpr; cv.height = d * dpr; cv.style.width = cv.style.height = d + 'px';
  cv.style.margin = open ? '12px 0 0 12px' : '6px auto 0';
  draw();
}
function center() { return own || view; }
function ballToLatLon(e) {
  const r = cv.getBoundingClientRect(), x = ((e.clientX - r.left) / r.width) * 2 - 1, y = 1 - ((e.clientY - r.top) / r.height) * 2;
  const rr = x * x + y * y; if (rr > 1) return null;
  const z = Math.sqrt(1 - rr), c = center(), la = c.lat * D2R, lo = c.lon * D2R;
  // inverse orthographic
  const lat = Math.asin(z * Math.sin(la) + y * Math.cos(la)) * R2D;
  const lon = (lo + Math.atan2(x, z * Math.cos(la) - y * Math.sin(la))) * R2D;
  return { lat, lon: ((lon + 540) % 360) - 180 };
}
function project(lat, lon) {
  const c = center(), la = c.lat * D2R, lo = c.lon * D2R, p = lat * D2R, l = lon * D2R;
  const cosc = Math.sin(la) * Math.sin(p) + Math.cos(la) * Math.cos(p) * Math.cos(l - lo);
  return { x: Math.cos(p) * Math.sin(l - lo), y: Math.cos(la) * Math.sin(p) - Math.sin(la) * Math.cos(p) * Math.cos(l - lo), front: cosc > 0 };
}
function draw() {
  if (!cv) return;
  const W = cv.width, H = cv.height, g = cv.getContext('2d'), R = W / 2;
  g.clearRect(0, 0, W, H);
  if (pix) {
    const im = g.createImageData(W, H), c = center(), la = c.lat * D2R, lo = c.lon * D2R, sl = Math.sin(la), cl = Math.cos(la);
    for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
      const x = (i + 0.5) / R - 1, y = 1 - (j + 0.5) / R, rr = x * x + y * y; if (rr > 1) continue;
      const z = Math.sqrt(1 - rr), lat = Math.asin(z * sl + y * cl), lon = lo + Math.atan2(x, z * cl - y * sl);
      const u = ((lon / (2 * Math.PI) + 0.5) % 1 + 1) % 1, v = 0.5 - lat / Math.PI;
      const si = (Math.min(IH - 1, Math.floor(v * IH)) * IW + Math.min(IW - 1, Math.floor(u * IW))) * 4, di = (j * W + i) * 4;
      const sh = 0.55 + 0.45 * z;
      im.data[di] = pix[si] * sh; im.data[di + 1] = pix[si + 1] * sh; im.data[di + 2] = pix[si + 2] * sh; im.data[di + 3] = 255;
    }
    g.putImageData(im, 0, 0);
  } else { g.fillStyle = '#555'; g.beginPath(); g.arc(R, R, R, 0, 7); g.fill(); }
  const dpr = W / parseFloat(cv.style.width || W);
  // current 3D view: ring sized by the camera range (≈ half the visible width), centre dot
  const p = project(view.lat, view.lon);
  if (p.front) {
    const ang = Math.min(1.4, Math.atan2(view.range * Math.tan(22.5 * D2R), 1737.4));
    const rr = Math.max(3 * dpr, Math.sin(ang) * R);
    g.strokeStyle = '#fff'; g.lineWidth = 1.5 * dpr; g.beginPath(); g.ellipse(R + p.x * R, R - p.y * R, rr, rr * 0.8, 0, 0, 7); g.stroke();
  }
  // pinned sites
  g.font = `${10 * dpr}px Oxanium, monospace`; g.textBaseline = 'middle';
  for (const pn of LLSN().pins?.() || []) {
    const s = LLSN().state.sites.find(x => x.id === pn.id); if (!s) continue;
    const q = project(s.lat, s.lon); if (!q.front) continue;
    const x = R + q.x * R, y = R - q.y * R;
    g.fillStyle = '#fff'; g.beginPath(); g.arc(x, y, 2.4 * dpr, 0, 7); g.fill();
    g.lineWidth = 3 * dpr; g.strokeStyle = '#000'; g.strokeText(`#${pn.n}`, x + 4 * dpr, y); g.fillText(`#${pn.n}`, x + 4 * dpr, y);
  }
  const f = LLSN().state.sites.find(x => x.id === LLSN().focus);
  if (f) { const q = project(f.lat, f.lon); if (q.front) { g.strokeStyle = '#F5B841'; g.lineWidth = 1.5 * dpr; g.beginPath(); g.arc(R + q.x * R, R - q.y * R, 4 * dpr, 0, 7); g.stroke(); } }
}
function fly(lat, lon) {
  const g = LLSN().globe; if (!g) return;
  g.flyTo({ lat, lon, range: Math.min(view.range, 900), tilt: 30 });
}
function go() {
  const side = box.querySelector('.mm-side'), r = parseCoords(side.querySelector('#mm-q').value), err = side.querySelector('.mm-err');
  if (r.err) { err.textContent = t(r.err); return; }
  err.textContent = ''; fly(r.lat, r.lon); lastPick = r;
  LLSN().pickPoint?.(r.lat, r.lon, { compute: false });
  side.querySelector('.mm-an').hidden = false;
  err.style.color = 'var(--muted)'; err.textContent = fill(t('mmHere'), { c: `${r.lat.toFixed(4)}°, ${r.lon.toFixed(4)}°` });
  setTimeout(() => { err.style.color = ''; }, 0);
}
function lists() {
  const el = box?.querySelector('.mm-lists'); if (!el || !box.classList.contains('open')) return;
  const st = LLSN().state, row = (s, tag) => `<button type="button" class="ls-link" data-site="${s.id}" style="display:block;text-align:left;color:${s.id === LLSN().focus ? 'var(--sun)' : 'var(--text)'};text-decoration:none;padding:1px 0">⌖ ${tag ? `<span class="pin-no">${tag}</span>` : ''}${esc(nameOf(s))}</button>`;
  const pins = (LLSN().pins?.() || []).map(p => [st.sites.find(s => s.id === p.id), `#${p.n}`]).filter(x => x[0]);
  const top = (LLSN().sortedSites?.() || []).slice(0, 5);
  const rec = recent.map(id => st.sites.find(s => s.id === id)).filter(Boolean);
  el.innerHTML = `${pins.length ? `<p class="muted" style="margin:4px 0 2px">${esc(t('mmPinned'))}</p>${pins.map(([s, n]) => row(s, n)).join('')}` : ''}
    <p class="muted" style="margin:6px 0 2px">${esc(t('mmTop'))}</p>${top.map((s, k) => row(s, `${k + 1}.`)).join('')}
    ${rec.length ? `<p class="muted" style="margin:6px 0 2px">${esc(t('mmRecent'))}</p>${rec.map(s => row(s)).join('')}` : ''}`;
}

whenReady(build);
