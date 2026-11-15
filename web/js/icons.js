// Luna Sight icon set by Chaei Oh (team Ginkgo Orbit designer), made during the contest (2026-11-14/15).
// Source: Chaei's design hand-off (01_아이콘: luna-sight-icons 39 + moon-focus/exit, relay-tower v2, site-marker,
// pin-add / pin-remove (+filled), minus, chevron-updown). Hand-drawn vector paths, no AI-generated art.
// Rules (from the set's README): 24 grid, stroke 1.5 (1.25 at <= 16 px), square caps, miter joins, color = currentColor.
// Usage: iconSvg('sun', { size: 14 }) -> '<svg class="ic ic-sun" ...>'. Static markup in index.html uses
// <svg data-icon="name"></svg>; hydrateIcons() fills those (called once from shell.js).
export const ICONS = {
  "sun": "<path d=\"M10.5 8H13.5L16 10.5V13.5L13.5 16H10.5L8 13.5V10.5Z\"></path><path d=\"M12 2.5V4.5M12 19.5V21.5M2.5 12H4.5M19.5 12H21.5M5.3 5.3L6.7 6.7M17.3 17.3L18.7 18.7M18.7 5.3L17.3 6.7M5.3 18.7L6.7 17.3\"></path>",
  "sun-average": "<path d=\"M7 13V11L9.5 8.5H14.5L17 11V13\"></path><path d=\"M12 3V5M4.8 5.8L6.2 7.2M19.2 5.8L17.8 7.2M3 11.5H4.5M19.5 11.5H21\"></path><path d=\"M3 16.5H21M6 20.5H18\"></path>",
  "earth": "<path d=\"M8 3H16L21 8V16L16 21H8L3 16V8Z\"></path><path d=\"M12 3L9 7V17L12 21M12 3L15 7V17L12 21M3 12H21\"></path>",
  "earth-visibility": "<path d=\"M2.5 12L7 6.5H17L21.5 12L17 17.5H7Z\"></path><path d=\"M11.0 9.5H13.0L14.5 11.0V13.0L13.0 14.5H11.0L9.5 13.0V11.0Z\"></path>",
  "elevation": "<path d=\"M2.5 19L8.5 8.5L12.5 15L15 11.5L21.5 19Z\"></path>",
  "detail-3d": "<path d=\"M12 3L20 7.5V16.5L12 21L4 16.5V7.5Z\"></path><path d=\"M4 7.5L12 12L20 7.5M12 12V21\"></path>",
  "moon": "<path d=\"M8 3H16L21 8V16L16 21H8L3 16V8Z\"></path><path d=\"M8.25 8H10.25L11.5 9.25V11.25L10.25 12.5H8.25L7 11.25V9.25Z\"></path><path d=\"M14 13.5H15.5L16.5 14.5V16L15.5 17H14L13 16V14.5Z\"></path><path d=\"M14.5 6.5H16\"></path>",
  "lander": "<path d=\"M9.0 5H15.0L16.5 6.5V11.0L15.0 12.5H9.0L7.5 11.0V6.5Z\"></path><path d=\"M12 5V2.5M7.5 12.5L5 19M16.5 12.5L19 19M3.5 19.5H6.5M17.5 19.5H20.5M10 12.5V15.5H14V12.5\"></path>",
  "relay-tower": "<path d=\"M12 8.5V13.5M7.5 21L12 13.5L16.5 21M6 21H18\"/><path d=\"M10.5 5.5H13.5V8.5H10.5Z\"/><path d=\"M8 4L6.5 7L8 10M16 4L17.5 7L16 10\"/><path d=\"M5 2.5L2.5 7L5 11.5M19 2.5L21.5 7L19 11.5\"/>",
  "link-off": "<path d=\"M9.5 7H6L3.5 9.5V14.5L6 17H9.5M14.5 7H18L20.5 9.5V14.5L18 17H14.5\"></path><path d=\"M12 3.5V5.5M12 18.5V20.5M8 12H9.5M14.5 12H16\"></path>",
  "shadow": "<path d=\"M3 19H21M4.5 19V7.5H9.5V19\"></path><path d=\"M12 19L14.5 16.5M15.5 19L18 16.5M19 19L21.5 16.5\"></path>",
  "slope": "<path d=\"M3 19L21 6.5V19Z\"></path><path d=\"M9.5 19V15.5\"></path>",
  "target": "<path d=\"M9.5 6H14.5L18 9.5V14.5L14.5 18H9.5L6 14.5V9.5Z\"></path><path d=\"M12 2.5V8.5M12 15.5V21.5M2.5 12H8.5M15.5 12H21.5\"></path><path d=\"M11.25 11.25H12.75V12.75H11.25Z\" fill=\"currentColor\"></path>",
  "layers": "<path d=\"M12 4L21 8.5L12 13L3 8.5Z\"></path><path d=\"M3 12.5L12 17L21 12.5M3 16.5L12 21L21 16.5\"></path>",
  "pin": "<path d=\"M12 21.5L6 15V7L9 4H15L18 7V15Z\"></path><path d=\"M10 8.5H14V12.5H10Z\"></path>",
  "pushpin": "<path d=\"M7.5 3.5H16.5M9.5 3.5V9.5L6.5 13.5H17.5L14.5 9.5V3.5M12 13.5V21\"></path>",
  "pushpin-filled": "<path d=\"M9.5 3.5V9.5L6.5 13.5H17.5L14.5 9.5V3.5Z\" fill=\"currentColor\"></path><path d=\"M7.5 3.5H16.5M12 13.5V21\"></path>",
  "star": "<path d=\"M12 3L14.5 8.6L20.6 9.2L16 13.3L17.3 19.3L12 16.2L6.7 19.3L8 13.3L3.4 9.2L9.5 8.6Z\"></path>",
  "marker-down": "<path d=\"M6 8H18L12 16.5Z\" fill=\"currentColor\"></path>",
  "table": "<path d=\"M5.0 4.5H19.0L20.5 6.0V18.0L19.0 19.5H5.0L3.5 18.0V6.0Z\"></path><path d=\"M3.5 9.5H20.5M3.5 14.5H20.5M9.5 9.5V19.5\"></path>",
  "lunar-clock": "<path d=\"M8 3H16L21 8V16L16 21H8L3 16V8Z\"></path><path d=\"M17 12V14.5L14.5 17H9.5L7 14.5V9.5L9.5 7H12\"></path><path d=\"M12 12L17.5 6.5\"></path>",
  "elevation-chart": "<path d=\"M4 3.5V20H20.5\"></path><path d=\"M7.5 16L11 10L14 13L19 6.5\"></path>",
  "calendar": "<path d=\"M5.0 5H19.0L20.5 6.5V19.0L19.0 20.5H5.0L3.5 19.0V6.5Z\"></path><path d=\"M3.5 10H20.5M8 3V7M16 3V7\"></path><path d=\"M14 14H16.5V16.5H14Z\" fill=\"currentColor\"></path>",
  "clock": "<path d=\"M8 3H16L21 8V16L16 21H8L3 16V8Z\"></path><path d=\"M12 7V12H16\"></path>",
  "play": "<path d=\"M7 4.5V19.5L19 12Z\" fill=\"currentColor\"></path>",
  "pause": "<path d=\"M8.5 5V19M15.5 5V19\"></path>",
  "speed": "<path d=\"M4 6L10.5 12L4 18Z\" fill=\"currentColor\"></path><path d=\"M12.5 6L19 12L12.5 18Z\" fill=\"currentColor\"></path>",
  "chevron-down": "<path d=\"M6 9L12 15L18 9\"></path>",
  "chevron-right": "<path d=\"M9 6L15 12L9 18\"></path>",
  "arrow-up-right": "<path d=\"M8 6H18V16M17.5 6.5L6 18\"></path>",
  "arrow-down": "<path d=\"M12 4V16M6.5 11L12 16.5L17.5 11M5 20.5H19\"></path>",
  "plus": "<path d=\"M12 4.5V19.5M4.5 12H19.5\"></path>",
  "close": "<path d=\"M5.5 5.5L18.5 18.5M18.5 5.5L5.5 18.5\"></path>",
  "check": "<path d=\"M4.5 12.5L9.5 17.5L19.5 7.5\"></path>",
  "info": "<path d=\"M8 3H16L21 8V16L16 21H8L3 16V8Z\"></path><path d=\"M12 10.5V16.5M12 7.25V7.75\"></path>",
  "search": "<path d=\"M7.0 3.5H12.0L15.5 7.0V12.0L12.0 15.5H7.0L3.5 12.0V7.0Z\"></path><path d=\"M15 15L20.5 20.5\"></path>",
  "language": "<path d=\"M4 4.5H20V16H10.5L6.5 19.5V16H4Z\"></path><path d=\"M8.5 13L12 7.5L15.5 13M9.8 11H14.2\"></path>",
  "sort": "<path d=\"M7 4V20M3.5 16.5L7 20L10.5 16.5M17 20V4M13.5 7.5L17 4L20.5 7.5\"></path>",
  "sliders": "<path d=\"M3.5 7H8M12 7H20.5M3.5 17H12M16 17H20.5\"></path><path d=\"M8 5H12V9H8Z\"></path><path d=\"M12 15H16V19H12Z\"></path>",
  "moon-focus": "<path d=\"M3 7V3H7M17 3H21V7M21 17V21H17M7 21H3V17\"></path><path d=\"M10.5 7.5H13.5L16.5 10.5V13.5L13.5 16.5H10.5L7.5 13.5V10.5Z\"></path>",
  "moon-focus-exit": "<path d=\"M3 6H6V3M18 3V6H21M21 18H18V21M6 21V18H3\"></path><path d=\"M10 6H14L18 10V14L14 18H10L6 14V10Z\"></path>",
  "site-marker": "<path d=\"M12 17.5L7.5 12V7L10 4.5H14L16.5 7V12Z\"/><path d=\"M10.75 7.5H13.25V10H10.75Z\" fill=\"currentColor\"/><path d=\"M6 20.5H9.5M14.5 20.5H18\"/>",
  "minus": "<path d=\"M5 12H19\"/>",
  "pin-add": "<path d=\"M6.5 3.5H17.5L20.5 6.5V17.5L17.5 20.5H6.5L3.5 17.5V6.5Z\"/><path d=\"M12 8V16M8 12H16\"/>",
  "pin-remove": "<path d=\"M6.5 3.5H17.5L20.5 6.5V17.5L17.5 20.5H6.5L3.5 17.5V6.5Z\"/><path d=\"M8 12H16\"/>",
  "chevron-updown": "<path d=\"M8 9.5L12 5.5L16 9.5M8 14.5L12 18.5L16 14.5\"/>",
  "pin-add-filled": "<path fill=\"currentColor\" stroke=\"none\" fill-rule=\"evenodd\" d=\"M6.5 3.5H17.5L20.5 6.5V17.5L17.5 20.5H6.5L3.5 17.5V6.5Z M11.25 7.5H12.75V11.25H16.5V12.75H12.75V16.5H11.25V12.75H7.5V11.25H11.25Z\"/>",
  "pin-remove-filled": "<path fill=\"currentColor\" stroke=\"none\" fill-rule=\"evenodd\" d=\"M6.5 3.5H17.5L20.5 6.5V17.5L17.5 20.5H6.5L3.5 17.5V6.5Z M7.5 11.25H16.5V12.75H7.5Z\"/>",
};

