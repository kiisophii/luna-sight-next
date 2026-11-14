# Phase 4 (S4) — one whole-Moon 3D view

Owner: Sua Kim (integrator). Code: `pipeline/build_globe_tiles.py` (data), `web/js/globe3d.js` (viewer),
`web/globe_test.html` (standalone test page; `index.html` is not touched). Sources: `data/DATASETS.md`.

## 1. Idea
One globe, no separate "south pole 3D" or "site 3D" screens. Terrain tiles get finer as the camera gets closer
(Google-Earth style). Coarse tiles exist everywhere; fine tiles exist only around the catalogue sites
(`web/data/sites.json`), where SLDEM2015 / PGDA data are fetched by HTTP Range.

## 2. Tile layout (`web/data/globe/`)
| Quadtree | Projection | Root | Spacing per level (256 cells / tile) |
|---|---|---|---|
| `band` | equirectangular, lat −72…72 | 5 × 2 tiles of 72° | z0 8.5 km · z1 4.3 · z2 2.1 · **z3 1.07 km (whole Moon)** · z4 533 m · z5 267 · z6 133 · z7 67 m (sites only) |
| `south`, `north` | polar stereographic, R = 1737.4 km (same as PGDA), ±560 km square | 1 tile | z0 4.4 km · z1 2.2 · **z2 1.09 km (whole cap)** · z3 547 m · z4 273 · z5 137 · z6 68 · z7 34 · z8 17 m (south-polar sites only) |

- Caps draw only poleward of 71.9° (fragment discard) and the band stops at 72°, so there is no seam at the poles
  and no singular pole row. Band tiles start at lon −180, so the dateline is a tile edge.
- Every PNG is 259 × 259: 257 × 257 shared-edge vertices + a 1-sample border so normals at tile edges are exact.
  Height = `(R·256 + G) / 2 − 10000` m above 1737.4 km (0.5 m steps, lossless).
- `index.json` lists every tile `[z, x, y, hmin, hmax, fine]` (`fine` = 1 when a SLDEM/PGDA source was used).
- Fine levels are generated only for complete quads (all 4 children) whose area is covered by a finer DEM; the
  refinement radius shrinks with level (60 km to ~250 m spacing, 40 km at 133 m, 20 km at 67 m, 10 km at 17–34 m)
  to keep the total size web-friendly.
