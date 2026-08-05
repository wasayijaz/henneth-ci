"""One-time backfill: pulls 90 days of PSX off-market CSVs (dps.psx.com.pk/download/omts) and
seeds state/offmarket_activity.json's per-day retained history. Reuses the same fetch/parse
helpers fetch_insider_offmarket.py uses weekly. Ad-hoc, not part of the cycle pipeline.
"""
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

from fetch_insider_offmarket import _fetch_omts_csv, _parse_omts_csv

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
BACKFILL_DAYS = 95  # a few days of slack over the strict 90 (weekends/holidays 404)


def main():
    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"})

    days: dict[str, dict] = {}
    today = date.today()
    covered = 0
    for i in range(1, BACKFILL_DAYS + 1):
        day = today - timedelta(days=i)
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
            days[day.isoformat()] = per_symbol
            covered += 1
        time.sleep(0.15)
        if i % 20 == 0:
            print(f"  {i}/{BACKFILL_DAYS} scanned, {covered} trading days found")

    out_path = STATE / "offmarket_activity.json"
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    existing_days = existing.get("days", {})
    existing_days.update(days)  # backfill fills gaps; doesn't overwrite anything newer

    out_path.write_text(json.dumps({
        "updated": existing.get("updated", "backfill"),
        "source": "dps.psx.com.pk/download/omts",
        "stale": False,
        "retention_days": 90,
        "days": existing_days,
    }, indent=2), encoding="utf-8")

    print(f"backfilled {covered} trading days, {len(existing_days)} total days in history")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
