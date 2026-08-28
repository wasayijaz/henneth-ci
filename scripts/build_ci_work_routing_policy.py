#!/usr/bin/env python3
"""Build the CI work-routing policy from retained source state.

This is a policy/route artifact, not a scheduler.  It makes explicit that the
roster-wide Company Intelligence scan is deterministic, while targeted owner or
AI review may only be requested from retained material changes or active event
review windows.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "work_routing_policy.json"
MATERIAL_SEVERITIES = {"material", "critical"}
TARGETED_TRIGGER_TYPES = {"retained_material_change", "post_baseline_source_change", "active_event_review_window"}


def _iso(value: Any) -> str | None:
    try:
        return date.fromisoformat(str(value or "")[:10]).isoformat()
    except ValueError:
        return None


def _as_of(*states: dict[str, Any]) -> str:
    dates = []
    for state in states:
        if not isinstance(state, dict):
            continue
        for key in ("as_of", "updated", "built"):
            parsed = _iso(state.get(key))
            if parsed:
                dates.append(parsed)
        meta = state.get("meta") or state.get("_meta") or {}
        if isinstance(meta, dict):
            for key in ("as_of", "updated", "built"):
                parsed = _iso(meta.get(key))
                if parsed:
                    dates.append(parsed)
    return max(dates) if dates else date.today().isoformat()


def _material_changes(symbol: str, change_state: dict[str, Any]) -> list[dict[str, Any]]:
    row = (change_state.get("companies") or {}).get(symbol) or {}
    out = []
    for item in row.get("items") or []:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "").lower()
        kind = str(item.get("kind") or "")
        date_basis = str(item.get("date_basis") or "")
        source_url = item.get("source_url") or (item.get("evidence") or {}).get("source_url")
        if severity not in MATERIAL_SEVERITIES or not str(source_url or "").startswith(("http://", "https://")):
            continue
        if kind == "issuer_document":
            continue
        out.append({
            "trigger_type": "retained_material_change",
            "change_id": item.get("id"),
            "kind": kind,
            "severity": severity,
            "date": _iso(item.get("date")),
            "date_basis": date_basis or None,
            "title": item.get("title"),
            "source_url": source_url,
            "document_id": item.get("document_id"),
        })
    return sorted(out, key=lambda row: (row.get("date") or "", row.get("change_id") or ""), reverse=True)


def _post_baseline_source_changes(symbol: str, monitoring_state: dict[str, Any]) -> list[dict[str, Any]]:
    row = (monitoring_state.get("companies") or {}).get(symbol) or {}
    out = []
    for alert in row.get("alerts") or []:
        if not isinstance(alert, dict) or alert.get("type") != "source_page_changed":
            continue
        source = alert.get("source") or {}
        identity = alert.get("evidence_identity") or {}
        if not source.get("source_url") or not identity.get("previous_sha256"):
            continue
        out.append({
            "trigger_type": "post_baseline_source_change",
            "alert_id": alert.get("alert_id"),
            "date": _iso(alert.get("date")),
            "title": alert.get("title"),
            "source_url": source.get("source_url"),
            "source": source.get("source"),
            "previous_sha256": identity.get("previous_sha256"),
        })
    return sorted(out, key=lambda row: (row.get("date") or "", row.get("alert_id") or ""), reverse=True)


def _active_review_windows(symbol: str, windows_state: dict[str, Any], as_of: str) -> list[dict[str, Any]]:
    row = (windows_state.get("companies") or {}).get(symbol) or {}
    today = date.fromisoformat(as_of)
    out = []
    for window in row.get("review_windows") or []:
        if not isinstance(window, dict):
            continue
        start = _iso(window.get("start"))
        end = _iso(window.get("end"))
        if not start or not end:
            continue
        if date.fromisoformat(start) <= today <= date.fromisoformat(end):
            out.append({
                "trigger_type": "active_event_review_window",
                "event_type": window.get("event_type"),
                "date": _iso(window.get("date")),
                "window_start": start,
                "window_end": end,
                "confirmed": bool(window.get("confirmed")),
                "source_kind": window.get("source_kind"),
                "source_url": window.get("source_url"),
            })
    return sorted(out, key=lambda row: (row.get("window_start") or "", row.get("event_type") or ""))


def _company_row(
    symbol: str,
    *,
    change_state: dict[str, Any],
    monitoring_state: dict[str, Any],
    windows_state: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:
    material = _material_changes(symbol, change_state)
    source_changes = _post_baseline_source_changes(symbol, monitoring_state)
    windows = _active_review_windows(symbol, windows_state, as_of)
    monitoring = (monitoring_state.get("companies") or {}).get(symbol) or {}
    triggers = material + source_changes + windows
    return {
        "symbol": symbol,
        "deterministic_scan_status": monitoring.get("status") or "unknown",
        "targeted_work_status": "eligible_for_owner_review_request" if triggers else "no_targeted_work_request",
        "targeted_triggers": triggers,
        "targeted_trigger_count": len(triggers),
        "allowed_targeted_work": [
            "owner_review",
            "single_company_ai_analysis",
        ] if triggers else [],
        "prohibited_work": [
            "daily_per_ticker_ai_schedule",
            "roster_wide_ai_sweep",
            "ai_request_without_retained_trigger",
        ],
    }


def build(output_path: Path = OUT, write: bool = True) -> dict[str, Any]:
    profiles = load_json(STATE / "company_profiles.json", {})
    change_state = load_json(STATE / "company_intel" / "change_intelligence.json", {"companies": {}})
    monitoring_state = load_json(STATE / "company_intel" / "monitoring.json", {"companies": {}})
    windows_state = load_json(STATE / "company_intel" / "event_review_windows.json", {"companies": {}})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    as_of = _as_of(change_state, monitoring_state, windows_state)
    companies = {
        symbol: _company_row(
            symbol,
            change_state=change_state,
            monitoring_state=monitoring_state,
            windows_state=windows_state,
            as_of=as_of,
        )
        for symbol in pilot
    }
    eligible = [symbol for symbol, row in companies.items() if row["targeted_trigger_count"]]
    output = {
        "schema_version": 1,
        "kind": "ci_work_routing_policy",
        "as_of": as_of,
        "pilot_symbols": pilot,
        "source": {
            "company_profiles": "state/company_profiles.json",
            "change_intelligence": "state/company_intel/change_intelligence.json",
            "monitoring": "state/company_intel/monitoring.json",
            "event_review_windows": "state/company_intel/event_review_windows.json",
        },
        "policy": {
            "deterministic_roster_scan_is_authoritative": True,
            "official_disclosure_scan_roster_wide": True,
            "issuer_freshness_scan_roster_wide": True,
            "targeted_ai_requires_retained_trigger": True,
            "event_review_windows_are_review_metadata_only": True,
            "no_daily_per_ticker_ai_schedules": True,
            "no_roster_wide_ai_sweeps": True,
            "no_external_calls": True,
            "no_supabase_writes": True,
            "no_prompt_payloads": True,
        },
        "deterministic_roster_scan": {
            "scope": "exact_ci_pilot",
            "company_count": len(pilot),
            "routes": [
                {
                    "route_id": "official_psx_disclosure_metadata_scan",
                    "script": "scripts/fetch_company_documents.py",
                    "scope": "all_pilot_companies",
                    "cadence": "daily_cloud_window",
                    "uses_ai": False,
                },
                {
                    "route_id": "official_issuer_freshness_hash_scan",
                    "script": "scripts/fetch_issuer_sources.py",
                    "scope": "all_pilot_companies",
                    "cadence": "weekly_cloud_window",
                    "uses_ai": False,
                },
                {
                    "route_id": "retained_monitoring_composition",
                    "script": "scripts/build_ci_monitoring.py",
                    "scope": "all_pilot_companies",
                    "cadence": "each_deterministic_ci_build",
                    "uses_ai": False,
                },
            ],
        },
        "targeted_work_gate": {
            "allowed_trigger_types": sorted(TARGETED_TRIGGER_TYPES),
            "request_scope": "single_company_or_explicit_trigger_batch_only",
            "candidate_symbols": eligible,
            "candidate_count": len(eligible),
            "max_untriggered_company_requests": 0,
            "daily_per_ticker_ai_schedule_allowed": False,
            "issuer_document_first_seen_import_is_not_a_trigger": True,
        },
        "companies": companies,
        "summary": {
            "company_count": len(companies),
            "targeted_candidate_count": len(eligible),
            "targeted_trigger_count": sum(row["targeted_trigger_count"] for row in companies.values()),
            "scheduled_ai_task_count": 0,
        },
    }
    if write:
        save_json(output_path, output)
        print(
            "ci_work_routing_policy: "
            f"{len(companies)} companies, {len(eligible)} targeted candidates, "
            f"{output['summary']['targeted_trigger_count']} retained triggers"
        )
    return output


def main() -> None:
    build()


if __name__ == "__main__":
    main()
