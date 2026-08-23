"""Pure helpers for Wave 2 historical operating-event benchmarks."""
from __future__ import annotations
from calendar import monthrange
from datetime import date
from typing import Any

HORIZONS = (("1Q", 3), ("2Q", 6), ("4Q", 12), ("8Q", 24))

def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    try:
        if len(text) != 10 or text[4] != "-" or text[7] != "-": return None
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None

def add_months(day: date, months: int) -> date:
    idx = day.year * 12 + day.month - 1 + months
    year, month = divmod(idx, 12); month += 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))

def first_on_or_after(rows: list[dict], target: date, cutoff: date | None = None) -> dict | None:
    for row in rows:
        d = parse_date(row.get("date"))
        if d and d >= target and (cutoff is None or d <= cutoff) and isinstance(row.get("close"), (int, float)):
            return row
    return None

def last_before(rows: list[dict], target: date) -> dict | None:
    found = None
    for row in rows:
        d = parse_date(row.get("date"))
        if d and d < target and isinstance(row.get("close"), (int, float)): found = row
        elif d and d >= target: break
    return found

def raw_return(baseline: dict | None, endpoint: dict | None) -> float | None:
    if not baseline or not endpoint or baseline.get("close") in (None, 0): return None
    return (float(endpoint["close"]) / float(baseline["close"]) - 1.0) * 100.0

def horizon_result(rows: list[dict], baseline: dict | None, event_day: date | None, months: int, last_day: date | None) -> dict:
    target = add_months(event_day, months) if event_day else None
    out = {"target_date": target.isoformat() if target else None, "selected_date": None, "selected_close": None, "return_pct": None, "status": "unavailable", "reason": None}
    if not event_day or not baseline:
        out["reason"] = "invalid_effective_date" if not event_day else "no_baseline_close"
        return out
    if last_day and target > last_day:
        out["status"], out["reason"] = "immature", "target_after_last_bar"
        return out
    endpoint = first_on_or_after(rows, target, last_day)
    if not endpoint:
        out["reason"] = "no_eligible_endpoint_close"
        return out
    out.update({"selected_date": endpoint.get("date"), "selected_close": endpoint.get("close"), "return_pct": raw_return(baseline, endpoint), "status": "mature"})
    return out
