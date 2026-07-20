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

from psx_data import ROOT, STATE, load_config, load_json, research_symbols, save_json
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
    library = json.loads((ROOT / "strategies" / "library.json").read_text(encoding="utf-8"))

    # preload histories once (deep preferred) and compute indicators ONCE per ticker
    inds = {}
    # Liquidity research gate (see psx_data.research_symbols): core + listed names liquid and
    # long-lived enough for a backtest to mean something. Running 70 strategies over a name
    # that trades a few hundred thousand rupees a day produces fills that do not exist.
    for sym in research_symbols():
        deep = load_json(STATE / "history_deep" / f"{sym}.json", None)
        dps = load_json(STATE / "history" / f"{sym}.json", None)
        h = deep if (deep and len(deep) > len(dps or [])) else dps
        if h and len(h) >= 220:
            inds[sym] = compute_indicators(h)

    # PER-SYMBOL FRICTION. A flat friction across the whole market is the single easiest way
    # to manufacture a fake edge on a thin stock: the strategies here are mostly breakout and
    # momentum, and Lesmond, Schill & Zhou (2004, "The Illusory Nature of Momentum Profits")
    # showed the stocks that produce the largest momentum returns are the same stocks that
    # cost the most to trade — so a constant cost assumption flatters exactly the names it
    # should penalise. Now that the universe reaches past the liquid core, that stops being a
    # rounding error and starts being the difference between a real signal and an artefact.
    #
    # friction = max(configured floor, estimated round-trip cost) — the Corwin-Schultz / FHT /
    # Roll estimators all return a proportional ROUND-TRIP spread, which is what one full
    # in-and-out trade pays. Never below the configured floor (that covers commission and
    # taxes, which the spread estimators do not).
    liq = load_json(STATE / "liquidity.json", {}).get("tickers", {})
    base_friction = cfg["friction_pct"]
    friction = {}
    for sym in inds:
        sp = (liq.get(sym) or {}).get("spread_pct")
        friction[sym] = round(max(base_friction, sp), 3) if sp is not None else base_friction

    results, strategy_map = {}, {}
    for spec in library:
        sid = spec["id"]
        per = {}
        for sym, ind in inds.items():
            st = run_strategy(spec, ind)
            if not st or st.get("n", 0) == 0:
                continue
            fr = friction[sym]
            net = (st.get("avg_return_pct") or 0) - fr
            st["net_expectancy_pct"] = round(net, 2)
            st["friction_pct"] = fr        # show the cost assumption, do not bury it
            oos = st.get("oos", {"n": 0})
            oos_ok = oos["n"] >= 3 and (oos.get("avg_return_pct") or 0) - fr > 0
            st["eligible"] = bool(
                st["n"] >= cfg["min_trades"] and (st.get("hit_rate") or 0) >= cfg["min_hit_rate"]
                and net >= cfg["min_net_expectancy_pct"] and oos_ok)
            # NOTE: name/category deliberately NOT stored per (strategy,ticker). They are
            # constant within a strategy, so writing them on all ~208 tickers repeated the
            # same two strings 14,000+ times and was most of this file's size. They live in
            # `meta` below; the dashboard re-attaches them on load.
            per[sym] = st
            if st["eligible"]:
                strategy_map.setdefault(sym, []).append({
                    "id": sid, "name": spec["name"], "category": spec["category"],
                    "net_expectancy_pct": st["net_expectancy_pct"], "hit_rate": st["hit_rate"],
                    "n": st["n"], "oos_n": oos["n"], "oos_hit": oos.get("hit_rate"),
                    "friction_pct": fr,
                    "target_pct": spec["target_pct"], "stop_pct": spec["stop_pct"],
                    "hold": spec["max_hold_sessions"]})
        results[sid] = per

    for sym in strategy_map:
        strategy_map[sym].sort(key=lambda x: -x["net_expectancy_pct"])

    save_json(STATE / "backtests.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"), "bars": cfg,
        "n_strategies": len(library),
        # one row per strategy instead of one per (strategy, ticker) pair
        "meta": {s["id"]: {"name": s["name"], "category": s["category"]} for s in library},
        "templates": results})
    # A ticker page needs only two numbers from the backtests on first paint (how many strategies
    # exist, and the friction floor) — the per-ticker results are behind a "Run to reveal" click.
    # backtests.json is ~4.8 MB, so loading it eagerly meant every ticker page pulled 4.8 MB for
    # content most visitors never open, and any one failed fetch blanked the whole page. This meta
    # file is the cheap half; the full file is fetched only when the reveal actually runs.
    save_json(STATE / "backtests_meta.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "n_strategies": len(library),
        "bars": cfg,
    })
    save_json(STATE / "strategy_map.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"), "tickers": strategy_map})
    # plain-English library index for the dashboard's strategy dictionary
    save_json(STATE / "strategy_library.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "strategies": [{
            "id": s["id"], "name": s["name"], "category": s["category"],
            "description": s.get("description", ""),
            "target_pct": s.get("target_pct"), "stop_pct": s.get("stop_pct"),
            "hold": s.get("max_hold_sessions")} for s in library]})

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
