"""Pure resolver for strict, descriptive conditional historical benchmarks."""
from __future__ import annotations

import hashlib
import statistics
from datetime import date
from typing import Any

HORIZONS = ("1Q", "2Q", "4Q", "8Q")
MIN_SAMPLE = 3

def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return "conditional_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _aggregate(candidates: list[dict], horizon: str) -> dict:
    values = []
    for candidate in candidates:
        outcome = (candidate.get("outcomes") or {}).get(horizon) or {}
        value = outcome.get("return_pct")
        if outcome.get("status") == "mature" and isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    base = {"n": len(values), "status": "available" if len(values) >= MIN_SAMPLE else "suppressed", "reason": None if len(values) >= MIN_SAMPLE else "n_lt_3"}
    if len(values) < MIN_SAMPLE:
        return {**base, "stats": {"mean_return_pct": None, "median_return_pct": None, "min_return_pct": None, "max_return_pct": None}}
    return {**base, "stats": {"mean_return_pct": sum(values) / len(values), "median_return_pct": statistics.median(values), "min_return_pct": min(values), "max_return_pct": max(values)}}


def candidate_evidence_summary(candidates: list[dict]) -> dict:
    """Display-safe completeness evidence; never a new outcome or inference."""
    by_class = {
        "same_company_exact": sum(1 for row in candidates if row.get("classification") == "same_company"),
        "same_sector_exact": sum(1 for row in candidates if row.get("classification") == "same_sector"),
    }
    mature_by_horizon = {
        horizon: sum(
            1 for row in candidates
            if ((row.get("outcomes") or {}).get(horizon) or {}).get("status") == "mature"
            and isinstance(((row.get("outcomes") or {}).get(horizon) or {}).get("return_pct"), (int, float))
            and not isinstance(((row.get("outcomes") or {}).get(horizon) or {}).get("return_pct"), bool)
        )
        for horizon in HORIZONS
    }
    latest = max((str(row.get("effective_date")) for row in candidates if _date(row.get("effective_date"))), default=None)
    evidence_status = (
        "no_prior_exact_analogues" if not candidates
        else "aggregate_ready" if any(count >= MIN_SAMPLE for count in mature_by_horizon.values())
        else "thin_history_present"
    )
    return {
        "evidence_status": evidence_status,
        "candidate_counts": by_class,
        "mature_horizon_counts": mature_by_horizon,
        "latest_prior_candidate_date": latest,
        "limitation": "Descriptive prior-event evidence only; it is not causal, a forecast, valuation or advice.",
    }


