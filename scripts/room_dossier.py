#!/usr/bin/env python3
"""Desk Room — dossier compiler (deterministic, zero tokens).

Compiles a COMPACT per-ticker dossier from the state layer so Room agents read
~1-2k tokens of pre-digested facts instead of raw JSON files. One compilation,
many agent readers. Nothing here calls an LLM or the network.

Output: state/dossiers.json = { SYM: {compact dossier}, ..., "_meta": {...} }
The orchestrator hands ONE ticker's dossier to the agents; they never load the
whole file. Keeping it one file (not 60) keeps the pipeline + preflight simple.

Design rules:
- Every field traces to a state file. Missing input -> the section is omitted,
  never guessed (desk hard-rule #2).
- Numbers are rounded/trimmed for token economy; full precision stays in source.
"""
import time

from psx_data import STATE, load_json, save_json


def _r(v, d=2):
    """Round if numeric, else pass through (None stays None)."""
    try:
        return round(float(v), d)
    except (TypeError, ValueError):
        return v


def build():
    quant = load_json(STATE / "quant.json", {}).get("tickers", {})
    pred = load_json(STATE / "predictability.json", {}).get("tickers", {})
    smap = load_json(STATE / "strategy_map.json", {}).get("tickers", {})
    fair = load_json(STATE / "fairvalue.json", {}).get("tickers", {})
    fsc = load_json(STATE / "fundamental_scores.json", {}).get("tickers", {})
    fund = load_json(STATE / "fundamentals.json", {}).get("tickers", {})
    divs = load_json(STATE / "dividends.json", {})
    uni = load_json(STATE / "universe.json", {}).get("symbols", {})
    live = load_json(STATE / "live.json", {}).get("tickers", {})
    news = load_json(STATE / "newslog.json", [])
    research = load_json(STATE / "research_index.json", {})  # doc digests, if present

    # index news + digests by ticker once
    news_by = {}
    for n in news:
        for t in (n.get("tickers") or []):
            news_by.setdefault(t, []).append(n)
    div_hist = {}
    for d in (divs.get("history") or []):
        div_hist.setdefault(d.get("symbol"), []).append(d)

    dossiers = {}
    for sym, q in quant.items():
        u = uni.get(sym, {})
        f = fund.get(sym, {})
        fv = fair.get(sym)
        sc = fsc.get(sym)
        proven = smap.get(sym, [])
        dh = sorted(div_hist.get(sym, []), key=lambda d: d.get("bc_start") or "", reverse=True)[:4]
        nn = sorted(news_by.get(sym, []), key=lambda n: n.get("ts") or "")[-6:]
        docs = (research.get("by_ticker", {}) or {}).get(sym, [])[:6]

        d = {
            "symbol": sym,
            "name": u.get("name", ""),
            "sector": u.get("sector") or f.get("sector") or "unknown",
            "indices": u.get("in", []),
            "price": _r(live.get(sym, {}).get("current") or q.get("close")),
            "asof": q.get("date"),
            # --- technical snapshot (Chartist reads this) ---
            "technical": {
                "ret_1d": _r(q.get("ret_1d")), "ret_5d": _r(q.get("ret_5d")), "ret_20d": _r(q.get("ret_20d")),
                "rsi14": _r(q.get("rsi14"), 1), "sma20": _r(q.get("sma20")), "sma50": _r(q.get("sma50")),
                "above_sma20": q.get("above_sma20"), "above_sma50": q.get("above_sma50"),
                "dist_to_20d_high_pct": _r(q.get("dist_to_20d_high_pct")),
                "vol_surge": _r(q.get("vol_surge")), "volatility_rank": _r(q.get("volatility_rank"), 1),
                "avg_daily_traded_value_m": _r((q.get("avg_daily_traded_value") or 0) / 1e6, 1),
                "predictability_score": _r((pred.get(sym) or {}).get("score"), 1),
                "proven_strategies": [
                    {"name": p.get("name"), "hit": _r(p.get("hit_rate"), 2),
                     "net_pct": _r(p.get("net_expectancy_pct")), "n": p.get("n")}
                    for p in proven[:6]
                ],
            },
            # --- fundamental snapshot (Fundamentalist reads this) ---
            "fundamental": {
                "market_cap": f.get("market_cap"), "pe": f.get("pe"), "forward_pe": f.get("forward_pe"),
                "eps": f.get("eps"), "div_yield": f.get("div_yield"), "payout_ratio": f.get("payout_ratio"),
                "beta": f.get("beta"), "revenue": f.get("revenue"), "net_income": f.get("net_income"),
                "next_earnings": f.get("next_earnings"),
                "scorecard": ({"rating": sc.get("rating"), "overall": sc.get("overall"),
                               "cards": sc.get("cards")} if sc else None),
                "recent_dividends": [
                    {"payout": d.get("announcement"), "rs": d.get("dividend_rs"),
                     "yield_pct": d.get("yield_pct_at_close"), "closure": d.get("bc_start")}
                    for d in dh
                ],
            },
            # --- valuation (both desks + Chair) ---
            "valuation": ({
                "price": _r(fv.get("price")), "composite_fair": _r(fv.get("composite_fair")),
                "mispricing_pct": _r(fv.get("mispricing_pct")), "verdict": fv.get("verdict"),
                "methods": {k: _r(v) for k, v in (fv.get("methods") or {}).items()},
                "eps": fv.get("eps"), "growth_est_pct": fv.get("growth_est_pct"),
            } if fv else None),
            # --- catalysts / news / documents (all personas) ---
            "recent_news": [
                {"ts": (n.get("ts") or "")[:16], "impact": n.get("impact"),
                 "headline": n.get("headline"), "url": n.get("url")}
                for n in nn
            ],
            "documents": docs,  # broker-note + filing digests tagged to this ticker (from Librarian)
        }
        dossiers[sym] = d

    dossiers["_meta"] = {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "n_tickers": len(dossiers),
        "note": "Compact per-ticker dossier for Desk Room agents. All fields sourced from state/. "
                "Agents read one ticker's dossier, never raw files or this whole object.",
    }
    save_json(STATE / "dossiers.json", dossiers)
    print(f"dossiers: {len(dossiers) - 1} tickers compiled -> state/dossiers.json")
    return dossiers


if __name__ == "__main__":
    build()
