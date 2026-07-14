#!/usr/bin/env python3
"""Live-site watchdog for the PSX Trade Desk.

preflight.py guards data BEFORE publish. This guards the site AFTER publish —
it fetches the actual deployed URLs a real user's browser would fetch and asserts
they are reachable, non-empty, fresh, and structurally sound. It closes the loop
between "we pushed" and "users actually see good data".

Catches the whole "missing information / empty page" class from the outside:
  - a deploy that didn't propagate (stale `updated`)
  - a state file that 404s or serves empty on the CDN
  - the desk silently frozen in degraded health
  - a sampled ticker page whose history the site can't serve ("No data for XXX")

No tokens, no keys. Read-only HTTP. Exit non-zero if the live site is unhealthy,
so a cycle can react (re-publish / alert) instead of leaving users on stale data.

Usage:
  python scripts/watchdog.py                       # check live site, human report
  python scripts/watchdog.py --base http://localhost:8877/dashboard   # check a preview
  python scripts/watchdog.py --max-age-days 4      # how stale `updated` may be
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import date, datetime

BASE_DEFAULT = "https://psx-trade-desk.vercel.app"
TIMEOUT = 20

problems, notes = [], []


def fetch(base, path):
    """Return (json_or_none, error_or_none). Cache-busted so we test the CDN edge, not our cache."""
    url = f"{base.rstrip('/')}/state/{path}?t={int(time.time())}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "psx-watchdog"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None, f"HTTP {r.status}"
            raw = r.read()
            if not raw or len(raw) < 5:
                return None, "empty body"
            return json.loads(raw), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:120]


def days_old(stamp):
    """Days since a 'YYYY-MM-DD ...' stamp; None if unparseable."""
    try:
        return (date.today() - datetime.strptime(str(stamp)[:10], "%Y-%m-%d").date()).days
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--max-age-days", type=int, default=5,
                    help="how stale the freshest data may be before it's a problem")
    ap.add_argument("--sample", type=int, default=5, help="how many ticker history files to spot-check")
    args = ap.parse_args()
    base = args.base

    # 1) the aggregate files a user's first paint depends on
    dash, err = fetch(base, "dashboard.json")
    if dash is None:
        problems.append(f"dashboard.json unreachable/empty on live site ({err})")
    else:
        age = days_old(dash.get("updated"))
        if age is None:
            notes.append("dashboard.json has no parseable 'updated'")
        elif age > args.max_age_days:
            problems.append(f"dashboard.json is STALE on live: updated {dash.get('updated')} ({age}d ago) "
                            f"— a deploy likely didn't propagate")

    quant, err = fetch(base, "quant.json")
    if quant is None:
        problems.append(f"quant.json unreachable/empty on live site ({err})")
    elif len(quant.get("tickers", {})) < 20:
        problems.append(f"quant.json on live has only {len(quant.get('tickers', {}))} tickers (expected >= 20)")

    # 2) desk not silently frozen
    health, err = fetch(base, "health.json")
    if health is None:
        problems.append(f"health.json unreachable on live ({err})")
    elif health.get("status") not in ("ok", "healthy"):
        problems.append(f"live desk is DEGRADED: {', '.join(health.get('problems', [])) or 'unknown'} "
                        f"— new signals are gated (Rule 6)")

    # 3) the daily read (the Today page's lead)
    dr, err = fetch(base, "daily_read.json")
    if dr is None:
        notes.append(f"daily_read.json not on live yet ({err}) — Today page shows the 'run a cycle' empty state")

    # 4) sample ticker pages: can the site actually serve their history? (the "No data for XXX" class)
    uni, _ = fetch(base, "universe.json")
    if uni and isinstance(uni.get("symbols"), dict) and quant:
        # sample the most-liquid names the UI is most likely to open first
        syms = list(quant.get("tickers", {}))[: args.sample]
        empty_hist = []
        for s in syms:
            h, herr = fetch(base, f"history/{s}.json")
            if not h or (isinstance(h, list) and len(h) < 2):
                empty_hist.append(f"{s}({herr or 'too short'})")
        if empty_hist:
            problems.append(f"live history missing/empty for: {', '.join(empty_hist)} "
                            f"— these ticker pages show 'No data'")

    ok = not problems
    print("PSX Trade Desk - live watchdog  [" + base + "]")
    if notes:
        print(f"\n  NOTE ({len(notes)}):")
        for n in notes:
            print(f"    - {n}")
    if problems:
        print(f"\n  PROBLEM ({len(problems)}):")
        for p in problems:
            print(f"    x {p}")
        print("\n  RESULT: LIVE SITE UNHEALTHY — re-run the pipeline and re-publish.")
        sys.exit(1)
    print("\n  RESULT: OK — live site is serving fresh, non-empty data.")
    sys.exit(0)


if __name__ == "__main__":
    main()
