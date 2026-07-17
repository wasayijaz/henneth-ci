"""Vedic (sidereal) ephemeris engine — the deterministic half of the desk's astro pillar.

Computes, from pure math (no network, no data files, no tokens):
  * sidereal positions of the nine Vedic grahas, right now
  * every dated event in the next N days: sign ingresses, retrograde/direct stations,
    conjunctions, new/full moons, and eclipses

and writes them to state/astro.json.

WHY THIS EXISTS AS A SCRIPT AND NOT AN AGENT (CLAUDE.md Rule 2):
An agent asked "when does Saturn change sign" would recall a date from memory and could be
wrong. Here every date is COMPUTED and reproducible, so the astro agent — like every other
agent on this desk — may only read dates from the data layer, never state one from memory.

Zodiac: SIDEREAL, Lahiri (Chitrapaksha) ayanamsa. The ayanamsa is not a hardcoded constant:
it is derived on every run by precessing Spica (Chitra) from its J2000 catalogue position,
per the Chitrapaksha definition that Spica sits at exactly 180 deg sidereal. The value is
published in the output so any reader can audit it (~24.21 deg in 2026).

Accuracy: VSOP87/ELP-2000 via pymeeus — arc-second class, far finer than the day-level dates
this desk publishes. Cross-checked at build time against Karka Sankranti 2026-07-16.
"""
import json
import math
import pathlib
import sys
import time
import datetime as dt

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
HORIZON_DAYS = 90
PKT = dt.timezone(dt.timedelta(hours=5))

try:
    from pymeeus.Epoch import Epoch
    from pymeeus.Angle import Angle
    from pymeeus.Sun import Sun
    from pymeeus.Moon import Moon
    from pymeeus.Mercury import Mercury
    from pymeeus.Venus import Venus
    from pymeeus.Mars import Mars
    from pymeeus.Jupiter import Jupiter
    from pymeeus.Saturn import Saturn
    from pymeeus import Coordinates
except ImportError:                       # never crash the cycle (CLAUDE.md: Python section)
    print("astro: pymeeus not installed — run `pip install -r requirements.txt`. Writing degraded status.")
    STATE.mkdir(exist_ok=True)
    (STATE / "astro.json").write_text(json.dumps({
        "updated": time.strftime("%Y-%m-%d %H:%M"), "status": "degraded",
        "error": "pymeeus missing", "positions": {}, "events": []}, indent=1), encoding="utf-8")
    sys.exit(0)

# ---------------------------------------------------------------- zodiac constants
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGNS_SA = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
            "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena"]
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya",
    "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
# the nine grahas. Uranus/Neptune/Pluto are deliberately absent: they are not part of the
# classical Vedic set this desk claims to use, and inventing a tradition would be dishonest.
PLANETS = {"Mercury": Mercury, "Venus": Venus, "Mars": Mars, "Jupiter": Jupiter, "Saturn": Saturn}
BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]

# Spica (Chitra), J2000 catalogue position + proper motion — the anchor of the Chitrapaksha ayanamsa
SPICA_RA = (13, 25, 11.579)
SPICA_DEC = (-11, 9, 40.75)
SPICA_PM_LON = -0.0278      # arcsec/yr
SPICA_PM_LAT = -0.0286

# Standard eclipse limits (Meeus): measured as the Sun's distance from the lunar node.
SOLAR_CERTAIN, SOLAR_POSSIBLE = 15.35, 18.52
LUNAR_CERTAIN, LUNAR_POSSIBLE = 9.5, 12.2

# Slow movers: a sign change for these is a season, not a day.
SLOW = {"Jupiter", "Saturn", "Rahu", "Ketu"}


def importance(ev: dict) -> int:
    """Fixed 1-5 scale, defined HERE and not left to an agent's discretion — the same reason
    CLAUDE.md Rule 10 pins the news scale. Drift here would silently change what the astro
    lens treats as a headline. 1 routine · 2 minor · 3 notable · 4 material · 5 rare.
    The Moon changes sign every ~2.3 days: that is wallpaper, and must never rank as an event."""
    t, b = ev["type"], ev.get("body")
    if t in ("new_moon", "full_moon"):
        ecl = ev.get("eclipse")
        if ecl:
            return 5 if ecl["certainty"] == "certain" else 3
        return 2
    if t == "ingress":
        return 1 if b == "Moon" else (4 if b in SLOW else 3)
    if t == "station":
        return 4 if b in SLOW else 3
    if t == "conjunction":
        if b == "Moon" or ev.get("with") == "Moon":
            return 1
        return 3 if (b in SLOW and ev.get("with") in SLOW) else 2
    return 1


