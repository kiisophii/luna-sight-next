// ui_select.js — one dropdown look for every <select> (designer Chaei's decisions #8, #12; written values only).
// The native <select> stays in the page (hidden) and remains the single source of truth: other modules keep
// reading .value and listening to 'change'. This only draws a button + option list and writes back to the select.
//   variant 'box'  : 32 px control, radius 6, options as 32 px cards, chosen = 10 % white
//   variant 'text' : plain text button "label ∨" (24 px), list opens aligned to the right edge
const CHEV = '<svg class="dd-chev" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const all = new Set();
let uid = 0;

export function enhanceSelect(sel, { variant = 'box', align = 'left' } = {}) {
  if (!sel || sel.dataset.dd) return null;
  sel.dataset.dd = '1';
  const id = `dd-${++uid}`;
  const wrap = document.createElement('span');
  wrap.className = `dd dd-${variant}`;
  // keep the select's footprint: full width where it filled its box, otherwise its own width
  const r = sel.getBoundingClientRect(), pr = sel.parentElement?.getBoundingClientRect();
  if (variant === 'box' && r.width > 0) {
    if (pr && r.width >= pr.width - 4) wrap.classList.add('dd-fill'); else wrap.style.minWidth = `${Math.round(r.width)}px`;
  }
  sel.after(wrap);
  wrap.append(sel);
  sel.classList.add('dd-native');
  sel.tabIndex = -1; sel.setAttribute('aria-hidden', 'true');
  const btn = document.createElement('button');
  btn.type = 'button'; btn.className = 'dd-btn';
  btn.setAttribute('aria-haspopup', 'listbox'); btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', id);
  const list = document.createElement('div');
  list.className = `dd-list dd-${align}`; list.id = id; list.setAttribute('role', 'listbox'); list.hidden = true;
  wrap.append(btn, list);

  const label = () => sel.getAttribute('aria-label') || sel.closest('label')?.querySelector('[data-i18n]')?.textContent || '';
  function refresh() {
    const o = sel.options[sel.selectedIndex];
    btn.innerHTML = `<span class="dd-val">${o ? escape(o.textContent) : ''}</span>${CHEV}`;
    const l = label(); if (l) btn.setAttribute('aria-label', `${l}: ${o ? o.textContent : ''}`);
    btn.disabled = sel.disabled;
  }
  function build() {
    list.innerHTML = [...sel.options].map((o, k) =>
      `<button type="button" role="option" class="dd-opt" data-k="${k}" aria-selected="${k === sel.selectedIndex}"${o.disabled ? ' disabled' : ''}>${escape(o.textContent)}</button>`).join('');
  }
  function open() {
    for (const d of all) if (d !== api) d.close();
    build(); list.hidden = false; btn.setAttribute('aria-expanded', 'true');
    (list.querySelector('[aria-selected="true"]') || list.querySelector('.dd-opt'))?.focus();
  }
  function close(focusBtn) { if (list.hidden) return; list.hidden = true; btn.setAttribute('aria-expanded', 'false'); if (focusBtn) btn.focus(); }
  function choose(k) {
    if (sel.selectedIndex !== k) { sel.selectedIndex = k; sel.dispatchEvent(new Event('change', { bubbles: true })); }
    refresh(); close(true);
  }
  btn.addEventListener('click', () => (list.hidden ? open() : close()));
  btn.addEventListener('keydown', e => { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(); } });
  list.addEventListener('click', e => { const b = e.target.closest('.dd-opt'); if (b && !b.disabled) choose(Number(b.dataset.k)); });
  list.addEventListener('keydown', e => {
    const opts = [...list.querySelectorAll('.dd-opt:not([disabled])')], i = opts.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); opts[Math.min(opts.length - 1, i + 1)]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); opts[Math.max(0, i - 1)]?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); opts[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); opts[opts.length - 1]?.focus(); }
    else if (e.key === 'Escape') { e.preventDefault(); close(true); }
    else if (e.key === 'Tab') close();
  });
  document.addEventListener('pointerdown', e => { if (!wrap.contains(e.target)) close(); });
  sel.addEventListener('change', refresh);
  new MutationObserver(() => requestAnimationFrame(refresh)).observe(sel, { childList: true, subtree: true, characterData: true, attributes: true });
  const api = { refresh, close, el: wrap };
  all.add(api);
  refresh();
  return api;
}
/** Enhance every <select> under root now and whenever modules add new ones (brief, horizon, local map, …). */
export function autoEnhance(root = document.body) {
  const run = n => (n.matches?.('select') ? [n] : [...(n.querySelectorAll?.('select') || [])])
    .filter(x => !x.dataset.dd && !x.hasAttribute('data-dd-skip') && !x.multiple).forEach(x => enhanceSelect(x));
  run(root);
  new MutationObserver(ms => { for (const m of ms) for (const n of m.addedNodes) if (n.nodeType === 1) run(n); }).observe(root, { childList: true, subtree: true });
}
/** Re-read every enhanced select (a module may set .value without firing 'change'). */
export function refreshSelects() { for (const d of all) d.refresh(); }
['llsn:ready', 'llsn:lang', 'llsn:sort', 'llsn:window', 'llsn:sites', 'llsn:focus'].forEach(ev => window.addEventListener(ev, () => requestAnimationFrame(refreshSelects)));

function escape(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
