"""Correlation layer: which researched names actually move together. Writes state/correlation.json.

Why this exists
---------------
CLAUDE.md Rule 4 bans two concurrent positions in the same SECTOR. That is a proxy for
"don't hold the same bet twice", and it is a leaky one in both directions:

  * two names in DIFFERENT sectors can be near-identical trades. An E&P and a refinery are
    filed under separate PSX sector codes but are both long the same oil-and-PKR complex; a
    bank and a leasing company both trade the policy rate. The sector rule waves those through.
  * conversely two names inside one sector can be genuinely different businesses.

This module measures the thing the sector label was standing in for. It does NOT change
Rule 4 and does not size anything — sector remains the hard constraint, and the sizing
formula stays the single path in CLAUDE.md. Correlation is a WARNING layer for the
portfolio and practice pages: "these two are 0.71 correlated, you are holding one position
in two accounts."

Method
------
Daily LOG returns from closes (log returns are additive over time and symmetric in sign, so
a -50% then +100% round trip does not leave a phantom drift the way simple returns do), then
pairwise Pearson correlation over the dates the two names BOTH traded.

Pairwise alignment matters on PSX: thin names miss sessions, and a naive "drop any date where
any symbol is missing" intersection across 250+ tickers would collapse the sample to whatever
the worst-covered name has. So each PAIR gets its own overlap, and a pair with fewer than
MIN_OVERLAP common bars is OMITTED rather than reported — a correlation off 40 shared days is
noise with three decimal places on it, and publishing it would be worse than publishing nothing.

Output is NOT an N^2 matrix. At 250+ researched names that file is ~60k entries and no page
would read more than a handful of them. Each symbol instead carries its TOP_N most-correlated
peers, which is exactly the concentration question ("what else do I own that is this?").
Note the asymmetry that follows: A can appear in B's top-8 without B appearing in A's, since
each list is truncated. The UI should treat a hit in EITHER list as a flag.

Pure math over local files. No network. Idempotent. Any failure prints and exits 0.
"""
import math
import sys
import time

import numpy as np
import pandas as pd

from psx_data import STATE, load_json, research_symbols, save_json

LOOKBACK = 750       # sessions (~3y). Older-than-3y co-movement is a different regime.
MIN_OVERLAP = 250    # common bars (~1y) before a pair is reportable at all
MIN_BARS = 300       # a symbol with less than this never enters the matrix
TOP_N = 8            # peers stored per symbol
HIGH_CORR = 0.60     # the level the UI should warn at (see note in main())


def log_returns(bars):
    """date -> log return, from closes only. Non-positive or missing closes break the log and
    are dropped: a zero print in the history is a data glitch, not a -100% day."""
    out = {}
    prev = None
    for b in bars:
        c, d = b.get("close"), b.get("date")
        if not isinstance(c, (int, float)) or c <= 0 or not d:
            prev = None          # gap: the next bar's return spans unknown ground, so skip it
            continue
        if prev is not None:
            out[d] = math.log(c / prev)
        prev = c
    return out


def build_frame(symbols):
    """One DataFrame, dates x symbols, NaN where a name did not trade that session."""
    series = {}
    for sym in symbols:
        bars = load_json(STATE / "history" / f"{sym}.json", None)
        if not bars or len(bars) < MIN_BARS:
            continue
        r = log_returns(bars)
        if len(r) < MIN_BARS:
            continue
        series[sym] = pd.Series(r, dtype="float64")
    if not series:
        return None
    df = pd.DataFrame(series).sort_index()
    return df.tail(LOOKBACK)


def main():
    symbols = research_symbols()
    df = build_frame(symbols)
    if df is None or df.shape[1] < 2:
        save_json(STATE / "correlation.json", {
            "updated": time.strftime("%Y-%m-%d %H:%M"),
            "status": "degraded",
            "error": "not enough usable price history to correlate anything",
            "tickers": {},
        })
        print("correlation: no usable history — wrote degraded status")
        sys.exit(0)

    cols = list(df.columns)
    # min_periods enforces the overlap floor inside pandas: pairs below it come back NaN and
    # are therefore never reported, which is the omit-rather-than-guess rule.
    corr = df.corr(min_periods=MIN_OVERLAP).to_numpy(copy=True)   # copy: fill_diagonal writes
    # overlap counts: boolean matrix product gives every pair's shared-bar count in one pass.
    mask = df.notna().to_numpy().astype(np.int32)
    overlap = mask.T @ mask
    np.fill_diagonal(corr, np.nan)      # a name is trivially 1.0 with itself

    out, pairs, flagged = {}, 0, 0
    for i, sym in enumerate(cols):
        row = corr[i]
        valid = np.flatnonzero(np.isfinite(row))
        if valid.size:
            order = valid[np.argsort(-row[valid])][:TOP_N]
        else:
            order = []
        peers = [{"symbol": cols[j],
                  "r": round(float(row[j]), 3),
                  "bars": int(overlap[i, j])} for j in order]
        pairs += len(peers)
        flagged += sum(1 for p in peers if p["r"] >= HIGH_CORR)
        out[sym] = {
            "bars": int(mask[:, i].sum()),
            "peers": peers,
            "max_r": peers[0]["r"] if peers else None,
            "high_corr_peers": [p["symbol"] for p in peers if p["r"] >= HIGH_CORR],
        }

    save_json(STATE / "correlation.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "status": "ok",
        "lookback_sessions": LOOKBACK,
        "min_overlap_bars": MIN_OVERLAP,
        "top_n": TOP_N,
        "high_corr_threshold": HIGH_CORR,
        "symbols_covered": len(out),
        "pairs_reported": pairs,
        "note": ("how closely two stocks have actually moved together, day by day, over the last "
                 "three years of closes. 1.0 means they rose and fell as one, 0 means no "
                 "relationship, below 0 means they tended to move opposite. each stock lists only "
                 "its eight closest companions — a pair is left out entirely unless the two names "
                 "traded on at least a year of the same days, because a number off a handful of "
                 "shared sessions is noise. this measures overlap of BEHAVIOUR, not of business: "
                 "two stocks in different sectors can still be one bet. research, not a rule — "
                 "the desk's hard limit stays one position per sector."),
        "method": {
            "returns": "daily log returns, ln(close_t / close_t-1), from state/history closes",
            "correlation": "Pearson, computed pairwise on the sessions BOTH names traded (not a common intersection across all symbols, which the thinnest name would dominate)",
            "omission": f"a pair with fewer than {MIN_OVERLAP} shared bars is omitted, never reported with a caveat",
            "shape": f"top {TOP_N} peers per symbol, not a full matrix — lists are truncated, so A may appear in B's list without B appearing in A's; treat a hit in either direction as a flag",
        },
        "caveats": [
            "Correlation is not causation and is unstable: it rises in sell-offs, which is exactly when diversification is being relied on. A calm-period number understates crisis co-movement.",
            "This is a whole-period average. It hides a pair that was uncorrelated for two years and has been moving as one for the last two months.",
            "Nothing here is beta or market-adjusted. Two names can both simply be following KSE100 rather than each other.",
        ],
        "tickers": out,
    })
    print(f"correlation: {len(out)} symbols · {pairs} pairs reported · "
          f"{flagged} at or above r={HIGH_CORR}")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:                     # degraded, never crash the cycle
        print(f"correlation: failed ({type(e).__name__}: {e}) — leaving previous output in place")
        sys.exit(0)
