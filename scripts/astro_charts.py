"""Birth charts for the astro pillar — and an honest account of which ones we can't have.

WHAT A COMPANY'S "BIRTH" IS
Financial astrology's standard convention is the FIRST TRADE: the moment the stock began trading
is treated as its birth. That is a real, dateable event — when it can be sourced.

WHY MOST PSX NAMES CANNOT HAVE A CHART, AND WHY WE SAY SO INSTEAD OF FAKING ONE
  * PSX publishes no listing date. dps.psx.com.pk/listings is empty and company pages carry only
    "incorporated under the Companies Act, 1913" — a legal reference, not a date.
  * Yahoo's firstTradeDate is CENSORED at its own data start: 77 of 99 PSX tickers report
    2008-01-01, which is when Yahoo's coverage begins, not when the company listed. FFC listed in
    1991; trusting that field would give FFC — and 76 other companies — the same fabricated chart.
  * The web gives years only. Wikipedia on FFC: "listed on the Karachi Stock Exchange in 1991".
    A year is useless for a chart: the Moon moves 13 degrees a DAY and the ascendant 360.
So a chart is built ONLY where the date is genuinely sourced. Everywhere else this file records
WHY there is none, and the product says so rather than inventing a birth moment. A fabricated chart
would poison every reading built on it, invisibly and forever.

INCORPORATION DATE — investigated and rejected as a fallback (2026-08). DPS company profiles
(dps.psx.com.pk/company/<TICKER>, BUSINESS DESCRIPTION paragraph) carry a real incorporation date
for most of the `unavailable` tickers (191/409 full date — see state/incorporation_audit.json).
Not used: incorporation date is a legal-formation event, not a market birth, and can sit decades
from actual listing (Attock Cement: incorporated 1981, listed 2002). astro_natal.py's own docstring
already documents that Meridian built and abandoned incorporation charts for exactly this reason.
Don't re-run this audit expecting a different answer — the gap is PSX not publishing listing dates,
not a data-source we haven't tried yet.

TIME
PSX does not publish a first-trade time either. We use the market open on the listing date as a
stated CONVENTION, and mark the chart accordingly: the ascendant depends entirely on it and is
flagged unreliable. The Moon's sign is stable across a trading day; its nakshatra usually is, and
the chart says when it isn't (a boundary within the session).

Writes state/company_charts.json. Network failure -> keeps the existing file, exits 0.
"""
import collections
import datetime as dt
import json
import pathlib
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "company_charts.json"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

KARACHI = {"place": "Karachi, Pakistan", "lat": 24.8607, "lon": 67.0011, "tz": "+05:00"}
# PSX opens 09:32 today; through most of the period it opened ~09:30. One convention, disclosed.
OPEN_TIME = "09:30"
SENTINEL_MIN = 5          # a firstTradeDate shared by >= this many tickers is a data-start artefact
# Yahoo's PSX coverage begins around 2007-09 / 2008-01. Near that edge we CANNOT tell "listed then"
# from "data starts then" — the crowd sits on 2008-01-01 but stragglers land on 2008-01-02/03 and
# late 2007, and those are old companies (Treet, Rafhan Maize, Bestway Cement listed decades ago).
# So anything within this window of the earliest date in the whole dataset is unverifiable, full stop.
COVERAGE_GRACE_DAYS = 200

# The market's own chart. Date verified against PSX's index methodology brochure (base period
# November 1991, base value 1,000). No launch time is published.
KSE100_CHART = {
    "subject": "KSE100",
    "kind": "index",
    "date": "1991-11-01",
    "time": OPEN_TIME,
    "certainty": "date_verified_time_convention",
    "source": "https://www.psx.com.pk/psx/themes/psx/uploads/KSE_100_Index_New_Brochure.pdf",
    "note": "PSX publishes the base DATE (1 Nov 1991, base 1,000) but no launch time. Time is the "
            "market open by convention — the ascendant depends on it and must not be leaned on.",
    **KARACHI,
}


