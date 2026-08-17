#!/usr/bin/env python3
"""Build the private Company Intelligence app data slice.

Writes Henneth Desk 2.CI.0/data/company_intelligence.json from existing state files.
This is the only data file the CI app reads. It is a private research surface, but it still
keeps the same rule: every displayed fact traces to the state layer or is marked unknown.
"""
import time
from pathlib import Path

from psx_data import ROOT, STATE, load_json, save_json

APP_DIR = ROOT / "Henneth Desk 2.CI.0"
OUT = APP_DIR / "data" / "company_intelligence.json"


def _num(value):
    try:
        return float(str(value).replace(",", "").replace("%", "").replace("Rs", "").strip())
    except (TypeError, ValueError):
        return None


def _round(value, places=2):
    n = _num(value)
    return round(n, places) if n is not None else None


def _url(value):
    value = str(value or "").strip()
    return value if value.startswith(("http://", "https://")) else None


def _latest_news(news, sym, limit=3):
    rows = [n for n in news if sym in (n.get("tickers") or [])]
    rows.sort(key=lambda n: n.get("ts") or "", reverse=True)
    return [
        {
            "date": (n.get("ts") or "")[:10],
            "impact": n.get("impact"),
            "headline": n.get("headline"),
            "url": _url(n.get("url")),
        }
        for n in rows[:limit]
        if n.get("headline")
    ]


def _research_docs(research, sym, limit=5):
    return [
        {
            "date": d.get("date"),
            "type": d.get("doc_type") or d.get("source"),
            "title": d.get("one_line") or d.get("digest"),
            "url": _url(d.get("url")),
        }
        for d in (research.get("by_ticker", {}) or {}).get(sym, [])[:limit]
    ]


def _document_queue_status(queue_state):
    rows = queue_state.get("history") or queue_state.get("queue") or []
    return {
        (row.get("doc_id"), row.get("content_sha256")): {
            "approval_status": row.get("approval_status"),
            "synthesis_status": row.get("synthesis_status"),
            "training_mode": bool(row.get("training_mode")),
        }
        for row in rows
        if isinstance(row, dict) and row.get("doc_id")
    }


def _company_filings(document_state, queue_status, sym, limit=30):
    rows = []
    for doc in (document_state.get("documents") or {}).values():
        if sym not in (doc.get("tickers") or []):
            continue
        evidence = [
            {
                "page": item.get("page"),
                "text": item.get("text"),
                "source_url": _url(item.get("source_url") or doc.get("source_url")),
            }
            for item in (doc.get("evidence") or [])[:4]
            if isinstance(item, dict) and item.get("text")
        ]
        facts = [
            {
                "fact_id": fact.get("fact_id"),
                "type": fact.get("fact_type"),
                "raw_value": fact.get("raw_value"),
                "normalized_value": fact.get("normalized_value"),
                "unit": fact.get("unit"),
                "currency": fact.get("currency"),
                "scale_multiplier": fact.get("scale_multiplier"),
                "evidence": (fact.get("evidence") or [])[:1],
            }
            for fact in (doc.get("facts") or [])[:8]
            if isinstance(fact, dict)
        ]
        queue = queue_status.get((doc.get("doc_id"), doc.get("content_sha256")), {})
        rows.append({
            "doc_id": doc.get("doc_id"),
            "date": doc.get("published_at"),
            "type": doc.get("doc_type"),
            "title": doc.get("title"),
            "url": _url(doc.get("source_url")),
            "source": doc.get("source"),
            "status": doc.get("status"),
            "error": doc.get("error"),
            "content_sha256": doc.get("content_sha256"),
            "evidence": evidence,
            "facts": facts,
            "synthesis": queue,
        })
    rows.sort(key=lambda row: (row.get("date") or "", row.get("doc_id") or ""), reverse=True)
    return rows[:limit]


