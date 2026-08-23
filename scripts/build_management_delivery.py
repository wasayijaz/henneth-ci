"""Build the Management Delivery & Contradiction Score state."""
from __future__ import annotations

from management_delivery import build_management_delivery
from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "management_delivery.json"


def build() -> dict:
    thesis_state = load_json(STATE / "company_intel" / "thesis_monitoring.json", {"companies": {}})
    signal_state = load_json(STATE / "company_intel" / "signal_clusters.json", {"companies": {}})
    operating_events = load_json(STATE / "company_intel" / "operating_events.json", {"companies": {}})
    confidence_state = load_json(STATE / "company_intel" / "intelligence_confidence.json", {"companies": {}})
    result = build_management_delivery(thesis_state, signal_state, operating_events, confidence_state)
    save_json(OUT, result)
    total = sum((row.get("delivery_record_count") or 0) for row in result.get("companies", {}).values())
    print(f"management_delivery: {len(result.get('companies', {}))} companies, {total} records")
    return result


if __name__ == "__main__":
    build()
