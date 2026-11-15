# Luna Sight — Lunar Landing Site Navigator

**Compare lunar landing sites and dates: at a given site and time, can a lander see the Sun and the Earth?**

**Live demo: https://kiisophii.github.io/lunar-landing-site-navigator/**

Team **Ginkgo Orbit** · NASA Space Apps Challenge 2026 · Seoul · Challenge 04: *Lunar Landing Site Navigator*

Luna Sight is a comparison and re-planning tool, not a "best site" picker. Pick candidate sites, change the landing date, and see side by side when each site has the Sun and the Earth above its local horizon. English by default, with a Korean toggle (KR/EN).

## Main features
- **3D Moon map** — explore the Moon in 3D with NASA LOLA terrain and LROC colour, switch map layers (mean sunlight, mean Earth visibility, elevation), and add your own landing point by clicking the map or typing coordinates.
- **Candidate comparison** — pin candidates from the list, change the landing date and operating period, and compare Sun and Earth visibility side by side over the lunar day.
- **Detailed comparison** — a measure-by-measure table for the pinned candidates, with Sun and Earth elevation charts and a shared timeline.
- **Site check** — one site in depth: Sun and Earth-view time, nearby locations, landing-date delays, relay tower, ground stations, horizon, terrain and seasons; share it as a link or export it as a PDF.
- **About** — why we built it, how to read the numbers, data and credits, assumptions and limits, and the team and AI use.

## Run it locally
The app is a static site; any static file server works. From the repository root:

```bash
python -m http.server 8000 --directory web
```

Then open http://localhost:8000 in a browser.

## Links
- Data sources and credits: [`submission/resources_en.md`](submission/resources_en.md) (full dataset list with URLs and citations: [`data/DATASETS.md`](data/DATASETS.md))
- AI (SI) usage log: [`docs/SI_USAGE.md`](docs/SI_USAGE.md)
- License: [Apache License 2.0](LICENSE)

## Repository layout
- `web/` — the static web app (deployed to GitHub Pages)
- `pipeline/` — Python data processing
- `data/DATASETS.md` — every data source, URL, license and citation
- `submission/` — texts for the Space Apps submission
- `docs/` — methods, checks and the SI usage log

## License
Apache License 2.0 (see [`LICENSE`](LICENSE)). Third-party data, fonts and libraries keep their own licenses; see [`submission/resources_en.md`](submission/resources_en.md) and [`data/DATASETS.md`](data/DATASETS.md). This project uses public NASA data; NASA has not reviewed, approved or endorsed it.
