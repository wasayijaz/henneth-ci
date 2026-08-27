#!/usr/bin/env python3
"""Structural guard for the controlled Henneth CI production-release workflow.

This is deliberately offline: it proves the repository contains the guarded
preview-to-promotion path, not that Vercel project settings or secrets are live.
"""
from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci-production-release.yml"


def validate(text: str) -> list[str]:
    required = (
        "workflow_dispatch:",
        "validate:",
        "preview:",
        "promote:",
        "needs: validate",
        "needs: preview",
        "environment: ci-production",
        "check_ci_product_contracts.py",
        "scripts/preflight.py",
        "check_ci_vercel_deployment_commit.py --self-test",
        "check_ci_release_http_smoke.py --base-url \"$PREVIEW_URL\"",
        "check_ci_release_http_smoke.py --base-url https://ci.henneth.app --require-authenticated",
        "vercel@39.1.0 deploy --prebuilt",
        "--meta githubCommitSha=\"$GITHUB_SHA\"",
        "vercel@39.1.0 promote \"$PREVIEW_URL\"",
        "Verify preview is bound to this commit",
        "check_ci_vercel_deployment_commit.py --deployment-url \"$PREVIEW_URL\" --commit-sha \"$GITHUB_SHA\"",
        "PREVIEW_DEPLOYMENT_ID: ${{ needs.preview.outputs.deployment_id }}",
        "Verify production is the promoted preview",
        "check_ci_vercel_deployment_commit.py --deployment-url https://ci.henneth.app --commit-sha \"$GITHUB_SHA\" --expected-deployment-id \"$PREVIEW_DEPLOYMENT_ID\"",
        "scripts/record_ci_release_integrity_receipt.py",
        "actions/upload-artifact@v4",
        "secrets.VERCEL_TOKEN",
        "secrets.VERCEL_ORG_ID",
        "secrets.VERCEL_CI_PROJECT_ID",
        "secrets.HENNETH_CI_OWNER_SMOKE_TOKEN",
        "secrets.HENNETH_CI_NON_OWNER_SMOKE_TOKEN",
    )
    return [f"missing release workflow contract: {needle}" for needle in required if needle not in text]


def self_test() -> int:
    passing = "\n".join((
        "workflow_dispatch:", "validate:", "preview:", "promote:", "needs: validate", "needs: preview",
        "environment: ci-production", "check_ci_product_contracts.py", "scripts/preflight.py",
        "check_ci_vercel_deployment_commit.py --self-test",
        "check_ci_release_http_smoke.py --base-url \"$PREVIEW_URL\"",
        "check_ci_release_http_smoke.py --base-url https://ci.henneth.app --require-authenticated",
        "vercel@39.1.0 deploy --prebuilt", "vercel@39.1.0 promote \"$PREVIEW_URL\"",
        "--meta githubCommitSha=\"$GITHUB_SHA\"",
        "Verify preview is bound to this commit",
        "check_ci_vercel_deployment_commit.py --deployment-url \"$PREVIEW_URL\" --commit-sha \"$GITHUB_SHA\"",
        "PREVIEW_DEPLOYMENT_ID: ${{ needs.preview.outputs.deployment_id }}",
        "Verify production is the promoted preview",
        "check_ci_vercel_deployment_commit.py --deployment-url https://ci.henneth.app --commit-sha \"$GITHUB_SHA\" --expected-deployment-id \"$PREVIEW_DEPLOYMENT_ID\"",
        "scripts/record_ci_release_integrity_receipt.py", "actions/upload-artifact@v4",
        "secrets.VERCEL_TOKEN", "secrets.VERCEL_ORG_ID", "secrets.VERCEL_CI_PROJECT_ID",
        "secrets.HENNETH_CI_OWNER_SMOKE_TOKEN", "secrets.HENNETH_CI_NON_OWNER_SMOKE_TOKEN",
    ))
    if validate(passing):
        print("self-test failed: complete fixture rejected")
        return 1
    if not validate(passing.replace("environment: ci-production", "")):
        print("self-test failed: unprotected production fixture accepted")
        return 1
    print("ci release workflow self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    errors = validate(WORKFLOW.read_text(encoding="utf-8")) if WORKFLOW.exists() else ["release workflow is missing"]
    if errors:
        print("ci release workflow: FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("ci release workflow: PASS (structural only; Vercel settings remain external evidence)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
