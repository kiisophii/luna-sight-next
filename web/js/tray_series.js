// Presentation series from the existing hourly visibility and terrain products.
export function cumulative(bits, mask) {
  if (!bits?.length) return null;
  const step = Math.max(1, Math.round(bits.length / 160)), pts = [];
  let on = 0;
  for (let k = 0; k < bits.length; k++) {
    if ((bits[k] & mask) === mask) on++;
    if (k % step === 0 || k === bits.length - 1) pts.push([k, on / (k + 1) * 100]);
  }
  return { pts, end: on / bits.length };
}

export function relayMasks(segments, i0, i1) {
  const start = Math.floor(i0), end = Math.floor(i1) + 1;
  const total = new Uint8Array(end - start), added = new Uint8Array(end - start);
  const covered = new Uint8Array(end - start);
  for (const [s, length, code] of segments) {
    const lo = Math.max(start, s), hi = Math.min(end, s + length);
    for (let i = lo; i < hi; i++) {
      covered[i - start] = 1;
      total[i - start] = code === 1 || code === 2 ? 1 : 0;
      added[i - start] = code === 2 ? 1 : 0;
    }
  }
  return covered.every(Boolean) ? { total, added } : null;
}

export function horizonPoints(horizon) {
  if (!horizon?.mask?.length) return [];
  const step = horizon.az_step_deg || 360 / horizon.mask.length;
  return [...horizon.mask.map((v, i) => [i * step, v]), [360, horizon.mask[0]]];
}
