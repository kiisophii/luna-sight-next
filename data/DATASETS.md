# Data sources

Add each dataset the moment you use it: name, URL, resolution, size, license, citation, where it is used.

| Dataset | URL | Resolution / size | License | Citation | Used for |
|---|---|---|---|---|---|
| PGDA LOLA south polar DEMs 5 / 10 / 20 / 60 / 80 / 240 m (via card 2 caches) | https://pgda.gsfc.nasa.gov/products/81 (5 m), https://pgda.gsfc.nasa.gov/products/90 (10–240 m); files under https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/ and /data/LOLA_20mpp/ | 5–240 m/px windows (3–200 km radius) around each site south of -80°; polar stereographic, R = 1737.4 km | NASA PGDA public distribution; attribution requested | Barker et al. 2021, doi:10.1016/j.pss.2020.105119; Barker et al. 2023, doi:10.3847/PSJ/acf3e1 | Phase 2 horizon engine (pipeline/horizon.py): finest-first near-field terrain for polar sites → web/data/horizon/<ID>.json |
| SLDEM2015 512 ppd (via card 3 caches) | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/tiles/float_img/ | 59 m/px, ±150 km window per site, 60 S..60 N | NASA PDS public archive (no use restriction found; unverified) | Barker et al. 2016, Icarus 273, 346-355, doi:10.1016/j.icarus.2015.07.039 | Phase 2 horizon engine: near-field terrain for non-polar sites (to 150 km) |
| LOLA GDR LDEM_64 / LDEM_16 float (via card 3 caches) | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ | 474 m/px and 1895 m/px global grids | NASA PDS public archive (no use restriction found; unverified) | Smith et al. 2010, GRL 37, L18204, doi:10.1029/2010GL043751 | Phase 2 horizon engine: far-field terrain out to 300 km (LDEM_64 preferred, LDEM_16 fallback) |
