"""Focused contract checks for historical earnings bridges."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from earnings_bridges import METRICS, build_state


def _fact(metric, period, value, fact_id, available_on):
    return {
        "status": "eligible", "metric": metric, "period_type": "annual", "duration_months": 12,
        "statement_type": "income_statement", "consolidation": "consolidated", "currency": "PKR",
        "period_end": period, "normalized_value": value, "unit": "PKR/share" if metric == "basic_eps" else "PKR",
        "unit_multiplier": 1,
        "source": {"fact_id": fact_id, "document_id": "psx:fixture", "source_url": "https://dps.psx.com.pk/download/document/fixture.pdf", "content_sha256": "a" * 64, "page": 1, "text": "fixture", "available_on": available_on},
    }


def _fixture():
    facts = []
    for period, values, suffix in (("2023-06-30", (100, 10, 1), "a"), ("2024-06-30", (120, 12, 1.2), "b")):
        for metric, value in zip(METRICS, values):
            facts.append(_fact(metric, period, value, f"{metric}-{suffix}", "2024-08-01"))
    return {"as_of": "2024-12-31", "pilot_symbols": ["TEST"], "companies": {"TEST": {"facts": facts}}}


def _assert_fixture():
    state = build_state(_fixture())
    row = state["companies"]["TEST"]
    assert row["status"] == "historical_bridge_available"
    bridge = row["bridges"][0]
    assert round(bridge["metrics"]["revenue"]["change_pct"], 8) == 20
    assert row["formal_engine_status"]["forecast"] == "not_activated"
    future = _fixture()
    future["companies"]["TEST"]["facts"][0]["source"]["available_on"] = "2025-01-01"
    assert build_state(future)["companies"]["TEST"]["bridge_count"] == 0


def _assert_real():
    with (ROOT / "state" / "company_intel" / "earnings_bridges.json").open(encoding="utf-8") as handle:
        state = json.load(handle)
    pilot = state.get("pilot_symbols") or []
    assert len(pilot) == 20 and len(set(pilot)) == 20
    assert set(state.get("companies") or {}) == set(pilot)
    assert state.get("policy", {}).get("formal_engine_eligibility_unchanged") is True
    for symbol, row in state["companies"].items():
        assert row["formal_engine_status"] == {"forecast": "not_activated", "valuation": "not_activated", "market_expectations": "not_activated"}
        for bridge in row.get("bridges") or []:
            assert bridge["symbol"] == symbol and bridge["status"] == "historical_descriptive_only"
            assert bridge["available_on"] <= state["as_of"]
            for metric in METRICS:
                data = bridge["metrics"][metric]
                for source_key in ("previous_source", "current_source"):
                    source = data[source_key]
                    assert source["fact_id"] and source["document_id"] and source["source_url"] and source["content_sha256"]
                    assert isinstance(source["page"], int) and source["page"] > 0
                    assert source["available_on"] <= state["as_of"]


if __name__ == "__main__":
    _assert_fixture()
    _assert_real()
    print("earnings_bridges: PASS")
