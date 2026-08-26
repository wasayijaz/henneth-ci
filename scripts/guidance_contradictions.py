"""First-class guidance and contradiction objects for Company Intelligence.

The builder is intentionally narrow: it only reads retained document evidence,
accepts explicit official-source assertion language, and emits categorical
objects. Numeric forecasts, valuation language, advice language and browser
inference stay out of the state product.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any


SCHEMA_VERSION = 1
GUIDANCE_VERSION = "guidance_contradictions_v1"
PKT = timezone(timedelta(hours=5))
FORBIDDEN_TEXT = (
    "buy",
    "sell",
    "recommend",
    "target price",
    "fair value",
    "upside",
    "downside",
    "probability",
    "guarantee",
    "return",
    "profit forecast",
    "eps forecast",
)
NUMERIC_FORECAST = re.compile(
    r"\b(?:forecast|target|guidance|expect(?:s|ed|ing)?|project(?:s|ed|ion)?|estimate(?:s|d)?)\b.{0,90}"
    r"(?:\d|rs\.?|pkr|%|percent|eps|revenue|sales|profit|pat|margin)",
    re.I | re.S,
)
GUIDANCE_PATTERNS = (
    re.compile(r"\b(?:company|management|board|directors|we)\s+(?:expects?|plans?|intends?|aims?|seeks?)\s+to\s+(?P<body>[^.;:]{12,180})", re.I),
    re.compile(r"\b(?:strategy|objective|focus|priority)\s+(?:is|remains|will be)\s+(?:to\s+)?(?P<body>[^.;:]{12,180})", re.I),
    re.compile(r"\b(?:company|management|board|directors|we)\s+(?:will|shall)\s+(?P<body>continue\s+to\s+[^.;:]{12,160})", re.I),
)
RISK_PATTERNS = (
    re.compile(r"\b(?:risk|risks)\s+(?:of|include|includes|remain|relate to)\s+(?P<body>[^.;:]{12,180})", re.I),
    re.compile(r"\b(?:challenge|challenges|uncertainty|uncertainties)\s+(?:include|includes|remain|relate to|around)\s+(?P<body>[^.;:]{12,180})", re.I),
    re.compile(r"\b(?P<body>(?:default in payment of debts|going concern|liquidity problems|trading halt))\b", re.I),
)
INCOMPATIBLE_MODALITIES = {
    ("increase", "decrease"),
    ("decrease", "increase"),
    ("continue", "stop"),
    ("stop", "continue"),
    ("proceed", "cancel"),
    ("cancel", "proceed"),
    ("risk_present", "risk_mitigated"),
    ("risk_mitigated", "risk_present"),
}


def _stable_id(prefix: str, *parts: Any) -> str:
    text = "\x1f".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]}"


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _text(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[: limit - 1].rstrip() + "..." if len(text) > limit else text


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        text = f"{text}T00:00:00"
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


def _derive_as_of(document_state: dict[str, Any]) -> str:
    values = []
    for doc in (document_state.get("documents") or {}).values():
        if not isinstance(doc, dict):
            continue
        parsed = _parse_time(doc.get("retrieved_at") or doc.get("published_at") or doc.get("date"))
        if parsed:
            values.append(parsed)
    if values:
        return max(values).isoformat()
    return "unknown"


def _is_url(value: Any) -> bool:
    return bool(re.match(r"^https?://", str(value or ""), re.I))


def _safe_language(text: str) -> bool:
    lowered = text.lower()
    if NUMERIC_FORECAST.search(text):
        return False
    return not any(term in lowered for term in FORBIDDEN_TEXT)


def _clean_evidence(doc: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any] | None:
    url = evidence.get("source_url") or doc.get("source_url")
    page = evidence.get("page")
    if not _is_url(url) or not isinstance(page, int) or page <= 0:
        return None
    doc_id = evidence.get("document_id") or evidence.get("doc_id") or doc.get("doc_id")
    available_on = _iso_time(doc.get("retrieved_at") or doc.get("published_at") or doc.get("date"))
    if not doc_id or not available_on:
        return None
    return {
        "document_id": doc_id,
        "source_url": url,
        "source": evidence.get("source") or doc.get("source") or "official source",
        "page": page,
        "available_on": available_on,
        "content_sha256": evidence.get("content_sha256") or doc.get("content_sha256"),
        "evidence_sha256": evidence.get("evidence_sha256"),
        "text": _text(evidence.get("text")),
    }


def _topic(body: str) -> str:
    cleaned = re.sub(
        r"\b(?:the|a|an|its|our|their|company|business|operations?|"
        r"expand|expansion|increase|grow|growth|improve|raise|reduce|reduction|decrease|decline|lower|fall|"
        r"continue|maintain|sustain|stop|discontinue|cancel|terminate|withdraw)\b",
        " ",
        body,
        flags=re.I,
    )
    words = [_norm(word) for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", cleaned)[:8]]
    return "_".join(word for word in words if word) or "unspecified"


def _modality(text: str, domain: str) -> str:
    lowered = text.lower()
    if domain == "risks":
        if re.search(r"\b(?:mitigat|reduce|resolved|improved|eased)\w*\b", lowered):
            return "risk_mitigated"
        return "risk_present"
    if re.search(r"\b(?:decrease|decline|reduce|lower|fall)\w*\b", lowered):
        return "decrease"
    if re.search(r"\b(?:increase|expand|grow|improve|raise)\w*\b", lowered):
        return "increase"
    if re.search(r"\b(?:cancel|terminate|withdraw|stop|discontinue)\w*\b", lowered):
        return "cancel" if re.search(r"\b(?:cancel|terminate|withdraw)\w*\b", lowered) else "stop"
    if re.search(r"\b(?:continue|maintain|sustain)\w*\b", lowered):
        return "continue"
    return "proceed"


def _extract_assertion(symbol: str, doc: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any] | None:
    clean = _clean_evidence(doc, evidence)
    if not clean or not clean.get("text") or not _safe_language(clean["text"]):
        return None
    for domain, patterns in (("guidance", GUIDANCE_PATTERNS), ("risks", RISK_PATTERNS)):
        for pattern in patterns:
            match = pattern.search(clean["text"])
            if not match:
                continue
            body = _text(match.group("body"), 220)
            if not body or not _safe_language(body):
                return None
            topic = _topic(body)
            modality = _modality(body, domain)
            conflict_key = f"{domain}:{topic}"
            assertion_key = f"{conflict_key}:{modality}"
            guidance_id = _stable_id("guidance", symbol, assertion_key, clean["document_id"], clean["page"], clean.get("evidence_sha256"))
            return {
                "guidance_id": guidance_id,
                "symbol": symbol,
                "domain": domain,
                "status": "eligible",
                "statement": body,
                "modality": modality,
                "topic_key": topic,
                "assertion_key": assertion_key,
                "conflict_key": conflict_key,
                "evidence": clean,
                "policy": {
                    "same_company_official_evidence": True,
                    "numeric_forecast": False,
                    "valuation": False,
                    "advice": False,
                },
            }
    return None


def _iter_candidate_evidence(symbol: str, document_state: dict[str, Any]):
    for doc in (document_state.get("documents") or {}).values():
        if not isinstance(doc, dict) or symbol not in (doc.get("tickers") or []):
            continue
        for evidence in doc.get("evidence") or []:
            if isinstance(evidence, dict):
                yield doc, evidence
        for event in doc.get("events") or []:
            for evidence in (event or {}).get("evidence") or []:
                if isinstance(evidence, dict):
                    yield doc, evidence


def _contradictions(symbol: str, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    by_conflict: dict[str, list[dict[str, Any]]] = {}
    for obj in objects:
        by_conflict.setdefault(obj["conflict_key"], []).append(obj)
    for conflict_key, rows in sorted(by_conflict.items()):
        for left_index, left in enumerate(rows):
            for right in rows[left_index + 1:]:
                if left["assertion_key"] == right["assertion_key"]:
                    continue
                if (left["modality"], right["modality"]) not in INCOMPATIBLE_MODALITIES:
                    continue
                out.append({
                    "contradiction_id": _stable_id("contradiction", symbol, conflict_key, left["guidance_id"], right["guidance_id"]),
                    "symbol": symbol,
                    "status": "exact_key_conflict",
                    "conflict_key": conflict_key,
                    "object_ids": [left["guidance_id"], right["guidance_id"]],
                    "assertion_keys": [left["assertion_key"], right["assertion_key"]],
                    "match_rule": "same_company_exact_normalized_conflict_key_incompatible_modalities",
                    "evidence": [left["evidence"], right["evidence"]],
                })
    return out


def build_guidance_state(document_state: dict[str, Any], pilot_symbols: list[str], as_of: str | None = None) -> dict[str, Any]:
    companies = {}
    for symbol in sorted(pilot_symbols):
        by_id = {}
        for doc, evidence in _iter_candidate_evidence(symbol, document_state):
            obj = _extract_assertion(symbol, doc, evidence)
            if obj:
                by_id.setdefault(obj["guidance_id"], obj)
        objects = sorted(by_id.values(), key=lambda obj: (obj["evidence"]["available_on"], obj["guidance_id"]))
        contradictions = _contradictions(symbol, objects)
        guidance_count = sum(1 for obj in objects if obj.get("domain") == "guidance")
        risk_count = sum(1 for obj in objects if obj.get("domain") == "risks")
        companies[symbol] = {
            "symbol": symbol,
            "status": "available" if objects else "no_guidance_objects",
            "guidance_count": guidance_count,
            "risk_count": risk_count,
            "object_count": len(objects),
            "contradiction_count": len(contradictions),
            "objects": objects,
            "contradictions": contradictions,
            "unknowns": [] if objects else ["no_retained_official_evidence_with_strict_guidance_assertion_shape"],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "guidance_version": GUIDANCE_VERSION,
        "as_of": as_of or _derive_as_of(document_state),
        "pilot_symbols": sorted(pilot_symbols),
        "source": {
            "company_documents": "state/company_documents.json",
        },
        "policy": {
            "retained_state_only": True,
            "same_company_required": True,
            "official_evidence_required": True,
            "exact_normalized_key_conflicts_only": True,
            "no_numeric_forecast": True,
            "no_valuation": True,
            "no_advice": True,
        },
        "companies": companies,
    }
