"""Stable checks for Forecast/Valuation Readiness Contract v1."""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_forecast_readiness as builder
from psx_data import load_json
from forecast_contract import (
    ADAPTER_UNAVAILABLE_OUTPUT_STATUS,
    EXECUTABLE_NUMERIC_ADAPTERS_BY_SECTOR,
    BLOCKED_OUTPUT_STATUS,
    CONTRACT_VERSION,
    POLICIES,
    REGISTRY_VERSION_BY_SECTOR,
    REQUIRED_PERIOD_COUNT,
    readiness_row,
)
from financial_statement_facts import PARSER_REVISION, PARSER_VERSION


FORBIDDEN_NUMERIC_KEYS = {
    "forecast_value", "valuation_value", "target_price", "fair_value", "expected_return",
    "market_implied_growth", "market_expectation", "dcf_value",
}


def _fail(message: str) -> None:
    raise AssertionError(message)


def _walk(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield path + (str(key),), item
            yield from _walk(item, path + (str(key),))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _walk(item, path + (str(idx),))


def _assert_finite(value) -> None:
    for path, item in _walk(value):
        if isinstance(item, float) and not math.isfinite(item):
            _fail(f"nonfinite at {'.'.join(path)}")


def _assert_no_numeric_outputs(data: dict) -> None:
    for path, item in _walk(data):
        key = path[-1] if path else ""
        if key in FORBIDDEN_NUMERIC_KEYS:
            _fail(f"forbidden numeric forecast/valuation output at {'.'.join(path)}")
        if len(path) >= 2 and path[-2] in {"blocked_outputs", "downstream_status"} and key in {"forecast", "valuation", "market_expectations", "numeric_impact"}:
            if not isinstance(item, str) or not item.startswith("blocked_"):
                _fail(f"{'.'.join(path)} is not blocked")


def _fact(line: str, year: int, *, value: float = 100, unit: str = "PKR", mult: int = 1_000_000,
          eps: bool = False, available_on: str | None = None, source_url: str = "https://dps.psx.com.pk/download/document/1.pdf",
          readiness: str = "model_loadable", flags: list[str] | None = None) -> dict:
    return {
        "fact_id": f"{line}-{year}",
        "document_id": f"psx:{year}",
        "source_url": source_url,
        "line": line,
        "parser_version": PARSER_VERSION,
        "parser_revision": PARSER_REVISION,
        "readiness": readiness,
        "period_end": f"{year}-12-31",
        "period_type": "annual",
        "duration_months": 12,
        "consolidation": "consolidated",
        "currency": "PKR",
        "statement_type": "income_statement",
        "unit": "PKR/share" if eps else unit,
        "unit_multiplier": 1 if eps else mult,
        "normalized_value": value if eps else value * mult,
        "available_on": available_on or f"{year + 1}-02-01",
        "quality_flags": flags or [],
        "content_sha256": f"hash-{year}",
        "evidence": [{"page": 1, "text": f"{line} {year}", "source_url": source_url}],
    }


def _ready_facts() -> list[dict]:
    rows = []
    for year in (2021, 2022, 2023):
        rows.extend([
            _fact("revenue", year, value=100 + year),
            _fact("profit_after_tax_attributable", year, value=20 + year),
            _fact("basic_eps", year, value=2 + year / 1000, eps=True),
        ])
    return rows


def _issuer_ready_facts() -> list[dict]:
    rows = []
    issuer_base = "https://issuer.example/investors/"
    for year in (2021, 2022, 2023):
        for fact in (
            _fact("revenue", year, value=100 + year),
            _fact("profit_after_tax_attributable", year, value=20 + year),
            _fact("basic_eps", year, value=2 + year / 1000, eps=True),
        ):
            url = f"{issuer_base}annual-{year}.pdf"
            doc_id = f"issuer:{year}"
            content_hash = ("abcdef0123456789" * 4)[:64]
            content_hash = content_hash[:-1] + str(year % 10)
            fact = {**fact, "document_id": doc_id, "source_url": url,
                    "issuer_registry_binding": {
                        "status": "qualified", "document_id": doc_id,
                        "link_id": doc_id, "source_url": url,
                        "source_page": issuer_base, "root_domain": "issuer.example",
                        "content_sha256": content_hash,
                        "evidence_page": 1,
                    }}
            fact["content_sha256"] = content_hash
            fact["evidence"] = [{"page": 1, "text": fact["line"], "source_url": url}]
            rows.append(fact)
    return rows


def _assert_shape(data: dict, pilot: list[str], *, require_exact_pilot: bool = True) -> None:
    _assert_finite(data)
    _assert_no_numeric_outputs(data)
    if data.get("contract_version") != CONTRACT_VERSION:
        _fail("contract version mismatch")
    if require_exact_pilot and (len(pilot) != 20 or len(set(pilot)) != 20):
        _fail("pilot boundary must be exactly 20")
    if data.get("pilot_symbols") != pilot:
        _fail("pilot symbol order mismatch")
    if set(data.get("companies") or {}) != set(pilot):
        _fail("company boundary mismatch")
    if data.get("policies") != POLICIES:
        _fail("policy mismatch")
    if data.get("registry_versions") != REGISTRY_VERSION_BY_SECTOR:
        _fail("model registry versions mismatch")
    if data.get("adapter_versions") != EXECUTABLE_NUMERIC_ADAPTERS_BY_SECTOR:
        _fail("model adapter versions mismatch")
    for symbol, row in (data.get("companies") or {}).items():
        if row.get("symbol") != symbol:
            _fail(f"{symbol}: symbol mismatch")
        if row.get("contract_version") != CONTRACT_VERSION:
            _fail(f"{symbol}: contract version mismatch")
        registry = row.get("model_registry") or {}
        adapter = row.get("model_adapter") or {}
        if registry.get("status") != "covered":
            _fail(f"{symbol}: pilot registry not covered")
        if registry.get("coverage_type") != "qualitative_sector_driver_registry":
            _fail(f"{symbol}: registry coverage type mismatch")
        if adapter.get("status") != "unavailable":
            _fail(f"{symbol}: numeric adapter unexpectedly available")
        if adapter.get("reason") != "blocked_model_adapter_unavailable":
            _fail(f"{symbol}: adapter unavailable reason mismatch")
        if symbol == "ENGROH" and (row.get("model_registry") or {}).get("selected_sector") != "HOLDING_COMPANY":
            _fail("ENGROH override did not select holding-company model")
        if row.get("status") not in {"input_ready", "blocked_model_adapter_unavailable", "blocked_insufficient_qualified_history"}:
            _fail(f"{symbol}: invalid readiness status")
        if row.get("activation_status") != row.get("status"):
            _fail(f"{symbol}: activation status mismatch")
        expected_outputs = ADAPTER_UNAVAILABLE_OUTPUT_STATUS if row.get("status") == "blocked_model_adapter_unavailable" else BLOCKED_OUTPUT_STATUS
        if row.get("blocked_outputs") != expected_outputs:
            _fail(f"{symbol}: blocked outputs mismatch")
        if row.get("status") == "blocked_model_adapter_unavailable" and row.get("qualified_period_count") < REQUIRED_PERIOD_COUNT:
            _fail(f"{symbol}: adapter-blocked without three qualified periods")
        if row.get("status") == "blocked_insufficient_qualified_history" and row.get("qualified_period_count", 0) >= REQUIRED_PERIOD_COUNT:
            _fail(f"{symbol}: insufficient-history status with qualified history")


def _synthetic_contract_assertions() -> None:
    ready = readiness_row("MLCF", "Cement", _ready_facts(), {"qualification_queue": {"candidate_documents": []}})
    if ready.get("status") != "blocked_model_adapter_unavailable" or ready.get("qualified_period_count") != 3:
        _fail("synthetic history-qualified row did not block on adapter")
    if ready.get("activation_status") != "blocked_model_adapter_unavailable":
        _fail("synthetic history-qualified row activated numeric outputs")
    if (ready.get("model_registry") or {}).get("registry_version") != "cement_v1":
        _fail("synthetic ready row selected wrong model")
    if (ready.get("model_adapter") or {}).get("status") != "unavailable":
        _fail("synthetic ready row did not expose unavailable adapter")
    issuer_ready = readiness_row("MLCF", "Cement", _issuer_ready_facts(), {"qualification_queue": {"candidate_documents": []}})
    if issuer_ready.get("status") != "blocked_model_adapter_unavailable" or issuer_ready.get("qualified_period_count") != 3:
        _fail("qualified issuer binding did not become adapter-blocked")
    tampered_issuer = _issuer_ready_facts()
    tampered_issuer[0] = {**tampered_issuer[0], "issuer_registry_binding": {
        **tampered_issuer[0]["issuer_registry_binding"], "content_sha256": "tampered",
    }}
    if readiness_row("MLCF", "Cement", tampered_issuer, {}).get("status") == "input_ready":
        _fail("tampered issuer binding activated readiness")
    cases = {
        "future_availability": [_fact("revenue", 2021, available_on="2020-01-01"), *_ready_facts()[1:]],
        "audit_only": [{**_ready_facts()[0], "readiness": "audit_only"}, *_ready_facts()[1:]],
        "unofficial_source": [{**_ready_facts()[0], "source_url": "https://example.com/x.pdf"}, *_ready_facts()[1:]],
        "quality_flag": [{**_ready_facts()[0], "quality_flags": ["conflict"]}, *_ready_facts()[1:]],
        "pat_scale_mismatch": [{**_ready_facts()[1], "unit_multiplier": 1000}, _ready_facts()[0], *_ready_facts()[2:]],
        "eps_scaled": [{**_ready_facts()[2], "unit_multiplier": 1000}, *_ready_facts()[:2], *_ready_facts()[3:]],
        "evidence_unlinked": [{**_ready_facts()[0], "evidence": [{"page": 1, "text": "bad", "source_url": "https://dps.psx.com.pk/download/document/other.pdf"}]}, *_ready_facts()[1:]],
        "not_consolidated": [{**_ready_facts()[0], "consolidation": "unconsolidated"}, *_ready_facts()[1:]],
        "not_annual": [{**_ready_facts()[0], "period_type": "quarter"}, *_ready_facts()[1:]],
        "same_day_availability": [{**_ready_facts()[0], "available_on": "2021-12-31"}, *_ready_facts()[1:]],
        "unsupported_sector": _ready_facts(),
    }
    for name, facts in cases.items():
        sector = "Technology & Communication" if name == "unsupported_sector" else "Cement"
        row = readiness_row("MLCF", sector, facts, {"qualification_queue": {"candidate_documents": []}})
        if row.get("status") == "blocked_model_adapter_unavailable":
            _fail(f"{name} did not fail closed")


def main() -> None:
    _synthetic_contract_assertions()
    durable = load_json(builder.OUT, {})
    _assert_shape(durable, durable.get("pilot_symbols") or [])
    with tempfile.TemporaryDirectory(prefix="henneth-forecast-readiness-") as td:
        root = Path(td)
        original_state, original_out = builder.STATE, builder.OUT
        try:
            builder.STATE = root
            builder.OUT = root / "company_intel" / "forecast_readiness.json"
            (root / "company_intel").mkdir(parents=True)
            (root / "company_profiles.json").write_text(json.dumps({"updated": "2026-01-01", "pilot": {"symbols": ["MLCF"]}}), encoding="utf-8")
            (root / "sectors.json").write_text(json.dumps({"updated": "2026-01-02", "tickers": {"MLCF": {"sector": "Cement"}}}), encoding="utf-8")
            (root / "company_financial_series.json").write_text(json.dumps({"tickers": {"MLCF": {"facts": _ready_facts()}}}), encoding="utf-8")
            (root / "company_intel" / "financial_coverage.json").write_text(json.dumps({"companies": {"MLCF": {"qualification_queue": {"candidate_documents": [{"document_id": "psx:1"}]}}}}), encoding="utf-8")
            built = builder.build()
            built_again = builder.build()
            if json.dumps(built, sort_keys=True, ensure_ascii=False, allow_nan=False) != json.dumps(built_again, sort_keys=True, ensure_ascii=False, allow_nan=False):
                _fail("temp fixture builder output is not deterministic")
            if built["as_of"] != "2026-01-02" or built["companies"]["MLCF"]["status"] != "blocked_model_adapter_unavailable":
                _fail("temp fixture did not build adapter-blocked output")
            summary = built.get("summary") or {}
            if (
                summary.get("ready_company_count") != 0
                or summary.get("history_qualified_company_count") != 1
                or summary.get("adapter_unavailable_company_count") != 1
                or summary.get("blocked_company_count") != 1
            ):
                _fail("temp fixture summary did not count adapter-blocked output")
            _assert_shape(built, ["MLCF"], require_exact_pilot=False)
        finally:
            builder.STATE, builder.OUT = original_state, original_out
    print("forecast_readiness: PASS (adapter manifest separated from qualitative registry; durable state and synthetic contract checked)")


if __name__ == "__main__":
    main()
