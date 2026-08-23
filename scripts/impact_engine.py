"""Deterministic event-to-driver Bear/Base/Bull scenario calculator."""
from __future__ import annotations
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from psx_data import STATE, load_json, save_json
from operating_events import stable_id

OUT = STATE / "company_intel" / "impact_scenarios.json"
EVENT_DRIVER = {
    "acquisition_divestment": ["portfolio_value", "subsidiary_value", "valuation"],
    "capacity_plant_expansion": [
        "auto_assembly_capacity",
        "clinker_capacity",
        "fertilizer_capacity",
        "generation_capacity",
        "refining_capacity",
        "storage_capacity",
    ],
    "contract_tender": ["dispatch_volume", "generation_volume", "order_book", "revenue", "sales_volume"],
    "debt_refinancing": ["deposit_cost", "finance_cost"],
    "exploration_well_discovery": ["exploration_success"],
    "hiring_expansion": ["employee_count"],
    "maintenance_shutdown": ["plant_availability", "production_volume", "refinery_throughput"],
    "management_change": [],
    "product_launch": ["model_mix", "product_mix", "sales_volume"],
    "regulatory_change": ["allowed_return", "policy_rate", "refinery_margin", "regulated_price", "tax_rate", "tariff"],
    "supplier_change": ["crude_supply", "gas_supply", "input_cost", "raw_material_cost"],
}
PROBS = {"bear": 0.25, "base": 0.5, "bull": 0.25}

def build():
    events = load_json(STATE / "company_intel" / "operating_events.json", {})
    graphs = load_json(STATE / "company_intel" / "driver_graphs.json", {})
    companies = {}
    for sym in events.get("pilot_symbols") or []:
        scenarios = []
        for event in (events.get("companies", {}).get(sym, {}).get("events") or []):
            drivers = EVENT_DRIVER.get(event.get("event_type"), [])
            graph_drivers = set((graphs.get("companies", {}).get(sym) or {}).get("drivers") or [])
            affected = [d for d in drivers if d in graph_drivers or d in {e.get("to") for e in (graphs.get("companies", {}).get(sym) or {}).get("edges") or []}]
            for name, probability in PROBS.items():
                sid = stable_id(event.get("event_id"), name, prefix="scn")
                flags = ["insufficient_data"] if affected else ["no_modeled_driver"]
                scenarios.append({
                    "scenario_id": sid,
                    "event_id": event.get("event_id"),
                    "company_id": sym,
                    "intelligence_type": "scenario",
                    "scenario_type": "scenario",
                    "scenario": name.title(),
                    "probability": probability,
                    "assumptions": {
                        "affected_drivers": affected,
                        "required_inputs": affected,
                        "missing_inputs": affected,
                    },
                    "impact_status": "insufficient_data" if affected else "unmodeled_driver",
                    "timing": {"expected_lag": event.get("expected_lag"), "effective_date": event.get("effective_date")},
                    "revenue_impact": None,
                    "ebitda_impact": None,
                    "eps_impact": None,
                    "fcf_impact": None,
                    "valuation_impact": None,
                    "confidence": event.get("confidence", 0),
                    "evidence": event.get("evidence") or [],
                    "quality_flags": flags,
                })
        companies[sym] = {"scenarios": scenarios}
    out = {"schema_version": 1, "pilot_symbols": events.get("pilot_symbols") or [], "companies": companies, "scenario_probabilities": PROBS}
    save_json(OUT, out)
    print(f"impact_scenarios: {sum(len(v['scenarios']) for v in companies.values())} scenarios")
    return out
if __name__ == "__main__": build()
