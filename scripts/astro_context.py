"""The two things the astro reading needs and the state layer did not carry.

1. TODAY'S ACTIVE CONDITIONS, named EXACTLY as astro_backtest.py names them. The backtest already
   measured every one of these against ~19 years of PSX prices. Without this file the dashboard can
   show what the sky is doing OR what the desk measured, but it cannot join them — and the join is
   the only honest value the astro pillar has: "this condition is live right now, and here is what
   it was actually worth when we tested it." The mask definitions below are copied from
   astro_backtest.py deliberately; if they ever drift apart the join becomes a lie, so they are
   asserted against the backtest's own condition list at the end of the run.

2. THE REFERENCE CHARTS' SLOW GRAHAS — Pakistan (1947-08-14) and the KSE-100 (1991-11-01).
   astro_map.json records both birth events but no positions, because neither has a known time.
   Saturn, Jupiter, Rahu and Ketu move so slowly that a whole day of uncertainty cannot shift their
   sign; the Moon and the ascendant move too fast, so they are refused outright. Each chart is
   therefore computed at BOTH competing times and only the placements that agree are published.
   That is astro_map's own usage_rule, enforced in code rather than in a footnote.

Writes state/astro_context.json. Free, deterministic, no network.
"""
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from pymeeus.Epoch import Epoch
    import astro_engine as ae
except ImportError:
    print("astro_context: pymeeus missing - skipping")
    sys.exit(0)

# the two charts, and the competing times each is argued at. The desk picks no winner between
# them; it publishes only what both agree on.
REFERENCE = {
    "pakistan": {
        "label": "Pakistan",
        "event": "Independence of Pakistan",
        "date": "1947-08-14",
        "times": ["00:00", "09:30"],
        "time_note": "disputed - astrologers argue a midnight 14/15 August chart and a ~09:30 "
                     "oath-taking chart. Both are computed; only placements that agree are shown.",
    },
    "kse100": {
        "label": "KSE-100",
        "event": "KSE-100 index launched with a base of 1,000 points",
        "date": "1991-11-01",
        "times": ["09:30", "15:30"],
        "time_note": "PSX publishes the base DATE, not a launch time. The chart is computed at both "
                     "the open and the close of that day; only placements that agree are shown.",
    },
}
SLOW = ["Saturn", "Jupiter", "Rahu", "Ketu"]
SATURN_YEARS = 29.457


def _epoch_for(date_s: str, time_s: str, tz_hours: float = 5.0) -> Epoch:
    y, m, d = (int(x) for x in date_s.split("-"))
    hh, mm = (int(x) for x in time_s.split(":"))
    return Epoch(y, m, d + (hh + mm / 60 - tz_hours) / 24)


def _place(body: str, e: Epoch) -> dict:
    lon = ae.sidereal(body, e)
    nk, pada = ae.nakshatra_of(lon)
    return {"lon": round(lon, 3), "sign": ae.SIGNS[ae.sign_of(lon)],
            "deg_in_sign": round(lon % 30, 2), "nakshatra": nk, "pada": pada}


def slow_grahas(date_s: str, times: list) -> dict:
    """Only the placements that survive the time dispute. A graha whose sign or nakshatra moves
    between the two candidate times is dropped, not fudged."""
    casts = [{b: _place(b, _epoch_for(date_s, t)) for b in SLOW} for t in times]
    out, dropped = {}, []
    for b in SLOW:
        signs = {c[b]["sign"] for c in casts}
        naks = {c[b]["nakshatra"] for c in casts}
        if len(signs) > 1:
            dropped.append(f"{b} (sign differs between the candidate times)")
            continue
        p = dict(casts[0][b])
        p["nakshatra_stable"] = len(naks) == 1
        if not p["nakshatra_stable"]:
            p["nakshatra"] = None
            p["pada"] = None
        out[b] = p
    return {"grahas": out, "dropped": dropped}


