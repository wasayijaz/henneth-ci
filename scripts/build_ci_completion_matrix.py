#!/usr/bin/env python3
"""Build the Company Intelligence completion matrix.

This is a source-independent audit artifact: it reads only retained repo/state
files and records what the current Company Intelligence product can prove today.
It never fetches, reprocesses documents, calls a model, or marks a future feature
complete just because a placeholder surface exists.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psx_data import ROOT, STATE, load_json, save_json

OUT = STATE / "company_intel" / "completion_matrix.json"

STATUSES = ("complete", "partial", "blocked", "not_started", "unknown")

PRIMARY_TABS = (
    "overview", "intelligence", "financials", "earnings", "business",
    "operations", "scenarios", "valuation", "guidance", "catalysts",
    "risks", "events", "filings", "peers", "ownership", "quant", "research",
)

REQUIREMENT_IDS = (
    "persistent_brains",
    "intelligence_typing",
    "events_and_signals",
    "driver_graphs",
    "impact_analogue_scenario",
    "financial_forecasts_valuation_expectations",
    "thesis_monitoring",
    "ask_henneth",
    "company_navigation",
    "scenario_lab",
    "provenance_confidence_no_lookahead",
    "training_and_approval",
    "private_access",
    "deterministic_calculations",
    "continuous_monitoring",
    "documentation_tests_deploy_readiness",
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _exists(rel_path: str) -> bool:
    return (ROOT / rel_path).exists()


def _text(rel_path: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _ok(label: str, rel_path: str, detail: str = "") -> dict[str, Any]:
    exists = _exists(rel_path)
    return {
        "label": label,
        "path": rel_path,
        "ok": exists,
        "detail": detail or ("present" if exists else "missing"),
    }


def _check(label: str, rel_path: str) -> dict[str, Any]:
    return _ok(label, rel_path, "preflight/focused checker path")


def _state(label: str, rel_path: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"label": label, "path": rel_path, "ok": bool(ok), "detail": detail}


def _contains(label: str, rel_path: str, needles: tuple[str, ...]) -> dict[str, Any]:
    haystack = _text(rel_path)
    missing = [needle for needle in needles if needle not in haystack]
    return {
        "label": label,
        "path": rel_path,
        "ok": not missing,
        "detail": "all expected markers present" if not missing else f"missing markers: {', '.join(missing[:5])}",
    }


def requirement_status(evidence: list[dict[str, Any]], blockers: list[str], hard_blocked: bool = False) -> str:
    ok_count = sum(1 for item in evidence if item.get("ok") is True)
    if hard_blocked:
        return "blocked"
    if not evidence or ok_count == 0:
        return "not_started"
    if blockers:
        return "partial"
    if ok_count != len(evidence):
        return "partial"
    return "complete"


def _row(
    requirement_id: str,
    title: str,
    evidence: list[dict[str, Any]],
    next_required_evidence: list[str],
    blockers: list[str] | None = None,
    hard_blocked: bool = False,
) -> dict[str, Any]:
    blockers = blockers or []
    status = requirement_status(evidence, blockers, hard_blocked)
    return {
        "id": requirement_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "blockers": blockers,
        "next_required_evidence": next_required_evidence,
    }


def _pilot_symbols(profiles: dict[str, Any]) -> list[str]:
    return list(((profiles.get("pilot") or {}).get("symbols") or []))


def _exact_pilot(data: dict[str, Any], pilot: list[str]) -> bool:
    companies = data.get("companies")
    return bool(len(pilot) == 20 and isinstance(companies, dict) and set(companies) == set(pilot))


def _company_count(data: dict[str, Any]) -> int:
    companies = data.get("companies")
    return len(companies) if isinstance(companies, dict) else 0


def _sum_company_metric(data: dict[str, Any], key: str) -> int:
    total = 0
    for row in (data.get("companies") or {}).values():
        value = row.get(key)
        if isinstance(value, int):
            total += value
    return total


def _has_non_empty_graphs(driver_graphs: dict[str, Any], pilot: list[str]) -> bool:
    companies = driver_graphs.get("companies") or {}
    for symbol in pilot:
        row = companies.get(symbol) or {}
        if not row.get("drivers") or not row.get("edges"):
            return False
    return bool(pilot)


def _strict_no_lookahead_count(event_studies: dict[str, Any]) -> tuple[int, int]:
    studies = event_studies.get("studies") or {}
    total = len(studies)
    strict = sum(1 for row in studies.values() if row.get("strict_no_lookahead") is True)
    return strict, total


def _completion_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {status: 0 for status in STATUSES}
    for row in rows:
        counts[row["status"]] += 1
    if counts["blocked"]:
        overall = "blocked"
    elif counts["partial"]:
        overall = "partial"
    elif counts["not_started"] or counts["unknown"]:
        overall = "partial"
    else:
        overall = "complete"
    return {
        "overall_status": overall,
        "requirement_count": len(rows),
        "counts": counts,
        "complete_requirement_ids": [row["id"] for row in rows if row["status"] == "complete"],
        "blocked_requirement_ids": [row["id"] for row in rows if row["status"] == "blocked"],
    }


def slice_summary(matrix: dict[str, Any]) -> dict[str, Any]:
    summary = matrix.get("summary") or {}
    counts = summary.get("counts") or {}
    return {
        "artifact": "state/company_intel/completion_matrix.json",
        "as_of": matrix.get("as_of") or "unknown",
        "overall_status": summary.get("overall_status") or "unknown",
        "requirement_count": summary.get("requirement_count") or 0,
        "complete": counts.get("complete", 0),
        "partial": counts.get("partial", 0),
        "blocked": counts.get("blocked", 0),
    }


def build(write: bool = True) -> dict[str, Any]:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = _pilot_symbols(profiles)
    brains = load_json(STATE / "company_intel" / "company_brains.json", {})
    operating_events = load_json(STATE / "company_intel" / "operating_events.json", {})
    driver_graphs = load_json(STATE / "company_intel" / "driver_graphs.json", {})
    impact_scenarios = load_json(STATE / "company_intel" / "impact_scenarios.json", {})
    event_studies = load_json(STATE / "company_intel" / "event_studies.json", {})
    conditional_benchmarks = load_json(STATE / "company_intel" / "conditional_benchmarks.json", {})
    causal_foundations = load_json(STATE / "company_intel" / "causal_foundations.json", {})
    forecast_readiness = load_json(STATE / "company_intel" / "forecast_readiness.json", {})
    scenario_lab = load_json(STATE / "company_intel" / "scenario_lab.json", {})
    signal_clusters = load_json(STATE / "company_intel" / "signal_clusters.json", {})
    thesis_monitoring = load_json(STATE / "company_intel" / "thesis_monitoring.json", {})
    confidence = load_json(STATE / "company_intel" / "intelligence_confidence.json", {})
    management_delivery = load_json(STATE / "company_intel" / "management_delivery.json", {})
    evidence_watchlist = load_json(STATE / "company_intel" / "evidence_watchlist.json", {})
    monitoring = load_json(STATE / "company_intel" / "monitoring.json", {})
    guidance = load_json(STATE / "company_intel" / "guidance_contradictions.json", {})
    peer_registry = load_json(STATE / "company_intel" / "peer_registry.json", {})
    ci_slice = load_json(ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json", {})

    strict_studies, study_total = _strict_no_lookahead_count(event_studies)
    ready_count = (forecast_readiness.get("summary") or {}).get("ready_company_count", 0)
    rows = [
        _row(
            "persistent_brains",
            "Persistent Company Brain",
            [
                _state("exact 20-company brain state", "state/company_intel/company_brains.json", _exact_pilot(brains, pilot), f"{_company_count(brains)} company rows"),
                _state("21-domain registry", "state/company_intel/company_brains.json", len(brains.get("domains") or []) == 21, f"{len(brains.get('domains') or [])} domains"),
                _check("brain contract checker", "scripts/check_company_brains.py"),
                _check("brain UI contract checker", "scripts/check_company_brain_ui.mjs"),
            ],
            ["Keep every future Brain domain reference-only and source-resolvable."],
        ),
        _row(
            "intelligence_typing",
            "Uniform Intelligence Typing",
            [
                _ok("shared type registry", "scripts/intelligence_types.py"),
                _state("five canonical types emitted", "state/company_intel/company_brains.json", brains.get("intelligence_types") == ["reported_fact", "derived_fact", "inference", "scenario", "forecast"], "reported_fact, derived_fact, inference, scenario, forecast"),
                _state("typed confidence rows", "state/company_intel/intelligence_confidence.json", _exact_pilot(confidence, pilot), f"{_company_count(confidence)} company rows"),
            ],
            ["Extend the registry only when a new producer emits source-resolvable objects of that type."],
        ),
        _row(
            "events_and_signals",
            "Operating Events and Signal Clusters",
            [
                _state("operating events state", "state/company_intel/operating_events.json", _exact_pilot(operating_events, pilot), f"{_company_count(operating_events)} company rows"),
                _state("signal cluster state", "state/company_intel/signal_clusters.json", _exact_pilot(signal_clusters, pilot), f"{_sum_company_metric(signal_clusters, 'clusterable_count')} clusterable records"),
                _check("operating intelligence checker", "scripts/check_operating_intelligence.py"),
                _check("signal cluster checker", "scripts/check_signal_clusters.py"),
            ],
            ["Add new event/signal classes only through the closed registries and retained evidence."],
        ),
        _row(
            "driver_graphs",
            "Declarative Driver Graphs",
            [
                _state("full-pilot driver graphs", "state/company_intel/driver_graphs.json", _has_non_empty_graphs(driver_graphs, pilot), f"{_company_count(driver_graphs)} company rows"),
                _ok("sector driver model registry", "scripts/sector_driver_models.py"),
                _check("driver/event routing checker", "scripts/check_operating_intelligence.py"),
            ],
            ["Measured driver evidence can be added later; current graphs are declarative routing only."],
        ),
        _row(
            "impact_analogue_scenario",
            "Impact, Analogue, and Scenario Products",
            [
                _state("impact scenario shells", "state/company_intel/impact_scenarios.json", _exact_pilot(impact_scenarios, pilot), f"{_company_count(impact_scenarios)} company rows"),
                _state("strict event studies", "state/company_intel/event_studies.json", strict_studies == study_total and study_total > 0, f"{strict_studies}/{study_total} strict no-lookahead studies"),
                _state("conditional benchmarks", "state/company_intel/conditional_benchmarks.json", _exact_pilot(conditional_benchmarks, pilot), f"{_company_count(conditional_benchmarks)} company rows"),
                _state("causal evidence map", "state/company_intel/causal_foundations.json", _exact_pilot(causal_foundations, pilot), f"{_company_count(causal_foundations)} company rows"),
                _state("scenario lab state", "state/company_intel/scenario_lab.json", _exact_pilot(scenario_lab, pilot), f"{_company_count(scenario_lab)} company rows"),
            ],
            ["Sourced operands for numeric impacts and enough mature analogue samples for published aggregates."],
            ["Numeric impact, probability, EBITDA, FCF, DCF, and formal forecast outputs remain blocked or null."],
        ),
        _row(
            "financial_forecasts_valuation_expectations",
            "Financial Forecasts, Formal Valuation, and Market Expectations",
            [
                _state("readiness contract", "state/company_intel/forecast_readiness.json", _exact_pilot(forecast_readiness, pilot), f"{_company_count(forecast_readiness)} company rows"),
                _check("forecast readiness contract checker", "scripts/check_forecast_contract.py"),
                _check("financial evidence reconciliation checker", "scripts/check_financial_evidence_reconciliation.py"),
            ],
            ["Three aligned annual consolidated PKR periods for revenue, attributable PAT, and EPS with official provenance and no conflicts; then implemented numeric models."],
            [f"Real input-ready company count is {ready_count}; downstream forecast, valuation, and market-expectations outputs remain blocked."],
            hard_blocked=True,
        ),
        _row(
            "thesis_monitoring",
            "Thesis Monitoring",
            [
                _state("deterministic thesis monitoring", "state/company_intel/thesis_monitoring.json", _exact_pilot(thesis_monitoring, pilot), f"{_company_count(thesis_monitoring)} company rows"),
                _state("management delivery", "state/company_intel/management_delivery.json", _exact_pilot(management_delivery, pilot), f"{_company_count(management_delivery)} company rows"),
                _ok("private thesis SQL contract", "docs/company_theses.sql"),
                _check("private thesis security checker", "scripts/check_company_theses_security.mjs"),
                _check("thesis UI checker", "scripts/check_company_theses_ui.mjs"),
            ],
            ["Owner applies and live-verifies company_theses SQL/RLS before private thesis storage is complete."],
            ["Private user thesis storage is code-ready but not known live from repo evidence."],
        ),
        _row(
            "ask_henneth",
            "Ask Henneth",
            [
                _ok("owner-only Ask endpoint", "Henneth Desk 2.CI.0/api/ask.js"),
                _ok("server-owned Ask contract", "Henneth Desk 2.CI.0/api/ask_contract.js"),
                _check("Ask contract checker", "scripts/check_ask_henneth.mjs"),
                _check("Ask endpoint checker", "scripts/check_ask_henneth_endpoint.mjs"),
                _check("Ask UI checker", "scripts/check_ask_henneth_ui.mjs"),
            ],
            ["Release smoke test with live owner JWT and provider env before claiming deployed Ask availability."],
        ),
        _row(
            "company_navigation",
            "Company Navigation",
            [
                _contains("exact primary tab registry", "Henneth Desk 2.CI.0/app.js", PRIMARY_TABS),
                _check("company navigation UI checker", "scripts/check_company_navigation_ui.mjs"),
                _state("formal peer registry", "state/company_intel/peer_registry.json", _exact_pilot(peer_registry, pilot), f"{_company_count(peer_registry)} company rows"),
            ],
            ["Keep future tabs display-only over emitted state; no browser-side business derivation."],
        ),
        _row(
            "scenario_lab",
            "Scenario Lab",
            [
                _state("scenario lab exact pilot", "state/company_intel/scenario_lab.json", _exact_pilot(scenario_lab, pilot), f"{_company_count(scenario_lab)} company rows"),
                _check("scenario lab checker", "scripts/check_company_scenario_lab.py"),
                _check("scenario lab UI checker", "scripts/check_company_scenario_lab_ui.mjs"),
            ],
            ["Formal forecast/valuation inputs remain separate from caller-supplied sensitivity arithmetic."],
        ),
        _row(
            "provenance_confidence_no_lookahead",
            "Provenance, Confidence, and No-Lookahead",
            [
                _check("provenance lint", "scripts/provenance_lint.py"),
                _state("strict no-lookahead event studies", "state/company_intel/event_studies.json", strict_studies == study_total and study_total > 0, f"{strict_studies}/{study_total} studies"),
                _state("confidence scoring", "state/company_intel/intelligence_confidence.json", _exact_pilot(confidence, pilot), f"{_company_count(confidence)} company rows"),
                _check("confidence checker", "scripts/check_intelligence_confidence.py"),
                _state("CI slice source", "Henneth Desk 2.CI.0/data/company_intelligence.json", len(ci_slice.get("tickers") or []) == len(pilot), f"{len(ci_slice.get('tickers') or [])} slice rows"),
            ],
            ["Any future source class needs retained URL/page/availability evidence and a focused checker before it can count as complete."],
        ),
        _row(
            "training_and_approval",
            "Training Mode and Owner Approval",
            [
                _ok("training batch handoff", "scripts/prepare_synthesis_batch.py"),
                _ok("approval gate", "scripts/company_brief_review.py"),
                _ok("training prompt", "prompts/company-intelligence-training.md"),
                _ok("append-only approval receipts", "state/company_brief_receipts.json"),
                _check("receipt reconciliation checker", "scripts/check_training_receipt_reconciliation.py"),
            ],
            ["Owner-approved candidate receipts for each future synthesized brief; never auto-approve model prose."],
            ["Training remains owner-gated by design and cannot be unattended from repo evidence."],
        ),
        _row(
            "private_access",
            "Private Access and Publication Boundary",
            [
                _ok("CI data middleware", "Henneth Desk 2.CI.0/middleware.js"),
                _ok("CI owner-only Ask endpoint", "Henneth Desk 2.CI.0/api/ask.js"),
                _ok("root state publication boundary", "scripts/root_state_publication.py"),
                _check("root state publication checker", "scripts/check_root_state_publication.py"),
                _check("generated URL safety checker", "scripts/check_generated_url_safety.py"),
            ],
            ["Live 401/403/200 owner-token smoke tests before release sign-off."],
        ),
        _row(
            "deterministic_calculations",
            "Deterministic Calculations",
            [
                _check("Rule 4 checker", "scripts/check_rule4.py"),
                _check("forecast readiness synthetic checker", "scripts/check_forecast_contract.py"),
                _check("scenario lab formula checker", "scripts/check_company_scenario_lab.py"),
                _check("financial model input checker", "scripts/check_financial_model_inputs.py"),
            ],
            ["New calculation surfaces need synthetic fixtures and byte/idempotency checks before entering the publish path."],
        ),
        _row(
            "continuous_monitoring",
            "Continuous Monitoring",
            [
                _state("monitoring pulse", "state/company_intel/monitoring.json", _exact_pilot(monitoring, pilot), f"{_company_count(monitoring)} company rows"),
                _state("evidence watchlist", "state/company_intel/evidence_watchlist.json", _exact_pilot(evidence_watchlist, pilot), f"{_company_count(evidence_watchlist)} company rows"),
                _state("guidance contradictions", "state/company_intel/guidance_contradictions.json", _exact_pilot(guidance, pilot), f"{_company_count(guidance)} company rows"),
                _check("monitoring checker", "scripts/check_ci_monitoring.py"),
                _check("evidence watchlist checker", "scripts/check_evidence_watchlist.py"),
            ],
            ["Broader alternative-data monitors require bounded retained source registries before they can be added."],
        ),
        _row(
            "documentation_tests_deploy_readiness",
            "Documentation, Tests, and Deploy Readiness",
            [
                _ok("architecture docs", "docs/ARCHITECTURE.md"),
                _ok("operations docs", "docs/OPERATIONS.md"),
                _ok("checkpoint handoff", "docs/CI-CHECKPOINT-2026-08-23.md"),
                _ok("preflight gate", "scripts/preflight.py"),
                _ok("cloud pipeline entry", "scripts/run_cloud.py"),
            ],
            ["Run full preflight and owner-approved publish/deploy smoke checks before declaring release complete."],
            ["This repository evidence cannot prove live deployment readiness or owner approval."],
        ),
    ]

    if tuple(row["id"] for row in rows) != REQUIREMENT_IDS:
        raise AssertionError("completion matrix requirement registry drifted")

    payload = {
        "schema_version": 1,
        "as_of": (forecast_readiness.get("as_of")
                  or profiles.get("updated")
                  or "unknown"),
        "scope": "Company Intelligence product completion audit",
        "source_policy": "retained repo/state evidence only; no fetching, model calls, SQL, publish, deploy, or source mutation",
        "pilot_symbols": pilot,
        "summary": _completion_summary(rows),
        "requirements": rows,
    }
    if write:
        save_json(OUT, payload)
        print(f"ci_completion_matrix: {len(rows)} requirements -> {_rel(OUT)}")
    return payload


if __name__ == "__main__":
    build()
