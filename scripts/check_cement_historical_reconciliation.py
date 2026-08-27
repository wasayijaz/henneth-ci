#!/usr/bin/env python3
"""Focused guardrails for the non-activating Cement historical reconciliation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cement_historical_reconciliation import POLICY, build_state


def source(metric: str, period: str) -> dict:
    return {"document_id": "psx:1", "fact_id": "fact_" + metric + "_" + period, "content_sha256": "a" * 64, "source_url": "https://dps.psx.com.pk/download/document/1.pdf", "page": 2, "text": "reported annual line", "available_on": "2025-08-01"}


def fact(metric: str, period: str, value: float, available: str = "2025-08-01") -> dict:
    row = {"metric": metric, "period_end": period, "period_type": "annual", "duration_months": 12, "statement_type": "income_statement", "consolidation": "consolidated", "currency": "PKR", "unit": "PKR/share" if metric == "basic_eps" else "PKR", "unit_multiplier": 1, "normalized_value": value, "status": "eligible", "source": source(metric, period)}
    row["source"]["available_on"] = available
    return row


def main() -> None:
    facts = [fact(metric, period, value) for period in ("2022-06-30", "2023-06-30", "2024-06-30") for metric, value in (("revenue", 100), ("profit_after_tax_attributable", 10), ("basic_eps", 1))]
    def qualified(count=3):
        periods = ("2022-06-30", "2023-06-30", "2024-06-30")[:count]
        return [{"period_end": period, "available_on": "2025-08-01", "source_fact_ids": {metric: "fact_" + metric + "_" + period for metric in ("revenue", "profit_after_tax_attributable", "basic_eps")}} for period in periods]
    financial = {"as_of": "2025-12-31", "companies": {"DGKC": {"facts": facts, "qualified_periods": qualified()}, "MLCF": {"facts": facts, "qualified_periods": qualified()}, "LUCK": {"facts": facts[:6], "qualified_periods": qualified(2)}}}
    cement = {"companies": {symbol: {"observation_count": 1, "metrics": {"cement_sales_total": [{"metric": "cement_sales_total", "readiness": "audit_only", "model_eligibility": "not_model_loadable", "source": {"available_on": None, "source_registry_status": "discovered"}}]}} for symbol in ("DGKC", "MLCF", "LUCK")}}
    state = build_state(financial, cement, as_of="2025-12-31")
    for symbol in ("DGKC", "MLCF"):
        row = state["companies"][symbol]
        assert row["qualified_financial_period_count"] == 3
        assert row["status"] == "blocked_missing_model_loadable_operating_drivers"
        assert row["adapter_status"] == "unavailable"
    assert state["companies"]["LUCK"]["status"] == "blocked_insufficient_qualified_financial_history"
    assert all(row["status"] == "missing" for row in state["companies"]["DGKC"]["driver_lanes"].values())
    future = fact("revenue", "2025-06-30", 200, "2026-01-01")
    financial["companies"]["DGKC"]["facts"].append(future)
    assert build_state(financial, cement, as_of="2025-12-31")["companies"]["DGKC"]["qualified_financial_period_count"] == 3
    serialized = json.dumps(state).lower()
    for forbidden in ("fair_value", "target_price", "forecast_value"):
        assert forbidden not in serialized
    assert POLICY["no_adapter_registration"] and POLICY["no_numeric_forecast"]
    print("cement historical reconciliation: PASS (source-gated historical actuals; no adapter activation)")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"cement historical reconciliation: FAIL {exc}")
        raise
