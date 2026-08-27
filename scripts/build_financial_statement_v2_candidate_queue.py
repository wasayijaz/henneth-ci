"""Build a review-only queue of retained annual documents missing v2 parsing.

This is a metadata audit.  It never opens or downloads a PDF, changes the
reprocess allowlist, or emits financial facts.  Only documents whose retained
metadata proves the current transport/provenance limits are eligible.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from build_financial_coverage import _period_from_doc
from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "financial_statement_v2_candidate_queue.json"
PILOT_COUNT = 20
PSX_FILE_CAP = 12 * 1024 * 1024
PSX_PAGE_CAP = 120
ISSUER_FILE_CAP = 50 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
DOC_ID_RE = re.compile(r"^psx:(\d+)$")
PSX_URL_RE = re.compile(r"^https://dps\.psx\.com\.pk/download/document/(\d+)\.pdf$")
ANNUAL_RE = re.compile(r"\b(annual\s+(?:report|accounts?)|year\s+ended|twelve\s+months\s+ended)\b", re.I)
INTERIM_RE = re.compile(r"\b(quarter|quarterly|half[ -]?year|six[ -]?months?|nine[ -]?months?|interim)\b", re.I)
EXCLUDED_RE = re.compile(r"\b(revoked|board\s+meeting|other\s+than\s+financial\s+results|agm|egm|notice)\b", re.I)


def _stable_id(*parts: Any) -> str:
    return "finv2cand_" + hashlib.sha256("\x1f".join(str(p or "") for p in parts).encode("utf-8")).hexdigest()[:20]


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _sha(value: Any) -> str | None:
    value = str(value or "").lower()
    return value if SHA256_RE.fullmatch(value) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _annual_evidence(row: dict[str, Any]) -> tuple[bool, str | None]:
    title = _text(row.get("title") or row.get("digest") or row.get("one_line"))
    if not title or INTERIM_RE.search(title) or EXCLUDED_RE.search(title):
        return False, None
    if not ANNUAL_RE.search(title):
        return False, None
    period = _period_from_doc({"title": title, "doc_type": row.get("doc_type")}, "financial_statement")
    return True, period.get("source") if period else "title"


def _issuer_registry_match(doc_id: str, ticker: str, url: str, registry: dict[str, Any]) -> bool:
    row = (registry.get("tickers") or {}).get(ticker) or {}
    root = _text(row.get("root_domain")).lower().strip(".")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().strip(".")
    if not root or not host or not (host == root or host.endswith("." + root)):
        return False
    matches = [
        link for link in row.get("document_links") or []
        if isinstance(link, dict) and str(link.get("id") or "") == doc_id
        and str(link.get("url") or "") == url
    ]
    return len(matches) == 1


def _parsed_v2(doc_id: str, content_sha256: str, receipts: dict[str, Any]) -> bool:
    facts = []
    # Facts are checked by the caller; receipts are independent retained proof.
    for receipt in receipts.get("receipts") or []:
        if not isinstance(receipt, dict):
            continue
        if (receipt.get("doc_id") == doc_id
                and str(receipt.get("content_sha256") or "").lower() == content_sha256
                and receipt.get("parser_version") == "financial_statement_v2"
                and receipt.get("status") in {"success", "processed_unsupported"}):
            return True
    return False


def _candidate(doc: dict[str, Any], ticker: str, registry: dict[str, Any], receipts: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = _text(doc.get("doc_id") or doc.get("id"))
    title = _text(doc.get("title") or doc.get("digest") or doc.get("one_line"))
    annual, annual_source = _annual_evidence(doc)
    if not annual or str(doc.get("status") or "") != "ready":
        return None
    digest = _sha(doc.get("content_sha256"))
    if not digest:
        return None
    url = _text(doc.get("source_url") or doc.get("url"))
    source = _text(doc.get("source"))
    media = _text(doc.get("media_type") or doc.get("mime_type")).lower()
    receipt = next((r for r in receipts.get("receipts") or [] if isinstance(r, dict)
                    and r.get("doc_id") == doc_id and str(r.get("content_sha256") or "").lower() == digest), {})
    length = _positive_int(doc.get("content_length")) or _positive_int(receipt.get("content_length"))
    pages = _positive_int(doc.get("page_count")) or _positive_int(receipt.get("page_count"))
    reasons = ["retained_ready_document", "annual_title_evidence", "not_parsed_as_financial_statement_v2"]
    if media not in {"application/pdf", "application/x-pdf"}:
        return None
    if source == "PSX DPS":
        match = DOC_ID_RE.fullmatch(doc_id)
        url_match = PSX_URL_RE.fullmatch(url)
        if not match or not url_match or match.group(1) != url_match.group(1):
            return None
        if length is None or length > PSX_FILE_CAP or pages is None or pages > PSX_PAGE_CAP:
            return None
        reasons.extend(["official_psx_provenance", "within_psx_file_cap", "within_psx_page_cap"])
        provenance = "official_psx_dps"
        file_cap, page_cap = PSX_FILE_CAP, PSX_PAGE_CAP
    elif source == "Issuer website":
        if not doc_id.startswith("issuer:") or not url.startswith("https://") or not url.lower().endswith(".pdf"):
            return None
        if not _issuer_registry_match(doc_id, ticker, url, registry):
            return None
        if length is None or length > ISSUER_FILE_CAP or pages is None:
            return None
        reasons.extend(["issuer_registry_link_exact", "within_issuer_file_cap", "retained_page_count"])
        provenance = "retained_issuer_registry"
        file_cap, page_cap = ISSUER_FILE_CAP, None
    else:
        return None
    if any(isinstance(f, dict) and f.get("parser_version") == "financial_statement_v2"
           and str(f.get("content_sha256") or "").lower() == digest for f in doc.get("facts") or []):
        return None
    if _parsed_v2(doc_id, digest, receipts):
        return None
    safe_period = _period_from_doc({"title": title, "doc_type": doc.get("doc_type")}, "financial_statement")
    return {
        "candidate_id": _stable_id(doc_id, digest),
        "document_id": doc_id,
        "ticker": ticker,
        "title": title,
        "source": source,
        "provenance": provenance,
        "source_url": url,
        "content_sha256": digest,
        "content_length": length,
        "page_count": pages,
        "media_type": media,
        "published_at": doc.get("published_at"),
        "annual_evidence": annual_source,
        "safe_period": safe_period,
        "limits": {"file_bytes": file_cap, "page_count": page_cap},
        "reason": "retained annual official/issuer document is within current file/page/provenance constraints and is not parsed as financial_statement_v2",
        "reasons": reasons,
        "review_status": "owner_review_required",
    }


def build() -> dict[str, Any]:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    if len(pilot) != PILOT_COUNT or len(set(pilot)) != PILOT_COUNT:
        raise ValueError("candidate queue pilot scope must be exactly 20 unique symbols")
    docs = load_json(STATE / "company_documents.json", {"documents": {}}).get("documents") or {}
    registry = load_json(STATE / "company_intel" / "source_registry.json", {"tickers": {}})
    receipts = load_json(STATE / "company_intel" / "reprocess_receipts.json", {"receipts": []})
    companies: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    for ticker in pilot:
        rows = []
        for doc in docs.values():
            if not isinstance(doc, dict) or ticker not in (doc.get("tickers") or []):
                continue
            row = _candidate(doc, ticker, registry, receipts)
            if row:
                rows.append(row)
        rows.sort(key=lambda item: (item.get("published_at") or "", item["document_id"]), reverse=True)
        companies[ticker] = {"ticker": ticker, "candidate_count": len(rows), "candidates": rows}
        candidates.extend(rows)
    candidates.sort(key=lambda item: (item["ticker"], item["document_id"]))
    result = {
        "schema_version": 1,
        "queue_version": "financial_statement_v2_candidate_queue_v1",
        "pilot_symbols": pilot,
        "source": {
            "company_documents": "state/company_documents.json",
            "source_registry": "state/company_intel/source_registry.json",
            "reprocess_receipts": "state/company_intel/reprocess_receipts.json",
        },
        "policy": {
            "review_only": True,
            "metadata_only": True,
            "no_download": True,
            "no_restage": True,
            "no_pdf_parsing": True,
            "no_ocr_or_cropping": True,
            "no_numeric_facts": True,
            "no_forecasts": True,
            "no_allowlist_change": True,
        },
        "limits": {"psx_file_bytes": PSX_FILE_CAP, "psx_page_count": PSX_PAGE_CAP, "issuer_file_bytes": ISSUER_FILE_CAP},
        "summary": {
            "company_count": len(companies),
            "candidate_count": len(candidates),
            "candidate_company_count": sum(1 for row in companies.values() if row["candidate_count"]),
        },
        "companies": companies,
        "candidates": candidates,
    }
    save_json(OUT, result)
    print(f"financial_statement_v2_candidate_queue: {len(candidates)} candidates across {len(companies)} companies")
    return result


if __name__ == "__main__":
    build()
