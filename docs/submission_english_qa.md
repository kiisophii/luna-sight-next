# Submission English UI check — 14 November 2026 (KST)

Reporter: Minchul Kim, assisted by ChatGPT/Codex. This is AI-operated inspection of the real Chrome UI, **not an independent human visual sign-off**. Human review: **TO CHECK**.

Demo: https://kiisophii.github.io/lunar-landing-site-navigator/
Source inventory snapshot: c799395a58e14d65f760d2969f320e6a588bc992. The live Pages deployment was inspected separately; no assertion that its deployed head equals this source snapshot.

Flows exercised: Korean-to-English switching, catalogue search for Shackleton, Apollo 17 and corrected Shackleton focus, local-map fallback, comparison cards, 30-day relay story and tower panel, season labels and browser console. The screenshot view was inspected for legibility. The first immediate relay read after focus still contained the previous site's values; subsequent observation showed the completed update, so that transient read is not reported as a persistent scientific defect.

| Issue | Finding |
|---|---|
| [#33](https://github.com/kiisophii/lunar-landing-site-navigator/issues/33) | Local-map fallback message stays in Korean after switching to English |
| [#31](https://github.com/kiisophii/lunar-landing-site-navigator/issues/31) | Local-map longitude mixes a negative sign with E suffix |
| [#29](https://github.com/kiisophii/lunar-landing-site-navigator/issues/29) | Relay improvement uses % where the quantity is percentage points |
| [#30](https://github.com/kiisophii/lunar-landing-site-navigator/issues/30) | “No real season at this latitude” overstates the computed sunlight result |
| [#32](https://github.com/kiisophii/lunar-landing-site-navigator/issues/32) | Link-budget explanation exposes CLI instructions and raw parameter JSON |

Each issue contains the actual English text, reproduction steps, user impact, scope and a suggested correction. No UI code or scientific data was edited. Observed console errors/warnings: none in the captured inspection log; this is not an exhaustive browser/network audit. No persistent broken desktop layout was confirmed. Mobile layouts, all date boundaries, all custom-coordinate calculations and a complete accessibility audit were not covered.
