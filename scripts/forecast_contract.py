"""Forecast/Valuation Readiness Contract v1.

This module is a gate, not a forecast engine. It only decides whether the
retained official financial facts are complete enough for downstream numeric
forecast, valuation, and market-expectations work to become eligible.
"""
from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

from financial_statement_facts import PARSER_REVISION, PARSER_VERSION
from manual_financial_claims import is_qualified_manual_fact
from sector_driver_models import COMPANY_OVERRIDES, SECTOR_MODELS, model_for_company


CONTRACT_VERSION = "forecast_readiness_contract_v1"
REQUIRED_LINES = ("revenue", "profit_after_tax_attributable", "basic_eps")
REQUIRED_PERIOD_COUNT = 3
BLOCKED_OUTPUT_STATUS = {
    "forecast": "blocked_insufficient_qualified_history",
    "valuation": "blocked_insufficient_qualified_history",
    "market_expectations": "blocked_insufficient_qualified_history",
}
ADAPTER_UNAVAILABLE_OUTPUT_STATUS = {
    "forecast": "blocked_model_adapter_unavailable",
    "valuation": "blocked_model_adapter_unavailable",
    "market_expectations": "blocked_model_adapter_unavailable",
}
REGISTRY_UNAVAILABLE_OUTPUT_STATUS = {
    "forecast": "blocked_unsupported_sector_model",
    "valuation": "blocked_unsupported_sector_model",
    "market_expectations": "blocked_unsupported_sector_model",
}
POLICIES = {
    "research_only": True,
    "no_numeric_forecast": True,
    "no_numeric_valuation": True,
    "no_market_expectations_output": True,
    "official_sources_only": True,
    "no_model_output_from_partial_history": True,
}
REGISTRY_VERSION_BY_SECTOR = {
    "BANKS": "banks_v1",
    "CEMENT": "cement_v1",
    "E&P": "e_and_p_v1",
    "REFINERY": "refinery_v1",
    "FERTILIZER": "fertilizer_v1",
    "AUTO_ASSEMBLER": "auto_assembler_v1",
    "POWER": "power_v1",
    "OMC": "omc_v1",
    "HOLDING_COMPANY": "holding_company_v1",
}
EXECUTABLE_NUMERIC_ADAPTERS_BY_SECTOR: dict[str, str] = {}
QUALITY_FLAG_FIELDS = ("quality_flags", "conflict_flags")


def selected_sector(symbol: str, exchange_sector: str | None) -> str | None:
    model = model_for_company(symbol, exchange_sector)
    return model.get("sector") if model else None


def selected_registry_version(symbol: str, exchange_sector: str | None) -> str | None:
    sector = selected_sector(symbol, exchange_sector)
    return REGISTRY_VERSION_BY_SECTOR.get(sector or "")


def selected_adapter_version(symbol: str, exchange_sector: str | None) -> str | None:
    sector = selected_sector(symbol, exchange_sector)
    return EXECUTABLE_NUMERIC_ADAPTERS_BY_SECTOR.get(sector or "")


def registry_status(symbol: str, exchange_sector: str | None) -> dict[str, Any]:
    sector = selected_sector(symbol, exchange_sector)
    model = model_for_company(symbol, exchange_sector)
    return {
        "status": "covered" if model else "unsupported_sector_model",
        "coverage_type": "qualitative_sector_driver_registry",
        "exchange_sector": exchange_sector,
        "selected_sector": sector,
        "registry_version": REGISTRY_VERSION_BY_SECTOR.get(sector or ""),
        "registry_source": "sector_driver_models.SECTOR_MODELS",
        "company_override": COMPANY_OVERRIDES.get(str(symbol).upper()),
        "drivers": (model or {}).get("drivers") or [],
    }


def adapter_status(symbol: str, exchange_sector: str | None) -> dict[str, Any]:
    sector = selected_sector(symbol, exchange_sector)
    adapter_version = EXECUTABLE_NUMERIC_ADAPTERS_BY_SECTOR.get(sector or "")
    if adapter_version:
        status = "available"
        reason = None
    elif sector:
        status = "unavailable"
        reason = "blocked_model_adapter_unavailable"
    else:
        status = "unsupported_sector_model"
        reason = "unsupported_sector_model"
    return {
        "status": status,
        "availability_type": "executable_numerical_adapter",
        "selected_sector": sector,
        "adapter_version": adapter_version,
        "adapter_source": None,
        "reason": reason,
    }


def supported_registry_versions() -> dict[str, str]:
    return {sector: REGISTRY_VERSION_BY_SECTOR[sector] for sector in SECTOR_MODELS}


def available_adapter_versions() -> dict[str, str]:
    return dict(EXECUTABLE_NUMERIC_ADAPTERS_BY_SECTOR)


def _num(value: Any) -> float | int | None:
    import math
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return None


def _fact_value(fact: dict[str, Any]) -> float | int | None:
    return _num(fact.get("normalized_value"))


def _has_quality_flags(fact: dict[str, Any]) -> bool:
    for field in QUALITY_FLAG_FIELDS:
        flags = fact.get(field)
        if isinstance(flags, list) and flags:
            return True
    return False


