#!/usr/bin/env python3
"""Source-gated Cement historical reconciliation; never a forecast adapter.

Financial actuals may be reconciled only when the existing financial-evidence
product already classifies them as eligible.  Cement operating snippets are a
separate lane: audit-only observations cannot become model inputs merely by
being present beside qualified income-statement facts.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "cement_historical_reconciliation.json"
CEMENT_SYMBOLS = ("MLCF", "DGKC", "LUCK")
REQUIRED_METRICS = ("revenue", "profit_after_tax_attributable", "basic_eps")
DRIVER_LANES = {
    "dispatch_volume": {"cement_sales_total"},
    "realized_price_or_revenue_per_tonne": {"realized_price", "revenue_per_tonne"},
    "cost_input": {"coal_cost_per_tonne", "power_cost_per_tonne", "fuel_cost_per_tonne"},
    "capacity": {"capacity_tonnes", "cement_capacity_tonnes"},
}
POLICY = {
    "historical_actuals_only": True,
    "no_audit_only_promotion": True,
    "no_lookahead": True,
    "no_adapter_registration": True,
    "no_numeric_forecast": True,
    "no_numeric_valuation": True,
    "no_market_expectations_output": True,
}


def _day(value: Any) -> str | None:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _source_ok(source: Any, cutoff: str) -> bool:
    if not isinstance(source, dict):
        return False
    available_on = _day(source.get("available_on"))
    content_hash = str(source.get("content_sha256") or "")
    return (
        available_on is not None and available_on <= cutoff
        and bool(source.get("document_id") and source.get("fact_id") and source.get("source_url") and source.get("text"))
        and isinstance(source.get("page"), int) and not isinstance(source.get("page"), bool) and source["page"] > 0
        and len(content_hash) == 64 and all(char in "0123456789abcdefABCDEF" for char in content_hash)
    )


def _financial_ok(fact: Any, cutoff: str) -> bool:
    if not isinstance(fact, dict) or fact.get("status") != "eligible":
        return False
    period_end = _day(fact.get("period_end"))
    available_on = _day((fact.get("source") or {}).get("available_on"))
    value = fact.get("normalized_value")
    return (
        fact.get("metric") in REQUIRED_METRICS
        and fact.get("period_type") == "annual" and fact.get("duration_months") == 12
        and fact.get("statement_type") == "income_statement" and fact.get("consolidation") == "consolidated"
        and fact.get("currency") == "PKR" and period_end is not None and available_on is not None
        and period_end < available_on <= cutoff and isinstance(value, (int, float)) and not isinstance(value, bool)
        and _source_ok(fact.get("source"), cutoff)
    )


def _qualified_periods(financial_row: dict[str, Any], cutoff: str) -> list[dict[str, Any]]:
    eligible_by_id = {
        str((fact.get("source") or {}).get("fact_id")): fact
        for fact in financial_row.get("facts") or []
        if _financial_ok(fact, cutoff)
    }
    periods: list[dict[str, Any]] = []
    # The upstream reconciliation owns duplicate/conflict treatment.  Reusing
    # its qualified slots avoids silently choosing among competing evidence.
    for qualified in financial_row.get("qualified_periods") or []:
        if not isinstance(qualified, dict):
            continue
        period_end = _day(qualified.get("period_end"))
        available_on = _day(qualified.get("available_on"))
        ids = qualified.get("source_fact_ids") or {}
        if period_end is None or available_on is None or not period_end < available_on <= cutoff:
            continue
        rows = {metric: eligible_by_id.get(str(ids.get(metric) or "")) for metric in REQUIRED_METRICS}
        if any(row is None for row in rows.values()):
            continue
        if rows["revenue"].get("unit") != "PKR" or rows["revenue"].get("unit_multiplier") != rows["profit_after_tax_attributable"].get("unit_multiplier"):
            continue
        if rows["basic_eps"].get("unit") != "PKR/share" or rows["basic_eps"].get("unit_multiplier") != 1:
            continue
        periods.append({
            "period_end": period_end,
            "actuals": {
                metric: {
                    "value": rows[metric]["normalized_value"],
                    "unit": rows[metric].get("unit"),
                    "unit_multiplier": rows[metric].get("unit_multiplier"),
                    "source": rows[metric]["source"],
                }
                for metric in REQUIRED_METRICS
            },
        })
    return periods


def _driver_lanes(cement_row: dict[str, Any], cutoff: str) -> dict[str, dict[str, Any]]:
    observations = [
        observation
        for metrics in (cement_row.get("metrics") or {}).values()
        if isinstance(metrics, list)
        for observation in metrics if isinstance(observation, dict)
    ]
    result: dict[str, dict[str, Any]] = {}
    for lane, accepted_metrics in DRIVER_LANES.items():
        valid = []
        audit_only = 0
        for observation in observations:
            if observation.get("metric") not in accepted_metrics:
                continue
            source = observation.get("source") or {}
            available_on = _day(source.get("available_on"))
            loadable = (
                observation.get("readiness") == "model_loadable"
                and observation.get("model_eligibility") == "model_loadable"
                and source.get("source_registry_status") == "qualified"
                and available_on is not None and available_on <= cutoff
                and _source_ok({**source, "fact_id": (source.get("source_fact_ids") or [None])[0]}, cutoff)
            )
            if loadable:
                valid.append(observation)
            else:
                audit_only += 1
        result[lane] = {
            "status": "available" if valid else "missing",
            "model_loadable_observation_count": len(valid),
            "audit_or_unqualified_observation_count": audit_only,
            "accepted_metrics": sorted(accepted_metrics),
        }
    return result


def _company(symbol: str, financial: dict[str, Any], cement: dict[str, Any], cutoff: str) -> dict[str, Any]:
    financial_row = (financial.get("companies") or {}).get(symbol) or {}
    cement_row = (cement.get("companies") or {}).get(symbol) or {}
    periods = _qualified_periods(financial_row, cutoff)
    lanes = _driver_lanes(cement_row, cutoff)
    missing = [lane for lane, row in lanes.items() if row["status"] != "available"]
    if len(periods) < 3:
        status = "blocked_insufficient_qualified_financial_history"
    elif missing:
        status = "blocked_missing_model_loadable_operating_drivers"
    else:
        # This is deliberately still not an executable adapter.  A separately
        # reviewed model must register one before downstream engines can move.
        status = "historical_reconciliation_available_adapter_still_unavailable"
    return {
        "symbol": symbol,
        "status": status,
        "reconciliation_kind": "historical_actuals_only",
        "qualified_financial_period_count": len(periods),
        "qualified_financial_periods": periods,
        "driver_lanes": lanes,
        "missing_driver_lanes": missing,
        "audit_operating_observation_count": cement_row.get("observation_count", 0),
        "adapter_status": "unavailable",
        "downstream_status": {"financial_model_inputs": "not_activated", "forecast": "not_activated", "valuation": "not_activated", "market_expectations": "not_activated"},
    }


def build_state(financial: dict[str, Any], cement: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    cutoff = _day(as_of or financial.get("as_of")) or date.today().isoformat()
    companies = {symbol: _company(symbol, financial, cement, cutoff) for symbol in CEMENT_SYMBOLS}
    return {
        "schema_version": 1,
        "product_version": "cement_historical_reconciliation_v1",
        "as_of": cutoff,
        "source": {"financial_evidence_reconciliation": "state/company_intel/financial_evidence_reconciliation.json", "cement_operating_series": "state/company_intel/cement_operating_series.json"},
        "policy": POLICY,
        "companies": companies,
    }


def build() -> dict[str, Any]:
    state = build_state(
        load_json(STATE / "company_intel" / "financial_evidence_reconciliation.json", {"companies": {}}),
        load_json(STATE / "company_intel" / "cement_operating_series.json", {"companies": {}}),
    )
    save_json(OUT, state)
    print("cement_historical_reconciliation: " + ", ".join(f"{symbol}={row['status']}" for symbol, row in state["companies"].items()))
    return state


if __name__ == "__main__":
    build()