def fetch_first_trades(symbols) -> dict:
    s = requests.Session()
    s.headers.update(HDRS)
    got = {}
    for sym in symbols:
        try:
            r = s.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.KA"
                      f"?range=1d&interval=1d", timeout=15)
            meta = r.json()["chart"]["result"][0]["meta"]
            ftd = meta.get("firstTradeDate")
            if ftd:
                got[sym] = dt.datetime.fromtimestamp(ftd, dt.timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            continue
    return got


def main():
    STATE.mkdir(exist_ok=True)
    # PSX ONLY. fetch_first_trades() below asks Yahoo for `{sym}.KA` firstTradeDate, so a US
    # symbol would be requested as `XLE.KA` and return nothing. More to the point, a first-trade
    # chart for an ETF is not a company horoscope — the Meridian convention this file implements
    # is about a listed COMPANY's first trade, and an index fund has no birth in that sense.
    _uni_all = json.loads((STATE / "universe.json").read_text(encoding="utf-8"))["symbols"]
    uni = {s: m for s, m in _uni_all.items() if (m or {}).get("market", "PSX") == "PSX"}
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    # TIER 1 — the Exchange's own record. state/listing_dates.json is parsed from PSX's official
    # floatation workbooks ("Date of Formal Listing", psx.com.pk Listings History, 2000-2013 +
    # 2018-2026). This is the same source Meridian used, and it beats any inference: where it
    # disagrees with Yahoo's first bar (NPL: listed 2009-10-07, Yahoo starts 2010-02-22), the
    # Exchange is right and Yahoo was late.
    exchange = {}
    ldp = STATE / "listing_dates.json"
    if ldp.exists():
        try:
            exchange = json.loads(ldp.read_text(encoding="utf-8")).get("tickers", {})
        except Exception:
            exchange = {}

    first = fetch_first_trades(sorted(uni))
    if len(first) < 20 and not exchange:
        print(f"astro_charts: only {len(first)} first-trade dates fetched — keeping the existing file")
        sys.exit(0)

    # Any date shared by a crowd of tickers is Yahoo's coverage start, not a listing day.
    counts = collections.Counter(first.values())
    sentinels = {d for d, n in counts.items() if n >= SENTINEL_MIN}
    earliest = min(first.values())
    edge = (dt.date.fromisoformat(earliest) + dt.timedelta(days=COVERAGE_GRACE_DAYS)).isoformat()

    charts = {"KSE100": KSE100_CHART}
    unavailable = {}
    for sym, d in sorted(exchange.items()):
        if sym not in uni:
            continue
        charts[sym] = {
            "subject": sym, "kind": "stock", "date": d, "time": OPEN_TIME,
            "certainty": "date_exchange_verified_time_convention",
            "source": ("PSX's own floatation workbook, column 'Date of Formal Listing' "
                       "(psx.com.pk > Listings > Listings History) — the Exchange's record"),
            "note": "Time is the PSX open by convention; the Exchange records the date, not the "
                    "minute. The ascendant depends on the minute and is not computed.",
            **KARACHI,
        }
    for sym, d in sorted(first.items()):
        if sym in charts:
            continue                      # the Exchange's record outranks any inference
        if d in sentinels:
            unavailable[sym] = (f"Yahoo reports first trade {d}, but {counts[d]} tickers share that "
                                f"date — it is the start of Yahoo's PSX coverage, not this "
                                f"company's listing. No verified listing date exists.")
            continue
        if d <= edge:
            unavailable[sym] = (f"Yahoo reports first trade {d}, which sits at the ragged edge of "
                                f"its PSX coverage (earliest in the whole dataset: {earliest}). At "
                                f"that edge 'listed then' and 'our data starts then' are "
                                f"indistinguishable, so this is not a usable birth date.")
            continue
        charts[sym] = {
            "subject": sym, "kind": "stock", "date": d, "time": OPEN_TIME,
            "certainty": "date_verified_time_convention",
            "source": f"Yahoo Finance firstTradeDate for {sym}.KA — trusted here only because it "
                      f"falls outside the data-start cluster, i.e. the history genuinely begins at "
                      f"this company's listing",
            "note": "Time is the PSX open by convention; PSX publishes no first-trade time. The "
                    "ascendant depends on it and is not reliable.",
            **KARACHI,
        }
    for sym in uni:
        if sym not in charts and sym not in unavailable:
            unavailable[sym] = "No first-trade date available from any source the desk uses."

    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "convention": {
            "birth_moment": "first trade (the standard convention in financial astrology)",
            "time": f"PSX open ({OPEN_TIME} PKT) on the listing date — a stated convention, not a "
                    f"published fact. The ascendant depends entirely on it.",
            "place": "Karachi (the exchange), not the company's head office",
            "zodiac": "sidereal, Lahiri — same engine as astro.json",
        },
        "honesty": ("A chart is built ONLY where the listing date is genuinely sourced. Yahoo's "
                    "firstTradeDate is censored at its coverage start (77 of 99 PSX tickers report "
                    "2008-01-01), PSX publishes no listing dates, and the web gives years only — so "
                    "most PSX companies CANNOT have an honest natal chart, and this file names each "
                    "one and says why. A fabricated birth moment would corrupt every reading built "
                    "on it, permanently and invisibly."),
        "counts": {"charts": len(charts), "unavailable": len(unavailable)},
        "charts": charts,
        "unavailable": unavailable,
        "how_to_add_one": ("Supply a sourced listing date (PSX listing notice, the company's own "
                           "annual report, or a prospectus) and it becomes a real chart here. The "
                           "desk will take a dated document over a guess every time."),
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"astro_charts: {len(charts)} verified charts ({len(charts) - 1} stocks + KSE100) | "
          f"{len(unavailable)} with no honest birth date")
    for k, v in list(charts.items())[:20]:
        print(f"   {k:10} {v['date']}  {v['certainty']}")


if __name__ == "__main__":
    main()
