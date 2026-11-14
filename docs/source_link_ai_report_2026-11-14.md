# 출처 링크 점검 결과 (카드 15)

> **AI(Claude)가 2026-11-14에 자동 확인, 사람 확인 아님.** 사람이 브라우저로 직접 여는 확인(체크리스트의 Human opened?)은 여전히 필요하다.

- 대상: `origin/s3-shackleton-minchul`의 `docs/source_link_checklist.md` 65개 URL (data/DATASETS.md + web/data/sites.json의 33개 source_url)
- 방법: curl(브라우저 UA)로 모두 요청. 큰 DEM/IMG/BSP/TIF는 `Range: bytes=0-1023`만 받아 응답 코드·파일 형식·전체 크기(Content-Range)를 확인. HTML은 제목과 본문 문장, PDF(5개)는 내려받아 텍스트를 추출해 표·좌표를 대조.
- **요약: PASS 62 · BROKEN 2 · MISMATCH 0 · UNRESOLVED 1** (65개)
  - 별도로 URL은 정상이지만 DATASETS.md 26행 설명이 낡은 문제 1건 (아래 문제 3)
  - 사이트 좌표: 확인 가능한 24개 사이트는 모두 페이지 숫자와 0.01° 이내 일치(대부분 소수점까지 똑같음). Artemis 9개 지역(Wiley 논문)은 차단 때문에 좌표 미확인.

