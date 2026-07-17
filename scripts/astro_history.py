"""Cached daily sky, 2007 -> today. The raw material for falsifying astro claims.

astro_engine.py computes where the grahas are NOW and 90 days ahead. To ask whether any astro
claim has ever been TRUE on PSX, we need where they were on every past trading day too.

COST AND WHY IT IS CACHED
One day of all nine grahas costs ~36ms, so the full ~19-year span is ~4 minutes. That is fine
once, and far too slow to repeat inside a 15-minute cloud cron that also fetches every price.
So the span is computed once, committed, and afterwards only EXTENDED by the missing days
(~70ms/day). MAX_NEW_DAYS bounds any single run so a long gap can never blow the cron's timeout —
it just catches up over a few runs.

Idempotent: re-running with nothing missing does nothing. Never crashes the cycle.
Writes state/astro_history.json (internal — not rendered to users).
"""
import datetime as dt
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "astro_history.json"
START = "2007-01-01"          # comfortably before the earliest deep-history bar (2007-09-26)
MAX_NEW_DAYS = 600            # per-run cap: keeps the cloud cron inside its timeout

try:
    from pymeeus.Epoch import Epoch
    import astro_engine as ae
except ImportError:
    print("astro_history: pymeeus missing — skipping (astro lens will stay unavailable)")
    sys.exit(0)


def _jde(d: dt.date) -> float:
    return float(Epoch(d.year, d.month, d.day + 0.5))   # noon UT: one stable sample per day


def sky_for(d: dt.date) -> dict:
    """All nine grahas for one day. Ayanamsa computed ONCE here, not once per body — it is the
    same value for every graha on a given day, and recomputing it nine times was ~13% of runtime."""
    e = Epoch(_jde(d))
    ayan = ae.ayanamsa(e)
    row = {}
    for b in ae.BODIES:
        lon = (ae._tropical(b, e) - ayan) % 360
        if b in ("Rahu", "Ketu"):
            retro = True                     # the mean node always moves backwards
        elif b in ("Sun", "Moon"):
            retro = False                    # never retrograde as seen from Earth
        else:
            a = (ae._tropical(b, Epoch(float(e) - 0.5)) - ayan) % 360
            c = (ae._tropical(b, Epoch(float(e) + 0.5)) - ayan) % 360
            retro = ((c - a + 180) % 360 - 180) < 0
        row[b] = (round(lon, 2), 1 if retro else 0)
    return row


def main():
    STATE.mkdir(exist_ok=True)
    data = {"start": START, "dates": [], "bodies": {b: {"lon": [], "retro": []} for b in ae.BODIES}}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            if prev.get("dates") and set(prev.get("bodies", {})) == set(ae.BODIES):
                data = prev
        except Exception as e:
            print(f"astro_history: existing cache unreadable ({type(e).__name__}) — rebuilding")

    have = set(data["dates"])
    last = dt.date.fromisoformat(data["dates"][-1]) if data["dates"] else None
    first_needed = dt.date.fromisoformat(START)
    today = dt.datetime.now(dt.timezone.utc).date()
    cursor = (last + dt.timedelta(days=1)) if last else first_needed

    todo = []
    d = cursor
    while d <= today and len(todo) < MAX_NEW_DAYS:
        if d.isoformat() not in have:
            todo.append(d)
        d += dt.timedelta(days=1)

    if not todo:
        print(f"astro_history: up to date ({len(data['dates'])} days cached through {data['dates'][-1]})")
        sys.exit(0)

    t0 = time.time()
    for i, day in enumerate(todo):
        try:
            row = sky_for(day)
        except Exception as e:
            print(f"astro_history: failed on {day} ({type(e).__name__}: {e}) — stopping, keeping what we have")
            break
        data["dates"].append(day.isoformat())
        for b, (lon, retro) in row.items():
            data["bodies"][b]["lon"].append(lon)
            data["bodies"][b]["retro"].append(retro)
        if i and i % 500 == 0:
            print(f"  ... {i}/{len(todo)} days ({time.time()-t0:.0f}s)")

    data["updated"] = time.strftime("%Y-%m-%d %H:%M")
    data["note"] = ("Daily sidereal longitude + retrograde flag per graha, sampled at 12:00 UT. "
                    "Lahiri ayanamsa, derived per day (see astro_engine.py). Internal cache for "
                    "astro_backtest.py — not rendered.")
    n = len(data["dates"])
    # integrity: the arrays must stay in lockstep with the date index or every test silently misaligns
    for b in ae.BODIES:
        if len(data["bodies"][b]["lon"]) != n or len(data["bodies"][b]["retro"]) != n:
            print(f"astro_history: FATAL — {b} arrays out of step with dates; refusing to write")
            sys.exit(1)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    caught_up = data["dates"][-1] == today.isoformat()
    print(f"astro_history: +{len(todo)} days in {time.time()-t0:.0f}s | {n} cached "
          f"({data['dates'][0]} -> {data['dates'][-1]})"
          f"{'' if caught_up else ' | more to catch up next run'}")


if __name__ == "__main__":
    main()
