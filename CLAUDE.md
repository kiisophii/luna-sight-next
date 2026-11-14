# Team Ginkgo Orbit — NASA Space Apps 2026, Challenge "Lunar Landing Site Navigator"

## Goal (one sentence)
A tool that lets mission planners, educators and the public quickly compare lunar landing sites and dates:
at that site and time, can the lander see the Sun (power, heat) and the Earth (direct-to-Earth link)?
It is a comparison and re-planning tool, NOT a "best site" picker. Ideas and design decisions come from
our team members; you (the AI) help implement, compute, document and cross-check.

## Must-show items (from the official challenge text)
- Pick and compare sites side by side: Apollo, CLPS, commercial, other nations, Artemis III regions, user coordinates.
- Change date/time; lunar day (29.5 d) and seasons.
- Sun and Earth position relative to the local horizon; TIME UNTIL SUNSET and TIME UNTIL EARTHSET; Sun elevation shown prominently.
- Power/communication metrics: sunlight fraction, Earth-visibility windows, both, longest shadow.
- 2D and 3D views; animation/timeline; accessible to non-experts (English UI default + Korean toggle).
- Terrain from LOLA, no atmospheric refraction, libration included (via ephemeris).

## Data (NASA first; cite every source in data/DATASETS.md the moment you use it)
- Ephemeris: NAIF kernels de440s.bsp, moon_pa_de421_1900-2050.bpc, moon_080317.tf, pck00008.tpc, naif0012.tls
  (https://naif.jpl.nasa.gov/pub/naif/generic_kernels/), read with Python Skyfield; frame MOON_ME (DE421).
  Cross-check with JPL Horizons API https://ssd.jpl.nasa.gov/api/horizons.api (no key).
- Terrain (multi-resolution: finest near the site, coarser far away, ALWAYS include lunar curvature):
  PGDA south pole 5 m / 10 m / 20 m / 60 m / 80 m / 240 m (https://pgda.gsfc.nasa.gov/products/90, data under /data/LOLA_20mpp/ and /data/LOLA_5mpp/),
  SLDEM2015 59 m tiles (±60°) and LOLA LDEM_16/64/128 global (https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/).
  Use HTTP Range requests to fetch only needed regions; resume downloads (curl -C -). Never commit raw data to git.
- Validation truth: PGDA average illumination & Earth visibility maps (https://pgda.gsfc.nasa.gov/products/69),
  cite Mazarico et al. 2011 (Icarus 211, 1066–1081).
- Color basemap: NASA SVS CGI Moon Kit (https://svs.gsfc.nasa.gov/4720). Site coordinates: NSSDCA, LROC posts, NASA/NTRS papers.
- Korea (KASA is a 2026 partner): Danuri/KPLO trajectory via Horizons COMMAND='-155'; ShadowCam images (NASA/KARI/ASU, terms pending);
  KDSA antenna coordinates (kdsa01.tf, NAIF; terms pending).

## Definitions (use exactly)
- Observer height 2 m above terrain. Horizon mask = max elevation angle per azimuth, marched outward with curvature.
- Sun visible fraction = visible part of the solar disk; "sunlit" = fraction ≥ 0.5.
- Earth visible = Earth CENTER above the horizon mask (conservative).
- "Both" = sunlit AND Earth visible. Ground stations need the Moon ≥ 10° above their horizon.

## Repo layout and data contracts (do not change formats without the team)
- web/ (static app, GitHub Pages), web/js/<your-file>.js (one file per task owner), pipeline/ (Python), data/DATASETS.md, docs/SI_USAGE.md
- **The exact file formats are in docs/data_contract.md (v1, fixed 2026-11-14 09:40). Read it before writing or reading any data file.**
  Key rules: MOON_ME frame; lon −180…180 east-positive; heights above R = 1737.4 km; azimuth 0 = north clockwise; UTC hour index from 2026-01-01T00Z.
- Only the integrator (Sua) edits web/index.html. You work in your own branch and open a PR.

## Style
- Colors: Sun = yellow, Earth = blue, relay = green. "Vivid" color theme. Units and assumptions shown on screen.
- English UI by default; Korean toggle. Numbers on screen and in the submission come only from today's computations.

## Rules for you (the AI)
- Cite a source URL for every dataset or number; say "unverified" if unsure. Never invent numbers.
- Long computations must save progress and resume after interruption; use all CPU cores only when told.
- Do not use or modify NASA logos. Do not generate images/videos without a visible "AI-generated" watermark.
- Show me how to verify your output (a command or a comparison), and keep the verification separate.
- Answer in Korean unless I ask otherwise; code, comments and commit messages in English.

## SI usage log (required)
After any task that changes files in this repo, append one row to docs/SI_USAGE.md:
| YYYY-MM-DD HH:MM (KST) | <member> | <role> | <tool/model> | <what was asked> | <files changed> | TO CHECK | TO CHECK |
Never edit or delete existing rows. Leave the last two cells for the human.
