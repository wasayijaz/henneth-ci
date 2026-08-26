"""Shared Company Brain vocabulary.

The brain is an index over existing intelligence products. It does not own the facts.
"""
from __future__ import annotations

from typing import Final

INTELLIGENCE_TYPES: Final[tuple[str, ...]] = (
    "reported_fact",
    "derived_fact",
    "inference",
    "scenario",
    "forecast",
)

BRAIN_DOMAINS: Final[tuple[str, ...]] = (
    "segments",
    "products",
    "facilities",
    "capacity",
    "customers",
    "suppliers",
    "employees",
    "management",
    "geography",
    "subsidiaries",
    "competitors",
    "financial_statements",
    "operating_kpis",
    "capital_allocation",
    "projects",
    "guidance",
    "risks",
    "catalysts",
    "historical_events",
    "forecasts",
    "valuation",
)

DOMAIN_STATUSES: Final[tuple[str, ...]] = ("available", "partial", "unknown", "blocked")

SOURCE_PRODUCTS: Final[tuple[str, ...]] = (
    "company_briefs",
    "operating_events",
    "event_studies",
    "financial_model_inputs",
    "financial_evidence_reconciliation",
    "financial_coverage",
    "forecast_readiness",
    "financial_forecasts",
    "formal_valuations",
    "market_expectations",
    "signal_clusters",
    "thesis_monitoring",
    "guidance_contradictions",
    "management_delivery",
    "intelligence_confidence",
    "scenario_lab",
    "impact_scenarios",
    "driver_graphs",
)

SOURCE_INDEX_PRODUCTS: Final[tuple[str, ...]] = (
    "operating_events",
    "financial_model_inputs",
    "financial_evidence_reconciliation",
    "financial_coverage",
    "forecast_readiness",
    "financial_forecasts",
    "formal_valuations",
    "market_expectations",
    "signal_clusters",
    "thesis_monitoring",
    "guidance_contradictions",
    "management_delivery",
    "intelligence_confidence",
    "scenario_lab",
    "impact_scenarios",
    "driver_graphs",
)
