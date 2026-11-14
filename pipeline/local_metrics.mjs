/** Persistent JSON-lines adapter for the actual production hourly metrics. */
import readline from 'node:readline';
import { actualCore, loadEphemeris, ROOT, validateHorizon } from './cache_metrics.mjs';

const { core, hash } = await actualCore(ROOT);
const ephem = await loadEphemeris(ROOT, core);
console.log(JSON.stringify({ ready: true, core_sha256: hash, ...ephem }));
for await (const line of readline.createInterface({ input: process.stdin })) {
  try {
    const { site, horizon } = JSON.parse(line);
    validateHorizon(site, horizon);
    core.state.horizons.clear();
    core.state.horizons.set(site.id, horizon);
    console.log(JSON.stringify({ metrics: core.metrics(site, 0, core.state.n - 1) }));
  } catch (error) {
    console.log(JSON.stringify({ error: error.message }));
  }
}
