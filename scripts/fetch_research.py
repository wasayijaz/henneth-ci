#!/usr/bin/env python3
"""Desk Room — research index builder (deterministic, zero tokens, degrades gracefully).

Assembles state/research_index.json = the library of documents the Room draws on:
  1. FILINGS from the news log — news-sentinel already scans PSX announcements and the
     Pakistani business press and tags results / board-meeting / corporate-briefing items
     to tickers. We surface those here as filing entries (headline-level; if only a
     headline+URL exists, that is an honest 'headline' digest, not a fabricated summary).
  2. BROKER NOTES from config/broker_sources.json — only sources the owner has added
     (public, free). For each, we fetch the page/PDF text and stage it for the Librarian
     to digest into research_index (the Librarian runs in the room-loop task, not here).

Nothing here calls an LLM. Network failures degrade to 'no new documents', never crash.
The by_ticker index lets dossiers surface a name's documents cheaply.
"""
import re
import sys
import time
from datetime import datetime

from psx_data import STATE, ROOT, load_json, save_json

FILING_HINTS = re.compile(r"\b(result|results|profit|eps|dividend|payout|board meeting|"
                          r"corporate briefing|briefing session|agm|annual general|accounts|"
                          r"quarter|q[1-4]|half.?year|financial statement)\b", re.I)
BROKER_STALE_DAYS = 7
BROKER_FAILED_RETRY_DAYS = 1
BY_TICKER_LIMIT = 100  # official PSX archive + broker/news rows; CI needs more than a headline tail


def _fresh_enough(updated: str | None, days: int) -> bool:
    if "--force" in sys.argv or not updated:
        return False
    try:
        age = datetime.now() - datetime.strptime(updated, "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    if age.total_seconds() < 0:
        return False
    return age.days < days


def _broker_sources_fresh(meta: dict) -> bool:
    days = BROKER_FAILED_RETRY_DAYS if meta.get("broker_sources_failed") else BROKER_STALE_DAYS
    return _fresh_enough(meta.get("broker_sources_fetched"), days)


def _classify(headline):
    h = headline.lower()
    if "corporate briefing" in h or "briefing session" in h:
        return "corporate_briefing"
    if "agm" in h or "annual general" in h:
        return "agm"
    if "result" in h or "profit" in h or "eps" in h or "accounts" in h or "financial statement" in h:
        return "results"
    if "board meeting" in h:
        return "board_meeting"
    return "filing"


def build():
    idx = load_json(STATE / "research_index.json",
                    {"documents": {}, "by_ticker": {}, "_meta": {}})
    docs = idx.get("documents", {})
    by_ticker = idx.get("by_ticker", {})

    news = load_json(STATE / "newslog.json", [])
    added = 0
    for n in news:
        headline = n.get("headline") or ""
        tickers = n.get("tickers") or []
        if not headline or not tickers or not FILING_HINTS.search(headline):
            continue
        # stable id from ts+headline so re-runs don't duplicate
        key = "news:" + str(n.get("ts", "")) + ":" + headline[:40]
        if key in docs:
            continue
        docs[key] = {
            "hash": key,
            "source": "PSX / business press",
            "source_type": "filing",
            "doc_type": _classify(headline),
            "date": (n.get("ts") or "")[:10],
            "tickers": tickers,
            "digest": headline,                 # headline-level; not a fabricated summary
            "digest_level": "headline",         # 'headline' | 'full' (Librarian upgrades to full)
            "claims": [],
            "url": n.get("url"),
            "omissions": None,
        }
        for t in tickers:
            entry = {"hash": key, "source": "filing", "doc_type": docs[key]["doc_type"],
                     "date": docs[key]["date"], "one_line": headline[:90], "url": n.get("url")}
            lst = by_ticker.setdefault(t, [])
            if not any(e.get("hash") == key for e in lst):
                lst.insert(0, entry)
                del lst[BY_TICKER_LIMIT:]
        added += 1

    # broker sources (only what the owner configured; safe if empty/unreachable)
    cfg = load_json(ROOT / "config" / "broker_sources.json", {"sources": []})
    broker_staged = 0
    old_meta = idx.get("_meta", {})
    broker_fetched_at = old_meta.get("broker_sources_fetched")
    broker_failed = []
    if _broker_sources_fresh(old_meta):
        print(f"  broker sources skipped; last fetched {broker_fetched_at} (--force to refresh)")
        broker_failed = old_meta.get("broker_sources_failed") or []
    else:
        for src in (cfg.get("sources") or []):
            if not src.get("enabled", True) or not src.get("url"):
                continue
            try:
                import requests
                r = requests.get(src["url"], timeout=20,
                                 headers={"User-Agent": "Mozilla/5.0 PSXDesk research fetch"})
                if r.ok and r.text:
                    # stage raw text for the Librarian to digest (kept out of the served index)
                    staging = STATE / "research_staging"
                    staging.mkdir(exist_ok=True)
                    (staging / (src["broker"] + "_" + time.strftime("%Y%m%d") + ".txt")).write_text(
                        r.text[:200000], encoding="utf-8", errors="ignore")
                    broker_staged += 1
                else:
                    broker_failed.append(src.get("broker") or src.get("url") or "unknown")
            except Exception as e:  # noqa: BLE001 — network failure must never crash the cycle
                broker_failed.append(src.get("broker") or src.get("url") or "unknown")
                print(f"  broker source {src.get('broker')} unreachable: {str(e)[:60]}")
        broker_fetched_at = time.strftime("%Y-%m-%d %H:%M")

    idx["documents"] = docs
    idx["by_ticker"] = by_ticker
    idx["_meta"] = {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "n_documents": len(docs),
        "broker_staged_for_digest": broker_staged,
        "broker_sources_fetched": broker_fetched_at,
        "broker_sources_failed": broker_failed,
        "note": "Filing docs are headline-level from the news log; broker notes (if any sources "
                "configured) are staged for the Librarian to digest. Nothing fabricated.",
    }
    save_json(STATE / "research_index.json", idx)
    print(f"research: {added} new filings, {len(docs)} docs total, {broker_staged} broker notes staged")
    return idx


if __name__ == "__main__":
    build()
