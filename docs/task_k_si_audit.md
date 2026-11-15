# Task K — Jiyong SI record audit

This is a dated administrative recount, not a new scientific verification or a human sign-off. Historical log rows and the submission disclosure are unchanged. Exact inherited rows are counted once across branches; distinct rows for stages of one task remain distinct log entries. Counts are **entries, not unique tasks, prompts, calls or hours**.

| Snapshot | Commit | Jiyong rows | Additional unique entries |
|---|---|---:|---:|
| main snapshot | `274e676665d71e56a9fb7ddc7ead13e65d15aecf` | 25 | 25 |
| PR 66 | `dc140bbd24eff9c1869adda4097f812cdd5ae208` | 23 | 1 |
| PR 67 | `e50d4362f769ff811c8c85509abb027c4f22842a` | 26 | 1 |
| PR 68 | `cf37fb7db6f758bc0b6a5ecd9bab842685dd58bf` | 28 | 3 |
| this PR | `current SI file (hash in JSON)` | 30 | 5 |

**35 unique Jiyong entries**, of which **17** still have an empty/`TO CHECK` human-review or human-change cell. The remaining nonempty cells are reproduced as written; AI does not infer or add human approval. Older `Confirmed by Jiyong — ... relayed by Sua` cells are historical attributions, not reconfirmed by this audit.

The four R/U/V/K rows and the subsequent local NASA storage-migration entry are included. C, D and X/P/Q live in pending PR branches and must be merged before a main-only final submission recount. The existing `submission/si_disclosure_en.md` is pinned to an older commit; its historical count must not be presented as this latest total.

## Entries still requiring human cells

| First listed source / line | Time | Role | Human check | Human changed? |
|---|---|---|---|---|
| [main snapshot L124](https://github.com/kiisophii/lunar-landing-site-navigator/blob/274e676665d71e56a9fb7ddc7ead13e65d15aecf/docs/SI_USAGE.md#L124) | 2026-11-14 22:49 (KST) | First-zoom texture performance fix and 4K comparison | TO CHECK | TO CHECK |
| [main snapshot L125](https://github.com/kiisophii/lunar-landing-site-navigator/blob/274e676665d71e56a9fb7ddc7ead13e65d15aecf/docs/SI_USAGE.md#L125) | 2026-11-14 23:21 (KST) | Terrain build and zoom-transition performance follow-up | TO CHECK | TO CHECK |
| [main snapshot L133](https://github.com/kiisophii/lunar-landing-site-navigator/blob/274e676665d71e56a9fb7ddc7ead13e65d15aecf/docs/SI_USAGE.md#L133) | 2026-11-14 23:39 (KST) | Independent 3.8 km map and custom-polar verification | TO CHECK | TO CHECK |
| [main snapshot L137](https://github.com/kiisophii/lunar-landing-site-navigator/blob/274e676665d71e56a9fb7ddc7ead13e65d15aecf/docs/SI_USAGE.md#L137) | 2026-11-15 00:39 (KST) | South-polar 250 m local grids | TO CHECK | TO CHECK |
| [main snapshot L138](https://github.com/kiisophii/lunar-landing-site-navigator/blob/274e676665d71e56a9fb7ddc7ead13e65d15aecf/docs/SI_USAGE.md#L138) | 2026-11-15 07:31 (KST) | Task B full independent non-polar uncertainty verification | TO CHECK | TO CHECK |
| [main snapshot L139](https://github.com/kiisophii/lunar-landing-site-navigator/blob/274e676665d71e56a9fb7ddc7ead13e65d15aecf/docs/SI_USAGE.md#L139) | 2026-11-15 07:59 (KST) | Task F custom polar terrain | TO CHECK | TO CHECK |
| [main snapshot L140](https://github.com/kiisophii/lunar-landing-site-navigator/blob/274e676665d71e56a9fb7ddc7ead13e65d15aecf/docs/SI_USAGE.md#L140) | 2026-11-15 08:08 (KST) | Task W full assumption sensitivity | TO CHECK | TO CHECK |
| [PR 66 L138](https://github.com/kiisophii/lunar-landing-site-navigator/blob/dc140bbd24eff9c1869adda4097f812cdd5ae208/docs/SI_USAGE.md#L138) | 2026-11-15 08:20 (KST) | Task C full station/window/link verification | TO CHECK | TO CHECK |
| [PR 67 L141](https://github.com/kiisophii/lunar-landing-site-navigator/blob/e50d4362f769ff811c8c85509abb027c4f22842a/docs/SI_USAGE.md#L141) | 2026-11-15 08:39 (KST) | Task D independent fine globe and albedo verification | TO CHECK | TO CHECK |
| [PR 68 L141](https://github.com/kiisophii/lunar-landing-site-navigator/blob/cf37fb7db6f758bc0b6a5ecd9bab842685dd58bf/docs/SI_USAGE.md#L141) | 2026-11-15 09:06 (KST) | Task X nonpolar 250 m neighbourhood maps | TO CHECK | TO CHECK |
| [PR 68 L142](https://github.com/kiisophii/lunar-landing-site-navigator/blob/cf37fb7db6f758bc0b6a5ecd9bab842685dd58bf/docs/SI_USAGE.md#L142) | 2026-11-15 09:06 (KST) | Task P complete visibility-window verification | TO CHECK | TO CHECK |
| [PR 68 L143](https://github.com/kiisophii/lunar-landing-site-navigator/blob/cf37fb7db6f758bc0b6a5ecd9bab842685dd58bf/docs/SI_USAGE.md#L143) | 2026-11-15 09:06 (KST) | Task Q complete monthly-season verification | TO CHECK | TO CHECK |
| [this PR L142](SI_USAGE.md#L142) | 2026-11-15 09:34 (KST) | Task R independent landing audit | TO CHECK | TO CHECK |
| [this PR L143](SI_USAGE.md#L143) | 2026-11-15 09:34 (KST) | Task U independent north-polar terrain audit | TO CHECK | TO CHECK |
| [this PR L144](SI_USAGE.md#L144) | 2026-11-15 09:34 (KST) | Task V independent Earth-definition audit | TO CHECK | TO CHECK |
| [this PR L145](SI_USAGE.md#L145) | 2026-11-15 09:34 (KST) | Task K SI record recount | TO CHECK | TO CHECK |
| [this PR L146](SI_USAGE.md#L146) | 2026-11-15 10:05 (KST) | Local NASA data storage migration | TO CHECK | TO CHECK |

## Reproduce

`python pipeline/task_k_si_audit.py`

Each input snapshot has a normalized-LF SHA256 and every counted row retains its raw text and locations in [JSON](task_k_si_audit.json). Member names are matched exactly, so mentions of Jiyong in another member's request are excluded. No other member's entries or human-only H/L work are certified here.
