# Site coordinate meaning audit — 33 catalogue points

Audit date: 14 November 2026 (KST). Pinned main: [f4705c066774641dd27c101928ffddc9a3304ce2](https://github.com/kiisophii/lunar-landing-site-navigator/tree/f4705c066774641dd27c101928ffddc9a3304ce2). Catalogue SHA-256: `fabf63bcfe2d33d556bb1e0c1f8934254600233fd65f0ecc7bb7d974d1ed7af0`.

## Result

All **33 stored coordinate pairs match the stated source pair**, after longitude normalization: maximum source-to-catalogue separation **0.000 m**. This verifies transcription, **not** whether every named ridge/peak is located at that point.

**Four records require Sua's semantic/label decision:** CONNECTING_RIDGE, PEAK_NEAR_SHACKLETON, DE_GERLACHE_RIM1 and SHOEMAKER_RIM_A. They use DEM polygon centres. Their existing notes disclose this, but their names and `polar_peak` group can still suggest a surveyed feature point. This is the same category of interpretation risk as the former Shackleton record; it is **not evidence that all four points are physically off their features**.

| Point definition | Count | Interpretation |
|---|---:|---|
| Observed landed vehicles | 18 | Six Apollo LMs, three Luna vehicles, nine other landers |
| Artemis research representative points | 9 | One published CLS per selected region; not region centres or NASA-selected touchdown points |
| Published Shackleton rim research point | 1 | First S row in Gläser Table 2 |
| DEM polygon centres | 4 | Label-risk flags; crest/summit placement not established |
| Paper-defined planned target | 1 | Lunar Vertex / IM-3 target, not an observed landing |

**sites.json and all scientific inputs/outputs were left unchanged.** This report is the notice for Sua to decide what, if anything, to change before catalogue edits.

## Method and distance meaning

All **15 distinct source_url pages** were opened afresh; shared pages cover multiple records. Reading included coordinate labels, nearby prose, table headers and definitions. Wiley Table A1 was accessible in this session. NTRS Data Book printed pp.57-58 and Gläser printed p.12 were also downloaded, rendered and visually checked for row alignment. Earlier numeric audits were context, not substitutes for these source checks.

Source latitudes below are north-positive and source longitudes east-positive (some are 0–360). Normalize longitude into −180…180. Use the great-circle distance on a sphere of R = 1,737,400 m:

`d = 2 R atan2(sqrt(a), sqrt(1-a))`, with `a = sin²(Δlat/2) + cos(lat_source) cos(lat_catalogue) sin²(Δlon/2)`; radians, shortest wrapped Δlon. Decimal arithmetic is used before conversion to radians so equivalent decimal longitudes do not create subtraction noise. Latitude/east components and full precision results are in [site_coordinate_audit.json](site_coordinate_audit.json).

**0 m means identical stated numbers.** It is not metre-level accuracy, a datum transformation, distance to a true summit, or a claim that the source point is safe for landing. For the four polygon-centre flags, distance to an independently established crest/summit is **unknown**, not zero. No polygon-centroid algorithm is specified by the source; its “centre” wording is not upgraded to a proven mathematical centroid.

## Per-site comparison

Coordinates are `(latitude, longitude)` in degrees. Source numbers are retained in their original numeric longitude convention. `PASS` concerns named vehicle/research-point meaning in the cited source; `REP` and `TARGET` require the stated representative/planned qualification. `FLAG` concerns the feature-point interpretation.

### Landed vehicles (18)

| ID | Catalogue (N+, E+) | Source (N+, E+) | Source row / marker | Meaning | Δ m | Status |
|---|---|---|---|---|---:|---|
| APOLLO11 | (0.67416, 23.47314) | (0.67416, 23.47314) | [S01](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html), Apollo 11 LM | Landed LM | 0.000 | PASS |
| APOLLO12 | (-3.0128, -23.4219) | (-3.0128, -23.4219) | [S01](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html), Apollo 12 LM | Landed LM | 0.000 | PASS |
| APOLLO14 | (-3.64589, -17.47194) | (-3.64589, -17.47194) | [S01](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html), Apollo 14 LM | Landed LM | 0.000 | PASS |
| APOLLO15 | (26.13239, 3.6333) | (26.13239, 3.63330) | [S01](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html), Apollo 15 LM | Landed LM | 0.000 | PASS |
| APOLLO16 | (-8.9734, 15.5011) | (-8.9734, 15.5011) | [S01](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html), Apollo 16 LM | Landed LM | 0.000 | PASS |
| APOLLO17 | (20.1911, 30.7723) | (20.1911, 30.7723) | [S01](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html), Apollo 17 LM | Landed LM | 0.000 | PASS |
| LUNA16 | (-0.5137, 56.3638) | (-0.5137, 56.3638) | [S02](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html), Luna 16 soft landing | Landed vehicle | 0.000 | PASS |
| LUNA20 | (3.7863, 56.6242) | (3.7863, 56.6242) | [S02](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html), Luna 20 soft landing | Landed vehicle | 0.000 | PASS |
| LUNA24 | (12.7142, 62.2129) | (12.7142, 62.2129) | [S02](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html), Luna 24 soft landing | Landed vehicle | 0.000 | PASS |
| CHANGE3 | (44.1214, -19.5116) | (44.1214, 340.4884) | [S03](https://lroc.im-ldi.com/images/637), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| CHANGE4 | (-45.4562, 177.5885) | (-45.4562, 177.5885) | [S04](https://lroc.im-ldi.com/images/1168), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| CHANGE5 | (43.0576, -51.9161) | (43.0576, 308.0839) | [S05](https://lroc.im-ldi.com/images/1172.2020), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| CHANGE6 | (-41.6385, -153.9852) | (-41.6385, 206.0148) | [S06](https://lroc.im-ldi.com/images/1374), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| CHANDRAYAAN3 | (-69.3741, 32.32) | (-69.3741, 32.32) | [S07](https://lroc.im-ldi.com/images/1314), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| SLIM | (-13.316, 25.251) | (-13.3160, 25.2510) | [S08](https://lroc.im-ldi.com/images/1358), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| IM1 | (-80.13, 1.44) | (-80.13, 1.44) | [S09](https://lroc.im-ldi.com/images/1360), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| IM2 | (-84.7906, 29.1957) | (-84.7906, 29.1957) | [S10](https://lroc.im-ldi.com/images/1408), Lander statement/caption | Landed vehicle | 0.000 | PASS |
| BLUE_GHOST1 | (18.562, 61.81) | (18.562, 61.810) | [S11](https://lroc.im-ldi.com/images/1406), Lander statement/caption | Landed vehicle | 0.000 | PASS |

### Artemis region representative points (9)

| ID | Catalogue (N+, E+) | Source (N+, E+) | Source row / marker | Meaning | Δ m | Status |
|---|---|---|---|---|---:|---|
| ARTEMIS_CABEUS_B | (-83.763, -69.983) | (-83.7630, -69.9830) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), PCB01 | Representative CLS | 0.000 | REP |
| ARTEMIS_HAWORTH | (-86.768, -20.514) | (-86.7680, -20.5140) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), HW01 | Representative CLS | 0.000 | REP |
| ARTEMIS_MALAPERT | (-85.942, -0.944) | (-85.9420, -0.9440) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), MMA01 (Mons Malapert) | Representative CLS | 0.000 | REP |
| ARTEMIS_MOUTON_PLATEAU | (-85.111, 26.71) | (-85.1110, 26.7100) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), MMP01 | Representative CLS | 0.000 | REP |
| ARTEMIS_MOUTON | (-85.416, 31.851) | (-85.4160, 31.8510) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), MMO01 | Representative CLS | 0.000 | REP |
| ARTEMIS_NOBILE_RIM1 | (-85.295, 36.917) | (-85.2950, 36.9170) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), NR101 | Representative CLS | 0.000 | REP |
| ARTEMIS_NOBILE_RIM2 | (-84.054, 56.481) | (-84.0540, 56.4810) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), NR201 | Representative CLS | 0.000 | REP |
| ARTEMIS_DE_GERLACHE_RIM2 | (-88.389, -68.865) | (-88.3890, -68.8650) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), dGR201 | Representative CLS | 0.000 | REP |
| ARTEMIS_SLATER_PLAIN | (-87.478, 124.521) | (-87.4780, 124.5210) | [S12](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434), SP01 | Representative CLS | 0.000 | REP |

