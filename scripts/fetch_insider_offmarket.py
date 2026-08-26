"""Fetch off-market transactions (PSX DPS daily CSV) and insider/substantial-shareholder
disclosures (PSX DPS announcements page) for every universe symbol.

Off-market: https://dps.psx.com.pk/download/omts/{date}.csv is a plain static file, no JS
rendering needed -- pulled directly with `requests`. Two sections per day (member-to-member,
cross client/institution); both roll into one per-symbol per-day total. Only trading-day CSVs
exist (weekends/holidays 404, today's date 404s until EOD publish) -- 404s are expected, not
errors.

Insider/substantial-shareholder disclosures: dps.psx.com.pk/announcements/companies is
client-side JS-hydrated (confirmed: plain GET returns none of the rendered rows). The
underlying AJAX endpoint needs session/CSRF state a bare POST can't reproduce, so this scrapes
the rendered page via the Firecrawl CLI instead and regex-filters the result. Filing metadata
(date, symbol, title, pdf link) is captured every week; PDF-content parsing (insider name/role,
shares, price) is a separate one-time backfill step (scripts/seed_insider_history.py) -- new
weekly filings land with transactions: [] until parsed. Desk hard-rule #2: unknown beats a
guess, so no direction is ever inferred from metadata alone.

RETAINED HISTORY, not a trailing-window snapshot: both state files ACCUMULATE across weekly
runs (>= 3 months retained per desk brief 2026-08-05), rather than being fully overwritten each
run. Off-market prunes days older than OFFMARKET_RETENTION_DAYS; insider filings are never
pruned (low volume, high signal value).

Weekly cadence, same family as fetch_fundamentals.py. Writes state/offmarket_activity.json and
state/insider_activity.json. Idempotent, degrades gracefully (network/scrape fail -> keep prior
file, exit 0)."""
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

import requests

from psx_data import STATE, load_json, market_symbols, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"}
OMTS_URL = "https://dps.psx.com.pk/download/omts/{date}.csv"
ANNOUNCEMENTS_URL = "https://dps.psx.com.pk/announcements/companies"
FETCH_LOOKBACK_DAYS = 10          # how far back each weekly run scans for new daily CSVs
OFFMARKET_RETENTION_DAYS = 90     # off-market days.json is pruned to this trailing window
INSIDER_SCRAPE_WINDOW_DAYS = 14   # how far back the announcements-page scrape scans for new rows
STALE_DAYS = 7
FAILED_RETRY_DAYS = 1


