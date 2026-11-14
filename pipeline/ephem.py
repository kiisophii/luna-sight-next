"""Card 1: reproducible MOON_ME_DE421 apparent ephemerides (contract v1.1).

Run: python pipeline/ephem.py
Dependencies: pip install -r pipeline/requirements-ephem.txt
Raw kernels and resumable checkpoints stay under ignored data/ directories.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

import numpy as np
from skyfield.api import Loader, PlanetaryConstants
from skyfield.timelib import Timescale, julian_date

ROOT = Path(__file__).resolve().parents[1]
R_MOON_KM = 1737.4
FRAME = "MOON_ME_DE421"
COLUMNS = ["sun_x", "sun_y", "sun_z", "earth_x", "earth_y", "earth_z"]
BASE = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
KERNELS = {
    "de440s.bsp": BASE + "spk/planets/de440s.bsp",
    "moon_pa_de421_1900-2050.bpc": BASE + "pck/moon_pa_de421_1900-2050.bpc",
    "moon_080317.tf": BASE + "fk/satellites/moon_080317.tf",
    "pck00008.tpc": BASE + "pck/a_old_versions/pck00008.tpc",
    "naif0012.tls": BASE + "lsk/naif0012.tls",
}
UTC = timezone.utc
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def download(url, path):
    """Skip complete files; resume partial HTTP transfers without appending a 200."""
    path = Path(path)
    if path.exists() and path.stat().st_size:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    size = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={size}-"} if size else {})
    with urllib.request.urlopen(request, timeout=180) as response:
        resumed = size > 0 and response.status == 206
        if resumed and not response.headers.get("Content-Range", "").startswith(f"bytes {size}-"):
            raise ValueError("Server returned an unexpected Content-Range")
        expected = response.headers.get("Content-Length")
        received = 0
        with partial.open("ab" if resumed else "wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
                received += len(block)
        if expected is not None and received != int(expected):
            raise IOError(f"Incomplete download: {url}")
    os.replace(partial, path)


class Ephemeris:
    def __init__(self, kernel_dir=ROOT / "data/raw/kernels"):
        self.kernel_dir = Path(kernel_dir)
        for name, url in KERNELS.items():
            download(url, self.kernel_dir / name)
        loader = Loader(str(self.kernel_dir))
        builtin = loader.timescale(builtin=True)
        # Use the explicitly downloaded LSK for UTC, not an implicit web update.
        tls = (self.kernel_dir / "naif0012.tls").read_text(encoding="ascii")
        entries = re.findall(r"(\d+)\s*,\s*@(\d{4})-([A-Z]{3})-(\d+)", tls)
        if not entries:
            raise ValueError("Cannot parse DELTET/DELTA_AT in naif0012.tls")
        months = {m: i + 1 for i, m in enumerate(
            ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
        dates = [julian_date(int(y), months[m], int(d)) for _, y, m, d in entries]
        self.ts = Timescale(builtin.delta_t_function, np.array(dates),
                            np.array([float(offset) for offset, *_ in entries]))
        self.eph = loader("de440s.bsp")
        self.moon = self.eph["moon"]
        self.pc = PlanetaryConstants()
        for name in ("moon_080317.tf", "pck00008.tpc"):
            with (self.kernel_dir / name).open("rb") as stream:
                self.pc.read_text(stream)
        # Skyfield retains the binary handle; do not close it after parsing.
        self._pck = (self.kernel_dir / "moon_pa_de421_1900-2050.bpc").open("rb")
        self.pc.read_binary(self._pck)
        self.frame = self.pc.build_frame_named(FRAME)

    def vectors(self, datetimes):
        """Moon-centred apparent (light-time, aberration, deflection) xyz in km."""
        t = self.ts.from_datetimes(datetimes)
        observer = self.moon.at(t)
        return np.concatenate([
            observer.observe(self.eph[body]).apparent().frame_xyz(self.frame).km.T
            for body in ("sun", "earth")
        ], axis=-1)

    def direct_az_el(self, lat, lon, height_m, datetimes, body="sun"):
        """Independent full topocentric Skyfield observation (no refraction).

        height_m is terrain elevation above R=1737.4 km; observer is +2 m.
        The PCK sphere radius is overridden explicitly via a distance.
        """
        from skyfield.planetarylib import PlanetTopos
        from skyfield.units import Angle, Distance
        validate_site(lat, lon, height_m)
        site = PlanetTopos.from_latlon_distance(
            self.frame, Angle(degrees=lat), Angle(degrees=lon),
            Distance(km=R_MOON_KM + (height_m + 2) / 1000))
        t = self.ts.from_datetimes(datetimes)
        apparent = (self.moon + site).at(t).observe(self.eph[body]).apparent()
        alt, az, _ = apparent.altaz()
        return np.column_stack((az.degrees, alt.degrees))

    def manifest(self):
        import skyfield
        return {"frame": FRAME, "numpy": np.__version__, "skyfield": skyfield.__version__,
                "corrections": "Skyfield observe().apparent(); frame at reception time",
                "utc_assumption": "naif0012.tls; no unknown future leap seconds inserted",
                "kernels": [{"name": name, "url": url, "bytes": (self.kernel_dir / name).stat().st_size,
                             "sha256": digest(self.kernel_dir / name)} for name, url in KERNELS.items()]}


def validate_site(lat, lon, height_m):
    if not all(np.isfinite([lat, lon, height_m])) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Site needs finite height, latitude -90..90, east longitude -180..180")


def az_el(vectors, lat, lon, height_m=0, body="sun"):
    """Web-equivalent geometry, including topocentric parallax for both bodies.

    Subtract the observer in MOON_ME from the centre-apparent vector. This
    matches core.js; direct_az_el separately measures this approximation.
    Return [..., 2] ordered azimuth north-clockwise, elevation (degrees).
    """
    validate_site(lat, lon, height_m)
    if body not in ("sun", "earth"):
        raise ValueError("body must be sun or earth")
    la, lo = np.deg2rad([lat, lon])
    east = np.array([-np.sin(lo), np.cos(lo), 0.0])
    north = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    col = 0 if body == "sun" else 3
    v = np.asarray(vectors)[..., col:col + 3] - (R_MOON_KM + (height_m + 2) / 1000) * up
    e, n, u = v @ east, v @ north, v @ up
    return np.stack((np.rad2deg(np.arctan2(e, n)) % 360,
                     np.rad2deg(np.arctan2(u, np.hypot(e, n)))), axis=-1)


def generate(engine, start, stop, step_h, destination, manifest, chunk_size=2048):
    """Half-open UTC interval; checkpoint only after flushing each entire chunk."""
    n = int((stop - start).total_seconds() / (step_h * 3600))
    key = {"start": start.isoformat(), "stop_exclusive": stop.isoformat(), "step_h": step_h,
           "n": n, "manifest": manifest}
    cache = ROOT / "data/processed" / (destination.stem + f"_{step_h}h")
    cache.parent.mkdir(parents=True, exist_ok=True)
    state_path, array_path = cache.with_suffix(".state.json"), cache.with_suffix(".npy")
    resume = json.loads(state_path.read_text()) if state_path.exists() else {}
    usable = resume.get("key") == key and array_path.exists()
    done = resume.get("done", 0) if usable else 0
    data = np.lib.format.open_memmap(array_path, mode="r+" if usable else "w+", dtype="<f4", shape=(n, 6))
    for i in range(done, n, chunk_size):
        end = min(i + chunk_size, n)
        dates = [start + timedelta(hours=k * step_h) for k in range(i, end)]
        values = engine.vectors(dates)
        if not np.all(np.isfinite(values)):
            raise ValueError(f"Non-finite values in chunk {i}:{end}")
        data[i:end] = values
        data.flush()
        write_json(state_path, {"key": key, "done": end})
        print(f"{destination.name}: {end}/{n}", flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".tmp")
    with temp.open("wb") as stream:
        if destination.suffix == ".bin":
            data.tofile(stream)
        else:
            np.savez_compressed(stream, vectors=np.asarray(data),
                                hour_index=np.arange(n, dtype=np.int64) * step_h +
                                int((start - EPOCH).total_seconds() / 3600),
                                start=start.isoformat().replace("+00:00", "Z"), step_h=step_h,
                                frame=FRAME, units="km", columns=np.array(COLUMNS),
                                stop_exclusive=stop.isoformat().replace("+00:00", "Z"))
    os.replace(temp, destination)
    return n


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernels", type=Path, default=ROOT / "data/raw/kernels")
    parser.add_argument("--skip-validation-series", action="store_true")
    args = parser.parse_args()
    engine = Ephemeris(args.kernels)
    manifest = engine.manifest()
    output = ROOT / "web/data/ephem.bin"
    n = generate(engine, EPOCH, datetime(2031, 1, 1, tzinfo=UTC), 1, output, manifest)
    if n != 43824 or output.stat().st_size != 43824 * 6 * 4:
        raise ValueError("Hourly output does not match the contract")
    write_json(output.with_suffix(".json"), {
        "start": "2026-01-01T00:00:00Z", "step_h": 1, "n": n, "frame": FRAME,
        "units": "km", "columns": COLUMNS,
        "source": "NAIF de440s.bsp + moon_pa_de421_1900-2050.bpc via Skyfield", "mock": False})
    if not args.skip_validation_series:
        # End is exclusive: 2038-07-31T22Z is the final sample.
        generate(engine, datetime(2020, 1, 1, tzinfo=UTC), datetime(2038, 8, 1, tzinfo=UTC), 2,
                 ROOT / "data/processed/ephem_2020-2038_2h.npz", manifest)
    manifest["web_output"] = {"bytes": output.stat().st_size, "sha256": digest(output), "n": n}
    write_json(ROOT / "docs/ephem_provenance.json", manifest)
    print("Generated real ephemerides; run check_contract.py and validate_ephem.py.")


if __name__ == "__main__":
    main()
