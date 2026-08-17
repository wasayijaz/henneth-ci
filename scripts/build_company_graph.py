#!/usr/bin/env python3
"""Build an evidence-linked company/document/fact/event graph.

This graph is a navigation index, not a model-generated knowledge base.  It
does not create a factual edge unless the edge can carry the official URL and,
where cited, the one-based source page.  Unknown periods remain unlinked.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Any

from psx_data import STATE, load_json, save_json

OUT = STATE / "company_intel" / "company_graph.json"


def _id(kind: str, value: str) -> str:
    return f"{kind}_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _ev(item: dict[str, Any], doc: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = next((e for e in item.get("evidence") or [] if isinstance(e, dict)), {})
    url = evidence.get("source_url") or (doc or {}).get("source_url")
    out = {"source_url": url} if url else {}
    if isinstance(evidence.get("page"), int) and evidence["page"] > 0:
        out["page"] = evidence["page"]
    return out


def build(documents_path: Path = STATE / "company_documents.json",
          series_path: Path = STATE / "company_financial_series.json",
          source_path: Path = STATE / "company_source_qa.json",
          output_path: Path = OUT) -> dict[str, Any]:
    docs_payload = load_json(documents_path, {})
    documents = docs_payload.get("documents") if isinstance(docs_payload, dict) else {}
    documents = documents if isinstance(documents, dict) else {}
    series_payload = load_json(series_path, {})
    series = series_payload.get("tickers") if isinstance(series_payload, dict) else {}
    series = series if isinstance(series, dict) else {}
    source_payload = load_json(source_path, {})
    source_tickers = source_payload.get("tickers") if isinstance(source_payload, dict) else {}
    source_tickers = source_tickers if isinstance(source_tickers, dict) else {}
    source_rows = source_payload.get("sources") if isinstance(source_payload, dict) else {}
    source_rows = source_rows if isinstance(source_rows, dict) else {}

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    companies: dict[str, dict[str, Any]] = {}

    def node(node_id: str, node_type: str, label: str, **extra: Any) -> str:
        value = {"id": node_id, "type": node_type, "label": label}
        value.update({k: v for k, v in extra.items() if v is not None})
        nodes.setdefault(node_id, value)
        return node_id

    def company(ticker: str) -> str:
        symbol = str(ticker).strip().upper()
        if not symbol:
            return ""
        cid = node(f"company:{symbol}", "company", symbol, ticker=symbol)
        companies.setdefault(symbol, {"node_id": cid, "document_ids": [], "period_ids": [],
                                      "fact_ids": [], "event_ids": [], "change_ids": [], "source_ids": []})
        return cid

    def edge(edge_type: str, source: str, target: str, evidence: dict[str, Any] | None = None, **extra: Any) -> None:
        evidence = evidence or {}
        # Provenance is part of identity, so a revised page creates a distinct
        # edge rather than mutating an old fact relationship.
        seed = "|".join((edge_type, source, target, str(evidence.get("source_url") or ""), str(evidence.get("page") or "")))
        eid = _id("edge", seed)
        row = {"id": eid, "type": edge_type, "from": source, "to": target}
        if evidence:
            row["evidence"] = evidence
        row.update({k: v for k, v in extra.items() if v is not None})
        edges.setdefault(eid, row)

    for doc_key, doc in sorted(documents.items()):
        if not isinstance(doc, dict) or doc.get("status") not in {"ready", "stale", "error"}:
            continue
        doc_id = str(doc.get("doc_id") or doc_key)
        did = node(f"document:{doc_id}", "document", str(doc.get("title") or doc_id),
                   document_id=doc_id, doc_type=doc.get("doc_type"), published_at=doc.get("published_at"),
                   status=doc.get("status"), source_url=doc.get("source_url"))
        tickers = sorted({str(t).strip().upper() for t in (doc.get("tickers") or []) if str(t).strip()})
        for ticker in tickers:
            company(ticker)
            # Filing relationship has official source URL but no page claim.
            edge("FILED", f"company:{ticker}", did, _ev({}, doc), document_id=doc_id)
            companies[ticker]["document_ids"].append(doc_id)
        # Facts and their reporting periods come from the normalized series.
        for ticker, bucket in series.items():
            for fact in (bucket or {}).get("facts") or []:
                if fact.get("document_id") != doc_id:
                    continue
                fid = f"fact:{doc_id}:{fact.get('fact_id') or fact.get('series_id') or _id('fact', str(fact))}"
                node(fid, "fact", str(fact.get("metric") or "other"), document_id=doc_id,
                     metric=fact.get("metric"), raw_value=fact.get("raw_value"), normalized_value=fact.get("normalized_value"),
                     period_end=fact.get("period_end"), period_type=fact.get("period_type"),
                     consolidation=fact.get("consolidation"), currency=fact.get("currency"),
                     quality_flags=fact.get("quality_flags"))
                evidence = _ev(fact, doc)
                if not evidence.get("source_url"):
                    continue
                edge("SUPPORTS_FACT", did, fid, evidence, document_id=doc_id)
                for ticker_value in (fact.get("ticker"), *tickers):
                    symbol = str(ticker_value or "").upper()
                    if not symbol:
                        continue
                    company(symbol)
                    companies[symbol]["fact_ids"].append(fid)
                    if fact.get("period_end"):
                        pseed = "|".join((symbol, str(fact.get("period_end")), str(fact.get("period_type")), str(fact.get("consolidation"))))
                        pid = _id("period", pseed)
                        node(pid, "period", str(fact["period_end"]), ticker=symbol,
                             period_end=fact.get("period_end"), period_type=fact.get("period_type"),
                             consolidation=fact.get("consolidation"))
                        edge("REPORTS_PERIOD", did, pid, evidence, document_id=doc_id)
                        companies[symbol]["period_ids"].append(pid)
                sid = node(f"source:{_id('url', evidence['source_url'])}", "source", evidence["source_url"],
                           url=evidence["source_url"])
                edge("EVIDENCED_BY", fid, sid, evidence, document_id=doc_id)
        # Events are individual nodes—not aggregate event-type summaries—so
        # every event relationship is traceable to its filing/page.
        for event in doc.get("events") or []:
            if not isinstance(event, dict) or not event.get("event_id"):
                continue
            eid = f"event:{event['event_id']}"
            node(eid, "event", str(event.get("event_type") or "other"), event_id=event.get("event_id"),
                 event_type=event.get("event_type"), event_date=event.get("event_date"), priority_weight=event.get("priority_weight"))
            evidence = _ev(event, doc)
            if not evidence.get("source_url"):
                continue
            for ticker in tickers:
                company(ticker)
                edge("HAS_EVENT", f"company:{ticker}", eid, evidence, document_id=doc_id)
                companies[ticker]["event_ids"].append(event["event_id"])
            edge("EVIDENCED_BY", eid, did, evidence, document_id=doc_id)
        for change in doc.get("ledger_changes") or []:
            if not isinstance(change, dict) or not change.get("change_id"):
                continue
            cid = f"change:{change['change_id']}"
            node(cid, "change", str(change["change_id"]), change_id=change["change_id"],
                 changed_at=change.get("changed_at"), fact_delta=change.get("fact_delta"))
            evidence = _ev({}, doc)
            if not evidence.get("source_url"):
                continue
            edge("REVISION_OF", cid, did, evidence, document_id=doc_id)
            for ticker in tickers:
                company(ticker)
                edge("HAS_CHANGE", f"company:{ticker}", cid, evidence, document_id=doc_id)
                companies[ticker]["change_ids"].append(change["change_id"])

    for ticker, row in sorted(source_tickers.items()):
        symbol = str(ticker).upper()
        company(symbol)
        for source_id in row.get("source_ids") or []:
            source = source_rows.get(source_id)
            if not isinstance(source, dict) or not source.get("url"):
                continue
            sid = node(f"source:{source_id}", "source", source["url"], source_id=source_id,
                       ticker=symbol, url=source["url"], kind=source.get("kind"), status=source.get("status"),
                       quality_flags=row.get("quality_flags"))
            edge("HAS_SOURCE", f"company:{symbol}", sid, {"source_url": source["url"]},
                 status=source.get("status"), quality_flags=row.get("quality_flags"))
            companies[symbol]["source_ids"].append(source_id)

    for summary in companies.values():
        for key in ("document_ids", "period_ids", "fact_ids", "event_ids", "change_ids", "source_ids"):
            summary[key] = sorted(set(summary[key]))
        summary["counts"] = {key.removesuffix("_ids"): len(summary[key]) for key in summary if key.endswith("_ids")}
    graph = {"schema_version": 1, "nodes": [nodes[key] for key in sorted(nodes)],
             "edges": [edges[key] for key in sorted(edges)], "companies": {k: companies[k] for k in sorted(companies)},
             "_meta": {"updated": time.strftime("%Y-%m-%d %H:%M"), "node_count": len(nodes), "edge_count": len(edges),
                       "source_documents": len(documents), "note": "Every factual edge carries source URL and cited page when available."}}
    previous = load_json(output_path, {}) if output_path.exists() else {}
    if graph["nodes"] != previous.get("nodes") or graph["edges"] != previous.get("edges") or graph["companies"] != previous.get("companies"):
        save_json(output_path, graph)
    return graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=Path, default=STATE / "company_documents.json")
    parser.add_argument("--series", type=Path, default=STATE / "company_financial_series.json")
    parser.add_argument("--sources", type=Path, default=STATE / "company_source_qa.json")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    graph = build(args.documents, args.series, args.sources, args.output)
    print(f"company_graph: companies={len(graph['companies'])} nodes={graph['_meta']['node_count']} edges={graph['_meta']['edge_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

