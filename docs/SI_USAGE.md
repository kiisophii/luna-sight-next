# SI (AI) usage log

Ideas and design decisions come from team members; SI tools assist with code, data processing, documentation and cross-checking.

| Time (KST) | Member | Role | Tool & model | What we asked | Output (file / commit) | How a human checked it | Changed by human? |
|---|---|---|---|---|---|---|---|
| 2026-11-14 09:30 (KST) | Sua Kim | 1 Integrator | Claude Code (Claude Opus 5.5) | Draft data contract v1 (file formats) and point AI instructions to it | docs/data_contract.md, CLAUDE.md, AGENTS.md | TO CHECK | TO CHECK |
| 2026-11-14 09:45 (KST) | Sua Kim | 1 Integrator | Claude Code (Claude Opus 5.5) | Contract v1.1: add Earth ±60 m / ±300 m min-max fields to validation.json (issue raised by Dongju Kim) | docs/data_contract.md | TO CHECK | TO CHECK |
| 2026-11-14 09:32 (KST) | Sua Kim | 6 Integrator | Claude Code (Claude Opus 5.5) | Card 6: mock data in contract formats, contract checker, core.js geometry API, static app skeleton (3-site cards, time slider + play, EN/KO toggle, ?tv=1, CSS variables for theme.css) | web/data/* (mock), pipeline/make_mocks.py, pipeline/check_contract.py, web/js/core.js, web/js/app.js, web/js/i18n.js, web/js/modules.json, web/css/base.css, web/index.html, web/version.json | TO CHECK | TO CHECK |
| 2026-11-14 09:35 (KST) | Sua Kim | 6 Integrator | Claude Code (Claude Opus 5.5) | Update mock validation.json and contract checker to data contract v1.1 (Earth min/max fields, spread % uses each body's min/max) | pipeline/check_contract.py, pipeline/make_mocks.py, web/data/validation.json | TO CHECK | TO CHECK |
| 2026-11-14 09:55 (KST) | Dongju Kim | 6 Verify/Korea | Claude Code (Claude Opus 5.5) | Card 5: download PGDA 18.6-year Sun/Earth visibility maps, sample 240 random points 85–90°S (seed 42) and named polar sites with ±60 m/±300 m min/max, compare() that writes validation.json (contract v1.1) | pipeline/validate.py, data/processed/validation_points.csv, data/processed/validation_named.csv, data/DATASETS.md | TO CHECK | TO CHECK |