export function iconSvg(name, { size = 16, cls = 'ic', strokeWidth, label } = {}) {
  const inner = ICONS[name] || '';
  const sw = strokeWidth || (size <= 16 ? 1.25 : 1.5);
  const a11y = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true" focusable="false"';
  return `<svg class="${cls} ic-${name}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="square" stroke-linejoin="miter" ${a11y}>${inner}</svg>`;
}

/** Fill every <svg data-icon="name" [data-size="n"]> under root (static markup in index.html). Keeps the element's classes. */
export function hydrateIcons(root = document) {
  root.querySelectorAll('svg[data-icon]').forEach(el => {
    const name = el.dataset.icon, size = +(el.dataset.size || 16);
    if (el.dataset.iconDone === name) return;
    el.setAttribute('viewBox', '0 0 24 24');
    el.setAttribute('fill', 'none');
    el.setAttribute('stroke', 'currentColor');
    el.setAttribute('stroke-width', size <= 16 ? '1.25' : '1.5');
    el.setAttribute('stroke-linecap', 'square');
    el.setAttribute('stroke-linejoin', 'miter');
    if (!el.hasAttribute('aria-label')) { el.setAttribute('aria-hidden', 'true'); el.setAttribute('focusable', 'false'); }
    el.classList.add('ic-' + name);
    el.innerHTML = ICONS[name] || '';
    el.dataset.iconDone = name;
  });
}
