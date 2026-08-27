"""Build deterministic source-bound assumptions for the formal engines.

This file emits objective market operands plus historical reference cases from
qualified reported annual observations.  Reference cases are not owner-approved
forecast inputs, so they deliberately do not expose the ``value`` field that the
formal engines require before computing numeric outputs.
"""
from __future__ import annotations

from datetime import date
import math
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from company_scenario_lab import parse_scaled
from forecast_contract import FORMAL_ENGINE_REQUIRED_APPROVED_RECORDS
from formal_financial_engines import approved_records
from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "financial_engine_assumptions.json"
BUILDER_ID = "build_financial_engine_assumptions.py"
GENERATED_SOURCE_PREFIX = "henneth_state:"
GENERATED_MARKET_METRICS = ("current_price", "shares_out")
GENERATED_REFERENCE_CASE_METRICS = ("revenue_growth_pct", "net_margin_pct")
GENERATED_METRICS = GENERATED_MARKET_METRICS + GENERATED_REFERENCE_CASE_METRICS
FORBIDDEN_GENERATED_MODEL_METRICS = ("exit_pe", "net_debt")
REFERENCE_CASE_FORMULA_VERSION = "financial_engine_assumptions_reference_case_v1"


def iso_date(value: Any) -> str | None:
    text = str(value or "")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def _state_date(state: dict[str, Any]) -> str | None:
    for key in ("updated", "as_of", "built"):
        parsed = iso_date(state.get(key))
        if parsed:
            return parsed
    meta = state.get("meta") or state.get("_meta") or {}
    if isinstance(meta, dict):
        for key in ("updated", "as_of", "built"):
            parsed = iso_date(meta.get(key))
            if parsed:
                return parsed
    return None


def _as_of(*states: dict[str, Any]) -> str | None:
    dates = [d for d in (_state_date(state) for state in states if isinstance(state, dict)) if d]
    return max(dates) if dates else None


def _pilot_symbols(profiles: dict[str, Any]) -> list[str]:
    symbols = (profiles.get("pilot") or {}).get("symbols") or []
    return [str(symbol).strip().upper() for symbol in symbols if str(symbol or "").strip()]


def _is_generated_record(record: dict[str, Any]) -> bool:
    source = record.get("source") or {}
    source_id = str(source.get("id") or "")
    return record.get("generated_by") == BUILDER_ID or source_id.startswith(GENERATED_SOURCE_PREFIX)


def _load_existing_records(path: Path) -> list[dict[str, Any]]:
    existing = load_json(path, {"records": []})
    return [dict(record) for record in existing.get("records") or [] if isinstance(record, dict)]


def _latest_history_close(state_dir: Path, symbol: str, cutoff: str | None) -> tuple[dict[str, Any] | None, str | None]:
    history_path = state_dir / "history" / f"{symbol}.json"
    rows = load_json(history_path, [])
    if not isinstance(rows, list):
        return None, "history_not_list"
    usable: list[dict[str, Any]] = []
    future_dates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_date = iso_date(row.get("date"))
        close = finite(row.get("close"))
        if not row_date or close is None or close <= 0:
            continue
        if cutoff and row_date > cutoff:
            future_dates.append(row_date)
            continue
        usable.append({"date": row_date, "close": close})
    if future_dates:
        return None, "history_date_after_source_state"
    if not usable:
        return None, "missing_valid_history_close"
    return sorted(usable, key=lambda row: row["date"])[-1], None


def _shares_out(fundamentals: dict[str, Any], symbol: str, cutoff: str | None) -> tuple[float | None, str | None, str | None]:
    row = (fundamentals.get("tickers") or {}).get(symbol) or {}
    if not isinstance(row, dict):
        return None, None, "missing_fundamentals_row"
    fetched = iso_date(row.get("fetched"))
    if not fetched:
        return None, None, "missing_fundamentals_fetched_date"
    if cutoff and fetched > cutoff:
        return None, fetched, "fundamentals_date_after_source_state"
    if not row.get("source_url"):
        return None, fetched, "missing_fundamentals_source_url"
    try:
        shares = parse_scaled(row.get("shares_out"))
    except (TypeError, ValueError):
        return None, fetched, "unparseable_shares_out"
    if shares <= 0:
        return None, fetched, "non_positive_shares_out"
    return shares, fetched, None


