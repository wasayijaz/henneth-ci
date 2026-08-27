"""Focused contract checks for the retained v2 candidate queue."""
from __future__ import annotations

import json
import re
from pathlib import Path

from build_financial_statement_v2_candidate_queue import OUT, build, PILOT_COUNT
from psx_data import ROOT, load_json


def fail(message: str) -> None:
    raise AssertionError(message)


def dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def walk(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            p = path + (str(key),)
            yield p, item
            yield from walk(item, p)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, path + (str(index),))


def main() -> int:
    expected = build()
    again = build()
    if dump(expected) != dump(again):
        fail("candidate queue is not deterministic")
    pilot = expected.get("pilot_symbols") or []
    if len(pilot) != PILOT_COUNT or len(set(pilot)) != PILOT_COUNT:
        fail("candidate queue pilot scope must be exactly 20 unique symbols")
    if set((expected.get("companies") or {})) != set(pilot):
        fail("candidate queue company boundary mismatch")
    policy = expected.get("policy") or {}
    for key in ("review_only", "metadata_only", "no_download", "no_restage", "no_pdf_parsing", "no_ocr_or_cropping", "no_numeric_facts", "no_allowlist_change"):
        if policy.get(key) is not True:
            fail(f"missing policy {key}=true")
    for path, value in walk(expected):
        if path[-1] in {"value", "amount", "eps", "revenue", "pat", "normalized_value", "raw_value"}:
            fail(f"numeric fact-like key present at {'.'.join(path)}")
    seen = set()
    for row in expected.get("candidates") or []:
        doc_id = str(row.get("document_id") or "")
        if doc_id in seen:
            fail(f"duplicate candidate {doc_id}")
        seen.add(doc_id)
        if not (doc_id.startswith("psx:") or doc_id.startswith("issuer:")):
            fail(f"unsafe document id {doc_id}")
        if row.get("review_status") != "owner_review_required":
            fail(f"{doc_id}: candidate is not review-only")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("content_sha256") or "")):
            fail(f"{doc_id}: retained content hash missing")
        if not row.get("source_url", "").startswith("https://"):
            fail(f"{doc_id}: source URL missing")
        if not row.get("reasons") or "not_parsed_as_financial_statement_v2" not in row["reasons"]:
            fail(f"{doc_id}: reason missing")
    committed = load_json(OUT, {})
    if dump(committed) != dump(expected):
        fail("committed candidate queue is stale")
    print(f"financial_statement_v2_candidate_queue: PASS ({len(seen)} candidates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
