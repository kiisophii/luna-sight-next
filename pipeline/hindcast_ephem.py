"""Card 21: hourly validation ephemeris 2019-01-01..2025-12-31 with exactly the card 1 pipeline
(pipeline/ephem.py: same kernels, MOON_ME_DE421, same columns, light-time-corrected apparent).

    python pipeline/hindcast_ephem.py   -> data/processed/ephem_2019-2025_1h.npz (git-ignored, resumable)
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ephem as E  # noqa: E402

OUT = E.ROOT / "data/processed/ephem_2019-2025_1h.npz"


def main():
    eng = E.Ephemeris(E.ROOT / "data/raw/kernels")
    n = E.generate(eng, datetime(2019, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc), 1,
                   OUT, eng.manifest())
    print("rows", n, "->", OUT)


if __name__ == "__main__":
    main()