def _epoch(d: dt.datetime) -> Epoch:
    """UTC datetime -> pymeeus Epoch (fractional day)."""
    frac = d.day + (d.hour + d.minute / 60 + d.second / 3600) / 24
    return Epoch(d.year, d.month, frac)


def ayanamsa(e: Epoch) -> float:
    """Lahiri (Chitrapaksha), derived — not assumed. Spica's tropical longitude minus 180."""
    ra = Angle(*SPICA_RA, ra=True)
    dec = Angle(*SPICA_DEC)
    j2000 = Epoch(2000, 1, 1.5)
    lon0, lat0 = Coordinates.equatorial2ecliptical(ra, dec, Coordinates.true_obliquity(j2000))
    lon_t, _ = Coordinates.precession_ecliptical(
        j2000, e, lon0, lat0, Angle(0, 0, SPICA_PM_LON), Angle(0, 0, SPICA_PM_LAT))
    return float(lon_t.to_positive()) - 180.0


def _tropical(body: str, e: Epoch) -> float:
    """Geocentric apparent tropical ecliptic longitude, degrees."""
    if body == "Sun":
        return float(Sun.apparent_geocentric_position(e)[0].to_positive())
    if body == "Moon":
        return float(Moon.apparent_ecliptical_pos(e)[0].to_positive()) % 360
    if body in ("Rahu", "Ketu"):
        # Mean node — the node most Vedic almanacs (panchangs) publish. Ketu is always opposite.
        node = float(Moon.longitude_mean_ascending_node(e)) % 360
        return node if body == "Rahu" else (node + 180) % 360
    ra, dec, _ = PLANETS[body].geocentric_position(e)
    lon, _ = Coordinates.equatorial2ecliptical(ra, dec, Coordinates.true_obliquity(e))
    return float(lon.to_positive()) % 360


def sidereal(body: str, e: Epoch) -> float:
    return (_tropical(body, e) - ayanamsa(e)) % 360


def speed(body: str, e: Epoch) -> float:
    """Degrees/day, signed. Negative = retrograde. Measured over +/- half a day."""
    jde = float(e)
    a, b = sidereal(body, Epoch(jde - 0.5)), sidereal(body, Epoch(jde + 0.5))
    d = (b - a + 180) % 360 - 180        # unwrap the 0/360 seam
    return d


