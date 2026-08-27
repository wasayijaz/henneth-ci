#!/usr/bin/env python3
"""Contract checker for deterministic event review windows."""
from datetime import date
from psx_data import STATE, load_json

TARGET_TYPES = {"results", "agm", "board_meeting", "briefing", "corporate_briefing"}
FORBIDDEN = ("prompt", "forecast", "advice", "buy", "sell", "order")


def _walk(value):
    if isinstance(value, str): yield value
    elif isinstance(value, dict):
        for v in value.values(): yield from _walk(v)
    elif isinstance(value, list):
        for v in value: yield from _walk(v)


def main():
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    data = load_json(STATE / "company_intel" / "event_review_windows.json", {})
    companies = data.get("companies") or {}
    assert len(pilot) == 20 and set(companies) == set(pilot), "slice must contain exact pilot 20"
    for row in companies.values():
        assert not any(key in row for key in ("scheduled_tasks", "ai_prompt", "forecast", "advice", "orders"))
    for symbol in pilot:
        row = companies[symbol]
        assert row.get("status") in {"available", "unknown"}
        assert isinstance(row.get("status_reason"), str) and row["status_reason"]
        known = row.get("known_events") or []
        confirmed = row.get("confirmed_events") or []
        expected_rows = row.get("expected_reporting_windows") or []
        assert confirmed == [event for event in known if event.get("confirmed")], "confirmed rows must remain an exact retained subset"
        for event in row.get("known_events") or []:
            assert event.get("event_type") in TARGET_TYPES
            day = date.fromisoformat(event["date"])
            window = event["window"]
            assert date.fromisoformat(window["start"]) <= day <= date.fromisoformat(window["end"])
            assert 3 <= (date.fromisoformat(window["end"]) - date.fromisoformat(window["start"])).days + 1 <= 5
            assert window.get("intensity") == "intensified"
        expected = row.get("expected_reporting_window") or {}
        assert expected.get("status") in {"unknown", "derived_from_past_cadence", "suppressed_known_event"}
        if expected.get("status") == "derived_from_past_cadence":
            assert expected.get("historical_dates") and expected.get("interval_days")
            assert date.fromisoformat(expected["date"])
            assert expected["window"]["source_kind"] == "retained_past_cadence"
            assert len(expected_rows) == 1 and expected_rows[0]["date"] == expected["date"]
        else:
            assert not expected_rows, "only a qualified cadence may produce an expected review row"
    print(f"event_review_windows: PASS ({len(pilot)} companies)")


if __name__ == "__main__":
    main()
