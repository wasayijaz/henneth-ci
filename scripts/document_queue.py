#!/usr/bin/env python3
"""Build the changed-document synthesis queue (training mode only).

This file is an agent hand-off artifact, not an invocation point.  The queue is
delta-only on ``doc_id + content_sha256`` and remains approval-pending until a
human changes it outside this deterministic pass.
"""
from __future__ import annotations

import time
from typing import Any

from psx_data import STATE, load_json, save_json

OUT = STATE / "document_synthesis_queue.json"
MAX_PENDING = 200


def build_queue(documents: dict[str, Any], path=OUT) -> dict[str, Any]:
    prior = load_json(path, {"schema_version": 1, "queue": [], "history": [], "_meta": {}})
    prior_history = list(prior.get("history") or [])
    if not prior_history:
        prior_history = list(prior.get("queue") or [])
    old = {(r.get("doc_id"), r.get("content_sha256")): r for r in prior_history}
    history: list[dict[str, Any]] = list(old.values())
    existing_keys = set(old)
    for doc_id, doc in sorted(documents.items()):
        if doc_id.startswith("_") or doc.get("status") != "ready":
            continue
        key = (doc_id, doc.get("content_sha256"))
        if key in existing_keys:
            continue
        event_max = max((e.get("priority_weight") or 0 for e in (doc.get("events") or [])), default=0)
        history.append({"queue_id": f"syn_{doc_id}_{str(doc.get('content_sha256') or '')[:12]}",
                        "doc_id": doc_id, "content_sha256": doc.get("content_sha256"),
                        "tickers": doc.get("tickers") or [], "doc_type": doc.get("doc_type"),
                        "priority": event_max, "queued_at": time.strftime("%Y-%m-%d %H:%M"),
                        "approval_status": "pending", "training_mode": True,
                        "synthesis_status": "not_started"})
    pending = [r for r in history if r.get("approval_status") == "pending"
               and r.get("synthesis_status") not in ("complete", "rejected")]
    pending.sort(key=lambda r: (-int(r.get("priority") or 0), r.get("queued_at") or "", r.get("queue_id") or ""))
    overflow = max(0, len(pending) - MAX_PENDING)
    retained = pending[:MAX_PENDING]
    if history == prior_history and retained == (prior.get("queue") or []) and overflow == (prior.get("_meta") or {}).get("overflow", 0) and path.exists():
        return prior
    out = {"schema_version": 1, "queue": retained, "history": history,
           "_meta": {"updated": time.strftime("%Y-%m-%d %H:%M"), "pending": len(retained),
                     "overflow": overflow, "retention_max": MAX_PENDING,
                     "training_mode": True,
                     "note": "Deterministic hand-off only; no model/provider call is made."}}
    save_json(path, out)
    return out
