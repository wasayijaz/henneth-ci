#!/usr/bin/env python3
"""Verify owner-approved brief receipts are reflected in the private CI slice.

The durable queue remains append-only.  This check guards the display/read edge:
an exact owner receipt for ``document_id/doc_id + content_sha256`` marks that
document complete in the generated CI slice; stale or unrelated receipts do not.
"""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import build_ci_slice as ci


def _state_file(root: Path, name: str, payload) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _minimal_state(state: Path) -> None:
    _state_file(state, "company_profiles.json", {
        "source": "fixture",
        "pilot": {"symbols": ["AAA"]},
        "tickers": {
            "AAA": {
                "symbol": "AAA",
                "business_description": "Fixture company.",
                "source_url": "https://issuer.example.test/aaa",
            }
        },
    })
    _state_file(state, "universe.json", {"symbols": {"AAA": {"name": "AAA Limited", "in": []}}})
    _state_file(state, "sectors.json", {"tickers": {"AAA": {"sector": "Cement", "code": "cement"}}})
    _state_file(state, "company_documents.json", {"documents": {
        "psx:1": {
            "doc_id": "psx:1",
            "status": "ready",
            "title": "AAA quarterly result",
            "doc_type": "financial_results",
            "source": "PSX DPS",
            "source_url": "https://dps.psx.com.pk/download/document/1.pdf",
            "published_at": "2026-08-20",
            "content_sha256": "hash-ok",
            "tickers": ["AAA"],
            "evidence": [{"page": 1, "text": "Revenue Rs 10m", "source_url": "https://dps.psx.com.pk/download/document/1.pdf"}],
            "facts": [],
        },
        "psx:2": {
            "doc_id": "psx:2",
            "status": "ready",
            "title": "AAA stale receipt result",
            "doc_type": "financial_results",
            "source": "PSX DPS",
            "source_url": "https://dps.psx.com.pk/download/document/2.pdf",
            "published_at": "2026-08-19",
            "content_sha256": "hash-current",
            "tickers": ["AAA"],
            "evidence": [{"page": 1, "text": "EPS Rs 1", "source_url": "https://dps.psx.com.pk/download/document/2.pdf"}],
            "facts": [],
        },
    }})
    _state_file(state, "document_synthesis_queue.json", {
        "schema_version": 1,
        "queue": [],
        "history": [
            {"queue_id": "qa", "document_id": "psx:1", "content_sha256": "hash-ok",
             "approval_status": "pending", "synthesis_status": "not_started", "training_mode": True},
            {"queue_id": "qb", "doc_id": "psx:2", "content_sha256": "hash-current",
             "approval_status": "pending", "synthesis_status": "not_started", "training_mode": True},
            {"queue_id": "qc", "doc_id": "psx:3", "content_sha256": "hash-missing",
             "approval_status": "pending", "synthesis_status": "not_started", "training_mode": True},
        ],
        "_meta": {"training_mode": True},
    })
    _state_file(state, "company_brief_receipts.json", {
        "schema_version": 1,
        "append_only": True,
        "receipts": [
            {"receipt_id": "approve_fixture", "brief_id": "brief_fixture", "ticker": "AAA",
             "approved_at": "2026-08-22 16:02",
             "based_on": [{"doc_id": "psx:1", "content_sha256": "hash-ok"}]},
            {"receipt_id": "approve_stale", "brief_id": "brief_stale", "ticker": "AAA",
             "approved_at": "2026-08-22 16:03",
             "based_on": [{"document_id": "psx:2", "content_sha256": "old-hash"}]},
        ],
    })


def main() -> int:
    queue = {
        "history": [
            {"document_id": "psx:1", "content_sha256": "hash-ok",
             "approval_status": "pending", "synthesis_status": "not_started", "training_mode": True},
            {"doc_id": "psx:2", "content_sha256": "hash-current",
             "approval_status": "pending", "synthesis_status": "not_started", "training_mode": True},
            {"doc_id": "psx:3", "content_sha256": "hash-missing",
             "approval_status": "pending", "synthesis_status": "not_started", "training_mode": True},
        ]
    }
    receipts = {"receipts": [
        {"receipt_id": "approve_fixture", "brief_id": "brief_fixture",
         "approved_at": "2026-08-22 16:02",
         "based_on": [{"doc_id": "psx:1", "content_sha256": "hash-ok"}]},
        {"receipt_id": "approve_stale", "brief_id": "brief_stale",
         "approved_at": "2026-08-22 16:03",
         "based_on": [{"document_id": "psx:2", "content_sha256": "old-hash"}]},
    ]}
    queue_before = copy.deepcopy(queue)
    receipts_before = copy.deepcopy(receipts)
    status = ci._document_queue_status(queue, receipts)
    assert status[("psx:1", "hash-ok")] == {
        "approval_status": "approved",
        "synthesis_status": "complete",
        "training_mode": True,
        "receipt_id": "approve_fixture",
        "brief_id": "brief_fixture",
        "approved_at": "2026-08-22 16:02",
    }
    assert status[("psx:2", "hash-current")]["approval_status"] == "pending", "hash mismatch was approved"
    assert status[("psx:3", "hash-missing")]["synthesis_status"] == "not_started", "missing receipt changed queue status"
    assert queue == queue_before and receipts == receipts_before, "reconciliation mutated its inputs"

    with tempfile.TemporaryDirectory(prefix="henneth-ci-receipts-") as tmp:
        root = Path(tmp)
        state = root / "state"
        out = root / "ci" / "company_intelligence.json"
        _minimal_state(state)
        original_state = ci.STATE
        original_out = ci.OUT
        original_root = ci.ROOT
        try:
            ci.ROOT = root
            ci.STATE = state
            ci.OUT = out
            ci.build()
        finally:
            ci.ROOT = original_root
            ci.STATE = original_state
            ci.OUT = original_out
        payload = json.loads(out.read_text(encoding="utf-8"))
        row = payload["tickers"][0]
        by_doc = {filing["doc_id"]: filing for filing in row["filings"]}
        approved = by_doc["psx:1"]["synthesis"]
        assert approved["approval_status"] == "approved"
        assert approved["synthesis_status"] == "complete"
        assert approved["training_mode"] is True
        assert approved["receipt_id"] == "approve_fixture"
        assert by_doc["psx:2"]["synthesis"]["approval_status"] == "pending"
        assert row["intelligence"]["pending_synthesis"] == 1
        assert json.loads((state / "document_synthesis_queue.json").read_text(encoding="utf-8"))["history"][0]["approval_status"] == "pending"
        assert json.loads((state / "company_brief_receipts.json").read_text(encoding="utf-8"))["receipts"][0]["receipt_id"] == "approve_fixture"
    print("training receipt reconciliation check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
