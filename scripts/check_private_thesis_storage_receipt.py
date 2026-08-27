#!/usr/bin/env python3
"""Validate the secret-free private thesis storage activation receipt.

This checker deliberately distinguishes schema configuration from live storage
proof. A configured SQL table is useful evidence, but it must not complete the
live private-thesis requirement until owner-token CRUD and cross-user RLS have
both been verified outside the repo.
"""
from __future__ import annotations

import re
import sys
from typing import Any

from psx_data import ROOT, load_json


RECEIPT = ROOT / "state" / "company_intel" / "private_thesis_storage_receipt.json"
PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
RECEIPT_ID = re.compile(r"^private_thesis_live_[0-9a-f]{20}$")
OWNER_CRUD_KEYS = ("create", "read", "update", "archive", "restore", "delete")
CROSS_USER_RLS_KEYS = ("read_blocked", "update_blocked", "delete_blocked")
FORBIDDEN_PATTERNS = (
    re.compile(r"https?://", re.I),
    re.compile(r"\.supabase\.co", re.I),
    re.compile(r"\bapikey\b", re.I),
    re.compile(r"\bauthorization\b", re.I),
    re.compile(r"\bbearer\b", re.I),
    re.compile(r"\bsb_secret_", re.I),
    re.compile(r"\bservice[_ -]?role\b", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.", re.I),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I),
)


def fail(message: str) -> None:
    raise AssertionError(message)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_string_values(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_string_values(item))
        return out
    return []


def _assert_no_secrets(receipt: dict[str, Any]) -> None:
    for value in _string_values(receipt):
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(value):
                fail("private thesis receipt contains forbidden secret-like or endpoint-like text")


def _assert_live_receipt(record: Any) -> bool:
    if not isinstance(record, dict):
        fail("live verification receipt entry is not an object")
    expected = {
        "schema_version",
        "receipt_id",
        "recorded_at",
        "verified_at",
        "verification_scope",
        "outcome",
        "owner_crud_smoke_test",
        "cross_user_rls_smoke_test",
        "security_advisors_reviewed",
        "stored_evidence",
    }
    if set(record) != expected:
        fail("live verification receipt fields drifted")
    if record.get("schema_version") != 1:
        fail("live verification receipt schema_version must be 1")
    if not isinstance(record.get("receipt_id"), str) or not RECEIPT_ID.fullmatch(record["receipt_id"]):
        fail("live verification receipt_id is invalid")
    for key in ("recorded_at", "verified_at"):
        if not isinstance(record.get(key), str) or not ISO_UTC.fullmatch(record[key]):
            fail(f"live verification {key} must be UTC")
    if record.get("verification_scope") != "manual_owner_browser_and_cross_user_rls_smoke_test":
        fail("live verification scope drifted")
    if record.get("outcome") not in {"passed", "failed"}:
        fail("live verification outcome is invalid")
    owner = record.get("owner_crud_smoke_test")
    if not isinstance(owner, dict) or tuple(owner.keys()) != OWNER_CRUD_KEYS:
        fail("owner CRUD smoke-test fields drifted")
    cross_user = record.get("cross_user_rls_smoke_test")
    if not isinstance(cross_user, dict) or tuple(cross_user.keys()) != CROSS_USER_RLS_KEYS:
        fail("cross-user RLS smoke-test fields drifted")
    if any(type(value) is not bool for value in owner.values()):
        fail("owner CRUD smoke-test values must be booleans")
    if any(type(value) is not bool for value in cross_user.values()):
        fail("cross-user RLS smoke-test values must be booleans")
    if type(record.get("security_advisors_reviewed")) is not bool:
        fail("security advisor review result must be boolean")
    passed = all(owner.values()) and all(cross_user.values()) and record["security_advisors_reviewed"]
    if (record.get("outcome") == "passed") != passed:
        fail("live verification outcome does not match recorded smoke-test results")
    if record.get("stored_evidence") != "pass_fail_only_no_identifiers_credentials_or_thesis_contents":
        fail("live verification receipt must store pass/fail evidence only")
    return passed


def main() -> None:
    receipt = load_json(RECEIPT, {})
    if not isinstance(receipt, dict):
        fail("private thesis receipt is not an object")
    if receipt.get("schema_version") != 1:
        fail("private thesis receipt schema_version must be 1")
    if not isinstance(receipt.get("project_ref"), str) or not PROJECT_REF.fullmatch(receipt["project_ref"]):
        fail("private thesis receipt project_ref is invalid")
    if receipt.get("table") != "company_theses":
        fail("private thesis receipt table drifted")
    if receipt.get("migration") != "activate_private_company_theses":
        fail("private thesis migration name drifted")
    if not isinstance(receipt.get("schema_configured_at"), str) or not ISO_UTC.fullmatch(receipt["schema_configured_at"]):
        fail("schema_configured_at must be an explicit UTC timestamp")
    if receipt.get("schema_status") != "configured":
        fail("schema_status must be configured")
    if receipt.get("live_verification_status") not in {"not_verified", "verified"}:
        fail("live_verification_status is invalid")
    contracts = receipt.get("offline_contracts")
    if contracts != [
        "docs/company_theses.sql",
        "scripts/record_private_thesis_storage_verification.py",
        "scripts/check_company_theses_security.mjs",
        "scripts/check_company_theses_ui.mjs",
    ]:
        fail("offline contract list drifted")
    security = receipt.get("security_contract")
    if not isinstance(security, dict):
        fail("security_contract is missing")
    if security.get("rls_enabled") is not True or security.get("anon_grants") is not False:
        fail("receipt must retain the RLS/no-anon boundary")
    if security.get("authenticated_grants") != ["select", "insert", "update", "delete"]:
        fail("authenticated grant list drifted")
    if security.get("owner_predicate") != "user_id = auth.uid()":
        fail("owner predicate summary drifted")
    if security.get("service_role_in_browser") is not False:
        fail("receipt must state service role is not in the browser")
    required = receipt.get("live_verification_required")
    if not isinstance(required, list) or len(required) < 4:
        fail("live verification checklist is missing")
    boundary = receipt.get("completion_boundary")
    if not isinstance(boundary, str) or "remains incomplete" not in boundary or "owner-token CRUD" not in boundary:
        fail("completion boundary must keep live storage incomplete until smoke-tested")
    if "live_verification_receipt" in receipt:
        fail("live verification proof must use the append-only live_verification_receipts array")
    receipts = receipt.get("live_verification_receipts")
    if not isinstance(receipts, list):
        fail("live_verification_receipts must be an append-only array")
    seen_ids: set[str] = set()
    latest_passed = False
    latest_id = None
    for record in receipts:
        passed = _assert_live_receipt(record)
        receipt_id = record["receipt_id"]
        if receipt_id in seen_ids:
            fail("duplicate live verification receipt_id")
        seen_ids.add(receipt_id)
        latest_passed = passed
        latest_id = receipt_id
    if receipts:
        if receipt.get("live_verification_latest_receipt_id") != latest_id:
            fail("latest live verification receipt id drifted")
    elif "live_verification_latest_receipt_id" in receipt:
        fail("empty live verification receipt history cannot name a latest receipt")
    expected_live_status = "verified" if latest_passed else "not_verified"
    if receipt.get("live_verification_status") != expected_live_status:
        fail("live_verification_status must match the latest append-only receipt outcome")
    _assert_no_secrets(receipt)
    print(f"private thesis storage receipt: PASS ({receipt['schema_status']}, live {receipt['live_verification_status']})")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"private thesis storage receipt: FAIL {exc}")
        sys.exit(1)
