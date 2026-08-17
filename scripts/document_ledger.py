#!/usr/bin/env python3
"""Append-only company event/change ledger.

The ledger itself never prunes durable events. Bounded retention is applied to
the document evidence and synthesis queue surfaces, not this audit history.
"""
from __future__ import annotations

import time
from typing import Any

from psx_data import STATE, load_json, save_json

OUT = STATE / "company_event_ledger.json"
def append_events(events: list[dict[str, Any]], path=OUT,
                  changes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Append unseen event IDs; existing event payloads are never overwritten."""
    prior = load_json(path, {"schema_version": 1, "companies": {}, "_meta": {}})
    companies = dict(prior.get("companies") or {})
    known = {e.get("event_id") for c in companies.values() for e in (c.get("events") or [])}
    known_changes = {c.get("change_id") for row in companies.values() for c in (row.get("changes") or [])}
    added = 0
    for event in events:
        eid = event.get("event_id")
        if not eid or eid in known:
            continue
        tickers = event.get("tickers") or ["_unassigned"]
        for ticker in sorted(set(tickers)):
            row = dict(companies.get(ticker) or {"events": [], "latest_by_type": {}})
            row.setdefault("events", []).append(event)
            row.setdefault("changes", [])
            row["latest_by_type"] = dict(row.get("latest_by_type") or {})
            etype = event.get("event_type") or "other"
            prior_id = row["latest_by_type"].get(etype)
            prior_event = next((x for x in row["events"] if x.get("event_id") == prior_id), None)
            if not prior_event or (event.get("event_date") or "") >= (prior_event.get("event_date") or ""):
                row["latest_by_type"][etype] = eid
            companies[ticker] = row
        known.add(eid)
        added += 1

    changes_added = 0
    for change in changes or []:
        cid = change.get("change_id")
        if not cid or cid in known_changes:
            continue
        for ticker in sorted(set(change.get("tickers") or ["_unassigned"])):
            row = dict(companies.get(ticker) or {"events": [], "latest_by_type": {}})
            row.setdefault("events", [])
            row.setdefault("changes", []).append(change)
            companies[ticker] = row
        known_changes.add(cid)
        changes_added += 1

    if not added and not changes_added and path.exists():
        return prior

    out = {"schema_version": 1, "companies": companies,
           "_meta": {"updated": time.strftime("%Y-%m-%d %H:%M"),
                     "events_added": added, "changes_added": changes_added,
                     "events_retained": sum(len(c.get("events") or []) for c in companies.values()),
                     "append_only": True,
                     "note": "Events are never deleted or overwritten; bounded surfaces are separate."}}
    save_json(path, out)
    return out