| # | URL | 무엇의 출처 | 판정 | 근거(페이지에서 확인한 내용 한 줄) |
|---:|---|---|---|---|
| 1 | http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.LBL | AVGVISIB 85S 60 m 라벨 (L43) | PASS | PDS3 라벨, PRODUCT_ID = "AVGVISIB_85S_060M_201608", LOLA |
| 2 | https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JE009434 | Wueller et al. 2026 Table A1, Artemis 9개 지역 대표점 (L25) | UNRESOLVED | Wiley 403(Cloudflare "Just a moment"). Crossref·OpenAlex·Semantic Scholar로 DOI가 "Assessing Potential Landing Sites… Within Artemis Candidate Landing Regions", Wueller·Berger 외, JGR Planets, 2026-02-27, CC BY 4.0임을 확인. Table A1 좌표 9쌍은 미확인 |
| 3 | https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301P.pdf | DSN 810-005 301 Rev. P Table 5 (L63) | PASS | PDF 첫 쪽 "DSN No. 810-005, 301, Rev. P", Table 5 "Geodetic Coordinates for DSN Stations … WGS 84", DSS 14 행 존재 |
| 4 | https://doi.org/10.1038/s41467-019-12278-3 | 창어 4호 논문 검증점 (L13) | PASS | Nature Comms "Descent trajectory reconstruction and landing site positioning of Chang'E-4", 177.5991°E 45.4446°S |
| 5 | https://doi.org/10.3847/1538-3881/abd414 | DE440 인용 (L7) | PASS | IOPscience "The JPL Planetary and Lunar Ephemerides DE440 and DE441" |
| 6 | https://lroc.im-ldi.com/images/1168 | CHANGE4 (-45.4562, 177.5885) | PASS | "Keeps on Roving!": refined lander 45.4562°S, 177.5885°E, 13 m(95%) — 좌표 일치 |
| 7 | https://lroc.im-ldi.com/images/1172.2020 | CHANGE5 (43.0576, -51.9161) | PASS | "First Look: Chang'e 5": 43.0576°N, 308.0839°E(=-51.9161), ±20 m — 일치 |
| 8 | https://lroc.im-ldi.com/images/1314 | CHANDRAYAAN3 (-69.3741, 32.32), 검증점 | PASS | "Chandrayaan-3 Landing Site": 69.3741°S, 32.32°E — 일치 |
| 9 | https://lroc.im-ldi.com/images/1358 | SLIM (-13.316, 25.251) | PASS | "JAXA SLIM Landing": 13.3160°S, 25.2510°E — 일치 |
| 10 | https://lroc.im-ldi.com/images/1360 | IM1 (-80.13, 1.44) | PASS | "Intuitive Machines IM-1 On The Moon!": 80.13°S, 1.44°E — 일치 |
| 11 | https://lroc.im-ldi.com/images/1374 | CHANGE6 (-41.6385, -153.9852) | PASS | "First Look: Chang'e 6": 41.6385°S, 206.0148°E(=-153.9852), ±30 m — 일치 |
| 12 | https://lroc.im-ldi.com/images/1406 | BLUE_GHOST1 (18.562, 61.81) | PASS | "Blue Ghost Seen Obliquely": 18.562°N, 61.810°E — 일치(LRO 위치 19.294N 67.956E와 구분됨) |
| 13 | https://lroc.im-ldi.com/images/1408 | IM2 (-84.7906, 29.1957) | PASS | "IM-2 Athena Seen Obliquely": 84.7906°S, 29.1957°E — 일치 |
| 14 | https://lroc.im-ldi.com/images/637 | CHANGE3 (44.1214, -19.5116) | PASS | "Chang'e 3 Lander and Rover From Above": 44.1214°N, 340.4884°E(=-19.5116) — 일치 |
| 15 | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/ | NAIF 커널 묶음 (L61) | PASS | 디렉터리 목록(fk/ lsk/ pck/ spk/ …) |
| 16 | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf | Lunar FK (L9) | PASS | "SPICE Lunar Reference Frame Specification Kernel", 원파일명 moon_080317.tf |
| 17 | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls | LSK (L11) | PASS | 텍스트 LSK, 2016-12-31 윤초 기록 포함 |
| 18 | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/a_old_versions/pck00008.tpc | PCK 00008 (L10) | PASS | "KPL/PCK … P_constants (PcK) SPICE kernel file" |
| 19 | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de421_1900-2050.bpc | DE421 달 자세 (L8) | PASS | 206, 전체 1,770,496 B — DATASETS 크기와 동일 |
| 20 | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp | DE440s (L7) | PASS | 206, 전체 32,726,016 B — DATASETS 크기와 동일 |
| 21 | https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf | KDSA 위치 (L62) | PASS | kdsa01.tf, 2021-03-08 생성, Lon 127.62181206, Lat 37.20723347, Alt 0.145359 km — 일치 |
| 22 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html | LUNA16/20/24 (L15) | PASS | 표: Luna 16 0.5137S 56.3638E, Luna 20 3.7863N 56.6242E, Luna 24 12.7142N 62.2129E — 3개 모두 일치 |
| 23 | https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html | APOLLO11–17 LM, Apollo 17 검증점 (L13, L14) | PASS | Wagner et al. 2017 표의 Lunar Module 행 6개(0.67416/23.47314 … 20.1911/30.7723) — 모두 일치 |
| 24 | https://ntrs.nasa.gov/api/citations/20170007365/downloads/20170007365.pdf | SHACKLETON_RIM (-89.6866, -162.81) (L72) | PASS (주의) | Gläser et al. "Illumination conditions at the lunar poles" Table 2(p.12)에 -89.6866, 197.19(=-162.81) 있음. 텍스트 추출 시 이름 열이 밀려 "Connecting Ridge, C2" 옆에 찍히지만, 남극 4행 중 3번째 행이고 Shackleton 중심(-89.67, 129.8E)에서 약 10.8 km(=림 반경)라 Shackleton S 행으로 판단. 사람이 PDF 12쪽을 눈으로 한 번 확인 권장 |
| 25 | https://ntrs.nasa.gov/api/citations/20230000531/downloads/Blewett_LVx-CP11_landingsite_LPSC2023_abstr1780.pdf | CP-11 착륙점 7.585N 58.725W (L66) | PASS | Blewett et al. LPSC 초록 "…MISSION CP-11", "selected is at 7.585° N, 58.725° W" |
| 26 | https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf | R01·R07·R11·LM2 사이트 (L26), R04 검증점 | PASS | ACD-50044 Rev A Table A2-2(pp.57–58): R01 Connecting Ridge -89.4632/-137.49, R07 -88.811/123.6901, R11 -88.6834/-67.9321, LM2 -88.0792/11.88866, R04 -89.7668/-171.87 — 모두 일치 (단 DATASETS 26행 설명은 문제 3 참고) |
| 27 | https://ntrs.nasa.gov/api/citations/20250002845/downloads/M2M-30044%20Lunar%20Surface%20Data%20Book%20Baseline_Final.pdf | Site04 기준좌표 p.75 (L36) | PASS | M2M-30044 Baseline, p.75 "R04 or Site04 Shackleton Rim -89.7668 -171.87" |
| 28 | https://ntrs.nasa.gov/citations/20170007365 | Gläser 논문 레코드 (L72) | PASS | NTRS "Illumination Conditions at the Lunar Poles: Implications for Future Exploration" |
| 29 | https://ntrs.nasa.gov/citations/20230007818 | ACD-50044 레코드 (L13) | PASS | NTRS "Lunar Surface Data Book" |
| 30 | https://ntrs.nasa.gov/citations/20240014584 | BEACON 개념 (L60) | PASS | NTRS "BEACON Demonstrator": "15 m deployed boom", 3GPP "users up to 10 km away, dependent on terrain" |
| 31 | https://pda.kasi.re.kr/lusem.php?lang=en | KASI LUSEM (L29) | PASS | "Landing site: Reiner Gamma", "Nova-C lander … CP-11 (or IM-3)" |
| 32 | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ | LDEM_16/64 float 디렉터리 (L49,50,55,68) | PASS | 목록에 ldem_16_float.img/.lbl, ldem_64_float.img/.lbl 있음 |
| 33 | …/cylindrical/float_img/ldem_16_float.img | LDEM_16 float (L38, L70) | PASS | 206, 전체 66,355,200 B — 일치 |
| 34 | …/cylindrical/float_img/ldem_64_float.img | LDEM_64 float (L39, L57, L69) | PASS | 206, 전체 1,061,683,200 B — 일치 |
| 35 | …/cylindrical/img/ldem_64.img | LDEM_64 int16 (L41) | PASS | 206, 전체 530,841,600 B — 일치 |
| 36 | …/polar/float_img/ldem_45s_400m_float.img | LDEM_45S_400M (L42) | PASS | 206, 전체 207,360,000 B — 일치 |
| 37 | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/ | SLDEM2015 타일 (L40, L48, L58) | PASS | 목록에 sldem2015_512_*_float.img 32개 — "32 tiles"와 일치 |
| 38 | https://pds.shadowcam.asu.edu/ | ShadowCam PDS (L65) | PASS (리다이렉트) | https://pds.shadowcam.im-ldi.com/ 로 이동, 목록에 bundle_kplo-shadowcam.xml, derived/ 등 |
| 39 | https://pds.shadowcam.asu.edu/bundle_kplo-shadowcam.xml | ShadowCam 번들 (L65) | PASS (리다이렉트) | im-ldi.com으로 이동, urn:nasa:pds:kplo-shadowcam, "KPLO ShadowCam Data Archive", DOI 10.17189/y89z-kt98 |
| 40 | https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/ | PGDA 20mpp 파일 폴더 (L59, L68) | BROKEN (soft 404) | HTTP 200이지만 본문이 "PGDA - Not Found … 404". 폴더 안 개별 TIF(41–45)는 정상 |
| 41 | https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_60S_240MPP_ADJ.TIF | 240 m DEM (L35, L53) | PASS | 206 image/tiff, 218,961,039 B(제품 페이지 "210M"과 맞음) |
| 42 | …/LOLA_20mpp/LDEM_60S_60MPP_ADJ.TIF | 60 m DEM (L33, L53) | PASS | 206 image/tiff, 3,089,110,093 B |
| 43 | …/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF | 20 m DEM (L32) | PASS | 206 image/tiff, 2,696,082,051 B; products/90에 파일명 명시 |
| 44 | …/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF | 80 m DEM (L34) | PASS | 206 image/tiff, 189,158,392 B |
| 45 | …/LOLA_20mpp/LDEM_83S_10MPP_ADJ.TIF | 10 m DEM (L31) | PASS | 206 image/tiff, 5,116,709,568 B |
| 46 | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/ | 5 m 폴더 (L47) | PASS | "South Pole Landing Site LOLA DEMs" 안내 + README, Site01/04/07… 목록 |
| 47 | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/ldem_87s_5mpp.tif | 5 m DEM (L30) | PASS | 206 image/tiff, 3,465,285,714 B (products/81 "3.3GB"와 일치) |
| 48 | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/Site04_final_adj_5mpp_surf.tif | Site04 5 m DEM (L37) | PASS | 206 image/tiff, 40,980,806 B; products/78에 같은 파일명 |
| 49 | https://pgda.gsfc.nasa.gov/data/MoonIllumination/ | 조명지도 파일 폴더 (L51) | BROKEN (soft 404) | HTTP 200이지만 본문 "PGDA - Not Found … 404". 개별 TIF(50–53)는 정상 |
| 50 | …/MoonIllumination/AVGVISIB_75S_120M_201608.TIF | 75S 태양 (L45) | PASS | 206 image/tiff, 83,052,039 B("83 MB" 일치) |
| 51 | …/MoonIllumination/AVGVISIB_75S_120M_201608_EARTH.TIF | 75S 지구 (L46) | PASS | 206 image/tiff, 43,148,153 B("43 MB" 일치) |
| 52 | …/MoonIllumination/AVGVISIB_85S_060M_201608.TIF | 85S 태양 (L43) | PASS | 206 image/tiff, 33,994,464 B("34 MB" 일치) |
| 53 | …/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF | 85S 지구 (L44) | PASS | 206 image/tiff, 24,862,958 B("25 MB" 일치) |
| 54 | https://pgda.gsfc.nasa.gov/products/69 | 조명지도 제품 페이지 (L43, L51) | PASS | "Lunar Polar Illumination", Mazarico 2011 Icarus 211 인용 요청 |
| 55 | https://pgda.gsfc.nasa.gov/products/78 | Site04 DEM 제품 (L37) | PASS | "High-Resolution LOLA Topography for Lunar South Pole Sites", "Site04: Shackleton rim", Site04_final_adj_5mpp_surf.tif |
| 56 | https://pgda.gsfc.nasa.gov/products/81 | 5 m 모자이크 제품 (L30, L47) | PASS | "South Pole LOLA DEM Mosaic", ldem_87s_5mpp 3.3GB, Barker et al. 2021 |
| 57 | https://pgda.gsfc.nasa.gov/products/90 | 10–240 m DEM 제품 (L31–35 등) | PASS | "A New View of the Lunar South Pole from LOLA", LDEM_80S_20MPP_ADJ 등 파일명, Barker 2023 PSJ 4,183 (doi …/acf3e1) |
| 58 | https://planetarynames.wr.usgs.gov/Feature/5450 | IAU Shackleton (L67) | PASS | Feature Name Shackleton, Feature ID 5450, Moon, Crater |
| 59 | https://science.nasa.gov/lunar-science/clps-deliveries/cp-11/ | CP-11 탑재체 목록 (L66) | PASS | "CP-11 Science Payloads": KASI LUSEM, PI Young-Jun Choi |
| 60 | https://ssd-api.jpl.nasa.gov/doc/horizons.html | Horizons API 문서 (L12, L52) | PASS | "Horizons API Version 1.3 (2025 June)" 문서 |
| 61 | https://ssd.jpl.nasa.gov/api/horizons.api | Horizons API 엔드포인트 (L12, L52, L64) | PASS | 파라미터 없이 JSON 응답 "Missing COMMAND specification" (정상 API 동작) |
| 62 | https://svs.gsfc.nasa.gov/4720 | CGI Moon Kit (L56) | PASS | "NASA SVS / CGI Moon Kit", 다운로드 목록에 lroc_color_poles_8k.tif |
| 63 | https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_8k.tif | 색 지도 파일 (L56) | PASS | 206 image/tiff, 50,641,970 B |
| 64 | https://www.frontiersin.org/journals/astronomy-and-space-sciences/articles/10.3389/fspas.2022.926018/full | IM3_REINER_GAMMA (7.585, -58.725) (L27) | PASS | "Ultraviolet and magnetic perspectives at Reiner Gamma…": "LVx landing site (7.585°N, 58.725°W)" 여러 번 — 일치 |
| 65 | https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/ | Artemis 9개 지역 목록 (L28) | PASS | 9개 지역명(Peak near Cabeus B … Slater Plain)이 sites.json의 ARTEMIS_* 9개와 같음 |

