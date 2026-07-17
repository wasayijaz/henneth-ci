"""A compact daily ephemeris table the BROWSER can use to cast a person's birth chart.

WHY THIS SHAPE
The personal astro feature computes each user's natal chart from their birth date/time/place. On a
static site that must happen in the browser, per user, privately — so the browser needs planetary
positions for any plausible birth date. pymeeus is Python and can't run client-side, so we ship a
precomputed table and interpolate it in JS.

WHAT IT CONTAINS
Daily sidereal (Lahiri) ecliptic longitude of the nine grahas, 1950-01-01 -> 2035-12-31, sampled at
00:00 UT. Longitudes are stored as tenths of a degree (0-3599) in a Uint16, so the whole table is a
flat binary the browser fetches once as an ArrayBuffer and caches.

  bytes = n_days * 9 * 2  (~0.56 MB for 86 years)

ACCURACY AND ITS ONE SOFT SPOT
Slow bodies (Sun through Saturn, the nodes) interpolate cleanly between daily samples. The Moon moves
~13 deg/day, so linear interpolation between two daily samples carries up to ~0.3 deg error mid-day —
fine for the Moon's SIGN, occasionally ambiguous right at a nakshatra boundary. The JS side flags a
birth whose Moon lands within 0.5 deg of a boundary as "near a cusp", rather than pretending to a
precision the table doesn't have. (A future refinement can compute the Moon directly from a series.)

Writes: state/natal_ephem.bin (binary) + state/natal_ephem.json (header the JS reads first).
Incremental + chunked like astro_history so a single run never blows a timeout.
"""
import datetime as dt
import json
import pathlib
import struct
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
BIN = STATE / "natal_ephem.bin"
HDR = STATE / "natal_ephem.json"
START = dt.date(1950, 1, 1)
END = dt.date(2035, 12, 31)
MAX_NEW = 4000          # per-run cap
BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]

try:
    from pymeeus.Epoch import Epoch
    import astro_engine as ae
except ImportError:
    print("build_natal_ephemeris: pymeeus missing — skipping")
    sys.exit(0)


def row_for(d: dt.date):
    e = Epoch(d.year, d.month, d.day + 0.5)     # 00:00 UT ~ midday-of-JD convention handled by engine
    ayan = ae.ayanamsa(e)
    out = []
    for b in BODIES:
        lon = (ae._tropical(b, e) - ayan) % 360
        out.append(int(round(lon * 10)) % 3600)
    return out


def main():
    STATE.mkdir(exist_ok=True)
    have = 0
    if BIN.exists() and HDR.exists():
        try:
            h = json.loads(HDR.read_text(encoding="utf-8"))
            if h.get("start") == START.isoformat() and h.get("bodies") == BODIES:
                have = h.get("n_days", 0)
        except Exception:
            have = 0

    total_days = (END - START).days + 1
    if have >= total_days:
        print(f"build_natal_ephemeris: complete ({have} days, {START} -> {END})")
        sys.exit(0)

    t0 = time.time()
    rows = bytearray()
    cursor = START + dt.timedelta(days=have)
    written = 0
    mode = "ab" if have else "wb"
    with open(BIN, mode) as f:
        d = cursor
        while d <= END and written < MAX_NEW:
            try:
                r = row_for(d)
            except Exception as e:
                print(f"build_natal_ephemeris: failed on {d} ({type(e).__name__}) — stopping, keeping progress")
                break
            f.write(struct.pack("<9H", *r))
            written += 1
            d += dt.timedelta(days=1)
            if written % 1000 == 0:
                print(f"  ... +{written} ({time.time()-t0:.0f}s)")

    n = have + written
    last = START + dt.timedelta(days=n - 1)
    HDR.write_text(json.dumps({
        "start": START.isoformat(), "end_target": END.isoformat(),
        "n_days": n, "last_date": last.isoformat(),
        "bodies": BODIES, "units": "tenths of a degree, sidereal (Lahiri), 00:00 UT",
        "record": "<9H (9 uint16 little-endian per day, in bodies order)",
        "complete": bool(n >= total_days),
        "note": "Browser-side birth-chart ephemeris. Slow bodies interpolate cleanly; the Moon is "
                "linear-interpolated and births within 0.5 deg of a nakshatra boundary are flagged "
                "near-a-cusp rather than forced.",
        "updated": time.strftime("%Y-%m-%d %H:%M"),
    }, indent=1), encoding="utf-8")
    done = n >= total_days
    print(f"build_natal_ephemeris: +{written} days -> {n}/{total_days} "
          f"({START} -> {last}){'  COMPLETE' if done else '  (more next run)'} "
          f"| {BIN.stat().st_size/1024:.0f} KB in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
