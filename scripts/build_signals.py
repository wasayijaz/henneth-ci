"""Deterministic active-signal generator — populates state/signals.json from
PROVEN strategies that are TRIGGERING on the latest bar. No LLM, no tokens, so it
runs free in the cloud pipeline every cycle.

For each universe ticker, for each strategy proven on it (strategy_map.json), it
evaluates the strategy's rules on the ticker's own history; if the rule fires on
the most recent bar, it's a candidate setup. Entry = last close, stop/target from
the strategy's own %s, size from config risk params. Candidates are ranked by
(net expectancy x hit rate) and filtered by portfolio risk limits.

HONESTY: these are BACKTEST-PROVEN candidate setups, not auditor-verified signals.
The LLM auditor (local agent pipeline) can later upgrade a candidate to "audited".
Labelled `basis: "backtest-proven, unaudited"` so the desk never overstates them."""
import json
import time

import numpy as np

from psx_data import ROOT, STATE, load_config, load_json, save_json
from strategy_engine import compute_indicators, signals

LIBRARY = {s["id"]: s for s in json.loads((ROOT / "strategies" / "library.json").read_text(encoding="utf-8"))}


def latest_series(sym):
    deep = load_json(STATE / "history_deep" / f"{sym}.json", None)
    dps = load_json(STATE / "history" / f"{sym}.json", None)
    return deep if (deep and len(deep) > len(dps or [])) else dps


def main():
    cfg = load_config()
    risk = cfg["risk"]
    capital = cfg["capital_pkr"]
    smap = load_json(STATE / "strategy_map.json", {"tickers": {}})["tickers"]
    quant = load_json(STATE / "quant.json", {"tickers": {}})["tickers"]
    live = load_json(STATE / "live.json", {"tickers": {}})["tickers"]
    universe = load_json(STATE / "universe.json", {"symbols": {}})["symbols"]
    # Real PSX sectors (fetch_sectors.py). CLAUDE.md Rule 4 caps the desk at one position per
    # sector — that limit was previously keyed on the COMPANY NAME, which is unique per ticker, so
    # it could never bind and four banks could pass as four different "sectors".
    sectors = load_json(STATE / "sectors.json", {"tickers": {}})["tickers"]
    positions = load_json(STATE / "positions.json", {"open": []})
    held = {p["ticker"] for p in positions.get("open", [])}

    candidates = []
    for sym, proven in smap.items():
        if sym in held:
            continue
        series = latest_series(sym)
        if not series or len(series) < 220:
            continue
        ind = compute_indicators(series)
        q = quant.get(sym, {})
        px = (live.get(sym) or {}).get("current") or series[-1]["close"]
        atr = q.get("atr14_proxy")
        adv = q.get("avg_daily_traded_value")

        for p in proven:
            spec = LIBRARY.get(p["id"])
            if not spec:
                continue
            sig = signals(spec, ind)
            if not bool(sig[-1]):
                continue  # not triggering on the most recent bar
            stop = round(px * (1 - spec["stop_pct"] / 100), 2)
            target = round(px * (1 + spec["target_pct"] / 100), 2)
            risk_per_share = px - stop
            if risk_per_share <= 0:
                continue
            # Position sizing — CLAUDE.md Rule 4, the ONE formula (Strategist & Auditor identical):
            # size by stop distance (risk_per_trade_pct of capital), then hard-cap position VALUE
            # at max_pct_per_trade (8%) of capital.
            #
            # STILL COMPUTED, NO LONGER PUBLISHED (docs/PUBLICATION_RESTRUCTURE.md §3). A share
            # count against a capital figure the desk holds is the single most advisory-looking
            # output in the product — the difference between "here is the setup" and "here is what
            # you should buy". The reader sizes it themselves at /tools/position-size-calculator/,
            # against their own capital, in their own browser.
            #
            # The computation stays because `shares <= 0` is the Rule 4 VALIDITY GUARD: it rejects
            # a setup whose stop is too wide for the risk budget at this price. Delete the maths
            # along with the output fields and invalid setups start publishing.
            risk_budget = capital * risk.get("risk_per_trade_pct", 1.0) / 100
            shares_by_risk = risk_budget / risk_per_share
            shares_by_cap = (capital * risk["max_pct_per_trade"] / 100) / px
            shares = int(min(shares_by_risk, shares_by_cap))
            if shares <= 0:
                continue  # stop too wide for the risk budget at this price — invalid setup
            score = p["net_expectancy_pct"] * (p["hit_rate"] or 0)
            candidates.append({
                "id": f"{time.strftime('%Y%m%d')}-{sym}-{p['id']}",
                "ticker": sym, "strategy": p["id"], "template": p["name"],
                "category": p["category"], "sector": sectors.get(sym, {}).get("sector", ""),
                "entry": round(px, 2), "stop": stop, "target": target,
                "rr": round((target - px) / risk_per_share, 2) if risk_per_share else None,
                "hold_sessions": p["hold"],
                # risk_per_share is a LEVEL (entry minus stop), not a size — it is what the
                # reader's own calculator needs, and it carries no capital figure of ours.
                "risk_per_share": round(risk_per_share, 2),
                "backtest": {"hit_rate": p["hit_rate"], "net_expectancy_pct": p["net_expectancy_pct"],
                             "n": p["n"], "oos_hit": p.get("oos_hit")},
                "confidence": "high" if score > 1.5 else "medium" if score > 0.7 else "low",
                "basis": "backtest-proven, unaudited",
                "thesis": f"{p['name']} is triggering now; on {sym}'s own history it won "
                          f"{round((p['hit_rate'] or 0)*100)}% over {p['n']} trades ({p['net_expectancy_pct']:+.1f}% net/trade), "
                          f"still profitable out-of-sample.",
                "_score": score,
            })

    # rank, then apply portfolio limits: max positions, one per sector, best per ticker
    candidates.sort(key=lambda c: -c["_score"])
    active, used_sectors, used_tickers = [], set(), set()
    for c in candidates:
        if len(active) >= risk["max_positions"]:
            break
        if c["ticker"] in used_tickers:
            continue
        # An unmapped ticker collapses into one shared "unknown" bucket rather than becoming its
        # own sector: this is a RISK limit, so the unknown case must fail safe (block), not open.
        sec = c["sector"] or "unknown"
        if sec in used_sectors:
            continue
        c.pop("_score", None)
        active.append(c)
        used_tickers.add(c["ticker"])
        used_sectors.add(sec)

    save_json(STATE / "signals.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "note": "deterministic candidate setups from proven strategies triggering on the latest bar; "
                "backtest-proven but NOT auditor-verified. Research, not advice.",
        "active": active,
        "n_candidates": len(candidates),
    })
    print(f"signals: {len(active)} active from {len(candidates)} triggering candidates")
    for s in active:
        print(f"  {s['ticker']:6} {s['template']:24} entry {s['entry']} stop {s['stop']} tgt {s['target']} ({s['confidence']})")


if __name__ == "__main__":
    main()
