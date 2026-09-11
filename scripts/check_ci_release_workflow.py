#!/usr/bin/env python3
"""Structural guard for the controlled Henneth CI production-release workflow.

This is deliberately offline: it proves the repository contains the guarded
preview-to-promotion path, not that Vercel project settings or secrets are live.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci-production-release.yml"
PROJECT_LINK = ROOT / ".vercel" / "project.json"
SUBDIR_PROJECT_LINK = ROOT / "ci-app" / ".vercel" / "project.json"
VERCEL_CLI_VERSION = "59.9.1"


def validate(text: str) -> list[str]:
    required = (
        "workflow_dispatch:",
        "validate:",
        "preview:",
        "promote:",
        "needs: validate",
        "needs: preview",
        "environment: ci-production",
        "Set release artifact cutoff",
        "HENNETH_CI_BUILD_CUTOFF_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "Finalize CI artifacts for this release commit",
        "HENNETH_CI_SOURCE_COMMIT_SHA: ${{ github.sha }}",
        "python scripts/build_ci_artifact_integrity.py",
        "python scripts/check_ci_artifact_integrity.py",
        "check_ci_product_contracts.py",
        "scripts/preflight.py",
        "check_ci_vercel_deployment_commit.py --self-test",
        "check_ci_release_http_smoke.py --base-url \"$PREVIEW_URL\"",
        "check_ci_release_http_smoke.py --base-url https://ci.henneth.app --require-authenticated",
        f"vercel@{VERCEL_CLI_VERSION} deploy --yes --prod --skip-domain",
        "--meta githubCommitSha=\"$GITHUB_SHA\"",
        f"vercel@{VERCEL_CLI_VERSION} promote \"$PREVIEW_URL\"",
        "Verify preview is bound to this commit",
        "check_ci_vercel_deployment_commit.py --deployment-url \"$PREVIEW_URL\" --commit-sha \"$GITHUB_SHA\"",
        "PREVIEW_DEPLOYMENT_ID: ${{ needs.preview.outputs.deployment_id }}",
        "Verify production is the promoted preview",
        "check_ci_vercel_deployment_commit.py --deployment-url https://ci.henneth.app --commit-sha \"$GITHUB_SHA\" --expected-deployment-id \"$PREVIEW_DEPLOYMENT_ID\"",
        "scripts/record_ci_release_integrity_receipt.py",
        "actions/upload-artifact@v4",
        "secrets.VERCEL_TOKEN",
        "VERCEL_ORG_ID: team_pAWpYAOOLZPwDFoqUeBguGIr",
        "VERCEL_PROJECT_ID: prj_6CYUpEbDTP0qIRl2U7XpaQrxeRrh",
        "secrets.HENNETH_CI_OWNER_SMOKE_EMAIL",
        "secrets.HENNETH_CI_OWNER_SMOKE_PASSWORD",
        "secrets.HENNETH_CI_NON_OWNER_SMOKE_EMAIL",
        "secrets.HENNETH_CI_NON_OWNER_SMOKE_PASSWORD",
        "secrets.VERCEL_AUTOMATION_BYPASS_SECRET",
    )
    errors = [f"missing release workflow contract: {needle}" for needle in required if needle not in text]
    if "SMOKE_TOKEN" in text:
        errors.append("obsolete static smoke-token input remains")
    if "vercel pull" in text:
        errors.append("release workflow must not use vercel pull; project-scoped CI tokens cannot reliably read project settings")
    if "--prebuilt" in text:
        errors.append("release workflow must deploy the restamped source preview, not a prebuilt artifact that requires vercel pull")
    if "working-directory: ci-app" in text:
        errors.append("release workflow must invoke Vercel from the repository root; the Vercel project root already points at ci-app")

    # GitHub only exposes environment-scoped secrets to jobs that explicitly
    # name the environment. The preview job consumes the Vercel credentials,
    # so protecting only the later promote job would leave it empty in CI.
    preview_start = text.find("  preview:\n")
    promote_start = text.find("  promote:\n")
    if preview_start < 0 or promote_start < 0 or promote_start <= preview_start:
        return errors
    preview_job = text[preview_start:promote_start]
    promote_job = text[promote_start:]
    if "environment: ci-production" not in preview_job:
        errors.append("preview job consumes protected Vercel secrets without ci-production environment")
    if "environment: ci-production" not in promote_job:
        errors.append("promote job must retain ci-production environment")

    authenticated_secrets = (
        "HENNETH_CI_OWNER_SMOKE_EMAIL",
        "HENNETH_CI_OWNER_SMOKE_PASSWORD",
        "HENNETH_CI_NON_OWNER_SMOKE_EMAIL",
        "HENNETH_CI_NON_OWNER_SMOKE_PASSWORD",
    )
    preview_authenticated_command = 'python scripts/check_ci_release_http_smoke.py --base-url "$PREVIEW_URL" --require-authenticated'
    production_authenticated_command = "python scripts/check_ci_release_http_smoke.py --base-url https://ci.henneth.app --require-authenticated"
    if preview_authenticated_command not in preview_job:
        errors.append("preview job must run authenticated owner/non-owner smoke before promotion")
    if production_authenticated_command not in promote_job:
        errors.append("promote job must retain authenticated owner/non-owner production smoke")
    for secret_name in authenticated_secrets:
        binding = f"{secret_name}: ${{{{ secrets.{secret_name} }}}}"
        if binding not in preview_job:
            errors.append(f"preview job is missing authenticated smoke secret binding: {secret_name}")
        if binding not in promote_job:
            errors.append(f"promote job is missing authenticated smoke secret binding: {secret_name}")
    return errors


def validate_project_link(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    project_link = root / PROJECT_LINK.relative_to(ROOT)
    subdir_project_link = root / SUBDIR_PROJECT_LINK.relative_to(ROOT)
    if project_link.exists():
        try:
            project = json.loads(project_link.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"release Vercel project link is invalid JSON: {exc}")
        else:
            if project.get("orgId") != "team_pAWpYAOOLZPwDFoqUeBguGIr":
                errors.append("release Vercel project link has the wrong orgId")
            if project.get("projectId") != "prj_6CYUpEbDTP0qIRl2U7XpaQrxeRrh":
                errors.append("release Vercel project link has the wrong projectId")
    if subdir_project_link.exists():
        errors.append("release workflow must not keep a nested ci-app/.vercel/project.json link")
    return errors


def self_test() -> int:
    passing = "\n".join((
        "workflow_dispatch:", "validate:", "needs: validate", "needs: preview",
        "  preview:",
        "    environment: ci-production",
        "    python scripts/check_ci_release_http_smoke.py --base-url \"$PREVIEW_URL\"",
        "    python scripts/check_ci_release_http_smoke.py --base-url \"$PREVIEW_URL\" --require-authenticated",
        "    HENNETH_CI_OWNER_SMOKE_EMAIL: ${{ secrets.HENNETH_CI_OWNER_SMOKE_EMAIL }}",
        "    HENNETH_CI_OWNER_SMOKE_PASSWORD: ${{ secrets.HENNETH_CI_OWNER_SMOKE_PASSWORD }}",
        "    HENNETH_CI_NON_OWNER_SMOKE_EMAIL: ${{ secrets.HENNETH_CI_NON_OWNER_SMOKE_EMAIL }}",
        "    HENNETH_CI_NON_OWNER_SMOKE_PASSWORD: ${{ secrets.HENNETH_CI_NON_OWNER_SMOKE_PASSWORD }}",
        "  promote:",
        "    environment: ci-production",
        "    python scripts/check_ci_release_http_smoke.py --base-url https://ci.henneth.app --require-authenticated",
        "    HENNETH_CI_OWNER_SMOKE_EMAIL: ${{ secrets.HENNETH_CI_OWNER_SMOKE_EMAIL }}",
        "    HENNETH_CI_OWNER_SMOKE_PASSWORD: ${{ secrets.HENNETH_CI_OWNER_SMOKE_PASSWORD }}",
        "    HENNETH_CI_NON_OWNER_SMOKE_EMAIL: ${{ secrets.HENNETH_CI_NON_OWNER_SMOKE_EMAIL }}",
        "    HENNETH_CI_NON_OWNER_SMOKE_PASSWORD: ${{ secrets.HENNETH_CI_NON_OWNER_SMOKE_PASSWORD }}",
        "check_ci_product_contracts.py", "scripts/preflight.py",
        "Set release artifact cutoff",
        "HENNETH_CI_BUILD_CUTOFF_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "Finalize CI artifacts for this release commit",
        "HENNETH_CI_SOURCE_COMMIT_SHA: ${{ github.sha }}",
        "python scripts/build_ci_artifact_integrity.py",
        "python scripts/check_ci_artifact_integrity.py",
        "check_ci_vercel_deployment_commit.py --self-test",
        "check_ci_release_http_smoke.py --base-url \"$PREVIEW_URL\"",
        "check_ci_release_http_smoke.py --base-url https://ci.henneth.app --require-authenticated",
        f"vercel@{VERCEL_CLI_VERSION} deploy --yes --prod --skip-domain", f"vercel@{VERCEL_CLI_VERSION} promote \"$PREVIEW_URL\"",
        "--meta githubCommitSha=\"$GITHUB_SHA\"",
        "Verify preview is bound to this commit",
        "check_ci_vercel_deployment_commit.py --deployment-url \"$PREVIEW_URL\" --commit-sha \"$GITHUB_SHA\"",
        "PREVIEW_DEPLOYMENT_ID: ${{ needs.preview.outputs.deployment_id }}",
        "Verify production is the promoted preview",
        "check_ci_vercel_deployment_commit.py --deployment-url https://ci.henneth.app --commit-sha \"$GITHUB_SHA\" --expected-deployment-id \"$PREVIEW_DEPLOYMENT_ID\"",
        "scripts/record_ci_release_integrity_receipt.py", "actions/upload-artifact@v4",
        "secrets.VERCEL_TOKEN", "VERCEL_ORG_ID: team_pAWpYAOOLZPwDFoqUeBguGIr",
        "VERCEL_PROJECT_ID: prj_6CYUpEbDTP0qIRl2U7XpaQrxeRrh",
        "secrets.HENNETH_CI_OWNER_SMOKE_EMAIL", "secrets.HENNETH_CI_OWNER_SMOKE_PASSWORD",
        "secrets.HENNETH_CI_NON_OWNER_SMOKE_EMAIL", "secrets.HENNETH_CI_NON_OWNER_SMOKE_PASSWORD",
        "secrets.VERCEL_AUTOMATION_BYPASS_SECRET",
    ))
    if validate(passing):
        print("self-test failed: complete fixture rejected")
        return 1
    for missing_flag in (" --prod", " --skip-domain"):
        if not validate(passing.replace(missing_flag, "")):
            print("self-test failed: non-staged deployment accepted")
            return 1
    preview_unprotected = passing.replace("environment: ci-production", "", 1)
    if not validate(preview_unprotected):
        print("self-test failed: unprotected preview fixture accepted")
        return 1
    promote_unprotected = passing.rsplit("environment: ci-production", 1)[0] + passing.rsplit("environment: ci-production", 1)[1]
    if not validate(promote_unprotected):
        print("self-test failed: unprotected promotion fixture accepted")
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
    errors.extend(validate_project_link())
    if errors:
        print("ci release workflow: FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("ci release workflow: PASS (structural only; Vercel settings remain external evidence)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
