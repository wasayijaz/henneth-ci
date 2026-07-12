"""ONE-TIME deep history backfill. Pulls max available daily OHLC (~2008->today,
18y) for every universe symbol from Yahoo Finance (PSX names carry the '.KA'
Karachi suffix). Verified to match DPS exactly on recent bars (same close, same
volume) and — unlike the DPS EOD feed — it INCLUDES real daily high/low.

Stored separately in state/history_deep/{SYM}.json so it does NOT disturb the
authoritative DPS pipeline (quant/backtest/live/crosscheck stay on DPS). The
dashboard uses deep history for the long-range chart (5Y/10Y/Max) and the
max-history behavior stats.

Safe to re-run (idempotent). Slow (~60 symbols) — run manually once, then only
to refresh depth occasionally.
Usage: python scripts/fetch_deep_history.py [--refresh]
"""
import sys
import time

import requests

from psx_data import STATE, load_json, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"}


def fetch(symbol: str, sess: requests.Session) -> list[dict] | None:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.KA"
           f"?interval=1d&range=25y")
    r = sess.get(url, timeout=25)
    if r.status_code != 200:
        return None
    res = r.json().get("chart", {}).get("result")
    if not res:
        return None
    ts = res[0].get("timestamp") or []
    q = res[0]["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if c is None or o is None:
            continue
        out.append({
            "date": time.strftime("%Y-%m-%d", time.gmtime(t)),
            "open": round(o, 2), "high": round(h, 2) if h else round(c, 2),
            "low": round(l, 2) if l else round(c, 2), "close": round(c, 2),
            "volume": int(v) if v else 0,
        })
    return out


def main():
    refresh = "--refresh" in sys.argv
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    sess = requests.Session()
    sess.headers.update(UA)

    ok, failed, skipped = 0, [], 0
    for sym in universe["symbols"]:
        dest = STATE / "history_deep" / f"{sym}.json"
        if dest.exists() and not refresh:
            skipped += 1
            continue
        try:
            hist = fetch(sym, sess)
            if hist and len(hist) > 250:
                save_json(dest, hist)
                ok += 1
                print(f"  {sym}: {len(hist)} bars, {hist[0]['date']} -> {hist[-1]['date']}")
            else:
                failed.append((sym, f"{len(hist) if hist else 0} bars"))
        except requests.RequestException as e:
            failed.append((sym, str(e)[:50]))
        time.sleep(0.5)

    save_json(STATE / "history_deep_meta.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "Yahoo Finance (.KA)",
        "ok": ok, "skipped_existing": skipped,
        "failed": [{"symbol": s, "note": n} for s, n in failed],
    })
    print(f"deep history: {ok} fetched, {skipped} already present, {len(failed)} failed")


if __name__ == "__main__":
    main()
