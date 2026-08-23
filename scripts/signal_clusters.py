"""Closed-registry signal clustering over provenance-complete operating events.

This module deliberately does not read broad ledgers, source QA, change digests,
or issuer-source inventories.  It accepts only already-derived operating events
and then revalidates them through narrow predicates before any proposition can
be clustered.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

REGISTRY_VERSION = "signal_cluster_registry_v1"
SUPPORTED_TYPES = {"management_change", "acquisition"}
INCOMPATIBLE_ACQUISITION_STAGES = {("completed", "terminated"), ("terminated", "completed")}
SEQUENTIAL_ACQUISITION_STAGES = {"intention": 1, "public_offer": 2, "approved": 3, "completed": 4}
HEX64 = re.compile(r"^[0-9a-f]{64}$", re.I)
PKT = timezone(timedelta(hours=5))


def stable_key(prefix: str, *parts: Any) -> str:
    text = "|".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _title(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}$", text):
        text = f"{text}T00:00:00"
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$", text):
        text = text.replace(" ", "T") + ":00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=PKT)
        return parsed.astimezone(PKT)
    except ValueError:
        return None


def _iso_time(value: Any) -> str | None:
    parsed = _parse_time(value)
    return parsed.isoformat() if parsed else None


def _date_only(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)[:10]).replace(tzinfo=PKT)
    except (TypeError, ValueError):
        return None


def freshness_band(effective_date: Any, as_of: str | None) -> str:
    eff = _date_only(effective_date)
    cutoff = _parse_time(as_of)
    if not eff or not cutoff:
        return "unknown"
    days = (cutoff.date() - eff.date()).days
    if days < 0:
        return "future"
    if days <= 180:
        return "recent"
    if days <= 730:
        return "older"
    return "historical"


def derive_as_of(operating_events: dict[str, Any], document_index: dict[str, Any] | None = None) -> str | None:
    values = []
    if document_index is not None:
        for company in (operating_events.get("companies") or {}).values():
            for event in company.get("events") or []:
                for evidence in event.get("evidence") or []:
                    doc = document_index.get(evidence.get("document_id")) or {}
                    parsed = _parse_time(doc.get("retrieved_at")) if doc.get("status") == "ready" else None
                    if parsed:
                        values.append(parsed)
    else:
        for company in (operating_events.get("companies") or {}).values():
            for event in company.get("events") or []:
                parsed = _parse_time(event.get("detected_at"))
                if parsed:
                    values.append(parsed)
    if not values:
        return None
    return max(values).isoformat()


def _distributor(source: str, url: str) -> str:
    text = f"{source} {url}".lower()
    return "psx" if "psx" in text or "dps.psx.com.pk" in text else "issuer"


def _clean_evidence(event: dict[str, Any], as_of: str | None,
                    document_index: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    if event.get("intelligence_type") != "reported_fact":
        reasons.append("not_reported_fact")
    if event.get("quality_flags"):
        reasons.append("blocking_quality_flags")
    level = event.get("source_quality_level")
    if not isinstance(level, int) or not (1 <= level <= 3):
        reasons.append("invalid_source_quality_level")
    effective_date = event.get("effective_date")
    if not effective_date:
        reasons.append("missing_effective_date")
    detected = _parse_time(event.get("detected_at"))
    cutoff = _parse_time(as_of)
    if not detected:
        reasons.append("missing_detected_at")
    elif cutoff and detected > cutoff:
        reasons.append("future_detected_at")
    evidence_rows = event.get("evidence") if isinstance(event.get("evidence"), list) else []
    if not evidence_rows:
        reasons.append("missing_evidence")
        return None, reasons
    ev = evidence_rows[0] or {}
    doc = (document_index or {}).get(ev.get("document_id")) or {}
    if document_index is not None:
        if not doc:
            reasons.append("document_not_retained")
        elif doc.get("status") != "ready":
            reasons.append("document_not_ready")
    url = ev.get("source_url") or event.get("source_url")
    if not re.match(r"^https?://", str(url or ""), re.I):
        reasons.append("invalid_source_url")
    if event.get("source_url") and url != event.get("source_url"):
        reasons.append("event_evidence_url_mismatch")
    if doc:
        if doc.get("source_url") != url:
            reasons.append("document_url_mismatch")
        if doc.get("content_sha256") != ev.get("content_sha256"):
            reasons.append("document_hash_mismatch")
    required = {
        "document_id": ev.get("document_id"),
        "content_sha256": ev.get("content_sha256"),
        "evidence_sha256": ev.get("evidence_sha256"),
        "page": ev.get("page"),
        "text": ev.get("text"),
    }
    for key, value in required.items():
        if value in (None, ""):
            reasons.append(f"missing_{key}")
    if ev.get("content_sha256") and not HEX64.fullmatch(str(ev.get("content_sha256"))):
        reasons.append("invalid_content_sha256")
    if ev.get("evidence_sha256") and not HEX64.fullmatch(str(ev.get("evidence_sha256"))):
        reasons.append("invalid_evidence_sha256")
    page = ev.get("page")
    if not isinstance(page, int) or page <= 0:
        reasons.append("invalid_page")
    available_at = _iso_time(doc.get("retrieved_at") if doc else event.get("detected_at"))
    if not available_at:
        reasons.append("missing_available_at")
    elif cutoff and _parse_time(available_at) and _parse_time(available_at) > cutoff:
        reasons.append("future_available_at")
    if freshness_band(effective_date, as_of) == "future":
        reasons.append("future_effective_date")
    if reasons:
        return None, sorted(set(reasons))
    return {
        "document_id": ev.get("document_id"),
        "content_sha256": ev.get("content_sha256"),
        "evidence_sha256": ev.get("evidence_sha256"),
        "source_url": url,
        "source": ev.get("source") or "official source",
        "page": page,
        "text": str(ev.get("text") or "")[:280],
        "source_quality_level": level,
        "document_retrieved_at": _iso_time(doc.get("retrieved_at")) if doc else None,
        "document_published_at": _iso_time(doc.get("published_at")) if doc else None,
    }, []


def _clean_person(value: str) -> str:
    value = re.sub(r"\s+(?:has\s+been|was|is)\s*$", "", value or "", flags=re.I)
    value = re.sub(r",.*$", "", value)
    value = re.sub(r"\b(?:CBE|SI|Pk|PK)\b\.?", "", value)
    value = re.sub(r"\s+", " ", value).strip(" -–.,")
    return _title(value)


def _management_payloads(text: str) -> list[dict[str, str]]:
    verbs = r"appointed|re-appointed|reappointed|resigned|resignation"
    roles = r"President\s*&\s*CEO|Chief Executive Officer|CEO|President|Chairman(?:\s+of\s+the\s+Board(?:\s+of\s+Directors)?)?|Chairperson|Director|Chief Financial Officer|CFO|Company Secretary"
    person = r"((?:Mr\.|Mrs\.|Ms\.|Lord|Syed|Mirza)?\s*[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,5})"
    patterns = [
        rf"(?P<person>{person})\s+(?:has\s+been\s+|was\s+|is\s+)?(?P<verb>{verbs})\s+(?:as|from\s+the\s+position\s+of)?\s*(?:the\s+)?(?P<role>{roles})",
        rf"(?P<verb>{verbs})\s+(?:of\s+)?(?:a\s+)?(?P<role>{roles})\s*[–-]\s*(?P<person>{person})",
        rf"(?P<verb>appointment)\s+of\s+(?:a\s+)?(?P<role>Director)\s+(?P<person>{person})",
        rf"(?P<verb>appointed|re-appointed|reappointed)\s+(?P<person>{person})(?:,\s*[A-Z ,.]*)?\s+as\s+(?:the\s+)?(?P<role>{roles})",
    ]
    payloads = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            groups = match.groupdict()
            person_value = _clean_person(groups.get("person") or "")
            role_value = _title(groups.get("role") or "")
            verb_value = groups.get("verb") or ""
            if not person_value or not role_value or not verb_value:
                continue
            if _norm(person_value) in {"president ceo", "chief executive officer", "company secretary"}:
                continue
            verb_norm = "resignation" if "resign" in verb_value.lower() else ("re_appointment" if "re" in verb_value.lower() else "appointment")
            payload = {"person": person_value, "role": role_value, "verb": verb_norm}
            if payload not in payloads:
                payloads.append(payload)
    return payloads


def _management_payload(text: str) -> dict[str, str] | None:
    payloads = _management_payloads(text)
    return payloads[0] if payloads else None


def _acquisition_payload(text: str) -> dict[str, str] | None:
    lowered = text.lower()
    stage = None
    if re.search(r"public announcement of intention|announcement of intention|intention\s+to\s+acquire", lowered):
        stage = "intention"
    elif re.search(r"public announcement of public offer|public announcement of offer|public offer|offer\s+to\s+acquire", lowered):
        stage = "public_offer"
    elif re.search(r"\bapproved\b|\bapproval\b", lowered):
        stage = "approved"
    elif re.search(r"\bcompleted\b|\bcompletion\b", lowered):
        stage = "completed"
    elif re.search(r"\bterminated\b|\bwithdrawn\b|\bcancelled\b", lowered):
        stage = "terminated"
    if not stage:
        return None
    target_patterns = [
        r"(?:target company\)?\s*(?:,|namely|is)?\s*)([A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?|Company))",
        r"(?:shares?|share capital)\s+representing.*?\bof\s+(?:the\s+)?([A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?|Company))",
        r"(?:shares?|share capital)\s+of\s+([A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?|Company))",
        r"control\s+of\s+([A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?|Company))",
        r"(?:acquisition of|acquire)\s+(?:approximately\s+[\d.]+%[^A-Z]+)?([A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?|Company))",
    ]
    for pattern in target_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            target = _title(re.sub(r"\s*\(.*$", "", match.group(1)))
            if len(target.split()) >= 2:
                return {"stage": stage, "target": target}
    return None


def normalize_proposition(event: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    propositions, reasons = normalize_propositions(event)
    return (propositions[0], None) if propositions else (None, reasons[0] if reasons else "not_clusterable")


def normalize_propositions(event: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    text = f"{event.get('description') or ''} {event.get('document_title') or ''}"
    event_type = event.get("event_type")
    subtype = event.get("event_subtype")
    if event_type == "management_change" or subtype == "management_change":
        payloads = _management_payloads(text)
        if not payloads:
            return [], ["not_named_management_change"]
        propositions = []
        for payload in payloads:
            assertion = f"management:{payload['verb']}:{_norm(payload['person'])}:{_norm(payload['role'])}:{event.get('effective_date')}"
            conflict = f"management:{_norm(payload['role'])}:{event.get('effective_date')}"
            proposition = {"type": "management_change", **payload, "assertion_key": assertion, "conflict_key": conflict, "modality": payload["verb"]}
            if proposition not in propositions:
                propositions.append(proposition)
        return propositions, []
    if event_type == "acquisition_divestment" or subtype == "acquisition":
        payload = _acquisition_payload(text)
        if not payload:
            return [], ["not_explicit_acquisition_stage_target"]
        assertion = f"acquisition:{_norm(payload['target'])}:{payload['stage']}:{event.get('effective_date')}"
        conflict = f"acquisition:{_norm(payload['target'])}:{event.get('effective_date')}"
        return [{"type": "acquisition", **payload, "assertion_key": assertion, "conflict_key": conflict, "modality": payload["stage"]}], []
    return [], ["event_type_not_in_registry"]


def eligible_observations(event: dict[str, Any], as_of: str | None,
                          document_index: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    symbol = event.get("symbol") or event.get("company_id")
    evidence, reasons = _clean_evidence(event, as_of, document_index)
    propositions, prop_reasons = normalize_propositions(event)
    reasons.extend(prop_reasons)
    if not symbol:
        reasons.append("missing_symbol")
    if reasons:
        return [], sorted(set(reasons))
    assert evidence is not None and propositions
    originator = f"issuer:{symbol}"
    distributor = _distributor(evidence.get("source") or "", evidence.get("source_url") or "")
    observations = []
    for proposition in propositions:
        observations.append({
            "observation_id": event.get("event_id") or stable_key("obs", symbol, proposition["assertion_key"], evidence["evidence_sha256"]),
            "symbol": symbol,
            "event_id": event.get("event_id"),
            "intelligence_type": event.get("intelligence_type"),
            "effective_date": event.get("effective_date"),
            "detected_at": _iso_time(event.get("detected_at")),
            "available_at": evidence.get("document_retrieved_at") or _iso_time(event.get("detected_at")),
            "originator": originator,
            "distributor": distributor,
            "distributors": [distributor],
            "proposition": proposition,
            "evidence": evidence,
            "provenance": [evidence],
        })
    return observations, []


def eligible_observation(event: dict[str, Any], as_of: str | None,
                         document_index: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    observations, reasons = eligible_observations(event, as_of, document_index)
    return (observations[0], []) if observations else (None, reasons)


def deduplicate_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for obs in sorted(observations, key=lambda o: (o.get("detected_at") or "", o.get("observation_id") or "")):
        key = (obs["proposition"]["assertion_key"], obs["originator"])
        if key not in by_key:
            by_key[key] = obs
            continue
        current = by_key[key]
        current["distributors"] = sorted(set((current.get("distributors") or [current.get("distributor")]) + (obs.get("distributors") or [obs.get("distributor")])))
        current["provenance"] = (current.get("provenance") or [current.get("evidence")]) + (obs.get("provenance") or [obs.get("evidence")])
        current.setdefault("duplicates", []).append({
            "observation_id": obs.get("observation_id"),
            "event_id": obs.get("event_id"),
            "distributor": obs.get("distributor"),
            "evidence_sha256": (obs.get("evidence") or {}).get("evidence_sha256"),
        })
    return list(by_key.values())


def _incompatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    pair = (left.get("modality"), right.get("modality"))
    if left["type"] == "acquisition" and pair in INCOMPATIBLE_ACQUISITION_STAGES:
        return True
    if left["type"] == "management_change" and pair in {("appointment", "resignation"), ("re_appointment", "resignation"), ("resignation", "appointment"), ("resignation", "re_appointment")}:
        return True
    return False


def _supersedes(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["type"] != "acquisition" or right["type"] != "acquisition":
        return False
    return SEQUENTIAL_ACQUISITION_STAGES.get(left.get("modality"), 0) > SEQUENTIAL_ACQUISITION_STAGES.get(right.get("modality"), 0)


def _assessment(rows: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    proposition = rows[0]["proposition"]
    originators = {row["originator"] for row in rows}
    incompatible_same_originator = []
    incompatible_independent = []
    superseded = []
    for other in all_rows:
        other_prop = other["proposition"]
        if other_prop["conflict_key"] != proposition["conflict_key"]:
            continue
        if other_prop["assertion_key"] == proposition["assertion_key"]:
            continue
        if _incompatible(proposition, other_prop):
            if originators.isdisjoint({other["originator"]}):
                incompatible_independent.append(other_prop["assertion_key"])
            else:
                incompatible_same_originator.append(other_prop["assertion_key"])
        elif _supersedes(proposition, other_prop):
            superseded.append(other_prop["assertion_key"])
    if incompatible_independent:
        return "contested", sorted(set(incompatible_independent))
    if incompatible_same_originator:
        return "inconsistent", sorted(set(incompatible_same_originator))
    if superseded:
        return "supersession", sorted(set(superseded))
    return ("corroborated" if len(originators) >= 2 else "single_source"), []


def cluster_observations(symbol: str, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = deduplicate_observations(observations)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["proposition"]["assertion_key"], []).append(row)
    clusters = []
    for assertion_key, members in sorted(grouped.items()):
        prop = members[0]["proposition"]
        originators = sorted({m["originator"] for m in members})
        distributors = sorted({d for m in members for d in (m.get("distributors") or [m.get("distributor")]) if d})
        assessment, related_assertions = _assessment(members, rows)
        band = {
            "single_source": "single_official_source",
            "corroborated": "corroborated_official_sources",
            "contested": "contested_official_sources",
            "inconsistent": "same_originator_inconsistent",
            "supersession": "same_originator_supersession",
        }[assessment]
        clusters.append({
            "cluster_id": stable_key("cluster", symbol, assertion_key),
            "symbol": symbol,
            "registry_version": REGISTRY_VERSION,
            "assessment": assessment,
            "confidence": {
                "band": band,
                "components": {
                    "originator_count": len(originators),
                    "distributor_count": len(distributors),
                    "evidence_rows": len(members),
                    "source_quality_levels": sorted({m["evidence"]["source_quality_level"] for m in members}),
                },
            },
            "proposition": {k: v for k, v in prop.items() if k not in {"assertion_key", "conflict_key"}},
            "assertion_key": assertion_key,
            "conflict_key": prop["conflict_key"],
            "originators": originators,
            "distributors": distributors,
            "related_assertion_keys": related_assertions,
            "observations": [{
                "observation_id": m["observation_id"],
                "event_id": m.get("event_id"),
                "effective_date": m.get("effective_date"),
                "detected_at": m.get("detected_at"),
                "originator": m.get("originator"),
                "distributor": m.get("distributor"),
                "evidence": m.get("evidence"),
                "provenance": m.get("provenance") or [m.get("evidence")],
                "duplicates": m.get("duplicates", []),
            } for m in members],
            "quality_flags": [],
        })
    return clusters


def build_signal_state(operating_events: dict[str, Any], pilot_symbols: list[str], as_of: str | None = None,
                       document_index: dict[str, Any] | None = None) -> dict[str, Any]:
    as_of = as_of or derive_as_of(operating_events, document_index)
    companies = {}
    for symbol in sorted(pilot_symbols):
        events = ((operating_events.get("companies") or {}).get(symbol) or {}).get("events") or []
        eligible: list[dict[str, Any]] = []
        rejections: dict[str, int] = {}
        latest = None
        for event in events:
            detected = event.get("detected_at")
            if detected and (latest is None or str(detected) > str(latest)):
                latest = detected
            observations, reasons = eligible_observations(event, as_of, document_index)
            if observations:
                eligible.extend(observations)
            else:
                for reason in reasons or ["not_clusterable"]:
                    rejections[reason] = rejections.get(reason, 0) + 1
        clusters = cluster_observations(symbol, eligible)
        if clusters:
            coverage_status = "clusterable"
        elif eligible:
            coverage_status = "eligible_unclustered"
        elif events:
            coverage_status = "rejected"
        else:
            coverage_status = "no_candidates"
        companies[symbol] = {
            "candidate_count": len(events),
            "eligible_count": len(eligible),
            "clusterable_count": len(clusters),
            "coverage_status": coverage_status,
            "rejection_reasons": dict(sorted(rejections.items())),
            "latest_detected_at": latest,
            "freshness": freshness_band(latest[:10] if latest else None, as_of),
            "clusters": clusters,
        }
    return {
        "schema_version": 1,
        "registry_version": REGISTRY_VERSION,
        "as_of": as_of,
        "pilot_symbols": sorted(pilot_symbols),
        "companies": companies,
        "source": "state/company_intel/operating_events.json",
    }
