#!/usr/bin/env python3
"""Regression checks for the manual CI refresh contract."""
from __future__ import annotations

from pathlib import Path
import tempfile
from unittest import mock

import refresh_ci


def check_missing_input_is_transactional() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        existing = root / "state" / "keep.json"
        existing.parent.mkdir(parents=True)
        existing.write_text('{"old": true}\n', encoding="utf-8")
        manifest = {"desk_pin_sha": "a" * 40, "inputs": {"keep.json": {}, "missing.json": {}}}

        def reader(relative: str) -> bytes:
            if relative == "keep.json":
                return b'{"new": true}\n'
            raise refresh_ci.RefreshError("missing committed blob")

        try:
            refresh_ci.stage_inputs(manifest, reader, root / "stage")
        except refresh_ci.RefreshError:
            pass
        else:
            raise AssertionError("missing input did not fail staging")
        assert existing.read_text(encoding="utf-8") == '{"old": true}\n'
        assert manifest["desk_pin_sha"] == "a" * 40


def check_snapshot_hash_and_noop_contract() -> None:
    manifest = {"desk_pin_sha": "a" * 40, "inputs": {"keep.json": {"sha256": "b" * 64}}}
    first = refresh_ci.refreshed_manifest(manifest, "c" * 40, {"keep.json": "d" * 64})
    second = refresh_ci.refreshed_manifest(manifest, "c" * 40, {"keep.json": "d" * 64})
    assert first["desk_pin_sha"] == second["desk_pin_sha"] == "c" * 40
    assert first["snapshot_sha256"] == second["snapshot_sha256"]
    assert refresh_ci.should_noop(False, False)
    assert not refresh_ci.should_noop(False, True)
    assert not refresh_ci.should_noop(True, False)


def check_chain_is_explicit_and_complete() -> None:
    assert "build_calendar.py" not in refresh_ci.AUDITED_CI_CHAIN
    assert refresh_ci.audited_steps() == list(refresh_ci.AUDITED_CI_CHAIN)
    with tempfile.TemporaryDirectory() as temporary:
        scripts = Path(temporary)
        try:
            refresh_ci.audited_steps(scripts)
        except refresh_ci.RefreshError as exc:
            assert "audited CI producer missing" in str(exc)
        else:
            raise AssertionError("missing audited producer did not fail")


def check_failed_and_timed_out_producers_are_failures() -> None:
    class Result:
        def __init__(self, returncode: int):
            self.returncode = returncode

    calls = []

    def fake_run(args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return Result(7)
        raise refresh_ci.subprocess.TimeoutExpired(args, refresh_ci.PRODUCER_TIMEOUT_S)

    with mock.patch.object(refresh_ci.subprocess, "run", side_effect=fake_run):
        failures, skipped = refresh_ci.run_chain(["first.py", "second.py"], "c" * 40)
    assert failures == ["first.py:7", f"second.py:timeout>{refresh_ci.PRODUCER_TIMEOUT_S}s"]
    assert skipped == []
    assert all(call.get("timeout") == refresh_ci.PRODUCER_TIMEOUT_S for call in calls)


def check_ci_head_is_separate_from_desk_pin() -> None:
    with mock.patch.object(refresh_ci, "_run", return_value=(b"d" * 40 + b"\n")) as command:
        ci_head = refresh_ci.resolve_ci_head()
    assert ci_head == "d" * 40
    assert "rev-parse" in command.call_args.args[0]
    assert refresh_ci.refreshed_manifest(
        {"desk_pin_sha": "a" * 40, "inputs": {}}, "e" * 40, {}
    )["desk_pin_sha"] == "e" * 40


def main() -> int:
    check_missing_input_is_transactional()
    check_snapshot_hash_and_noop_contract()
    check_chain_is_explicit_and_complete()
    check_failed_and_timed_out_producers_are_failures()
    check_ci_head_is_separate_from_desk_pin()
    print("ci_refresh regression checks: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
