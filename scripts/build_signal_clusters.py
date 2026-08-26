"""Build the provenance-gated, closed-registry signal-cluster state.

``signal_clusters.py`` owns the classifier.  This boundary owns the *published
contract*: the registry is emitted alongside the rows it governs so consumers
never have to infer which labels happen to be supported by the implementation.
"""
from __future__ import annotations

import copy

from psx_data import STATE, load_json, save_json
from signal_clusters import (
    REGISTRY_VERSION,
    SUPPORTED_TYPES,
    SEQUENTIAL_ACQUISITION_STAGES,
    build_signal_state,
)

OUT = STATE / "company_intel" / "signal_clusters.json"

# This is deliberately a small closed registry.  Every class below is backed by
# a branch in ``normalize_propositions``; labels which are merely plausible but
# not source-resolvable are not listed and therefore cannot be emitted.
REGISTRY_SCHEMA_VERSION = 1
SIGNAL_CLUSTER_REGISTRY = {
    "schema_version": REGISTRY_SCHEMA_VERSION,
    "version": REGISTRY_VERSION,
    "closed": True,
    "event_aliases": {
        "acquisition": {
            "event_types": ["acquisition_divestment"],
            "subtypes": ["acquisition"],
            "proposition_type": "acquisition",
            "stages": ["approved", "completed", "intention", "public_offer", "terminated"],
            "required_proposition_fields": ["target", "stage", "effective_date"],
        },
        "management_change": {
            "event_types": ["management_change"],
            "subtypes": ["management_change"],
            "proposition_type": "management_change",
            "actions": ["appointment", "re_appointment", "resignation"],
            "required_proposition_fields": ["person", "role", "verb", "effective_date"],
        },
    },
    "supported_event_types": sorted({"acquisition_divestment", "management_change"}),
    "supported_proposition_types": sorted(SUPPORTED_TYPES),
    "source_policy": {
        "intelligence_type": "reported_fact",
        "retained_document_status": "ready",
        "required_evidence_fields": [
            "document_id", "content_sha256", "evidence_sha256", "source_url", "page", "text",
        ],
        "source_url_protocols": ["http", "https"],
        "unsupported_events": "rejected",
    },
    "no_lookahead": {
        "cutoff_fields": ["detected_at", "available_at", "effective_date"],
        "future_values": "rejected",
    },
    "conflict_policy": {
        "acquisition_incompatible_stages": ["completed|terminated", "terminated|completed"],
        "acquisition_sequential_stages": ["intention", "public_offer", "approved", "completed"],
        "management_incompatible_actions": [
            "appointment|resignation", "re_appointment|resignation",
            "resignation|appointment", "resignation|re_appointment",
        ],
    },
}


def registry_contract() -> dict:
    """Return a detached registry payload suitable for JSON publication."""
    # Keep the declaration tied to the implementation constants.  If a future
    # classifier changes its registry version or stage order, this build cannot
    # silently publish an old declaration.
    registry = copy.deepcopy(SIGNAL_CLUSTER_REGISTRY)
    registry["version"] = REGISTRY_VERSION
    registry["supported_proposition_types"] = sorted(SUPPORTED_TYPES)
    registry["conflict_policy"]["acquisition_sequential_stages"] = list(SEQUENTIAL_ACQUISITION_STAGES)
    return registry


def build():
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = (profiles.get("pilot") or {}).get("symbols") or []
    operating_events = load_json(STATE / "company_intel" / "operating_events.json", {"companies": {}})
    documents = load_json(STATE / "company_documents.json", {"documents": {}}).get("documents") or {}
    # Only retain evidence that exactly matches a ready durable document.
    for sym, row in (operating_events.get("companies") or {}).items():
        kept=[]
        for event in row.get("events") or []:
            valid=[]
            for evidence in event.get("evidence") or []:
                doc=documents.get(evidence.get("document_id")) or {}
                if doc.get("status") != "ready" or doc.get("content_sha256") != evidence.get("content_sha256"): continue
                if not isinstance(evidence.get("content_sha256"),str) or len(evidence.get("content_sha256"))!=64: continue
                if not isinstance(evidence.get("page"),int) or not evidence.get("text"): continue
                valid.append(evidence)
            if valid:
                event=dict(event); event["evidence"]=valid
                doc=documents.get(valid[0].get("document_id")) or {}
                event["document_title"]=doc.get("title")
                kept.append(event)
        row["events"]=kept
    result = build_signal_state(operating_events, list(pilot), document_index=documents)
    # Registry metadata is intentionally present at the top level and on every
    # pilot row.  A row copied into the CI slice therefore remains self-
    # describing and cannot outlive the classifier version that produced it.
    result["registry"] = registry_contract()
    for row in (result.get("companies") or {}).values():
        row["registry_version"] = REGISTRY_VERSION
    save_json(OUT, result)
    total = sum(len(row.get("clusters") or []) for row in result["companies"].values())
    print(f"signal_clusters: {len(result['companies'])} companies, {total} clusters")
    return result


if __name__ == "__main__":
    build()
