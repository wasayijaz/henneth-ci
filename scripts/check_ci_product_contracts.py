#!/usr/bin/env python3
"""Aggregate execution gate for focused Company Intelligence product checks.

This gate is intentionally explicit: it proves the curated product contract
checkers actually execute successfully, without recursively invoking preflight
or the CI completion matrix checker that depends on this file.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FOCUSED_CHECKS: tuple[str, ...] = (
    "check_document_intelligence.py",
    "check_financial_graph.py",
    "check_training_receipt_reconciliation.py",
    "check_operating_intelligence.py",
    "check_signal_clusters.py",
    "check_event_studies.py",
    "check_conditional_benchmarks.py",
    "check_causal_foundations.py",
    "check_financial_model_inputs.py",
    "check_financial_evidence_reconciliation.py",
    "check_forecast_contract.py",
    "check_formal_financial_engines.py",
    "check_ci_reference_cases.py",
    "check_company_scenario_lab.py",
    "check_company_brains.py",
    "check_company_brain_formal_engines.py",
    "check_company_brain_source_index.py",
    "check_thesis_monitoring.py",
    "check_intelligence_confidence.py",
    "check_management_delivery.py",
    "check_guidance_contradictions.py",
    "check_ci_global_no_lookahead.py",
    "check_evidence_watchlist.py",
    "check_ci_monitoring.py",
    "check_peer_registry.py",
    "check_ci_reprocess_manifest.py",
    "check_ownership_source_manifest.py",
    "provenance_lint.py",
    "check_generated_url_safety.py",
    "check_root_state_publication.py",
    "check_company_brain_ui.mjs",
    "check_intelligence_confidence_ui.mjs",
    "check_causal_foundations_ui.mjs",
    "check_financial_coverage_ui.mjs",
    "check_historical_reference_cases_ui.mjs",
    "check_company_scenario_lab_ui.mjs",
    "check_thesis_monitoring_ui.mjs",
    "check_ci_monitoring_ui.mjs",
    "check_company_theses_security.mjs",
    "check_company_theses_ui.mjs",
    "check_ask_henneth.mjs",
    "check_root_ask_hardening.mjs",
    "check_ask_henneth_endpoint.mjs",
    "check_ask_henneth_ui.mjs",
    "check_company_navigation_ui.mjs",
)

FORBIDDEN_CHECKS = {"preflight.py", "check_ci_completion_matrix.py", Path(__file__).name}
OUTPUT_TAIL_CHARS = 1000


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: tuple[str, ...]
    status: str
    returncode: int | None = None
    detail: str = ""


def _rel_command(command: tuple[str, ...], root: Path) -> str:
    rendered: list[str] = []
    for part in command:
        try:
            path = Path(part)
            if path.is_absolute():
                rendered.append(path.relative_to(root).as_posix())
                continue
        except ValueError:
            pass
        rendered.append(part)
    return " ".join(rendered)


def _tail(text: str) -> str:
    clean = (text or "").strip()
    return clean[-OUTPUT_TAIL_CHARS:]


def run_checks(root: Path = ROOT, checks: tuple[str, ...] = FOCUSED_CHECKS, timeout: int = 90) -> list[CheckResult]:
    """Run each explicitly listed checker and return deterministic results."""
    results: list[CheckResult] = []
    seen: set[str] = set()
    for name in checks:
        normalized = Path(name).name
        path = root / "scripts" / normalized
        if normalized.endswith(".py"):
            command = (sys.executable, str(path))
        elif normalized.endswith(".mjs"):
            command = ("node", str(path))
        else:
            command = tuple()
        if normalized in seen:
            results.append(CheckResult(normalized, command, "failed", detail="duplicate checker in aggregate list"))
            continue
        seen.add(normalized)
        if normalized in FORBIDDEN_CHECKS:
            results.append(CheckResult(normalized, command, "failed", detail="recursive checker is forbidden"))
            continue
        if not path.exists():
            results.append(CheckResult(normalized, command, "missing", detail="checker file is missing"))
            continue
        if not command:
            results.append(CheckResult(normalized, command, "failed", detail="unsupported checker extension"))
            continue
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            results.append(CheckResult(normalized, command, "failed", detail=f"timed out after {timeout}s: {_tail((exc.stdout or '') + (exc.stderr or ''))}"))
            continue
        except Exception as exc:  # noqa: BLE001 - checker failures must be reported, not crash this gate
            results.append(CheckResult(normalized, command, "failed", detail=f"could not run checker: {exc}"))
            continue
        if completed.returncode == 0:
            results.append(CheckResult(normalized, command, "passed", returncode=0))
        else:
            detail = _tail((completed.stdout or "") + ("\n" if completed.stdout and completed.stderr else "") + (completed.stderr or ""))
            results.append(CheckResult(normalized, command, "failed", returncode=completed.returncode, detail=detail or "no output"))
    return results


def print_report(results: list[CheckResult], root: Path = ROOT) -> None:
    passed = [result for result in results if result.status == "passed"]
    failed = [result for result in results if result.status != "passed"]
    if failed:
        print(f"ci_product_contracts: FAIL ({len(passed)}/{len(results)} checks executed successfully)")
    else:
        print(f"ci_product_contracts: PASS ({len(results)} checks executed)")
    for result in results:
        command = _rel_command(result.command, root)
        print(f"  {result.status.upper()}: {result.name} :: {command}")
        if result.detail:
            for line in result.detail.splitlines():
                print(f"    {line}")


def _write_fixture(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="henneth-ci-contracts-") as tmp:
        root = Path(tmp)
        scripts = root / "scripts"
        _write_fixture(scripts / "pass_check.py", "print('fixture pass')\n")
        _write_fixture(scripts / "fail_check.py", "raise SystemExit('fixture failure')\n")

        success = run_checks(root, ("pass_check.py",), timeout=5)
        if len(success) != 1 or success[0].status != "passed":
            print("self-test failed: passing fixture did not pass")
            return 1

        missing = run_checks(root, ("missing_check.py",), timeout=5)
        if len(missing) != 1 or missing[0].status != "missing":
            print("self-test failed: missing fixture was not reported")
            return 1

        failed = run_checks(root, ("fail_check.py",), timeout=5)
        if len(failed) != 1 or failed[0].status != "failed" or "fixture failure" not in failed[0].detail:
            print("self-test failed: failing fixture did not propagate output")
            return 1

        forbidden = run_checks(root, ("preflight.py",), timeout=5)
        if len(forbidden) != 1 or forbidden[0].status != "failed" or "forbidden" not in forbidden[0].detail:
            print("self-test failed: forbidden recursion fixture was accepted")
            return 1

    print("ci_product_contracts self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run local fixture checks")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    results = run_checks()
    print_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
