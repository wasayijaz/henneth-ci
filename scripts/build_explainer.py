#!/usr/bin/env python3
"""Explainability composer (deterministic, zero tokens).

The consumer edge: "is this company healthy? is the price reasonable? what changed
this week?" — answered in plain English from data the desk already holds reliably,
so a first-time PSX investor gets the picture without reading RSI. No LLM, no scrape.

Per ticker -> state/explainer.json:
  health      : from the fundamental scorecard (rating + one line)
  value       : from the 4-method fair-value model (below/near/above, softened)
  momentum    : from quant (trend vs SMAs, 20d move) — plain words
  income      : from the dividend record (yield + multi-year consistency)
  what_changed: newest high-impact news + the latest Desk Room house-view line
  dividend_by_year / return_by_year : trustworthy multi-year TRENDS from data we own
                (income-statement trends need a source the cloud can't scrape reliably —
                 left out rather than shipped brittle).
"""
import time
from collections import defaultdict

from psx_data import STATE, load_json, save_json


def _num(s):
    try:
        return float(str(s).replace(",", "").replace("%", "").replace("Rs", "").strip())
    except (TypeError, ValueError):
        return None


def build():
    quant = load_json(STATE / "quant.json", {}).get("tickers", {})
    fair = load_json(STATE / "fairvalue.json", {}).get("tickers", {})
    fsc = load_json(STATE / "fundamental_scores.json", {}).get("tickers", {})
    fund = load_json(STATE / "fundamentals.json", {}).get("tickers", {})
    divs = load_json(STATE / "dividends.json", {}).get("history", [])
    news = load_json(STATE / "newslog.json", [])
    rooms = load_json(STATE / "rooms.json", {})
    insider = load_json(STATE / "insider_activity.json", {}).get("symbols", {})
    offmkt = load_json(STATE / "offmarket_activity.json", {}).get("days", {})

    # dividends per fiscal year, per ticker (reliable multi-year trend)
    import re
    div_by_year = defaultdict(lambda: defaultdict(float))
    for d in divs:
        # bc_start is ISO (2026-05-12); announced is "April 29, 2026" — pull a 4-digit year from either
        m = re.search(r"\b(20[12][0-9])\b", str(d.get("bc_start") or "") + " " + str(d.get("announced") or ""))
        rs = d.get("dividend_rs")
        if m and isinstance(rs, (int, float)):
            div_by_year[d.get("symbol")][m.group(1)] += rs

    news_by = defaultdict(list)
    for n in news:
        for t in (n.get("tickers") or []):
            news_by[t].append(n)

    # insider/off-market: metadata only, no direction inferred (desk hard-rule) -- last 30d
    # filing count + trailing-window off-market aggregate, per symbol
    import datetime
    cutoff30 = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    offmkt_by_sym = defaultdict(lambda: {"shares": 0, "value": 0, "days": 0})
    for day_data in offmkt.values():
        for sym, agg in day_data.items():
            o = offmkt_by_sym[sym]
            o["shares"] += agg.get("shares", 0)
            o["value"] += agg.get("value", 0)
            o["days"] += 1

    out = {}
    for sym, q in quant.items():
        f = fund.get(sym, {})
        fv = fair.get(sym)
        sc = fsc.get(sym)
        room = rooms.get(sym)

        # HEALTH
        health = None
        if sc:
            lbl = {"attractive": "Looks financially solid", "caution": "Some financial flags",
                   "neutral": "A mixed financial picture", "mixed": "A mixed financial picture"}.get(
                       sc.get("rating"), "A mixed financial picture")
            health = {"verdict": lbl, "one_line": sc.get("overall", "")}

        # VALUE
        value = None
        if fv:
            v = {"undervalued": "Priced below the model's fair value",
                 "overvalued": "Priced above the model's fair value",
                 "fair": "Priced near the model's fair value"}.get(fv.get("verdict"), fv.get("verdict"))
            value = {"verdict": v, "one_line": f"Trades at Rs {q.get('close')}, blended model fair value "
                     f"Rs {round(fv.get('composite_fair', 0))} ({fv.get('mispricing_pct'):+}%). "
                     f"A model estimate, not a target — a low price never means a company is cheap."}

        # MOMENTUM (plain words, no jargon)
        up20 = q.get("ret_20d")
        trend = "in an uptrend" if q.get("above_sma50") and q.get("above_sma20") else \
                "in a downtrend" if not q.get("above_sma50") else "in a pullback within an uptrend"
        momentum = {"verdict": f"Price is {trend}",
                    "one_line": f"{'Up' if (up20 or 0) >= 0 else 'Down'} {abs(up20 or 0)}% over the last month; "
                    f"{'above' if q.get('above_sma50') else 'below'} its longer-term average."}

        # INCOME
        income = None
        dy = f.get("div_yield")
        years = sorted(div_by_year.get(sym, {}).items())
        if dy and _num(dy):
            consistency = f"paid dividends in {len(years)} of the last years on record" if years else "dividend history thin"
            income = {"verdict": f"{dy} dividend yield",
                      "one_line": f"Payout ratio {f.get('payout_ratio', 'n/a')}; {consistency}."}
        elif years:
            income = {"verdict": "Pays dividends", "one_line": f"On record in {len(years)} years."}
        else:
            income = {"verdict": "No dividend on record", "one_line": "This name has no payout in the desk's data."}

        # WHAT CHANGED THIS WEEK
        changed = []
        recent_filings = [r for r in insider.get(sym, []) if (r.get("date") or "") >= cutoff30]
        if recent_filings:
            changed.append(f"{len(recent_filings)} insider/substantial-shareholder filing"
                            f"{'s' if len(recent_filings) > 1 else ''} in the last 30 days "
                            "(metadata only, no direction inferred).")
        om = offmkt_by_sym.get(sym)
        if om:
            changed.append(f"Off-market: {om['shares']:,.0f} shares, Rs {om['value']:,.0f} "
                            f"across {om['days']} day{'s' if om['days'] != 1 else ''} on record.")
        for n in sorted(news_by.get(sym, []), key=lambda x: x.get("ts") or "")[-3:][::-1]:
            if (n.get("impact") or 0) >= 3:
                changed.append(f"{(n.get('ts') or '')[:10]}: {n.get('headline')}")
        if room and room.get("house_view"):
            changed.append("Desk Room read: " + (room["house_view"].get("summary", "")[:140]))
        if not changed:
            changed = ["Nothing material flagged this week."]

        out[sym] = {
            "name": f.get("name") or "",
            "health": health, "value": value, "momentum": momentum, "income": income,
            "what_changed": changed,
            "dividend_by_year": [{"year": y, "rs": round(v, 2)} for y, v in years][-6:],
            "return_by_year": _returns_by_year(sym),
        }

    out["_meta"] = {"built": time.strftime("%Y-%m-%d %H:%M"), "n": len(out),
                    "note": "Plain-English 'is it healthy / is the price reasonable / what changed' from "
                            "reliable desk data. Income-statement trends omitted (no cloud-scrapable source)."}
    save_json(STATE / "explainer.json", out)
    print(f"explainer: composed {len(out) - 1} tickers -> state/explainer.json")
    return out


def _returns_by_year(sym):
    hist = load_json(STATE / "history_deep" / f"{sym}.json", None)
    if not isinstance(hist, list) or len(hist) < 30:
        hist = load_json(STATE / "history" / f"{sym}.json", [])
    if not isinstance(hist, list) or len(hist) < 30:
        return []
    by_year = {}
    for b in hist:
        y = (b.get("date") or "")[:4]
        if y.isdigit() and b.get("close"):
            by_year.setdefault(y, []).append(b["close"])
    rows = []
    for y in sorted(by_year)[-6:]:
        c = by_year[y]
        rows.append({"year": y, "ret_pct": round((c[-1] / c[0] - 1) * 100, 1)})
    return rows


if __name__ == "__main__":
    build()
