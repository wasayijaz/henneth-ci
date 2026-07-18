"""Deep dividend history (10-15+ years) per ticker, from Yahoo's dividend events.

WHY THIS EXISTS
  state/dividends.json comes from the PSX DPS payouts endpoint, which only returns a rolling
  ~18-month window. That is the right source for ANNOUNCED / UPCOMING payouts (it carries book
  closure and buy-by dates), but it is far too short to answer "what did reinvesting dividends
  actually do over 5 or 10 years". Running a long price window against a short dividend window
  silently undercounts payouts and understates reinvestment.

  Yahoo's chart API returns dividend events on the same `.KA` symbols the desk already uses for
  deep price history. Critically, both series live in the SAME adjustment space: fetch_deep_history
  stores `indicators.quote[0]` (split/bonus-adjusted, NOT dividend-adjusted) and these dividend
  amounts are likewise split-adjusted. So per-share payouts and prices are directly comparable and
  applying dividends on top of these closes does not double-count them.

OUTPUT  state/dividends_deep.json
  {updated, source, note, coverage_from, tickers: {SYM: [{"ex": "YYYY-MM-DD", "rs": float}, ...]}}

Idempotent and safe to re-run: symbols already fetched are refreshed only when stale, and any
network failure leaves the previous good file in place and exits 0 (never crashes a cycle).
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
OUT = STATE / "dividends_deep.json"
UNIVERSE = STATE / "universe.json"

RANGE = "20y"
REFRESH_DAYS = 14          # a ticker already on file is re-pulled only this often
MAX_FETCH = 130            # bound per run; the cycle must stay fast
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PSXTradeDesk/1.0)"}


def load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def fetch_symbol(sess, sym):
    """Return [{'ex': 'YYYY-MM-DD', 'rs': float}] or None on failure (None != empty list)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.KA"
    try:
        r = sess.get(url, params={"range": RANGE, "interval": "1d", "events": "div"},
                     headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None
        res = (r.json().get("chart") or {}).get("result") or []
        if not res:
            return None
        ev = (res[0].get("events") or {}).get("dividends") or {}
        out = []
        for k, v in ev.items():
            amt = v.get("amount")
            if amt is None or amt <= 0:
                continue
            d = datetime.fromtimestamp(int(k), tz=timezone.utc).strftime("%Y-%m-%d")
            out.append({"ex": d, "rs": round(float(amt), 4)})
        out.sort(key=lambda x: x["ex"])
        return out
    except Exception:
        return None


def main():
    uni = load(UNIVERSE, {})
    symbols = sorted((uni.get("symbols") or {}).keys())
    if not symbols:
        print("dividends_deep: no universe yet, nothing to do")
        return

    prev = load(OUT, {})
    tickers = dict(prev.get("tickers") or {})
    seen_at = dict(prev.get("_fetched_at") or {})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_ts = time.time()

    def stale(sym):
        ts = seen_at.get(sym)
        return True if not ts else (now_ts - ts) > REFRESH_DAYS * 86400

    todo = [s for s in symbols if stale(s)][:MAX_FETCH]
    if not todo:
        print(f"dividends_deep: all {len(symbols)} symbols fresh, nothing to fetch")
        return

    sess = requests.Session()
    ok = fail = 0
    for sym in todo:
        rows = fetch_symbol(sess, sym)
        if rows is None:
            fail += 1
            continue
        # An empty list is a legitimate answer (the company pays nothing) - record it so the
        # symbol is not re-fetched every run.
        tickers[sym] = rows
        seen_at[sym] = now_ts
        ok += 1
        time.sleep(0.25)

    if ok == 0:
        # total failure -> leave the previous good file untouched, degrade quietly, exit 0
        print(f"dividends_deep: DEGRADED - {fail} failures, 0 successes; keeping previous file")
        return

    all_dates = [r["ex"] for rows in tickers.values() for r in rows]
    payload = {
        "updated": today,
        "source": "Yahoo Finance chart API dividend events (.KA symbols)",
        "note": ("Split/bonus-adjusted per-share cash dividends, in the SAME adjustment space as "
                 "state/history_deep (which stores Yahoo indicators.quote[0], split-adjusted and "
                 "NOT dividend-adjusted). Dates are EX-dividend dates, not book-closure dates. "
                 "For announced/upcoming payouts with buy-by and book-closure dates, use "
                 "state/dividends.json (PSX DPS), which is authoritative but only ~18 months deep."),
        "coverage_from": min(all_dates) if all_dates else None,
        "n_tickers": len(tickers),
        "n_payouts": len(all_dates),
        "_fetched_at": seen_at,
        "tickers": tickers,
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    span = f"{payload['coverage_from']} -> {today}" if all_dates else "none"
    print(f"dividends_deep: {ok} fetched, {fail} failed | {len(tickers)} tickers, "
          f"{len(all_dates)} payouts, {span} -> {OUT.name}")


if __name__ == "__main__":
    main()