def sign_of(lon: float) -> int:
    return int(lon // 30) % 12


def nakshatra_of(lon: float):
    span = 360 / 27
    i = int(lon // span) % 27
    pada = int((lon % span) // (span / 4)) + 1
    return NAKSHATRAS[i], pada


def describe(body: str, e: Epoch) -> dict:
    lon = sidereal(body, e)
    si = sign_of(lon)
    nk, pada = nakshatra_of(lon)
    sp = speed(body, e)
    return {
        "lon": round(lon, 4),
        "sign": SIGNS[si], "sign_sa": SIGNS_SA[si],
        "deg_in_sign": round(lon % 30, 2),
        "nakshatra": nk, "pada": pada,
        "speed_deg_per_day": round(sp, 4),
        "retrograde": sp < 0,
    }


def _bisect_cross(fn, t0: float, t1: float, tol: float = 1e-4) -> float:
    """Find where fn changes sign between two JDEs (tol ~ 8 seconds)."""
    f0 = fn(t0)
    while t1 - t0 > tol:
        mid = (t0 + t1) / 2
        if (fn(mid) < 0) == (f0 < 0):
            t0 = mid
        else:
            t1 = mid
    return (t0 + t1) / 2


def _pkt_date(jde: float) -> str:
    y, m, d = Epoch(jde).get_date()
    utc = dt.datetime(int(y), int(m), 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=float(d) - 1)
    return utc.astimezone(PKT).strftime("%Y-%m-%d")


def _pkt_stamp(jde: float) -> str:
    y, m, d = Epoch(jde).get_date()
    utc = dt.datetime(int(y), int(m), 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=float(d) - 1)
    return utc.astimezone(PKT).strftime("%Y-%m-%d %H:%M")


def find_events(start: Epoch, days: int) -> list:
    """Scan the window day by day, then bisect to the exact moment of each event."""
    events = []
    j0 = float(start)
    grid = [j0 + i for i in range(days + 1)]

    # cache one sidereal longitude per (body, day) — the scan is the expensive part
    lon = {b: [sidereal(b, Epoch(j)) for j in grid] for b in BODIES}

    for b in BODIES:
        for i in range(days):
            l0, l1 = lon[b][i], lon[b][i + 1]

            # --- sign ingress: the sign index changed between the two days
            s0, s1 = sign_of(l0), sign_of(l1)
            if s0 != s1:
                boundary = (max(s0, s1) if (s1 - s0) % 12 == 1 else min(s0, s1)) * 30.0
                if (s1 - s0) % 12 == 1:                      # direct motion into the next sign
                    boundary = s1 * 30.0
                else:                                        # retrograde back into the previous
                    boundary = s0 * 30.0
                f = lambda t, bb=b, bd=boundary: (sidereal(bb, Epoch(t)) - bd + 180) % 360 - 180
                try:
                    jc = _bisect_cross(f, grid[i], grid[i + 1])
                except Exception:
                    jc = grid[i + 1]
                events.append({
                    "date": _pkt_date(jc), "at_pkt": _pkt_stamp(jc), "type": "ingress",
                    "body": b, "from": SIGNS[s0], "to": SIGNS[s1],
                    "text": f"{b} enters {SIGNS[s1]} ({SIGNS_SA[s1]})",
                })

            # --- station: direct <-> retrograde (nodes are always retrograde; skip them)
            if b not in ("Sun", "Moon", "Rahu", "Ketu"):
                v0, v1 = speed(b, Epoch(grid[i])), speed(b, Epoch(grid[i + 1]))
                if (v0 < 0) != (v1 < 0):
                    f = lambda t, bb=b: speed(bb, Epoch(t))
                    try:
                        jc = _bisect_cross(f, grid[i], grid[i + 1], tol=1e-3)
                    except Exception:
                        jc = grid[i + 1]
                    direction = "retrograde" if v1 < 0 else "direct"
                    events.append({
                        "date": _pkt_date(jc), "at_pkt": _pkt_stamp(jc), "type": "station",
                        "body": b, "direction": direction,
                        "sign": SIGNS[sign_of(sidereal(b, Epoch(jc)))],
                        "text": f"{b} stations {direction} in {SIGNS[sign_of(sidereal(b, Epoch(jc)))]}",
                    })

    # --- conjunctions: closest approach within 1 degree (Sun-Moon is covered by the phases below)
    pairs = [(a, b) for i, a in enumerate(BODIES) for b in BODIES[i + 1:]
             if not (a == "Sun" and b == "Moon") and not (a == "Rahu" and b == "Ketu")]
    for a, b in pairs:
        sep = [abs((lon[a][i] - lon[b][i] + 180) % 360 - 180) for i in range(len(grid))]
        for i in range(1, len(grid) - 1):
            if sep[i] <= sep[i - 1] and sep[i] <= sep[i + 1] and sep[i] < 1.0:
                events.append({
                    "date": _pkt_date(grid[i]), "type": "conjunction", "body": a, "with": b,
                    "sign": SIGNS[sign_of(lon[a][i])], "separation_deg": round(sep[i], 2),
                    "text": f"{a} conjunct {b} in {SIGNS[sign_of(lon[a][i])]} ({round(sep[i], 2)} deg apart)",
                })

    # --- new/full moons, and the eclipses that fall on them.
    # moon_phase() returns the phase NEAREST the epoch given — which can be in the PAST. Walking
    # forward from the returned date therefore stalls: ask from Jul 19, get Jul 14, step to Jul 19,
    # get Jul 14 again, forever. (That bug silently dropped every new moon, including the total
    # solar eclipse of 2026-08-12.) Probe on a fixed lunation-spaced grid instead, and de-dupe.
    LUNATION = 29.530589
    for target in ("new", "full"):
        seen = set()
        for k in range(int(days / LUNATION) + 3):
            probe = j0 + k * LUNATION
            if probe > j0 + days + LUNATION:
                break
            try:
                jm = float(Moon.moon_phase(Epoch(probe), target=target))
            except Exception:
                continue
            key = round(jm, 2)
            if key in seen or not (j0 <= jm <= j0 + days):
                continue
            seen.add(key)
            em = Epoch(jm)
            sun_l = sidereal("Sun", em)
            node_l = sidereal("Rahu", em)
            # distance from the Sun to the NEAREST node (either end of the axis)
            dn = min(abs((sun_l - node_l + 180) % 360 - 180),
                     abs((sun_l - (node_l + 180) + 180) % 360 - 180))
            moon_sign = SIGNS[sign_of(sidereal("Moon", em))]
            ev = {
                "date": _pkt_date(jm), "at_pkt": _pkt_stamp(jm),
                "type": "new_moon" if target == "new" else "full_moon",
                "body": "Moon", "sign": moon_sign,
                "sun_node_distance_deg": round(dn, 2),
                "text": f"{'New' if target == 'new' else 'Full'} Moon in {moon_sign}",
            }
            cert, poss = (SOLAR_CERTAIN, SOLAR_POSSIBLE) if target == "new" else (LUNAR_CERTAIN, LUNAR_POSSIBLE)
            if dn <= poss:
                kind = "solar" if target == "new" else "lunar"
                ev["eclipse"] = {"kind": kind, "certainty": "certain" if dn <= cert else "possible",
                                 "method": f"Sun {round(dn, 2)} deg from the lunar node; {kind} eclipse limit {cert} deg"}
                ev["text"] += f" — {ev['eclipse']['certainty']} {kind} eclipse"
            events.append(ev)

    for ev in events:
        ev["importance"] = importance(ev)
    events.sort(key=lambda x: (x["date"], x.get("at_pkt", "")))
    return events


def main():
    STATE.mkdir(exist_ok=True)
    now_utc = dt.datetime.now(dt.timezone.utc)
    e = _epoch(now_utc)
    try:
        ayan = ayanamsa(e)
        positions = {b: describe(b, e) for b in BODIES}
        events = find_events(e, HORIZON_DAYS)
        status = "ok"
        err = None
    except Exception as ex:                    # degraded, never crash the cycle
        print(f"astro: computation failed ({type(ex).__name__}: {ex}) — writing degraded status")
        ayan, positions, events, status, err = None, {}, [], "degraded", f"{type(ex).__name__}: {ex}"

    moon = positions.get("Moon", {})
    out = {
        "updated": now_utc.astimezone(PKT).strftime("%Y-%m-%d %H:%M"),
        "updated_utc": now_utc.strftime("%Y-%m-%d %H:%M"),
        "status": status,
        "error": err,
        "system": {
            "zodiac": "sidereal",
            "ayanamsa": "Lahiri (Chitrapaksha)",
            "ayanamsa_deg": round(ayan, 4) if ayan is not None else None,
            "node": "mean",
            "bodies": "the nine classical grahas (no outer planets)",
            "method": ("sidereal = tropical − ayanamsa; the ayanamsa is derived each run by precessing "
                       "Spica from its J2000 position (Chitrapaksha: Spica = 180° sidereal), never hardcoded. "
                       "Positions are VSOP87/ELP-2000 (pymeeus), geocentric apparent."),
            "engine": "scripts/astro_engine.py",
        },
        "horizon_days": HORIZON_DAYS,
        "importance_scale": {
            "1": "routine (the Moon changing sign — happens every ~2.3 days)",
            "2": "minor (new/full moon, fast-body conjunction)",
            "3": "notable (Sun/Mercury/Venus/Mars ingress, inner-planet station, possible eclipse)",
            "4": "material (Jupiter/Saturn/Rahu/Ketu ingress, slow-planet station)",
            "5": "rare (a certain eclipse)",
            "note": "Fixed in astro_engine.py, not left to an agent — drift here would silently change what the lens calls a headline.",
        },
        "positions": positions,
        "moon_phase_illumination": (round(float(Moon.illuminated_fraction_disk(e)), 3)
                                    if status == "ok" else None),
        "events": events,
        "note": ("Computed, not recalled: every date here is derived from first principles so no agent "
                 "has to remember one. Astrology is a research lens on this desk, not a signal source — "
                 "it never generates or gates a trade setup, and every astro read is scored like a broker call."),
    }
    (STATE / "astro.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    if status == "ok":
        big = [e for e in events if e["importance"] >= 3]
        # ASCII only on stdout: the app-scheduled tasks run on a Windows console (cp1252) where a
        # stray degree sign or >= raises UnicodeEncodeError and takes the whole cycle down. The
        # JSON is written UTF-8 and keeps the real symbols.
        print(f"astro: ayanamsa {ayan:.4f} deg (Lahiri) | {len(events)} events over {HORIZON_DAYS} days "
              f"({len(big)} of impact 3+)")
        for b in BODIES:
            p = positions[b]
            print(f"  {b:8} {p['lon']:7.2f} {p['sign']:12} {p['deg_in_sign']:5.2f} "
                  f"{p['nakshatra']:18} pada {p['pada']}{'  R' if p['retrograde'] else ''}")
        for ev in big[:14]:
            print(f"  {ev['date']}  [{ev['importance']}] {ev['type']:12} "
                  f"{ev['text'].encode('ascii', 'replace').decode()}")
    else:
        print("astro: wrote degraded astro.json")


if __name__ == "__main__":
    main()