## 사람 확인이나 Issue가 필요한 것

### 문제 1 · 2 — PGDA 폴더 링크 2개가 404 페이지 (BROKEN, Issue 권장)

`/data/LOLA_20mpp/`와 `/data/MoonIllumination/`은 HTTP 200을 주지만 내용은 PGDA 404 페이지다. 안의 개별 파일은 모두 정상이라 데이터 자체는 문제없다. 제품 페이지(products/90, products/69)로 바꾸는 게 맞다. 사람이 브라우저로 열어 404 화면을 확인한 뒤 올린다.

```
Title: [Card 15 sources] Broken or misdirected source: https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/ and https://pgda.gsfc.nasa.gov/data/MoonIllumination/

Body:
Original URLs:
- https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/  (data/DATASETS.md L59, L68)
- https://pgda.gsfc.nasa.gov/data/MoonIllumination/  (data/DATASETS.md L51)

Human review: <name>, <date>, <browser>
Observed: both URLs return HTTP 200 but the body is the PGDA "Not Found / 404" page (no directory listing).
The individual files under them do resolve (e.g. LDEM_80S_20MPP_ADJ.TIF, AVGVISIB_85S_060M_201608.TIF return image/tiff with the expected sizes), so the data provenance is intact; only the folder links are dead.

Expected source: a page that lists the files.
Verified replacement:
- LOLA_20mpp folder -> https://pgda.gsfc.nasa.gov/products/90 (lists LDEM_80S_20MPP_ADJ.TIF, LDEM_60S_240MPP_ADJ.TIF etc.)
- MoonIllumination folder -> https://pgda.gsfc.nasa.gov/products/69 (Lunar Polar Illumination, AVGVISIB downloads)
Proposal: keep the direct file URLs; replace the two folder links with the product pages (or write "files under products/90" in text without a link).
```

