// about_hero.js — About hero band: a decorative Earth-to-Moon scene driven by the About scroll (Chaei's copy,
// measured motion 11/15; drawn here from scratch as SVG, no frames or practice code).
//   progress p = About scroll / scrollable distance; scene time = min(p / 0.85, 1) — it ends at p 0.85 and stays.
//   The shown value follows the target by 12 % per frame; reduced motion shows the landed scene at once.
//   Launch (65 % W, 91 % H) -> Moon's lower edge (68.2 % W, 44 % H) on wide screens; 61.5 % -> 72.6 % below 860 px.
//   Effects: launch flame + warm atmosphere 0.05-0.30, tail streak 0.25-0.45, 180 deg flip 0.40-0.55, landing burn
//   0.50-0.75, Moon halo 0.55-0.75 (peak 0.70), orange landing ring 0.65-0.80 (peak 0.70). Dotted path and stars fixed.
// Decorative only: no data, not to scale.

// fraction of the path covered at p (from the measured rocket heights, normalised)
const ALONG = [[0, 0], [0.10, 0], [0.15, 0.034], [0.20, 0.102], [0.25, 0.271], [0.30, 0.449], [0.35, 0.602], [0.40, 0.737], [0.45, 0.831], [0.50, 0.873], [0.55, 0.966], [0.60, 0.992], [0.65, 1]];
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ramp = (p, a, b) => clamp((p - a) / (b - a));
const smooth = (p, a, b) => { const x = ramp(p, a, b); return x * x * (3 - 2 * x); };
const bump = (p, a, b, c, d) => (p <= a || p >= d ? 0 : p < b ? smooth(p, a, b) : p <= c ? 1 : 1 - smooth(p, c, d));
function along(p) {
  for (let k = 1; k < ALONG.length; k++) if (p <= ALONG[k][0]) { const [p0, f0] = ALONG[k - 1], [p1, f1] = ALONG[k]; return f0 + (f1 - f0) * ((p - p0) / (p1 - p0)); }
  return 1;
}

