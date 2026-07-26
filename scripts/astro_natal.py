"""Natal charts, Vimshottari dashas, and transits-to-natal — the actual method of Vedic prediction.

The earlier backtest tested transits IN ISOLATION (retrograde, combust, dignity, eclipses) and found
nothing. That was never the whole of the tradition. Vedic prediction is mostly about two things this
desk had not touched:
  * TRANSITS TO A NATAL CHART — Saturn crossing the natal Moon (Sade Sati), Jupiter's return, etc.
  * DASHAS — Vimshottari planetary periods, keyed to the natal Moon's nakshatra.
This computes both, for the 15 subjects whose birth date is genuinely sourced (astro_charts.py).

THE BIRTH MOMENT — the orthodox convention, not our invention
Bill Meridian, who built the first-trade chart database the field runs on, started with
INCORPORATION charts and abandoned them: "not satisfied with the relationship of the chart of
incorporation with share price movements, he turned to the horoscope of first trade." His charts
are "set for the time of the opening of the exchange, 10am until 1985 and 9:30 AM since... the
moment at which one could actually buy the stock" (billmeridian.com/articles-files/history-fin-astro.htm).
So: FIRST TRADE DATE, cast at the EXCHANGE OPEN. That is what this file computes. The time is not a
guess we are papering over — it is how the tradition defines the chart. The incorporation-date
alternative is the one the field already tested and rejected.

WHAT WE STILL REFUSE, AND WHAT WE MERELY DISCLOSE

1. NO ASCENDANT, NO HOUSES — refused. The convention fixes a time, but PSX's open has itself moved
   over the decades (09:32 today) and the ascendant travels a full degree every four minutes. Houses
   built on that are precision theatre. We read from the Moon sign (Chandra lagna), which is
   standard Vedic practice and survives the ambiguity.

2. TIME SENSITIVITY — disclosed, not refused. The chart is ALSO computed at the close, purely to
   measure how much the answer would move if the true first trade came later in the session. The
   convention's answer is what we publish; the slip is published beside it so a reader knows how
   load-bearing the convention is. For dashas that slip runs to years, and saying so is the point.

Writes state/astro_natal.json. Free, deterministic, no network.
"""
import datetime as dt
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"

try:
    from pymeeus.Epoch import Epoch
    import astro_engine as ae
except ImportError:
    print("astro_natal: pymeeus missing — skipping")
    sys.exit(0)

# Vimshottari: the 120-year cycle. Order and lengths are fixed tradition, not tunable.
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
               "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
TOTAL_YEARS = 120
NAK_SPAN = 360 / 27
YEAR_DAYS = 365.2425
CLOSE_TIME = "15:30"        # PSX close; paired with the 09:30 open to bracket the unknown moment


def _epoch_for(date_s: str, time_s: str, tz_hours: float = 5.0) -> Epoch:
    y, m, d = (int(x) for x in date_s.split("-"))
    hh, mm = (int(x) for x in time_s.split(":"))
    ut = hh + mm / 60 - tz_hours                     # PKT -> UT
    return Epoch(y, m, d + ut / 24)


def natal_positions(e: Epoch) -> dict:
    ayan = ae.ayanamsa(e)
    out = {}
    for b in ae.BODIES:
        lon = (ae._tropical(b, e) - ayan) % 360
        nk, pada = ae.nakshatra_of(lon)
        out[b] = {"lon": round(lon, 3), "sign": ae.SIGNS[ae.sign_of(lon)],
                  "deg_in_sign": round(lon % 30, 2), "nakshatra": nk, "pada": pada}
    return out


