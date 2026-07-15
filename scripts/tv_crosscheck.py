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

# TradingView PSX is ~15 min delayed AND split/bonus-adjusted differently from DPS (unadjusted).
# CLAUDE.md: a TV-vs-DPS mismatch is NOT an error and must never degrade health on its own.
# So this gate has TWO bands per field:
#   dev <= DRIFT_TOL      -> match (fine)
#   DRIFT_TOL < dev <= ERR_TOL -> "drift" (advisory: lag / adjustment diff; recorded, does NOT fail)
#   dev > ERR_TOL         -> "error" (genuine: decimal/split/wrong-symbol glitch -> real FAIL, degrades health)
# ERR_TOL for close must clear a full ±7.5% PSX circuit move STACKED with a real corporate-action
# adjustment gap (e.g. a 1-for-5 bonus issue alone is a ~16.7% adjustment) — 20% covers that with
# headroom, while a decimal error (10x) or missed split (2x+) still trips it by a wide margin.
DRIFT_TOL = {"close": 0.03, "rsi14": 0.10, "sma20": 0.03, "sma50": 0.03}
ERR_TOL = {"close": 0.20, "rsi14": 0.35, "sma20": 0.12, "sma50": 0.12}


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

    results, fails, drift = {}, [], []
    for sym in syms:
        tv = fetch_tv(sym)
        if not tv or "error" in tv:
            results[sym] = {"status": "NO_TV_DATA", **(tv or {})}
            time.sleep(1.0)
            continue
        q = quant[sym]
        checks = {}
        sym_status = "PASS"  # escalates to DRIFT then ERROR
        for field in ("close", "rsi14", "sma20", "sma50"):
            ours, theirs = q.get(field), tv.get(field)
            if ours is None or theirs is None or theirs == 0:
                checks[field] = {"ours": ours, "tv": theirs, "match": None}
                continue
            dev = abs(ours / theirs - 1)
            fstat = "match" if dev <= DRIFT_TOL[field] else "drift" if dev <= ERR_TOL[field] else "error"
            checks[field] = {"ours": ours, "tv": round(theirs, 2), "dev_pct": round(dev * 100, 3),
                             "match": fstat == "match", "flag": fstat}
            # only the CLOSE price gates health; indicators are advisory (they lag a bar behind TV).
            # But an "error"-level indicator deviation must still surface as at least DRIFT — never
            # silently invisible — since it can signal a genuine bug in the desk's own indicator math,
            # even though it shouldn't freeze new signals the way a close-price error does.
            if fstat == "error" and field == "close":
                sym_status = "ERROR"
            elif fstat in ("error", "drift") and sym_status == "PASS":
                sym_status = "DRIFT"
        results[sym] = {"status": sym_status, "checks": checks,
                        "tv_high": tv["high"], "tv_low": tv["low"]}
        if sym_status == "ERROR":
            fails.append(sym)          # genuine data error -> degrades health (Rule 6)
        elif sym_status == "DRIFT":
            drift.append(sym)          # explainable lag/adjustment -> advisory only
        time.sleep(1.0)  # respect TV rate limits

    save_json(STATE / "crosscheck.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "checked": len(syms),
        "fails": fails,     # genuine glitches only — these gate health
        "drift": drift,     # TV lag / adjustment differences — recorded, never gate health
        "results": results,
    })
    print(f"crosscheck: {len(syms)} checked, {len(fails)} ERROR, {len(drift)} drift"
          + (f" -> ERROR: {', '.join(fails)}" if fails else "")
          + (f" -> drift: {', '.join(drift)}" if drift else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
