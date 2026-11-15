# Recover the +16 first-click follow-up

PR #130 merged the desktop list placement at `f5283ca`. Its later source-branch commit `afed1d3dbf00b6448da16e004527d4579e4b04c0` was absent from both integration `abb09f54daca0a7d157ba875b4ebe3b515e4ab1f` and main (v51, `bd6bba8d87a838fc38232ba8def1893637690d5a`) at the final check.

Only that commit's `web/js/globe3d.js` patch is recovered: `setClusterButton`, `placeClusterButton`, and their two declutter call sites. The 16 added / 5 removed production lines match the source patch exactly. No source branch merge, index.html edit, scientific-data change, or legend/list-placement rewrite is included. Current integration label hysteresis, camera alignment, relay marks and all other code are preserved.

## Reproduction and result

The real local app uses `?gv=-30,20,6500,0,0`, fresh browser contexts and the existing intro-seen setting. A single first press on +16 is held for 650 ms across the scheduled 400 ms declutter cycle. A MutationObserver counts text-node replacement while pressed. Browser mouse events, never forced DOM clicks, open the list and select its last scrolled row.

Before: Chromium replaced the text node twice but opened the list; Windows WebKit replaced it three times and **the first click did not open the list**. This is a focused reproduction, not a failure-rate estimate. [Baseline results](baseline/results.json).

After: **10/10 first clicks open the list**, with the same text node and zero child replacements throughout the press. All cases have zero +16/elevation-legend overlap, zero list/dock/header/legend overlap, selectable last rows, correct selected site IDs, and zero page or console errors. All list rows are at least 32 px high. [Full measurements](fixed/results.json).

| Engine | Viewport | Language | Layer / panel | First click, placement, selection | List direction | Selected last row |
|---|---|---|---|---|---|---|
| chromium | 1440 x 900 | en | light | PASS | above | PEAK_NEAR_SHACKLETON |
| chromium | 1440 x 900 | ko | elev | PASS | above | PEAK_NEAR_SHACKLETON |
| chromium | 1280 x 800 | en | elev | PASS | above | ARTEMIS_SLATER_PLAIN |
| chromium | 1280 x 800 | ko | light | PASS | above | ARTEMIS_SLATER_PLAIN |
| chromium | 1440 x 900 | en | elev / left folded | PASS | above | PEAK_NEAR_SHACKLETON |
| webkit | 1440 x 900 | en | light | PASS | above | PEAK_NEAR_SHACKLETON |
| webkit | 1440 x 900 | ko | elev | PASS | above | PEAK_NEAR_SHACKLETON |
| webkit | 1280 x 800 | en | elev | PASS | above | ARTEMIS_SLATER_PLAIN |
| webkit | 1280 x 800 | ko | light | PASS | above | ARTEMIS_SLATER_PLAIN |
| webkit | 1440 x 900 | en | elev / left folded | PASS | above | PEAK_NEAR_SHACKLETON |

Chromium 151.0.7922.34 and Windows WebKit 26.5, Playwright 1.62.1. Chromium emitted software-rendering ReadPixels performance warnings; these are retained in results.json. Windows WebKit is not a real macOS Safari/iPhone test. This checks the requested UI paths, not all app functionality or physical data accuracy.

Representative captures: [Chromium 1440 EN](fixed/chromium-1440-en-light.png), [WebKit 1280 elevation](fixed/webkit-1280-en-elev.png), [folded panel](fixed/webkit-1440-en-elev-folded.png). The remaining captures accompany the JSON.

## Re-run

Use an environment with Node, Playwright and its Chromium/WebKit binaries. If Playwright is outside the checkout, set NODE_PATH to its containing node_modules directory; set PLAYWRIGHT_BROWSERS_PATH to that installation's browser cache. No dependency install or download occurs in the verifier.

```powershell
node pipeline/verify_cluster_first_click.cjs --baseline abb09f5
node pipeline/verify_cluster_first_click.cjs
```

The verifier serves the checked-out web directory on a temporary loopback port. Baseline mode substitutes only the integration globe3d.js response, leaving other assets identical. Screenshots and results go to this directory (override with --out). Do not run it against an actively edited teammate checkout.

## Final integration refresh

Before push, integration advanced to `4b330daccf3af3ea82d88e170738321f6367a049` (Apollo 17 terrain-slope additions). Its globe3d.js was unchanged and the first-click fix was still missing. The single Codex commit was rebased onto that head; the SI conflict was resolved by retaining the complete new integration log and appending only this task row.

A minimal refresh check on the rebased code passed **2/2**: Chromium and Windows WebKit, 1280 x 800 EN, elevation layer. First clicks open, text nodes remain intact, no list/legend/dock/header overlap, last-row selection matches, zero page/console errors. [Refresh results](integration-refresh/results.json).

```powershell
node pipeline/verify_cluster_first_click.cjs --quick --out docs/qa/cluster-first-click/integration-refresh
```

The final PR base is integration `1675728a` (main v51 / PR #136 comparison tray merged into integration). The globe implementation was still unchanged and still missing this fix. The Codex commit was rebased again, preserving all integration SI rows. The focused Chromium/WebKit elevation/list check passed **2/2** on this final base, with zero page/console errors. [Final integration evidence](final-integration/results.json). Full 10-case coverage above remains pinned to its recorded earlier base; it is not presented as a full rerun after the tray update.
