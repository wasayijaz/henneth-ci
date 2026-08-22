#!/usr/bin/env python3
"""Restore a cited official PDF page that evidence compaction removed.

This is a manual repair tool, not a scheduled fetcher. It accepts only an
existing ready PSX DPS document, verifies the downloaded bytes against the
durable content hash, and appends one bounded page excerpt to ``brief_evidence``.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from urllib.parse import urlparse

import requests

from document_extract import evidence_for
from psx_data import STATE, load_json, save_json

OUT = STATE / "company_documents.json"
MAX_PDF_BYTES = 12 * 1024 * 1024
ALLOWED_HOST = "dps.psx.com.pk"


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or not parsed.path.startswith("/download/document/"):
        raise ValueError("brief evidence repair accepts official PSX DPS document URLs only")


def _download(url: str) -> bytes:
    _validate_url(url)
    response = requests.get(url, timeout=(10, 35), stream=True, allow_redirects=False,
                            headers={"User-Agent": "HennethDesk/2.CI.0 evidence-repair"})
    response.raise_for_status()
    declared = response.headers.get("content-length")
    if declared and int(declared) > MAX_PDF_BYTES:
        raise ValueError("official PDF exceeds size limit")
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(65536):
        if not chunk:
            continue
        size += len(chunk)
        if size > MAX_PDF_BYTES:
            raise ValueError("official PDF exceeds size limit")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body.startswith(b"%PDF-"):
        raise ValueError("official URL did not return a PDF")
    return body


def restore(doc_id: str, page: int, term: str, path=OUT) -> bool:
    payload = load_json(path, {"documents": {}})
    documents = payload.get("documents") or {}
    doc = documents.get(doc_id) or {}
    if doc.get("status") != "ready" or not doc.get("content_sha256"):
        raise ValueError(f"{doc_id} is not a ready durable document")
    body = _download(str(doc.get("source_url") or ""))
    actual_hash = hashlib.sha256(body).hexdigest()
    if actual_hash != doc.get("content_sha256"):
        raise ValueError("downloaded PDF hash does not match the durable document receipt")
    import pymupdf
    with pymupdf.open(stream=body, filetype="pdf") as pdf:
        pages = [re.sub(r"\s+", " ", item.get_text("text")).strip() for item in pdf]
    if page < 1 or page > len(pages):
        raise ValueError("requested evidence page is outside the official PDF")
    evidence = evidence_for(term, [pages[page - 1]])
    if not evidence:
        raise ValueError("requested term was not found on the cited page")
    evidence["page"] = page
    retained = list(doc.get("brief_evidence") or [])
    key = (page, actual_hash)
    if key in {(row.get("page"), row.get("content_sha256")) for row in retained}:
        return False
    retained.append({**evidence, "source_url": doc.get("source_url"),
                     "content_sha256": actual_hash,
                     "retained_reason": "owner-approved brief citation"})
    documents[doc_id] = {**doc, "brief_evidence": retained}
    save_json(path, {**payload, "documents": documents})
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("doc_id", nargs="?")
    parser.add_argument("--page", type=int)
    parser.add_argument("--term", help="regex that must occur on the cited page")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_check:
        _validate_url("https://dps.psx.com.pk/download/document/1.pdf")
        for unsafe in ("http://dps.psx.com.pk/download/document/1.pdf",
                       "https://example.com/download/document/1.pdf",
                       "https://dps.psx.com.pk/company/1"):
            try:
                _validate_url(unsafe)
                print("brief evidence self-check: FAIL")
                return 1
            except ValueError:
                pass
        print("brief evidence self-check: PASS")
        return 0
    if not args.doc_id or not args.page or not args.term:
        parser.error("doc_id, --page and --term are required unless --self-check is used")
    try:
        changed = restore(args.doc_id, args.page, args.term)
        print(f"brief evidence: {'restored' if changed else 'already retained'} {args.doc_id} page {args.page}")
        return 0
    except (OSError, ValueError, requests.RequestException) as exc:
        print(f"brief evidence: FAIL — {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
