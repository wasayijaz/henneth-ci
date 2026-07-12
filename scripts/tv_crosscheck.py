"""Independent verification of the desk's numbers against TradingView (tradingview-ta lib,
screener='pakistan', exchange='PSX'). This is the Week-1 gate and the Auditor's second source.

Usage:
  python scripts/tv_crosscheck.py            # spot-check 8 heavyweights
  python scripts/tv_crosscheck.py --all      # full universe sweep (throttled, ~1 min)

Compares close / RSI14 / SMA20 / SMA50 from state/quant.json vs TradingView.
Writes state/crosscheck.json. Non-zero exit if any FAIL (usable as a gate).
"""
import sys
import time

from psx_data import STATE, load_json, save_json

try:
    from tradingview_ta import Interval, TA_Handler
except ImportError:
    print("FATAL: pip install tradingview-ta", file=sys.stderr)
    sys.exit(2)

SPOT = ["HUBC", "OGDC", "LUCK", "FFC", "MEBL", "UBL", "ENGROH", "PSO"]
TOL = {"close": 0.01, "rsi14": 0.05, "sma20": 0.01, "sma50": 0.01}  # relative tolerance


def fetch_tv(symbol: str) -> dict | None:
    try:
        a = TA_Handler(symbol=symbol, screener="pakistan", exchange="PSX",
                       interval=Interval.INTERVAL_1_DAY).get_analysis()
        ind = a.indicators
        return {"close": ind["close"], "rsi14": ind["RSI"],
                "sma20": ind["SMA20"], "sma50": ind["SMA50"],
                "high": ind["high"], "low": ind["low"]}
    except Exception as e:  # noqa: BLE001 — symbol may not exist on TV under same code
        return {"error": str(e)[:100]}


def main():
    quant = load_json(STATE / "quant.json", {"tickers": {}})["tickers"]
    syms = list(quant) if "--all" in sys.argv else [s for s in SPOT if s in quant]

    results, fails = {}, []
    for sym in syms:
        tv = fetch_tv(sym)
        if not tv or "error" in tv:
            results[sym] = {"status": "NO_TV_DATA", **(tv or {})}
            time.sleep(1.0)
            continue
        q = quant[sym]
        checks = {}
        ok = True
        for field in ("close", "rsi14", "sma20", "sma50"):
            ours, theirs = q.get(field), tv.get(field)
            if ours is None or theirs is None or theirs == 0:
                checks[field] = {"ours": ours, "tv": theirs, "match": None}
                continue
            dev = abs(ours / theirs - 1)
            match = dev <= TOL[field]
            checks[field] = {"ours": ours, "tv": round(theirs, 2), "dev_pct": round(dev * 100, 3),
                             "match": match}
            ok = ok and match
        results[sym] = {"status": "PASS" if ok else "FAIL", "checks": checks,
                        "tv_high": tv["high"], "tv_low": tv["low"]}
        if not ok:
            fails.append(sym)
        time.sleep(1.0)  # respect TV rate limits

    save_json(STATE / "crosscheck.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "checked": len(syms),
        "fails": fails,
        "results": results,
    })
    print(f"crosscheck: {len(syms)} checked, {len(fails)} FAIL"
          + (f" -> {', '.join(fails)}" if fails else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
