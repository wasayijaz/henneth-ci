#!/usr/bin/env python3
"""Record secret-free release evidence for Henneth Company Intelligence.

The script appends no remote data by itself and contacts no provider.  It only
updates the local receipt from operator-supplied evidence after GitHub, Vercel
and browser/auth smokes have actually been checked.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_ci_release_integrity_receipt import RECEIPT, validate
from psx_data import ROOT, load_json, save_json


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def current_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=5,
    ).strip().lower()


def manifest_hash() -> str | None:
    path = ROOT / "state" / "company_intel" / "artifact_integrity.json"
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_receipt(commit_sha: str) -> dict[str, Any]:
    missing_commit = {"status": "missing", "commit_sha": None, "checked_at": None}
    return {
        "schema_version": 1,
        "kind": "ci_release_integrity_receipt",
        "release_commit_sha": commit_sha,
        "release_status": "not_verified",
        "recorded_at": utc_now(),
        "local_contract": {
            "artifact_integrity_checked": False,
            "ordinary_preflight_checked": False,
            "does_not_prove_deployment": True,
        },
        "deployment_proof_boundary": "Release is not verified until all required evidence names this exact commit and passes.",
        "artifact_integrity_manifest_sha256": None,
        "required_evidence": {
            "github_ci": {**missing_commit, "workflow": None, "run_id": None},
            "preview_deployment": {**missing_commit, "url": None},
            "production_deployment": {**missing_commit, "url": None},
            "public_login_smoke": {"status": "missing", "url": None, "checked_at": None},
            "owner_private_data_smoke": {"status": "missing", "url": None, "http_status": None, "checked_at": None},
            "non_owner_private_data_smoke": {"status": "missing", "url": None, "http_status": None, "checked_at": None},
        },
    }


def update_receipt(args: argparse.Namespace, receipt_path: Path = RECEIPT) -> dict[str, Any]:
    receipt = load_json(receipt_path, {})
    commit_sha = (args.commit_sha or current_commit()).strip().lower()
    if not isinstance(receipt, dict) or not receipt:
        receipt = base_receipt(commit_sha)
    if receipt.get("release_status") == "verified":
        raise ValueError("release receipt is append-only once verified; do not overwrite deployed proof")
    updated = copy.deepcopy(receipt)
    if updated.get("release_commit_sha") != commit_sha:
        raise ValueError("existing receipt release_commit_sha does not match requested commit")
    updated["recorded_at"] = utc_now()
    if args.artifact_integrity_checked:
        updated["local_contract"]["artifact_integrity_checked"] = True
        updated["artifact_integrity_manifest_sha256"] = manifest_hash()
    if args.ordinary_preflight_checked:
        updated["local_contract"]["ordinary_preflight_checked"] = True
    evidence = updated["required_evidence"]
    checked_at = args.checked_at or utc_now()
    if args.github_ci_success:
        evidence["github_ci"] = {
            "status": "success",
            "commit_sha": commit_sha,
            "workflow": args.github_workflow,
            "run_id": args.github_run_id,
            "checked_at": checked_at,
        }
    if args.preview_ready:
        evidence["preview_deployment"] = {
            "status": "ready",
            "url": args.preview_url,
            "commit_sha": commit_sha,
            "checked_at": checked_at,
        }
    if args.production_ready:
        evidence["production_deployment"] = {
            "status": "ready",
            "url": args.production_url,
            "commit_sha": commit_sha,
            "checked_at": checked_at,
        }
    if args.public_login_passed:
        evidence["public_login_smoke"] = {
            "status": "passed",
            "url": args.public_login_url,
            "checked_at": checked_at,
        }
    if args.owner_private_data_200:
        evidence["owner_private_data_smoke"] = {
            "status": "passed",
            "url": args.private_data_url,
            "http_status": 200,
            "checked_at": checked_at,
        }
    if args.non_owner_private_data_403:
        evidence["non_owner_private_data_smoke"] = {
            "status": "passed",
            "url": args.private_data_url,
            "http_status": 403,
            "checked_at": checked_at,
        }
    candidate = copy.deepcopy(updated)
    candidate["release_status"] = "verified"
    try:
        verified = validate(candidate)
    except AssertionError:
        verified = False
    if not verified:
        if not args.dry_run:
            raise ValueError("release evidence is incomplete or inconsistent; use --dry-run to inspect without writing")
        updated["release_status"] = "not_verified"
    else:
        updated["release_status"] = "verified"
    validate(updated)
    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit-sha", help="full release commit SHA; defaults to current HEAD")
    parser.add_argument("--checked-at", help="UTC timestamp for supplied checks; defaults to now")
    parser.add_argument("--output", type=Path, help="write a new immutable receipt artifact instead of repository state")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--artifact-integrity-checked", action="store_true")
    parser.add_argument("--ordinary-preflight-checked", action="store_true")
    parser.add_argument("--github-ci-success", action="store_true")
    parser.add_argument("--github-workflow")
    parser.add_argument("--github-run-id")
    parser.add_argument("--preview-ready", action="store_true")
    parser.add_argument("--preview-url")
    parser.add_argument("--production-ready", action="store_true")
    parser.add_argument("--production-url", default="https://ci.henneth.app")
    parser.add_argument("--public-login-passed", action="store_true")
    parser.add_argument("--public-login-url", default="https://ci.henneth.app")
    parser.add_argument("--owner-private-data-200", action="store_true")
    parser.add_argument("--non-owner-private-data-403", action="store_true")
    parser.add_argument("--private-data-url", default="https://ci.henneth.app/data/company_intelligence.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output_path = args.output or RECEIPT
        updated = update_receipt(args, output_path)
    except Exception as exc:
        print(f"ci release integrity receipt recorder: FAIL {exc}")
        return 1
    if args.dry_run:
        print(json.dumps(updated, indent=1, ensure_ascii=True))
        return 0
    save_json(output_path, updated)
    print(f"ci release integrity receipt recorded: {updated['release_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