### 문제 3 — DATASETS.md 26행 설명이 SHACKLETON_RIM을 아직 ACD-50044에 묶어 둠 (문서 불일치, Issue 권장)

sites.json의 SHACKLETON_RIM은 이제 Gläser et al. NTRS 20170007365(-89.6866, -162.81)를 가리키는데, DATASETS.md 26행(ACD-50044 Rev A)은 여전히 "5 published coordinate pair(s)"와 used-for에 `SHACKLETON_RIM`을 적고 있다. ACD-50044에 실제로 들어 있는 건 R04(-89.7668, -171.87)이고 지금 사이트 좌표가 아니다. 72행(새 출처)과 겹쳐 심사자가 헷갈릴 수 있다.

```
Title: [Card 15 sources] DATASETS.md ACD-50044 row still lists SHACKLETON_RIM after source change

Body:
File: data/DATASETS.md L26 (NASA ACD-50044 Rev A, Table A2-2)
URL: https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf (link itself OK)

Problem: the row says "5 published coordinate pair(s)" and its used-for column includes web/data/sites.json SHACKLETON_RIM.
But sites.json SHACKLETON_RIM now uses -89.6866, -162.81 from Glaser et al. (NTRS 20170007365, Table 2), recorded in DATASETS.md L72.
ACD-50044 Table A2-2 only contains R04 Shackleton Rim -89.7668, -171.87, which is no longer the catalogue coordinate.

Fix: change L26 to 4 coordinate pairs (CONNECTING_RIDGE R01, PEAK_NEAR_SHACKLETON R07, DE_GERLACHE_RIM1 R11, SHOEMAKER_RIM_A LM2) and drop SHACKLETON_RIM; keep the R04 mention only where it is used as a validation point (L13). Also re-check docs/sites_source_audit.json for the same stale entry.
Checked: ACD-50044 pp.57-58 values for R01/R07/R11/LM2 match sites.json exactly.
```

### 사람 확인만 필요 (Issue 아님)

- **#2 Wiley 논문 (Artemis 9개 지역 좌표)** — 봇 차단(Cloudflare)으로 열리지 않음. DOI·제목·저자·CC BY 4.0은 Crossref/OpenAlex로 확인됨. 사람이 브라우저로 Appendix Table A1을 열어 PCB01, HW01, MMA01, MMP01, MMO01, NR101, NR201, dGR201, SP01의 위·경도 9쌍을 sites.json과 대조해야 한다. 차단만으로는 Issue를 올리지 않는다.
- **#24 Gläser 2017 Table 2** — 값은 표에 있으나 PDF 텍스트 정렬상 이름 열이 한 줄 어긋나 보인다. 기하 계산으로는 Shackleton 림이 맞다. 12쪽을 눈으로 한 번 보고 "Shackleton, S" 첫 행이 -89.6866 / 197.19인지 확인.
- **#38, #39 ShadowCam** — `pds.shadowcam.asu.edu`가 `pds.shadowcam.im-ldi.com`으로 리다이렉트된다. 지금은 동작하므로 문제는 아니고, 원하면 새 주소를 함께 적어 둔다.