def _fresh_file(path, days: int) -> bool:
    data = load_json(path, {})
    updated = data.get("updated")
    if not updated:
        return False
    try:
        age = datetime.now() - datetime.strptime(updated, "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    if age.total_seconds() < 0:
        return False
    cadence_days = FAILED_RETRY_DAYS if data.get("stale") else days
    return age.days < cadence_days


def _cadence_skip() -> bool:
    if "--force" in sys.argv:
        return False
    off_ok = _fresh_file(STATE / "offmarket_activity.json", STALE_DAYS)
    insider_ok = _fresh_file(STATE / "insider_activity.json", STALE_DAYS)
    if off_ok and insider_ok:
        print(f"insider/offmarket: skip until {STALE_DAYS}d cadence (--force to refresh)")
        return True
    return False


# ---------------------------------------------------------------------------------------------
# Off-market: pure requests, zero Firecrawl cost.

def _fetch_omts_csv(day: date, sess: requests.Session) -> str | None:
    url = OMTS_URL.format(date=day.strftime("%Y-%m-%d"))
    try:
        r = sess.get(url, timeout=20)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None  # expected on weekends/holidays/today-before-EOD -- not an error
    return r.content.decode("utf-8", errors="replace")


_ROW_RE = re.compile(
    r"^\d{2}-\w{3}-\d{2},\d{2}-\w{3}-\d{2},[^,]*,([A-Z0-9]+),[^,]*,([\d,]+),([\d.]+),([\d,]+)\s*$"
)


def _parse_omts_csv(text: str) -> list[dict]:
    """Rows from BOTH sections (member-to-member, cross client/institution) -- the desk cares
    which symbol traded off-market and how much, not which of the two off-market channels."""
    rows = []
    for line in text.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        sym, turnover, rate, value = m.groups()
        try:
            rows.append({
                "symbol": sym,
                "shares": int(turnover.replace(",", "")),
                "rate": float(rate),
                "value": int(value.replace(",", "")),
            })
        except ValueError:
            continue
    return rows


def fetch_offmarket_days(known_days: set[str]) -> dict[str, dict]:
    """Scan the trailing FETCH_LOOKBACK_DAYS for off-market CSVs not already in history and
    return {iso_date: {symbol: {shares, value, trades}}} for the new days only."""
    sess = requests.Session()
    sess.headers.update(UA)
    new_days: dict[str, dict] = {}
    today = date.today()
    for i in range(1, FETCH_LOOKBACK_DAYS + 1):  # start yesterday -- today 404s until EOD publish
        day = today - timedelta(days=i)
        iso = day.isoformat()
        if iso in known_days:
            continue
        text = _fetch_omts_csv(day, sess)
        if text is None:
            continue
        per_symbol: dict[str, dict] = {}
        for row in _parse_omts_csv(text):
            agg = per_symbol.setdefault(row["symbol"], {"shares": 0, "value": 0, "trades": 0})
            agg["shares"] += row["shares"]
            agg["value"] += row["value"]
            agg["trades"] += 1
        if per_symbol:
            new_days[iso] = per_symbol
        time.sleep(0.2)  # politeness
    return new_days


# ---------------------------------------------------------------------------------------------
# Insider/substantial-shareholder disclosures: Firecrawl scrape (JS-rendered), then filter.

_TITLE_RE = re.compile(r"(Disclosure of Interest|Substantial Shareholder|Change in Shareholding)",
                        re.I)
# Firecrawl's rendered table spells dates 'Mon D, YYYY' (e.g. 'Aug 4, 2026') -- confirmed against
# the actual scrape output, NOT the 'DD-Mon-YY' shape this used to assume (that never matched a
# single row -- root cause of the 0-filings bug). Matches build_calendar.parse_loose's shape.
_DATE_RE = re.compile(r"\b(\w{3,9})\s+(\d{1,2}),\s*(\d{4})\b")
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _parse_announcement_date(s: str) -> str | None:
    """PSX announcement rows spell dates 'Mon D, YYYY' (e.g. 'Aug 4, 2026')."""
    m = _DATE_RE.search(s)
    if not m:
        return None
    mon_s, day_s, year_s = m.groups()
    mon = _MONTHS.get(mon_s[:3].title())
    if not mon:
        return None
    try:
        return date(int(year_s), mon, int(day_s)).isoformat()
    except ValueError:
        return None


def _scrape_announcements() -> str | None:
    """Firecrawl CLI scrape of the JS-hydrated announcements page. Returns markdown or None on
    any failure -- never raises, this must not take the cycle down."""
    out_path = STATE.parent / ".firecrawl" / "insider-scrape.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Windows: "firecrawl" resolves to a .cmd shim (npm global install). subprocess.run without
    # shell=True can't exec a .cmd directly -- resolve the real path via shutil.which first (it
    # honors PATHEXT and finds the .cmd), then run that resolved path with no shell needed.
    exe = shutil.which("firecrawl")
    if exe is None:
        return None
    try:
        r = subprocess.run(
            [exe, "scrape", ANNOUNCEMENTS_URL, "-o", str(out_path)],
            capture_output=True, text=True, timeout=90,
        )
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return None
    if r.returncode != 0 or not out_path.exists():
        return None
    return out_path.read_text(encoding="utf-8", errors="replace")


def _parse_insider_rows(md: str, universe_symbols: set[str]) -> list[dict]:
    """Regex-filter the scraped markdown for insider-type filings within the scrape window,
    tagged to a known universe symbol. Metadata only -- no direction/share-count inference;
    the caller merges these into retained history rather than replacing it."""
    cutoff = date.today() - timedelta(days=INSIDER_SCRAPE_WINDOW_DAYS)
    rows = []
    for line in md.splitlines():
        if not _TITLE_RE.search(line):
            continue
        d = _parse_announcement_date(line)
        if not d or d < cutoff.isoformat():
            continue
        # tag to whichever universe symbol appears as a standalone token in the line
        sym = next((s for s in universe_symbols if re.search(rf"\b{re.escape(s)}\b", line)), None)
        if not sym:
            continue
        title_m = _TITLE_RE.search(line)
        # the row also links the symbol and company name -- both to /company/{SYM}, not the
        # filing. The actual filing is the one link under /download/document/, always last.
        link_m = re.search(r"\((https?://\S*?/download/document/\S+?)\)", line)
        rows.append({
            "symbol": sym,
            "date": d,
            "title": title_m.group(1),
            "pdf_url": link_m.group(1) if link_m else None,
            "source": None,        # not yet PDF-parsed; seed_insider_history.py fills this
            "transactions": [],    # populated by the one-time/backfill PDF-parse step
        })
    # de-dupe (symbol, date, title) -- the page can list the same filing more than once
    seen = set()
    out = []
    for row in rows:
        key = (row["symbol"], row["date"], row["title"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def fetch_insider(universe_symbols: set[str]) -> dict | None:
    md = _scrape_announcements()
    if md is None:
        return None
    rows = _parse_insider_rows(md, universe_symbols)
    by_symbol: dict[str, list] = {}
    for row in rows:
        by_symbol.setdefault(row["symbol"], []).append(row)
    return by_symbol


# ---------------------------------------------------------------------------------------------

def main():
    if _cadence_skip():
        sys.exit(0)

    symbols = set(market_symbols("PSX"))

    # -- off-market: accumulate new days into retained history, prune trailing window --
    prior_omts = load_json(STATE / "offmarket_activity.json", {"days": {}})
    prior_days = prior_omts.get("days", {})
    new_days = fetch_offmarket_days(set(prior_days))
    if not new_days and not prior_days:
        stale = True  # first-ever run and it failed -- nothing to fall back to
        merged_days = {}
    else:
        stale = False
        merged_days = {**prior_days, **new_days}
        cutoff = (date.today() - timedelta(days=OFFMARKET_RETENTION_DAYS)).isoformat()
        merged_days = {d: v for d, v in merged_days.items() if d >= cutoff}
    save_json(STATE / "offmarket_activity.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "dps.psx.com.pk/download/omts",
        "stale": stale,
        "retention_days": OFFMARKET_RETENTION_DAYS,
        "days": merged_days,
    })
    print(f"offmarket: {len(merged_days)} days retained ({len(new_days)} new this run)"
          f"{' (STALE)' if stale else ''}")

    # -- insider: accumulate new filings into retained history, never pruned --
    prior_insider = load_json(STATE / "insider_activity.json", {"symbols": {}})
    existing_symbols = prior_insider.get("symbols", {})
    new_by_symbol = fetch_insider(symbols)
    if new_by_symbol is None:
        insider_stale = True
    else:
        insider_stale = False
        for sym, filings in new_by_symbol.items():
            cur = existing_symbols.setdefault(sym, [])
            # dedupe on (date, pdf_url) -- pdf_url is the actual unique filing identifier;
            # title text can vary slightly (whitespace/truncation) between scrapes of the same
            # page. Fall back to including title only when pdf_url is missing (link regex miss).
            def _key(f):
                return (f.get("date"), f.get("pdf_url")) if f.get("pdf_url") \
                    else (f.get("date"), f.get("pdf_url"), f.get("title"))
            seen = {_key(f) for f in cur}
            for f in filings:
                key = _key(f)
                if key not in seen:
                    cur.append(f)
                    seen.add(key)
            cur.sort(key=lambda f: f.get("date") or "")
    save_json(STATE / "insider_activity.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "dps.psx.com.pk/announcements/companies",
        "stale": insider_stale,
        "symbols": existing_symbols,
    })
    total_filings = sum(len(v) for v in existing_symbols.values())
    print(f"insider: {len(existing_symbols)} symbols, {total_filings} filings retained"
          f"{' (STALE)' if insider_stale else ''}")
    sys.exit(0)


if __name__ == "__main__":
    main()
