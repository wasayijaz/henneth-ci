#!/usr/bin/env python3
"""Desk Room — coverage queue builder (deterministic, zero tokens).

Decides WHICH tickers get a Room deep-dive next, so agents spend tokens where it
matters and the whole universe still rotates. Pure ranking over existing state —
no LLM, no network.

Priority (higher score = sooner):
  1000  results / AGM / corporate-briefing due within 7 days
   500  per unit of max recent-news impact (>=4) since last Room visit
   300  a signal fired / auditor-passed setup exists
   200  a new broker note / filing landed for the ticker
  +staleness: days since last Room session (guarantees full rotation)

Output: state/room_queue.json = { ranked: [ {symbol, score, reasons[]}, ... ], meta }
The daily task takes the top `deep_dives_per_day` from budget.json.
"""
import time
from datetime import datetime, timezone

from psx_data import STATE, load_json, save_json


def _days_until(datestr):
    if not datestr:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            d = datetime.strptime(datestr.strip()[:len(datetime.now().strftime(fmt)) + 4], fmt)
            return (d.date() - datetime.now(timezone.utc).date()).days
        except (ValueError, TypeError):
            continue
    return None


def build():
    quant = load_json(STATE / "quant.json", {}).get("tickers", {})
    cal = load_json(STATE / "earnings_calendar.json", {}).get("events", [])
    news = load_json(STATE / "newslog.json", [])
    signals = load_json(STATE / "signals.json", {}).get("active", [])
    research = load_json(STATE / "research_index.json", {})
    rooms = load_json(STATE / "rooms.json", {})  # last Room session per ticker, if any

    last_visit = {s: (v.get("built") or "")[:10] for s, v in rooms.items() if s != "_meta"}
    today = datetime.now(timezone.utc).date()

    # events within 7 days
    upcoming = {}
    for e in cal:
        du = _days_until(e.get("date"))
        if du is not None and 0 <= du <= 7:
            t = e.get("ticker")
            if t:
                upcoming[t] = min(upcoming.get(t, 99), du)

    # max recent news impact since (roughly) last visit
    news_impact = {}
    for n in news:
        for t in (n.get("tickers") or []):
            imp = n.get("impact") or 0
            if imp >= 4 and (not last_visit.get(t) or (n.get("ts") or "")[:10] > last_visit[t]):
                news_impact[t] = max(news_impact.get(t, 0), imp)

    signal_tickers = {s.get("ticker") for s in signals}
    doc_tickers = set((research.get("by_ticker") or {}).keys())

    # SCOPE: only names the desk could actually act on.
    #
    # This used to rank every ticker in quant.json. Once the universe went to the whole KSE
    # All Share that meant 442 names queued for a full 5-persona debate — ~74 days of budget
    # at 6/day — and most of that spend would go to stocks below the liquidity floor, which
    # can never produce a setup no matter what the Chair concludes. Debating them is not
    # coverage, it is burning tokens to reach a house view nobody can trade.
    #
    # Restricting to signal-eligible names cuts the queue to ~100 and full coverage to ~2-3
    # weeks, with every debate landing on a name that can carry a position.
    # Falls back to the full list if liquidity.json is missing, so this never silently
    # narrows coverage on a broken cycle.
    liq = load_json(STATE / "liquidity.json", {}).get("tickers", {})
    eligible = {s for s, m in liq.items() if m.get("signal_eligible")}
    scope = [s for s in quant if s in eligible] if eligible else list(quant)

    ranked = []
    for sym in scope:
        score, reasons = 0, []
        if sym in upcoming:
            score += 1000
            reasons.append(f"event in {upcoming[sym]}d")
        if sym in news_impact:
            score += 500 * news_impact[sym]
            reasons.append(f"news impact {news_impact[sym]}")
        if sym in signal_tickers:
            score += 300
            reasons.append("active signal")
        if sym in doc_tickers:
            score += 200
            reasons.append("new document")
        lv = last_visit.get(sym)
        stale_days = (today - datetime.strptime(lv, "%Y-%m-%d").date()).days if lv else 999
        score += min(stale_days, 60)  # staleness bonus caps so events always outrank
        reasons.append("never covered" if stale_days == 999 else f"{stale_days}d since last Room")
        ranked.append({"symbol": sym, "score": score, "reasons": reasons})

    ranked.sort(key=lambda r: -r["score"])
    out = {
        "ranked": ranked,
        "_meta": {
            "built": time.strftime("%Y-%m-%d %H:%M"),
            "top": [r["symbol"] for r in ranked[:5]],
            "scope": "signal_eligible" if eligible else "all_quant_fallback",
            "scope_n": len(scope),
            "note": "Room coverage queue, scoped to signal-eligible names (liquidity.json) — the desk "
                    "does not spend a 5-persona debate on a stock it would refuse to trade. Daily task "
                    "deep-dives the top N (budget.deep_dives_per_day). Events and high-impact news "
                    "outrank staleness so nothing important waits.",
        },
    }
    save_json(STATE / "room_queue.json", out)
    print(f"queue: {len(ranked)} tickers ranked -> top5 {out['_meta']['top']}")
    return out


if __name__ == "__main__":
    build()
