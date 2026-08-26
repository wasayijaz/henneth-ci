#!/usr/bin/env python3
"""Focused local checks for scripts/supabase_ci_store.py."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import supabase_ci_store as store
from psx_data import save_json


SECRET = "sb_secret_this_must_never_be_logged"
FIXED_NOW = "2026-08-27T00:00:00Z"


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post_json(self, url: str, headers: dict[str, str], rows: list[dict[str, Any]]) -> int:
        self.calls.append({"kind": "json", "url": url, "headers": dict(headers), "rows": json.loads(json.dumps(rows))})
        return 201

    def upload_storage(self, url: str, headers: dict[str, str], body: bytes) -> int:
        self.calls.append({"kind": "storage", "url": url, "headers": dict(headers), "body": body})
        return 201


def fail(message: str) -> None:
    raise AssertionError(message)


def sample_root(with_blob: bool = False) -> tempfile.TemporaryDirectory[str]:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    state = root / "state"
    docs = {
        "schema_version": 1,
        "documents": {
            "psx:1": {
                "doc_id": "psx:1",
                "tickers": ["LUCK", "MLCF"],
                "title": "Annual report",
                "doc_type": "results",
                "status": "ready",
                "source": "PSX DPS",
                "source_url": "https://dps.psx.com.pk/download/document/1.pdf",
                "content_sha256": "a" * 64,
                "available_on": "2026-08-01T09:00:00+05:00",
                "published_at": "2026-08-01T09:00:00+05:00",
            },
            "psx:bad": {
                "doc_id": "psx:bad",
                "tickers": ["LUCK"],
                "status": "ready",
                "source_url": "https://dps.psx.com.pk/download/document/bad.pdf",
                "content_sha256": "not-a-sha",
                "available_on": "2026-08-01",
            },
        },
    }
    series = {
        "schema_version": 1,
        "tickers": {
            "LUCK": {
                "facts": [
                    {
                        "ticker": "LUCK",
                        "series_id": "series_1",
                        "document_id": "psx:1",
                        "metric": "basic_eps",
                        "period_end": "2026-06-30",
                        "normalized_value": 12.34,
                        "source_url": "https://dps.psx.com.pk/download/document/1.pdf",
                        "content_sha256": "a" * 64,
                        "evidence": [
                            {
                                "document_id": "psx:1",
                                "source_url": "https://dps.psx.com.pk/download/document/1.pdf",
                                "content_sha256": "a" * 64,
                                "page": 3,
                                "text": "EPS line",
                            }
                        ],
                    },
                    {
                        "ticker": "LUCK",
                        "series_id": "series_bad",
                        "document_id": "psx:1",
                        "metric": "revenue",
                        "source_url": "https://dps.psx.com.pk/download/document/1.pdf",
                        "content_sha256": "a" * 64,
                        "evidence": [{"text": "missing page"}],
                    },
                ]
            }
        },
    }
    operating = {
        "schema_version": 1,
        "as_of": "2026-08-02",
        "companies": {
            "LUCK": {
                "events": [
                    {
                        "event_id": "evt_1",
                        "symbol": "LUCK",
                        "event_type": "management_change",
                        "detected_at": "2026-08-02T10:00:00+05:00",
                        "evidence": [
                            {
                                "document_id": "psx:1",
                                "source": "PSX DPS",
                                "source_url": "https://dps.psx.com.pk/download/document/1.pdf",
                                "content_sha256": "a" * 64,
                                "evidence_sha256": "d" * 64,
                                "page": 9,
                                "text": "board changed",
                            }
                        ],
                    }
                ]
            }
        },
    }
    if with_blob:
        raw_dir = root / ".cache" / "company_intel" / "raw"
        raw_dir.mkdir(parents=True)
        pdf_body = b"%PDF-1.7\nfixture official filing bytes\n%%EOF\n"
        pdf_path = raw_dir / "psx_1.pdf"
        pdf_path.write_bytes(pdf_body)
        save_json(root / ".cache" / "company_intel" / "extraction_queue.json", {
            "schema_version": 1,
            "documents": [{
                "doc_id": "psx:1",
                "path": str(pdf_path),
                "sha256": "ignored-by-archive-which-rehashes-bytes",
                "content_length": len(pdf_body),
                "mime_type": "application/pdf",
            }],
        })
    save_json(state / "company_documents.json", docs)
    save_json(state / "company_financial_series.json", series)
    save_json(state / "company_intel" / "operating_events.json", operating)
    return tmp


def row_counts(rows: store.ArchiveRows) -> dict[str, int]:
    return {name: len(values) for name, values in rows.as_table_map().items()}


def assert_absent_config_noop() -> None:
    tmp = sample_root()
    try:
        fake = FakeTransport()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = store.run(root=Path(tmp.name), env={}, transport=fake, clock=lambda: FIXED_NOW)
        text = out.getvalue()
        if result["mode"] != "dry-run" or fake.calls:
            fail("missing config must be a dry-run with no transport calls")
        if store.ENV_URL not in text or store.ENV_KEY not in text:
            fail("dry-run output must name the missing config keys")
    finally:
        tmp.cleanup()


def assert_deterministic_archive_rows() -> None:
    tmp = sample_root()
    try:
        first, first_stats = store.build_rows(Path(tmp.name), clock=lambda: FIXED_NOW)
        second, second_stats = store.build_rows(Path(tmp.name), clock=lambda: FIXED_NOW)
        if store.stable_json(first.as_table_map()) != store.stable_json(second.as_table_map()):
            fail("archive rows are not deterministic")
        if first_stats.rows != second_stats.rows or first_stats.rejected != second_stats.rejected:
            fail("stats are not deterministic")
        counts = row_counts(first)
        if not all(counts[name] for name in ("source_documents", "document_facts", "state_snapshots", "sync_runs")):
            fail(f"sample fixture did not produce all archive row classes: {counts}")
    finally:
        tmp.cleanup()


def assert_schema_contract() -> None:
    tmp = sample_root()
    try:
        rows, stats = store.build_rows(Path(tmp.name), clock=lambda: FIXED_NOW)
        if stats.rejected.get("missing_source_sha256") != 1:
            fail("invalid document hash was not rejected")
        if not stats.rejected.get("missing_page"):
            fail("fact without page provenance was not rejected")

        source_keys = {row["document_key"] for row in rows.source_documents}
        if rows.document_blobs:
            fail("blob rows must not be prebuilt before a configured storage upload")
        for row in rows.source_documents:
            expected = {
                "document_key",
                "symbol",
                "source_url",
                "source_system",
                "document_type",
                "title",
                "published_at",
                "available_at",
                "source_sha256",
                "metadata",
            }
            if set(row) != expected:
                fail(f"ci_source_documents row keys drifted: {sorted(row)}")
            if not row["document_key"].startswith("doc_") or not row["source_sha256"]:
                fail("source document row missing stable key or source hash")

        for row in rows.document_facts:
            expected = {
                "fact_key",
                "document_key",
                "symbol",
                "fact_type",
                "fact_payload",
                "available_at",
                "payload_sha256",
            }
            if set(row) != expected:
                fail(f"ci_document_facts row keys drifted: {sorted(row)}")
            if row["document_key"] not in source_keys:
                fail("fact references a document_key that is not posted to ci_source_documents")
            if row["payload_sha256"] != store.digest(row["fact_payload"]):
                fail("fact payload hash drifted")

        for row in rows.state_snapshots:
            expected = {"snapshot_key", "state_name", "symbol", "available_at", "payload", "payload_sha256"}
            if set(row) != expected:
                fail(f"ci_state_snapshots row keys drifted: {sorted(row)}")
            if row["payload_sha256"] != store.digest(row["payload"]):
                fail("snapshot payload hash drifted")

        run = rows.sync_runs[0]
        expected = {"run_key", "producer", "started_at", "completed_at", "status", "payload_sha256", "counts"}
        if set(run) != expected:
            fail(f"ci_sync_runs row keys drifted: {sorted(run)}")
        if run["status"] != "completed":
            fail("ci_sync_runs status must satisfy the deployed completed/running/failed/skipped contract")
        if run["counts"]["source_documents"] != len(rows.source_documents):
            fail("sync run counts do not describe source document rows")
    finally:
        tmp.cleanup()


def assert_actual_postgrest_endpoints() -> None:
    tmp = sample_root()
    try:
        fake = FakeTransport()
        env = {
            store.ENV_URL: "https://example.supabase.co",
            store.ENV_KEY: SECRET,
        }
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = store.run(root=Path(tmp.name), env=env, transport=fake, clock=lambda: FIXED_NOW)
        text = out.getvalue()
        if result["mode"] != "posted" or not fake.calls:
            fail("configured run did not call fake transport")
        seen = [(call["url"].split("/rest/v1/", 1)[1], len(call["rows"])) for call in fake.calls]
        expected_prefixes = [
            "ci_source_documents?on_conflict=document_key",
            "ci_document_blobs?on_conflict=document_key",
            "ci_document_facts?on_conflict=fact_key",
            "ci_state_snapshots?on_conflict=snapshot_key",
            "ci_sync_runs?on_conflict=run_key",
        ]
        actual_prefixes = [url for url, _count in seen]
        if actual_prefixes != [prefix for prefix in expected_prefixes if "ci_document_blobs" not in prefix]:
            fail(f"PostgREST endpoints drifted: {actual_prefixes}")
        for call in fake.calls:
            if call["kind"] != "json":
                continue
            headers = call["headers"]
            if headers.get("apikey") != SECRET or headers.get("Authorization") != "Bearer " + SECRET:
                fail("request headers were not set for Supabase")
            if "resolution=ignore-duplicates" not in headers.get("Prefer", ""):
                fail("append-only duplicate-ignore preference missing")
        if SECRET in text or "Authorization" in text or "apikey" in text:
            fail("secret-bearing request headers leaked into logs")
    finally:
        tmp.cleanup()


def assert_blob_storage_contract() -> None:
    tmp = sample_root(with_blob=True)
    try:
        fake = FakeTransport()
        env = {
            store.ENV_URL: "https://example.supabase.co",
            store.ENV_KEY: SECRET,
        }
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = store.run(root=Path(tmp.name), env=env, transport=fake, clock=lambda: FIXED_NOW)
        if result["mode"] != "posted":
            fail("blob fixture did not execute configured archive run")
        kinds = [call["kind"] for call in fake.calls]
        if kinds[:4] != ["json", "storage", "storage", "json"]:
            fail(f"blob upload order drifted: {kinds}")
        if "ci_source_documents?on_conflict=document_key" not in fake.calls[0]["url"]:
            fail("source documents must be inserted before storage uploads")
        blob_post = fake.calls[3]
        if "ci_document_blobs?on_conflict=document_key" not in blob_post["url"]:
            fail("blob metadata must be inserted after storage uploads")
        storage_calls = fake.calls[1:3]
        blob_rows = blob_post["rows"]
        if len(blob_rows) != 2 or len(storage_calls) != 2:
            fail("two-symbol retained document should archive one blob row per source document")
        expected_body = b"%PDF-1.7\nfixture official filing bytes\n%%EOF\n"
        expected_hash = store.hashlib.sha256(expected_body).hexdigest()
        for call, row in zip(storage_calls, blob_rows):
            if call["body"] != expected_body:
                fail("storage upload body drifted")
            if row["content_sha256"] != expected_hash or row["byte_size"] != len(expected_body):
                fail("blob row did not hash and size the uploaded bytes")
            if row["content_type"] != "application/pdf":
                fail("blob content type must be application/pdf")
            if not row["storage_path"].startswith(f"source-documents/{row['document_key']}/"):
                fail("storage path must be deterministic from document_key")
            if expected_hash not in row["storage_path"]:
                fail("storage path must include the byte hash")
            if not call["url"].endswith("/storage/v1/object/ci-documents/" + row["storage_path"]):
                fail(f"storage endpoint drifted: {call['url']}")
            headers = call["headers"]
            if headers.get("apikey") != SECRET or headers.get("Authorization") != "Bearer " + SECRET:
                fail("storage request headers were not set for Supabase")
            if headers.get("Content-Type") != "application/pdf" or headers.get("x-upsert") != "true":
                fail("storage upload headers drifted")
        if SECRET in out.getvalue() or "Authorization" in out.getvalue() or "apikey" in out.getvalue():
            fail("secret-bearing storage headers leaked into logs")
    finally:
        tmp.cleanup()


def assert_no_local_path_skips_blob_archive() -> None:
    tmp = sample_root(with_blob=False)
    try:
        fake = FakeTransport()
        env = {
            store.ENV_URL: "https://example.supabase.co",
            store.ENV_KEY: SECRET,
        }
        with contextlib.redirect_stdout(io.StringIO()):
            store.run(root=Path(tmp.name), env=env, transport=fake, clock=lambda: FIXED_NOW)
        if any(call["kind"] == "storage" for call in fake.calls):
            fail("missing local PDF path must not trigger a storage upload")
        if any("ci_document_blobs" in call["url"] for call in fake.calls if call["kind"] == "json"):
            fail("missing local PDF path must not insert blob metadata")
    finally:
        tmp.cleanup()


def main() -> None:
    assert_absent_config_noop()
    assert_deterministic_archive_rows()
    assert_schema_contract()
    assert_actual_postgrest_endpoints()
    assert_blob_storage_contract()
    assert_no_local_path_skips_blob_archive()
    print("supabase_ci_store: PASS (dry-run, schema contract, endpoints, blob storage, idempotency, secret-safe logging)")


if __name__ == "__main__":
    main()
