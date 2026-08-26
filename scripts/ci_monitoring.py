"""Continuous Monitoring/Freshness v1 for Company Intelligence.

This composes retained CI state into one company-level monitoring row. It does
not fetch, score, forecast, value, or match loose browser-side evidence.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any


SCHEMA_VERSION = 1
MONITORING_VERSION = "ci_monitoring_v1"
PKT = timezone(timedelta(hours=5))
STATUSES = {"healthy", "degraded", "stale", "unknown"}
ALERT_TYPES = {
    "source_registry_degraded",
    "source_page_changed",
    "retained_change",
    "active_evidence_watch",
    "guidance_contradiction",
}
SOURCE_STALE_DAYS = 45
CHANGE_STALE_DAYS = 90
FORBIDDEN_TEXT = (
    "buy",
    "sell",
    "recommend",
    "target price",
    "fair value",
    "upside",
    "downside",
    "probability",
    "odds",
    "forecast",
    "valuation",
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


def _date(value: Any) -> str | None:
    parsed = _parse_time(value)
    return parsed.date().isoformat() if parsed else None


def _latest(*values: Any) -> str | None:
    parsed = [_parse_time(value) for value in values]
    parsed = [value for value in parsed if value is not None]
    return max(parsed).isoformat() if parsed else None


def _is_url(value: Any) -> bool:
    return str(value or "").startswith(("http://", "https://"))


def _source_ref(*, url: Any, document_id: Any = None, page: Any = None, source_id: Any = None, source: Any = None) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "source_url": url if _is_url(url) else None,
        "document_id": document_id,
        "source_id": source_id,
        "source": source,
    }
    if isinstance(page, int) and page >= 1:
        ref["page"] = page
    return ref


def _valid_source_ref(ref: dict[str, Any]) -> bool:
    return bool(_is_url(ref.get("source_url")))


def _source_as_of(
    source_registry: dict[str, Any],
    source_qa: dict[str, Any],
    change_intelligence: dict[str, Any],
    event_ledger: dict[str, Any],
    operating_events: dict[str, Any],
    evidence_watchlist: dict[str, Any],
    guidance_state: dict[str, Any],
) -> dict[str, str]:
    return {
        "source_registry": str(source_registry.get("updated") or "unknown"),
        "source_qa": str((source_qa.get("_meta") or {}).get("updated") or "unknown"),
        "change_intelligence": str((change_intelligence.get("_meta") or {}).get("updated") or "unknown"),
        "event_ledger": str((event_ledger.get("_meta") or {}).get("updated") or "unknown"),
        "operating_events": str(operating_events.get("as_of") or "unknown"),
        "evidence_watchlist": str(evidence_watchlist.get("as_of") or "unknown"),
        "guidance_contradictions": str(guidance_state.get("as_of") or "unknown"),
    }


def _derived_as_of(source_as_of: dict[str, str]) -> str:
    values = [_iso_time(value) for value in source_as_of.values()]
    values = [value for value in values if value]
    return max(values) if values else "unknown"


def _source_page_alerts(symbol: str, registry_row: dict[str, Any], source_qa_row: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    alerts = []
    latest_source_at = None
    for page in registry_row.get("monitored_pages") or []:
        if not isinstance(page, dict):
            continue
        if page.get("status") not in {"ok", "healthy", "not_modified"}:
            continue
        if not page.get("previous_sha256") or not page.get("last_changed_at"):
            continue
        changed_at = _iso_time(page.get("last_changed_at"))
        if not changed_at or not _is_url(page.get("url")):
            continue
        latest_source_at = _latest(latest_source_at, changed_at)
        source_id = None
        for sid in source_qa_row.get("source_ids") or []:
            if isinstance(sid, str):
                source_id = source_id or sid
        alerts.append({
            "alert_id": _stable_id("ci_alert", symbol, "source_page_changed", page.get("url"), page.get("last_changed_at"), page.get("content_sha256")),
            "symbol": symbol,
            "type": "source_page_changed",
            "status": "observed",
            "date": changed_at,
            "title": page.get("label") or page.get("kind") or "issuer page changed",
            "reason": "monitored issuer page changed after a prior retained hash",
            "source": _source_ref(url=page.get("url"), source_id=source_id, source="issuer_source_registry"),
            "evidence_identity": {
                "content_sha256": page.get("content_sha256"),
                "previous_sha256": page.get("previous_sha256"),
            },
        })
    return alerts, latest_source_at


def _source_discovery_latest(registry_row: dict[str, Any]) -> str | None:
    values = []
    for link in registry_row.get("document_links") or []:
        if isinstance(link, dict) and _is_url(link.get("url")):
            values.append(link.get("first_seen_at"))
    for page in registry_row.get("monitored_pages") or []:
        if isinstance(page, dict) and _is_url(page.get("url")) and page.get("status") in {"ok", "healthy", "not_modified"}:
            values.append(page.get("first_seen_at"))
    return _latest(*values)


def _registry_degraded_alert(symbol: str, registry_row: dict[str, Any], source_qa_row: dict[str, Any]) -> dict[str, Any] | None:
    status = registry_row.get("status") or source_qa_row.get("registry_status")
    flags = source_qa_row.get("quality_flags") or []
    if status in {"ok", "healthy"} and not source_qa_row.get("missing_required_source") and not flags:
        return None
    url = registry_row.get("dps_company_url") or registry_row.get("issuer_url") or source_qa_row.get("issuer_url")
    if not _is_url(url):
        return None
    return {
        "alert_id": _stable_id("ci_alert", symbol, "source_registry_degraded", status, ",".join(sorted(str(flag) for flag in flags))),
        "symbol": symbol,
        "type": "source_registry_degraded",
        "status": "open",
        "date": None,
        "title": "issuer source registry degraded",
        "reason": registry_row.get("error") or ", ".join(str(flag) for flag in flags) or "missing required issuer source",
        "source": _source_ref(url=url, source="issuer_source_registry"),
        "evidence_identity": {
            "registry_status": status or "unknown",
            "quality_flags": sorted(str(flag) for flag in flags),
            "missing_required_source": bool(source_qa_row.get("missing_required_source")),
        },
    }


def _change_alerts(symbol: str, change_row: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    alerts = []
    latest_change_at = _iso_time(change_row.get("latest_change_at"))
    for item in change_row.get("items") or []:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        source_url = item.get("source_url") or evidence.get("source_url")
        if not _is_url(source_url):
            continue
        if item.get("kind") in {"event", "financial"} and evidence.get("page") is not None:
            if not isinstance(evidence.get("page"), int) or evidence.get("page") < 1:
                continue
        date = _iso_time(item.get("date")) or _date(item.get("date"))
        latest_change_at = _latest(latest_change_at, date)
        alerts.append({
            "alert_id": _stable_id("ci_alert", symbol, "retained_change", item.get("id"), item.get("date"), source_url),
            "symbol": symbol,
            "type": "retained_change",
            "status": "observed",
            "date": date,
            "title": item.get("title") or item.get("kind") or "retained change",
            "reason": item.get("summary") or "retained change-intelligence item",
            "source": _source_ref(
                url=source_url,
                document_id=item.get("document_id"),
                page=evidence.get("page"),
                source="change_intelligence",
            ),
            "evidence_identity": {
                "change_id": item.get("id"),
                "kind": item.get("kind"),
                "date_basis": item.get("date_basis"),
            },
        })
    alerts.sort(key=lambda row: (row.get("date") or "", row.get("alert_id") or ""), reverse=True)
    return alerts[:6], latest_change_at


def _watch_alerts(symbol: str, watch_row: dict[str, Any]) -> list[dict[str, Any]]:
    alerts = []
    for item in watch_row.get("items") or []:
        if not isinstance(item, dict):
            continue
        evidence = (item.get("matched_evidence") or item.get("source_evidence") or [])
        source = next((ref for ref in evidence if isinstance(ref, dict) and _is_url(ref.get("source_url"))), None)
        if not source:
            continue
        alerts.append({
            "alert_id": _stable_id("ci_alert", symbol, "active_evidence_watch", item.get("watch_id"), item.get("status")),
            "symbol": symbol,
            "type": "active_evidence_watch",
            "status": item.get("status") or "watching",
            "date": ((item.get("source_assertion") or {}).get("available_at") or (item.get("matched_event") or {}).get("available_at")),
            "title": item.get("monitored_assertion") or item.get("watch_id") or "evidence watch",
            "reason": item.get("status_reason") or "active exact-ID evidence watch",
            "source": _source_ref(
                url=source.get("source_url"),
                document_id=source.get("document_id"),
                page=source.get("page"),
                source=source.get("source") or "evidence_watchlist",
            ),
            "evidence_identity": {
                "watch_id": item.get("watch_id"),
                "thesis_id": (item.get("ids") or {}).get("thesis_id"),
                "source_cluster_id": (item.get("ids") or {}).get("source_cluster_id"),
                "delivery_id": (item.get("ids") or {}).get("delivery_id"),
                "matched_event_id": (item.get("ids") or {}).get("matched_event_id"),
            },
        })
    return alerts


def _guidance_contradiction_alerts(symbol: str, guidance_row: dict[str, Any]) -> list[dict[str, Any]]:
    alerts = []
    for item in guidance_row.get("contradictions") or []:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") or []
        source = next((ref for ref in evidence if isinstance(ref, dict) and _is_url(ref.get("source_url"))), None)
        if not source:
            continue
        alerts.append({
            "alert_id": _stable_id("ci_alert", symbol, "guidance_contradiction", item.get("contradiction_id")),
            "symbol": symbol,
            "type": "guidance_contradiction",
            "status": item.get("status") or "exact_key_conflict",
            "date": source.get("available_on"),
            "title": item.get("conflict_key") or "guidance contradiction",
            "reason": item.get("match_rule") or "exact normalized-key contradiction",
            "source": _source_ref(
                url=source.get("source_url"),
                document_id=source.get("document_id"),
                page=source.get("page"),
                source=source.get("source") or "guidance_contradictions",
            ),
            "evidence_identity": {
                "contradiction_id": item.get("contradiction_id"),
                "object_ids": item.get("object_ids") or [],
            },
        })
    return alerts


def _event_latest(symbol: str, event_row: dict[str, Any], operating_row: dict[str, Any]) -> str | None:
    values = []
    for event in event_row.get("events") or []:
        if isinstance(event, dict) and symbol in (event.get("tickers") or []):
            values.append(event.get("event_date"))
    for event in operating_row.get("events") or []:
        if isinstance(event, dict) and event.get("symbol") == symbol:
            values.extend([event.get("detected_at"), event.get("effective_date")])
    return _latest(*values)


def _is_stale(latest_at: str | None, as_of: str, days: int) -> bool:
    latest = _parse_time(latest_at)
    current = _parse_time(as_of)
    if not latest or not current:
        return False
    return latest < current - timedelta(days=days)


def _row_status(
    *,
    known: bool,
    degraded: bool,
    latest_source_at: str | None,
    latest_change_at: str | None,
    as_of: str,
) -> str:
    if not known:
        return "unknown"
    if degraded:
        return "degraded"
    # A quiet company can have no retained change at all.  An old source is still
    # stale in that case; requiring a missing change timestamp to be stale would
    # incorrectly label an unobserved, old source healthy.
    if _is_stale(latest_source_at, as_of, SOURCE_STALE_DAYS) and (
        not _parse_time(latest_change_at) or _is_stale(latest_change_at, as_of, CHANGE_STALE_DAYS)
    ):
        return "stale"
    return "healthy"


def build_ci_monitoring(
    source_registry: dict[str, Any],
    source_qa: dict[str, Any],
    change_intelligence: dict[str, Any],
    event_ledger: dict[str, Any],
    operating_events: dict[str, Any],
    evidence_watchlist: dict[str, Any],
    guidance_state: dict[str, Any],
    *,
    pilot_symbols: list[str],
) -> dict[str, Any]:
    source_as_of = _source_as_of(source_registry, source_qa, change_intelligence, event_ledger, operating_events, evidence_watchlist, guidance_state)
    as_of = _derived_as_of(source_as_of)
    registry_rows = source_registry.get("tickers") or {}
    qa_rows = source_qa.get("tickers") or {}
    change_rows = change_intelligence.get("companies") or {}
    event_rows = event_ledger.get("companies") or {}
    operating_rows = operating_events.get("companies") or {}
    watch_rows = evidence_watchlist.get("companies") or {}
    guidance_rows = guidance_state.get("companies") or {}
    companies: dict[str, Any] = {}
    status_counts = {status: 0 for status in sorted(STATUSES)}
    alert_count = 0
    for symbol in pilot_symbols:
        registry_row = registry_rows.get(symbol) or {}
        qa_row = qa_rows.get(symbol) or {}
        change_row = change_rows.get(symbol) or {}
        event_row = event_rows.get(symbol) or {}
        operating_row = operating_rows.get(symbol) or {}
        watch_row = watch_rows.get(symbol) or {}
        guidance_row = guidance_rows.get(symbol) or {}
        known = any(row for row in (registry_row, qa_row, change_row, event_row, operating_row, watch_row, guidance_row))
        source_alerts, page_latest = _source_page_alerts(symbol, registry_row, qa_row)
        degraded_alert = _registry_degraded_alert(symbol, registry_row, qa_row)
        if degraded_alert:
            source_alerts.insert(0, degraded_alert)
        change_alerts, change_latest = _change_alerts(symbol, change_row)
        event_latest = _event_latest(symbol, event_row, operating_row)
        latest_source_at = _latest(page_latest, _source_discovery_latest(registry_row))
        latest_change_at = _latest(change_latest, event_latest)
        alerts = source_alerts + change_alerts + _watch_alerts(symbol, watch_row) + _guidance_contradiction_alerts(symbol, guidance_row)
        alerts = [alert for alert in alerts if _valid_source_ref(alert.get("source") or {})]
        alerts.sort(key=lambda row: (row.get("date") or "", row.get("alert_id") or ""), reverse=True)
        degraded = bool(degraded_alert)
        status = _row_status(
            known=known,
            degraded=degraded,
            latest_source_at=latest_source_at,
            latest_change_at=latest_change_at,
            as_of=as_of,
        )
        status_counts[status] += 1
        alert_count += len(alerts)
        companies[symbol] = {
            "symbol": symbol,
            "status": status,
            "status_reason": (
                "source registry or monitored source quality is degraded" if status == "degraded"
                else "retained source and change timestamps are stale" if status == "stale"
                else "no retained monitoring source row exists" if status == "unknown"
                else "retained monitoring sources are current enough and no degraded source gate is open"
            ),
            "latest_source_at": latest_source_at,
            "latest_change_at": latest_change_at,
            "latest_event_at": event_latest,
            "source_health": {
                "registry_status": registry_row.get("status") or qa_row.get("registry_status") or "unknown",
                "monitored_page_count": qa_row.get("monitored_page_count") or 0,
                "document_link_count": qa_row.get("document_link_count") or 0,
                "quality_flags": qa_row.get("quality_flags") or [],
                "missing_required_source": bool(qa_row.get("missing_required_source")),
            },
            "activity": {
                "change_status": change_row.get("status") or "unknown",
                "change_counts": change_row.get("counts") or {},
                "watch_status": watch_row.get("status") or "unknown",
                "active_watch_count": watch_row.get("active_watch_count") or 0,
                "guidance_status": guidance_row.get("status") or "unknown",
                "guidance_contradiction_count": guidance_row.get("contradiction_count") or 0,
            },
            "alerts": alerts,
            "alert_count": len(alerts),
            "limitations": [
                "research_only",
                "retained_state_only",
                "no_lookahead",
                "no_scores",
                "no_forecasts",
                "no_valuation",
                "no_advice",
            ],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "monitoring_version": MONITORING_VERSION,
        "as_of": as_of,
        "source_as_of": source_as_of,
        "pilot_symbols": list(pilot_symbols),
        "source": {
            "source_registry": "state/company_intel/source_registry.json",
            "source_qa": "state/company_source_qa.json",
            "change_intelligence": "state/company_intel/change_intelligence.json",
            "event_ledger": "state/company_event_ledger.json",
            "operating_events": "state/company_intel/operating_events.json",
            "evidence_watchlist": "state/company_intel/evidence_watchlist.json",
            "guidance_contradictions": "state/company_intel/guidance_contradictions.json",
        },
        "policy": {
            "research_only": True,
            "retained_state_only": True,
            "categorical_status_only": True,
            "source_provenance_required": True,
            "previous_hash_required_for_page_change": True,
            "degraded_source_never_marked_fresh": True,
            "no_browser_inference": True,
            "no_lookahead": True,
            "no_scores": True,
            "no_forecasts": True,
            "no_valuation": True,
            "no_advice": True,
        },
        "status_vocabulary": sorted(STATUSES),
        "alert_type_vocabulary": sorted(ALERT_TYPES),
        "staleness_policy": {
            "source_stale_days": SOURCE_STALE_DAYS,
            "change_stale_days": CHANGE_STALE_DAYS,
            "basis": "relative_to_latest_retained_source_timestamp",
        },
        "summary": {
            "company_count": len(pilot_symbols),
            "alert_count": alert_count,
            "status_counts": status_counts,
        },
        "companies": companies,
    }
