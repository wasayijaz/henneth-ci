#!/usr/bin/env python3
"""Secret-safe HTTP smoke checks for a deployed Henneth CI release.

Anonymous checks prove the public login surface is reachable and private data
fails closed. Owner/non-owner checks are optional only because their Supabase
email/password credentials must live in a protected CI environment. The
script exchanges those credentials for short-lived access tokens in memory,
never prints request headers or response bodies, and never persists tokens.
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
# Public client configuration. Keep this synchronized with the authentication
# client in ci-app/app.js; it is deliberately not a secret.
SUPABASE_URL = "https://qteoncckohuoatbjjykb.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw"
VERCEL_BYPASS_SECRET_ENV = "VERCEL_AUTOMATION_BYPASS_SECRET"


def fail(message: str) -> None:
    raise AssertionError(message)


def request(url: str, token: str | None = None) -> tuple[int, dict[str, Any] | None, str]:
    headers = {"User-Agent": "henneth-ci-release-smoke/1.0"}
    bypass_secret = str(os.environ.get(VERCEL_BYPASS_SECRET_ENV) or "").strip()
    if bypass_secret:
        headers["x-vercel-protection-bypass"] = bypass_secret
        headers["x-vercel-set-bypass-cookie"] = "true"
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


def fetch_access_token(email: str, password: str) -> str:
    """Exchange one protected credential pair for an in-memory access token."""
    if not email.strip() or not password:
        fail("protected smoke email/password credentials are required")
    body = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        SUPABASE_URL + "/auth/v1/token?grant_type=password",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "content-type": "application/json",
            "User-Agent": "henneth-ci-release-smoke/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # Do not read or report the provider response: it can contain details
        # about the account and must never become a workflow log artifact.
        raise AssertionError(f"Supabase password grant returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"Supabase password grant failed: {type(exc).__name__}") from exc
    except Exception as exc:  # noqa: BLE001 - provider failures stay secret-safe
        raise AssertionError(f"Supabase password grant failed: {type(exc).__name__}") from exc
    if status != 200 or not isinstance(payload, dict):
        fail("Supabase password grant returned an invalid response")
    token = payload.get("access_token")
    if not isinstance(token, str) or not token.strip():
        fail("Supabase password grant did not return an access token")
    return token.strip()


def shell_smoke(base_url: str) -> None:
    status, _payload, body = request(base_url.rstrip("/") + "/")
    if status != 200:
        fail(f"public login shell returned HTTP {status}")
    if "vercel.com/sso-api" in body or "Authentication Required" in body:
        fail(f"public login shell hit Vercel deployment protection; set {VERCEL_BYPASS_SECRET_ENV}")
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
    owner_token = fetch_access_token(
        str(os.environ.get("HENNETH_CI_OWNER_SMOKE_EMAIL") or "").strip(),
        str(os.environ.get("HENNETH_CI_OWNER_SMOKE_PASSWORD") or ""),
    )
    non_owner_token = fetch_access_token(
        str(os.environ.get("HENNETH_CI_NON_OWNER_SMOKE_EMAIL") or "").strip(),
        str(os.environ.get("HENNETH_CI_NON_OWNER_SMOKE_PASSWORD") or ""),
    )
    private_smoke(base_url, owner_token, 200, None)
    private_smoke(base_url, non_owner_token, 403, "forbidden")


def self_test() -> int:
    class FakeResponse:
        status = 200

        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    original_urlopen = urllib.request.urlopen
    original_request = request
    original_shell_smoke = shell_smoke
    original_private_smoke = private_smoke
    original_fetch_access_token = fetch_access_token
    seen: list[urllib.request.Request] = []

    def fake_urlopen(req, timeout):
        seen.append(req)
        return FakeResponse({"access_token": "offline-token"})

    try:
        urllib.request.urlopen = fake_urlopen
        token = fetch_access_token("owner@example.test", "offline-password")
        if token != "offline-token" or len(seen) != 1:
            print("self-test failed: password grant fixture drifted")
            return 1
        headers = {key.lower(): value for key, value in seen[0].header_items()}
        if seen[0].get_method() != "POST" or headers.get("apikey") != SUPABASE_PUBLISHABLE_KEY:
            print("self-test failed: password grant request contract drifted")
            return 1
        calls = iter(((401, {"error": "owner_required"}, ""),))
        globals()["request"] = lambda *_args, **_kwargs: next(calls)
        private_smoke("https://ci.example.test", None, 401, "owner_required")
        globals()["request"] = original_request

        os.environ[VERCEL_BYPASS_SECRET_ENV] = "offline-bypass-secret"
        captured_request: dict[str, Any] = {}

        def fake_request_urlopen(req, timeout):
            captured_request["headers"] = {key.lower(): value for key, value in req.header_items()}
            return FakeResponse({"ok": True})

        urllib.request.urlopen = fake_request_urlopen
        request("https://ci.example.test/")
        if captured_request.get("headers", {}).get("x-vercel-protection-bypass") != "offline-bypass-secret":
            print("self-test failed: Vercel protection bypass header was not sent")
            return 1
        os.environ.pop(VERCEL_BYPASS_SECRET_ENV, None)

        authenticated_calls: list[tuple[str | None, int, str | None]] = []
        globals()["shell_smoke"] = lambda _base_url: None
        globals()["fetch_access_token"] = lambda email, _password: f"token-for-{email}"
        globals()["private_smoke"] = lambda _base_url, token, expected, error: authenticated_calls.append((token, expected, error))
        prior_env = {name: os.environ.get(name) for name in (
            "HENNETH_CI_OWNER_SMOKE_EMAIL", "HENNETH_CI_OWNER_SMOKE_PASSWORD",
            "HENNETH_CI_NON_OWNER_SMOKE_EMAIL", "HENNETH_CI_NON_OWNER_SMOKE_PASSWORD",
            VERCEL_BYPASS_SECRET_ENV,
        )}
        os.environ.update({
            "HENNETH_CI_OWNER_SMOKE_EMAIL": "owner@example.test",
            "HENNETH_CI_OWNER_SMOKE_PASSWORD": "owner-password",
            "HENNETH_CI_NON_OWNER_SMOKE_EMAIL": "non-owner@example.test",
            "HENNETH_CI_NON_OWNER_SMOKE_PASSWORD": "non-owner-password",
        })
        run("https://ci.example.test", require_authenticated=True)
        if authenticated_calls != [
            (None, 401, "owner_required"),
            ("token-for-owner@example.test", 200, None),
            ("token-for-non-owner@example.test", 403, "forbidden"),
        ]:
            print("self-test failed: authenticated smoke sequence drifted")
            return 1
    except AssertionError as exc:
        print(f"self-test failed: {exc}")
        return 1
    finally:
        urllib.request.urlopen = original_urlopen
        globals()["request"] = original_request
        globals()["shell_smoke"] = original_shell_smoke
        globals()["private_smoke"] = original_private_smoke
        globals()["fetch_access_token"] = original_fetch_access_token
        if "prior_env" in locals():
            for name, value in prior_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
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
