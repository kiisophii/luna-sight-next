"""Write MOCK data files for the web app (card 6).

Every file gets "mock": true. Real pipelines (cards 1-5) overwrite them with the same
names and formats (docs/data_contract.md v1). Nothing here is a real measurement:
the ephemeris is a simple analytic toy model (circular orbits, rough librations) just so
the UI has something that moves. Do NOT quote any number produced from these files.

Run:  python pipeline/make_mocks.py
"""
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "data"

SITES = [
    {"id": "APOLLO17", "name": "Apollo 17", "name_ko": "아폴로 17호", "short": "Apollo 17",
     "group": "apollo", "lat": 20.1908, "lon": 30.7717, "elev_m": None,
     "source_url": "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html"},
    {"id": "CHANGE4", "name": "Chang'e 4", "name_ko": "창어 4호", "short": "Chang'e 4",
     "group": "change", "lat": -45.4446, "lon": 177.5991, "elev_m": None, "source_url": ""},
    {"id": "SHACKLETON_RIM", "name": "Shackleton rim (mock point)", "name_ko": "섀클턴 크레이터 가장자리(가짜 지점)",
     "short": "Shackleton", "group": "polar_peak", "lat": -89.9, "lon": 0.0, "elev_m": None, "source_url": ""},
]

# Mock window: one lunar (synodic) day of hourly samples starting at hour index 0.
N_HOURS = 720
SYNODIC_H = 29.530589 * 24
ANOM_H = 27.554550 * 24     # longitude libration period (rough)
DRAC_H = 27.212221 * 24     # latitude libration period (rough)
SUN_KM = 1.496e8
EARTH_KM = 384400.0


def unit(lat_deg, lon_deg):
    la, lo = math.radians(lat_deg), math.radians(lon_deg)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def ephem_row(h):
    # Earth: near the +x axis, wobbling a few degrees (toy libration).
    e_lon = 6.3 * math.sin(2 * math.pi * h / ANOM_H)
    e_lat = 6.7 * math.sin(2 * math.pi * h / DRAC_H)
    # Sun: sub-solar longitude moves west once per synodic month; start near full moon side
    s_lon = 180.0 - 360.0 * h / SYNODIC_H + 40.0
    s_lat = 1.54 * math.sin(2 * math.pi * h / DRAC_H)
    s = [SUN_KM * c for c in unit(s_lat, s_lon)]
    e = [EARTH_KM * c for c in unit(e_lat, e_lon)]
    return s + e


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    sites = []
    for s in SITES:
        sites.append({**s, "coord_quality": "estimated",
                      "note": "MOCK placeholder from the team brief; card 4 replaces it with a cited value.",
                      "mock": True})
    write_json(DATA / "sites.json", sites)

    with open(DATA / "ephem.bin", "wb") as f:
        for h in range(N_HOURS):
            f.write(struct.pack("<6f", *ephem_row(h)))
    write_json(DATA / "ephem.json", {
        "start": "2026-01-01T00:00:00Z", "step_h": 1, "n": N_HOURS, "frame": "MOON_ME_DE421", "units": "km",
        "columns": ["sun_x", "sun_y", "sun_z", "earth_x", "earth_y", "earth_z"],
        "source": "MOCK: analytic toy model in pipeline/make_mocks.py (not an ephemeris)", "mock": True})

    for s in SITES:
        write_json(DATA / "horizon" / f"{s['id']}.json", {
            "id": s["id"], "lat": s["lat"], "lon": s["lon"], "h0_m": 0.0, "obs_height_m": 2,
            "az_step_deg": 0.5, "mask": [0.0] * 720, "max_range_km": 0,
            "dem_sources": [], "mock": True})

    # Contract v1.1 shape with one zero-valued placeholder row each (shape only, no meaning).
    write_json(DATA / "validation.json", {
        "window": "2020-01-01..2038-08-01", "step_h": 2, "n_points": 1, "seed": 42,
        "sun": {"mae_pp": 0, "rmse_pp": 0, "r": 0, "within_pgda_60m_spread_pct": 100},
        "earth": {"mae_pp": 0, "rmse_pp": 0, "r": 0, "within_pgda_60m_spread_pct": 100},
        "points": [{"lat": -89.9, "lon": 0.0,
                    "ours_sun": 0.0, "pgda_sun": 0.0, "pgda_sun_min60": 0.0, "pgda_sun_max60": 0.0,
                    "ours_earth": 0.0, "pgda_earth": 0.0, "pgda_earth_min60": 0.0, "pgda_earth_max60": 0.0}],
        "named": [{"id": "SHACKLETON_RIM",
                   "ours_sun": 0.0, "pgda_sun": 0.0, "pgda_sun_min300": 0.0, "pgda_sun_max300": 0.0,
                   "ours_earth": 0.0, "pgda_earth": 0.0, "pgda_earth_min300": 0.0, "pgda_earth_max300": 0.0}],
        "pgda_files": [], "mock": True})
    print("mock files written to", DATA)


if __name__ == "__main__":
    main()
