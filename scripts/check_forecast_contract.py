"""Stable checks for Forecast/Valuation Readiness Contract v1."""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
sys.path.insert(0, str(ROOT / "scripts"))

import build_forecast_readiness as builder
from forecast_contract import (
    BLOCKED_OUTPUT_STATUS,
    CONTRACT_VERSION,
    MODEL_NOT_IMPLEMENTED_OUTPUT_STATUS,
    MODEL_VERSION_BY_SECTOR,
    POLICIES,
    REQUIRED_PERIOD_COUNT,
    readiness_row,
)
from financial_statement_facts import PARSER_REVISION, PARSER_VERSION
from psx_data import load_json


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


def _assert_shape(data: dict, pilot: list[str]) -> None:
    _assert_finite(data)
    _assert_no_numeric_outputs(data)
    if data.get("contract_version") != CONTRACT_VERSION:
        _fail("contract version mismatch")
    if len(pilot) != 20 or len(set(pilot)) != 20:
        _fail("pilot boundary must be exactly 20")
    if data.get("pilot_symbols") != pilot:
        _fail("pilot symbol order mismatch")
    if set(data.get("companies") or {}) != set(pilot):
        _fail("company boundary mismatch")
    if data.get("policies") != POLICIES:
        _fail("policy mismatch")
    if data.get("model_versions") != MODEL_VERSION_BY_SECTOR:
        _fail("model registry versions mismatch")
    for symbol, row in (data.get("companies") or {}).items():
        if row.get("symbol") != symbol:
            _fail(f"{symbol}: symbol mismatch")
        if row.get("contract_version") != CONTRACT_VERSION:
            _fail(f"{symbol}: contract version mismatch")
        if (row.get("model_registry") or {}).get("status") != "supported":
            _fail(f"{symbol}: pilot model not supported")
        if symbol == "ENGROH" and (row.get("model_registry") or {}).get("selected_sector") != "HOLDING_COMPANY":
            _fail("ENGROH override did not select holding-company model")
        if row.get("status") not in {"input_ready", "blocked"}:
            _fail(f"{symbol}: invalid readiness status")
        if row.get("activation_status") != "blocked_model_not_implemented":
            _fail(f"{symbol}: numeric activation not blocked")
        expected_outputs = MODEL_NOT_IMPLEMENTED_OUTPUT_STATUS if row.get("status") == "input_ready" else BLOCKED_OUTPUT_STATUS
        if row.get("blocked_outputs") != expected_outputs:
            _fail(f"{symbol}: blocked outputs mismatch")
        if row.get("status") == "input_ready" and row.get("qualified_period_count") < REQUIRED_PERIOD_COUNT:
            _fail(f"{symbol}: input ready without three qualified periods")


def _synthetic_contract_assertions() -> None:
    ready = readiness_row("MLCF", "Cement", _ready_facts(), {"qualification_queue": {"candidate_documents": []}})
    if ready.get("status") != "input_ready" or ready.get("qualified_period_count") != 3:
        _fail("synthetic ready row did not become ready")
    if ready.get("activation_status") != "blocked_model_not_implemented":
        _fail("synthetic input-ready row activated numeric outputs")
    if (ready.get("model_registry") or {}).get("model_version") != "cement_v1":
        _fail("synthetic ready row selected wrong model")
    issuer_ready = readiness_row("MLCF", "Cement", _issuer_ready_facts(), {"qualification_queue": {"candidate_documents": []}})
    if issuer_ready.get("status") != "input_ready" or issuer_ready.get("qualified_period_count") != 3:
        _fail("qualified issuer binding did not become input-ready")
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
        if row.get("status") == "input_ready":
            _fail(f"{name} did not fail closed")


def main() -> None:
    expected = builder.build()
    expected_again = builder.build()
    if json.dumps(expected, sort_keys=True, ensure_ascii=False, allow_nan=False) != json.dumps(expected_again, sort_keys=True, ensure_ascii=False, allow_nan=False):
        _fail("builder output is not deterministic")
    pilot = expected.get("pilot_symbols") or []
    _assert_shape(expected, pilot)
    summary = expected.get("summary") or {}
    ready_symbols = sorted(symbol for symbol, row in (expected.get("companies") or {}).items()
                           if row.get("status") == "input_ready")
    qualified_symbols = sorted(symbol for symbol, row in (expected.get("companies") or {}).items()
                               if row.get("qualified_period_count", 0) >= 1)
    if (summary.get("ready_company_count") != len(ready_symbols)
            or summary.get("qualified_fact_company_count") != len(qualified_symbols)):
        _fail("real-state readiness summary does not match its qualified companies")
    for symbol, row in (expected.get("companies") or {}).items():
        if row.get("status") == "input_ready":
            if row.get("qualified_period_count", 0) < 3:
                _fail(f"{symbol}: input-ready state lacks three qualified periods")
        elif row.get("status") != "blocked" or row.get("qualified_period_count", 0) >= 3:
            _fail(f"{symbol}: real state has inconsistent readiness")
    _synthetic_contract_assertions()
    before = builder.OUT.read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_forecast_readiness.py")], capture_output=True, text=True, timeout=30)
    if result.returncode != 0 or builder.OUT.read_bytes() != before:
        _fail("builder output is not byte-idempotent")
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
            if built["as_of"] != "2026-01-02" or built["companies"]["MLCF"]["status"] != "input_ready":
                _fail("temp fixture did not build source-derived ready output")
            if (built.get("summary") or {}).get("ready_company_count") != 1 or (built.get("summary") or {}).get("blocked_company_count") != 0:
                _fail("temp fixture summary did not count input-ready output")
        finally:
            builder.STATE, builder.OUT = original_state, original_out
    slice_path = ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json"
    slice_data = load_json(slice_path, {"tickers": []})
    by_symbol = {row.get("symbol"): row for row in slice_data.get("tickers") or []}
    for symbol, state_row in expected.get("companies", {}).items():
        if (by_symbol.get(symbol) or {}).get("forecast_readiness") != state_row:
            _fail(f"{symbol}: CI slice forecast_readiness mismatch")
    print(f"forecast_readiness: PASS ({len(pilot)} companies, {len(ready_symbols)} input-ready; formal outputs remain source-gated)")


if __name__ == "__main__":
    main()
