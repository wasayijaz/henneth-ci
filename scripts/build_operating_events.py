"""Build evidence-backed operating events for the declared CI pilot."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from psx_data import ROOT, STATE, load_json, save_json
from operating_events import (
    TYPE_MAP, bounded_text, evidence_hash, stable_id, source_quality,
    confidence, quality_flags, iso_date, strict_event_is_supported,
)
from document_events import event_is_supported

OUT = STATE / "company_intel" / "operating_events.json"

def build() -> dict:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = (profiles.get("pilot") or {}).get("symbols") or []
    docs = (load_json(STATE / "company_documents.json", {}).get("documents") or {})
    ledger = load_json(STATE / "company_event_ledger.json", {}).get("companies") or {}
    companies = {}
    for sym in sorted(pilot):
        out = []
        for raw in (ledger.get(sym, {}).get("events") or []):
            event_type = TYPE_MAP.get(raw.get("event_type"))
            evidence = [e for e in (raw.get("evidence") or []) if isinstance(e, dict) and e.get("text") and e.get("source_url")]
            doc = docs.get(raw.get("doc_id"), {})
            if not event_type or not evidence or not event_is_supported(raw) or not strict_event_is_supported(event_type, evidence):
                continue
            url = evidence[0].get("source_url") or doc.get("source_url")
            excerpt = bounded_text(evidence[0].get("text"))
            event = {
                "event_id": stable_id(sym, raw.get("event_id") or raw.get("doc_id"), event_type),
                "company_id": sym, "symbol": sym, "event_type": event_type,
                "event_subtype": raw.get("event_type"), "intelligence_type": "reported_fact",
                "priority_weight": raw.get("priority_weight"),
                "detected_at": raw.get("event_date") or doc.get("retrieved_at"),
                "effective_date": iso_date(raw.get("event_date")), "expected_completion": None,
                "business_segment": None, "location": None,
                "description": excerpt, "source_url": url,
                "source_quality_level": source_quality(url, doc.get("source")),
                "confidence": 0, "estimated_scale": None, "expected_cost": None,
                "affected_drivers": [], "expected_lag": None, "historical_analogues": [],
                "peer_analogues": [], "scenario_ids": [], "financial_model_version": None,
                "evidence": [
                    {
                        "document_id": raw.get("doc_id"),
                        "source": doc.get("source"),
                        "source_url": e.get("source_url"),
                        "page": e.get("page"),
                        "text": bounded_text(e.get("text")),
                        "content_sha256": doc.get("content_sha256"),
                        "evidence_sha256": evidence_hash(raw.get("doc_id"), e.get("source_url"), e.get("page"), e.get("text")),
                    }
                    for e in evidence[:3]
                ],
                "quality_flags": [],
            }
            recency_days = None
            effective = iso_date(raw.get("event_date"))
            if effective:
                try:
                    recency_days = max(0, (date.today() - date.fromisoformat(effective)).days)
                except ValueError:
                    recency_days = None
            event["confidence"] = confidence(event["source_quality_level"], len(event["evidence"]), recency_days=recency_days)
            event["quality_flags"] = quality_flags(event)
            out.append(event)
        out.sort(key=lambda e: (e.get("effective_date") or "", e["event_id"]), reverse=True)
        companies[sym] = {"events": out}
    result = {"schema_version": 1, "pilot_symbols": sorted(pilot), "companies": companies,
              "event_types": sorted(TYPE_MAP.values()), "source": "state/company_documents.json + state/company_event_ledger.json"}
    save_json(OUT, result)
    print(f"operating_events: {sum(len(v['events']) for v in companies.values())} events across {len(companies)} pilot companies")
    return result

if __name__ == "__main__": build()
