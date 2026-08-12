#!/usr/bin/env python3
"""Print the last N entries of state/newslog.json as compact JSON.

Lets news-sentinel see recent context for dedup without loading the whole
(growing) log into its own context window. Idempotent, read-only.

Usage: python scripts/newslog_tail.py [N]   (default N=30)
"""
import json
import sys
from pathlib import Path

STATE = Path(__file__).resolve().parent.parent / "state"
LOG = STATE / "newslog.json"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    if not LOG.exists():
        print("[]")
        return
    with open(LOG, encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(data[-n:], ensure_ascii=False))


if __name__ == "__main__":
    main()
