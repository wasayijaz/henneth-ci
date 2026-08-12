#!/usr/bin/env python3
"""Append new items to state/newslog.json without the caller ever loading
the full (growing) log into its own context.

Root cause this replaces: news-sentinel only had Read/Write, so appending
meant reading the whole file into agent context and re-writing it whole
every cycle -- as the log grew (~2000 lines) this caused autocompact
context-thrashing and dropped whole checkpoints. This script does the
read/append/write in a Python process instead; the agent only ever
holds the NEW item(s) in its own context.

Reads a JSON array of new items from a file path or "-" for stdin,
validates required keys, dedupes against existing items by
(url, headline, ts), appends, writes back. Never deletes existing items.

Usage:
  python scripts/newslog_append.py items.json
  echo '[...]' | python scripts/newslog_append.py -
"""
import json
import sys
from pathlib import Path

STATE = Path(__file__).resolve().parent.parent / "state"
LOG = STATE / "newslog.json"
REQUIRED = {"ts", "source", "headline", "tickers", "impact", "summary", "url"}


def load_items(arg):
    raw = sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")
    items = json.loads(raw)
    if not isinstance(items, list):
        raise SystemExit("error: input must be a JSON array of items")
    return items


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: newslog_append.py <items.json|->")
    items = load_items(sys.argv[1])

    for it in items:
        missing = REQUIRED - it.keys()
        if missing:
            raise SystemExit(f"error: item missing keys {missing}: {it}")
        if not isinstance(it["tickers"], list):
            raise SystemExit(f"error: tickers must be a list: {it}")
        if not (1 <= int(it["impact"]) <= 5):
            raise SystemExit(f"error: impact must be 1-5: {it}")

    existing = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    seen = {(e.get("url"), e.get("headline"), e.get("ts")) for e in existing}

    added = 0
    for it in items:
        key = (it.get("url"), it.get("headline"), it.get("ts"))
        if key in seen:
            continue
        existing.append(it)
        seen.add(key)
        added += 1

    LOG.write_text(json.dumps(existing, indent=1, ensure_ascii=False), encoding="utf-8")
    skipped = len(items) - added
    print(f"appended {added}/{len(items)} item(s), log now {len(existing)} total"
          + (f" (skipped {skipped} duplicate(s))" if skipped else ""))

    # clean up the scratch input file so it never lingers / gets committed by accident
    if sys.argv[1] != "-" and sys.argv[1].endswith(".tmp"):
        Path(sys.argv[1]).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