def saturn_return(natal_lon: float, birth: dt.date, today: dt.date) -> dict:
    """Saturn back on its birth degree - the one long-cycle event a time-less chart can still
    claim, because Saturn covers only ~0.03 degrees a day."""
    done, nxt = [], None
    for k in range(1, 5):
        target = birth + dt.timedelta(days=SATURN_YEARS * 365.2425 * k)
        # bisect the month around the estimate for the exact crossing of the natal longitude
        lo = target - dt.timedelta(days=400)
        hi = target + dt.timedelta(days=400)
        f = lambda d: (ae.sidereal("Saturn", _epoch_for(d.isoformat(), "12:00")) - natal_lon + 180) % 360 - 180
        a, b = lo, hi
        if f(a) * f(b) > 0:
            continue
        for _ in range(40):
            m = a + (b - a) / 2
            if f(a) * f(m) <= 0:
                b = m
            else:
                a = m
        hit = a + (b - a) / 2
        (done if hit <= today else []).append(hit.isoformat())
        if hit > today and nxt is None:
            nxt = hit.isoformat()
    return {"completed": len(done), "dates": done, "next": nxt}


def active_conditions(e: Epoch, amap: dict) -> list:
    """TODAY, expressed in the backtest's own vocabulary. Names must match astro_backtest.py's
    mask keys exactly - the dashboard joins on this string."""
    lon = {b: ae.sidereal(b, e) for b in ae.BODIES}
    spd = {b: ae.speed(b, e) for b in ae.BODIES}
    sun = lon["Sun"]
    moon_elong = abs((lon["Moon"] - sun + 180) % 360 - 180)
    out = []

    def add(cond, detail):
        out.append({"condition": cond, "detail": detail})

    for b in ae.BODIES:
        sign = ae.SIGNS[ae.sign_of(lon[b])]
        # the nodes are retrograde by definition, so "Rahu retrograde" is not a condition - it is
        # every day. The backtest never tested it; neither do we.
        if b not in ("Sun", "Moon", "Rahu", "Ketu") and spd[b] < 0:
            add(f"{b} retrograde", f"{b} is retrograde in {sign}.")
        if b not in ("Sun", "Moon", "Rahu", "Ketu"):
            sep = abs((lon[b] - sun + 180) % 360 - 180)
            if sep < 8.0:
                add(f"{b} combust", f"{b} sits {sep:.1f} degrees from the Sun in {sign} - combust.")
        g = (amap.get("grahas", {}) or {}).get(b, {})
        own = g.get("own_signs") or []
        exalt = (g.get("exalted") or {}).get("sign")
        debil = (g.get("debilitated") or {}).get("sign")
        if sign in own or sign == exalt:
            add(f"{b} strong (own/exalted sign)",
                f"{b} is in {sign} - {'exalted' if sign == exalt else 'its own sign'}.")
        if debil and sign == debil:
            add(f"{b} debilitated", f"{b} is in {sign} - its sign of debilitation.")

    if moon_elong < 26:
        add("near the new moon (+/-2d)", f"The Moon is {moon_elong:.0f} degrees from the Sun.")
    if moon_elong > 154:
        add("near the full moon (+/-2d)", f"The Moon is {moon_elong:.0f} degrees from the Sun.")
    node = lon["Rahu"]
    dn = min(abs((sun - node + 180) % 360 - 180), abs((sun - (node + 180) + 180) % 360 - 180))
    if (moon_elong < 26 and dn < 15.35) or (moon_elong > 154 and dn < 9.5):
        add("eclipse window (+/-7 sessions)",
            f"A syzygy with the Sun {dn:.0f} degrees from the nodal axis.")
    return out