def official_financial_fact_provenance(fact: dict[str, Any]) -> bool:
    """Accept direct PSX PDFs or exact qualified issuer-registry bindings."""
    evidence = fact.get("evidence") or []
    first_evidence = evidence[0] if evidence and isinstance(evidence[0], dict) else {}
    source_url = str(fact.get("source_url") or "")
    base = (
        str(fact.get("fact_id") or "")
        and str(fact.get("content_sha256") or "")
        and isinstance(first_evidence.get("page"), int)
        and not isinstance(first_evidence.get("page"), bool)
        and first_evidence.get("page") >= 1
        and str(first_evidence.get("text") or "")
        and first_evidence.get("source_url") == source_url
    )
    if not base:
        return False
    if str(fact.get("document_id") or "").startswith("psx:"):
        return bool(source_url.startswith("https://dps.psx.com.pk/"))
    if not str(fact.get("document_id") or "").startswith("issuer:"):
        return False
    content_hash = str(fact.get("content_sha256") or "")
    if len(content_hash) != 64 or any(char not in "0123456789abcdefABCDEF" for char in content_hash):
        return False
    binding = fact.get("issuer_registry_binding")
    if not isinstance(binding, dict) or binding.get("status") != "qualified":
        return False
    link_url = str(binding.get("source_url") or "")
    source_page = str(binding.get("source_page") or "")
    def _host(value: str) -> str:
        text = value.lower().rstrip(".")
        return text[4:] if text.startswith("www.") else text
    root_domain = _host(str(binding.get("root_domain") or ""))
    host = _host(urlparse(source_url).hostname or "")
    page_host = _host(urlparse(source_page).hostname or "")
    return (
        str(binding.get("document_id") or "") == str(fact.get("document_id") or "")
        and str(binding.get("link_id") or "") == str(fact.get("document_id") or "")
        and link_url == source_url
        and str(binding.get("content_sha256") or "") == str(fact.get("content_sha256") or "")
        and source_url.startswith("https://")
        and source_url.lower().endswith(".pdf")
        and bool(root_domain and (host == root_domain or host.endswith("." + root_domain))
                 and (page_host == root_domain or page_host.endswith("." + root_domain)))
        and binding.get("evidence_page") == first_evidence.get("page")
    )


def _official_fact(fact: dict[str, Any]) -> bool:
    return official_financial_fact_provenance(fact)


def _iso_date(value: Any) -> str | None:
    text = str(value or "")
    try:
        date.fromisoformat(text)
        return text
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def qualified_financial_fact_source(fact: dict[str, Any]) -> bool:
    return (
        (
            fact.get("parser_version") == PARSER_VERSION
            and fact.get("parser_revision") == PARSER_REVISION
        )
        or is_qualified_manual_fact(fact)
    )


def _base_fact_ok(fact: dict[str, Any]) -> bool:
    period_end = _iso_date(fact.get("period_end"))
    available_on = _iso_date(fact.get("available_on"))
    return (
        qualified_financial_fact_source(fact)
        and fact.get("readiness") == "model_loadable"
        and fact.get("duration_months") == 12
        and fact.get("period_type") == "annual"
        and fact.get("consolidation") == "consolidated"
        and fact.get("currency") == "PKR"
        and fact.get("statement_type") == "income_statement"
        and period_end is not None
        and available_on is not None
        and available_on > period_end
        and _fact_value(fact) is not None
        and _official_fact(fact)
        and not _has_quality_flags(fact)
    )


