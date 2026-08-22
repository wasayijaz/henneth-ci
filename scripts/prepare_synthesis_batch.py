#!/usr/bin/env python3
"""Prepare a compact, balanced CI synthesis training batch.

This is the token-efficiency boundary: model agents receive only selected changed documents and
their retained evidence, not the full state corpus. It performs no model call and writes only to
ignored `.cache/company_intel/`.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from psx_data import ROOT, STATE, load_json, save_json

DEFAULT_OUT = ROOT / ".cache" / "company_intel" / "training_batch.json"
MAX_BATCH = 10


def _approved_keys(receipts: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (item.get("doc_id"), item.get("content_sha256"))
        for receipt in receipts.get("receipts") or []
        for item in receipt.get("based_on") or []
        if isinstance(item, dict) and item.get("doc_id") and item.get("content_sha256")
    }


def select(queue: dict[str, Any], documents: dict[str, Any], receipts: dict[str, Any],
           limit: int, allowed_symbols: set[str] | None = None,
           published_since: str | None = None) -> list[dict[str, Any]]:
    approved = _approved_keys(receipts)
    docs = documents.get("documents") or {}
    candidates = []
    for row in queue.get("queue") or []:
        if not isinstance(row, dict) or row.get("approval_status") != "pending":
            continue
        key = (row.get("doc_id"), row.get("content_sha256"))
        doc = docs.get(row.get("doc_id")) or {}
        if key in approved or doc.get("status") != "ready" or doc.get("content_sha256") != key[1]:
            continue
        if not (doc.get("evidence") or doc.get("events") or doc.get("facts")):
            continue
        tickers = sorted(set(doc.get("tickers") or row.get("tickers") or []))
        if allowed_symbols is not None and not (set(tickers) & allowed_symbols):
            continue
        if published_since and str(doc.get("published_at") or "")[:10] < published_since:
            continue
        candidates.append({"row": row, "doc": doc, "balance_ticker": tickers[0] if tickers else "_unassigned"})

    chosen = []
    counts: Counter[str] = Counter()
    while candidates and len(chosen) < limit:
        candidates.sort(key=lambda item: (
            counts[item["balance_ticker"]],
            -int(item["row"].get("priority") or 0),
            item["row"].get("queued_at") or "",
            item["row"].get("queue_id") or "",
        ))
        item = candidates.pop(0)
        counts[item["balance_ticker"]] += 1
        chosen.append(item)
    return chosen


def build(limit: int = MAX_BATCH, output: Path = DEFAULT_OUT,
          published_since: str | None = None) -> dict[str, Any]:
    queue = load_json(STATE / "document_synthesis_queue.json", {"queue": []})
    documents = load_json(STATE / "company_documents.json", {"documents": {}})
    receipts = load_json(STATE / "company_brief_receipts.json", {"receipts": []})
    financial = load_json(STATE / "company_financial_series.json", {"tickers": {}}).get("tickers") or {}
    profiles = load_json(STATE / "company_profiles.json", {"tickers": {}})
    pilot = set((profiles.get("pilot") or {}).get("symbols") or (profiles.get("tickers") or {}).keys())
    selected = select(queue, documents, receipts, limit, pilot, published_since)
    rows = []
    for item in selected:
        row, doc = item["row"], item["doc"]
        doc_id = doc.get("doc_id")
        doc_financial = [
            fact for ticker in doc.get("tickers") or []
            for fact in (financial.get(ticker, {}) or {}).get("facts") or []
            if fact.get("document_id") == doc_id
        ]
        rows.append({
            "queue_id": row.get("queue_id"), "doc_id": doc_id,
            "content_sha256": doc.get("content_sha256"), "tickers": doc.get("tickers") or [],
            "title": doc.get("title"), "doc_type": doc.get("doc_type"),
            "published_at": doc.get("published_at"), "source_url": doc.get("source_url"),
            "events": doc.get("events") or [], "facts": doc.get("facts") or [],
            "evidence": doc.get("evidence") or [], "normalized_financials": doc_financial,
        })
    payload = {"schema_version": 1, "training_mode": True, "count": len(rows), "items": rows,
               "note": "Compact deterministic handoff; no model call and no publication."}
    prior = load_json(output, {}) if output.exists() else {}
    if payload != prior:
        save_json(output, payload)
    print(f"synthesis_batch: {len(rows)} items -> {output.relative_to(ROOT)}")
    return payload


def _self_check() -> int:
    docs = {"documents": {
        "a": {"doc_id": "a", "status": "ready", "content_sha256": "1", "tickers": ["AAA"], "evidence": [{"page": 1}]},
        "b": {"doc_id": "b", "status": "ready", "content_sha256": "2", "tickers": ["AAA"], "evidence": [{"page": 1}]},
        "c": {"doc_id": "c", "status": "ready", "content_sha256": "3", "tickers": ["BBB"], "evidence": [{"page": 1}]},
    }}
    queue = {"queue": [
        {"queue_id": "qa", "doc_id": "a", "content_sha256": "1", "approval_status": "pending", "priority": 5},
        {"queue_id": "qb", "doc_id": "b", "content_sha256": "2", "approval_status": "pending", "priority": 4},
        {"queue_id": "qc", "doc_id": "c", "content_sha256": "3", "approval_status": "pending", "priority": 1},
    ]}
    chosen = select(queue, docs, {"receipts": []}, 2)
    assert [row["row"]["doc_id"] for row in chosen] == ["a", "c"], "batch is not company-balanced"
    approved = {"receipts": [{"based_on": [{"doc_id": "a", "content_sha256": "1"}]}]}
    assert all(row["row"]["doc_id"] != "a" for row in select(queue, docs, approved, 3))
    print("synthesis batch self-check: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=MAX_BATCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--published-since", help="include only documents published on/after YYYY-MM-DD")
    args = parser.parse_args(argv)
    if args.self_check:
        return _self_check()
    if not 1 <= args.limit <= MAX_BATCH:
        parser.error(f"--limit must be between 1 and {MAX_BATCH}")
    output = args.output.resolve()
    cache_root = (ROOT / ".cache" / "company_intel").resolve()
    if not output.is_relative_to(cache_root):
        parser.error("--output must stay inside .cache/company_intel")
    if args.published_since and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.published_since):
        parser.error("--published-since must be YYYY-MM-DD")
    build(args.limit, output, args.published_since)
    return 0


if __name__ == "__main__":
    sys.exit(main())
