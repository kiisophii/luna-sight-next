// Compare the actual shared core.js API with the cached Horizons observations.
// Run after validate_ephem.py: node pipeline/check_ephem_web.mjs
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const code = await fs.readFile(path.join(root, 'web/js/core.js'), 'utf8');
// Use an unmodified .mjs copy so this also works without a package.json type.
const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'llsn-core-check-'));
const tempModule = path.join(tempDir, 'core.mjs');
await fs.writeFile(tempModule, code);
const core = await import(pathToFileURL(tempModule).href);
await fs.unlink(tempModule);
await fs.rmdir(tempDir);
const raw = await fs.readFile(path.join(root, 'web/data/ephem.bin'));
const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
core.state.ephem = Float32Array.from({ length: raw.length / 4 }, (_, k) => view.getFloat32(k * 4, true));
core.state.n = raw.length / 24;
const files = (await fs.readdir(path.join(root, 'data/raw/horizons')))
  .filter(name => /_(sun|earth)\.json$/.test(name));
if (files.length !== 12) throw Error(`Expected 12 Horizons tables, got ${files.length}`);
let count = 0, maxAz = 0, maxEl = 0;
for (const file of files) {
  const cached = JSON.parse(await fs.readFile(path.join(root, 'data/raw/horizons', file), 'utf8'));
  const coords = new URL(cached.url).searchParams.get('SITE_COORD').replaceAll("'", '').split(',').map(Number);
  const site = { id: file, lon: coords[0], lat: coords[1], elev_m: 0 };
  const fn = file.endsWith('_sun.json') ? core.sunAzEl : core.earthAzEl;
  const rows = cached.response.result.split('$$SOE')[1].split('$$EOE')[0].trim().split('\n');
  for (const row of rows) {
    const fields = row.split(',');
    const hour = Math.round((Number(fields[0]) - 2461041.5) * 24);
    const value = fn(site, hour);
    const az = Math.abs(((value.az - Number(fields[3]) + 540) % 360) - 180);
    const el = Math.abs(value.el - Number(fields[4]));
    maxAz = Math.max(maxAz, az); maxEl = Math.max(maxEl, el); count++;
  }
}
const result = { n_comparisons: count, max_az_deg: maxAz, max_el_deg: maxEl,
  threshold_deg: 0.01, passed: count === 1452 && maxAz < 0.01 && maxEl < 0.01,
  method: 'Actual web/js/core.js sunAzEl/earthAzEl reading exported float32; 6 sites, 121 UTC samples, Sun and Earth' };
await fs.writeFile(path.join(root, 'docs/ephem_web_check.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));
if (!result.passed) process.exitCode = 1;
