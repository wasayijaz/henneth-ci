#!/usr/bin/env python3
"""Desk Room — broker-call pre-filter (deterministic, zero tokens).

The free first stage of the weekly broker-call harvest. Scans the news log for items
that look like a research house making a PUBLIC call (a target/rating on a name), so the
cheap harvester agent only spends tokens on real candidates instead of reading everything.

We track brokers' calls as reported in the business press (not gated PDFs). A candidate =
a news item whose text mentions a broker alias from config/brokers.json AND a call keyword.

Output: state/broker_call_queue.json = { candidates: [ {broker, headline, url, date, ...} ], _meta }
The harvester agent turns each candidate into a structured, scoreable claim; it also runs its
own bounded web search to catch calls the news log missed.
"""
import re
import time

from psx_data import STATE, ROOT, load_json, save_json

CALL_KW = re.compile(r"\b(target price|price target|\bPT\b|\bTP\b|target of|rating|overweight|"
                     r"underweight|market perform|out ?perform|under ?perform|initiate[sd]?|"
                     r"upgrade[sd]?|downgrade[sd]?|raises?|cuts?|lowers?|reiterate[sd]?|"
                     r"buy|sell|hold|accumulate|neutral|fair value|sees\b)\b", re.I)


def build():
    brokers = load_json(ROOT / "config" / "brokers.json", {"brokers": []}).get("brokers", [])
    alias_to_id = {}
    for b in brokers:
        for a in b.get("aliases", []):
            alias_to_id[a.lower()] = b["id"]
    alias_pat = re.compile("|".join(re.escape(a) for a in sorted(alias_to_id, key=len, reverse=True)), re.I) \
        if alias_to_id else None

    news = load_json(STATE / "newslog.json", [])
    seen = set(load_json(STATE / "broker_call_queue.json", {}).get("_seen", []))
    candidates = []
    for n in news:
        text = f"{n.get('headline', '')} {n.get('summary', '')}"
        if not alias_pat:
            break
        m = alias_pat.search(text)
        if not m or not CALL_KW.search(text):
            continue
        key = (n.get("ts", "") + m.group(0))[:60]
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "broker": alias_to_id.get(m.group(0).lower(), m.group(0)),
            "matched_alias": m.group(0),
            "headline": n.get("headline"),
            "summary": n.get("summary"),
            "url": n.get("url"),
            "date": (n.get("ts") or "")[:10],
            "tickers": n.get("tickers") or [],
        })

    out = {
        "candidates": candidates,
        "_seen": list(seen)[-2000:],
        "_meta": {
            "built": time.strftime("%Y-%m-%d %H:%M"),
            "n_candidates": len(candidates),
            "brokers_tracked": [b["id"] for b in brokers],
            "note": "Deterministic broker-call candidates from the news log. The harvester agent "
                    "extracts structured claims from these + its own weekly web search.",
        },
    }
    save_json(STATE / "broker_call_queue.json", out)
    print(f"broker calls: {len(candidates)} new candidate(s) from the news log "
          f"across {len(brokers)} tracked houses")
    return out


if __name__ == "__main__":
    build()
