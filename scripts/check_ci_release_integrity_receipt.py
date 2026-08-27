#!/usr/bin/env python3
"""Validate the local Company Intelligence release-integrity receipt.

This checker is deliberately offline.  It verifies that a retained receipt has
the fields needed to prove GitHub, preview, production and auth smoke evidence
for one exact commit, but it does not call those services and does not invent a
passing deployment proof.
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psx_data import ROOT, load_json, save_json


RECEIPT = ROOT / "state" / "company_intel" / "release_integrity_receipt.json"
SCHEMA_VERSION = 1
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
HTTPS_URL = re.compile(r"^https://[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*$")

REQUIRED_EVIDENCE_KEYS = (
    "github_ci",
    "preview_deployment",
    "production_deployment",
    "public_login_smoke",
    "owner_private_data_smoke",
    "non_owner_private_data_smoke",
)

FORBIDDEN_PATTERNS = (
    re.compile(r"\bauthorization\b", re.I),
    re.compile(r"\bbearer\b", re.I),
    re.compile(r"\bapikey\b", re.I),
    re.compile(r"\bservice[_ -]?role\b", re.I),
    re.compile(r"\bsb_secret_", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.", re.I),
)


def fail(message: str) -> None:
    raise AssertionError(message)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_strings(item))
        return out
    return []


def _assert_no_secrets(receipt: dict[str, Any]) -> None:
    for value in _strings(receipt):
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(value):
                fail("release receipt contains forbidden credential-like text")


def _without_integrity_envelope(receipt: dict[str, Any]) -> dict[str, Any]:
    """Keep release evidence separate from the finalizer's root metadata."""
    payload = copy.deepcopy(receipt)
    envelope = payload.pop("_meta", None)
    if envelope is not None and not isinstance(envelope, dict):
        fail("release receipt integrity envelope must be an object")
    return payload


def _assert_utc(value: Any, label: str) -> None:
    if not isinstance(value, str) or not UTC_Z.fullmatch(value):
        fail(f"{label} must be an explicit UTC timestamp")


def _assert_commit(value: Any, label: str) -> str:
    if not isinstance(value, str) or not COMMIT_SHA.fullmatch(value):
        fail(f"{label} must be a full 40-character commit SHA")
    return value


def _assert_url(value: Any, label: str) -> None:
    if not isinstance(value, str) or not HTTPS_URL.fullmatch(value):
        fail(f"{label} must be an https URL")


def _status_is_success(evidence: dict[str, Any]) -> bool:
    if evidence["github_ci"].get("status") != "success":
        return False
    if evidence["preview_deployment"].get("status") != "ready":
        return False
    if evidence["production_deployment"].get("status") != "ready":
        return False
    if evidence["public_login_smoke"].get("status") != "passed":
        return False
    owner = evidence["owner_private_data_smoke"]
    if owner.get("status") != "passed" or owner.get("http_status") != 200:
        return False
    non_owner = evidence["non_owner_private_data_smoke"]
    if non_owner.get("status") != "passed" or non_owner.get("http_status") != 403:
        return False
    return True