export function mountHero(host, label) {
  if (!host) return;
  const still = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let W = 0, H = 0, geo = null, cur = 0, target = 0, raf = 0, els = null;

  function build() {
    const r = host.getBoundingClientRect(); W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
    const narrow = W < 860, s = Math.max(0.8, Math.min(1.4, H / 249));
    const L = { x: (narrow ? 0.615 : 0.65) * W, y: 0.91 * H }, A = { x: (narrow ? 0.726 : 0.682) * W, y: 0.44 * H };
    const mR = Math.min(0.19 * H, 0.055 * W), M = { x: A.x + (narrow ? 0.004 : 0.015) * W, y: A.y - mR - 0.025 * H };
    // Earth: a big circle whose top sits at 92 % of the height; chord at the bottom edge about 26 % of the width
    const d = 0.08 * H, half = (narrow ? 0.30 : 0.128) * W, eR = (half * half + d * d) / (2 * d), E = { x: L.x, y: 0.92 * H + eR };
    let x = 11; const rnd = () => ((x = (x * 9301 + 49297) % 233280) / 233280);
    let stars = ''; const n = Math.round(Math.min(90, W * H / 4500));
    for (let k = 0; k < n; k++) { const big = rnd() > 0.9; stars += `<circle cx="${(rnd() * W).toFixed(1)}" cy="${(rnd() * H * 0.9).toFixed(1)}" r="${big ? 1.1 : 0.6}" fill="#fff" opacity="${(0.15 + rnd() * 0.6).toFixed(2)}"/>`; }
    const ang = Math.atan2(A.x - L.x, -(A.y - L.y)) * 180 / Math.PI;      // degrees right of vertical
    geo = { L, A, M, mR, s, ang };
    host.innerHTML = `<svg class="abh-svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${label}">
  <defs>
    <radialGradient id="abh-air" cx="50%" cy="100%" r="60%"><stop offset="0.4" stop-color="#7cc0f5" stop-opacity=".85"/><stop offset="0.8" stop-color="#3a78b8" stop-opacity=".28"/><stop offset="1" stop-color="#3a78b8" stop-opacity="0"/></radialGradient>
    <radialGradient id="abh-warm" cx="50%" cy="100%" r="60%"><stop offset="0.3" stop-color="#ffb347" stop-opacity=".7"/><stop offset="1" stop-color="#ff8a3d" stop-opacity="0"/></radialGradient>
    <radialGradient id="abh-halo" cx="50%" cy="50%" r="50%"><stop offset="0.66" stop-color="#cfd3da" stop-opacity="0"/><stop offset="0.76" stop-color="#cfd3da" stop-opacity=".5"/><stop offset="1" stop-color="#cfd3da" stop-opacity="0"/></radialGradient>
    <radialGradient id="abh-fire" cx="50%" cy="30%" r="60%"><stop offset="0" stop-color="#fff3c4"/><stop offset="0.35" stop-color="#ffc24a"/><stop offset="1" stop-color="#ff7a2e" stop-opacity="0"/></radialGradient>
    <linearGradient id="abh-tail" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="#05070a"/>
  <g>${stars}</g>
  <ellipse cx="${E.x}" cy="${0.92 * H + 0.02 * H}" rx="${half * 1.8}" ry="${0.32 * H}" fill="url(#abh-air)"/>
  <ellipse class="abh-warm" cx="${L.x}" cy="${0.92 * H}" rx="${half * 1.2}" ry="${0.22 * H}" fill="url(#abh-warm)" opacity="0"/>
  <circle cx="${E.x}" cy="${E.y}" r="${eR}" fill="#06090e" stroke="#7fb4e6" stroke-opacity=".8" stroke-width="1.2"/>
  <circle cx="${M.x}" cy="${M.y}" r="${mR * 1.45}" fill="url(#abh-halo)"/>
  <circle class="abh-halo2" cx="${M.x}" cy="${M.y}" r="${mR * 1.5}" fill="url(#abh-halo)" opacity="0"/>
  <circle cx="${M.x}" cy="${M.y}" r="${mR}" fill="#0b0d10" stroke="#b9bec7" stroke-opacity=".45" stroke-width="1"/>
  <line x1="${L.x}" y1="${L.y}" x2="${A.x}" y2="${A.y}" stroke="#e6eaf2" stroke-opacity=".45" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="0.1 5"/>
  <ellipse class="abh-ring" rx="${17 * s}" ry="${7 * s}" fill="none" stroke="#ff9a3c" stroke-width="1.6" opacity="0"/>
  <g class="abh-rocket">
    <rect class="abh-streak" x="${-0.8 * s}" y="${7 * s}" width="${1.6 * s}" height="${40 * s}" fill="url(#abh-tail)" opacity="0"/>
    <ellipse class="abh-flame" cx="0" cy="${9 * s}" rx="${3.2 * s}" ry="${7 * s}" fill="url(#abh-fire)" opacity="0"/>
    <g class="abh-legs" opacity="0" stroke="#e6eaf2" stroke-width="${1.1 * s}" stroke-linecap="round"><path d="M${-2.4 * s} ${4.5 * s} L${-5.5 * s} ${9.5 * s} M${2.4 * s} ${4.5 * s} L${5.5 * s} ${9.5 * s}"/></g>
    <path d="M0 ${-7 * s} C ${2.6 * s} ${-4 * s}, ${2.8 * s} ${1 * s}, ${2.4 * s} ${5 * s} L ${-2.4 * s} ${5 * s} C ${-2.8 * s} ${1 * s}, ${-2.6 * s} ${-4 * s}, 0 ${-7 * s} Z" fill="#f4f6fa"/>
    <path d="M${-2.4 * s} ${2 * s} L${-4.4 * s} ${6 * s} L${-2.2 * s} ${5 * s} Z M${2.4 * s} ${2 * s} L${4.4 * s} ${6 * s} L${2.2 * s} ${5 * s} Z" fill="#c9ced6"/>
    <circle cx="0" cy="${-2.4 * s}" r="${0.9 * s}" fill="#0b0e14"/>
  </g>
</svg>`;
    const q = c => host.querySelector(c);
    els = { rocket: q('.abh-rocket'), flame: q('.abh-flame'), streak: q('.abh-streak'), legs: q('.abh-legs'), warm: q('.abh-warm'), halo: q('.abh-halo2'), ring: q('.abh-ring') };
    draw(cur);
  }

  function draw(p) {
    if (!els || !geo) return;
    const t = Math.min(1, p / 0.85) * 0.85;               // the scene ends at p 0.85 and stays
    const { L, A, ang } = geo, f = along(t);
    const x = L.x + (A.x - L.x) * f, y = L.y + (A.y - L.y) * f;
    const flip = smooth(t, 0.40, 0.55) * 180;
    els.rocket.setAttribute('transform', `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${(ang + flip).toFixed(2)})`);
    const launch = bump(t, 0.05, 0.10, 0.20, 0.40), land = bump(t, 0.50, 0.58, 0.68, 0.75);
    els.flame.setAttribute('opacity', Math.max(launch, land).toFixed(3));
    els.flame.setAttribute('transform', `scale(${(0.6 + 0.6 * Math.max(launch, land * 0.8)).toFixed(3)})`);
    els.streak.setAttribute('opacity', (0.8 * bump(t, 0.25, 0.28, 0.40, 0.45)).toFixed(3));
    els.warm.setAttribute('opacity', (0.55 * bump(t, 0.05, 0.10, 0.25, 0.35)).toFixed(3));
    els.halo.setAttribute('opacity', (0.7 * bump(t, 0.55, 0.68, 0.70, 0.78) + 0.12 * ramp(t, 0.75, 0.85)).toFixed(3));
    const ring = bump(t, 0.65, 0.70, 0.70, 0.80);
    els.ring.setAttribute('opacity', ring.toFixed(3)); els.ring.setAttribute('cx', x.toFixed(2)); els.ring.setAttribute('cy', y.toFixed(2));
    els.ring.setAttribute('transform', `rotate(${(ang).toFixed(1)} ${x.toFixed(2)} ${y.toFixed(2)})`);
    els.legs.setAttribute('opacity', ramp(t, 0.58, 0.66).toFixed(3));
  }

  const progress = () => { const max = document.documentElement.scrollHeight - window.innerHeight; return max > 0 ? clamp(window.scrollY / max) : 0; };
  const onAbout = () => document.body.classList.contains('on-about') && host.isConnected;
  function tick() {
    raf = 0; if (!onAbout()) return;
    cur += (target - cur) * 0.12;
    if (Math.abs(target - cur) < 0.0005) cur = target; else raf = requestAnimationFrame(tick);
    draw(cur);
  }
  function onScroll() {
    if (!onAbout()) return;
    target = still() ? 1 : progress();
    if (still()) { cur = 1; draw(cur); return; }
    if (!raf) raf = requestAnimationFrame(tick);
  }
  cur = target = still() ? 1 : progress();
  build();
  new ResizeObserver((f => { let q = 0; return () => { if (!q) q = requestAnimationFrame(() => { q = 0; f(); }); }; })(() => { const r = host.getBoundingClientRect(); if (Math.round(r.width) !== W || Math.round(r.height) !== H) build(); })).observe(host);   // next frame, so rebuilding never re-enters the observer
  window.addEventListener('scroll', onScroll, { passive: true });
  window.matchMedia?.('(prefers-reduced-motion: reduce)').addEventListener?.('change', onScroll);
  // test / debugging hook: set the progress directly (no smoothing)
  host.abhSet = p => { cur = target = clamp(p); draw(cur); };
}
