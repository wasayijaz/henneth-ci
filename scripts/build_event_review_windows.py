#!/usr/bin/env python3
"""Build the deterministic, low-token Company Intelligence event review windows."""
from __future__ import annotations

import hashlib
from statistics import median
from datetime import date, timedelta

from psx_data import STATE, load_json, save_json

OUT = STATE / "company_intel" / "event_review_windows.json"
TARGET_TYPES = {"results", "agm", "board_meeting", "briefing", "corporate_briefing"}


def _iso(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _window(day, source_kind, rationale):
    start, end = day - timedelta(days=2), day + timedelta(days=2)
    return {"start": start.isoformat(), "end": end.isoformat(), "days": 5,
            "intensity": "intensified", "source_kind": source_kind,
            "rationale": rationale}


def _historical_earnings(ledger, symbol):
    dates = []
    for event in ((ledger.get("companies", {}).get(symbol) or {}).get("events") or []):
        if event.get("event_type") != "earnings":
            continue
        day = _iso(event.get("event_date"))
        if day and day not in dates:
            dates.append(day)
    return sorted(dates)


def _cadence_expected(history, as_of):
    if len(history) < 3:
        return {"status": "unknown", "reason": "insufficient_dated_past_earnings_cadence", "historical_dates": history}
    ordinal = [date.fromisoformat(v) for v in history]
    gaps = [(b - a).days for a, b in zip(ordinal, ordinal[1:]) if 70 <= (b - a).days <= 120]
    if len(gaps) < 2:
        return {"status": "unknown", "reason": "past_earnings_cadence_not_stable", "historical_dates": history}
    interval = int(round(median(gaps)))
    anchor = ordinal[-1]
    expected = anchor + timedelta(days=interval)
    # Do not emit a stale/past derived window; the retained cadence is only a baseline.
    while expected < as_of:
        expected += timedelta(days=interval)
    start, end = expected - timedelta(days=2), expected + timedelta(days=2)
    return {
        "status": "derived_from_past_cadence",
        "event_type": "results",
        "date": expected.isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": 5,
                    "intensity": "intensified", "source_kind": "retained_past_cadence",
                    "rationale": "Five-day review window centered on the median 70-120 day gap in retained dated earnings events; not a confirmed date."},
        "anchor_date": anchor.isoformat(), "interval_days": interval,
        "historical_dates": history,
        "rationale": "Conservative cadence baseline only; no forecast, task, or market expectation.",
    }


def build():
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    calendar = load_json(STATE / "earnings_calendar.json", {})
    ledger = load_json(STATE / "company_event_ledger.json", {})
    as_of = _iso(calendar.get("updated")) or date.today().isoformat()
    as_of_date = date.fromisoformat(as_of)
    rows = {}
    for symbol in pilot:
        known = []
        for event in calendar.get("events") or []:
            if event.get("ticker") != symbol or event.get("type") not in TARGET_TYPES:
                continue
            day = _iso(event.get("date"))
            if not day or date.fromisoformat(day) < as_of_date:
                continue
            event_id = "calendar:" + hashlib.sha1(f"{symbol}|{event.get('type')}|{day}".encode()).hexdigest()[:16]
            known.append({"event_id": event_id, "event_type": event.get("type"), "date": day,
                          "confirmed": bool(event.get("confirmed")),
                          "source": event.get("source") or None,
                          "window": _window(date.fromisoformat(day), "earnings_calendar",
                                            "Known retained calendar event; confirmation is preserved as supplied.")})
        known.sort(key=lambda row: (row["date"], row["event_type"], row["event_id"]))
        expected = _cadence_expected(_historical_earnings(ledger, symbol), as_of_date)
        if any(row["event_type"] == "results" for row in known):
            expected = {"status": "suppressed_known_event", "reason": "known_results_event_present", "historical_dates": expected.get("historical_dates", [])}
        expected_windows = []
        if expected.get("status") == "derived_from_past_cadence":
            expected_windows.append({
                "event_type": "results", "date": expected["date"], "confirmed": False,
                "status": expected["status"], "source_kind": expected["window"]["source_kind"],
                "rationale": expected["rationale"], **expected["window"],
            })
        review_windows = [
            row["window"] | {"event_type": row["event_type"], "date": row["date"], "confirmed": row["confirmed"], "source_url": row["source"]}
            for row in known
        ] + expected_windows
        rows[symbol] = {
            "symbol": symbol, "as_of": as_of, "known_events": known,
            # Presentation-ready collections are still source state, not browser-derived rows.
            "confirmed_events": [row for row in known if row["confirmed"]],
            "expected_reporting_window": expected,
            "expected_reporting_windows": expected_windows,
            "review_windows": review_windows,
            "status": "available" if known or expected_windows else "unknown",
            "status_reason": "retained_calendar_or_cadence_available" if known or expected_windows else expected.get("reason", "no_retained_event_window"),
        }
    save_json(OUT, {"meta": {"schema_version": 1, "as_of": as_of, "count": len(rows),
                              "source": "state/earnings_calendar.json + state/company_event_ledger.json",
                              "policy": "Deterministic review metadata only; no scheduled tasks, external calls, AI prompts, forecasts, advice, or auto actions."},
               "companies": rows})
    print(f"event_review_windows: {len(rows)} companies -> {OUT}")


if __name__ == "__main__":
    build()
