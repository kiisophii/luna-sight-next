// Lower-page presentation only. Shared computations remain in core.js and values.js.
import { getLang } from './i18n.js';
const style = document.createElement('link');
style.rel = 'stylesheet';
style.href = new URL('../css/design_lower.css', import.meta.url).href;
document.head.append(style);
const rail = document.getElementById('ls-pages');
let collapseTimer;
function updateRailLabel() {
  const label = rail?.querySelector('[data-page="cmp"] > span > span');
  if (label) { label.removeAttribute('data-i18n'); label.textContent = getLang() === 'ko' ? '비교' : 'Compare'; }
}
function showRail() {
  rail?.classList.add('is-expanded');
  clearTimeout(collapseTimer);
  collapseTimer = setTimeout(() => rail?.classList.remove('is-expanded'), 1800);
}
window.addEventListener('scroll', showRail, { passive:true });
window.addEventListener('llsn:lang', updateRailLabel);
updateRailLabel();
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') document.querySelectorAll('.detail-tooltip').forEach(tip => { tip.hidden = true; });
});

// Leave ordinary wheel events to page scrolling, including when the globe has focus.
document.addEventListener('wheel', event => {
  const canvas = event.target.closest?.('.ls-globe canvas');
  if (!canvas) return;
  if (!event.ctrlKey) event.stopImmediatePropagation();
  else canvas.focus({ preventScroll: true });
}, { capture: true, passive: true });
document.addEventListener('pointerdown', event => {
  if (!event.target.closest('.detail-info')) document.querySelectorAll('.detail-tooltip').forEach(tip => { tip.hidden = true; });
});
