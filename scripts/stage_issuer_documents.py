#!/usr/bin/env python3
"""Stage same-domain issuer PDF links for deterministic extraction.

Input is ``state/company_intel/source_registry.json`` from DPS-declared issuer
websites. This script downloads only bounded same-domain PDFs, merges their
metadata into ``state/research_index.json``, and writes the same transient
extraction queue used by the PSX announcement fetcher. It never archives raw
PDFs in git and never calls a browser/model/paid provider.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from psx_data import ROOT, STATE, load_json, save_json

INDEX_PATH = STATE / "research_index.json"
CACHE_ROOT = ROOT / ".cache" / "company_intel"
RAW_DIR = CACHE_ROOT / "raw"
QUEUE_PATH = CACHE_ROOT / "extraction_queue.json"
CACHE_CHECK = CACHE_ROOT / "issuer_document_checks.json"
MAX_DOWNLOADS_PER_RUN = 16
MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_REDIRECTS = 4
LOCAL_CADENCE_DAYS = 7
PKT = timezone(timedelta(hours=5))
UA = {"User-Agent": "Mozilla/5.0 HennethDesk/2.CI.0 issuer-document-stager"}
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_cache_path(doc_id: str) -> Path:
    safe_id = _SAFE_ID_RE.sub("_", doc_id).strip("._")
    if not safe_id:
        raise ValueError("unsafe empty document id")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = (RAW_DIR / f"{safe_id}.pdf").resolve()
    if RAW_DIR.resolve() not in path.parents:
        raise ValueError("cache path escaped producer directory")
    return path


def _validate_pdf_url(url: str, root_domain: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("issuer document URL must be HTTPS")
    host = parsed.hostname.lower().strip(".")
    domain = str(root_domain or "").lower().strip(".")
    if not domain or (host != domain and not host.endswith("." + domain)):
        raise ValueError("issuer document left DPS-declared root domain")
    if not parsed.path.lower().endswith(".pdf"):
        raise ValueError("issuer document is not a PDF link")
    return url


def _schedule_skip(force: bool) -> bool:
    if force or os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return False
    now = datetime.now(PKT)
    return not (now.weekday() == 0 and now.hour == 8 and now.minute < 30)


def _local_cadence_skip(force: bool) -> bool:
    if force or os.environ.get("GITHUB_ACTIONS"):
        return False
    cached = load_json(CACHE_CHECK, {})
    try:
        last = datetime.fromisoformat(cached.get("last_attempt") or "")
    except ValueError:
        return False
    return timedelta(0) <= datetime.now(PKT) - last < timedelta(days=LOCAL_CADENCE_DAYS)


def _fetch_pdf(url: str, root_domain: str, session: requests.Session) -> tuple[bytes, dict]:
    current = _validate_pdf_url(url, root_domain)
    response = None
    for _ in range(MAX_REDIRECTS + 1):
        response = session.get(current, headers=UA, timeout=(10, 35), stream=True, allow_redirects=False)
        if response.is_redirect or response.is_permanent_redirect:
            target = response.headers.get("location")
            if not target:
                raise ValueError("issuer PDF redirect omitted Location")
            current = _validate_pdf_url(urljoin(current, target), root_domain)
            continue
        break
    if response is None:
        raise ValueError("issuer PDF was not fetched")
    response.raise_for_status()
    _validate_pdf_url(response.url, root_domain)
    declared = response.headers.get("content-length")
    if declared and int(declared) > MAX_PDF_BYTES:
        raise ValueError("issuer PDF exceeds size limit")
    chunks = []
    size = 0
    for chunk in response.iter_content(65536):
        if not chunk:
            continue
        size += len(chunk)
        if size > MAX_PDF_BYTES:
            raise ValueError("issuer PDF exceeds size limit")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body.startswith(b"%PDF-"):
        raise ValueError("issuer link did not return a PDF")
    return body, {
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "content_length": len(body),
        "mime_type": "application/pdf",
    }


def _symbols(value: str | None, registry: dict) -> list[str]:
    all_symbols = [str(s).upper() for s in (registry.get("tickers") or {})]
    if not value:
        return sorted(all_symbols)
    requested = [s.strip().upper() for s in value.split(",") if s.strip()]
    known = set(all_symbols)
    return [symbol for symbol in requested if symbol in known]


def _candidate_rows(registry: dict, index: dict, limit: int) -> list[tuple[str, dict, dict]]:
    extracted = load_json(STATE / "company_documents.json", {"documents": {}})
    ready_hashes = {
        doc_id: row.get("content_sha256")
        for doc_id, row in (extracted.get("documents") or {}).items()
        if row.get("status") == "ready" and row.get("content_sha256")
    }
    rows_by_symbol: dict[str, list[tuple[str, dict, dict]]] = {}
    for symbol, row in sorted((registry.get("tickers") or {}).items()):
        root_domain = row.get("root_domain")
        for document in row.get("document_links") or []:
            url = document.get("url")
            doc_id = document.get("id")
            if not url or not doc_id or not str(urlparse(url).path).lower().endswith(".pdf"):
                continue
            prior = (index.get("documents") or {}).get(doc_id) or {}
            if prior.get("content_sha256") and ready_hashes.get(doc_id) == prior.get("content_sha256"):
                continue
            try:
                _validate_pdf_url(url, root_domain)
            except ValueError:
                continue
            rows_by_symbol.setdefault(symbol, []).append((symbol, row, document))
    selected: list[tuple[str, dict, dict]] = []
    while len(selected) < limit and any(rows_by_symbol.values()):
        for symbol in sorted(rows_by_symbol):
            if rows_by_symbol[symbol] and len(selected) < limit:
                selected.append(rows_by_symbol[symbol].pop(0))
    return selected


def _merge_document(index: dict, symbol: str, ticker_row: dict, link: dict, metadata: dict | None = None,
                    error: str | None = None) -> dict:
    doc_id = link["id"]
    prior = (index.get("documents") or {}).get(doc_id) or {}
    row = {
        **prior,
        "id": doc_id,
        "hash": doc_id,
        "source": "Issuer website",
        "source_type": "issuer_document",
        "doc_type": link.get("document_type") or "issuer_document",
        "date": None,
        "published_at": None,
        "first_seen_at": link.get("first_seen_at"),
        "retrieved_at": time.strftime("%Y-%m-%d %H:%M"),
        "tickers": [symbol],
        "company_name": None,
        "title": link.get("label") or link.get("document_type") or "Issuer document",
        "digest": link.get("label") or link.get("document_type") or "Issuer document",
        "digest_level": "headline",
        "claims": prior.get("claims") or [],
        "url": link.get("url"),
        "source_page": link.get("source_page") or ticker_row.get("issuer_url"),
        "official_document_id": None,
        "omissions": prior.get("omissions"),
    }
    if metadata:
        row.update(metadata)
        row["download"] = {"status": "verified", "checked_at": time.strftime("%Y-%m-%d %H:%M"), "error": None}
    elif error:
        row["download"] = {"status": "failed", "checked_at": time.strftime("%Y-%m-%d %H:%M"), "error": error[:140]}
    index.setdefault("documents", {})[doc_id] = row
    item = {
        "hash": doc_id, "source": "issuer_document", "doc_type": row["doc_type"],
        "date": row.get("date"), "published_at": row.get("published_at"),
        "one_line": row["title"][:140], "url": row.get("url"),
    }
    existing = [x for x in ((index.get("by_ticker") or {}).get(symbol) or []) if x.get("hash") != doc_id]
    index.setdefault("by_ticker", {})[symbol] = sorted([item] + existing,
                                                        key=lambda x: (x.get("published_at") or x.get("date") or "", x.get("hash") or ""),
                                                        reverse=True)[:100]
    return row


def _self_check() -> int:
    try:
        _validate_pdf_url("https://reports.example.com/annual.pdf", "example.com")
    except ValueError:
        print("issuer_document stage self-check: FAIL (valid URL rejected)")
        return 1
    try:
        _validate_pdf_url("http://reports.example.com/annual.pdf", "example.com")
        print("issuer_document stage self-check: FAIL")
        return 1
    except ValueError:
        pass
    try:
        _validate_pdf_url("https://evil.test/annual.pdf", "example.com")
        print("issuer_document stage self-check: FAIL")
        return 1
    except ValueError:
        pass
    try:
        _validate_pdf_url("https://evilexample.com/annual.pdf", "example.com")
        print("issuer_document stage self-check: FAIL")
        return 1
    except ValueError:
        pass
    print("issuer_document stage self-check: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", help="comma-separated pilot symbols")
    parser.add_argument("--limit", type=int, default=MAX_DOWNLOADS_PER_RUN)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_check:
        return _self_check()
    if args.limit < 1 or args.limit > MAX_DOWNLOADS_PER_RUN:
        parser.error(f"--limit must be 1..{MAX_DOWNLOADS_PER_RUN}")
    if _schedule_skip(args.force):
        print("issuer_documents: outside the weekly Monday 08:xx PKT cloud window")
        return 0
    if _local_cadence_skip(args.force):
        print(f"issuer_documents: inside {LOCAL_CADENCE_DAYS}d local cadence")
        return 0

    registry = load_json(STATE / "company_intel" / "source_registry.json", {"tickers": {}})
    symbols = set(_symbols(args.symbols, registry))
    scoped = {**registry, "tickers": {s: row for s, row in (registry.get("tickers") or {}).items() if s in symbols}}
    prior_index = load_json(INDEX_PATH, {"documents": {}, "by_ticker": {}, "_meta": {}})
    index = {
        "documents": dict(prior_index.get("documents") or {}),
        "by_ticker": dict(prior_index.get("by_ticker") or {}),
        "_meta": dict(prior_index.get("_meta") or {}),
    }
    selected = _candidate_rows(scoped, index, args.limit)
    queue = []
    verified = failed = 0
    session = requests.Session()
    for symbol, ticker_row, link in selected:
        try:
            metadata = None
            if not args.metadata_only:
                body, metadata = _fetch_pdf(link["url"], ticker_row.get("root_domain"), session)
                path = _safe_cache_path(link["id"])
                path.write_bytes(body)
                queue.append({
                    "doc_id": link["id"], "path": str(path),
                    "sha256": metadata["content_sha256"],
                    "content_length": metadata["content_length"],
                    "mime_type": metadata["mime_type"],
                })
                verified += 1
            _merge_document(index, symbol, ticker_row, link, metadata=metadata)
        except (requests.RequestException, OSError, ValueError) as exc:
            failed += 1
            _merge_document(index, symbol, ticker_row, link, error=f"{type(exc).__name__}:{str(exc)}")
    if index != prior_index:
        index["_meta"] = {
            **index.get("_meta", {}),
            "issuer_documents": sum(1 for doc in index["documents"].values() if doc.get("source") == "Issuer website"),
            "issuer_document_source": "state/company_intel/source_registry.json",
        }
        save_json(INDEX_PATH, index)
    save_json(QUEUE_PATH, {"schema_version": 1, "created_at": time.strftime("%Y-%m-%d %H:%M"), "documents": queue})
    save_json(CACHE_CHECK, {"last_attempt": datetime.now(PKT).isoformat(timespec="seconds"), "failures": failed})
    print(f"issuer_documents: {len(selected)} candidates, {verified} PDFs staged, {failed} failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
