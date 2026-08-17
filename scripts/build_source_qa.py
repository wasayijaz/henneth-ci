#!/usr/bin/env python3
"""Build a compact issuer-source index and explicit source-health flags."""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from psx_data import STATE, load_json, save_json

OUT = STATE / "company_source_qa.json"


def _source_id(url: str) -> str:
    parts = urlsplit(str(url))
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    return "src_" + hashlib.sha256(clean.encode("utf-8")).hexdigest()[:24]


def build(input_path: Path = STATE / "company_intel" / "source_registry.json", output_path: Path = OUT) -> dict[str, Any]:
    payload = load_json(input_path, {})
    registry = payload.get("tickers") if isinstance(payload, dict) else {}
    registry = registry if isinstance(registry, dict) else {}
    tickers: dict[str, Any] = {}
    sources: dict[str, Any] = {}
    for ticker, row in sorted(registry.items()):
        if not isinstance(row, dict):
            continue
        pages = row.get("monitored_pages") if isinstance(row.get("monitored_pages"), list) else []
        links = row.get("document_links") if isinstance(row.get("document_links"), list) else []
        flags: list[str] = []
        status = str(row.get("status") or "unknown")
        if status not in {"ok", "healthy"}:
            flags.append("registry_degraded")
        if not row.get("issuer_url"):
            flags.append("missing_issuer_url")
        page_rows = []
        for page in pages:
            if not isinstance(page, dict) or not page.get("url"):
                continue
            page_status = str(page.get("status") or "unknown")
            if page_status not in {"ok", "healthy", "not_modified"}:
                flags.append("page_degraded")
            source = {"source_id": _source_id(page["url"]), "ticker": str(ticker).upper(),
                      "url": page["url"], "kind": page.get("kind") or "issuer_page",
                      "label": page.get("label"), "status": page_status,
                      "content_sha256": page.get("content_sha256"),
                      "content_length": page.get("content_length"),
                      "first_seen_at": page.get("first_seen_at"),
                      "last_changed_at": page.get("last_changed_at"),
                      "error": page.get("error")}
            sources[source["source_id"]] = source
            page_rows.append(source["source_id"])
        link_rows = []
        for link in links:
            if not isinstance(link, dict) or not link.get("url"):
                continue
            source = {"source_id": _source_id(link["url"]), "ticker": str(ticker).upper(),
                      "url": link["url"], "kind": link.get("document_type") or "issuer_document",
                      "label": link.get("label"), "status": link.get("status") or "discovered",
                      "source_page": link.get("source_page"),
                      "first_seen_at": link.get("first_seen_at"),
                      "last_seen_at": link.get("last_seen_at"), "error": link.get("error")}
            sources[source["source_id"]] = source
            link_rows.append(source["source_id"])
        if not pages:
            flags.append("missing_monitored_page")
        if not links:
            flags.append("no_document_links")
        tickers[str(ticker).upper()] = {
            "ticker": str(ticker).upper(), "issuer_url": row.get("issuer_url"),
            "registry_status": status, "source_ids": page_rows + link_rows,
            "monitored_page_count": len(page_rows), "document_link_count": len(link_rows),
            "quality_flags": sorted(set(flags)),
            "missing_required_source": not bool(row.get("issuer_url")) or not bool(page_rows),
        }
    previous = load_json(output_path, {}) if output_path.exists() else {}
    out = {"schema_version": 1, "tickers": tickers,
           "sources": {key: sources[key] for key in sorted(sources)},
           "_meta": {"updated": time.strftime("%Y-%m-%d %H:%M"),
                     "source": "state/company_intel/source_registry.json",
                     "ticker_count": len(tickers), "source_count": len(sources),
                     "note": "Index contains URLs and validators only; no issuer page bodies are persisted."}}
    previous_compare = dict(previous) if isinstance(previous, dict) else {}
    previous_meta = dict(previous_compare.get("_meta") or {})
    current_compare = dict(out)
    current_meta = dict(current_compare.get("_meta") or {})
    previous_meta.pop("updated", None)
    current_meta.pop("updated", None)
    previous_compare["_meta"] = previous_meta
    current_compare["_meta"] = current_meta
    if current_compare != previous_compare:
        save_json(output_path, out)
    else:
        out = previous
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=STATE / "company_intel" / "source_registry.json")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    result = build(args.input, args.output)
    print(f"source_qa: tickers={result['_meta']['ticker_count']} sources={result['_meta']['source_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
