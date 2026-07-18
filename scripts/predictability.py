"""Predictability scores: how often did simple patterns on this ticker resolve
as expected over the cached history? Score 0-100 per ticker, shrunk toward 50
when sample is small. Writes state/predictability.json."""
import time

import numpy as np

from indicators import rolling_max, rsi, sma
from psx_data import STATE, load_json, save_json

HORIZON = 10       # sessions to resolve
TARGET = 0.03      # +3% counts as success
STOP = -0.03       # -3% first counts as failure
SHRINK_N = 15      # pseudo-observations at 50% for small samples


def _resolve(closes: np.ndarray, i: int) -> bool | None:
    """From bar i, does price gain TARGET before losing STOP within HORIZON?"""
    entry = closes[i]
    for j in range(i + 1, min(i + 1 + HORIZON, len(closes))):
        r = closes[j] / entry - 1
        if r >= TARGET:
            return True
        if r <= STOP:
            return False
    return None  # unresolved: excluded


def pattern_signals(closes: np.ndarray, vols: np.ndarray,
                    opens: np.ndarray | None = None) -> dict[str, np.ndarray]:
    sma20, sma50 = sma(closes, 20), sma(closes, 50)
    rsi14 = rsi(closes)
    hi20 = rolling_max(closes, 20)
    vol20 = np.full(len(vols), np.nan)
    for i in range(21, len(vols)):
        vol20[i] = vols[i - 20:i].mean()
    surge = np.divide(vols, vol20, out=np.full(len(vols), np.nan), where=vol20 > 0)

    prev_close = np.concatenate([[np.nan], closes[:-1]])
    prev_below_50 = np.concatenate([[True], (closes[:-1] < sma50[:-1])])
    up_day = closes > prev_close
    prev_rsi = np.concatenate([[np.nan], rsi14[:-1]])

    with np.errstate(invalid="ignore"):
        sigs = {
            "breakout": (closes > hi20) & (surge > 1.5),
            "pullback_trend": (closes > sma50) & (np.abs(closes / sma20 - 1) < 0.015)
                              & (rsi14 >= 40) & (rsi14 <= 55),
            "momentum_follow": (np.concatenate([[np.nan] * 5, closes[5:] / closes[:-5] - 1]) > 0.05)
                               & (closes > sma20),
            # first up-day after an oversold read
            "oversold_bounce": (prev_rsi < 30) & up_day,
            # close crosses back above the 50MA on real volume
            "ma50_reclaim": (closes > sma50) & prev_below_50 & (surge > 1.2),
            # stretched >5% below 20MA while long-term trend intact
            "meanrev_snapback": (closes < sma20 * 0.95) & (closes > sma50 * 0.97)
                                & (rsi14 < 40),
        }
        if opens is not None:
            # gapped up >=2% at the open and held it into the close
            gap = opens / prev_close - 1
            sigs["gap_up_hold"] = (gap >= 0.02) & (closes >= opens) & (surge > 1.2)
        return sigs


def score_ticker(hist: list[dict]) -> dict | None:
    if len(hist) < 150:
        return None
    closes = np.array([d["close"] for d in hist])
    vols = np.array([d["volume"] for d in hist], dtype=float)
    opens = np.array([d["open"] for d in hist])
    patterns = {}
    total_hits, total_n = 0.0, 0
    for name, sig in pattern_signals(closes, vols, opens).items():
        idx = [i for i in np.flatnonzero(sig == True) if i < len(closes) - 1]  # noqa: E712
        results = [r for i in idx if (r := _resolve(closes, i)) is not None]
        n = len(results)
        hits = sum(results)
        raw = hits / n if n else None
        patterns[name] = {"n": n, "hit_rate": round(raw, 3) if raw is not None else None}
        total_hits += hits
        total_n += n
    # shrunk composite: (hits + 0.5*SHRINK_N) / (n + SHRINK_N)
    shrunk = (total_hits + 0.5 * SHRINK_N) / (total_n + SHRINK_N)
    return {
        "score": round(shrunk * 100, 1),
        "total_signals": total_n,
        "patterns": patterns,
    }


def main():
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    out = {}
    # tier filter: predictability scores feed signals, which only exist for core names.
    for sym in [s for s, m in universe["symbols"].items() if (m or {}).get("tier", "core") == "core"]:
        hist = load_json(STATE / "history" / f"{sym}.json", None)
        row = score_ticker(hist) if hist else None
        if row:
            out[sym] = row
    save_json(STATE / "predictability.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "params": {"horizon": HORIZON, "target": TARGET, "stop": STOP},
        "tickers": out,
    })
    ranked = sorted(out.items(), key=lambda kv: -kv[1]["score"])[:5]
    print(f"predictability: {len(out)} tickers | top: "
          + ", ".join(f"{s} {v['score']}" for s, v in ranked))


if __name__ == "__main__":
    main()