def _assert_evidence(receipt: dict[str, Any], release_sha: str) -> bool:
    evidence = receipt.get("required_evidence")
    if not isinstance(evidence, dict):
        fail("required_evidence must be an object")
    if tuple(evidence.keys()) != REQUIRED_EVIDENCE_KEYS:
        fail("required_evidence fields drifted")

    github = evidence["github_ci"]
    if not isinstance(github, dict) or set(github) != {"status", "commit_sha", "workflow", "run_id", "checked_at"}:
        fail("github_ci evidence fields drifted")
    if github.get("status") not in {"missing", "success", "failed"}:
        fail("github_ci status is invalid")
    if github.get("commit_sha") is not None and _assert_commit(github.get("commit_sha"), "github_ci.commit_sha") != release_sha:
        fail("github_ci commit does not match release commit")
    if not (github.get("workflow") is None or isinstance(github.get("workflow"), str)):
        fail("github_ci.workflow must be a string or null")
    if not (github.get("run_id") is None or isinstance(github.get("run_id"), str)):
        fail("github_ci.run_id must be a string or null")
    if github.get("checked_at") is not None:
        _assert_utc(github.get("checked_at"), "github_ci.checked_at")

    for name in ("preview_deployment", "production_deployment"):
        row = evidence[name]
        if not isinstance(row, dict) or set(row) != {"status", "url", "commit_sha", "checked_at"}:
            fail(f"{name} evidence fields drifted")
        if row.get("status") not in {"missing", "ready", "failed"}:
            fail(f"{name}.status is invalid")
        if row.get("url") is not None:
            _assert_url(row.get("url"), f"{name}.url")
        if row.get("commit_sha") is not None and _assert_commit(row.get("commit_sha"), f"{name}.commit_sha") != release_sha:
            fail(f"{name} commit does not match release commit")
        if row.get("checked_at") is not None:
            _assert_utc(row.get("checked_at"), f"{name}.checked_at")

    login = evidence["public_login_smoke"]
    if not isinstance(login, dict) or set(login) != {"status", "url", "checked_at"}:
        fail("public_login_smoke evidence fields drifted")
    if login.get("status") not in {"missing", "passed", "failed"}:
        fail("public_login_smoke.status is invalid")
    if login.get("url") is not None:
        _assert_url(login.get("url"), "public_login_smoke.url")
    if login.get("checked_at") is not None:
        _assert_utc(login.get("checked_at"), "public_login_smoke.checked_at")

    owner = evidence["owner_private_data_smoke"]
    if not isinstance(owner, dict) or set(owner) != {"status", "url", "http_status", "checked_at"}:
        fail("owner_private_data_smoke evidence fields drifted")
    if owner.get("status") not in {"missing", "passed", "failed"}:
        fail("owner_private_data_smoke.status is invalid")
    if owner.get("url") is not None:
        _assert_url(owner.get("url"), "owner_private_data_smoke.url")
    if owner.get("http_status") is not None and owner.get("http_status") != 200:
        fail("owner private data smoke must prove HTTP 200")
    if owner.get("checked_at") is not None:
        _assert_utc(owner.get("checked_at"), "owner_private_data_smoke.checked_at")

    non_owner = evidence["non_owner_private_data_smoke"]
    if not isinstance(non_owner, dict) or set(non_owner) != {"status", "url", "http_status", "checked_at"}:
        fail("non_owner_private_data_smoke evidence fields drifted")
    if non_owner.get("status") not in {"missing", "passed", "failed"}:
        fail("non_owner_private_data_smoke.status is invalid")
    if non_owner.get("url") is not None:
        _assert_url(non_owner.get("url"), "non_owner_private_data_smoke.url")
    if non_owner.get("http_status") is not None and non_owner.get("http_status") != 403:
        fail("non-owner private data smoke must prove HTTP 403")
    if non_owner.get("checked_at") is not None:
        _assert_utc(non_owner.get("checked_at"), "non_owner_private_data_smoke.checked_at")

    return _status_is_success(evidence)


def validate(receipt: dict[str, Any]) -> bool:
    if not isinstance(receipt, dict):
        fail("release receipt is not an object")
    receipt = _without_integrity_envelope(receipt)
    expected = {
        "schema_version",
        "kind",
        "release_commit_sha",
        "release_status",
        "recorded_at",
        "local_contract",
        "deployment_proof_boundary",
        "artifact_integrity_manifest_sha256",
        "required_evidence",
    }
    # The CI artifact finalizer stamps every generated JSON with a root
    # ``_meta`` envelope.  It is generation/provenance metadata only; none of
    # its fields may satisfy (or change) the release evidence contract below.
    # Keep the business/release schema exact while allowing that one envelope.
    if set(receipt) - expected - {"_meta"}:
        fail("release receipt top-level fields drifted")
    if "_meta" in receipt and not isinstance(receipt["_meta"], dict):
        fail("release receipt _meta must be an object")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        fail("release receipt schema_version must be 1")
    if receipt.get("kind") != "ci_release_integrity_receipt":
        fail("release receipt kind drifted")
    release_sha = _assert_commit(receipt.get("release_commit_sha"), "release_commit_sha")
    if receipt.get("release_status") not in {"not_verified", "verified"}:
        fail("release_status is invalid")
    _assert_utc(receipt.get("recorded_at"), "recorded_at")
    local = receipt.get("local_contract")
    if not isinstance(local, dict) or set(local) != {
        "artifact_integrity_checked",
        "ordinary_preflight_checked",
        "does_not_prove_deployment",
    }:
        fail("local_contract fields drifted")
    if any(type(local.get(key)) is not bool for key in local):
        fail("local_contract values must be booleans")
    if local.get("does_not_prove_deployment") is not True:
        fail("local contract must clearly say it does not prove deployment")
    boundary = receipt.get("deployment_proof_boundary")
    if not isinstance(boundary, str) or "not verified" not in boundary or "all required evidence" not in boundary:
        fail("deployment proof boundary must fail closed until all evidence is recorded")
    manifest_hash = receipt.get("artifact_integrity_manifest_sha256")
    if manifest_hash is not None and (not isinstance(manifest_hash, str) or not SHA256.fullmatch(manifest_hash)):
        fail("artifact_integrity_manifest_sha256 must be a SHA-256 or null")
    passed = _assert_evidence(receipt, release_sha)
    if (receipt.get("release_status") == "verified") != passed:
        fail("release_status must match the required evidence")
    _assert_no_secrets(receipt)
    return passed


