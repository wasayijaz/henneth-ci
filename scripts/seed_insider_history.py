"""One-time backfill step: seeds state/insider_activity.json's retained history from
.firecrawl/insider-structured.json (the 300 parsed transactions from the 21-batch Haiku
fan-out). Groups transaction rows back into filings (symbol, date, pdf_url), matches each
filing's title back from insider-scrape.md source rows where possible. Ad-hoc, not part of
the cycle pipeline -- run once, then fetch_insider_offmarket.py takes over weekly accumulation.
"""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FC = ROOT / ".firecrawl"
STATE = ROOT / "state"

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE_RE = re.compile(r"\b(\w{3,9})\s+(\d{1,2}),\s*(\d{4})\b")


def parse_date(s: str) -> str | None:
    m = _DATE_RE.search(s or "")
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


def main():
    structured = json.loads((FC / "insider-structured.json").read_text(encoding="utf-8"))
    rows = structured["rows"]

    filings: dict[tuple, dict] = {}
    for r in rows:
        sym = r.get("symbol")
        filing_date = parse_date(r.get("date"))
        pdf_url = r.get("pdf_url")
        if not sym or not pdf_url:
            continue
        key = (sym, filing_date, pdf_url)
        filing = filings.setdefault(key, {
            "symbol": sym,
            "date": filing_date,
            "title": None,  # not carried through the Haiku extraction batches
            "pdf_url": pdf_url,
            "source": r.get("source"),
            "transactions": [],
        })
        filing["transactions"].append({
            "insider_name": r.get("insider_name"),
            "insider_role": r.get("insider_role"),
            "transaction_type": r.get("transaction_type"),
            "shares_traded": r.get("shares_traded"),
            "price_per_share": r.get("price_per_share"),
            "transaction_date": r.get("transaction_date"),
        })

    by_symbol: dict[str, list] = {}
    for filing in filings.values():
        by_symbol.setdefault(filing["symbol"], []).append(filing)
    for sym in by_symbol:
        by_symbol[sym].sort(key=lambda f: f["date"] or "")

    out_path = STATE / "insider_activity.json"
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    existing_symbols = existing.get("symbols", {})

    # merge on (date, pdf_url). A colliding key is NOT simply skipped: the weekly accumulator
    # (fetch_insider_offmarket.py) records a filing as soon as it appears on the announcements
    # page, before anything has parsed its PDF, so the row already in state is routinely a
    # placeholder with transactions: []. Skipping on collision let those placeholders beat the
    # backfill's fully parsed rows -- 12 filings / 20 transactions were being dropped that way.
    # Enrich instead: fill only fields the existing row is missing. Never overwrite real data,
    # so this stays additive and safe to re-run.
    for sym, new_filings in by_symbol.items():
        cur = existing_symbols.setdefault(sym, [])
        seen = {(f.get("date"), f.get("pdf_url")): f for f in cur}
        for f in new_filings:
            key = (f["date"], f["pdf_url"])
            prior = seen.get(key)
            if prior is None:
                cur.append(f)
                seen[key] = f
                continue
            if not prior.get("transactions") and f["transactions"]:
                prior["transactions"] = f["transactions"]
            for field in ("title", "source"):
                if not prior.get(field) and f.get(field):
                    prior[field] = f[field]
        cur.sort(key=lambda f: f["date"] or "")

    # Carry the existing header through untouched. This script only ADDS history; it knows
    # nothing about the freshness of the weekly scrape, so hardcoding stale=False here would
    # silently clear a real degraded-data flag that data_health.py and the site both read.
    out_path.write_text(json.dumps({
        "updated": existing.get("updated", "backfill"),
        "source": existing.get(
            "source",
            "dps.psx.com.pk/announcements/companies (backfill: Firecrawl paginated + PDF parse)"),
        "stale": existing.get("stale", False),
        "symbols": existing_symbols,
    }, indent=2), encoding="utf-8")

    total_filings = sum(len(v) for v in by_symbol.values())
    total_txns = sum(len(f["transactions"]) for v in by_symbol.values() for f in v)
    print(f"seeded {len(by_symbol)} symbols, {total_filings} filings, {total_txns} transactions")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
