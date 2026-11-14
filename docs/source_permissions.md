# KDSA / ShadowCam source status

Status (corrected 2026-11-14 KST): **no permission was requested and none is claimed.**

| Resource | Status | Current implementation |
|---|---|---|
| KDSA station coordinates (kdsa01.tf) | Station coordinates taken from the publicly released SPICE frame kernel kdsa01.tf (KARI, 2021-03-08), distributed by NASA/JPL NAIF at https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf; factual coordinates used with citation; no separate permission was requested. | Station coordinates and numerical direct-link calculations (`web/data/korea/stations.json`, Korea panel). |
| ShadowCam (NASA/KARI/ASU, PDS archive) | Links and label metadata only; no ShadowCam images are redistributed (credit NASA/KARI/ASU; no separate permission was requested). | Archive links and PDS label metadata in `web/data/korea/korea.json`; no image files are downloaded, rehosted or overlaid. |

Sources: [kdsa01.tf](https://naif.jpl.nasa.gov/pub/naif/pds/wgc/lessons/event_finding_kplo/kernels/fk/kdsa01.tf), [ShadowCam archive](https://pds.shadowcam.asu.edu/), [archive DOI](https://doi.org/10.17189/y89z-kt98).

**Correction.** An earlier version of this file (PR #36) recorded a "PROJECT USE APPROVED (user-relayed)" status for both items. That was a
misunderstanding: Sua Kim confirmed on 2026-11-14 that the Seoul organisers / mentors were never asked. No approval exists, and none is
claimed anywhere in the repository. Keep NASA/KARI/ASU and NAIF source credits; nothing here relicenses third-party material.
