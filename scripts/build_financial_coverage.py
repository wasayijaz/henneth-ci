"""Build Financial Results Coverage & Qualification Queue v1.

This is a metadata-only coverage map. It never opens PDFs, promotes audit-only
facts, or infers financial values.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "financial_coverage.json"
REQUIRED_METRICS = ("revenue", "profit_after_tax_attributable", "basic_eps")
REQUIRED_ANNUAL_SLOT_COUNT = 3


def _stable_id(prefix: str, *parts: Any) -> str:
    text = "\x1f".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]}"


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _url(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if text.startswith(("https://", "http://")) else None


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else None


def _period_from_doc(row: dict[str, Any], classification: str) -> dict[str, Any] | None:
    title = row.get("title") or row.get("one_line")
    text = _text(title)
    if not text:
        return None
    patterns = [
        (r"(?:quarter|period|nine months|half year|six months)\s+ended\s+(\d{4})[-./](\d{1,2})[-./](\d{1,2})", "interim"),
        (r"(?:quarter|period|nine months|half year|six months)\s+ended\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", "interim"),
        (r"(?:year|twelve months)\s+ended\s+(\d{4})[-./](\d{1,2})[-./](\d{1,2})", "annual"),
        (r"(?:year|twelve months)\s+ended\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", "annual"),
        (r"(?<!half[ -])(?:year|twelve months)\s+ended\s+(?:[-:.,]\s*)?(\d{1,2})[.-](\d{1,2})[.-](\d{4})", "annual"),
        (r"(?<!half[ -])(?:year|twelve months)\s+ended\s+(?:[-:.,]\s*)?([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", "annual"),
        (r"31[.-]12[.-](\d{4})", "unknown"),
        (r"31[.-]03[.-](\d{4})", "unknown"),
        (r"30[.-]09[.-](\d{4})", "unknown"),
        (r"30[.-]06[.-](\d{4})", "unknown"),
    ]
    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    for pattern, period_type in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 1:
            year = int(groups[0])
            matched = match.group(0)
            month = int(matched.split(".")[1] if "." in matched else matched.split("-")[1])
            day = 30 if month in {6, 9} else 31
        elif groups[0].isdigit() and len(groups[0]) == 4:
            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
        elif groups[0].isdigit():
            day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
        else:
            month = months.get(groups[0].lower())
            if not month:
                return None
            day, year = int(groups[1]), int(groups[2])
        try:
            period_end = date(year, month, day).isoformat()
        except ValueError:
            # Ambiguous title fragments such as a malformed ``2025-30-06``
            # must never become an annual slot.  Keep the document visible but
            # leave its period unqualified for a future bounded restage.
            continue
        return {
            "period_end": period_end,
            "period_type": period_type,
            "source": "title",
            "matched_text": match.group(0),
        }
    doc_type = _text(row.get("doc_type")).lower()
    if classification == "financial_statement" and (doc_type == "annual_report" or "annual report" in text.lower()):
        return {
            "period_end": None,
            "period_type": "annual",
            "source": "metadata",
            "matched_text": "annual_report",
        }
    return None


def _is_official_psx(row: dict[str, Any]) -> bool:
    url = _url(row.get("source_url") or row.get("url"))
    source = _text(row.get("source")).lower()
    doc_id = _text(row.get("doc_id") or row.get("hash"))
    return doc_id.startswith("psx:") and (url is None or "dps.psx.com.pk" in url) and source in {"", "filing", "psx dps"}


def _classification(row: dict[str, Any]) -> str:
    doc_type = _text(row.get("doc_type")).lower()
    title = _text(row.get("title") or row.get("one_line")).lower()
    if "other than financial results" in title:
        return "excluded_board_meeting_other_than_results"
    if doc_type in {"results", "financial_results"} or "financial results" in title:
        return "financial_results"
    if doc_type in {"financial_statement", "annual_report"} or "annual report" in title or "quarterly report" in title:
        return "financial_statement"
    if doc_type == "board_meeting" and "financial result" in title:
        return "financial_results_notice"
    return "non_financial_official_document"


def _doc_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_official_psx(row):
        return None
    title = _text(row.get("title") or row.get("one_line"))
    classification = _classification(row)
    period = _period_from_doc(row, classification)
    doc_id = _text(row.get("doc_id") or row.get("hash"))
    return {
        "document_id": doc_id,
        "title": title,
        "doc_type": row.get("doc_type"),
        "classification": classification,
        "published_at": row.get("published_at") or _iso_date(row.get("date")),
        "source_url": _url(row.get("source_url") or row.get("url")),
        "status": row.get("status"),
        "content_sha256": row.get("content_sha256"),
        "safe_period": period,
    }


def _indexed_docs(symbol: str, research_index: dict[str, Any], company_documents: dict[str, Any]) -> list[dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for row in (research_index.get("by_ticker") or {}).get(symbol) or []:
        doc = _doc_row(row)
        if doc:
            docs[doc["document_id"]] = doc
    for row in (company_documents.get("documents") or {}).values():
        if symbol not in (row.get("tickers") or []):
            continue
        doc = _doc_row(row)
        if doc:
            existing = docs.get(doc["document_id"]) or {}
            docs[doc["document_id"]] = {**existing, **{k: v for k, v in doc.items() if v not in (None, "", [])}}
    rows = list(docs.values())
    rows.sort(key=lambda item: (item.get("published_at") or "", item.get("document_id") or ""), reverse=True)
    return rows


def _annual_slots(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    periods = {}
    for doc in docs:
        safe_period = doc.get("safe_period") or {}
        period_end = safe_period.get("period_end")
        if safe_period.get("period_type") != "annual" or not period_end:
            continue
        periods[period_end] = {
            "period_end": period_end,
            "period_type": "annual",
            "source": safe_period.get("source"),
            "matched_text": safe_period.get("matched_text"),
            "document_id": doc.get("document_id"),
            "title": doc.get("title"),
        }
    rows = [periods[period] for period in sorted(periods, reverse=True)[:REQUIRED_ANNUAL_SLOT_COUNT]]
    while len(rows) < REQUIRED_ANNUAL_SLOT_COUNT:
        slot = len(rows) + 1
        rows.append({
            "period_end": None,
            "period_type": "annual",
            "source": "unknown",
            "slot": f"annual_period_{slot}",
            "evidence_status": "missing_explicit_annual_period_evidence",
        })
    for idx, row in enumerate(rows, start=1):
        row.setdefault("slot", f"annual_period_{idx}")
    return rows


def _audit_coverage(symbol: str, financial_series: dict[str, Any]) -> dict[str, Any]:
    row = (financial_series.get("tickers") or {}).get(symbol) or {}
    facts = [fact for fact in row.get("facts") or [] if isinstance(fact, dict)]
    audit_only = [fact for fact in facts if fact.get("readiness") == "audit_only"]
    by_metric: dict[str, int] = {}
    for fact in audit_only:
        metric = fact.get("metric")
        if metric:
            by_metric[metric] = by_metric.get(metric, 0) + 1
    return {
        "audit_only_fact_count": len(audit_only),
        "audit_only_metrics": [
            {"metric": metric, "fact_count": count}
            for metric, count in sorted(by_metric.items())
        ],
        "model_loadable_count": (row.get("coverage") or {}).get("model_loadable_count", 0),
        "note": "Audit-only facts are retained as coverage signals only and are not promoted into required values.",
    }


def _missing_matrix(slots: list[dict[str, Any]], model_row: dict[str, Any]) -> list[dict[str, Any]]:
    observations = model_row.get("observations") or {}
    rows = []
    for slot in slots:
        period_end = slot.get("period_end")
        missing = []
        present = []
        for metric in REQUIRED_METRICS:
            values = [
                item for item in observations.get(metric) or []
                if period_end and isinstance(item, dict) and item.get("period_end") == period_end
            ]
            if values:
                present.append(metric)
            else:
                missing.append(metric)
        rows.append({
            "slot": slot.get("slot"),
            "period_end": period_end,
            "period_type": "annual",
            "required_metrics": list(REQUIRED_METRICS),
            "present_model_ready_metrics": present,
            "missing_metrics": missing,
            "period_evidence_status": "explicit" if period_end else "missing_explicit_annual_period_evidence",
            "status": "complete" if not missing else "missing_required_metrics",
        })
    return rows


def _top_candidates(docs: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    candidates = [
        doc for doc in docs
        if doc.get("classification") in {"financial_results", "financial_statement"}
        and doc.get("source_url")
        and doc.get("document_id")
    ]
    candidates.sort(key=lambda doc: (
        0 if (doc.get("safe_period") or {}).get("period_type") == "annual" else 1,
        doc.get("published_at") or "",
        doc.get("document_id") or "",
    ), reverse=False)
    candidates = sorted(candidates, key=lambda doc: (doc.get("published_at") or "", doc.get("document_id") or ""), reverse=True)
    return [
        {
            "document_id": doc.get("document_id"),
            "published_at": doc.get("published_at"),
            "title": doc.get("title"),
            "source_url": doc.get("source_url"),
            "safe_period": doc.get("safe_period"),
            "reason": "official financial document candidate for future owner-approved bounded restage",
        }
        for doc in candidates[:limit]
    ]


def build() -> dict:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    research_index = load_json(STATE / "research_index.json", {})
    company_documents = load_json(STATE / "company_documents.json", {"documents": {}})
    financial_series = load_json(STATE / "company_financial_series.json", {"tickers": {}})
    model_inputs = load_json(STATE / "company_intel" / "financial_model_inputs.json", {"companies": {}})
    companies = {}
    for symbol in pilot:
        docs = _indexed_docs(symbol, research_index, company_documents)
        financial_docs = [doc for doc in docs if doc.get("classification") in {"financial_results", "financial_statement", "financial_results_notice"}]
        annual_slots = _annual_slots(financial_docs)
        model_row = (model_inputs.get("companies") or {}).get(symbol) or {}
        missing = _missing_matrix(annual_slots, model_row)
        candidates = _top_candidates(financial_docs)
        status = "queued_for_qualification" if candidates and any(row["missing_metrics"] for row in missing) else "blocked_no_candidate_documents" if any(row["missing_metrics"] for row in missing) else "complete"
        companies[symbol] = {
            "symbol": symbol,
            "status": status,
            "classification": "financial_results_coverage",
            "indexed_official_financial_doc_count": len(financial_docs),
            "indexed_official_financial_docs": financial_docs[:20],
            "required_annual_periods": annual_slots,
            "missing_revenue_pat_eps_by_annual_period": missing,
            "model_readiness": {
                "status": model_row.get("status") or "unknown",
                "model_version": model_row.get("model_version"),
                "downstream_status": {
                    "forecast": "blocked_not_implemented",
                    "valuation": "blocked_not_implemented",
                },
                "quality_flags": model_row.get("quality_flags") or [],
            },
            "audit_only_series": _audit_coverage(symbol, financial_series),
            "qualification_queue": {
                "status": "needs_owner_approved_bounded_restage" if candidates else "blocked_no_candidate_documents",
                "queue_id": _stable_id("finqual", symbol, annual_slots[0].get("period_end") or annual_slots[0].get("slot")),
                "candidate_documents": candidates,
            },
            "limitations": [
                "PDFs were not parsed.",
                "Audit-only facts were not promoted.",
                "Revenue, PAT, and EPS values were not inferred.",
                "Forecast and valuation remain blocked.",
            ],
        }
    result = {
        "schema_version": 1,
        "coverage_version": "financial_coverage_v1",
        "pilot_symbols": pilot,
        "source": {
            "research_index": "state/research_index.json",
            "company_documents": "state/company_documents.json",
            "company_financial_series": "state/company_financial_series.json",
            "financial_model_inputs": "state/company_intel/financial_model_inputs.json",
        },
        "policy": {
            "research_only": True,
            "metadata_only": True,
            "no_pdf_parsing": True,
            "no_audit_only_promotion": True,
            "no_value_inference": True,
            "forecast": "blocked_not_implemented",
            "valuation": "blocked_not_implemented",
        },
        "summary": {
            "company_count": len(companies),
            "queued_company_count": sum(1 for row in companies.values() if row.get("status") == "queued_for_qualification"),
        },
        "companies": companies,
    }
    save_json(OUT, result)
    print(f"financial_coverage: {len(companies)} companies, {result['summary']['queued_company_count']} queued")
    return result


if __name__ == "__main__":
    build()