Each is a **representative research candidate landing point**. Table A1 supplies its CLS identifier; Appendix A and the site-selection sections define that role. The nine catalogue notes and “(region)” names preserve that qualification. MMA01 is under Mons Malapert in the paper; the catalogue uses the Malapert Massif region label. Neither label proves a mountain summit. This audit does not endorse a present-day NASA mission selection.

### Polar research and regional records (5)

| ID | Catalogue (N+, E+) | Source (N+, E+) | Source row / marker | Meaning | Δ m | Status |
|---|---|---|---|---|---:|---|
| SHACKLETON_RIM | (-89.6866, -162.81) | (-89.6866, 197.19) | [S13](https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf), Table 2, first S; p.12 | Rim research point | 0.000 | PASS |
| CONNECTING_RIDGE | (-89.4632, -137.49) | (-89.4632, -137.49) | [S14](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf), A2-2 R01; p.58 | DEM polygon centre | 0.000 | **FLAG** |
| PEAK_NEAR_SHACKLETON | (-88.811, 123.6901) | (-88.811, 123.6901) | [S14](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf), A2-2 R07; p.58 | DEM polygon centre | 0.000 | **FLAG** |
| DE_GERLACHE_RIM1 | (-88.6834, -67.9321) | (-88.6834, -67.9321) | [S14](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf), A2-2 R11; p.58 | DEM polygon centre | 0.000 | **FLAG** |
| SHOEMAKER_RIM_A | (-88.0792, 11.88866) | (-88.0792, 11.88866) | [S14](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf), A2-2 LM2; p.57 | DEM polygon centre | 0.000 | **FLAG** |