def _dedup(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for fact in facts:
        key = (
            fact.get("line"),
            fact.get("period_end"),
            fact.get("consolidation"),
            fact.get("currency"),
            fact.get("statement_type"),
            fact.get("unit"),
            fact.get("unit_multiplier"),
        )
        grouped.setdefault(key, []).append(fact)
    selected = []
    for rows in grouped.values():
        values = {_fact_value(row) for row in rows}
        if len(values) == 1:
            selected.append(sorted(rows, key=lambda row: str(row.get("fact_id") or ""))[0])
    return sorted(selected, key=lambda row: (str(row.get("period_end") or ""), str(row.get("fact_id") or "")))


def qualified_periods(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_line = {
        line: _dedup([
            fact for fact in facts
            if isinstance(fact, dict) and fact.get("line") == line and _base_fact_ok(fact)
        ])
        for line in REQUIRED_LINES
    }
    rows = []
    periods = sorted(set.intersection(*(set(f.get("period_end") for f in by_line[line]) for line in REQUIRED_LINES))) if all(by_line.values()) else []
    for period_end in periods:
        revs = [f for f in by_line["revenue"] if f.get("period_end") == period_end]
        pats = [f for f in by_line["profit_after_tax_attributable"] if f.get("period_end") == period_end]
        epss = [f for f in by_line["basic_eps"] if f.get("period_end") == period_end]
        for revenue in revs:
            for pat in pats:
                same_money = (
                    revenue.get("consolidation") == pat.get("consolidation")
                    and revenue.get("currency") == pat.get("currency")
                    and revenue.get("statement_type") == pat.get("statement_type")
                and revenue.get("unit") == "PKR"
                and pat.get("unit") == "PKR"
                and revenue.get("unit_multiplier") == pat.get("unit_multiplier")
            )
                if not same_money:
                    continue
                for eps in epss:
                    same_context = (
                        revenue.get("consolidation") == eps.get("consolidation")
                        and revenue.get("currency") == eps.get("currency")
                        and revenue.get("statement_type") == eps.get("statement_type")
                    )
                    eps_scale = eps.get("unit_multiplier") == 1 and eps.get("unit") == "PKR/share"
                    if same_context and eps_scale:
                        rows.append({
                            "period_end": period_end,
                            "available_on": max(revenue.get("available_on") or "", pat.get("available_on") or "", eps.get("available_on") or ""),
                            "consolidation": revenue.get("consolidation"),
                            "currency": revenue.get("currency"),
                            "statement_type": revenue.get("statement_type"),
                            "monetary_unit": revenue.get("unit"),
                            "monetary_unit_multiplier": revenue.get("unit_multiplier"),
                            "eps_unit": eps.get("unit"),
                            "eps_unit_multiplier": eps.get("unit_multiplier"),
                            "source_fact_ids": {
                                "revenue": revenue.get("fact_id"),
                                "profit_after_tax_attributable": pat.get("fact_id"),
                                "basic_eps": eps.get("fact_id"),
                            },
                            "document_ids": sorted({revenue.get("document_id"), pat.get("document_id"), eps.get("document_id")}),
                        })
                        break
                if rows and rows[-1].get("period_end") == period_end:
                    break
            if rows and rows[-1].get("period_end") == period_end:
                break
    return rows


def readiness_row(symbol: str, exchange_sector: str | None, facts: list[dict[str, Any]], coverage_row: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry_status(symbol, exchange_sector)
    adapter = adapter_status(symbol, exchange_sector)
    periods = qualified_periods(facts)
    missing = []
    if registry["status"] != "covered":
        missing.append("qualitative_sector_driver_registry")
    if len(periods) < REQUIRED_PERIOD_COUNT:
        missing.append("three_aligned_annual_revenue_pat_eps_periods")
    history_ready = len(periods) >= REQUIRED_PERIOD_COUNT
    registry_ready = registry["status"] == "covered"
    if history_ready and registry_ready and adapter["status"] == "available":
        status = "input_ready"
        activation_status = "input_ready"
        downstream = {key: "input_ready" for key in ("forecast", "valuation", "market_expectations")}
    elif history_ready and registry_ready:
        missing.append("executable_numerical_adapter")
        status = "blocked_model_adapter_unavailable"
        activation_status = "blocked_model_adapter_unavailable"
        downstream = dict(ADAPTER_UNAVAILABLE_OUTPUT_STATUS)
    elif not history_ready:
        status = "blocked_insufficient_qualified_history"
        activation_status = "blocked_insufficient_qualified_history"
        downstream = dict(BLOCKED_OUTPUT_STATUS)
    else:
        status = "blocked_unsupported_sector_model"
        activation_status = "blocked_unsupported_sector_model"
        downstream = dict(REGISTRY_UNAVAILABLE_OUTPUT_STATUS)
    candidates = (((coverage_row or {}).get("qualification_queue") or {}).get("candidate_documents")) or []
    candidate_refs = [{
        "document_id": row.get("document_id"),
        "published_at": row.get("published_at"),
        "title": row.get("title"),
        "source_url": row.get("source_url"),
        "reason": row.get("reason"),
        "safe_period": row.get("safe_period"),
    } for row in candidates if row.get("document_id") and row.get("source_url")]
    downstream["numeric_impact"] = (
        status if status.startswith("blocked_") else "blocked_model_adapter_unavailable"
    )
    return {
        "symbol": symbol,
        "status": status,
        "activation_status": activation_status,
        "contract_version": CONTRACT_VERSION,
        "model_registry": registry,
        "model_adapter": adapter,
        "registry_version": registry.get("registry_version"),
        "adapter_version": adapter.get("adapter_version"),
        "qualified_period_count": len(periods),
        "qualified_periods": periods,
        "missing_requirements": missing,
        "coverage_candidate_document_ids": [row.get("document_id") for row in candidates if row.get("document_id")],
        "qualification_candidate_document_refs": candidate_refs,
        "blocked_outputs": {key: value for key, value in downstream.items() if key != "numeric_impact"},
        "downstream_status": downstream,
        "policy": {
            "forecasts": "blocked_until_qualified_history_and_executable_adapter",
            "valuation": "blocked_until_qualified_history_and_executable_adapter",
            "market_expectations": "blocked_until_qualified_history_and_executable_adapter",
            "numeric_impact": "blocked_until_sourced_operands_and_implementation",
        },
        "limitations": [
            "Sector driver coverage is qualitative registry coverage, not an implemented forecast or valuation model.",
            "Executable numerical adapter availability is tracked separately and is currently unavailable for every registry.",
            "Audit-only, conflicting, non-annual, non-consolidated, or weak-provenance facts cannot activate the gate.",
        ],
        "quality_flags": [] if status == "input_ready" else [status],
    }
