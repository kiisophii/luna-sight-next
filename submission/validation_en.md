# Validation — Luna Sight — Lunar Landing Site Navigator (Team Ginkgo Orbit)

Final text for the project page and the backup deck. Every number is copied from `docs/VALIDATION.md` or
`docs/hindcast.md`; the footnotes give file:line (line numbers as of this commit, after PR #28).

## (a) Validation paragraph for the project page (≤ 120 words)

We checked the app's key numbers against independent NASA sources. Sun and Earth directions agree with
JPL Horizons to within 0.000041° over 2020–2038 [^1], and our ephemeris pipeline matches Horizons to
0.00004° for 2019–2025 [^2]. Terrain horizons recomputed by brute force agree to about 0.02° [^3]. Against
NASA's 18.6-year south-polar illumination maps (PGDA), sunlight at 240 random points differs by
1.66 percentage points on average (r = 0.985) and Earth visibility (PGDA's any-part rule) by 1.24 points (r = 0.990) [^4][^5].
At the six Apollo landings, our Sun elevation matches the Apollo Lunar Surface Journal to 0.05° [^6].
Four robotic landers shut down near our computed sunsets [^7]. App metrics are identical
in JavaScript and an independent Python port [^8].

*(120 words)*

## (b) Strongest checks

| What was compared | Against (source) | Max difference | Criterion |
|---|---|---|---|
| Sun & Earth directions, 18.6-year ephemeris 2020–2038 (34,296 comparisons) | NASA JPL Horizons (DE441) | 0.000041° [^1] | < 0.01° |
| Sun & Earth directions at 6 real landing sites, 2026 (1,452 comparisons) | NASA JPL Horizons | 0.000034° [^9] | < 0.01° |
| Ephemeris 2019–2025, 50 random hours | NASA JPL Horizons | 0.00004° [^2] | < 0.01° |
| Non-polar terrain horizons, 17 sites × 720 azimuths | own brute-force code from NASA LOLA/SLDEM2015 | 0.016° with 1 m steps (0.219° with 20 m steps), RMS ≤ 0.026° [^3] | ~0.02° |
| Sunlight fraction, 240 random points 85–90° S, 18.6 years | NASA PGDA AVGVISIB 60 m (Mazarico et al. 2011) | MAE 1.66 pp, RMSE 2.62 pp, r 0.985 [^4] | — |
| Earth visibility, same points, PGDA's any-part rule (the app's stricter centre rule: MAE 3.87 pp) | NASA PGDA AVGVISIB_EARTH 60 m | MAE 1.24 pp, RMSE 3.37 pp, r 0.990 [^5] | — |
| Sun elevation at the six Apollo landings | NASA Apollo Lunar Surface Journal table | 0.05° (0.02° at the Journal's coordinates) [^6] | Apollo < 0.1° |
| Moon visibility from Yeoju KDSA + NASA DSN (4 stations, 100 random hours each) | NASA JPL Horizons | 0.0012° [^10] | < 0.05° |

## (c) Backup-deck slide — "How do we know it is right?"

- **Sky geometry = NASA JPL Horizons** to ≤ 0.000041° over 2019–2038 [^1][^2]
- **Terrain horizons** re-derived by brute force: ~0.02° [^3]
- **NASA PGDA 18.6-year maps**, 240 points 85–90° S: Sun 1.66 pp, Earth 1.24 pp (PGDA's any-part rule; app's centre rule 3.87 pp) mean difference [^4][^5]
- **Apollo 11–17**: Sun elevation at landing within 0.05° of the Apollo Lunar Surface Journal [^6]
- **Real landers** (Chandrayaan-3, Chang'e 3, IM-1, SLIM): shutdowns between 2 days before and 1 day after our sunset — a proxy [^7]
- **App code**: JavaScript = independent Python port on all 33 sites [^8]
- **Korea link**: Yeoju KDSA + DSN Moon visibility within 0.0012° of Horizons [^10]

## (d) Limits

- **No PGDA truth north of 75° S.** PGDA comparisons cover 85–90° S (240 points) [^4] and 75–85° S (400 points, whole-Moon map) [^11]; mid- and low-latitude sites rely on Horizons geometry, LOLA horizons and the Apollo/robotic hindcast.
- **Near field < 200 m is not marched at non-polar sites** (horizons start at 0.2 km, as in card 9) [^3].
- **End of operations is only a proxy for sunset**; operators often power down before nightfall, some reports give only a date, and SLIM / Chang'e 3 times come from secondary news reports. Chang'e 4 has no public first-night time and was not compared [^12][^13].
- **Apollo reference values are a published computation** (ALSJ), not an in-situ measurement [^14].
- **Geometry only**: no link budget or antenna scheduling; KDSA coordinates come from a publicly released NASA/JPL NAIF SPICE file, used with citation (no separate permission requested) [^15].
- **No ground truth for horizons beyond the DEMs themselves** (no surface photographs compared) [^16].
- **PGDA's exact 18.6-year dates and observer height are not stated** (unverified) [^17].

---

[^1]: `docs/VALIDATION.md:55` — row 3: "34,296 comparisons, max 0.000041°".
[^2]: `docs/hindcast.md:9` — "matches JPL Horizons to **0.00004°** at 50 random hours (criterion 0.01°)"; detail `docs/hindcast.md:13`.
[^3]: `docs/VALIDATION.md:59` — row 7: "max 0.012–0.219° (0.016° with 1 m steps), RMS ≤ 0.026°", criterion "~0.02°", "same 0.2 km start".
[^4]: `docs/VALIDATION.md:60` — row 8: "MAE 1.66 pp, RMSE 2.62 pp, r 0.985", 240 random points 85–90° S.
[^5]: `docs/VALIDATION.md:61` — row 9: "MAE 1.24 pp, RMSE 3.37 pp, r 0.990".
[^6]: `docs/hindcast.md:7` — "within **0.05°** at our catalogue points (0.02° at the Journal's own coordinates)"; per-mission values `docs/hindcast.md:21`–`26`.
[^7]: `docs/hindcast.md:8` — Chandrayaan-3 3.8 h before, SLIM 1 day after, IM-1 2 days before, Chang'e 3 18.6 h before our sunset; table `docs/hindcast.md:36`–`40`.
[^8]: `docs/VALIDATION.md:65` — row 13: "identical on 3 synthetic fixtures and all 33 real sites".
[^9]: `docs/VALIDATION.md:54` — row 2: "1,452 comparisons, max 0.000034°".
[^10]: `docs/VALIDATION.md:67` — row 15: "max 0.0012°", criterion "< 0.05°".
[^11]: `docs/VALIDATION.md:63` — row 11: whole-Moon map, "75–85° S (400 points)".
[^12]: `docs/hindcast.md:32` — "End of operations is an approximate proxy, not an exact measurement of sunset."
[^13]: `docs/hindcast.md:40` — Chang'e 4 "no public source"; `docs/hindcast.md:60` — SLIM and Chang'e 3 from secondary news reports.
[^14]: `docs/hindcast.md:59` — "Apollo reference values are a published computation (ALSJ), not an in-situ measurement."
[^15]: `docs/VALIDATION.md:78` — "Link windows are geometry only: no link budget, no antenna scheduling. KDSA coordinates: publicly released NASA/JPL NAIF SPICE file kdsa01.tf, used with citation; no separate permission was requested."
[^16]: `docs/VALIDATION.md:77` — "No ground truth for site horizons beyond the DEMs themselves".
[^17]: `docs/VALIDATION.md:80` — "PGDA's exact 18.6-year dates and observer height are not stated (unverified)."