- Colour: NASA SVS CGI Moon Kit `lroc_color_poles_8k.tif` → `moon_color_8k.jpg` / `moon_color_2k.jpg`
  (sampled per pixel from the surface direction, with Tarini's trick so the dateline has no mip seam).

## 3. Rebuild
```bash
python pipeline/build_globe_tiles.py test      # projection + height-encoding self-check
python pipeline/build_globe_tiles.py fetch     # SLDEM2015 ±62 km, PGDA 20/60/80 m windows (resumable)
python pipeline/build_globe_tiles.py albedo    # SVS colour map -> JPEG
LDEM64_IMG=path/to/ldem_64_float.img python pipeline/build_globe_tiles.py build   # resumable (data/processed/globe_progress.json)
```
`ldem_64_float.img` (1.06 GB) comes from `pipeline/fetch_global.py` (card 3). Raw data stay in `data/raw/` (git-ignored).

## 4. Viewer API (`web/js/globe3d.js`)
```js
import { createGlobe } from './js/globe3d.js';
const g = await createGlobe(element, { base: 'data/', hour: 7627, exaggeration: 1, view: {lat, lon, range, tilt, heading} });
g.setTime(hourIndexOrDate);            // Sun light + Sun/Earth sprites from ephem.bin (linear interpolation)
g.flyTo({lat, lon, range, tilt, heading});   // Promise, animated (up-and-over in log range)
g.focusSite('APOLLO17', {range: 40, tilt: 60});
g.setExaggeration(k);                  // display default x3 (team decision 11/14), no buttons; a persistent note says
                                       // "Height x3 (display only; calculations use true heights)" / "높이 3배 과장 · 보기용 (계산은 실제 높이)"
g.setLang('en' | 'ko');
// options: avoid: ['header', '.side-panel', '#minimap', ...]  -> off-screen Sun/Earth chips never cover these
//          chipInsets: {top, right, bottom, left}             -> extra free margins for chips
g.getView(); g.on('siteclick' | 'view' | 'time', fn); g.heightAt(lat, lon); g.stats; g.dispose();
g.step();                              // manual frames until tiles are loaded (tests / hidden tabs)
```
- Camera: left-drag pans along the surface (parallel transport, works across the poles), right-drag or
  Shift-drag rotates/tilts, wheel or pinch zooms (two-finger twist rotates), arrows pan, Shift+arrows rotate/tilt,
  +/− zoom, N = north up, R = reset tilt. Tilt is limited to 0° from far away and up to 80° near the ground.
- Light = directional Sun from `ephem.bin`; terrain shading from per-tile normal maps (full 256-cell resolution,
  geometry uses every 2nd sample); shadow map (4096²) follows the camera target (box ≈ 1.4 × range).
- Vertical exaggeration is fixed at ×3 for display (team decision 11/14; the designer may revise). No buttons; a
  persistent note shows it. Every number (HUD horizon test, app metrics) uses true heights.
- Off-screen chips slide along the edge of the safe area until they overlap none of `opts.avoid`, the note/HUD,
  or each other; if no free spot exists they hide rather than cover UI. A small arrow shows the true direction.
- Sun and Earth sprites sit at their real directions (Earth with topocentric parallax from the camera) and are
  depth-tested against the terrain, so ridges hide them. Icons are enlarged (not true angular size). Off-screen
  chips at the screen edge point to them.
- HUD: Sun / Earth elevation and azimuth at the target, and whether the terrain (from loaded tiles, true scale,
  0.2–400 km, curvature included, 2 m observer) hides them. This is a visual aid; the app's numbers come from
  `core.js` + `horizon/<ID>.json`.
- Memory: LRU of 420 tile meshes; geometry, normal map and material are disposed on eviction.

## 5. Known limits
- Colour map is ~4.7 km/px, so close up the detail comes from the terrain shading, not from the colour.
- Outside the site patches the finest terrain is 1.07 km (band) / 1.09 km (caps).
- LDEM_64 is offset ~0.002–0.003° east of SLDEM2015 (`docs/global_terrain.md` §4); at patch borders this is < 1 tile pixel.
- The north cap has no PGDA product in our cache, so it stays at LDEM_64 resolution.

## 6. Integration into the live page (branch `s4-globe-integrate-sua`, 2026-11-14)
- `index.html`: section `#llsn-globe` is the first panel; then picker → cards → horizon panorama → analysis window → filters (main's order).
  Under the globe a mirrored time strip (Play + slider + selected time) drives the same `LLSN.setTime` as the analysis window.
- `web/js/globe_app.js` (first entry of `modules.json`) imports `globe3d.js` dynamically, so if WebGL or the three.js CDN fails
  the rest of the page still works and the panel shows a message.
  - `llsn:time` → `globe.setTime(i)` (Sun light, shadows, Sun/Earth markers); picker / card click or `llsn:focus` → `focusSite` (one flight, deduplicated);
    globe marker click → `LLSN.pick(id)` (comparison card + focus → horizon panorama + period table); `llsn:lang` → `setLang`.
  - Buttons: Whole Moon, South pole, Focused site, +/−. `?gv=lat,lon,range,tilt,heading` sets the first view (read only). `?tv=1` enlarges the stage and labels.
  - Chips avoid the zoom buttons, the progress pill, the hint, the site markers and the note/HUD (1,852 checks in TV mode, 0 overlaps).
- `globe3d.js` performance changes: render on demand (idle = no GPU work), pause while scrolled off-screen (IntersectionObserver),
  tile mesh builds limited to ~6 ms per frame, 8k colour map loaded only below 3,000 km range, adaptive quality below ~25 fps
  (pixel ratio 1 → 2048² shadows → coarser LOD), `opts.ephem/ephemMeta/sites` share the app's data (no second download),
  `wheelNeedsFocus` (the page scrolls until the globe is clicked; a hint explains it). Night side ambient 0.05 → 0.10 (display only).
- `app.js`: slider input applied once per animation frame; "until sunset / Earthset" results reused while the selected time stays
  before the cached flip (same values to the displayed precision, 600 checks). App-side scrub cost 13.4 ms → 0.1 ms median.