def _company_timeline(event_state, sym, limit=50):
    company = (event_state.get("companies") or {}).get(sym) or {}
    events = [
        {
            "event_id": event.get("event_id"),
            "doc_id": event.get("doc_id"),
            "date": event.get("event_date"),
            "type": event.get("event_type"),
            "priority_weight": event.get("priority_weight"),
            "evidence": (event.get("evidence") or [])[:2],
        }
        for event in (company.get("events") or [])
        if isinstance(event, dict)
    ]
    events.sort(key=lambda row: (row.get("date") or "", row.get("event_id") or ""), reverse=True)
    changes = [
        {
            "change_id": change.get("change_id"),
            "doc_id": change.get("doc_id"),
            "date": change.get("changed_at"),
            "type": change.get("change_type") or "document_revision",
            "previous_sha256": change.get("previous_sha256"),
            "content_sha256": change.get("content_sha256"),
            "fact_delta": change.get("fact_delta"),
        }
        for change in (company.get("changes") or [])
        if isinstance(change, dict)
    ]
    changes.sort(key=lambda row: (row.get("date") or "", row.get("change_id") or ""), reverse=True)
    return events[:limit], changes[:20]


def _company_sources(source_state, sym):
    row = ((source_state.get("tickers") or source_state.get("companies") or {}).get(sym) or {})
    sources = row.get("monitored_pages") if isinstance(row.get("monitored_pages"), list) else []
    document_links = row.get("document_links") if isinstance(row.get("document_links"), list) else []
    return {
        "status": row.get("status") or source_state.get("status") or "unknown",
        "error": row.get("error"),
        "issuer_url": _url(row.get("issuer_url") or row.get("website")),
        "sources": [
            {
                "kind": source.get("kind"),
                "url": _url(source.get("url")),
                "title": source.get("label"),
                "changed": bool(source.get("previous_sha256")),
                "last_changed": source.get("last_changed_at"),
                "first_seen": source.get("first_seen_at"),
                "status": source.get("status"),
            }
            for source in sources[:12]
            if isinstance(source, dict) and _url(source.get("url"))
        ],
        "documents": [
            {
                "id": document.get("id"),
                "type": document.get("document_type"),
                "title": document.get("label"),
                "url": _url(document.get("url")),
                "first_seen": document.get("first_seen_at"),
            }
            for document in document_links[:40]
            if isinstance(document, dict) and _url(document.get("url"))
        ],
    }


def _offmarket(offmarket, sym):
    shares = value = trades = days = 0
    for day_data in (offmarket.get("days") or {}).values():
        row = day_data.get(sym) if isinstance(day_data, dict) else None
        if not row:
            continue
        shares += row.get("shares") or 0
        value += row.get("value") or 0
        trades += row.get("trades") or 0
        days += 1
    return None if days == 0 else {
        "shares": shares,
        "value_pkr": value,
        "trades": trades,
        "days": days,
        "retention_days": offmarket.get("retention_days"),
    }


def _insider(insider, sym):
    rows = list((insider.get("symbols") or {}).get(sym) or [])
    rows.sort(key=lambda r: r.get("date") or "", reverse=True)
    return [
        {
            "date": r.get("date"),
            "title": r.get("title"),
            "pdf_url": r.get("pdf_url"),
            "parsed_transactions": len(r.get("transactions") or []),
        }
        for r in rows[:5]
    ]


