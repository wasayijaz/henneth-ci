"""Build a categorical causal-driver evidence map for Company Intelligence.

This is not a causal estimate. It is a resolver: every row starts from an
existing driver edge, then records whether local retained events and strict
no-lookahead event studies currently support research on that edge.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from psx_data import STATE, load_json, save_json

OUT = Path(os.environ.get("HENNETH_CAUSAL_OUT", STATE / "company_intel" / "causal_foundations.json"))


def _stable_id(*parts):
    raw = "|".join(str(part or "") for part in parts)
    return "cause_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _edge_id(symbol, edge):
    return _stable_id(symbol, edge.get("from"), edge.get("to"), edge.get("statement_line"), edge.get("unit"), edge.get("basis"))


def _event_driver_links(events, driver):
    linked = []
    for event in events:
        if driver not in (event.get("affected_drivers") or []):
            continue
        linked.append({
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "effective_date": event.get("effective_date"),
            "source_url": event.get("source_url"),
        })
    return linked


def _study_ref(study, event, symbol):
    if not study or study.get("symbol") != symbol or study.get("event_id") != event.get("event_id"):
        return None
    baseline_date = ((study or {}).get("baseline") or {}).get("selected_date")
    effective_date = event.get("effective_date")
    if study.get("effective_date") != effective_date:
        return None
    strict = bool(
        baseline_date and effective_date and baseline_date < effective_date
        and ((study.get("baseline") or {}).get("status") == "available")
    )
    return {
        "study_id": study.get("study_id"),
        "event_id": study.get("event_id"),
        "strict_no_lookahead": strict,
        "baseline_status": ((study.get("baseline") or {}).get("status") or "unknown"),
    }


def _status(event_refs, study_refs):
    if study_refs:
        if any(ref.get("strict_no_lookahead") and ref.get("baseline_status") == "available" for ref in study_refs):
            return "observed_event_with_strict_study"
        return "observed_event_study_blocked"
    if event_refs:
        return "observed_event_no_study"
    return "driver_edge_only"


def _next_requirement(status):
    return {
        "observed_event_with_strict_study": "period_aligned_financial_outcomes_required",
        "observed_event_study_blocked": "strict_event_study_baseline_required",
        "observed_event_no_study": "event_study_required",
        "driver_edge_only": "retained_official_event_link_required",
    }.get(status, "manual_review_required")


def build():
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = (profiles.get("pilot") or {}).get("symbols") or []
    driver_graphs = load_json(STATE / "company_intel" / "driver_graphs.json", {"companies": {}})
    operating_events = load_json(STATE / "company_intel" / "operating_events.json", {"companies": {}})
    studies = load_json(STATE / "company_intel" / "event_studies.json", {"studies": {}}).get("studies") or {}

    companies = {}
    for sym in pilot:
        graph = (driver_graphs.get("companies") or {}).get(sym) or {}
        events = [event for event in (((operating_events.get("companies") or {}).get(sym) or {}).get("events") or []) if event.get("event_id") and event.get("symbol") == sym and event.get("company_id") == sym]
        events_by_id = {event.get("event_id"): event for event in events if event.get("event_id")}
        rows = []
        for edge in graph.get("edges") or []:
            driver = edge.get("from")
            event_refs = _event_driver_links(events, driver)
            event_refs.sort(key=lambda ref: (ref.get("effective_date") or "", ref.get("event_id") or ""), reverse=True)
            study_refs = [
                ref for ref in (
                _study_ref(studies[event_ref["event_id"]], events_by_id[event_ref["event_id"]], sym)
                for event_ref in event_refs
                if event_ref.get("event_id") in studies
                ) if ref is not None
            ][:6]
            event_refs = event_refs[:6]
            evidence_status = _status(event_refs, study_refs)
            rows.append({
                "causal_id": _edge_id(sym, edge),
                "symbol": sym,
                "edge_id": _edge_id(sym, edge),
                "driver": driver,
                "target": edge.get("to"),
                "statement_line": edge.get("statement_line"),
                "unit": edge.get("unit"),
                "edge_basis": edge.get("basis"),
                "evidence_status": evidence_status,
                "event_refs": event_refs,
                "event_study_refs": study_refs,
                "next_data_requirement": _next_requirement(evidence_status),
                "policy": {
                    "numeric_impact": "blocked",
                    "forecast": "blocked",
                    "valuation": "blocked",
                },
            })
        rows.sort(key=lambda row: (row.get("evidence_status") or "", row.get("driver") or "", row.get("target") or "", row.get("statement_line") or "", row.get("unit") or "", row.get("edge_id") or ""))
        companies[sym] = {
            "symbol": sym,
            "sector": graph.get("sector"),
            "causal_rows": rows,
            "coverage": {
                "driver_edge_count": len(graph.get("edges") or []),
                "causal_row_count": len(rows),
                "observed_event_rows": sum(1 for row in rows if row.get("event_refs")),
                "strict_study_rows": sum(1 for row in rows if any(ref.get("strict_no_lookahead") for ref in row.get("event_study_refs") or [])),
            },
        }

    result = {
        "schema_version": 1,
        "built": "deterministic_from_local_state",
        "pilot_symbols": pilot,
        "companies": companies,
        "source": [
            "state/company_intel/driver_graphs.json",
            "state/company_intel/operating_events.json",
            "state/company_intel/event_studies.json",
        ],
        "policy": {
            "categorical_status_only": True,
            "no_numeric_impact": True,
            "no_forecast_probability_valuation_or_price": True,
            "macro_skipped_no_stable_test_ids": True,
        },
    }
    save_json(OUT, result)
    print(f"causal_foundations: {sum(len(v['causal_rows']) for v in companies.values())} rows across {len(companies)} companies")
    return result


if __name__ == "__main__":
    build()
