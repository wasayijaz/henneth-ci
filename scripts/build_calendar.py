"""Normalize scraped earnings + ex-dividend dates into a single forward-looking
calendar (state/earnings_calendar.json). Deterministic: parses the loose date
strings from fundamentals.json (e.g. 'Jul 29, 2026', 'Aug 28') and dividends.json.
The fundamentals-agent later verifies these and flips confirmed=true with a source.

Dividend timing rule (PSX, retail): to RECEIVE a dividend you must hold shares
BEFORE the ex-dividend date. So buy_by = last session before ex-date; you may
sell ON or AFTER the ex-date and still receive it (sell_ok_from = ex-date)."""
import re
import time
from datetime import date, datetime, timedelta

from psx_data import STATE, load_json, save_json

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_loose(s: str, today: date) -> str | None:
    """'Jul 29, 2026' or 'Aug 28' (assume next occurrence) -> ISO date."""
    if not s:
        return None
    m = re.match(r"([A-Za-z]{3})\s+(\d{1,2})(?:,\s*(\d{4}))?", s.strip())
    if not m:
        return None
    mon = MONTHS.get(m.group(1)[:3].title())
    if not mon:
        return None
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else today.year
    try:
        d = date(year, mon, day)
    except ValueError:
        return None
    if not m.group(3) and d < today:  # no year given and already passed -> next year
        d = date(year + 1, mon, day)
    return d.isoformat()


def prev_business_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    d -= timedelta(days=1)
    while d.weekday() >= 5:  # sat/sun
        d -= timedelta(days=1)
    return d.isoformat()


def main():
    today = date.today()
    fund = load_json(STATE / "fundamentals.json", {"tickers": {}})["tickers"]
    divs = load_json(STATE / "dividends.json", {"upcoming": [], "history": []})

    events = []
    for sym, v in fund.items():
        ed = parse_loose(v.get("next_earnings", ""), today)
        if ed and ed >= today.isoformat():
            events.append({"ticker": sym, "type": "results", "date": ed,
                           "confirmed": False, "source": v.get("source_url"),
                           "note": "scraped estimate — fundamentals-agent verifies"})
        xd = parse_loose(v.get("ex_div_date", ""), today)
        if xd and xd >= today.isoformat():
            dr = None
            m = re.search(r"([\d.]+)", str(v.get("div_yield", "")))
            events.append({"ticker": sym, "type": "ex_dividend", "date": xd,
                           "buy_by": prev_business_day(xd), "sell_ok_from": xd,
                           "div_yield": v.get("div_yield"), "confirmed": False,
                           "source": v.get("source_url")})

    # DPS upcoming book closures (buy_by already computed there)
    for d in divs.get("upcoming", []):
        if d.get("bc_start"):
            events.append({"ticker": d["symbol"], "type": "book_closure",
                           "date": d["bc_start"], "bc_end": d.get("bc_end"),
                           "buy_by": d.get("buy_by"), "sell_ok_from": d.get("bc_start"),
                           "dividend_rs": d.get("dividend_rs"),
                           "yield_pct": d.get("yield_pct_at_close"),
                           "announcement": d.get("announcement"), "confirmed": True,
                           "source": "https://dps.psx.com.pk/company/" + d["symbol"]})

    events.sort(key=lambda e: e["date"])
    save_json(STATE / "earnings_calendar.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "note": "scraped/normalized; confirmed=true only after fundamentals-agent verifies vs primary source",
        "events": events,
    })
    res = sum(1 for e in events if e["type"] == "results")
    dv = sum(1 for e in events if e["type"] in ("ex_dividend", "book_closure"))
    print(f"calendar: {len(events)} forward events ({res} results, {dv} dividend/closure)")
    for e in events[:8]:
        print(f"  {e['date']} {e['ticker']} {e['type']}")


if __name__ == "__main__":
    main()
