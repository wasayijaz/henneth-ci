#!/usr/bin/env python3
"""Offline guard for period/unit/provenance and no-churn financial transforms."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from build_financial_series import _sanitize_row, build, merge_rows
from build_company_graph import build as build_graph
from financial_series import normalize_fact


def _fixture(title: str, page: str, raw: str = "12,345") -> tuple[dict, dict, list[str]]:
    doc = {"doc_id": "psx:check", "tickers": ["ABC"], "title": title,
           "source_url": "https://dps.psx.com.pk/download/document/1.pdf", "status": "ready"}
    fact = {"fact_id": "fact_fixture", "fact_type": "revenue", "raw_value": raw,
            "normalized_value": 12345, "unit": "reported", "scale_multiplier": 1,
            "evidence": [{"source_url": doc["source_url"], "page": 1, "text": "Revenue " + raw}]}
    return doc, fact, [page]


def run() -> None:
    doc, fact, pages = _fixture("ABC Quarterly Results for the period ended 30.09.2025",
                                "CONDENSED CONSOLIDATED STATEMENT (Rupees in million) Revenue 12,345")
    row = normalize_fact(doc, fact, pages=pages)
    assert row and row["period_end"] == "2025-09-30", row
    assert row["period_type"] == "quarter", row
    assert row["consolidation"] == "consolidated", row
    assert row["currency"] == "PKR" and row["unit_multiplier"] == 1_000_000, row
    assert row["normalized_value"] == 12_345_000_000, row
    assert row["readiness"] == "model_loadable", row
    assert not {"missing_period_end", "missing_currency", "missing_unit_scale", "missing_consolidation_basis"}.intersection(row["quality_flags"]), row
    eps_doc = {**doc, "doc_id": "psx:eps-fixture", "title": "ABC Results"}
    eps_fact = {"fact_id": "fact_eps", "fact_type": "eps", "raw_value": "12.5", "normalized_value": 12.5,
                "unit": "PKR/share", "scale_multiplier": 1,
                "evidence": [{"source_url": doc["source_url"], "page": 1, "text": "EPS Rs 12.5. Revenue Rs 12 bn."}]}
    eps = normalize_fact(eps_doc, eps_fact, pages=["EPS Rs 12.5. Revenue Rs 12 bn."])
    assert eps and eps["unit_multiplier"] == 1 and eps["normalized_value"] == 12.5, eps
    unclaimed_fact = {"fact_id": "fact_div", "fact_type": "dividend", "raw_value": "26",
                      "normalized_value": 26, "unit": "PKR/share", "scale_multiplier": 1_000_000,
                      "evidence": [{"source_url": doc["source_url"], "page": 1,
                                    "text": "Unclaimed dividend 26,721 (Rupees in million)"}]}
    unclaimed = normalize_fact(eps_doc | {"doc_id": "psx:div-fixture"}, unclaimed_fact,
                               pages=["Unclaimed dividend 26,721 (Rupees in million)"])
    assert unclaimed and unclaimed["unit_multiplier"] == 1 and unclaimed["normalized_value"] == 26, unclaimed

    doc2, fact2, pages2 = _fixture("ABC Annual Results for year ended 31.12.2024",
                                  "SEPARATE FINANCIAL STATEMENTS (Rupees in thousand) Revenue 12,345")
    row2 = normalize_fact(doc2 | {"doc_id": "psx:fixture2"}, fact2 | {"fact_id": "fact_fixture2"}, pages=pages2)
    assert row2 and row2["period_end"] == "2024-12-31" and row2["consolidation"] == "unconsolidated", row2
    assert row2["unit_multiplier"] == 1_000 and row2["normalized_value"] == 12_345_000, row2

    missing_doc, missing_fact, missing_pages = _fixture("ABC Results", "Revenue 12,345")
    missing = normalize_fact(missing_doc, missing_fact, pages=missing_pages)
    assert missing and missing["period_end"] is None and "missing_period_end" in missing["quality_flags"], missing
    misleading_doc, misleading_fact, _ = _fixture("ABC Results", "Revenue 12,345")
    misleading_fact["evidence"][0]["page"] = 1
    misleading = normalize_fact(misleading_doc, misleading_fact,
                                 pages=["Revenue 12,345", "Financial period ended 31.12.2024"])
    assert misleading and misleading["period_end"] is None, "borrowed a period from a different page"
    assert normalize_fact(missing_doc, missing_fact | {"evidence": [{"page": 0, "text": "Revenue 12,345"}]}, pages=missing_pages) is None
    repaired = _sanitize_row({"unit": "PKR/share", "unit_multiplier": 1_000_000,
                              "raw_value": "12.5", "normalized_value": 12_500_000,
                              "metric": "eps", "quality_flags": ["missing_period_end"]})
    assert repaired["unit_multiplier"] == 1 and repaired["normalized_value"] == 12.5
    assert repaired["readiness"] == "audit_only"

    with tempfile.TemporaryDirectory(prefix="henneth-financial-check-") as temp:
        root = Path(temp)
        input_path = root / "company_documents.json"
        output_path = root / "company_financial_series.json"
        input_path.write_text(json.dumps({"documents": {"psx:fixture": {**doc, "facts": [fact]}}}), encoding="utf-8")
        first = build(input_path, output_path)
        bytes_first = output_path.read_bytes()
        second = build(input_path, output_path)
        assert first["tickers"]["ABC"]["facts"], first
        assert output_path.read_bytes() == bytes_first, "no-op build rewrote durable series"
        merge_rows([row], output_path)
        merged = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(merged["tickers"]["ABC"]["facts"]) == 1, "merge duplicated a stable row"
        poorer = dict(row)
        poorer["period_end"] = None
        poorer["period_type"] = "unknown"
        poorer["consolidation"] = "unknown"
        merge_rows([poorer], output_path)
        merged = json.loads(output_path.read_text(encoding="utf-8"))
        assert merged["tickers"]["ABC"]["facts"][0]["period_end"] == row["period_end"], "poorer rebuild replaced richer row"
        sources_path = root / "company_source_qa.json"
        graph_path = root / "company_graph.json"
        source_url = doc["source_url"]
        docs_payload = {"documents": {doc["doc_id"]: {**doc, "events": [{"event_id": "evt_fixture", "event_type": "earnings", "event_date": "2025-10-01", "evidence": [{"source_url": source_url, "page": 1, "text": "Results"}]}], "facts": [fact]}}}
        input_path.write_text(json.dumps(docs_payload), encoding="utf-8")
        sources_path.write_text(json.dumps({"tickers": {}, "sources": {}}), encoding="utf-8")
        graph = build_graph(input_path, output_path, sources_path, graph_path)
        factual = {"SUPPORTS_FACT", "REPORTS_PERIOD", "HAS_EVENT", "EVIDENCED_BY", "REVISION_OF"}
        assert all(e.get("evidence", {}).get("source_url") for e in graph["edges"] if e.get("type") in factual), graph
        graph_bytes = graph_path.read_bytes()
        build_graph(input_path, output_path, sources_path, graph_path)
        assert graph_path.read_bytes() == graph_bytes, "no-op graph rewrote durable state"
    print("financial graph self-check: ok")


if __name__ == "__main__":
    try:
        run()
    except (AssertionError, KeyError, TypeError) as exc:
        print(f"financial graph self-check: FAIL: {exc}")
        sys.exit(1)
