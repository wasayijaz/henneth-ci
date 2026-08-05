"""One-time filter step: reads the 4 raw Firecrawl backfill files (May/Jun/Jul/Aug 2026, "C"
category, ~3334 rows) and keeps only genuine insider/substantial-shareholder disclosure rows,
tagged to a known universe symbol, deduped. Uses the same _TITLE_RE as
scripts/fetch_insider_offmarket.py. Writes .firecrawl/insider-filtered.json for the next stage
(PDF-content extraction). Ad-hoc script, not part of the cycle pipeline."""
import json
import re
from pathlib import Path

from psx_data import market_symbols

ROOT = Path(__file__).resolve().parent.parent
FC = ROOT / ".firecrawl"

BACKFILL_FILES = [
    "backfill-may-full-out.json",
    "backfill-jun-full-out.json",
    "backfill-jul-full-out.json",
    "backfill-aug-partial-out.json",
]

_TITLE_RE = re.compile(r"(Disclosure of Interest|Substantial Shareholder|Change in Shareholding)",
                        re.I)


def main():
    universe = set(market_symbols("PSX"))

    raw_rows = []
    for fname in BACKFILL_FILES:
        path = FC / fname
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_rows.extend(data["rows"])
        print(f"{fname}: {len(data['rows'])} raw rows")

    print(f"total raw: {len(raw_rows)}")

    kept = []
    dropped_title = 0
    dropped_symbol = 0
    for row in raw_rows:
        title = row.get("title", "")
        m = _TITLE_RE.search(title)
        if not m:
            dropped_title += 1
            continue
        sym = row.get("symbol", "").strip()
        if sym not in universe:
            dropped_symbol += 1
            continue
        kept.append({
            "symbol": sym,
            "date": row.get("date"),
            "time": row.get("time"),
            "title": m.group(1),
            "pdf_url": row.get("pdf_url"),
        })

    print(f"dropped (title mismatch): {dropped_title}")
    print(f"dropped (symbol not in universe): {dropped_symbol}")
    print(f"kept before dedupe: {len(kept)}")

    seen = set()
    deduped = []
    for row in kept:
        key = (row["symbol"], row["date"], row["title"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    print(f"kept after dedupe: {len(deduped)}")

    null_pdf = sum(1 for r in deduped if not r["pdf_url"])
    print(f"null pdf_url: {null_pdf}")

    out_path = FC / "insider-filtered.json"
    out_path.write_text(json.dumps({"count": len(deduped), "rows": deduped}, indent=2),
                         encoding="utf-8")
    print(f"wrote {out_path} ({len(deduped)} rows)")


if __name__ == "__main__":
    main()
