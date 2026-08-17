#!/usr/bin/env python3
"""Build deterministic, evidence-linked company change intelligence.

This is a product-facing digest over already-retained official-source state. It
does not scrape, call a model, infer investment advice, or invent facts. Items
are included only when they can point back to a source URL/document/page or to a
recorded source-registry hash change.
"""
from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path
from typing import Any

from psx_data import STATE, load_json, save_json
from document_events import event_is_supported

OUT = STATE / "company_intel" / "change_intelligence.json"
MAX_ITEMS = 18
MATERIAL_EVENT_TYPES = {
    "acquisition", "regulatory_action", "management_change", "rating_change",
    "contract", "credit_event",
}
ROUTINE_EVENT_TYPES = {"earnings", "board_meeting", "agm", "briefing", "dividend"}


def _id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return "chg_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def _date(value: Any) -> str:
    return str(value or "")[:10]


def _source_evidence(item: dict[str, Any], doc: dict[str, Any] | None = None) -> dict[str, Any] | None:
    evidence = next((e for e in item.get("evidence") or [] if isinstance(e, dict)), {})
    url = evidence.get("source_url") or (doc or {}).get("source_url")
    if not url:
        return None
    out = {"source_url": url}
    if isinstance(evidence.get("page"), int) and evidence["page"] > 0:
        out["page"] = evidence["page"]
    if evidence.get("text"):
        out["text"] = evidence["text"]
    return out


