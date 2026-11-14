// korea.js — Korea links data helpers (docs/data_contract.md section 9, v1.2 proposal). Owner: Sua (differentiator B).
// Plain ES module, no UI. The integrator wires it into the page (list in modules.json when a panel exists).

const base = 'data/korea/';
const cache = new Map();

async function get(name) {
  if (!cache.has(name)) cache.set(name, fetch(base + name, { cache: 'no-cache' }).then(r => {
    if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`); return r.json();
  }));
  return cache.get(name);
}

/** Decode a station bitset: returns Uint8Array of 0/1 per hour index. */
export function decodeBits(b64, n) {
  const bin = atob(b64), out = new Uint8Array(n);
  for (let k = 0; k < n; k++) out[k] = (bin.charCodeAt(k >> 3) >> (k & 7)) & 1;
  return out;
}

/** {stationId: Uint8Array(n)} — Moon >= 10° above each station at hour index i. */
export async function stationBits() {
  const s = await get('stations.json');
  return Object.fromEntries(s.stations.map(st => [st.id, decodeBits(st.bits_b64, s.n)]));
}

/** Which stations see the Moon at hour index i: ['KDSA', 'DSN_MADRID', ...]. */
export async function stationsAt(i) {
  const bits = await stationBits();
  const k = Math.floor(i);
  return Object.keys(bits).filter(id => bits[id][k]);
}

/**
 * "When can Korea talk to the Moon tonight?" dateKST = 'YYYY-MM-DD'.
 * Tonight = that date from 12:00 KST to the next date 12:00 KST. Returns [{from, to, maxEl}] in KST strings.
 */
export async function kdsaTonight(dateKST) {
  const d = await get('kdsa_daily_kst.json');
  const next = new Date(Date.parse(dateKST + 'T00:00:00Z') + 86400e3).toISOString().slice(0, 10);
  const pm = (d.days[dateKST] || []).filter(w => w[1] > '12:00').map(w => ({ from: w[0] < '12:00' ? '12:00' : w[0], to: w[1], maxEl: w[2] }));
  const am = (d.days[next] || []).filter(w => w[0] < '12:00').map(w => ({ from: `${w[0]} (+1d)`, to: `${w[1] > '12:00' ? '12:00' : w[1]} (+1d)`, maxEl: w[2] }));
  // merge a window that crosses midnight (24:00 / 00:00)
  if (pm.length && am.length && pm[pm.length - 1].to === '24:00' && am[0].from === '00:00 (+1d)') {
    pm[pm.length - 1].to = am.shift().to;
  }
  return [...pm, ...am];
}

/** Danuri summary + passes for one site id (null if not computed). */
export async function danuriFor(siteId) {
  const d = await get('danuri.json');
  return d.sites.find(s => s.id === siteId) || null;
}

export async function koreaInfo() { return get('korea.json'); }
