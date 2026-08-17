#!/usr/bin/env python3
"""Validate and owner-approve evidence-backed CI brief candidates.

Model agents write only ignored candidates. This deterministic gate verifies every statement's
document/page receipt and blocks advice language. ``approve`` is the explicit human checkpoint that
appends a durable receipt and updates the current private brief; it never runs in the cloud pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from psx_data import ROOT, STATE, load_json, save_json

OUT = STATE / "company_briefs.json"
RECEIPTS = STATE / "company_brief_receipts.json"
CANDIDATE_ROOT = (ROOT / ".cache" / "company_intel" / "candidates").resolve()
SECTION_KEYS = ("what_changed", "financial_read", "management_and_capital", "open_questions")
ADVICE_RE = re.compile(
    r"\b(buy|sell|hold|accumulate|reduce|overweight|underweight|price target|target price|"
    r"entry|stop[- ]?loss|take profit|guaranteed|you should|we recommend)\b", re.I,
)


class CandidateError(ValueError):
    pass


def _candidate_path(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(CANDIDATE_ROOT) or path.suffix.lower() != ".json":
        raise CandidateError("candidate must be a JSON file inside .cache/company_intel/candidates")
    return path


def _evidence_pages(doc: dict[str, Any]) -> set[int]:
    pages: set[int] = set()
    for item in (doc.get("evidence") or []):
        if isinstance(item.get("page"), int):
            pages.add(item["page"])
    for row in (doc.get("events") or []) + (doc.get("facts") or []):
        for item in row.get("evidence") or []:
            if isinstance(item.get("page"), int):
                pages.add(item["page"])
    return pages


def validate(candidate: dict[str, Any], documents_state: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    documents = (documents_state or load_json(STATE / "company_documents.json", {})).get("documents") or {}
    ticker = str(candidate.get("ticker") or "").strip().upper()
    if candidate.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not ticker:
        errors.append("ticker is required")
    based_on = candidate.get("based_on")
    if not isinstance(based_on, list) or not based_on:
        errors.append("based_on must contain at least one document receipt")
        based_on = []
    allowed_docs: dict[str, dict[str, Any]] = {}
    for receipt in based_on:
        doc_id = receipt.get("doc_id") if isinstance(receipt, dict) else None
        doc = documents.get(doc_id) or {}
        if not doc or doc.get("status") != "ready":
            errors.append(f"{doc_id or 'unknown'} is not a ready document")
            continue
        if ticker not in (doc.get("tickers") or []):
            errors.append(f"{doc_id} does not belong to {ticker}")
        if receipt.get("content_sha256") != doc.get("content_sha256"):
            errors.append(f"{doc_id} content hash does not match the durable receipt")
        allowed_docs[doc_id] = doc
    headline = str(candidate.get("headline") or "").strip()
    if not headline or len(headline) > 180:
        errors.append("headline is required and must be at most 180 characters")
    if ADVICE_RE.search(headline):
        errors.append("headline contains prohibited advice language")
    sections = candidate.get("sections")
    if not isinstance(sections, dict):
        errors.append("sections must be an object")
        sections = {}
    for key in SECTION_KEYS:
        rows = sections.get(key, [])
        if not isinstance(rows, list):
            errors.append(f"sections.{key} must be a list")
            continue
        for index, row in enumerate(rows):
            text = str(row.get("text") or "").strip() if isinstance(row, dict) else ""
            refs = row.get("evidence") if isinstance(row, dict) else None
            label = f"sections.{key}[{index}]"
            if not text:
                errors.append(f"{label} text is required")
            elif ADVICE_RE.search(text):
                errors.append(f"{label} contains prohibited advice language")
            if not isinstance(refs, list) or not refs:
                errors.append(f"{label} requires document/page evidence")
                continue
            for ref in refs:
                doc_id = ref.get("doc_id") if isinstance(ref, dict) else None
                page = ref.get("page") if isinstance(ref, dict) else None
                doc = allowed_docs.get(doc_id)
                if not doc:
                    errors.append(f"{label} cites an unapproved document {doc_id}")
                elif not isinstance(page, int) or page not in _evidence_pages(doc):
                    errors.append(f"{label} cites unavailable page evidence {doc_id}:{page}")
    limitations = candidate.get("limitations") or []
    if not isinstance(limitations, list):
        errors.append("limitations must be a list")
    else:
        for index, limitation in enumerate(limitations):
            if not str(limitation or "").strip():
                errors.append(f"limitations[{index}] is empty")
            elif ADVICE_RE.search(str(limitation)):
                errors.append(f"limitations[{index}] contains prohibited advice language")
    if len(json.dumps(candidate, ensure_ascii=False).split()) > 650:
        errors.append("candidate exceeds the bounded training size")
    return errors


def _candidate_id(candidate: dict[str, Any]) -> str:
    canonical = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "brief_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def approve(candidate: dict[str, Any]) -> str:
    errors = validate(candidate)
    if errors:
        raise CandidateError("; ".join(errors))
    verification_path = candidate.pop("_verification_path", None)
    candidate_name = candidate.pop("_candidate_name", None)
    if not verification_path:
        raise CandidateError("a clean verifier receipt is required before approval")
    verification = json.loads(Path(verification_path).read_text(encoding="utf-8"))
    if verification.get("verdict") != "clean":
        raise CandidateError("verifier verdict is not clean")
    if not verification.get("candidate"):
        raise CandidateError("verifier receipt does not identify its candidate")
    if candidate_name and verification.get("candidate") != candidate_name:
        raise CandidateError("verifier receipt names a different candidate")
    brief_id = _candidate_id(candidate)
    now = time.strftime("%Y-%m-%d %H:%M")
    ticker = candidate["ticker"].upper()
    receipt_state = load_json(RECEIPTS, {"schema_version": 1, "receipts": []})
    receipts = list(receipt_state.get("receipts") or [])
    if any(row.get("brief_id") == brief_id for row in receipts):
        return brief_id
    approved = {**candidate, "brief_id": brief_id, "status": "owner_approved",
                "approved_at": now, "verification": verification}
    briefs_state = load_json(OUT, {"schema_version": 1, "companies": {}})
    companies = dict(briefs_state.get("companies") or {})
    company = dict(companies.get(ticker) or {"history": []})
    history = list(company.get("history") or [])
    prior = company.get("current")
    if prior and prior.get("brief_id") != brief_id:
        history.append(prior)
    company.update({"current": approved, "history": history})
    companies[ticker] = company
    receipts.append({"receipt_id": "approve_" + brief_id, "brief_id": brief_id,
                     "ticker": ticker, "approved_at": now,
                     "based_on": candidate.get("based_on") or []})
    save_json(OUT, {"schema_version": 1, "companies": companies, "updated": now})
    save_json(RECEIPTS, {"schema_version": 1, "receipts": receipts, "updated": now,
                         "append_only": True})
    return brief_id


def _self_check() -> int:
    doc = {"status": "ready", "tickers": ["FFC"], "content_sha256": "abc",
           "evidence": [{"page": 2, "text": "EPS Rs 12.5", "source_url": "https://example.test/1"}],
           "events": [], "facts": []}
    candidate = {"schema_version": 1, "ticker": "FFC",
                 "based_on": [{"doc_id": "psx:1", "content_sha256": "abc"}],
                 "headline": "Quarterly result disclosed",
                 "sections": {key: [] for key in SECTION_KEYS}, "limitations": []}
    candidate["sections"]["financial_read"] = [
        {"text": "Reported EPS was Rs 12.5.", "evidence": [{"doc_id": "psx:1", "page": 2}]}
    ]
    state = {"documents": {"psx:1": doc}}
    assert not validate(candidate, state)
    bad_page = json.loads(json.dumps(candidate))
    bad_page["sections"]["financial_read"][0]["evidence"][0]["page"] = 9
    assert any("unavailable page" in error for error in validate(bad_page, state))
    advice = json.loads(json.dumps(candidate))
    advice["headline"] = "You should buy FFC"
    assert any("advice" in error for error in validate(advice, state))
    print("company brief review self-check: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate", "approve", "self-check"))
    parser.add_argument("candidate", nargs="?")
    parser.add_argument("--verification", help="clean verifier JSON; required for approve")
    parser.add_argument("--owner-confirmed", action="store_true",
                        help="required acknowledgement that the owner approved this exact candidate")
    args = parser.parse_args(argv)
    if args.action == "self-check":
        return _self_check()
    if not args.candidate:
        parser.error("candidate is required for validate/approve")
    try:
        path = _candidate_path(args.candidate)
        candidate = json.loads(path.read_text(encoding="utf-8"))
        if args.action == "validate":
            errors = validate(candidate)
            if errors:
                print("brief candidate: FAIL")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("brief candidate: PASS")
            return 0
        if not args.verification:
            raise CandidateError("--verification is required for approve")
        if not args.owner_confirmed:
            raise CandidateError("--owner-confirmed is required for approve")
        verification = _candidate_path(args.verification)
        candidate["_verification_path"] = str(verification)
        candidate["_candidate_name"] = path.name
        print(f"brief approved: {approve(candidate)}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, CandidateError) as exc:
        print(f"brief candidate: FAIL — {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