def _missing_receipt(commit_sha: str) -> dict[str, Any]:
    stamp = "2026-08-28T00:00:00Z"
    missing = {
        "status": "missing",
        "commit_sha": None,
        "checked_at": None,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "ci_release_integrity_receipt",
        "release_commit_sha": commit_sha,
        "release_status": "not_verified",
        "recorded_at": stamp,
        "local_contract": {
            "artifact_integrity_checked": False,
            "ordinary_preflight_checked": False,
            "does_not_prove_deployment": True,
        },
        "deployment_proof_boundary": "Release is not verified until all required evidence names this exact commit and passes.",
        "artifact_integrity_manifest_sha256": None,
        "required_evidence": {
            "github_ci": {**missing, "workflow": None, "run_id": None},
            "preview_deployment": dict(missing, url=None),
            "production_deployment": dict(missing, url=None),
            "public_login_smoke": {"status": "missing", "url": None, "checked_at": None},
            "owner_private_data_smoke": {"status": "missing", "url": None, "http_status": None, "checked_at": None},
            "non_owner_private_data_smoke": {"status": "missing", "url": None, "http_status": None, "checked_at": None},
        },
    }


def _passing_receipt(commit_sha: str) -> dict[str, Any]:
    receipt = _missing_receipt(commit_sha)
    receipt["release_status"] = "verified"
    receipt["recorded_at"] = "2026-08-28T12:00:00Z"
    receipt["local_contract"]["artifact_integrity_checked"] = True
    receipt["local_contract"]["ordinary_preflight_checked"] = True
    receipt["artifact_integrity_manifest_sha256"] = "a" * 64
    evidence = receipt["required_evidence"]
    evidence["github_ci"] = {
        "status": "success",
        "commit_sha": commit_sha,
        "workflow": "CI contract",
        "run_id": "123456789",
        "checked_at": "2026-08-28T12:01:00Z",
    }
    evidence["preview_deployment"] = {
        "status": "ready",
        "url": "https://preview-ci-henneth-app.vercel.app",
        "commit_sha": commit_sha,
        "checked_at": "2026-08-28T12:02:00Z",
    }
    evidence["production_deployment"] = {
        "status": "ready",
        "url": "https://ci.henneth.app",
        "commit_sha": commit_sha,
        "checked_at": "2026-08-28T12:03:00Z",
    }
    evidence["public_login_smoke"] = {
        "status": "passed",
        "url": "https://ci.henneth.app",
        "checked_at": "2026-08-28T12:04:00Z",
    }
    evidence["owner_private_data_smoke"] = {
        "status": "passed",
        "url": "https://ci.henneth.app/data/company_intelligence.json",
        "http_status": 200,
        "checked_at": "2026-08-28T12:05:00Z",
    }
    evidence["non_owner_private_data_smoke"] = {
        "status": "passed",
        "url": "https://ci.henneth.app/data/company_intelligence.json",
        "http_status": 403,
        "checked_at": "2026-08-28T12:06:00Z",
    }
    return receipt


def _self_test() -> int:
    commit_sha = "1234567890abcdef1234567890abcdef12345678"
    with tempfile.TemporaryDirectory(prefix="henneth-ci-release-receipt-") as _tmp:
        validate(_missing_receipt(commit_sha))
        validate(_passing_receipt(commit_sha))
        mismatch = _passing_receipt(commit_sha)
        mismatch["required_evidence"]["production_deployment"]["commit_sha"] = "0" * 40
        try:
            validate(mismatch)
        except AssertionError:
            pass
        else:
            print("self-test failed: mismatched production commit was accepted")
            return 1
        wrong_owner = _passing_receipt(commit_sha)
        wrong_owner["required_evidence"]["owner_private_data_smoke"]["http_status"] = 403
        try:
            validate(wrong_owner)
        except AssertionError:
            pass
        else:
            print("self-test failed: owner private-data non-200 was accepted")
            return 1
        false_green = _missing_receipt(commit_sha)
        false_green["release_status"] = "verified"
        try:
            validate(false_green)
        except AssertionError:
            pass
        else:
            print("self-test failed: verified status without evidence was accepted")
            return 1
    print("ci release integrity receipt self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run local fixture checks without touching repo state")
    parser.add_argument("--path", type=Path, default=RECEIPT, help="receipt path to validate")
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test()
    receipt = load_json(args.path, {})
    try:
        verified = validate(receipt)
    except AssertionError as exc:
        print(f"ci release integrity receipt: FAIL {exc}")
        return 1
    status = "verified" if verified else "not_verified"
    print(f"ci release integrity receipt: PASS ({status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
