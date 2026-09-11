#!/usr/bin/env python3
"""Verify a Vercel deployment is bound to the expected Git commit.

This is the live-provider half of the controlled CI release gate.  It reads
Vercel deployment metadata through the documented deployment API and fails if
the deployment does not name the exact release SHA.  It never prints tokens,
headers, response bodies, or other secret-bearing material.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


API_ORIGIN = "https://api.vercel.com"
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
READY_STATES = {"READY"}


def fail(message: str) -> None:
    raise AssertionError(message)


def _deployment_lookup_key(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or not parsed.netloc:
            fail("deployment URL must be an https URL")
        return parsed.netloc
    return value.strip()


def _team_query(team_id: str | None) -> str:
    team_id = (team_id or "").strip()
    # VERCEL_ORG_ID is a user id for personal accounts and a team id for team
    # projects.  The REST API only wants teamId for team-owned resources.
    if not team_id.startswith("team_"):
        return ""
    return "?" + urllib.parse.urlencode({"teamId": team_id})


def _request_deployment(id_or_url: str, token: str, team_id: str | None) -> dict[str, Any]:
    lookup = urllib.parse.quote(_deployment_lookup_key(id_or_url), safe="")
    url = f"{API_ORIGIN}/v13/deployments/{lookup}{_team_query(team_id)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "henneth-ci-vercel-deployment-commit/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise AssertionError(f"Vercel deployment lookup returned HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001 - keep provider failures secret-safe
        raise AssertionError(f"Vercel deployment lookup failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        fail("Vercel deployment lookup returned a non-object payload")
    return payload


def _deployment_id(payload: dict[str, Any]) -> str:
    value = payload.get("uid") or payload.get("id")
    if not isinstance(value, str) or not value:
        fail("Vercel deployment payload did not include a deployment id")
    return value


def _ready_state(payload: dict[str, Any]) -> str:
    value = payload.get("readyState") or payload.get("state")
    if not isinstance(value, str):
        fail("Vercel deployment payload did not include a ready state")
    return value


def _commit_sha(payload: dict[str, Any]) -> str | None:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        value = meta.get("githubCommitSha")
        if isinstance(value, str) and value:
            return value.lower()
    git_source = payload.get("gitSource")
    if isinstance(git_source, dict):
        value = git_source.get("sha") or git_source.get("ref")
        if isinstance(value, str) and COMMIT_SHA.fullmatch(value.lower()):
            return value.lower()
    return None


def validate_payload(
    payload: dict[str, Any],
    *,
    expected_commit_sha: str,
    expected_deployment_id: str | None = None,
) -> tuple[str, str]:
    expected_commit_sha = expected_commit_sha.strip().lower()
    if not COMMIT_SHA.fullmatch(expected_commit_sha):
        fail("expected commit SHA must be a full 40-character lowercase hex SHA")

    deployment_id = _deployment_id(payload)
    if payload.get("target") != "production":
        fail("release deployment must be built for production before promotion")
    if expected_deployment_id and deployment_id != expected_deployment_id:
        fail("production URL does not resolve to the verified preview deployment id")

    ready_state = _ready_state(payload)
    if ready_state not in READY_STATES:
        fail(f"Vercel deployment is not ready: {ready_state}")

    actual_commit_sha = _commit_sha(payload)
    if actual_commit_sha != expected_commit_sha:
        fail("Vercel deployment commit metadata does not match GITHUB_SHA")
    return deployment_id, actual_commit_sha


def self_test() -> int:
    commit_sha = "1234567890abcdef1234567890abcdef12345678"
    fixture = {
        "uid": "dpl_test",
        "readyState": "READY",
        "target": "production",
        "meta": {"githubCommitSha": commit_sha},
    }
    deployment_id, actual = validate_payload(fixture, expected_commit_sha=commit_sha)
    if deployment_id != "dpl_test" or actual != commit_sha:
        print("self-test failed: complete fixture produced wrong result")
        return 1
    mismatch = dict(fixture, meta={"githubCommitSha": "0" * 40})
    try:
        validate_payload(dict(fixture, target="preview"), expected_commit_sha=commit_sha)
    except AssertionError:
        pass
    else:
        print("self-test failed: Preview-environment deployment accepted for promotion")
        return 1
    try:
        validate_payload(mismatch, expected_commit_sha=commit_sha)
    except AssertionError:
        pass
    else:
        print("self-test failed: commit mismatch was accepted")
        return 1
    wrong_id = dict(fixture)
    try:
        validate_payload(wrong_id, expected_commit_sha=commit_sha, expected_deployment_id="dpl_other")
    except AssertionError:
        pass
    else:
        print("self-test failed: deployment id mismatch was accepted")
        return 1
    print("ci Vercel deployment commit self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment-url", help="Vercel deployment URL, hostname, or id")
    parser.add_argument("--commit-sha", help="expected full Git commit SHA")
    parser.add_argument("--expected-deployment-id", help="require this deployment id")
    parser.add_argument("--token-env", default="VERCEL_TOKEN", help="environment variable holding the Vercel token")
    parser.add_argument("--team-id-env", default="VERCEL_ORG_ID", help="optional environment variable holding the Vercel team id")
    parser.add_argument("--github-output", help="optional GitHub Actions output file")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.deployment_url:
        parser.error("--deployment-url is required")
    if not args.commit_sha:
        parser.error("--commit-sha is required")
    token = str(os.environ.get(args.token_env) or "").strip()
    if not token:
        print("ci Vercel deployment commit: FAIL Vercel token is required")
        return 1
    team_id = str(os.environ.get(args.team_id_env) or "").strip()
    try:
        payload = _request_deployment(args.deployment_url, token, team_id)
        deployment_id, actual_commit_sha = validate_payload(
            payload,
            expected_commit_sha=args.commit_sha,
            expected_deployment_id=args.expected_deployment_id,
        )
    except AssertionError as exc:
        print(f"ci Vercel deployment commit: FAIL {exc}")
        return 1
    output_path = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"deployment_id={deployment_id}\n")
            handle.write(f"deployment_commit_sha={actual_commit_sha}\n")
    print(f"ci Vercel deployment commit: PASS deployment_id={deployment_id} commit={actual_commit_sha[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