def _current_price_record(state_dir: Path, symbol: str, cutoff: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    latest, reason = _latest_history_close(state_dir, symbol, cutoff)
    if not latest:
        return None, {"symbol": symbol, "metric": "current_price", "reason": reason}
    available_on = latest["date"]
    return {
        "symbol": symbol,
        "metric": "current_price",
        "value": latest["close"],
        "unit": "PKR/share",
        "approved": True,
        "approval_scope": "deterministic_market_operand_only",
        "record_type": "approved_market_operand",
        "available_on": available_on,
        "generated_by": BUILDER_ID,
        "source": {
            "id": f"{GENERATED_SOURCE_PREFIX}history:{symbol}:{available_on}:close",
            "label": f"{symbol} retained PSX DPS daily close",
            "path": f"state/history/{symbol}.json",
            "url": f"https://dps.psx.com.pk/timeseries/eod/{symbol}",
            "available_on": available_on,
        },
    }, None


def _shares_out_record(fundamentals: dict[str, Any], symbol: str, cutoff: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    shares, fetched, reason = _shares_out(fundamentals, symbol, cutoff)
    if shares is None:
        return None, {"symbol": symbol, "metric": "shares_out", "reason": reason}
    row = (fundamentals.get("tickers") or {}).get(symbol) or {}
    return {
        "symbol": symbol,
        "metric": "shares_out",
        "value": shares,
        "unit": "shares",
        "approved": True,
        "approval_scope": "deterministic_market_operand_only",
        "record_type": "approved_market_operand",
        "available_on": fetched,
        "generated_by": BUILDER_ID,
        "source": {
            "id": f"{GENERATED_SOURCE_PREFIX}fundamentals:{symbol}:{fetched}:shares_out",
            "label": f"{symbol} retained shares-out field from fundamentals state",
            "path": "state/fundamentals.json",
            "url": row.get("source_url"),
            "available_on": fetched,
        },
    }, None


def _actual_lookup(model_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    observations = model_row.get("observations") or {}
    rows: dict[str, dict[str, Any]] = {}
    for line_rows in observations.values():
        if not isinstance(line_rows, list):
            continue
        for row in line_rows:
            if isinstance(row, dict) and row.get("fact_id"):
                rows[str(row["fact_id"])] = row
    return rows


def _source_fact_ref(line: str, row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence") or []
    pages = [
        item.get("page")
        for item in evidence
        if isinstance(item, dict) and item.get("page") is not None
    ]
    return {
        "line": line,
        "fact_id": row.get("fact_id"),
        "document_id": row.get("document_id"),
        "content_sha256": row.get("content_sha256"),
        "source_url": row.get("source_url"),
        "period_end": row.get("period_end"),
        "available_on": row.get("available_on") or row.get("availability"),
        "statement_type": row.get("statement_type"),
        "period_type": row.get("period_type"),
        "duration_months": row.get("duration_months"),
        "consolidation": row.get("consolidation"),
        "currency": row.get("currency"),
        "unit": row.get("unit"),
        "unit_multiplier": row.get("unit_multiplier"),
        "normalized_value": row.get("normalized_value"),
        "source_method": row.get("source_method") or row.get("parser_version"),
        "source_revision": row.get("source_revision") or row.get("parser_revision"),
        "evidence_pages": pages,
    }


def _qualified_actual(
    lookup: dict[str, dict[str, Any]],
    period: dict[str, Any],
    line: str,
    cutoff: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    fact_id = ((period.get("source_fact_ids") or {}).get(line))
    if not fact_id:
        return None, f"missing_qualified_{line}_fact_id"
    row = lookup.get(str(fact_id))
    if not row:
        return None, f"missing_qualified_{line}_fact"
    row_date = iso_date(row.get("available_on") or row.get("availability"))
    if not row_date:
        return None, f"missing_qualified_{line}_available_on"
    if cutoff and row_date > cutoff:
        return None, f"qualified_{line}_fact_after_source_state"
    value = finite(row.get("normalized_value"))
    if value is None:
        return None, f"non_finite_qualified_{line}"
    if row.get("readiness") not in (None, "model_loadable"):
        return None, f"unloadable_qualified_{line}"
    if row.get("period_type") != "annual" or row.get("duration_months") != 12:
        return None, f"non_annual_qualified_{line}"
    if row.get("consolidation") != "consolidated":
        return None, f"non_consolidated_qualified_{line}"
    if iso_date(row.get("period_end")) != iso_date(period.get("period_end")):
        return None, f"qualified_{line}_period_mismatch"
    if not row.get("source_url") or not row.get("document_id"):
        return None, f"missing_qualified_{line}_provenance"
    return row, None


def _reference_case_records(
    model_inputs: dict[str, Any],
    readiness: dict[str, Any],
    symbol: str,
    cutoff: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    model_row = (model_inputs.get("companies") or {}).get(symbol) or {}
    readiness_row = (readiness.get("companies") or {}).get(symbol) or {}
    history_qualified = (
        model_row.get("status") in {"ready", "blocked_model_adapter_unavailable"}
        and readiness_row.get("status") in {"input_ready", "blocked_model_adapter_unavailable"}
    )
    if not history_qualified:
        reason = "not_three_qualified_reported_annual_observations"
        return [], [
            {"symbol": symbol, "metric": metric, "reason": reason}
            for metric in GENERATED_REFERENCE_CASE_METRICS
        ]

    periods = [
        period for period in readiness_row.get("qualified_periods") or []
        if isinstance(period, dict) and iso_date(period.get("period_end"))
    ]
    periods = sorted(periods, key=lambda period: str(period.get("period_end")))[-3:]
    if len(periods) < 3:
        reason = "fewer_than_three_qualified_reported_annual_observations"
        return [], [
            {"symbol": symbol, "metric": metric, "reason": reason}
            for metric in GENERATED_REFERENCE_CASE_METRICS
        ]

    lookup = _actual_lookup(model_row)
    rows: list[dict[str, Any]] = []
    source_facts_by_metric = {"revenue_growth_pct": [], "net_margin_pct": []}
    for period in periods:
        revenue_row, revenue_reason = _qualified_actual(lookup, period, "revenue", cutoff)
        pat_row, pat_reason = _qualified_actual(lookup, period, "profit_after_tax_attributable", cutoff)
        if revenue_reason:
            return [], [{"symbol": symbol, "metric": metric, "reason": revenue_reason} for metric in GENERATED_REFERENCE_CASE_METRICS]
        if pat_reason:
            return [], [{"symbol": symbol, "metric": metric, "reason": pat_reason} for metric in GENERATED_REFERENCE_CASE_METRICS]
        assert revenue_row is not None and pat_row is not None
        revenue = finite(revenue_row.get("normalized_value"))
        pat = finite(pat_row.get("normalized_value"))
        if revenue is None or revenue <= 0:
            return [], [{"symbol": symbol, "metric": metric, "reason": "non_positive_qualified_revenue"} for metric in GENERATED_REFERENCE_CASE_METRICS]
        if pat is None:
            return [], [{"symbol": symbol, "metric": metric, "reason": "non_finite_qualified_profit_after_tax_attributable"} for metric in GENERATED_REFERENCE_CASE_METRICS]
        rows.append({
            "period_end": iso_date(period.get("period_end")),
            "revenue": revenue,
            "pat": pat,
            "revenue_fact": revenue_row,
            "pat_fact": pat_row,
        })
        source_facts_by_metric["revenue_growth_pct"].append(_source_fact_ref("revenue", revenue_row))
        source_facts_by_metric["net_margin_pct"].extend([
            _source_fact_ref("revenue", revenue_row),
            _source_fact_ref("profit_after_tax_attributable", pat_row),
        ])

    growth_rates: list[float] = []
    for previous, current in zip(rows, rows[1:]):
        years = (date.fromisoformat(current["period_end"]) - date.fromisoformat(previous["period_end"])).days / 365.2425
        if years <= 0:
            return [], [{"symbol": symbol, "metric": "revenue_growth_pct", "reason": "non_increasing_qualified_periods"}]
        growth_rates.append(((current["revenue"] / previous["revenue"]) ** (1.0 / years) - 1.0) * 100.0)
    margins = [row["pat"] / row["revenue"] * 100.0 for row in rows]
    available_on = max(
        iso_date(fact["available_on"]) or ""
        for facts in source_facts_by_metric.values()
        for fact in facts
    )
    period_ends = [row["period_end"] for row in rows]

    def record(metric: str, derived_value: float, source_facts: list[dict[str, Any]], formula: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "metric": metric,
            "derived_value": derived_value,
            "unit": "pct",
            "approved": False,
            "approval_scope": "historical_reference_case_not_owner_approved",
            "record_type": "derived_reference_case",
            "epistemic_type": "derived",
            "case_type": "reference_case",
            "assumption_status": "not_owner_approved_forecast_input",
            "available_on": available_on,
            "generated_by": BUILDER_ID,
            "formula_version": REFERENCE_CASE_FORMULA_VERSION,
            "period_ends": period_ends,
            "source": {
                "id": f"{GENERATED_SOURCE_PREFIX}financial_model_inputs:{symbol}:{metric}:{'-'.join(period_ends)}",
                "label": f"{symbol} historical reference-case {metric} from three qualified annual observations",
                "path": "state/company_intel/financial_model_inputs.json",
                "available_on": available_on,
            },
            "formula": formula,
            "source_facts": source_facts,
            "policy": {
                "historical_baseline_only": True,
                "not_owner_approved": True,
                "not_a_forecast": True,
                "not_accepted_by_formal_engine_approved_records": True,
            },
        }

    records = [
        record(
            "revenue_growth_pct",
            sum(growth_rates) / len(growth_rates),
            source_facts_by_metric["revenue_growth_pct"],
            {
                "name": "average_annualized_growth_between_three_reported_annual_revenue_observations",
                "interval_growth_rates_pct": growth_rates,
            },
        ),
        record(
            "net_margin_pct",
            sum(margins) / len(margins),
            source_facts_by_metric["net_margin_pct"],
            {
                "name": "average_pat_margin_across_three_reported_annual_observations",
                "period_margin_rates_pct": margins,
                "margin_definition": "profit_after_tax_attributable / revenue",
            },
        ),
    ]
    return records, []


def _record_ref(metric: str, record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("source") or {}
    return {
        "metric": metric,
        "record_type": record.get("record_type"),
        "approval_scope": record.get("approval_scope"),
        "available_on": record.get("available_on") or source.get("available_on"),
        "source_id": source.get("id"),
        "source_label": source.get("label"),
        "source_path": source.get("path"),
        "source_url": source.get("url"),
    }


def _reference_case_refs(records: list[dict[str, Any]], symbol: str) -> list[dict[str, Any]]:
    refs = []
    for record in records:
        if record.get("symbol") != symbol or record.get("record_type") != "derived_reference_case":
            continue
        refs.append({
            "metric": record.get("metric"),
            "assumption_status": record.get("assumption_status"),
            "case_type": record.get("case_type"),
            "formula_version": record.get("formula_version"),
            "available_on": record.get("available_on"),
            "source_id": (record.get("source") or {}).get("id"),
            "policy": {
                "historical_baseline_only": True,
                "not_owner_approved": True,
                "not_accepted_by_formal_engine_approved_records": True,
            },
        })
    return sorted(refs, key=lambda row: str(row.get("metric") or ""))


def _assumption_gap_manifest(
    pilot: list[str],
    model_inputs: dict[str, Any],
    readiness: dict[str, Any],
    records: list[dict[str, Any]],
    as_of: str | None,
) -> dict[str, Any]:
    companies: dict[str, Any] = {}
    product_count = 0
    blocked_product_count = 0
    ready_product_count = 0
    input_ready_count = 0
    for symbol in pilot:
        model_row = (model_inputs.get("companies") or {}).get(symbol) or {}
        readiness_row = (readiness.get("companies") or {}).get(symbol) or {}
        missing_prerequisites = []
        if model_row.get("status") != "ready":
            missing_prerequisites.append("financial_model_inputs_ready")
        if readiness_row.get("status") != "input_ready":
            missing_prerequisites.append("forecast_readiness_input_ready")
        accepted = approved_records({"records": records}, symbol, as_of)
        accepted_metrics = set(accepted)
        reference_cases = _reference_case_refs(records, symbol)
        products: dict[str, Any] = {}
        if missing_prerequisites:
            status = "not_evaluated_until_input_ready"
        else:
            status = "input_ready_pending_approved_records"
            input_ready_count += 1
        for product, required in FORMAL_ENGINE_REQUIRED_APPROVED_RECORDS.items():
            product_count += 1
            required_metrics = list(required)
            missing = [metric for metric in required_metrics if metric not in accepted_metrics]
            product_status = (
                "not_evaluated_until_input_ready"
                if missing_prerequisites
                else "ready_for_formal_engine"
                if not missing
                else "blocked_missing_approved_records"
            )
            if product_status == "ready_for_formal_engine":
                ready_product_count += 1
            else:
                blocked_product_count += 1
            products[product] = {
                "status": product_status,
                "required_approved_records": required_metrics,
                "accepted_records": [
                    _record_ref(metric, accepted[metric])
                    for metric in required_metrics
                    if metric in accepted
                ],
                "missing_approved_records": [] if missing_prerequisites else missing,
                "missing_prerequisites": list(missing_prerequisites),
                "policy": {
                    "no_formula_result": True,
                    "owner_approved_forward_and_valuation_assumptions_required": True,
                },
            }
        companies[symbol] = {
            "symbol": symbol,
            "status": status,
            "forecast_readiness_status": readiness_row.get("status"),
            "financial_model_inputs_status": model_row.get("status"),
            "qualified_period_count": readiness_row.get("qualified_period_count"),
            "products": products,
            "historical_reference_cases": reference_cases,
            "reference_cases_can_satisfy_missing_records": False,
            "next_required_action": (
                "owner_approve_source_labelled_forward_and_valuation_records"
                if not missing_prerequisites
                else "complete_qualified_financial_inputs_before_assumption_review"
            ),
        }
    return {
        "schema_version": 1,
        "as_of": as_of,
        "source": {
            "financial_engine_assumptions": "state/company_intel/financial_engine_assumptions.json",
            "financial_model_inputs": "state/company_intel/financial_model_inputs.json",
            "forecast_readiness": "state/company_intel/forecast_readiness.json",
        },
        "summary": {
            "company_count": len(companies),
            "input_ready_company_count": input_ready_count,
            "product_count": product_count,
            "ready_product_count": ready_product_count,
            "blocked_product_count": blocked_product_count,
        },
        "policy": {
            "gap_manifest_only": True,
            "does_not_approve_assumptions": True,
            "does_not_compute_formal_outputs": True,
            "derived_reference_cases_are_not_approved_records": True,
        },
        "companies": companies,
    }


def build(state_dir: Path = STATE, output_path: Path | None = None) -> dict[str, Any]:
    state_dir = Path(state_dir)
    output_path = Path(output_path) if output_path is not None else state_dir / "company_intel" / "financial_engine_assumptions.json"
    profiles = load_json(state_dir / "company_profiles.json", {})
    fundamentals = load_json(state_dir / "fundamentals.json", {})
    history_meta = load_json(state_dir / "history_meta.json", {})
    model_inputs = load_json(state_dir / "company_intel" / "financial_model_inputs.json", {})
    readiness = load_json(state_dir / "company_intel" / "forecast_readiness.json", {})
    as_of = _as_of(profiles, fundamentals, history_meta, model_inputs, readiness)
    fundamentals_cutoff = _state_date(fundamentals)
    history_cutoff = _state_date(history_meta) or as_of
    reference_cutoff = _state_date(readiness) or _state_date(model_inputs) or as_of

    preserved = [record for record in _load_existing_records(output_path) if not _is_generated_record(record)]
    generated: list[dict[str, Any]] = []
    generated_market_operands: list[dict[str, Any]] = []
    generated_reference_cases: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for symbol in _pilot_symbols(profiles):
        for builder in (
            lambda sym=symbol: _current_price_record(state_dir, sym, history_cutoff),
            lambda sym=symbol: _shares_out_record(fundamentals, sym, fundamentals_cutoff),
        ):
            record, block = builder()
            if record:
                generated.append(record)
                generated_market_operands.append(record)
            elif block:
                blocked.append(block)
        reference_records, reference_blocks = _reference_case_records(model_inputs, readiness, symbol, reference_cutoff)
        generated.extend(reference_records)
        generated_reference_cases.extend(reference_records)
        blocked.extend(reference_blocks)

    generated.sort(key=lambda record: (record["symbol"], record["metric"], record["available_on"]))
    records = preserved + generated
    generated_metrics = {record.get("metric") for record in generated}
    forbidden_generated = sorted(generated_metrics.intersection(FORBIDDEN_GENERATED_MODEL_METRICS))
    if forbidden_generated:
        raise ValueError(f"builder generated forbidden metrics: {', '.join(forbidden_generated)}")
    for record in generated_reference_cases:
        if record.get("approved") is True or "value" in record:
            raise ValueError(f"reference case entered approved/value path: {record.get('symbol')} {record.get('metric')}")

    state = {
        "schema_version": 1,
        "as_of": as_of,
        "source": {
            "company_profiles": "state/company_profiles.json",
            "history": "state/history/{symbol}.json",
            "history_meta": "state/history_meta.json",
            "fundamentals": "state/fundamentals.json",
            "financial_model_inputs": "state/company_intel/financial_model_inputs.json",
            "forecast_readiness": "state/company_intel/forecast_readiness.json",
        },
        "policy": {
            "generated_market_operands": list(GENERATED_MARKET_METRICS),
            "generated_reference_case_metrics": list(GENERATED_REFERENCE_CASE_METRICS),
            "reference_cases_are_historical_baselines_only": True,
            "reference_cases_are_not_owner_approved_assumptions": True,
            "reference_cases_do_not_use_formal_engine_value_field": True,
            "no_exit_pe_or_net_debt_generated": True,
            "owner_approved_records_preserved": True,
        },
        "summary": {
            "pilot_symbol_count": len(_pilot_symbols(profiles)),
            "preserved_record_count": len(preserved),
            "generated_record_count": len(generated),
            "generated_market_operand_count": len(generated_market_operands),
            "generated_reference_case_count": len(generated_reference_cases),
            "blocked_record_count": len(blocked),
        },
        "records": records,
        "blocked": sorted(blocked, key=lambda row: (row.get("symbol") or "", row.get("metric") or "")),
    }
    state["assumption_gaps"] = _assumption_gap_manifest(_pilot_symbols(profiles), model_inputs, readiness, records, as_of)
    save_json(output_path, state)
    print(
        "financial_engine_assumptions: "
        f"{len(generated_market_operands)} generated market operands, "
        f"{len(generated_reference_cases)} generated reference cases, "
        f"{len(preserved)} preserved records, {len(blocked)} blocked"
    )
    return state


if __name__ == "__main__":
    build(STATE, OUT)