def build():
    universe = load_json(STATE / "universe.json", {"symbols": {}}).get("symbols", {})
    quant = load_json(STATE / "quant.json", {"tickers": {}}).get("tickers", {})
    live = load_json(STATE / "live.json", {"tickers": {}}).get("tickers", {})
    profiles_state = load_json(STATE / "company_profiles.json", {"tickers": {}})
    profiles = profiles_state.get("tickers", {})
    fundamentals = load_json(STATE / "fundamentals.json", {"tickers": {}}).get("tickers", {})
    score = load_json(STATE / "fundamental_scores.json", {"tickers": {}}).get("tickers", {})
    fairvalue = load_json(STATE / "fairvalue.json", {"tickers": {}}).get("tickers", {})
    liquidity = load_json(STATE / "liquidity.json", {"tickers": {}}).get("tickers", {})
    sectors = load_json(STATE / "sectors.json", {"tickers": {}}).get("tickers", {})
    news = load_json(STATE / "newslog.json", [])
    research = load_json(STATE / "research_index.json", {})
    company_documents = load_json(STATE / "company_documents.json", {"documents": {}})
    company_events = load_json(STATE / "company_event_ledger.json", {"companies": {}})
    synthesis_queue = load_json(STATE / "document_synthesis_queue.json", {"queue": [], "history": []})
    source_registry = load_json(STATE / "company_intel" / "source_registry.json", {"tickers": {}})
    insider = load_json(STATE / "insider_activity.json", {"symbols": {}})
    offmarket = load_json(STATE / "offmarket_activity.json", {"days": {}})
    queue_status = _document_queue_status(synthesis_queue)

    symbols = sorted(
        profiles,
        key=lambda s: (-(liquidity.get(s, {}).get("adtv_pkr") or 0), s),
    )
    rows = []
    for sym in symbols:
        q = quant.get(sym, {})
        lv = live.get(sym, {})
        f = fundamentals.get(sym, {})
        sc = score.get(sym, {})
        fv = fairvalue.get(sym, {})
        liq = liquidity.get(sym, {})
        profile = profiles.get(sym, {})
        filings = _company_filings(company_documents, queue_status, sym)
        timeline, changes = _company_timeline(company_events, sym)
        sources = _company_sources(source_registry, sym)
        rows.append({
            "symbol": sym,
            "name": (universe.get(sym) or {}).get("name") or f.get("name") or "",
            "sector": (sectors.get(sym) or {}).get("sector") or "",
            "indices": (universe.get(sym) or {}).get("in", []),
            "price": {
                "current": lv.get("current") or q.get("close"),
                "date": q.get("date"),
                "ret_1d": q.get("ret_1d"),
                "ret_20d": q.get("ret_20d"),
            },
            "profile": {
                "business_description": profile.get("business_description"),
                "incorporation": profile.get("incorporation"),
                "source_url": profile.get("source_url"),
                "fetched": profile.get("fetched"),
                "stale": bool(profile.get("stale")),
            },
            "fundamentals": {
                "market_cap": f.get("market_cap"),
                "eps": f.get("eps"),
                "pe": f.get("pe"),
                "forward_pe": f.get("forward_pe"),
                "div_yield": f.get("div_yield"),
                "payout_ratio": f.get("payout_ratio"),
                "beta": f.get("beta"),
                "rating": sc.get("rating"),
                "overall": sc.get("overall"),
            },
            "valuation": {
                "verdict": fv.get("verdict"),
                "composite_fair": fv.get("composite_fair"),
                "mispricing_pct": fv.get("mispricing_pct"),
            },
            "liquidity": {
                "research_eligible": bool(liq.get("research_eligible")),
                "signal_eligible": bool(liq.get("signal_eligible")),
                "adtv_pkr": liq.get("adtv_pkr"),
                "adtv_m": _round((liq.get("adtv_pkr") or 0) / 1_000_000, 1),
            },
            "documents": _research_docs(research, sym),
            "filings": filings,
            "timeline": timeline,
            "changes": changes,
            "sources": sources,
            "intelligence": {
                "document_count": len(filings),
                "event_count": len(timeline),
                "change_count": len(changes),
                "pending_synthesis": sum(
                    1 for filing in filings
                    if (filing.get("synthesis") or {}).get("approval_status") == "pending"
                ),
                "last_event_at": timeline[0].get("date") if timeline else None,
                "source_status": sources.get("status"),
            },
            "news": _latest_news(news, sym),
            "insider_filings": _insider(insider, sym),
            "offmarket": _offmarket(offmarket, sym),
        })

    save_json(OUT, {
        "meta": {
            "built": time.strftime("%Y-%m-%d %H:%M"),
            "source": "Henneth state layer",
            "profile_source": profiles_state.get("source"),
            "profile_updated": profiles_state.get("updated"),
            "count": len(rows),
            "note": "Private company-intelligence slice. Research, not advice. No execution or order path.",
        },
        "tickers": rows,
    })
    print(f"ci_slice: {len(rows)} tickers -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
