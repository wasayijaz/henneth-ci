#!/usr/bin/env python3
"""Validate the Company Intelligence completion matrix."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_ci_completion_matrix as builder
from psx_data import load_json


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _fail(message: str) -> None:
    raise AssertionError(message)


def _synthetic_status_rules() -> None:
    ok = [{"ok": True}]
    bad = [{"ok": False}]
    if builder.requirement_status([], []) != "not_started":
        _fail("empty evidence must be not_started")
    if builder.requirement_status(bad, []) != "not_started":
        _fail("all-false evidence must be not_started")
    if builder.requirement_status(ok, []) != "complete":
        _fail("all-ok evidence without blockers must be complete")
    if builder.requirement_status([ok[0], bad[0]], []) != "partial":
        _fail("mixed evidence must be partial")
    if builder.requirement_status(ok, ["needs live proof"]) != "partial":
        _fail("blockers on implemented evidence must be partial")
    if builder.requirement_status(ok, ["qualified inputs missing"], hard_blocked=True) != "blocked":
        _fail("hard-blocked rows must stay blocked even with evidence")


def _assert_shape(matrix: dict) -> None:
    if matrix.get("schema_version") != 1:
        _fail("schema version mismatch")
    if matrix.get("source_policy") != "retained repo/state evidence only; no fetching, model calls, SQL, publish, deploy, or source mutation":
        _fail("source policy drifted")
    pilot = matrix.get("pilot_symbols") or []
    if len(pilot) != 20 or len(set(pilot)) != 20:
        _fail("pilot boundary must be exactly 20")
    rows = matrix.get("requirements") or []
    ids = [row.get("id") for row in rows]
    if tuple(ids) != builder.REQUIREMENT_IDS:
        _fail("requirement registry mismatch")
    if len(ids) != len(set(ids)):
        _fail("duplicate requirement id")
    counts = {status: 0 for status in builder.STATUSES}
    for row in rows:
        status = row.get("status")
        if status not in builder.STATUSES:
            _fail(f"{row.get('id')}: invalid status {status}")
        counts[status] += 1
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            _fail(f"{row.get('id')}: missing evidence")
        for item in evidence:
            if not isinstance(item.get("ok"), bool) or not item.get("label") or not item.get("path"):
                _fail(f"{row.get('id')}: malformed evidence row")
        if status == "complete" and not all(item.get("ok") for item in evidence):
            _fail(f"{row.get('id')}: complete row has failed evidence")
        if status in {"partial", "blocked", "not_started", "unknown"} and not row.get("next_required_evidence"):
            _fail(f"{row.get('id')}: incomplete row missing next required evidence")
    if (matrix.get("summary") or {}).get("counts") != counts:
        _fail("summary counts mismatch")


def _assert_conservative_statuses(matrix: dict) -> None:
    by_id = {row["id"]: row for row in matrix.get("requirements") or []}
    forecast = by_id["financial_forecasts_valuation_expectations"]
    readiness = load_json(ROOT / "state" / "company_intel" / "forecast_readiness.json", {})
    ready_count = ((readiness.get("summary") or {}).get("ready_company_count") or 0)
    if forecast.get("status") != "blocked":
        _fail("financial forecast/valuation row must remain blocked until real readiness exists")
    if not any(f"Real input-ready company count is {ready_count}" in blocker for blocker in forecast.get("blockers") or []):
        _fail("forecast row did not record real readiness blocker")
    for row_id in ("training_and_approval", "documentation_tests_deploy_readiness"):
        if by_id[row_id].get("status") == "complete":
            _fail(f"{row_id} cannot be complete from repo evidence alone")
    if by_id["impact_analogue_scenario"].get("status") != "partial":
        _fail("impact/analogue/scenario row must stay partial while numeric impacts are null")


def _assert_slice_summary(matrix: dict) -> None:
    slice_path = ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json"
    ci_slice = load_json(slice_path, {})
    expected = builder.slice_summary(matrix)
    actual = (ci_slice.get("meta") or {}).get("completion_matrix")
    if actual != expected:
        _fail("CI slice completion_matrix summary is missing or stale")


def main() -> None:
    _synthetic_status_rules()
    if not builder.OUT.exists():
        _fail("completion_matrix.json is missing")
    matrix = load_json(builder.OUT, {})
    rebuilt = builder.build(write=False)
    if _dump(matrix) != _dump(rebuilt):
        _fail("completion matrix is not current/deterministic")
    _assert_shape(matrix)
    _assert_conservative_statuses(matrix)
    _assert_slice_summary(matrix)
    summary = matrix["summary"]["counts"]
    print(
        "ci_completion_matrix: PASS "
        f"({len(matrix['requirements'])} requirements; "
        f"{summary['complete']} complete, {summary['partial']} partial, {summary['blocked']} blocked)"
    )


if __name__ == "__main__":
    main()
