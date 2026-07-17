"""Natal charts, Vimshottari dashas, and transits-to-natal — the actual method of Vedic prediction.

The earlier backtest tested transits IN ISOLATION (retrograde, combust, dignity, eclipses) and found
nothing. That was never the whole of the tradition. Vedic prediction is mostly about two things this
desk had not touched:
  * TRANSITS TO A NATAL CHART — Saturn crossing the natal Moon (Sade Sati), Jupiter's return, etc.
  * DASHAS — Vimshottari planetary periods, keyed to the natal Moon's nakshatra.
This computes both, for the 15 subjects whose birth date is genuinely sourced (astro_charts.py).

TWO DELIBERATE REFUSALS, because a chart is only as honest as its worst input:

1. NO ASCENDANT, NO HOUSES. PSX publishes no first-trade TIME. The ascendant moves 360 degrees a
   day, so houses computed from a guessed time are fiction dressed as precision. We read from the
   Moon sign (Chandra lagna) instead — which is standard Vedic practice, and stable across a
   session. Half a chart that is true beats a whole one that is invented.

2. EVERY CONCLUSION IS TESTED FOR TIME-STABILITY. The chart is computed twice, at the market open
   AND at the close, and anything that DISAGREES between the two is marked unstable and must not be
   published. This turns the unknown time from a hidden lie into a measured uncertainty — most
   notably for dashas, whose start dates hinge on the Moon's exact degree and can shift by years.

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


def transits_to_natal(natal: dict, now_pos: dict) -> list:
    """What the sky is doing TO this chart right now. Conjunction within 3 degrees only — the
    tighter the orb the harder it is to claim a hit after the fact."""
    out = []
    for t, tp in now_pos.items():
        for n, np_ in natal.items():
            sep = abs((tp["lon"] - np_["lon"] + 180) % 360 - 180)
            if sep <= 3.0:
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
        "time_stability": {
            "method": f"the chart is computed twice — at the {chart['time']} open and the "
                      f"{CLOSE_TIME} close — and anything that disagrees is not publishable",
            "per_graha": stable,
            "moon_sign_stable": moon_sign_stable,
            "moon_nakshatra_stable": moon_nak_stable,
            "maha_lord_stable": maha_lord_stable,
            "antar_lord_stable": antar_lord_stable,
            "dasha_stable": dasha_stable,
            "dasha_timeline_slip_days": slip_days,
            "verdict": ("Everything below survives the unknown first-trade time."
                        if dasha_stable and moon_sign_stable else
                        f"Partly unusable. The Moon travels ~3.3° across a trading session and a "
                        f"nakshatra is 13.3°, so an unknown birth time slides the whole Vimshottari "
                        f"timeline by ~{slip_days} days ({slip_days / 365.25:.1f} years) here. The "
                        f"period LORDS may still be solid — see maha_lord_stable / antar_lord_stable "
                        f"— but DATED dasha predictions are not available for this subject and the "
                        f"desk will not print them."),
        },
        "dasha": {"current": cur_o, "stable": dasha_stable,
                  "sequence": seq_o[:6],
                  "note": ("Vimshottari, keyed to the natal Moon's nakshatra. The start of the very "
                           "first period depends on the Moon's exact degree, so an unknown birth "
                           "time propagates into every boundary — the slip across one trading "
                           f"session is {slip_days} days here.")},
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
                 "birth date is genuinely sourced. No ascendant and no houses: the first-trade time "
                 "is unpublished, so they would be invented. Every conclusion is bracketed across "
                 "the trading session and marked unstable if the unknown time changes it."),
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
        ss = r["sade_sati"]
        print(f"  {sym:9} b.{r['birth']['date']} Moon {r['natal']['Moon']['sign']:11} "
              f"{r['natal']['Moon']['nakshatra']:16} | dasha {d.get('maha','?')}/{d.get('antar','?'):8} "
              f"stable={r['time_stability']['dasha_stable']!s:5} slip={r['time_stability']['dasha_boundary_slip_days']}d"
              f"{' | SADE SATI: ' + ss['phase'] if ss.get('active') else ''}")


if __name__ == "__main__":
    main()
