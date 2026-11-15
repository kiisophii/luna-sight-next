// minimap_drag.js — the minimap can be moved inside the map area (Chaei's copy 15:35, item 5-3; written from the
// described behaviour). A 14 px grip on top starts the drag; the position is kept as a 0–1 fraction of the free
// travel inside the map area (between the left panel and the tray, 20 px margins, above the dock) in localStorage.
// Near a corner (12 px) it snaps there. Double-click or Home resets to the top-right. Arrow keys move 10 px
// (Shift: 40 px). The legend box, the 'Height ×3' note and the layer legend follow the minimap (5-4) and are
// placed under it — also while it is expanded, so the expanded box never covers them.
import { t } from './i18n.js';
import { addStrings, whenReady } from './ui_shared.js';

addStrings({ mmMove: 'Move minimap (arrow keys to move, double-click to reset)' }, { mmMove: '미니맵 옮기기 (방향키로 이동, 더블클릭하면 원래 자리)' });

const KEY = 'ls.minimapPos', CW = 128, CH = 164, DEF = { fx: 1, fy: 0 };
const still = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const desktop = () => window.innerWidth >= 1100;
let box, grip, pos = { ...DEF };

function load() { try { const p = JSON.parse(localStorage.getItem(KEY) || 'null'); if (p && isFinite(p.fx) && isFinite(p.fy)) pos = { fx: Math.min(1, Math.max(0, p.fx)), fy: Math.min(1, Math.max(0, p.fy)) }; } catch (e) { pos = { ...DEF }; } }
function save() { try { localStorage.setItem(KEY, JSON.stringify(pos)); } catch (e) { /* private mode: keep the default next time */ } }

/** Free area for the minimap in .ls-screen coordinates. */
function area() {
  const sc = document.querySelector('.ls-screen').getBoundingClientRect(), R = sel => document.querySelector(sel)?.getBoundingClientRect();
  const L = R('.ls-left'), T = R('.ls-tray'), D = R('.ls-toolbar');
  const l = (L ? L.right : sc.left) + 20 - sc.left, r = (T ? T.left : sc.right) - 20 - sc.left;
  const tp = 64, b = (D && D.height ? D.top - 8 : sc.bottom - 20) - sc.top;
  return { l, t: tp, r, b, sc };
}
function place(animate) {
  if (!box) return;
  if (innerWidth <= 899) {
    const open = box.classList.contains('open');
    Object.assign(box.style, {left:'',top:'',right:'',bottom:'',width:`${Math.min(open ? 580 : 222, innerWidth - 32)}px`,height:`${open ? 358 : 228}px`});
    for (const selector of ['#hud-1','#globe-stage .g3-dock','#map-legend']) { const e=document.querySelector(selector); if(e) for(const key of ['left','top','right','bottom']) e.style[key]=''; }
    return;
  }
  box.style.width = box.style.height = '';
  const follow = ['#hud-1', '#globe-stage .g3-dock', '#map-legend'].map(s => document.querySelector(s)).filter(Boolean);
  if (!desktop()) { for (const e of [box, ...follow]) { e.style.left = e.style.top = e.style.right = e.style.bottom = ''; } return; }
  const a = area(), open = box.classList.contains('open');
  const x = a.l + pos.fx * Math.max(0, a.r - a.l - CW), y = a.t + pos.fy * Math.max(0, a.b - a.t - CH);
  let w = CW, h = CH, bx = x, by = y;
  if (open) {                                     // grow away from the nearest edges, stay inside the map area
    w = Math.min(440, a.r - a.l); h = 240;
    bx = pos.fx > 0.5 ? x + CW - w : x; by = pos.fy > 0.5 ? y + CH - h : y;
    bx = Math.min(Math.max(a.l, bx), a.r - w); by = Math.min(Math.max(a.t, by), Math.max(a.t, a.b - h));
  }
  box.classList.toggle('mm-anim', !!animate && !still());
  Object.assign(box.style, { left: `${Math.round(bx)}px`, top: `${Math.round(by)}px`, right: 'auto', bottom: 'auto' });
  // followers: stacked under the box (above it when there is no room), aligned to the box side nearer the map edge
  const right = pos.fx > 0.5, total = follow.filter(e => !e.hidden && e.offsetParent !== null).reduce((s, e) => s + e.offsetHeight + 8, 0);
  const below = by + h + 8 + total <= a.b;
  let yy = below ? by + h + 8 : by - 8 - total;
  for (const e of follow) {
    if (e.hidden || e.offsetParent === null) { continue; }
    Object.assign(e.style, { top: `${Math.round(yy)}px`, bottom: 'auto', left: right ? 'auto' : `${Math.round(bx)}px`, right: right ? `${Math.round(a.sc.width - (bx + w))}px` : 'auto' });
    yy += e.offsetHeight + 8;
  }
}
function setFromPx(x, y) {
  const a = area(), fw = Math.max(1, a.r - a.l - CW), fh = Math.max(1, a.b - a.t - CH);
  pos = { fx: Math.min(1, Math.max(0, (x - a.l) / fw)), fy: Math.min(1, Math.max(0, (y - a.t) / fh)) };
}
function snap() {
  const a = area(), fw = Math.max(1, a.r - a.l - CW), fh = Math.max(1, a.b - a.t - CH);
  for (const k of ['fx', 'fy']) { const f = k === 'fx' ? fw : fh; if (pos[k] * f <= 12) pos[k] = 0; else if ((1 - pos[k]) * f <= 12) pos[k] = 1; }
}

