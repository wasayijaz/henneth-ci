"""Quant layer: pure math per ticker from cached history. Writes state/quant.json.
No opinions, only numbers. LLM agents read this; they never compute it."""
import time

import numpy as np

from indicators import atr_proxy, pct_return, rolling_max, rsi, sma
from psx_data import STATE, load_json, save_json


def compute(symbol: str, hist: list[dict]) -> dict | None:
    if len(hist) < 60:
        return None
    closes = np.array([d["close"] for d in hist])
    vols = np.array([d["volume"] for d in hist], dtype=float)
    c = closes[-1]

    sma20, sma50 = sma(closes, 20), sma(closes, 50)
    r = np.diff(closes) / closes[:-1]
    vol20 = vols[-21:-1].mean() if len(vols) > 21 else np.nan
    hi20 = rolling_max(closes, 20)[-1]

    # volatility rank: current 60d stdev vs its own 3y distribution
    vol_rank = None
    if len(r) > 120:
        window = 60
        stdevs = np.array([r[i - window:i].std() for i in range(window, len(r))])
        vol_rank = round(float((stdevs <= stdevs[-1]).mean() * 100), 1)

    avg_traded_value = float((closes[-20:] * vols[-20:]).mean()) if len(closes) >= 20 else None

    return {
        "close": round(float(c), 2),
        "date": hist[-1]["date"],
        "ret_1d": round(float(pct_return(closes, 1)[-1] * 100), 2),
        "ret_5d": round(float(pct_return(closes, 5)[-1] * 100), 2),
        "ret_20d": round(float(pct_return(closes, 20)[-1] * 100), 2),
        "rsi14": round(float(rsi(closes)[-1]), 1),
        "atr14_proxy": round(float(atr_proxy(closes)[-1]), 2),
        "sma20": round(float(sma20[-1]), 2),
        "sma50": round(float(sma50[-1]), 2),
        "above_sma20": bool(c > sma20[-1]),
        "above_sma50": bool(c > sma50[-1]),
        "dist_to_20d_high_pct": round(float((hi20 / c - 1) * 100), 2),
        "vol_surge": round(float(vols[-1] / vol20), 2) if vol20 and vol20 > 0 else None,
        "volatility_rank": vol_rank,
        "avg_daily_traded_value": avg_traded_value,
    }


def main():
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    out, skipped = {}, []
    for sym in universe["symbols"]:
        hist = load_json(STATE / "history" / f"{sym}.json", None)
        row = compute(sym, hist) if hist else None
        if row:
            out[sym] = row
        else:
            skipped.append(sym)
    save_json(STATE / "quant.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "tickers": out,
        "skipped": skipped,
    })
    print(f"quant: {len(out)} tickers computed, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
