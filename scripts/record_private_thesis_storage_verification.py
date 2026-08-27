#!/usr/bin/env python3
"""Append a secret-free manual verification receipt for private thesis storage.

This script does not contact Supabase and does not perform the smoke test. It is
only the durable local receipt writer used after the owner manually confirms the
browser CRUD path and cross-user RLS isolation. The receipt stores pass/fail
outcomes only: no account identifiers, endpoints, credentials, or thesis text.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

from psx_data import ROOT, load_json, save_json


RECEIPT = ROOT / "state" / "company_intel" / "private_thesis_storage_receipt.json"
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
OWNER_CRUD_KEYS = ("create", "read", "update", "archive", "restore", "delete")
CROSS_USER_RLS_KEYS = ("read_blocked", "update_blocked", "delete_blocked")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _receipt_id(record: dict[str, Any]) -> str:
    stable = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]
    return f"private_thesis_live_{digest}"


def _record_from_args(args: argparse.Namespace) -> dict[str, Any]:
    verified_at = args.verified_at or _utc_now()
    recorded_at = _utc_now()
    if not ISO_UTC.fullmatch(verified_at):
        raise ValueError("--verified-at must be UTC like 2026-08-27T12:34:56Z")
    owner = {key: bool(getattr(args, f"owner_{key}")) for key in OWNER_CRUD_KEYS}
    cross_user = {key: bool(getattr(args, f"cross_user_{key}")) for key in CROSS_USER_RLS_KEYS}
    passed = all(owner.values()) and all(cross_user.values()) and bool(args.security_advisors_reviewed)
    record = {
        "schema_version": 1,
        "recorded_at": recorded_at,
        "verified_at": verified_at,
        "verification_scope": "manual_owner_browser_and_cross_user_rls_smoke_test",
        "outcome": "passed" if passed else "failed",
        "owner_crud_smoke_test": owner,
        "cross_user_rls_smoke_test": cross_user,
        "security_advisors_reviewed": bool(args.security_advisors_reviewed),
        "stored_evidence": "pass_fail_only_no_identifiers_credentials_or_thesis_contents",
    }
    record["receipt_id"] = _receipt_id(record)
    return record


def _append_receipt(receipt: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(receipt)
    receipts = updated.setdefault("live_verification_receipts", [])
    if not isinstance(receipts, list):
        raise ValueError("live_verification_receipts must be an array")
    existing_ids = [item.get("receipt_id") for item in receipts if isinstance(item, dict)]
    if record["receipt_id"] in existing_ids:
        raise ValueError("this verification receipt is already recorded")
    receipts.append(record)
    updated["live_verification_status"] = "verified" if record.get("outcome") == "passed" else "not_verified"
    updated["live_verification_latest_receipt_id"] = record["receipt_id"]
    return updated


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-at", help="UTC timestamp when the manual smoke test finished")
    parser.add_argument("--dry-run", action="store_true", help="print the generated record without writing the receipt file")
    parser.add_argument("--allow-failed-receipt", action="store_true", help="intentionally append an incomplete/failed verification result")
    parser.add_argument("--self-test", action="store_true", help="run local fixture checks without touching repo state")
    for key in OWNER_CRUD_KEYS:
        parser.add_argument(f"--owner-{key}", action="store_true", help=f"owner browser {key} check passed")
    for key in CROSS_USER_RLS_KEYS:
        parser.add_argument(f"--cross-user-{key.replace('_', '-')}", dest=f"cross_user_{key}", action="store_true", help=f"cross-user RLS {key.replace('_', ' ')} check passed")
    parser.add_argument("--security-advisors-reviewed", action="store_true", help="Supabase security advisors were reviewed after the smoke test")
    return parser


def _self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="henneth-private-thesis-receipt-") as tmp:
        base = {
            "schema_version": 1,
            "live_verification_status": "not_verified",
            "live_verification_receipts": [],
        }
        parser = _build_parser()
        args = parser.parse_args([
            "--verified-at", "2026-08-27T12:34:56Z",
            "--owner-create", "--owner-read", "--owner-update", "--owner-archive", "--owner-restore", "--owner-delete",
            "--cross-user-read-blocked", "--cross-user-update-blocked", "--cross-user-delete-blocked",
            "--security-advisors-reviewed",
        ])
        first = _append_receipt(base, _record_from_args(args))
        if first["live_verification_status"] != "verified" or len(first["live_verification_receipts"]) != 1:
            print("self-test failed: passing receipt did not mark live storage verified")
            return 1
        try:
            _append_receipt(first, first["live_verification_receipts"][0])
        except ValueError:
            pass
        else:
            print("self-test failed: duplicate receipt id was accepted")
            return 1
        failed_args = parser.parse_args(["--verified-at", "2026-08-27T12:34:56Z", "--owner-read"])
        failed = _append_receipt(base, _record_from_args(failed_args))
        if failed["live_verification_status"] != "not_verified" or failed["live_verification_receipts"][0]["outcome"] != "failed":
            print("self-test failed: failed receipt outcome was not preserved")
            return 1
    print("private thesis verification receipt writer self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test()
    receipt = load_json(RECEIPT, {})
    if not isinstance(receipt, dict):
        print("private thesis verification receipt writer: FAIL receipt is not an object")
        return 1
    try:
        record = _record_from_args(args)
        if record["outcome"] != "passed" and not (args.dry_run or args.allow_failed_receipt):
            raise ValueError("failed or incomplete verification receipts require --allow-failed-receipt")
        updated = _append_receipt(receipt, record)
    except ValueError as exc:
        print(f"private thesis verification receipt writer: FAIL {exc}")
        return 1
    if args.dry_run:
        print(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True))
        return 0
    save_json(RECEIPT, updated)
    print(f"private thesis verification receipt appended: {record['receipt_id']} ({record['outcome']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
