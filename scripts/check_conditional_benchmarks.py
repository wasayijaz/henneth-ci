"""Contract checks for Conditional Historical Benchmarks v1."""
from __future__ import annotations
import json, math, subprocess, sys, tempfile
from datetime import date
from pathlib import Path
from psx_data import ROOT, STATE, load_json
from conditional_benchmarks import candidate_evidence_summary, readiness_ledger
from ci_checker_helpers import without_root_meta

OUT = STATE / "company_intel" / "conditional_benchmarks.json"
HORIZONS = {"1Q", "2Q", "4Q", "8Q"}

def fail(message): raise AssertionError(message)
def iso(value):
    try: return date.fromisoformat(str(value or ""))
    except ValueError: return None
def walk(value):
    if isinstance(value, float) and not math.isfinite(value): fail("nonfinite value")
    if isinstance(value, dict):
        for item in value.values(): walk(item)
    elif isinstance(value, list):
        for item in value: walk(item)

def readiness_summary(rows):
    ledgers = [row.get("readiness_ledger") or {} for row in rows]
    missing = [
        int((ledger.get("missing_mature_outcomes_to_minimum") or {}).get(ledger.get("nearest_ready_horizon")) or 3)
        for ledger in ledgers
    ]
    grouped = {}
    for row in rows:
        target = row.get("target_event") or {}
        grouped.setdefault((target.get("event_type"), target.get("event_subtype")), []).append(row)
    event_class_gaps = []
    for (event_type, event_subtype), items in sorted(grouped.items(), key=lambda item: (str(item[0][0] or ""), str(item[0][1] or ""))):
        item_ledgers = [item.get("readiness_ledger") or {} for item in items]
        item_missing = [
            int((ledger.get("missing_mature_outcomes_to_minimum") or {}).get(ledger.get("nearest_ready_horizon")) or 3)
            for ledger in item_ledgers
        ]
        event_class_gaps.append({
            "event_type": event_type,
            "event_subtype": event_subtype,
            "benchmark_count": len(items),
            "candidate_history_present_count": sum(1 for ledger in item_ledgers if int(ledger.get("strict_candidate_count") or 0) > 0),
            "aggregate_ready_count": sum(1 for ledger in item_ledgers if ledger.get("status") == "aggregate_ready"),
            "total_strict_candidate_count": sum(int(ledger.get("strict_candidate_count") or 0) for ledger in item_ledgers),
            "minimum_missing_mature_outcomes_to_publish": min(item_missing) if item_missing else 3,
        })
    return {
        "dated_benchmark_count": len(rows),
        "benchmarks_with_candidates": sum(1 for ledger in ledgers if int(ledger.get("strict_candidate_count") or 0) > 0),
        "aggregate_ready_benchmark_count": sum(1 for ledger in ledgers if ledger.get("status") == "aggregate_ready"),
        "suppressed_benchmark_count": sum(1 for ledger in ledgers if ledger.get("status") != "aggregate_ready"),
        "total_strict_candidate_count": sum(int(ledger.get("strict_candidate_count") or 0) for ledger in ledgers),
        "minimum_missing_mature_outcomes_to_publish": min(missing) if missing else 3,
        "event_class_gaps": event_class_gaps,
        "policy": "Metadata-only readiness; counts are recomputed from strict retained candidates and do not relax no-lookahead or minimum-sample rules.",
    }

