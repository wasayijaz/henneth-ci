"""Focused checks for the audit-only cement operating series."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
sys.path.insert(0, str(ROOT / "scripts"))

from cement_operating_series import CEMENT_PILOT_SYMBOLS, ObservationSpec, build_state


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def walk(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise AssertionError("non-finite value")
    if isinstance(value, dict):
        for child in value.values():
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)


def fixture_documents() -> dict:
    return {
        "documents": {
            "issuer:fixture": {
                "doc_id": "issuer:fixture",
                "tickers": ["DGKC"],
                "source": "Issuer registry",
                "source_url": "https://example.com/dgkc.pdf",
                "content_sha256": "fixturehash",
                "local_sha256": "fixturehash",
                "published_at": "2026-08-27T03:00:00+05:00",
                "retrieved_at": "2026-08-27 00:00",
                "facts": [{"fact_id": "fact_fixture", "evidence": [{"page": 7, "text": "FY24 FY23 Cement sales 100 90"}]}],
                "evidence": [{"page": 7, "text": "FY24 FY23 Cement sales 100 90"}],
            }
        }
    }


def fixture_registry() -> dict:
    return {
        "tickers": {
            "DGKC": {
                "document_links": [
                    {
                        "id": "issuer:fixture",
                        "status": "discovered",
                        "source_page": "https://example.com/ir",
                        "first_seen_at": "2026-08-27T03:00:00+05:00",
                    }
                ]
            }
        }
    }


def assert_fixture_contract() -> None:
    spec = ObservationSpec(
        "DGKC",
        "cement_sales_total",
        "2024-06-30",
        100,
        "100",
        "tonnes",
        "issuer:fixture",
        7,
        ("FY24 FY23 Cement sales 100 90",),
        ("fact_fixture",),
    )
    state = build_state(fixture_documents(), fixture_registry(), specs=(spec,), as_of="2026-08-27")
    row = state["companies"]["DGKC"]
    obs = row["metrics"]["cement_sales_total"][0]
    assert obs["readiness"] == "audit_only"
    assert obs["approval_status"] == "not_owner_approved_forecast_input"
    assert obs["model_eligibility"] == "not_model_loadable"
    assert obs["source"]["available_on"] == "2026-08-27T03:00:00+05:00"
    assert obs["source"]["status"] == "official_publication_date"
    assert obs["source"]["source_fact_ids"] == ["fact_fixture"]
    assert state["companies"]["MLCF"]["status"] == "insufficient_aligned_annual_operating_history"
    assert state["companies"]["LUCK"]["status"] == "missing_retained_cement_operating_history"
    bad_spec = ObservationSpec("DGKC", "cement_sales_total", "2024-06-30", 101, "101", "tonnes", "issuer:fixture", 7, ("missing anchor",))
    try:
        build_state(fixture_documents(), fixture_registry(), specs=(bad_spec,), as_of="2026-08-27")
    except ValueError:
        pass
    else:
        raise AssertionError("missing retained anchor did not fail closed")


def assert_real_state() -> None:
    state = load(STATE / "company_intel" / "cement_operating_series.json")
    walk(state)
    assert state.get("schema_version") == 1
    assert state.get("policy", {}).get("audit_only") is True
    assert state.get("policy", {}).get("formal_engine_eligibility_unchanged") is True
    assert set(state.get("pilot_symbols") or []) == set(CEMENT_PILOT_SYMBOLS)
    assert set(state.get("companies") or {}) == set(CEMENT_PILOT_SYMBOLS)
    dgkc = state["companies"]["DGKC"]
    assert dgkc["status"] == "audit_only_series_available"
    assert dgkc["activation_status"] == "blocked_audit_only_no_model_adapter"
    assert dgkc["observation_count"] >= 30
    assert dgkc["annual_period_count"] >= 7
    assert dgkc["lane_assessment"]["pilot_peer_operating_lane"] == "blocked_insufficient_aligned_peer_history"
    required_metrics = {"clinker_production", "cement_production", "cement_sales_local", "cement_sales_export", "cement_sales_total"}
    assert required_metrics <= set(dgkc["metrics"])
    seen_ids = set()
    for metric, observations in dgkc["metrics"].items():
        periods = [obs["period_end"] for obs in observations]
        assert periods == sorted(periods), f"{metric} not sorted"
        for obs in observations:
            assert obs["observation_id"] not in seen_ids
            seen_ids.add(obs["observation_id"])
            assert obs["readiness"] == "audit_only"
            assert obs["approval_status"] == "not_owner_approved_forecast_input"
            assert obs["model_eligibility"] == "not_model_loadable"
            source = obs["source"]
            for field in ("document_id", "source_url", "page", "text", "content_sha256", "retained_on", "status"):
                assert source.get(field) not in (None, ""), f"{obs['observation_id']} missing {field}"
            assert str(source["source_url"]).startswith("https://")
            assert isinstance(source["page"], int) and source["page"] > 0
            assert obs["raw_value"] in source["text"]
            if source["status"] == "official_publication_date":
                assert source.get("available_on") not in (None, "")
            else:
                assert source["status"] == "publication_date_not_retained_audit_only"
                assert source.get("available_on") is None
    assert state["companies"]["MLCF"]["status"] == "insufficient_aligned_annual_operating_history"
    assert state["companies"]["MLCF"]["observation_count"] == 0
    assert state["companies"]["LUCK"]["status"] == "missing_retained_cement_operating_history"
    assert state["companies"]["LUCK"]["observation_count"] == 0
    for row in state["companies"].values():
        assert set(row["downstream_status"].values()) == {"not_activated"}
    model_inputs = load(STATE / "company_intel" / "financial_model_inputs.json")
    assert model_inputs.get("source") == "state/company_financial_series.json"
    assert model_inputs.get("model_adapter_source") is None
    assert "cement_operating_series" not in json.dumps(model_inputs)
    for path in ("forecast_readiness.json", "financial_forecasts.json", "formal_valuations.json", "market_expectations.json"):
        payload = load(STATE / "company_intel" / path)
        assert "cement_operating_series" not in json.dumps(payload), f"{path} consumed audit-only operating series"


def main() -> None:
    assert_fixture_contract()
    assert_real_state()
    print("cement_operating_series: PASS")


if __name__ == "__main__":
    main()
