#!/usr/bin/env python3
"""Secret-safe HTTP smoke checks for a deployed Henneth CI release.

Anonymous checks prove the public login surface is reachable and private data
fails closed.  Owner/non-owner checks are optional only because their bearer
tokens must live in a protected CI environment, never in repository state or
command output.  The script never prints request headers or response bodies.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


DATA_PATH = "/data/company_intelligence.json"
TIMEOUT_SECONDS = 20


def fail(message: str) -> None:
    raise AssertionError(message)


def request(url: str, token: str | None = None) -> tuple[int, dict[str, Any] | None, str]:
    headers = {"User-Agent": "henneth-ci-release-smoke/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    except Exception as exc:  # noqa: BLE001 - report only a short transport category
        raise AssertionError(f"request failed: {type(exc).__name__}") from exc
    try:
        payload = json.loads(body) if body else None
    except json.JSONDecodeError:
        payload = None
    return status, payload if isinstance(payload, dict) else None, body.decode("utf-8", "replace")


def shell_smoke(base_url: str) -> None:
    status, _payload, body = request(base_url.rstrip("/") + "/")
    if status != 200:
        fail(f"public login shell returned HTTP {status}")
    if "id=\"loginForm\"" not in body or "Owner access" not in body:
        fail("public login shell does not expose the expected owner login surface")


def private_smoke(base_url: str, token: str | None, expected_status: int, expected_error: str | None) -> None:
    status, payload, _body = request(base_url.rstrip("/") + DATA_PATH, token)
    if status != expected_status:
        fail(f"private data returned HTTP {status}; expected {expected_status}")
    if expected_error is not None and (payload or {}).get("error") != expected_error:
        fail("private data gate response shape drifted")
    if expected_status == 200 and not isinstance(payload, dict):
        fail("owner private-data response was not a JSON object")


def run(base_url: str, *, require_authenticated: bool = False) -> None:
    shell_smoke(base_url)
    private_smoke(base_url, None, 401, "owner_required")
    if not require_authenticated:
        return
    owner_token = str(os.environ.get("HENNETH_CI_OWNER_SMOKE_TOKEN") or "").strip()
    non_owner_token = str(os.environ.get("HENNETH_CI_NON_OWNER_SMOKE_TOKEN") or "").strip()
    if not owner_token or not non_owner_token:
        fail("protected owner and non-owner smoke tokens are required")
    private_smoke(base_url, owner_token, 200, None)
    private_smoke(base_url, non_owner_token, 403, "forbidden")


def self_test() -> int:
    try:
        private_smoke("https://example.test", None, 401, "owner_required")
    except AssertionError:
        # The transport is deliberately unavailable; this confirms a failure
        # cannot be converted into a false pass.
        pass
    else:
        print("self-test failed: unavailable endpoint passed")
        return 1
    print("ci release HTTP smoke self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="preview or production CI origin")
    parser.add_argument("--require-authenticated", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.base_url or not args.base_url.startswith("https://"):
        parser.error("--base-url must be an https origin")
    try:
        run(args.base_url, require_authenticated=args.require_authenticated)
    except AssertionError as exc:
        print(f"ci release HTTP smoke: FAIL {exc}")
        return 1
    print("ci release HTTP smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
