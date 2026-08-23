"""Contract checks for Conditional Historical Benchmarks v1."""
from __future__ import annotations
import json, math, subprocess, sys, tempfile
from datetime import date
from pathlib import Path
from psx_data import ROOT, STATE, load_json

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

def main():
    profiles = load_json(STATE / "company_profiles.json", {}); pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    events_state = load_json(STATE / "company_intel" / "operating_events.json", {}); studies_state = load_json(STATE / "company_intel" / "event_studies.json", {}); sectors = load_json(STATE / "sectors.json", {}).get("tickers") or {}
    data = load_json(OUT, {}); walk(data)
    if data.get("pilot_symbols") != pilot or list((data.get("companies") or {}).keys()) != pilot: fail("pilot order/boundary mismatch")
    events = {event.get("event_id"): event for symbol in pilot for event in (((events_state.get("companies") or {}).get(symbol) or {}).get("events") or [])}
    studies = studies_state.get("studies") or {}; total = 0
    for symbol in pilot:
        row = data["companies"][symbol]; expected_ids = [event.get("event_id") for event in (((events_state.get("companies") or {}).get(symbol) or {}).get("events") or [])]
        benchmarks = row.get("benchmarks") or []
        if row.get("symbol") != symbol or [b.get("target_event", {}).get("event_id") for b in benchmarks] != expected_ids: fail(f"{symbol}: target coverage/order mismatch")
        if row.get("benchmark_count") != len(benchmarks): fail(f"{symbol}: count mismatch")
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
            if set(aggregates) != HORIZONS: fail(f"{symbol}: horizon boundary")
            for horizon, aggregate in aggregates.items():
                values = [((candidate.get("outcomes") or {}).get(horizon) or {}).get("return_pct") for candidate in all_candidates if ((candidate.get("outcomes") or {}).get(horizon) or {}).get("status") == "mature" and isinstance(((candidate.get("outcomes") or {}).get(horizon) or {}).get("return_pct"), (int, float))]
                if aggregate.get("n") != len(values): fail(f"{symbol}: n mismatch")
                numeric = list((aggregate.get("stats") or {}).values())
                if len(values) < 3 and (aggregate.get("status") != "suppressed" or aggregate.get("reason") != "n_lt_3" or any(value is not None for value in numeric)): fail(f"{symbol}: thin sample leaked")
                if len(values) >= 3 and (aggregate.get("status") != "available" or any(value is None for value in numeric)): fail(f"{symbol}: mature aggregate missing")
            blocked = benchmark.get("blocked_states") or {}
            if (blocked.get("causal") or {}).get("reason") != "descriptive_not_causal" or not all((blocked.get(key) or {}).get("status") == "blocked" for key in ("peer", "international", "financial", "causal", "forecast", "valuation")): fail(f"{symbol}: blocked states")
    if total != len(events): fail("benchmark count must equal operating event count")
    before = OUT.read_bytes()
    with tempfile.TemporaryDirectory() as temp:
        candidate = Path(temp) / "conditional.json"; result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_conditional_benchmarks.py"), "--out", str(candidate)], capture_output=True, text=True, timeout=30)
        if result.returncode or candidate.read_bytes() != before: fail("builder not byte-idempotent")
    slice_rows = {row.get("symbol"): row for row in load_json(ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json", {"tickers": []}).get("tickers") or []}
    for symbol in pilot:
        if (slice_rows.get(symbol) or {}).get("conditional_benchmarks") != data["companies"][symbol]: fail(f"{symbol}: slice mismatch")
    print(f"conditional_benchmarks: PASS ({len(pilot)} companies, {total} event benchmarks)")

if __name__ == "__main__": main()
