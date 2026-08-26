#!/usr/bin/env python3
"""Render exact approved image-only filings for transient manual/vision review only.

This never writes state, receipts, queues or financial facts. It is deliberately
separate from canonical reprocessing: page images and their manifest stay ignored
under .cache until an owner-led, independently verified review is complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import time
from pathlib import Path

import pymupdf
from psx_data import ROOT, STATE, load_json, save_json
from reprocess_company_documents import (APPROVED_WAVE3_ALLOWLIST, RequestsTransport, RunBudget,
    fetch_verified_pdf, load_allowlist, resolve_documents, validate_operator_ids)

REVIEW_ROOT = ROOT / ".cache" / "company_intel" / "manual_review"
ZOOM = 2.0


def _run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4)


def _review_meta(path: Path, ids: list[str]) -> dict:
    payload = load_json(path, {})
    documents = payload.get("documents") if isinstance(payload, dict) else {}
    if set(ids) != set(documents or {}):
        raise ValueError("review manifest must contain exactly the approved document IDs")
    return documents


def stage(ids: list[str], allowlist_path: Path, review_path: Path) -> Path:
    ids = validate_operator_ids(ids)
    allowlist = load_allowlist(allowlist_path)
    docs = resolve_documents(ids, STATE, allowlist)
    review_meta = _review_meta(review_path, ids)
    run = REVIEW_ROOT / _run_id()
    run.mkdir(parents=True, exist_ok=False)
    budget = RunBudget()
    rendered = []
    for doc in docs:
        meta = review_meta[doc.doc_id]
        fetched = fetch_verified_pdf(doc, RequestsTransport(), budget, allow_image_only=True)
        if fetched.content_sha256 != meta.get("content_sha256"):
            raise ValueError(f"{doc.doc_id}: review manifest hash mismatch")
        pages = []
        out = run / doc.doc_id.replace(":", "_")
        out.mkdir()
        with pymupdf.open(stream=fetched.body, filetype="pdf") as pdf:
            for index, page in enumerate(pdf, 1):
                image = out / f"page-{index:03d}.png"
                pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), alpha=False)
                pix.save(image)
                pages.append({"page": index, "path": str(image.relative_to(ROOT)),
                              "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                              "width": pix.width, "height": pix.height})
        rendered.append({"doc_id": doc.doc_id, "symbol": doc.tickers[0], "period_end": meta.get("period"),
                         "source_url": doc.url, "published_at": doc.row.get("published_at"),
                         "available_on": doc.row.get("published_at"), "content_sha256": fetched.content_sha256,
                         "page_count": fetched.page_count, "pages": pages})
    manifest = {"schema_version": 1, "review_mode": "manual_vision_candidate_only", "run_id": run.name,
                "canonical_state_committed": False, "model_loadable_facts_created": False,
                "owner_verification_required": True, "independent_verification_required": True,
                "documents": rendered}
    save_json(run / "review_manifest.json", manifest)
    print(json.dumps({"run": str(run.relative_to(ROOT)), "documents": len(rendered)}, sort_keys=True))
    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", action="append", required=True)
    parser.add_argument("--allowlist-manifest", type=Path, default=ROOT / "config" / "ci_reprocess_allowlist.json")
    parser.add_argument("--review-manifest", type=Path, default=ROOT / "config" / "ci_reprocess_review_manifest.json")
    args = parser.parse_args()
    stage(args.document_id, args.allowlist_manifest, args.review_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