def vimshottari(moon_lon: float, birth: dt.date):
    """Maha-dasha sequence from the natal Moon's nakshatra. The balance of the first period is set
    by how far the Moon had already travelled through its nakshatra — which is exactly why an
    unknown birth time matters, and why the caller brackets it."""
    nak_i = int(moon_lon // NAK_SPAN) % 27
    lord = DASHA_ORDER[nak_i % 9]
    frac_done = (moon_lon % NAK_SPAN) / NAK_SPAN
    start_i = DASHA_ORDER.index(lord)
    seq, cursor = [], birth - dt.timedelta(days=frac_done * DASHA_YEARS[lord] * YEAR_DAYS)
    for k in range(10):
        g = DASHA_ORDER[(start_i + k) % 9]
        yrs = DASHA_YEARS[g]
        end = cursor + dt.timedelta(days=yrs * YEAR_DAYS)
        seq.append({"lord": g, "from": cursor.isoformat(), "to": end.isoformat(), "years": yrs})
        cursor = end
    return seq


def current_dasha(seq, today: dt.date):
    for i, d in enumerate(seq):
        if d["from"] <= today.isoformat() < d["to"]:
            # antardasha: each sub-period is maha_years * antar_years / 120
            maha = d["lord"]
            s = dt.date.fromisoformat(d["from"])
            si = DASHA_ORDER.index(maha)
            for k in range(9):
                g = DASHA_ORDER[(si + k) % 9]
                days = DASHA_YEARS[maha] * DASHA_YEARS[g] / TOTAL_YEARS * YEAR_DAYS
                e = s + dt.timedelta(days=days)
                if s <= today < e:
                    return {"maha": maha, "maha_from": d["from"], "maha_to": d["to"],
                            "antar": g, "antar_from": s.isoformat(), "antar_to": e.isoformat()}
                s = e
            return {"maha": maha, "maha_from": d["from"], "maha_to": d["to"],
                    "antar": None, "antar_from": None, "antar_to": None}
    return None


def antar_ladder(maha: str, maha_from: str) -> list:
    """Every antardasha inside one mahadasha, with dates. current_dasha() finds only the period
    running today; a reader wants to see when it ends and what follows, which needs the ladder."""
    s = dt.date.fromisoformat(maha_from)
    si = DASHA_ORDER.index(maha)
    out = []
    for k in range(9):
        g = DASHA_ORDER[(si + k) % 9]
        e = s + dt.timedelta(days=DASHA_YEARS[maha] * DASHA_YEARS[g] / TOTAL_YEARS * YEAR_DAYS)
        out.append({"lord": g, "from": s.isoformat(), "to": e.isoformat()})
        s = e
    return out


def upcoming_changes(seq, today: dt.date, n: int = 3) -> list:
    """The next n dated period changes — antardasha handovers first, then the next mahadasha.
    Dates, not vibes: this is what makes the tradition's claim falsifiable in advance."""
    out = []
    for i, d in enumerate(seq):
        if d["to"] <= today.isoformat():
            continue
        for a in antar_ladder(d["lord"], d["from"]):
            if a["from"] > today.isoformat() and a["from"] < d["to"]:
                out.append({"kind": "antar", "on": a["from"], "lord": a["lord"],
                            "under": d["lord"],
                            "text": f"{a['lord']} antardasha begins inside the {d['lord']} mahadasha"})
        if i + 1 < len(seq):
            out.append({"kind": "maha", "on": d["to"], "lord": seq[i + 1]["lord"], "under": None,
                        "text": f"the {d['lord']} mahadasha ends and the {seq[i + 1]['lord']} "
                                f"mahadasha begins"})
    out.sort(key=lambda x: x["on"])
    return out[:n]


def transits_to_natal(natal: dict, now_pos: dict) -> list:
    """What the sky is doing TO this chart right now. Conjunction within 2.5 degrees only — the
    tighter the orb the harder it is to claim a hit after the fact. Same orb as dashboard/app.js's
    gocharaRead() (the personal-chart equivalent of this check) — kept equal on purpose so a
    company chart and a person's chart don't disagree on what counts as "conjunct" for no reason.
    Not the same question as astro_engine.py's find_events() conjunctions (1.0 deg): that one logs
    the single exact-minimum day two transiting bodies pass each other, this one asks "is anything
    near this natal point right now" on any given day — different questions, deliberately different
    orbs."""
    out = []
    for t, tp in now_pos.items():
        for n, np_ in natal.items():
            sep = abs((tp["lon"] - np_["lon"] + 180) % 360 - 180)
            if sep <= 2.5:
                out.append({"transiting": t, "over_natal": n, "orb_deg": round(sep, 2),
                            "sign": tp["sign"],
                            "text": f"transiting {t} is conjunct natal {n} ({round(sep, 2)}° orb)"})
    out.sort(key=lambda x: x["orb_deg"])
    return out


def sade_sati(natal_moon_sign_i: int, saturn_lon: float):
    """Saturn through the 12th, 1st and 2nd signs from the natal Moon — the most-cited Vedic
    transit there is. Purely mechanical from two sign positions."""
    sat_i = ae.sign_of(saturn_lon)
    rel = (sat_i - natal_moon_sign_i) % 12
    if rel == 11:
        return {"active": True, "phase": "rising (Saturn in the 12th from natal Moon)"}
    if rel == 0:
        return {"active": True, "phase": "peak (Saturn over the natal Moon)"}
    if rel == 1:
        return {"active": True, "phase": "setting (Saturn in the 2nd from natal Moon)"}
    if rel in (3, 7):
        return {"active": False, "phase": f"Dhaiya (Saturn in the {rel + 1}th from natal Moon)"}
    return {"active": False, "phase": None}


def build_one(chart: dict, now_e: Epoch, now_pos: dict, today: dt.date) -> dict:
    # bracket the unknown time: compute the chart at the open AND at the close
    e_open = _epoch_for(chart["date"], chart["time"])
    e_close = _epoch_for(chart["date"], CLOSE_TIME)
    n_open, n_close = natal_positions(e_open), natal_positions(e_close)
    birth = dt.date.fromisoformat(chart["date"])

    # what survives the unknown time, and what doesn't
    stable = {}
    for b in ae.BODIES:
        stable[b] = {"sign": n_open[b]["sign"] == n_close[b]["sign"],
                     "nakshatra": n_open[b]["nakshatra"] == n_close[b]["nakshatra"]}
    moon_sign_stable = stable["Moon"]["sign"]
    moon_nak_stable = stable["Moon"]["nakshatra"]

    seq_o = vimshottari(n_open["Moon"]["lon"], birth)
    seq_c = vimshottari(n_close["Moon"]["lon"], birth)
    cur_o, cur_c = current_dasha(seq_o, today), current_dasha(seq_c, today)
    # Report what is and isn't usable, separately — "all unstable" would throw away real signal.
    # The LORD of the current period can be solid even when its dates are not.
    maha_lord_stable = bool(cur_o and cur_c and cur_o["maha"] == cur_c["maha"] and moon_nak_stable)
    antar_lord_stable = bool(maha_lord_stable and cur_o and cur_c and cur_o["antar"] == cur_c["antar"])
    dasha_stable = antar_lord_stable
    # How far the WHOLE timeline slides — measured on the same boundary (the sequence start), not
    # by comparing two different periods' end dates, which would report nonsense.
    slip_days = abs((dt.date.fromisoformat(seq_o[0]["from"])
                     - dt.date.fromisoformat(seq_c[0]["from"])).days)

    moon_i = ae.sign_of(n_open["Moon"]["lon"])
    ss = sade_sati(moon_i, now_pos["Saturn"]["lon"]) if moon_sign_stable else {
        "active": None, "phase": "cannot be determined — the natal Moon's sign is not stable across "
                                "the unknown first-trade time"}

    return {
        "subject": chart["subject"], "kind": chart["kind"],
        "birth": {"date": chart["date"], "time_convention": chart["time"], "place": chart["place"],
                  "certainty": chart["certainty"], "source": chart["source"]},
        "natal": n_open,
        "ascendant": None,
        "ascendant_note": ("Deliberately not computed. PSX publishes no first-trade time; the "
                           "ascendant moves 360° a day, so houses from a guessed time would be "
                           "fiction. This chart is read from the Moon sign (Chandra lagna), which "
                           "is standard Vedic practice and survives the unknown time."),
        "time_sensitivity": {
            "published_at": f"{chart['time']} — the exchange open on the first-trade date, which is "
                            f"the orthodox first-trade convention (Meridian). This is the chart.",
            "method": f"the chart is ALSO computed at the {CLOSE_TIME} close, purely to measure how "
                      f"much each conclusion depends on the convention being right",
            "per_graha": stable,
            "moon_sign_stable": moon_sign_stable,
            "moon_nakshatra_stable": moon_nak_stable,
            "maha_lord_stable": maha_lord_stable,
            "antar_lord_stable": antar_lord_stable,
            "dasha_stable": dasha_stable,
            "dasha_timeline_slip_days": slip_days,
            "verdict": ("Robust: this chart reads the same whether the first trade happened at the "
                        "open or the close, so the convention is not doing the work."
                        if dasha_stable and moon_sign_stable else
                        f"Convention-dependent. The Moon covers ~3.3° in a session and a nakshatra "
                        f"is 13.3°, so had the first trade come at the close instead of the open the "
                        f"whole Vimshottari timeline would sit ~{slip_days} days "
                        f"({slip_days / 365.25:.1f} years) away. The published dates follow the "
                        f"convention; treat them as convention-dependent, not measured. The period "
                        f"LORD is the sturdier claim — see maha_lord_stable."),
        },
        "dasha": {"current": cur_o, "convention_robust": dasha_stable,
                  "sequence": seq_o[:6],
                  "antar_ladder": (antar_ladder(cur_o["maha"], cur_o["maha_from"]) if cur_o else []),
                  "upcoming": upcoming_changes(seq_o, today, 3),
                  "note": (f"Vimshottari, keyed to the natal Moon's nakshatra, cast at the exchange "
                           f"open per the first-trade convention. Every boundary inherits the Moon's "
                           f"exact degree, so if the true first trade came later in the session the "
                           f"timeline moves ~{slip_days} days ({slip_days / 365.25:.1f} years). "
                           f"Published as the convention's answer, with that dependence stated.")},
        "sade_sati": ss,
        "transits_to_natal": transits_to_natal(n_open, now_pos),
    }


def main():
    STATE.mkdir(exist_ok=True)
    cf = STATE / "company_charts.json"
    if not cf.exists():
        print("astro_natal: no company_charts.json — run scripts/astro_charts.py first")
        sys.exit(0)
    charts = json.loads(cf.read_text(encoding="utf-8"))
    now_utc = dt.datetime.now(dt.timezone.utc)
    now_e = ae._epoch(now_utc)
    today = now_utc.astimezone(ae.PKT).date()
    try:
        now_pos = {b: {"lon": ae.sidereal(b, now_e), "sign": ae.SIGNS[ae.sign_of(ae.sidereal(b, now_e))]}
                   for b in ae.BODIES}
    except Exception as e:
        print(f"astro_natal: sky computation failed ({type(e).__name__}: {e})")
        sys.exit(0)

    out = {}
    for sym, ch in (charts.get("charts") or {}).items():
        try:
            out[sym] = build_one(ch, now_e, now_pos, today)
        except Exception as e:
            print(f"astro_natal: {sym} failed ({type(e).__name__}: {e}) — skipped")

    res = {
        "updated": now_utc.astimezone(ae.PKT).strftime("%Y-%m-%d %H:%M"),
        "note": ("Natal charts, Vimshottari dashas and transits-to-natal for the subjects whose "
                 "first-trade date is genuinely sourced. Cast at the exchange open on that date — "
                 "the orthodox first-trade convention (Meridian), not a guess of ours. No ascendant "
                 "and no houses: those turn on the minute, and PSX's open has itself shifted over "
                 "the decades. Each conclusion carries how much it depends on the convention."),
        "convention": {
            "birth_moment": "first trade date, cast at the exchange open",
            "why": ("Financial astrology's standard. Bill Meridian built the field's first-trade "
                    "database after testing INCORPORATION charts and rejecting them — he was 'not "
                    "satisfied with the relationship of the chart of incorporation with share price "
                    "movements'. His charts are set to the exchange open, 'the moment at which one "
                    "could actually buy the stock'. So the incorporation-date alternative is the one "
                    "the tradition already tried and discarded."),
            "source": "https://billmeridian.com/articles-files/history-fin-astro.htm",
            "meridian_got_his_dates_from": ("the Exchange itself, from the 1970s. That is the unlock "
                                            "for the other 88 PSX names: PSX holds the listing dates "
                                            "even though it does not publish them."),
        },
        "discipline": ("This is what the tradition SAYS about these charts. It is not a forecast and "
                       "not advice. The transit-only claims the desk could test showed no edge on "
                       "PSX (see astro_backtest.json); the natal methods here are not yet tested, "
                       "and are labelled untested rather than sold as insight."),
        "n_charts": len(out),
        "subjects": out,
    }
    (STATE / "astro_natal.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(f"astro_natal: {len(out)} charts built")
    for sym, r in list(out.items())[:16]:
        d = (r["dasha"]["current"] or {})
        st = r["time_sensitivity"]
        ss = r["sade_sati"]
        print(f"  {sym:9} b.{r['birth']['date']} Moon {r['natal']['Moon']['sign']:11} "
              f"{r['natal']['Moon']['nakshatra']:16} | dasha {d.get('maha','?')}/{str(d.get('antar','?')):8} "
              f"to {str(d.get('maha_to'))[:7]} | robust={st['dasha_stable']!s:5} slip={st['dasha_timeline_slip_days']}d"
              f"{' | SADE SATI: ' + ss['phase'] if ss.get('active') else ''}")
    ok = sum(1 for r in out.values() if r["time_sensitivity"]["maha_lord_stable"])
    rob = sum(1 for r in out.values() if r["time_sensitivity"]["dasha_stable"])
    ssn = sum(1 for r in out.values() if (r["sade_sati"] or {}).get("active"))
    print(f"\n  dashas published at the first-trade convention (exchange open): {len(out)} of {len(out)}")
    print(f"  ... of which the period LORD holds even at the close: {ok} of {len(out)}")
    print(f"  ... fully convention-independent (lord AND dates): {rob} of {len(out)}")
    print(f"  Sade Sati running: {ssn} of {len(out)}")


if __name__ == "__main__":
    main()
