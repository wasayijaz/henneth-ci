"""Focused checks for CI historical reference-case slice exposure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_ci_slice as builder
from psx_data import load_json


SLICE = ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json"
ASSUMPTIONS = ROOT / "state" / "company_intel" / "financial_engine_assumptions.json"


def fail(message: str) -> None:
    raise AssertionError(message)


def dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def valid_record(**overrides) -> dict:
    record = {
        "symbol": "MLCF",
        "metric": "revenue_growth_pct",
        "derived_value": 7.123456,
        "unit": "pct",
        "approved": False,
        "approval_scope": "historical_reference_case_not_owner_approved",
        "record_type": "derived_reference_case",
        "epistemic_type": "derived",
        "case_type": "reference_case",
        "assumption_status": "not_owner_approved_forecast_input",
        "available_on": "2024-03-01",
        "formula_version": "financial_engine_assumptions_reference_case_v1",
        "period_ends": ["2021-12-31", "2022-12-31", "2023-12-31"],
        "source": {
            "id": "fixture:reference_case",
            "label": "fixture reference case",
            "path": "state/company_intel/financial_model_inputs.json",
            "available_on": "2024-03-01",
        },
        "formula": {"name": "fixture_formula"},
        "source_facts": [
            {
                "line": "revenue",
                "fact_id": "fact-1",
                "document_id": "doc-1",
                "content_sha256": "hash-1",
                "source_url": "https://example.com/report.pdf",
                "period_end": "2023-12-31",
                "available_on": "2024-03-01",
                "normalized_value": 100.0,
            }
        ],
    }
    record.update(overrides)
    return record


def assert_helper_filters() -> None:
    records = [
        valid_record(),
        valid_record(metric="net_margin_pct", approved=True),
        valid_record(metric="net_margin_pct", value=10.0),
        valid_record(metric="net_margin_pct", available_on="2024-03-02"),
        valid_record(metric="net_margin_pct", source={"id": "x", "label": "missing path", "available_on": "2024-03-01"}),
        valid_record(metric="net_margin_pct", source_facts=[]),
        valid_record(symbol="OTHER"),
        {"symbol": "MLCF", "metric": "shares_out", "value": 100.0, "approved": True},
    ]
    first = builder._historical_reference_cases({"records": records}, "MLCF", "2024-03-01")
    second = builder._historical_reference_cases({"records": records}, "MLCF", "2024-03-01")
    if dump(first) != dump(second):
        fail("historical reference-case helper is not deterministic")
    if first["case_count"] != 1 or first["rejected_record_count"] != 5:
        fail(f"helper filter counts mismatch: {first}")
    case = first["cases"][0]
    if case.get("approved") is not False or "value" in case:
        fail("accepted reference case can enter approved value path")
    if case.get("derived_value") != 7.1235:
        fail("derived value was not deterministically rounded")
    if not (case.get("policy") or {}).get("not_accepted_by_formal_engine_approved_records"):
        fail("formal-engine exclusion policy missing")


def assert_real_slice() -> None:
    data = load_json(SLICE, {})
    assumptions = load_json(ASSUMPTIONS, {"records": []})
    rows = data.get("tickers") or []
    meta = ((data.get("meta") or {}).get("historical_reference_cases") or {})
    cutoff = meta.get("source_cutoff")
    if not rows:
        fail("CI slice has no tickers")
    if not cutoff:
        fail("historical reference-case source cutoff missing")
    expected_total = 0
    observed_total = 0
    for row in rows:
        symbol = row.get("symbol")
        payload = row.get("historical_reference_cases")
        if not isinstance(payload, dict):
            fail(f"{symbol}: historical_reference_cases missing")
        expected = builder._historical_reference_cases(assumptions, symbol, cutoff)
        if dump(payload) != dump(expected):
            fail(f"{symbol}: slice reference cases differ from safe helper output")
        if (row.get("intelligence") or {}).get("historical_reference_case_count") != payload.get("case_count"):
            fail(f"{symbol}: intelligence count mismatch")
        expected_total += expected.get("case_count", 0)
        observed_total += payload.get("case_count", 0)
        for case in payload.get("cases") or []:
            if case.get("approved") is not False or "value" in case:
                fail(f"{symbol}: unsafe top-level value path in reference case")
            if case.get("available_on") > cutoff:
                fail(f"{symbol}: future-dated reference case leaked")
            if case.get("record_type") != "derived_reference_case":
                fail(f"{symbol}: non-reference-case record leaked")
            for fact in case.get("source_facts") or []:
                if fact.get("available_on") > cutoff:
                    fail(f"{symbol}: future-dated source fact leaked")
                for field in ("fact_id", "document_id", "source_url", "period_end", "available_on", "normalized_value"):
                    if fact.get(field) in (None, ""):
                        fail(f"{symbol}: source fact missing {field}")
    if observed_total != expected_total:
        fail("reference case total mismatch")
    if (meta.get("summary") or {}).get("reference_case_count") != observed_total:
        fail("metadata reference case count mismatch")
    policy = meta.get("policy") or {}
    if not policy.get("historical_baselines_only") or not policy.get("formal_engine_eligibility_unchanged"):
        fail("slice metadata policy is not explicit")


def main() -> None:
    assert_helper_filters()
    assert_real_slice()
    print("ci historical reference cases: PASS")


if __name__ == "__main__":
    main()
