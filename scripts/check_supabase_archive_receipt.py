#!/usr/bin/env python3
"""Fail closed on the public evidence contract for CI archive synchronization."""
from __future__ import annotations

import re
import sys
from typing import Any

from psx_data import ROOT, load_json


RECEIPT = ROOT / "state" / "company_intel" / "supabase_archive_receipt.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")


def fail(message: str) -> None:
    raise AssertionError(message)


def _valid_count_map(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, int) and not isinstance(item, bool) and item >= 0
        for key, item in value.items()
    )


def _valid_http_statuses(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(table, str) and isinstance(statuses, list)
        and all(isinstance(status, int) and not isinstance(status, bool) and 200 <= status < 300 for status in statuses)
        for table, statuses in value.items()
    )


def _check_sync_receipt(item: Any) -> None:
    if not isinstance(item, dict):
        fail("sync receipt is not an object")
    expected = {"run_key", "completed_at", "payload_sha256", "counts", "http_statuses"}
    if set(item) != expected:
        fail(f"sync receipt fields drifted: {sorted(item)}")
    if not isinstance(item["run_key"], str) or not item["run_key"].startswith("run_"):
        fail("sync receipt is missing its stable remote run key")
    if not isinstance(item["completed_at"], str) or not item["completed_at"].endswith("Z"):
        fail("sync receipt completion time must be UTC")
    if not isinstance(item["payload_sha256"], str) or not SHA256.fullmatch(item["payload_sha256"]):
        fail("sync receipt payload hash is invalid")
    if not _valid_count_map(item["counts"]):
        fail("sync receipt counts are invalid")
    if not _valid_http_statuses(item["http_statuses"]):
        fail("sync receipt contains a non-success HTTP status")


def main() -> None:
    receipt = load_json(RECEIPT, {})
    if not isinstance(receipt, dict):
        fail("archive receipt is not an object")
    if not isinstance(receipt.get("schema_version"), int) or receipt["schema_version"] < 1:
        fail("archive receipt schema_version is invalid")
    if not isinstance(receipt.get("project_ref"), str) or not PROJECT_REF.fullmatch(receipt["project_ref"]):
        fail("archive receipt project_ref is invalid")
    status = receipt.get("status")
    if status not in {"configured_not_synced", "synced", "sync_failed"}:
        fail("archive receipt status is invalid")

    serialized = str(receipt)
    if ".supabase.co" in serialized or "sb_secret_" in serialized or "Authorization" in serialized or "apikey" in serialized:
        fail("archive receipt must not retain a server URL, credential, or request header")

    sync_receipts = receipt.get("sync_receipts")
    if status == "configured_not_synced":
        if sync_receipts not in (None, []):
            fail("unsynced archive receipt cannot claim successful sync history")
    elif sync_receipts not in (None, []):
        if not isinstance(sync_receipts, list):
            fail("archive sync history is not a list")
        for item in sync_receipts:
            _check_sync_receipt(item)
        run_keys = [item["run_key"] for item in sync_receipts]
        if len(set(run_keys)) != len(run_keys):
            fail("sync receipt history contains a duplicate run key")
        if receipt.get("latest_sync") != sync_receipts[-1]:
            fail("latest_sync must exactly mirror the newest append-only receipt")
    if status == "synced":
        if not isinstance(sync_receipts, list) or not sync_receipts:
            fail("synced archive receipt needs at least one success receipt")

    attempt = receipt.get("last_attempt")
    if status == "configured_not_synced":
        if attempt is not None:
            fail("configured archive receipt cannot claim an attempted sync")
    else:
        if not isinstance(attempt, dict):
            fail("archive receipt needs a latest-attempt record")
        required = {"run_key", "completed_at", "status", "payload_sha256", "counts"}
        if status == "sync_failed":
            required.add("error_type")
        if set(attempt) != required:
            fail(f"latest-attempt fields drifted: {sorted(attempt)}")
        if attempt.get("status") != ("synced" if status == "synced" else "failed"):
            fail("latest-attempt status does not agree with archive status")
        if not isinstance(attempt.get("run_key"), str) or not attempt["run_key"].startswith("run_"):
            fail("latest attempt is missing its stable run key")
        if not isinstance(attempt.get("completed_at"), str) or not attempt["completed_at"].endswith("Z"):
            fail("latest attempt completion time must be UTC")
        if not isinstance(attempt.get("payload_sha256"), str) or not SHA256.fullmatch(attempt["payload_sha256"]):
            fail("latest attempt payload hash is invalid")
        if not _valid_count_map(attempt.get("counts")):
            fail("latest attempt counts are invalid")
        if status == "sync_failed" and not isinstance(attempt.get("error_type"), str):
            fail("failed archive attempt must retain only an error type")

    print(f"supabase archive receipt: PASS ({status})")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"supabase archive receipt: FAIL {exc}")
        sys.exit(1)
