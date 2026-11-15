"""Independently read source transcriptions for Task R; not production catalogue imports.

Coordinates are landers (not rover/target/orbiter positions), degrees north/east.
Source numbers were independently read on 2026-11-15. Short paraphrases avoid
reproducing articles; URL byte hashes are recorded by task_r_audit.py.
"""
APOLLO_COORD = 'https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html'
LUNA_COORD = 'https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html'
LUNA_TIME = 'https://nssdc.gsfc.nasa.gov/planetary/lunar/lunarussr.html'
ALSJ = 'https://apollojournals.org/alsj/alsj-EarthSun_AltAz.html'
LROC = 'https://lroc.im-ldi.com/images/'


def record(sid, utc, lat, lon, coord_url, time_url, precision='minute', note='', **extra):
    return dict(id=sid, landing_utc=utc, lat=lat, lon=lon,
                coordinate_source=coord_url, time_source=time_url,
                time_precision=precision, note=note, **extra)


SOURCES = [
    record('APOLLO11', '1969-07-20T20:17:39Z', .67416, 23.47314, APOLLO_COORD, ALSJ, 'second', alsj_point=[.6875,23.4333], alsj_sun_deg=10.65),
    record('APOLLO12', '1969-11-19T06:54:36Z', -3.0128, -23.4219, APOLLO_COORD, ALSJ, 'second', alsj_point=[-3.1975,-23.3856], alsj_sun_deg=5.19),
    record('APOLLO14', '1971-02-05T09:18:13Z', -3.64589, -17.47194, APOLLO_COORD, ALSJ, 'second', alsj_point=[-3.6733,-17.4653], alsj_sun_deg=10.36),
    record('APOLLO15', '1971-07-30T22:16:29Z', 26.13239, 3.6333, APOLLO_COORD, ALSJ, 'second', alsj_point=[26.1008,3.6528], alsj_sun_deg=12.05),
    record('APOLLO16', '1972-04-21T02:23:35Z', -8.9734, 15.5011, APOLLO_COORD, ALSJ, 'second', alsj_point=[-8.9914,15.5144], alsj_sun_deg=14.76),
    record('APOLLO17', '1972-12-11T19:54:58Z', 20.1911, 30.7723, APOLLO_COORD, ALSJ, 'second', alsj_point=[20.1653,30.7658], alsj_sun_deg=13.33),
    record('LUNA16', '1970-09-20T05:18:00Z', -.5137,56.3638,LUNA_COORD,LUNA_TIME,'minute', 'Legacy mission page coordinates differ from LRO coordinates; latter used.'),
    record('LUNA20', '1972-02-21T19:19:00Z',3.7863,56.6242,LUNA_COORD,LUNA_TIME,'minute', 'NASA Beyond Earth gives 19:19:09 UT, compatible with minute precision.', alternate_utc='1972-02-21T19:19:09Z', alternate_source='https://www.nasa.gov/wp-content/uploads/2018/09/beyond-earth-tagged.pdf'),
    record('LUNA24','1976-08-18T06:36:00Z',12.7142,62.2129,LUNA_COORD,'https://www.nasa.gov/wp-content/uploads/2023/04/1976.pdf','minute','Unresolved NASA source conflict: chronology August entry 06:36 GMT versus NSSDCA summary 02:00 UT. Compute both; do not declare source agreement.',alternate_utc='1976-08-18T02:00:00Z',alternate_source=LUNA_TIME),
    record('CHANGE3','2013-12-14T13:11:00Z',44.1214,-19.5116,LROC+'637','https://www.cnsa.gov.cn/n6758968/n6758972/c6798565/content.html','minute','21:11 Beijing time minus 8 h; longitude 340.4884 E minus 360.'),
    record('CHANGE4','2019-01-03T02:26:00Z',-45.4562,177.5885,LROC+'1168',LROC+'1168','minute','Refined LROC location; 13 m horizontal uncertainty, 95% confidence.'),
    record('CHANGE5','2020-12-01T15:11:00Z',43.0576,-51.9161,LROC+'1172.2020',LROC+'1172.2020','minute','Longitude 308.0839 E minus 360; horizontal accuracy +/-20 m.'),
    record('CHANGE6','2024-06-01T22:23:00Z',-41.6385,-153.9852,LROC+'1374','https://www.cnsa.gov.cn/n6758823/n6758838/c10541444/content.html','minute','June 2 06:23 Beijing minus 8 h is June 1 UTC; longitude 206.0148 E minus 360; horizontal accuracy +/-30 m.'),
    record('CHANDRAYAAN3','2023-08-23T12:34:00Z',-69.3741,32.32,LROC+'1314','https://www.eoibahrain.gov.in/pdf/PR-%20Chandrayaan%203sd.pdf','minute','Indian government post-event release: 18:04 IST minus 5h30. ISRO mission page confirms date but its 18:04 schedule is a prediction, not used as measured time.'),
    record('SLIM','2024-01-19T15:20:00Z',-13.3160,25.2510,LROC+'1358',LROC+'1358'),
    record('IM1','2024-02-22T23:23:53Z',-80.13,1.44,LROC+'1360',LROC+'1360','second','Coordinates only 0.01 degree precision; no metre-level accuracy implied.'),
    record('IM2','2025-03-06T17:28:00Z',-84.7906,29.1957,LROC+'1408','https://ntrs.nasa.gov/api/citations/20260003150/downloads/MSolo%20PRIME-1%20overview%20and%20results%20-%20LSSW.pdf','minute','PRIME-1 science-team slide 2 distinguishes target from actual site; NASA initial blog rounds to approximately 17:30 UTC. Lander on side in crater.',alternate_utc='2025-03-06T17:30:00Z',alternate_source='https://www.nasa.gov/blogs/missions/2025/03/06/intuitive-machines-mission-lands-near-south-pole-carrying-nasa-science/'),
    record('BLUE_GHOST1','2025-03-02T08:34:00Z',18.562,61.810,LROC+'1406','https://fireflyspace.com/missions/blue-ghost-mission-1/','minute','02:34 CST plus 6 h; use lander coordinates, not LRO observer position.'),
]