function init() {
  box = document.getElementById('ls-minimap'); if (!box) return;
  grip = document.createElement('div');
  grip.className = 'mm-grip'; grip.setAttribute('role', 'button'); grip.tabIndex = 0; grip.innerHTML = '<i></i>';
  const label = () => { grip.setAttribute('aria-label', t('mmMove')); grip.title = t('mmMove'); };
  label(); window.addEventListener('llsn:lang', label);
  box.prepend(grip);
  load();
  let d = null;
  grip.addEventListener('pointerdown', e => {
    if (!desktop() || e.button > 0 || box.classList.contains('open')) return;
    const r = box.getBoundingClientRect(), sc = area().sc;
    d = { dx: e.clientX - r.left, dy: e.clientY - r.top, sc }; grip.setPointerCapture(e.pointerId); box.classList.add('dragging'); box.classList.remove('mm-anim'); e.preventDefault();
  });
  grip.addEventListener('pointermove', e => { if (!d) return; setFromPx(e.clientX - d.dx - d.sc.left, e.clientY - d.dy - d.sc.top); place(false); });
  const end = () => { if (!d) return; d = null; box.classList.remove('dragging'); snap(); save(); place(true); };
  grip.addEventListener('pointerup', end); grip.addEventListener('pointercancel', end);
  const reset = () => { pos = { ...DEF }; save(); place(true); };
  grip.addEventListener('dblclick', reset);
  grip.addEventListener('keydown', e => {
    const m = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (e.key === 'Home') { e.preventDefault(); reset(); return; }
    if (!m || !desktop()) return;
    e.preventDefault();
    const a = area(), st = e.shiftKey ? 40 : 10, r = box.getBoundingClientRect();
    setFromPx(r.left - a.sc.left + m[0] * st, r.top - a.sc.top + m[1] * st); save(); place(false);
  });
  new MutationObserver(() => place(false)).observe(box, { attributes: true, attributeFilter: ['class'] });
  const later = () => requestAnimationFrame(() => place(false));
  window.addEventListener('resize', later);
  ['llsn:ready', 'llsn:lang', 'llsn:pins', 'llsn:globe'].forEach(ev => window.addEventListener(ev, later));
  for (const s of ['.ls-toolbar', '#map-legend', '#hud-1', '.ls-left', '.ls-tray']) { const e = document.querySelector(s); if (e) new ResizeObserver(later).observe(e); }
  new MutationObserver(later).observe(document.getElementById('map-legend'), { attributes: true, childList: true });
  place(false);
  setTimeout(() => place(false), 600);
}
whenReady(init);