### Planned science target (1)

| ID | Catalogue (N+, E+) | Source (N+, E+) | Source row / marker | Meaning | Δ m | Status |
|---|---|---|---|---|---:|---|
| IM3_REINER_GAMMA | (7.585, -58.725) | (7.585, -58.725) | [S15](https://www.frontiersin.org/journals/astronomy-and-space-sciences/articles/10.3389/fspas.2022.926018/full), Fig.3 (also 9/10) | Planned LVx target | 0.000 | TARGET |

## Source context that prevents the wrong-point interpretation

| Source | Coordinate statement and definition checked |
|---|---|
| S01 | Use the Lunar Module row for each Apollo mission, not ALSEP or the reflector. The page explicitly names the DE421 mean-Earth reference system. |
| S02 | Use the Luna 16/20/24 soft-landing rows, not rover paths or impact rows. |
| S03 | The paragraph deriving the Chang'e-3 lander position distinguishes lander from rover and nearby crater. |
| S04 | The refined coordinate belongs to the Chang'e-4 lander; rover travel/distance is separate. Reported uncertainty: 13 m (95%). |
| S05 | Chang'e-5 lander coordinate, not the centre of a crater triangle; reported horizontal accuracy ±20 m. |
| S06 | Chang'e-6 lander, not Apollo basin centre; reported horizontal accuracy ±30 m. |
| S07 | Caption associates the coordinate with the box containing the landed Chandrayaan-3 vehicle. |
| S08 | Lead caption identifies SLIM on the surface, not its intended target or Shioli crater. |
| S09 | IM-1 final resting location; only two decimal places. Do not infer survey precision from the 0 m transcription offset. |
| S10 | IM-2 final surface position on its side inside a small crater; not the earlier target. |
| S11 | Blue Ghost's pixel/box coordinate; the next paragraph separately gives LRO's imaging position. Neither the volcanic-cone centre nor that LRO position was used. |
| S12 | Table A1 IDs identify representative candidates. Region names and candidate-point coordinates are not interchangeable. |
| S13 | Table 2 first S row selects a particular research point. Section 3 and Fig.6c identify rim context; no unique summit or landed vehicle is claimed. The second S row is a different point. |
| S14 | Paragraph immediately above Table A2-2 defines coordinates as centre points of DEM polygons. Its 5–10 m statement concerns those centres, not distance from a summit. |
| S15 | Figure 3's star denotes a proposed LVx landing target; figures 9/10 corroborate the pair. It is not a geometric centre of the Reiner Gamma swirl or a confirmed touchdown. |

## Decision requested from Sua — four flags

| ID | Meaning risk | Proposed resolution for discussion only |
|---|---|---|
| CONNECTING_RIDGE | Region-centre versus ridge-point wording | Qualify visible name as a regional/DEM centre (R01). |
| PEAK_NEAR_SHACKLETON | Centre does not establish a summit | Qualify the representative centre; avoid an exact-peak implication. |
| DE_GERLACHE_RIM1 | Centre does not establish rim-crest placement | Qualify the regional centre (R11). |
| SHOEMAKER_RIM_A | Centre does not establish rim-crest placement | Qualify the regional centre (LM2). |

The existing note is a useful disclosure, but a visible label/group should convey the same meaning. Renaming/qualification can preserve existing calculations; moving a coordinate requires an agreed, specific feature-point source and downstream horizon/metrics/window invalidation and revalidation. Do not automatically substitute another paper's similarly named site. **No change proposed here has been applied to sites.json.**

## Source access register

| Source | Primary URL opened | Exact review location |
|---|---|---|
| S01 — NSSDCA Apollo LM table | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | Six LM rows; opened successfully 2026-11-14 |
| S02 — NSSDCA spacecraft / impact table | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html | Luna 16, 20, 24 rows; opened successfully 2026-11-14 |
| S03 — LROC Chang'e 3 lander/rover | https://lroc.im-ldi.com/images/637 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S04 — LROC Chang'e 4 refined lander | https://lroc.im-ldi.com/images/1168 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S05 — LROC Chang'e 5 first look | https://lroc.im-ldi.com/images/1172.2020 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S06 — LROC Chang'e 6 first look | https://lroc.im-ldi.com/images/1374 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S07 — LROC Chandrayaan-3 landing | https://lroc.im-ldi.com/images/1314 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S08 — LROC SLIM landing | https://lroc.im-ldi.com/images/1358 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S09 — LROC IM-1 landed position | https://lroc.im-ldi.com/images/1360 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S10 — LROC IM-2 Athena surface position | https://lroc.im-ldi.com/images/1408 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S11 — LROC Blue Ghost oblique view | https://lroc.im-ldi.com/images/1406 | Coordinate paragraph/image caption identified above; opened successfully 2026-11-14 |
| S12 — Wueller et al. (2026), Appendix A | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | Appendix A, Table A1 (PCB01/HW01/MMA01/MMP01/MMO01/NR101/NR201/dGR201/SP01); opened successfully 2026-11-14 |
| S13 — Gläser et al. (2017), Table 2 | https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf | Printed p.12 Table 2; section 3 and Fig.6c (printed p.16); opened successfully 2026-11-14 |
| S14 — NASA ACD-50044 Rev A, pp.57-58 | https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf | Printed pp.57-58, definition and Table A2-2; opened successfully 2026-11-14 |
| S15 — Waller et al. (2022), figure captions | https://www.frontiersin.org/journals/astronomy-and-space-sciences/articles/10.3389/fspas.2022.926018/full | Figures 3, 9 and 10 captions; opened successfully 2026-11-14 |

## Recompute the recorded numerical offsets

Run from the repository root with Python (standard library only). This checks arithmetic against the transcribed evidence; it does not independently validate the original prose definitions.

```python
import json, math
from decimal import Decimal as D
from pathlib import Path
s = {x["id"]: x for x in json.loads(Path("web/data/sites.json").read_text(encoding="utf-8"))}
a = json.loads(Path("docs/site_coordinate_audit.json").read_text(encoding="utf-8"))
assert len(s) == len(a["rows"]) == 33
for r in a["rows"]:
    p = s[r["id"]]
    x, y = D(r["source_latitude_north_positive_deg"]), D(r["source_longitude_east_positive_deg"])
    while y > 180: y -= 360
    while y < -180: y += 360
    dp = math.radians(float(D(str(p["lat"])) - x))
    dl = D(str(p["lon"])) - y
    while dl > 180: dl -= 360
    while dl < -180: dl += 360
    dl = math.radians(float(dl))
    h = math.sin(dp/2)**2 + math.cos(math.radians(float(x))) * math.cos(math.radians(p["lat"])) * math.sin(dl/2)**2
    d = 2*a["radius_m"]*math.atan2(math.sqrt(max(0,h)), math.sqrt(max(0,1-h)))
    assert abs(d-r["source_pair_distance_m"]) < 1e-6, r["id"]
print("33 offsets reproduced; semantic flags remain for human/team decision")
```

## Scope and review status

Completed by AI: fresh primary-source reading, visual PDF table inspection, role classification and decimal-normalized distance calculation. Independent human re-review and Sua's disposition of the four label flags are **not yet reported**. No fabricated human PASS is entered. The user's standing authorization allows evidence-based completion of their own SI cells.

No DEM crest/summit survey, source-datum transformation, new Horizons query, mission-target update or complete UI audit was performed. Matching source coordinates does not verify all points are in an identical precise reference frame. Heights remain outside this audit. Rows with a representative/centre/target meaning must retain that qualification wherever their metrics are presented. This report is valid for the pinned catalogue; a catalogue/source change requires review of the affected rows.