def _doc_map(documents_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    documents = documents_payload.get("documents") if isinstance(documents_payload, dict) else {}
    return documents if isinstance(documents, dict) else {}


def _doc_items(documents: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for doc_id, doc in sorted(documents.items()):
        if not isinstance(doc, dict) or doc.get("status") != "ready" or not doc.get("source_url"):
            continue
        tickers = sorted({str(t).upper() for t in doc.get("tickers") or [] if str(t).strip()})
        date_value = doc.get("published_at") or doc.get("retrieved_at")
        date_basis = "published_at" if doc.get("published_at") else "retrieved_at"
        for ticker in tickers:
            by_symbol.setdefault(ticker, []).append({
                "id": _id(ticker, "document", doc_id, doc.get("content_sha256")),
                "kind": "document",
                "severity": "routine" if doc.get("doc_type") in {"results", "board_meeting", "dividend"} else "watch",
                "date": _date(date_value),
                "date_basis": date_basis,
                "title": doc.get("title") or doc.get("doc_type") or doc_id,
                "summary": f"Official {doc.get('source') or 'source'} document retained as {doc.get('doc_type') or 'unclassified'}.",
                "document_id": doc_id,
                "source_url": doc.get("source_url"),
                "evidence": {"source_url": doc.get("source_url")},
            })
    return by_symbol


def _event_items(events_payload: dict[str, Any], documents: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    companies = events_payload.get("companies") if isinstance(events_payload, dict) else {}
    for ticker, row in sorted((companies or {}).items()):
        symbol = str(ticker).upper()
        for event in (row or {}).get("events") or []:
            if not isinstance(event, dict) or not event_is_supported(event):
                continue
            event_type = event.get("event_type") or "other"
            doc = documents.get(event.get("doc_id")) or {}
            evidence = _source_evidence(event, doc)
            if not evidence:
                continue
            severity = "material" if event_type in MATERIAL_EVENT_TYPES else "routine"
            if event_type == "credit_event":
                severity = "critical"
            by_symbol.setdefault(symbol, []).append({
                "id": _id(symbol, "event", event.get("event_id"), event_type, event.get("event_date")),
                "kind": "event",
                "severity": severity,
                "date": _date(event.get("event_date") or doc.get("published_at")),
                "title": event_type.replace("_", " "),
                "summary": "Official document language matched the desk's event classifier.",
                "document_id": event.get("doc_id"),
                "source_url": evidence.get("source_url"),
                "evidence": evidence,
                "priority_weight": event.get("priority_weight"),
            })
    return by_symbol


def _series_groups(facts: list[dict[str, Any]]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        if fact.get("readiness") != "model_loadable":
            continue
        if not fact.get("period_end"):
            continue
        if fact.get("normalized_value") is None or "conflict" in (fact.get("quality_flags") or []):
            continue
        key = (fact.get("metric"), fact.get("consolidation"), fact.get("currency"),
               fact.get("unit"), fact.get("unit_multiplier"))
        groups.setdefault(key, []).append(fact)
    return groups


def _financial_items(series_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for ticker, bucket in sorted((series_payload.get("tickers") or {}).items()):
        symbol = str(ticker).upper()
        for key, rows in _series_groups((bucket or {}).get("facts") or []).items():
            rows.sort(key=lambda row: (row.get("period_end") or "", row.get("series_id") or ""))
            if len(rows) < 2:
                continue
            prior, latest = rows[-2], rows[-1]
            try:
                old = float(prior.get("normalized_value"))
                new = float(latest.get("normalized_value"))
            except (TypeError, ValueError):
                continue
            delta = new - old
            if delta == 0:
                continue
            pct = (delta / abs(old) * 100) if old else None
            metric, consolidation, currency, unit, multiplier = key
            evidence = _source_evidence(latest)
            if not evidence:
                continue
            direction = "rose" if delta > 0 else "fell"
            by_symbol.setdefault(symbol, []).append({
                "id": _id(symbol, "financial", latest.get("series_id"), prior.get("series_id")),
                "kind": "financial",
                "severity": "watch" if pct is None or abs(pct) < 20 else "material",
                "date": latest.get("period_end"),
                "title": f"{metric or 'metric'} {direction}",
                "summary": f"{metric or 'Metric'} {direction} versus the prior comparable period on the same basis.",
                "metric": metric,
                "period_end": latest.get("period_end"),
                "previous_period_end": prior.get("period_end"),
                "delta": round(delta, 4),
                "delta_pct": round(pct, 2) if pct is not None else None,
                "latest_value": new,
                "previous_value": old,
                "consolidation": consolidation,
                "currency": currency,
                "unit": unit,
                "unit_multiplier": multiplier,
                "document_id": latest.get("document_id"),
                "source_url": evidence.get("source_url"),
                "evidence": evidence,
            })
    return by_symbol


def _source_items(source_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for ticker, row in sorted((source_payload.get("tickers") or {}).items()):
        symbol = str(ticker).upper()
        for page in row.get("monitored_pages") or []:
            if not isinstance(page, dict) or not page.get("url") or not page.get("previous_sha256"):
                continue
            by_symbol.setdefault(symbol, []).append({
                "id": _id(symbol, "source", page.get("url"), page.get("content_sha256")),
                "kind": "source",
                "severity": "watch",
                "date": _date(page.get("last_changed_at") or page.get("first_seen_at")),
                "date_basis": "last_changed_at" if page.get("last_changed_at") else "first_seen_at",
                "title": page.get("label") or page.get("kind") or "Issuer page changed",
                "summary": "Same-domain issuer page hash changed since the previous retained check.",
                "source_url": page.get("url"),
                "evidence": {"source_url": page.get("url")},
                "source_kind": page.get("kind"),
            })
        for link in row.get("document_links") or []:
            if not isinstance(link, dict) or not link.get("url") or not link.get("id"):
                continue
            by_symbol.setdefault(symbol, []).append({
                "id": _id(symbol, "issuer_document", link.get("id")),
                "kind": "issuer_document",
                "severity": "watch" if link.get("document_type") != "annual_report" else "material",
                "date": _date(link.get("first_seen_at")),
                "date_basis": "first_seen_at",
                "title": link.get("label") or link.get("document_type") or "Issuer document discovered",
                "summary": "Same-domain issuer PDF link discovered from the monitored issuer website.",
                "document_id": link.get("id"),
                "source_url": link.get("url"),
                "evidence": {"source_url": link.get("url")},
                "source_page": link.get("source_page"),
            })
    return by_symbol


def _merge_items(*groups: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    symbols = sorted({symbol for group in groups for symbol in group})
    result: dict[str, dict[str, Any]] = {}
    severity_rank = {"critical": 4, "material": 3, "watch": 2, "routine": 1}
    for symbol in symbols:
        items = [item for group in groups for item in group.get(symbol, [])]
        items.sort(key=lambda item: (
            item.get("date") or "",
            severity_rank.get(item.get("severity"), 0),
            item.get("id") or "",
        ), reverse=True)
        capped = items[:MAX_ITEMS]
        counts: dict[str, int] = {}
        for item in capped:
            counts[item["kind"]] = counts.get(item["kind"], 0) + 1
        result[symbol] = {
            "ticker": symbol,
            "status": "active" if capped else "quiet",
            "latest_change_at": capped[0].get("date") if capped else None,
            "counts": counts,
            "items": capped,
        }
    return result


def build(documents_path: Path = STATE / "company_documents.json",
          events_path: Path = STATE / "company_event_ledger.json",
          series_path: Path = STATE / "company_financial_series.json",
          source_path: Path = STATE / "company_intel" / "source_registry.json",
          output_path: Path = OUT) -> dict[str, Any]:
    documents_payload = load_json(documents_path, {"documents": {}})
    documents = _doc_map(documents_payload)
    events_payload = load_json(events_path, {"companies": {}})
    series_payload = load_json(series_path, {"tickers": {}})
    source_payload = load_json(source_path, {"tickers": {}})
    companies = _merge_items(
        _event_items(events_payload, documents),
        _financial_items(series_payload),
        _source_items(source_payload),
        _doc_items(documents),
    )
    payload = {
        "schema_version": 1,
        "companies": companies,
        "_meta": {
            "updated": time.strftime("%Y-%m-%d %H:%M"),
            "company_count": len(companies),
            "item_count": sum(len(row.get("items") or []) for row in companies.values()),
            "note": "Deterministic official-source change digest. Research, not advice.",
        },
    }
    previous = load_json(output_path, {}) if output_path.exists() else {}
    if payload.get("companies") != previous.get("companies"):
        save_json(output_path, payload)
    return payload


def _self_check() -> int:
    source = {
        "tickers": {
            "ABC": {
                "monitored_pages": [
                    {"url": "https://abc.example/investors", "content_sha256": "new"},
                    {
                        "url": "https://abc.example/results",
                        "content_sha256": "new",
                        "previous_sha256": "old",
                        "last_changed_at": "2026-08-18T08:00:00+05:00",
                    },
                ],
                "document_links": [],
            }
        }
    }
    source_items = _source_items(source).get("ABC") or []
    if len(source_items) != 1 or source_items[0].get("source_url") != "https://abc.example/results":
        print("change intelligence self-check: FAIL (absence became a source-change claim)")
        return 1
    series = {
        "tickers": {
            "ABC": {
                "facts": [
                    {
                        "series_id": "old", "metric": "revenue", "period_end": "2025-06-30",
                        "normalized_value": 100, "consolidation": "consolidated", "currency": "PKR",
                        "unit": "million", "unit_multiplier": 1_000_000, "readiness": "model_loadable",
                        "source_url": "https://abc.example/old.pdf", "evidence": [{"page": 2, "source_url": "https://abc.example/old.pdf"}],
                    },
                    {
                        "series_id": "new", "metric": "revenue", "period_end": "2026-06-30",
                        "normalized_value": 120, "consolidation": "consolidated", "currency": "PKR",
                        "unit": "million", "unit_multiplier": 1_000_000, "readiness": "model_loadable",
                        "source_url": "https://abc.example/new.pdf", "evidence": [{"page": 3, "source_url": "https://abc.example/new.pdf"}],
                    },
                    {
                        "series_id": "unknown", "metric": "profit", "period_end": None,
                        "normalized_value": 9, "readiness": "audit_only",
                        "source_url": "https://abc.example/unknown.pdf",
                    },
                ]
            }
        }
    }
    financial = _financial_items(series).get("ABC") or []
    if len(financial) != 1 or financial[0].get("delta_pct") != 20.0:
        print("change intelligence self-check: FAIL (non-comparable facts entered the digest)")
        return 1
    if (financial[0].get("evidence") or {}).get("page") != 3:
        print("change intelligence self-check: FAIL (financial evidence lost its page)")
        return 1
    print("change intelligence self-check: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--documents", type=Path, default=STATE / "company_documents.json")
    parser.add_argument("--events", type=Path, default=STATE / "company_event_ledger.json")
    parser.add_argument("--series", type=Path, default=STATE / "company_financial_series.json")
    parser.add_argument("--sources", type=Path, default=STATE / "company_intel" / "source_registry.json")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if args.self_check:
        return _self_check()
    payload = build(args.documents, args.events, args.series, args.sources, args.output)
    print(f"change_intelligence: companies={payload['_meta']['company_count']} items={payload['_meta']['item_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
