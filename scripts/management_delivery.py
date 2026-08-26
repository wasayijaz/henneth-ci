"""Deterministic Management Delivery & Contradiction Score v2.

This module compares active deterministic thesis records with later retained
official events, and emits an additive company-scoped guidance delivery slice
from first-class guidance objects. It does not infer from loose proximity,
forecast outcomes, valuation, advice language, or browser-side matching.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from signal_clusters import _incompatible, _supersedes, normalize_propositions


SCHEMA_VERSION = 1
DELIVERY_VERSION = "management_delivery_v2"
PKT = timezone(timedelta(hours=5))
STATUSES = {"confirmed", "contradicted", "not_observed", "blocked_no_guidance_objects"}
INCOMPATIBLE_MODALITIES = {
    ("increase", "decrease"),
    ("decrease", "increase"),
    ("continue", "stop"),
    ("stop", "continue"),
    ("proceed", "cancel"),
    ("cancel", "proceed"),
    ("risk_present", "risk_mitigated"),
    ("risk_mitigated", "risk_present"),
    ("appointment", "resignation"),
    ("resignation", "appointment"),
    ("intention", "cancel"),
    ("cancel", "intention"),
    ("public_offer", "cancel"),
    ("cancel", "public_offer"),
}
FORBIDDEN_TEXT = (
    "buy",
    "sell",
    "recommend",
    "target price",
    "fair value",
    "upside",
    "downside",
    "probability",
    "forecast",
    "guarantee",
    "should",
)


def _stable_id(prefix: str, *parts: Any) -> str:
    text = "\x1f".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]}"


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if len(text) == 10:
        text = f"{text}T00:00:00"
    elif len(text) == 16 and " " in text:
        text = text.replace(" ", "T") + ":00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PKT)
    return parsed.astimezone(PKT)


def _iso_time(value: Any) -> str | None:
    parsed = _parse_time(value)
    return parsed.isoformat() if parsed else None


def _event_available_at(event: dict[str, Any]) -> str | None:
    for evidence in event.get("evidence") or []:
        if isinstance(evidence, dict):
            value = evidence.get("document_retrieved_at")
            if value:
                return _iso_time(value)
    return _iso_time(event.get("detected_at"))


def _source_available_at(cluster: dict[str, Any], thesis: dict[str, Any]) -> str | None:
    values = []
    for obs in cluster.get("observations") or []:
        evidence = obs.get("evidence") or {}
        for value in (obs.get("available_at"), evidence.get("document_retrieved_at"), obs.get("detected_at"), obs.get("effective_date")):
            parsed = _parse_time(value)
            if parsed:
                values.append(parsed)
                break
    if values:
        return max(values).isoformat()
    for event_id in thesis.get("linked_event_ids") or []:
        if event_id:
            return None
    return None


def _evidence_refs_from_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    seen = set()
    for evidence in event.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        key = (evidence.get("document_id"), evidence.get("evidence_sha256"), evidence.get("page"))
        if key in seen:
            continue
        seen.add(key)
        refs.append({
            "document_id": evidence.get("document_id"),
            "source_url": evidence.get("source_url") or event.get("source_url"),
            "page": evidence.get("page"),
            "content_sha256": evidence.get("content_sha256"),
            "evidence_sha256": evidence.get("evidence_sha256"),
            "source": evidence.get("source"),
        })
    return refs


def _guidance_evidence_ref(obj: dict[str, Any]) -> dict[str, Any]:
    evidence = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else {}
    return {
        "guidance_id": obj.get("guidance_id"),
        "document_id": evidence.get("document_id"),
        "source_url": evidence.get("source_url"),
        "page": evidence.get("page"),
        "content_sha256": evidence.get("content_sha256"),
        "evidence_sha256": evidence.get("evidence_sha256"),
        "source": evidence.get("source"),
        "available_on": evidence.get("available_on"),
    }


def _guidance_evidence_identity(obj: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    evidence = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else {}
    return (
        evidence.get("document_id"),
        evidence.get("content_sha256"),
        evidence.get("evidence_sha256"),
        evidence.get("page"),
    )


def _guidance_policy_ok(obj: dict[str, Any]) -> bool:
    policy = obj.get("policy") if isinstance(obj.get("policy"), dict) else {}
    return (
        obj.get("status") == "eligible"
        and bool(policy.get("same_company_official_evidence"))
        and policy.get("numeric_forecast") is False
        and policy.get("valuation") is False
        and policy.get("advice") is False
    )


def _later_guidance_objects(source_obj: dict[str, Any], objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_time = _parse_time((source_obj.get("evidence") or {}).get("available_on"))
    source_identity = _guidance_evidence_identity(source_obj)
    rejected = {
        "not_first_class_guidance": 0,
        "not_strictly_later": 0,
        "self_confirming_source": 0,
    }
    candidates = []
    reviewed = 0
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        reviewed += 1
        if obj.get("guidance_id") == source_obj.get("guidance_id") or not _guidance_policy_ok(obj):
            rejected["not_first_class_guidance"] += 1
            continue
        object_time = _parse_time((obj.get("evidence") or {}).get("available_on"))
        if not source_time or not object_time or object_time <= source_time:
            rejected["not_strictly_later"] += 1
            continue
        if _guidance_evidence_identity(obj) == source_identity:
            rejected["self_confirming_source"] += 1
            continue
        candidates.append(obj)
    candidates.sort(key=lambda obj: ((obj.get("evidence") or {}).get("available_on") or "", obj.get("guidance_id") or ""))
    review = {
        "reviewed_object_count": reviewed,
        "candidate_object_count": len(candidates),
        "rejected_counts": rejected,
        "match_rule": "same_company_first_class_guidance_strictly_later_non_self_source",
    }
    return candidates, review


def _guidance_record(symbol: str, source_obj: dict[str, Any], objects: list[dict[str, Any]]) -> dict[str, Any]:
    candidates, review = _later_guidance_objects(source_obj, objects)
    status = "not_observed"
    match = None
    reasons = ["no later first-class guidance object matched the exact assertion or conflict key"]
    limitations = ["Loose same-company guidance proximity is deliberately ignored."]
    for obj in candidates:
        if obj.get("assertion_key") == source_obj.get("assertion_key"):
            status = "confirmed"
            match = {
                "guidance_id": obj.get("guidance_id"),
                "available_at": (obj.get("evidence") or {}).get("available_on"),
                "assertion_key": obj.get("assertion_key"),
                "conflict_key": obj.get("conflict_key"),
                "match_rule": "same_company_exact_guidance_assertion_key_strictly_later",
                "evidence": [_guidance_evidence_ref(obj)],
            }
            reasons = ["later first-class guidance exactly matched the normalized assertion key"]
            limitations = []
            break
        if obj.get("conflict_key") == source_obj.get("conflict_key") and obj.get("assertion_key") != source_obj.get("assertion_key"):
            if (source_obj.get("modality"), obj.get("modality")) in INCOMPATIBLE_MODALITIES:
                status = "contradicted"
                match = {
                    "guidance_id": obj.get("guidance_id"),
                    "available_at": (obj.get("evidence") or {}).get("available_on"),
                    "assertion_key": obj.get("assertion_key"),
                    "conflict_key": obj.get("conflict_key"),
                    "match_rule": "same_company_exact_guidance_conflict_key_incompatible_modality_strictly_later",
                    "evidence": [_guidance_evidence_ref(obj)],
                }
                reasons = ["later first-class guidance matched the exact conflict key with an incompatible modality"]
                limitations = []
                break
    return {
        "guidance_record_id": _stable_id("guidance_delivery", symbol, source_obj.get("guidance_id")),
        "symbol": symbol,
        "guidance_id": source_obj.get("guidance_id"),
        "assertion_key": source_obj.get("assertion_key"),
        "conflict_key": source_obj.get("conflict_key"),
        "status": status,
        "scorecard_type": "categorical_status_only",
        "source_guidance": {
            "available_at": (source_obj.get("evidence") or {}).get("available_on"),
            "statement": source_obj.get("statement"),
            "domain": source_obj.get("domain"),
            "modality": source_obj.get("modality"),
            "evidence": [_guidance_evidence_ref(source_obj)],
        },
        "matched_guidance": match,
        "guidance_review": review,
        "reasons": reasons,
        "limitations": limitations,
    }


def _guidance_records(symbol: str, guidance_row: dict[str, Any]) -> list[dict[str, Any]]:
    objects = [
        obj for obj in guidance_row.get("objects") or []
        if isinstance(obj, dict) and obj.get("symbol") == symbol and _guidance_policy_ok(obj)
    ]
    objects.sort(key=lambda obj: ((obj.get("evidence") or {}).get("available_on") or "", obj.get("guidance_id") or ""))
    return [_guidance_record(symbol, obj, objects) for obj in objects]


def _confidence_link(confidence_row: dict[str, Any], source_cluster_id: str | None) -> dict[str, Any] | None:
    for assessment in confidence_row.get("assessments") or []:
        if assessment.get("source_cluster_id") == source_cluster_id:
            return {
                "confidence_id": assessment.get("confidence_id"),
                "source_cluster_id": source_cluster_id,
                "band": assessment.get("band"),
            }
    return None


def _cluster_map(signal_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        cluster.get("cluster_id"): cluster
        for cluster in signal_row.get("clusters") or []
        if isinstance(cluster, dict) and cluster.get("cluster_id")
    }


def _candidate_events(events: list[dict[str, Any]], source_available_at: str | None, linked_event_ids: set[str]) -> list[dict[str, Any]]:
    source_time = _parse_time(source_available_at)
    candidates = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("event_id") in linked_event_ids:
            continue
        if event.get("intelligence_type") != "reported_fact":
            continue
        if event.get("quality_flags"):
            continue
        level = event.get("source_quality_level")
        if not isinstance(level, int) or not (1 <= level <= 3):
            continue
        available_at = _event_available_at(event)
        event_time = _parse_time(available_at)
        if not source_time or not event_time or event_time <= source_time:
            continue
        propositions, reasons = normalize_propositions(event)
        for prop in propositions:
            candidates.append({
                "event": event,
                "proposition": prop,
                "available_at": available_at,
                "reasons": reasons,
            })
    candidates.sort(key=lambda row: (row.get("available_at") or "", (row.get("event") or {}).get("event_id") or ""))
    return candidates


def _match_delivery(
    thesis: dict[str, Any],
    cluster: dict[str, Any],
    events: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None, list[str], list[str]]:
    assertion_key = thesis.get("assertion_key")
    conflict_key = thesis.get("conflict_key")
    source_available_at = _source_available_at(cluster, thesis)
    if not assertion_key or not conflict_key or not source_available_at:
        return "blocked_no_guidance_objects", None, ["missing_normalized_source_assertion"], [
            "A normalized source assertion and availability date are required before delivery can be evaluated."
        ]
    source_prop = dict(cluster.get("proposition") or {})
    source_prop["assertion_key"] = assertion_key
    source_prop["conflict_key"] = conflict_key
    linked_event_ids = {event_id for event_id in thesis.get("linked_event_ids") or [] if event_id}
    for candidate in _candidate_events(events, source_available_at, linked_event_ids):
        prop = candidate["proposition"]
        event = candidate["event"]
        if prop.get("assertion_key") == assertion_key:
            return "confirmed", {
                "event_id": event.get("event_id"),
                "available_at": candidate.get("available_at"),
                "effective_date": event.get("effective_date"),
                "assertion_key": prop.get("assertion_key"),
                "conflict_key": prop.get("conflict_key"),
                "match_rule": "same_symbol_exact_assertion_key_strictly_later",
                "evidence": _evidence_refs_from_event(event),
            }, ["later official event exactly matched the normalized proposition"], []
        if prop.get("conflict_key") == conflict_key and prop.get("assertion_key") != assertion_key:
            if _incompatible(source_prop, prop) or _supersedes(prop, source_prop):
                return "contradicted", {
                    "event_id": event.get("event_id"),
                    "available_at": candidate.get("available_at"),
                    "effective_date": event.get("effective_date"),
                    "assertion_key": prop.get("assertion_key"),
                    "conflict_key": prop.get("conflict_key"),
                    "match_rule": "same_symbol_exact_conflict_key_strictly_later",
                    "evidence": _evidence_refs_from_event(event),
                }, ["later official event matched the exact conflict key with an incompatible proposition"], []
    return "not_observed", None, ["no later official event matched the exact assertion or conflict key"], [
        "Loose same-symbol event proximity is deliberately ignored."
    ]


def _delivery_record(
    symbol: str,
    thesis: dict[str, Any],
    cluster: dict[str, Any],
    events: list[dict[str, Any]],
    confidence_row: dict[str, Any],
) -> dict[str, Any]:
    status, event_match, reasons, limitations = _match_delivery(thesis, cluster, events)
    confidence_link = _confidence_link(confidence_row, thesis.get("source_cluster_id"))
    return {
        "delivery_id": _stable_id("delivery", symbol, thesis.get("thesis_id"), thesis.get("source_cluster_id")),
        "symbol": symbol,
        "thesis_id": thesis.get("thesis_id"),
        "source_cluster_id": thesis.get("source_cluster_id"),
        "assertion_key": thesis.get("assertion_key"),
        "conflict_key": thesis.get("conflict_key"),
        "status": status,
        "scorecard_type": "categorical_status_only",
        "source_assertion": {
            "available_at": _source_available_at(cluster, thesis),
            "linked_event_ids": thesis.get("linked_event_ids") or [],
            "evidence": thesis.get("evidence") or [],
            "monitored_assertion": thesis.get("monitored_assertion"),
        },
        "matched_event": event_match,
        "confidence_link": confidence_link,
        "reasons": reasons,
        "limitations": limitations,
    }


def build_management_delivery(
    thesis_state: dict[str, Any],
    signal_state: dict[str, Any],
    operating_events: dict[str, Any],
    confidence_state: dict[str, Any],
    guidance_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    guidance_state = guidance_state or {}
    symbols = list(thesis_state.get("pilot_symbols") or signal_state.get("pilot_symbols") or [])
    companies = {}
    total = 0
    blocked = 0
    for symbol in symbols:
        thesis_row = (thesis_state.get("companies") or {}).get(symbol) or {}
        signal_row = (signal_state.get("companies") or {}).get(symbol) or {}
        confidence_row = (confidence_state.get("companies") or {}).get(symbol) or {}
        events = ((operating_events.get("companies") or {}).get(symbol) or {}).get("events") or []
        guidance_row = (guidance_state.get("companies") or {}).get(symbol) or {"symbol": symbol, "status": "no_guidance_objects", "objects": []}
        clusters = _cluster_map(signal_row)
        records = []
        guidance_records = _guidance_records(symbol, guidance_row)
        for thesis in thesis_row.get("theses") or []:
            cluster = clusters.get(thesis.get("source_cluster_id")) or {}
            record = _delivery_record(symbol, thesis, cluster, events, confidence_row)
            records.append(record)
            total += 1
            if record.get("status") == "blocked_no_guidance_objects":
                blocked += 1
        companies[symbol] = {
            "symbol": symbol,
            "status": "tracked" if records else "no_active_thesis",
            "active_thesis_count": len(thesis_row.get("theses") or []),
            "delivery_record_count": len(records),
            "guidance_status": "available" if guidance_records else "blocked_no_guidance_objects",
            "guidance_object_count": len(guidance_row.get("objects") or []),
            "guidance_record_count": len(guidance_records),
            "records": records,
            "guidance_records": guidance_records,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "delivery_version": DELIVERY_VERSION,
        "as_of": thesis_state.get("as_of") or signal_state.get("as_of") or confidence_state.get("as_of") or "unknown",
        "pilot_symbols": symbols,
        "source": {
            "thesis_monitoring": "state/company_intel/thesis_monitoring.json",
            "signal_clusters": "state/company_intel/signal_clusters.json",
            "operating_events": "state/company_intel/operating_events.json",
            "intelligence_confidence": "state/company_intel/intelligence_confidence.json",
            "guidance_contradictions": "state/company_intel/guidance_contradictions.json",
        },
        "policy": {
            "research_only": True,
            "no_advice": True,
            "no_odds_claims": True,
            "no_forward_estimates": True,
            "no_price_claims": True,
            "same_symbol_required": True,
            "exact_assertion_or_conflict_key_required": True,
            "first_class_guidance_objects_required": True,
            "strictly_later_than_latest_source_required": True,
            "source_linked_self_confirmation_excluded": True,
        },
        "guidance_coverage": {
            "status": (
                "available" if all(row.get("guidance_record_count") for row in companies.values())
                else "partial" if any(row.get("guidance_record_count") for row in companies.values())
                else "blocked_no_guidance_objects"
            ),
            "source": "state/company_intel/guidance_contradictions.json",
            "guidance_version": guidance_state.get("guidance_version"),
            "reason": "Management delivery v2 consumes only first-class guidance/risk objects with exact normalized keys.",
        },
        "status_vocabulary": sorted(STATUSES),
        "summary": {
            "active_thesis_count": total,
            "delivery_record_count": total,
            "blocked_record_count": blocked,
        },
        "companies": companies,
    }
