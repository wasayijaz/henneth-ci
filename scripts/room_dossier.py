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
import hashlib
import json
import time
from datetime import date

from build_calendar import parse_loose
from psx_data import STATE, load_json, save_json


def _material_hash(d):
    """Hash only the fields that should trigger a fresh Room debate. Price ticking
    around does NOT change this — valuation verdict, scorecard, documents, high-impact
    news, and earnings proximity do. Cheap price-only moves are handled as Tier-1 deltas."""
    mat = {
        "verdict": (d.get("valuation") or {}).get("verdict"),
        "scorecard": (d.get("fundamental") or {}).get("scorecard", {}) and
                     (d["fundamental"]["scorecard"] or {}).get("rating"),
        "docs": [x.get("hash") if isinstance(x, dict) else x for x in (d.get("documents") or [])],
        "hi_news": [n.get("headline") for n in (d.get("recent_news") or []) if (n.get("impact") or 0) >= 4],
        "next_earnings": (d.get("fundamental") or {}).get("next_earnings"),
        "company_profile": {
            "business_description": (d.get("company_profile") or {}).get("business_description"),
            "incorporation": (d.get("company_profile") or {}).get("incorporation"),
        },
        "proven": [p.get("name") for p in (d.get("technical") or {}).get("proven_strategies", [])],
    }
    return hashlib.sha1(json.dumps(mat, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _r(v, d=2):
    """Round if numeric, else pass through (None stays None)."""
    try:
        return round(float(v), d)
    except (TypeError, ValueError):
        return v


def build():
    _today = date.today()
    _today_iso = _today.isoformat()
    quant = load_json(STATE / "quant.json", {}).get("tickers", {})
    pred = load_json(STATE / "predictability.json", {}).get("tickers", {})
    smap = load_json(STATE / "strategy_map.json", {}).get("tickers", {})
    fair = load_json(STATE / "fairvalue.json", {}).get("tickers", {})
    fsc = load_json(STATE / "fundamental_scores.json", {}).get("tickers", {})
    fund = load_json(STATE / "fundamentals.json", {}).get("tickers", {})
    divs = load_json(STATE / "dividends.json", {})
    uni = load_json(STATE / "universe.json", {}).get("symbols", {})
    live = load_json(STATE / "live.json", {}).get("tickers", {})
    # real PSX sectors (fetch_sectors.py). Before this existed the line below resolved to "unknown"
    # for EVERY ticker — universe.json and fundamentals.json carry no sector — so every persona
    # claim was filed under "unknown" or whatever free text the agent happened to type.
    sect_map = load_json(STATE / "sectors.json", {}).get("tickers", {})
    news = load_json(STATE / "newslog.json", [])
    research = load_json(STATE / "research_index.json", {})  # doc digests, if present
    profiles = load_json(STATE / "company_profiles.json", {}).get("tickers", {})

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
        prof = profiles.get(sym) or {}
        proven = smap.get(sym, [])
        # A row with no bc_start yet (freshly announced, book closure not scheduled/parsed) is the
        # NEWEST thing that happened, not the oldest — treat missing bc_start as "beyond today" (not
        # "") so it sorts to the top instead of the bottom, where a top-4 slice would drop it (root
        # cause of HBL's 2026-08-04 interim dividend missing from a 2026-08-10 asof dossier).
        dh = sorted(div_hist.get(sym, []), key=lambda d: d.get("bc_start") or "9999-99-99", reverse=True)[:4]
        _nn_all = sorted(news_by.get(sym, []), key=lambda n: n.get("ts") or "")
        nn = _nn_all[-6:]
        # Rule 10 (CLAUDE.md): impact>=4 news re-triggers the full pipeline, so it must never
        # silently vanish from the dossier just because newer low-impact items crowded it out of
        # the last-6 cutoff (the other half of the HBL window-gap: its H1'26 results item).
        _hi_dropped = [n for n in _nn_all[:-6] if (n.get("impact") or 0) >= 4]
        if _hi_dropped:
            nn = sorted(_hi_dropped + nn, key=lambda n: n.get("ts") or "")
        docs = (research.get("by_ticker", {}) or {}).get(sym, [])[:6]

        d = {
            "symbol": sym,
            "name": u.get("name", ""),
            "sector": (sect_map.get(sym) or {}).get("sector") or "unknown",
            "indices": u.get("in", []),
            "price": _r(live.get(sym, {}).get("current") or q.get("close")),
            "asof": q.get("date"),
            "company_profile": ({
                "business_description": prof.get("business_description"),
                "incorporation": prof.get("incorporation"),
                "source_url": prof.get("source_url"),
                "fetched": prof.get("fetched"),
                "stale": prof.get("stale"),
            } if prof else None),
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
                # pe: prefer score_fundamentals.py's live_pe (today's price / eps) over
                # fundamentals.json's own scrape-time ratio, which can lag a session's move
                # (single canonical source — same value the Screener/Compare pages show).
                "market_cap": f.get("market_cap"),
                "pe": ((sc or {}).get("metrics") or {}).get("pe", f.get("pe")),
                "forward_pe": f.get("forward_pe"),
                "eps": f.get("eps"), "eps_basis": f.get("eps_basis", "unknown"),
                "div_yield": f.get("div_yield"), "payout_ratio": f.get("payout_ratio"),
                "beta": f.get("beta"), "revenue": f.get("revenue"), "net_income": f.get("net_income"),
                # next_earnings is a raw scraped string (e.g. "Jun 18, 2026") with no freshness
                # check, so a date that has already passed (PSO showed Jun 18 2026 vs a Jul 16
                # 2026 asof) was surfaced as if still upcoming. Mirror build_calendar.py's own
                # forward-event gate (`parse_loose(...) >= today`): drop it to unknown/None
                # rather than pass a stale date through (never guess a replacement).
                "next_earnings": (f.get("next_earnings") if f.get("next_earnings") and
                                   (parse_loose(f.get("next_earnings"), _today) or "") >= _today_iso
                                   else None),
                "scorecard": ({"rating": sc.get("rating"), "overall": sc.get("overall"),
                               "cards": sc.get("cards")} if sc else None),
                "recent_dividends": [
                    {"payout": d.get("announcement"), "rs": d.get("dividend_rs"),
                     "yield_pct": d.get("yield_pct_at_close"), "closure": d.get("bc_start"),
                     # Normalized type from fetch_dividends.py's already-parsed `period` field
                     # (I/II/III/IV/F from the PSX payout text) instead of re-parsing the free-text
                     # `announcement` string — avoids the interim/final mislabeling that hit
                     # LOTCHEM and FCCL when personas guessed from the raw text.
                     "type": ("interim" if d.get("period") in ("I", "II", "III", "IV") else
                              "final" if d.get("period") == "F" else "unknown")}
                    for d in dh
                ],
            },
            # --- valuation (both desks read this) ---
            "valuation": ({
                "price": _r(fv.get("price")), "composite_fair": _r(fv.get("composite_fair")),
                "mispricing_pct": _r(fv.get("mispricing_pct")), "verdict": fv.get("verdict"),
                "methods": {k: _r(v) for k, v in (fv.get("methods") or {}).items()},
                "eps": fv.get("eps"), "eps_basis": fv.get("eps_basis", "unknown"),
                "growth_est_pct": fv.get("growth_est_pct"),
            } if fv else None),
            # --- catalysts / news / documents (all personas) ---
            "recent_news": [
                {"ts": (n.get("ts") or "")[:16], "impact": n.get("impact"),
                 "headline": n.get("headline"), "url": n.get("url")}
                for n in nn
            ],
            "documents": docs,  # broker-note + filing digests tagged to this ticker (from Librarian)
        }
        d["material_hash"] = _material_hash(d)  # the delta-gate key (Tier 0 vs Tier 2)
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
