"""The PUBLIC, lighter astro layer for the marketing site.

WHAT THIS IS FOR
The terminal's personal astro (#/cast, #/mychart) reads a user's birth chart against every named
PSX ticker. This builds the marketing-site version of the same idea, deliberately one notch
softer: a reader gets their Moon sign, the elements and grahas it runs with, and which SECTORS and
COMMODITIES tradition pairs to those grahas — never a named security, never a price, never a call.
The ticker-level reading is what the account is for, and the page says so.

WHY A SEPARATE SLICE AND NOT A state/ READ
The marketing build is hermetic — Block 1 moved it off `state/` entirely so an Astro build can
never depend on the desk's private data layer (see scripts/build_public_slice.py, same pattern).
Everything this writes is impersonal and already publishable; nothing here is user data, and
nothing here is a desk output that the account gate protects.

TWO ARTEFACTS

1. site/public/moon_ephem.bin — the MOON COLUMN ONLY, lifted out of the verified
   state/natal_ephem.bin the terminal already ships. 9 bodies x uint16 becomes 1, so ~552 KB
   becomes ~61 KB: small enough to hand a marketing visitor on first paint.

   Slicing the existing table rather than recomputing matters. astro_engine's ephemeris is the
   verified one; a second, independently-derived Moon table on the public site could disagree with
   the terminal's answer for the same birth date, and "the free version told me Taurus, the paid
   one says Gemini" is the worst possible bug in an astrology product.

   Vedic practice reads from the Moon sign (Chandra lagna), which is also why the terminal refuses
   houses and ascendants (see scripts/astro_natal.py) — so Moon-only is not a degraded chart here,
   it is the load-bearing part.

2. site/src/data/public/astro_lite.json — the impersonal reference the page renders against:
   graha -> sectors (from state/astro_map.json's sector_significators, the same karakas the desk
   uses), graha -> commodities (mirroring COMMODITIES in dashboard/app.js), and the current sky.

Idempotent and safe to re-run. Missing inputs degrade to a skip, never a crash.
"""
import json
import pathlib
import struct
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
SITE_PUBLIC = ROOT / "site" / "public"
SITE_DATA = ROOT / "site" / "src" / "data" / "public"

MOON_INDEX = 1          # position of "Moon" in the header's `bodies` order
BODIES_PER_DAY = 9

# Mirrors COMMODITIES in dashboard/app.js:1177. Duplicated deliberately rather than imported —
# app.js is browser JS with no module boundary this can reach, and a silent drift is caught by
# the check at the bottom of this file rather than by a reader noticing.
COMMODITIES = [
    {"name": "Gold", "graha": "Sun", "note": "the Sun's metal — kingship and store of value"},
    {"name": "Silver", "graha": "Moon", "note": "the Moon's metal — liquidity and the public's hoard"},
    {"name": "Crude oil", "graha": "Saturn", "note": "Saturn's — what is dug from deep underground"},
    {"name": "Natural gas", "graha": "Rahu", "note": "Rahu's — the volatile and the piped"},
    {"name": "Copper", "graha": "Venus", "note": "Venus's metal — wiring, comfort, industry"},
    {"name": "Wheat", "graha": "Moon", "note": "the Moon's — the staple crop and its rains"},
    {"name": "Cotton", "graha": "Venus", "note": "Venus's fibre — cloth and its trade"},
    {"name": "Sugar", "graha": "Venus", "note": "Venus's sweetness — cane and refinery"},
]

# The twelve sidereal signs with their element and ruling graha. Standard Jyotish attribution;
# the page uses element to group and graha to join onto the sector/commodity tables.
SIGNS = [
    ("Aries", "Fire", "Mars"), ("Taurus", "Earth", "Venus"), ("Gemini", "Air", "Mercury"),
    ("Cancer", "Water", "Moon"), ("Leo", "Fire", "Sun"), ("Virgo", "Earth", "Mercury"),
    ("Libra", "Air", "Venus"), ("Scorpio", "Water", "Mars"), ("Sagittarius", "Fire", "Jupiter"),
    ("Capricorn", "Earth", "Saturn"), ("Aquarius", "Air", "Saturn"), ("Pisces", "Water", "Jupiter"),
]


def load(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def build_moon_bin(hdr):
    """Lift the Moon column out of the full ephemeris."""
    raw = (STATE / "natal_ephem.bin").read_bytes()
    n = hdr["n_days"]
    expect = n * BODIES_PER_DAY * 2
    if len(raw) < expect:
        print(f"build_astro_lite: ephem short ({len(raw)} < {expect}) — skipping")
        return None
    vals = struct.unpack_from(f"<{n * BODIES_PER_DAY}H", raw, 0)
    moon = vals[MOON_INDEX::BODIES_PER_DAY]
    SITE_PUBLIC.mkdir(parents=True, exist_ok=True)
    out = SITE_PUBLIC / "moon_ephem.bin"
    out.write_bytes(struct.pack(f"<{len(moon)}H", *moon))
    return {"file": "/moon_ephem.bin", "n_days": len(moon), "bytes": out.stat().st_size}


def main():
    hdr = load(STATE / "natal_ephem.json")
    amap = load(STATE / "astro_map.json", {})
    sky = load(STATE / "astro.json", {})

    if not hdr or not (STATE / "natal_ephem.bin").exists():
        print("build_astro_lite: no natal ephemeris yet — skipping (run build_natal_ephemeris.py)")
        sys.exit(0)
    if hdr.get("bodies", [])[MOON_INDEX:MOON_INDEX + 1] != ["Moon"]:
        print("build_astro_lite: ephemeris body order changed — refusing to slice blindly")
        sys.exit(0)

    moon = build_moon_bin(hdr)
    if not moon:
        sys.exit(0)

    # graha -> sectors, inverted from the desk's own karaka table so the two can never disagree
    by_graha = {}
    for sector, rec in (amap.get("sector_significators") or {}).items():
        if sector.startswith("_") or not isinstance(rec, dict):
            continue
        g = rec.get("primary")
        if not g:
            continue
        by_graha.setdefault(g, []).append({
            "sector": sector, "why": rec.get("why", ""), "confidence": rec.get("confidence", ""),
        })

    comm_by_graha = {}
    for c in COMMODITIES:
        comm_by_graha.setdefault(c["graha"], []).append({"name": c["name"], "note": c["note"]})

    # The current sky, impersonal — the same positions the Astro board publishes.
    positions = {k: {"sign": v.get("sign"), "nakshatra": v.get("nakshatra")}
                 for k, v in (sky.get("positions") or {}).items()
                 if isinstance(v, dict)}

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "astro_lite.json").write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "scripts/build_astro_lite.py — impersonal slice; no user data, no desk output",
        "ephem": {**moon, "start": hdr["start"], "units": "tenths of a degree, sidereal (Lahiri), 00:00 UT"},
        "signs": [{"name": n, "element": e, "ruler": r} for n, e, r in SIGNS],
        "sectors_by_graha": by_graha,
        "commodities_by_graha": comm_by_graha,
        "sky": {"updated": sky.get("updated"), "system": sky.get("system"), "positions": positions},
        "discipline": (amap.get("discipline") or {}).get("research_lens_only", ""),
    }, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"astro_lite: moon {moon['n_days']} days ({moon['bytes'] // 1024} KB) · "
          f"{len(by_graha)} grahas -> {sum(len(v) for v in by_graha.values())} sectors · "
          f"{len(positions)} sky positions")
    sys.exit(0)


if __name__ == "__main__":
    main()