def main():
    STATE.mkdir(exist_ok=True)
    amap = json.loads((STATE / "astro_map.json").read_text(encoding="utf-8")) \
        if (STATE / "astro_map.json").exists() else {}
    now_utc = dt.datetime.now(dt.timezone.utc)
    today = now_utc.astimezone(ae.PKT).date()
    try:
        e = ae._epoch(now_utc)
        conds = active_conditions(e, amap)
    except Exception as ex:
        print(f"astro_context: sky computation failed ({type(ex).__name__}: {ex})")
        sys.exit(0)

    ref = {}
    for key, spec in REFERENCE.items():
        try:
            sg = slow_grahas(spec["date"], spec["times"])
            birth = dt.date.fromisoformat(spec["date"])
            sat = sg["grahas"].get("Saturn")
            ref[key] = {
                "label": spec["label"], "event": spec["event"], "date": spec["date"],
                "times_tested": spec["times"], "time_note": spec["time_note"],
                "grahas": sg["grahas"], "dropped": sg["dropped"],
                "saturn_return": saturn_return(sat["lon"], birth, today) if sat else None,
                "refused": ["Moon", "Ascendant"],
            }
        except Exception as ex:
            print(f"astro_context: {key} failed ({type(ex).__name__}: {ex}) - skipped")

    # what the two charts share - the only synastry a time-less pair of charts can honestly claim
    shared = []
    pk = (ref.get("pakistan") or {}).get("grahas") or {}
    ks = (ref.get("kse100") or {}).get("grahas") or {}
    for b in SLOW:
        a, c = pk.get(b), ks.get(b)
        if not a or not c:
            continue
        row = {"graha": b, "pakistan_sign": a["sign"], "kse100_sign": c["sign"],
               "same_sign": a["sign"] == c["sign"],
               "same_nakshatra": bool(a.get("nakshatra") and a["nakshatra"] == c.get("nakshatra")),
               "separation_deg": round(abs((a["lon"] - c["lon"] + 180) % 360 - 180), 1)}
        shared.append(row)

    # where today's sky sits relative to both charts (slow grahas only, same discipline)
    try:
        sky_slow = {b: _place(b, e) for b in SLOW}
    except Exception:
        sky_slow = {}

    res = {
        "updated": now_utc.astimezone(ae.PKT).strftime("%Y-%m-%d %H:%M"),
        "updated_utc": now_utc.strftime("%Y-%m-%d %H:%M"),
        "status": "ok",
        "what_this_is": ("Two joins the astro reading could not make before: today's sky expressed "
                         "in the backtest's own condition vocabulary, and the slow-graha placements "
                         "of the Pakistan and KSE-100 charts. Nothing here is a forecast."),
        "discipline": ("Conditions are named exactly as astro_backtest.json names them so a reader "
                       "can look up what each was measured to be worth. The reference charts publish "
                       "only Saturn, Jupiter, Rahu and Ketu, and only where the placement is the same "
                       "under every competing birth time; the Moon and the ascendant are refused."),
        "today": {"date": today.isoformat(), "n_active": len(conds), "conditions": conds,
                  "sky_slow": sky_slow},
        "reference": ref,
        "shared": shared,
    }
    (STATE / "astro_context.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    # the join must not silently rot: every live condition has to exist in the backtest
    bt = STATE / "astro_backtest.json"
    if bt.exists():
        known = {t["condition"] for t in json.loads(bt.read_text(encoding="utf-8")).get("all_tests", [])}
        orphan = [c["condition"] for c in conds if c["condition"] not in known]
        if orphan:
            print(f"astro_context: WARNING - conditions not present in the backtest: {orphan}")

    print(f"astro_context: {len(conds)} conditions active today")
    for c in conds:
        print(f"  {c['condition']:34} {c['detail']}")
    for k, r in ref.items():
        gg = ", ".join(f"{b} {p['sign']}" for b, p in r["grahas"].items())
        sr = r.get("saturn_return") or {}
        print(f"  {r['label']:9} {r['date']}  {gg}")
        print(f"  {'':9} Saturn returns completed: {sr.get('completed')}, next {sr.get('next')}")
        if r["dropped"]:
            print(f"  {'':9} dropped: {r['dropped']}")


if __name__ == "__main__":
    main()