def main():
    profiles = load_json(STATE / "company_profiles.json", {}); pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    events_state = load_json(STATE / "company_intel" / "operating_events.json", {}); studies_state = load_json(STATE / "company_intel" / "event_studies.json", {}); sectors = load_json(STATE / "sectors.json", {}).get("tickers") or {}
    data = load_json(OUT, {}); walk(data)
    if data.get("pilot_symbols") != pilot or list((data.get("companies") or {}).keys()) != pilot: fail("pilot order/boundary mismatch")
    events = {event.get("event_id"): event for symbol in pilot for event in (((events_state.get("companies") or {}).get(symbol) or {}).get("events") or [])}
    studies = studies_state.get("studies") or {}; total = 0; all_benchmarks = []
    for symbol in pilot:
        row = data["companies"][symbol]; expected_ids = [event.get("event_id") for event in (((events_state.get("companies") or {}).get(symbol) or {}).get("events") or []) if iso(event.get("effective_date"))]
        benchmarks = row.get("benchmarks") or []
        if row.get("symbol") != symbol or [b.get("target_event", {}).get("event_id") for b in benchmarks] != expected_ids: fail(f"{symbol}: target coverage/order mismatch")
        if row.get("benchmark_count") != len(benchmarks): fail(f"{symbol}: count mismatch")
        all_benchmarks.extend(benchmarks)
        for benchmark in benchmarks:
            total += 1; target = benchmark.get("target_event") or {}; target_event = events.get(target.get("event_id")); target_study = studies.get(target.get("event_id"))
            if not target_event or not target_study or target.get("study_id") != target_study.get("study_id"): fail(f"{symbol}: unresolved target")
            if target_event.get("symbol") != symbol: fail(f"{symbol}: target crosses company")
            allowed_analogues = {row.get("event_id"): row for row in target_study.get("analogues") or []}
            all_candidates = []
            for group, classification in (("same_company_exact", "same_company"), ("same_sector_exact", "same_sector")):
                for candidate in (benchmark.get("candidates") or {}).get(group) or []:
                    all_candidates.append(candidate); event = events.get(candidate.get("event_id")); study = studies.get(candidate.get("event_id")); source = allowed_analogues.get(candidate.get("event_id"))
                    if not event or not study or not source or candidate.get("outcomes") != source.get("outcomes"): fail(f"{symbol}: unresolved/recomputed candidate")
                    if study.get("event_id") != event.get("event_id") or study.get("symbol") != event.get("symbol") or study.get("effective_date") != event.get("effective_date"): fail(f"{symbol}: candidate study identity mismatch")
                    if candidate.get("outcome_source") != {"target_study_id": target_study.get("study_id"), "target_event_id": target.get("event_id")}: fail(f"{symbol}: outcome source mismatch")
                    if candidate.get("study_id") != study.get("study_id") or candidate.get("classification") != classification: fail(f"{symbol}: candidate identity/class mismatch")
                    if not iso(event.get("effective_date")) or not iso(target_event.get("effective_date")) or not iso(event.get("effective_date")) < iso(target_event.get("effective_date")): fail(f"{symbol}: lookahead analogue")
                    if event.get("event_type") != target_event.get("event_type") or event.get("event_subtype") != target_event.get("event_subtype"): fail(f"{symbol}: nonexact event match")
                    if classification == "same_company" and event.get("symbol") != symbol: fail(f"{symbol}: same-company mismatch")
                    if classification == "same_sector" and (not (sectors.get(event.get("symbol")) or {}).get("sector") or not (sectors.get(symbol) or {}).get("sector") or event.get("symbol") == symbol or (sectors.get(event.get("symbol")) or {}).get("sector") != (sectors.get(symbol) or {}).get("sector")): fail(f"{symbol}: same-sector mismatch")
            aggregates = benchmark.get("horizon_aggregates") or {}
            expected_summary = candidate_evidence_summary(all_candidates)
            if benchmark.get("candidate_evidence_summary") != expected_summary:
                fail(f"{symbol}: candidate evidence summary was not retained exactly")
            expected_readiness = readiness_ledger(all_candidates)
            if benchmark.get("readiness_ledger") != expected_readiness:
                fail(f"{symbol}: readiness ledger was not recomputed from strict candidates")
            if expected_readiness.get("status") == "aggregate_ready":
                if not expected_readiness.get("aggregate_ready_horizons"):
                    fail(f"{symbol}: aggregate-ready ledger lacks ready horizons")
            elif any(aggregate.get("status") == "available" for aggregate in (benchmark.get("horizon_aggregates") or {}).values()):
                fail(f"{symbol}: available aggregate without readiness")
            if set(aggregates) != HORIZONS: fail(f"{symbol}: horizon boundary")
            for horizon, aggregate in aggregates.items():
                values = [((candidate.get("outcomes") or {}).get(horizon) or {}).get("return_pct") for candidate in all_candidates if ((candidate.get("outcomes") or {}).get(horizon) or {}).get("status") == "mature" and isinstance(((candidate.get("outcomes") or {}).get(horizon) or {}).get("return_pct"), (int, float))]
                if aggregate.get("n") != len(values): fail(f"{symbol}: n mismatch")
                numeric = list((aggregate.get("stats") or {}).values())
                if len(values) < 3 and (aggregate.get("status") != "suppressed" or aggregate.get("reason") != "n_lt_3" or any(value is not None for value in numeric)): fail(f"{symbol}: thin sample leaked")
                if len(values) >= 3 and (aggregate.get("status") != "available" or any(value is None for value in numeric)): fail(f"{symbol}: mature aggregate missing")
            blocked = benchmark.get("blocked_states") or {}
            if (blocked.get("causal") or {}).get("reason") != "descriptive_not_causal" or not all((blocked.get(key) or {}).get("status") == "blocked" for key in ("peer", "international", "financial", "causal", "forecast", "valuation")): fail(f"{symbol}: blocked states")
        if row.get("readiness_summary") != readiness_summary(benchmarks):
            fail(f"{symbol}: company readiness summary drifted")
    expected_total = sum(1 for event in events.values() if iso(event.get("effective_date")))
    if total != expected_total: fail("benchmark count must equal dated operating event count")
    if data.get("readiness_summary") != readiness_summary(all_benchmarks):
        fail("top-level readiness summary drifted")
    with tempfile.TemporaryDirectory() as temp:
        candidate = Path(temp) / "conditional.json"; result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_conditional_benchmarks.py"), "--out", str(candidate)], capture_output=True, text=True, timeout=30)
        if result.returncode or without_root_meta(load_json(candidate, {})) != without_root_meta(load_json(OUT, {})):
            fail("builder logical output is not idempotent")
    slice_rows = {row.get("symbol"): row for row in load_json(ROOT / "ci-app" / "data" / "company_intelligence.json", {"tickers": []}).get("tickers") or []}
    for symbol in pilot:
        if (slice_rows.get(symbol) or {}).get("conditional_benchmarks") != data["companies"][symbol]: fail(f"{symbol}: slice mismatch")
    print(f"conditional_benchmarks: PASS ({len(pilot)} companies, {total} event benchmarks)")

if __name__ == "__main__": main()
