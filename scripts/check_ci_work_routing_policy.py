#!/usr/bin/env python3
"""Verify CI work routing cannot become a broad per-ticker AI schedule."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_ci_work_routing_policy import OUT, TARGETED_TRIGGER_TYPES, build
from psx_data import STATE, load_json
from ci_checker_helpers import without_root_meta


def fail(message: str) -> None:
    raise AssertionError(message)


def dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def walk_keys(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


def main() -> None:
    if not OUT.exists():
        fail("CI work-routing policy is missing")
    policy = load_json(OUT, {})
    rebuilt = build(write=False)
    if dump(without_root_meta(policy)) != dump(without_root_meta(rebuilt)):
        fail("CI work-routing policy is stale or non-deterministic")
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    if len(pilot) != 20 or policy.get("pilot_symbols") != pilot:
        fail("CI work-routing pilot boundary mismatch")
    flags = policy.get("policy") or {}
    for key in (
        "deterministic_roster_scan_is_authoritative",
        "official_disclosure_scan_roster_wide",
        "issuer_freshness_scan_roster_wide",
        "targeted_ai_requires_retained_trigger",
        "no_daily_per_ticker_ai_schedules",
        "no_roster_wide_ai_sweeps",
        "no_external_calls",
        "no_supabase_writes",
        "no_prompt_payloads",
    ):
        if flags.get(key) is not True:
            fail(f"CI work-routing policy flag missing: {key}")
    routes = ((policy.get("deterministic_roster_scan") or {}).get("routes")) or []
    expected_routes = {
        "official_psx_disclosure_metadata_scan": "scripts/fetch_company_documents.py",
        "official_issuer_freshness_hash_scan": "scripts/fetch_issuer_sources.py",
        "retained_monitoring_composition": "scripts/build_ci_monitoring.py",
    }
    if {row.get("route_id"): row.get("script") for row in routes} != expected_routes:
        fail("deterministic scan routes drifted")
    if any(row.get("uses_ai") is not False or row.get("scope") != "all_pilot_companies" for row in routes):
        fail("roster-wide deterministic route can invoke AI or lost pilot-wide scope")
    gate = policy.get("targeted_work_gate") or {}
    if gate.get("allowed_trigger_types") != sorted(TARGETED_TRIGGER_TYPES):
        fail("targeted trigger vocabulary drifted")
    if gate.get("daily_per_ticker_ai_schedule_allowed") is not False or gate.get("max_untriggered_company_requests") != 0:
        fail("targeted gate allows untriggered broad AI work")
    companies = policy.get("companies") or {}
    if list(companies) != pilot:
        fail("company order/boundary mismatch")
    candidate_count = 0
    trigger_count = 0
    for symbol in pilot:
        row = companies.get(symbol) or {}
        triggers = row.get("targeted_triggers") or []
        if row.get("symbol") != symbol:
            fail(f"{symbol}: symbol mismatch")
        if row.get("targeted_work_status") == "eligible_for_owner_review_request":
            candidate_count += 1
            if not triggers:
                fail(f"{symbol}: eligible row has no retained trigger")
        elif row.get("targeted_work_status") != "no_targeted_work_request":
            fail(f"{symbol}: invalid targeted work status")
        else:
            if triggers or row.get("allowed_targeted_work"):
                fail(f"{symbol}: untriggered row allows targeted work")
        for trigger in triggers:
            trigger_count += 1
            if trigger.get("trigger_type") not in TARGETED_TRIGGER_TYPES:
                fail(f"{symbol}: unsupported trigger type")
            if trigger.get("trigger_type") == "retained_material_change":
                if not trigger.get("change_id"):
                    fail(f"{symbol}: material trigger missing retained change id")
                if trigger.get("kind") == "issuer_document":
                    fail(f"{symbol}: issuer link-index import became a direct material trigger")
            if trigger.get("trigger_type") == "post_baseline_source_change" and not (
                trigger.get("alert_id") and trigger.get("source_url") and trigger.get("previous_sha256")
            ):
                fail(f"{symbol}: source-change trigger missing retained monitoring proof")
            if trigger.get("trigger_type") == "active_event_review_window" and not (trigger.get("window_start") and trigger.get("window_end")):
                fail(f"{symbol}: event-window trigger missing retained window")
    summary = policy.get("summary") or {}
    if summary.get("targeted_candidate_count") != candidate_count or summary.get("targeted_trigger_count") != trigger_count:
        fail("summary targeted counts mismatch")
    if summary.get("scheduled_ai_task_count") != 0:
        fail("policy claims scheduled AI tasks")
    if gate.get("issuer_document_first_seen_import_is_not_a_trigger") is not True:
        fail("targeted gate does not block historical issuer first-seen imports")
    forbidden_keys = {"prompt_payload", "prompt_payloads", "per_ticker_daily_ai", "daily_ai_schedule"}
    present_forbidden = sorted(key for key in walk_keys(policy) if key in forbidden_keys)
    if present_forbidden:
        fail("policy contains prompt/scheduler payload keys: " + ", ".join(present_forbidden))
    print(f"ci_work_routing_policy: PASS ({len(pilot)} companies, {trigger_count} retained triggers)")


if __name__ == "__main__":
    main()
