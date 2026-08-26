"""Build the deterministic CI monitoring/freshness state."""
from __future__ import annotations

import argparse
from pathlib import Path

from ci_monitoring import build_ci_monitoring
from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "monitoring.json"


def build(output_path: Path = OUT) -> dict:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    source_registry = load_json(STATE / "company_intel" / "source_registry.json", {"tickers": {}})
    source_qa = load_json(STATE / "company_source_qa.json", {"tickers": {}})
    change_intelligence = load_json(STATE / "company_intel" / "change_intelligence.json", {"companies": {}})
    event_ledger = load_json(STATE / "company_event_ledger.json", {"companies": {}})
    operating_events = load_json(STATE / "company_intel" / "operating_events.json", {"companies": {}})
    evidence_watchlist = load_json(STATE / "company_intel" / "evidence_watchlist.json", {"companies": {}})
    guidance_state = load_json(STATE / "company_intel" / "guidance_contradictions.json", {"companies": {}})
    result = build_ci_monitoring(
        source_registry,
        source_qa,
        change_intelligence,
        event_ledger,
        operating_events,
        evidence_watchlist,
        guidance_state,
        pilot_symbols=pilot,
    )
    save_json(output_path, result)
    print(f"ci_monitoring: {len(result.get('companies', {}))} companies, {result.get('summary', {}).get('alert_count', 0)} alerts")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
