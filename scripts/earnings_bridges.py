"""Source-linked historical earnings bridges for Company Intelligence.

This is a descriptive historical product.  It deliberately consumes neither
owner forward assumptions nor model-adapter readiness, and it cannot activate
forecast, valuation, or market-expectations engines.
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "earnings_bridges.json"
PRODUCT_VERSION = "historical_earnings_bridge_v1"
METRICS = ("revenue", "profit_after_tax_attributable", "basic_eps")


def _date(value: Any) -> date | None:
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _stable_id(*parts: Any) -> str:
    text = "\x1f".join(str(part or "") for part in parts)
    return "ebr_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _eligible_annual_fact(record: dict[str, Any], as_of: date | None) -> bool:
    source = record.get("source") or {}
    available = _date(source.get("available_on"))
    return (
        record.get("status") == "eligible"
        and record.get("metric") in METRICS
        and record.get("period_type") == "annual"
        and record.get("duration_months") == 12
        and record.get("statement_type") == "income_statement"
        and record.get("consolidation") == "consolidated"
        and record.get("currency") == "PKR"
        and _date(record.get("period_end")) is not None
        and available is not None
        and (as_of is None or available <= as_of)
        and _number(record.get("normalized_value")) is not None
        and source.get("fact_id")
        and source.get("document_id")
        and source.get("source_url")
        and source.get("content_sha256")
        and isinstance(source.get("page"), int)
        and source.get("page") > 0
        and source.get("text")
    )


def _periods(records: list[dict[str, Any]], as_of: date | None) -> tuple[list[dict[str, Any]], list[str]]:
    slots: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        if not _eligible_annual_fact(record, as_of):
            continue
        slots.setdefault(str(record["period_end"]), {}).setdefault(str(record["metric"]), []).append(record)
    rows: list[dict[str, Any]] = []
    blocked: list[str] = []
    for period_end, by_metric in sorted(slots.items()):
        if set(by_metric) != set(METRICS):
            blocked.append(period_end)
            continue
        if any(len(by_metric[metric]) != 1 for metric in METRICS):
            blocked.append(period_end)
            continue
        rows.append({
            "period_end": period_end,
            "facts": {metric: by_metric[metric][0] for metric in METRICS},
        })
    return rows, sorted(set(blocked))


def _consecutive(previous: str, current: str) -> bool:
    older, newer = _date(previous), _date(current)
    return bool(older and newer and newer.year == older.year + 1 and (newer.month, newer.day) == (older.month, older.day))


def _source(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("source") or {}
    return {
        "fact_id": source.get("fact_id"),
        "document_id": source.get("document_id"),
        "source_url": source.get("source_url"),
        "content_sha256": source.get("content_sha256"),
        "page": source.get("page"),
        "text": source.get("text"),
        "available_on": source.get("available_on"),
    }


def _bridge(symbol: str, previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    availability: list[str] = []
    for metric in METRICS:
        old = previous["facts"][metric]
        new = current["facts"][metric]
        old_value = _number(old.get("normalized_value"))
        new_value = _number(new.get("normalized_value"))
        assert old_value is not None and new_value is not None
        old_source, new_source = _source(old), _source(new)
        availability.extend([str(old_source["available_on"]), str(new_source["available_on"])])
        metrics[metric] = {
            "previous_value": old_value,
            "current_value": new_value,
            "change_amount": new_value - old_value,
            "change_pct": None if old_value == 0 else (new_value / old_value - 1) * 100,
            "unit": old.get("unit"),
            "unit_multiplier": old.get("unit_multiplier"),
            "previous_source": old_source,
            "current_source": new_source,
        }
    return {
        "bridge_id": _stable_id(symbol, previous["period_end"], current["period_end"]),
        "symbol": symbol,
        "bridge_type": "historical_reported_annual_change",
        "intelligence_type": "derived_fact",
        "status": "historical_descriptive_only",
        "previous_period_end": previous["period_end"],
        "period_end": current["period_end"],
        "available_on": max(availability),
        "formula_version": PRODUCT_VERSION,
        "metrics": metrics,
        "quality_flags": ["not_a_forecast", "not_owner_assumption", "no_formal_engine_activation"],
    }


def company_bridge(symbol: str, reconciliation: dict[str, Any], as_of: str | None) -> dict[str, Any]:
    cutoff = _date(as_of)
    records = reconciliation.get("facts") or []
    periods, blocked_periods = _periods([row for row in records if isinstance(row, dict)], cutoff)
    bridges = [
        _bridge(symbol, prior, current)
        for prior, current in zip(periods, periods[1:])
        if _consecutive(prior["period_end"], current["period_end"])
    ]
    status = "historical_bridge_available" if bridges else "blocked_insufficient_conflict_free_aligned_history"
    return {
        "symbol": symbol,
        "status": status,
        "bridge_count": len(bridges),
        "qualified_period_count": len(periods),
        "blocked_periods": blocked_periods,
        "bridges": bridges,
        "formal_engine_status": {
            "forecast": "not_activated",
            "valuation": "not_activated",
            "market_expectations": "not_activated",
        },
        "quality_flags": [] if bridges else ["insufficient_conflict_free_aligned_annual_history"],
    }


def build_state(reconciliation_state: dict[str, Any], pilot_symbols: list[str] | None = None) -> dict[str, Any]:
    pilot = list(pilot_symbols or reconciliation_state.get("pilot_symbols") or [])
    as_of = reconciliation_state.get("as_of")
    companies = {
        symbol: company_bridge(symbol, (reconciliation_state.get("companies") or {}).get(symbol) or {}, as_of)
        for symbol in pilot
    }
    return {
        "schema_version": 1,
        "product_version": PRODUCT_VERSION,
        "as_of": as_of,
        "pilot_symbols": pilot,
        "source": "state/company_intel/financial_evidence_reconciliation.json",
        "policy": {
            "historical_descriptive_only": True,
            "official_eligible_facts_only": True,
            "no_lookahead": True,
            "no_owner_forward_assumptions": True,
            "formal_engine_eligibility_unchanged": True,
        },
        "summary": {
            "company_count": len(companies),
            "company_with_bridge_count": sum(1 for row in companies.values() if row["bridge_count"]),
            "bridge_count": sum(row["bridge_count"] for row in companies.values()),
        },
        "companies": companies,
    }


def build() -> dict[str, Any]:
    result = build_state(load_json(STATE / "company_intel" / "financial_evidence_reconciliation.json", {}))
    save_json(OUT, result)
    print(f"earnings_bridges: {result['summary']['bridge_count']} historical bridges across {result['summary']['company_count']} companies")
    return result


if __name__ == "__main__":
    build()
