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
    if receipt.get("live_verification_status") == "verified":
        proof = receipt.get("live_verification_receipt")
        if not isinstance(proof, dict):
            fail("verified live storage requires a live_verification_receipt object")
        required_fields = {
            "verified_at",
            "owner_crud_smoke_test",
            "cross_user_rls_smoke_test",
            "security_advisors_reviewed",
        }
        if set(proof) != required_fields:
            fail("live_verification_receipt fields drifted")
        if not isinstance(proof.get("verified_at"), str) or not ISO_UTC.fullmatch(proof["verified_at"]):
            fail("live verification timestamp must be UTC")
        if proof.get("owner_crud_smoke_test") is not True:
            fail("owner CRUD smoke test was not confirmed")
        if proof.get("cross_user_rls_smoke_test") is not True:
            fail("cross-user RLS smoke test was not confirmed")
        if proof.get("security_advisors_reviewed") is not True:
            fail("Supabase security advisors must be reviewed before live verification")
    else:
        if "live_verification_receipt" in receipt:
            fail("unverified live storage cannot include a live_verification_receipt")
    _assert_no_secrets(receipt)
    print(f"private thesis storage receipt: PASS ({receipt['schema_status']}, live {receipt['live_verification_status']})")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"private thesis storage receipt: FAIL {exc}")
        sys.exit(1)