def build_conditional_benchmarks(pilot: list[str], event_state: dict, study_state: dict, sector_rows: dict) -> dict:
    events = {event.get("event_id"): event for symbol in pilot for event in (((event_state.get("companies") or {}).get(symbol) or {}).get("events") or []) if event.get("event_id")}
    studies = study_state.get("studies") or {}
    companies = {}
    for symbol in pilot:
        benchmarks = []
        company_events = (((event_state.get("companies") or {}).get(symbol) or {}).get("events") or [])
        for target in company_events:
            target_id = target.get("event_id")
            target_study = studies.get(target_id) or {}
            target_sector = (sector_rows.get(symbol) or {}).get("sector")
            target_date = _date(target.get("effective_date"))
            # A conditional benchmark has a strict before/after boundary.  A
            # target without a parseable effective date cannot define that
            # boundary, so retain it only in the operating-event source rather
            # than emitting a superficially "blocked" benchmark row.
            if not target_date:
                continue
            same_company, same_sector = [], []
            for analogue in target_study.get("analogues") or []:
                candidate_event = events.get(analogue.get("event_id")) or {}
                candidate_study = studies.get(analogue.get("event_id")) or {}
                if not candidate_event or not candidate_study:
                    continue
                candidate_date = _date(candidate_event.get("effective_date"))
                if not target_date or not candidate_date or candidate_date >= target_date:
                    continue
                if candidate_event.get("event_type") != target.get("event_type") or candidate_event.get("event_subtype") != target.get("event_subtype"):
                    continue
                classification = analogue.get("classification")
                candidate_sector = (sector_rows.get(candidate_event.get("symbol")) or {}).get("sector")
                if classification == "same_company" and candidate_event.get("symbol") != symbol:
                    continue
                if classification == "same_sector" and (not target_sector or not candidate_sector or candidate_event.get("symbol") == symbol or candidate_sector != target_sector):
                    continue
                row = {
                    "event_id": candidate_event.get("event_id"),
                    "study_id": candidate_study.get("study_id"),
                    "symbol": candidate_event.get("symbol"),
                    "effective_date": candidate_event.get("effective_date"),
                    "classification": classification,
                    "event_type": candidate_event.get("event_type"),
                    "event_subtype": candidate_event.get("event_subtype"),
                    "sector": candidate_sector,
                    "outcomes": analogue.get("outcomes") or {},
                    "outcome_source": {"target_study_id": target_study.get("study_id"), "target_event_id": target_id},
                }
                (same_company if classification == "same_company" else same_sector).append(row)
            same_company.sort(key=lambda row: (row.get("effective_date") or "", row.get("event_id") or ""), reverse=True)
            same_sector.sort(key=lambda row: (row.get("effective_date") or "", row.get("event_id") or ""), reverse=True)
            candidates = same_company + same_sector
            benchmarks.append({
                "benchmark_id": _id(symbol, target_id, target.get("event_type"), target.get("event_subtype")),
                "target_event": {"event_id": target_id, "study_id": target_study.get("study_id"), "symbol": symbol, "event_type": target.get("event_type"), "event_subtype": target.get("event_subtype"), "effective_date": target.get("effective_date"), "sector": target_sector, "description": target.get("description")},
                "context": {"conditions": [f"event_type={target.get('event_type')}", f"event_subtype={target.get('event_subtype')}", f"sector={target_sector or 'unknown'}"], "summary": "Exact event class and retained current-sector context."},
                "status": "candidate_history_present" if candidates else "no_prior_exact_analogues",
                "matching_policy": {"event_type": "exact", "event_subtype": "exact", "candidate_date": "strictly_before_target", "same_company": "same_symbol", "same_sector": "same_current_sector_other_symbol", "returns": "reuse_target_event_study_analogue_outcomes", "minimum_aggregate_sample": MIN_SAMPLE},
                "candidates": {"same_company_exact": same_company, "same_sector_exact": same_sector},
                "candidate_evidence_summary": candidate_evidence_summary(candidates),
                "horizon_aggregates": {horizon: _aggregate(candidates, horizon) for horizon in HORIZONS},
                "blocked_states": {
                    "peer": {"status": "blocked", "reason": "no_peer_registry"},
                    "international": {"status": "blocked", "reason": "no_international_registry"},
                    "financial": {"status": "blocked", "reason": "no_period_aligned_financials"},
                    "causal": {"status": "blocked", "reason": "descriptive_not_causal"},
                    "forecast": {"status": "blocked", "reason": "not_implemented"},
                    "valuation": {"status": "blocked", "reason": "not_implemented"},
                },
            })
        companies[symbol] = {"symbol": symbol, "status": "benchmarks_available" if benchmarks else "no_operating_events", "benchmark_count": len(benchmarks), "benchmarks": benchmarks, "blocked_states": {"peer": {"status": "blocked", "reason": "no_peer_registry"}, "international": {"status": "blocked", "reason": "no_international_registry"}, "financial": {"status": "blocked", "reason": "no_period_aligned_financials"}, "causal": {"status": "blocked", "reason": "descriptive_not_causal"}}, "policy": {"descriptive_only": True, "strict_no_lookahead": True, "minimum_sample_three": True, "no_browser_matching": True}, "limitations": ["Current-sector membership can introduce survivorship bias.", "Raw price returns are not adjusted or total returns.", "Historical association is not causal."]}
    return {"schema_version": 1, "benchmark_version": "conditional_benchmarks_v1", "pilot_symbols": pilot, "companies": companies, "policy": {"descriptive_only": True, "no_causal_claim": True, "no_forecast_or_valuation": True, "no_advice": True}, "source": ["state/company_intel/operating_events.json", "state/company_intel/event_studies.json", "state/sectors.json"]}
