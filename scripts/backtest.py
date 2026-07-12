"""Backtest every strategy in strategies/library.json across every universe ticker.

Uses the config-driven engine (strategy_engine.py) so all 50+ strategies share one
audited indicator library. Runs on DEEP history (Yahoo .KA, ~19y, real OHLC) when
present — more samples + true high/low for the indicators — falling back to DPS.

Entry = next session's open after a signal bar. Exit = first of {target, stop, time}.
Eligibility bars: n>=min_trades, hit_rate>=min_hit, net expectancy>=min after friction,
AND positive out-of-sample (last third of history). Writes state/backtests.json and
state/strategy_map.json (per ticker -> proven strategies ranked by net expectancy)."""
import json
import time

import numpy as np

from psx_data import ROOT, STATE, load_config, load_json, save_json
from strategy_engine import compute_indicators, signals


def _trade_returns(sig, opens, closes, tgt, stp, hold):
    trades = []
    i = 0
    for s in np.flatnonzero(sig):
        if s + 1 >= len(closes) or s < i:
            continue
        entry = opens[s + 1]
        if entry <= 0:
            continue
        exit_r, j = None, s + 1
        for j in range(s + 1, min(s + 1 + hold, len(closes))):
            r = closes[j] / entry - 1
            if r >= tgt:
                exit_r = tgt
                break
            if r <= -stp:
                exit_r = -stp
                break
        if exit_r is None:
            exit_r = closes[j] / entry - 1
        trades.append((s, exit_r))
        i = j + 1
    return trades


def _stats(returns):
    if not returns:
        return {"n": 0}
    a = np.array(returns)
    wins, losses = a[a > 0], a[a <= 0]
    lmean = abs(losses.mean()) if len(losses) else 0
    return {
        "n": int(len(a)),
        "hit_rate": round(float((a > 0).mean()), 3),
        "avg_return_pct": round(float(a.mean() * 100), 2),
        "payoff_ratio": round(float(wins.mean() / lmean), 2) if len(wins) and lmean > 0 else None,
        "worst_pct": round(float(a.min() * 100), 2),
    }


def run_strategy(spec, ind):
    sig = signals(spec, ind)
    opens, closes = ind["open"], ind["close"]
    tgt, stp, hold = spec["target_pct"] / 100, spec["stop_pct"] / 100, spec["max_hold_sessions"]
    trades = _trade_returns(sig, opens, closes, tgt, stp, hold)
    if not trades:
        return {"n": 0}
    split = int(len(closes) * 2 / 3)
    full = _stats([r for _, r in trades])
    full["oos"] = _stats([r for s, r in trades if s >= split])
    return full


def main():
    cfg = load_config()["backtest"]
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    library = json.loads((ROOT / "strategies" / "library.json").read_text(encoding="utf-8"))

    # preload histories once (deep preferred) and compute indicators ONCE per ticker
    inds = {}
    for sym in universe["symbols"]:
        deep = load_json(STATE / "history_deep" / f"{sym}.json", None)
        dps = load_json(STATE / "history" / f"{sym}.json", None)
        h = deep if (deep and len(deep) > len(dps or [])) else dps
        if h and len(h) >= 220:
            inds[sym] = compute_indicators(h)

    results, strategy_map = {}, {}
    for spec in library:
        sid = spec["id"]
        per = {}
        for sym, ind in inds.items():
            st = run_strategy(spec, ind)
            if not st or st.get("n", 0) == 0:
                continue
            net = (st.get("avg_return_pct") or 0) - cfg["friction_pct"]
            st["net_expectancy_pct"] = round(net, 2)
            oos = st.get("oos", {"n": 0})
            oos_ok = oos["n"] >= 3 and (oos.get("avg_return_pct") or 0) - cfg["friction_pct"] > 0
            st["eligible"] = bool(
                st["n"] >= cfg["min_trades"] and (st.get("hit_rate") or 0) >= cfg["min_hit_rate"]
                and net >= cfg["min_net_expectancy_pct"] and oos_ok)
            st["name"] = spec["name"]
            st["category"] = spec["category"]
            per[sym] = st
            if st["eligible"]:
                strategy_map.setdefault(sym, []).append({
                    "id": sid, "name": spec["name"], "category": spec["category"],
                    "net_expectancy_pct": st["net_expectancy_pct"], "hit_rate": st["hit_rate"],
                    "n": st["n"], "oos_n": oos["n"], "oos_hit": oos.get("hit_rate"),
                    "target_pct": spec["target_pct"], "stop_pct": spec["stop_pct"],
                    "hold": spec["max_hold_sessions"]})
        results[sid] = per

    for sym in strategy_map:
        strategy_map[sym].sort(key=lambda x: -x["net_expectancy_pct"])

    save_json(STATE / "backtests.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"), "bars": cfg,
        "n_strategies": len(library), "templates": results})
    save_json(STATE / "strategy_map.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"), "tickers": strategy_map})

    elig_total = sum(len(v) for v in strategy_map.values())
    covered = len(strategy_map)
    print(f"backtest: {len(library)} strategies x {len(inds)} tickers")
    print(f"  {elig_total} eligible (strategy,ticker) pairs across {covered} tickers")
    top = sorted((p for lst in strategy_map.values() for p in lst),
                 key=lambda x: -x["net_expectancy_pct"])[:8]
    for t in top:
        print(f"  {t['id']:20} net {t['net_expectancy_pct']:+.2f}% hit {t['hit_rate']:.0%} n={t['n']}")


if __name__ == "__main__":
    main()
