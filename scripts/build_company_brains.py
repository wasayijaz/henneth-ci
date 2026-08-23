"""Build the compact, reference-only Company Brain index for the CI pilot."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intelligence_types import BRAIN_DOMAINS, INTELLIGENCE_TYPES, SOURCE_PRODUCTS
from psx_data import STATE, load_json, save_json

OUT = STATE / "company_intel" / "company_brains.json"

BRIEF_DOMAIN_MAP = {
    "what_changed": ("projects", "catalysts", "historical_events"),
    "financial_read": ("financial_statements", "operating_kpis"),
    "management_and_capital": ("management", "capital_allocation"),
}
EVENT_DOMAIN_MAP = {
    "hiring_expansion": ("employees", "capacity"),
    "capacity_plant_expansion": ("capacity", "facilities", "projects"),
    "exploration_well_discovery": ("capacity", "projects", "catalysts"),
    "contract_tender": ("customers", "projects", "catalysts"),
    "management_change": ("management",),
    "debt_refinancing": ("capital_allocation", "risks"),
    "product_launch": ("products", "catalysts"),
    "supplier_change": ("suppliers", "risks"),
    "maintenance_shutdown": ("facilities", "capacity", "risks"),
    "regulatory_change": ("risks", "catalysts"),
    "acquisition_divestment": ("subsidiaries", "capital_allocation", "catalysts"),
}


def _stable_id(symbol: str, product: str, source_id: str) -> str:
    raw = f"{symbol}|{product}|{source_id}".encode("utf-8")
    return "bio_" + hashlib.sha256(raw).hexdigest()[:20]


def _date(value: object) -> str | None:
    return value[:10] if isinstance(value, str) and len(value) >= 10 else None


def _evidence_refs(evidence: object) -> list[dict]:
    rows = evidence if isinstance(evidence, list) else [evidence] if isinstance(evidence, dict) else []
    refs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ref = {key: row[key] for key in (
            "document_id", "doc_id", "page", "content_sha256", "evidence_sha256", "source_url"
        ) if row.get(key) is not None}
        if ref:
            refs.append(ref)
    return refs[:3]


def _domains() -> dict:
    rows = {domain: {"status": "unknown", "object_refs": []} for domain in BRAIN_DOMAINS}
    rows["forecasts"] = {"status": "blocked", "object_refs": [], "reason": "forecast_objects_not_permitted"}
    rows["valuation"] = {"status": "blocked", "object_refs": [], "reason": "valuation_objects_not_permitted"}
    return rows


def _add_object(objects: list[dict], domains: dict, symbol: str, product: str, source_id: str,
                typ: str, domain_names: tuple[str, ...], available_on: str,
                evidence_refs: list[dict], confidence: int | None,
                input_refs: list[str] | None = None) -> None:
    obj = {
        "id": _stable_id(symbol, product, source_id),
        "type": typ,
        "source_product": product,
        "source_id": source_id,
        "available_on": available_on,
        "evidence_refs": evidence_refs,
        "confidence": confidence,
        "brain_paths": [f"companies/{symbol}/domains/{name}" for name in domain_names],
    }
    if input_refs:
        obj["input_refs"] = input_refs
    objects.append(obj)
    for name in domain_names:
        domains[name]["object_refs"].append(obj["id"])


def _brief_objects(symbol: str, briefs: dict, domains: dict, objects: list[dict]) -> None:
    history = (((briefs.get("companies") or {}).get(symbol) or {}).get("history") or [])
    for brief in history:
        approved_on = _date(brief.get("approved_at"))
        brief_id = brief.get("brief_id")
        if brief.get("status") != "owner_approved" or not approved_on or not brief_id:
            continue
        for section, domain_names in BRIEF_DOMAIN_MAP.items():
            for index, row in enumerate(((brief.get("sections") or {}).get(section) or [])):
                if not isinstance(row, dict):
                    continue
                evidence = _evidence_refs(row.get("evidence"))
                if evidence:
                    _add_object(objects, domains, symbol, "company_briefs", f"{brief_id}:{section}:{index}",
                                "reported_fact", domain_names, approved_on, evidence, 90)


def _event_objects(symbol: str, operating: dict, domains: dict, objects: list[dict]) -> None:
    events = (((operating.get("companies") or {}).get(symbol) or {}).get("events") or [])
    for event in events:
        event_id = event.get("event_id")
        available_on = _date(event.get("detected_at") or event.get("effective_date"))
        evidence = _evidence_refs(event.get("evidence"))
        if not event_id or not available_on or not evidence:
            continue
        domain_names = tuple(dict.fromkeys(EVENT_DOMAIN_MAP.get(event.get("event_type"), ()) + ("historical_events",)))
        typ = event.get("intelligence_type") or "reported_fact"
        if typ not in {"reported_fact", "derived_fact", "inference"}:
            typ = "reported_fact"
        _add_object(objects, domains, symbol, "operating_events", event_id, typ, domain_names,
                    available_on, evidence, event.get("confidence"))


def _study_objects(symbol: str, studies: dict, domains: dict, objects: list[dict]) -> None:
    for study_id, study in sorted((studies.get("studies") or {}).items()):
        available_on = _date(study.get("data_cutoff") or study.get("effective_date"))
        if study.get("symbol") != symbol or not available_on:
            continue
        _add_object(objects, domains, symbol, "event_studies", study_id, "derived_fact",
                    ("historical_events",), available_on,
                    [{"source_path": f"state/company_intel/event_studies.json#/studies/{study_id}"}],
                    None, [study["event_id"]] if study.get("event_id") else None)


def _finalize(domains: dict) -> None:
    for row in domains.values():
        row["object_refs"] = sorted(set(row["object_refs"]))
        if row["object_refs"]:
            row["status"] = "available"


def build(write: bool = True) -> dict:
    profiles = load_json(STATE / "company_profiles.json", {})
    briefs = load_json(STATE / "company_briefs.json", {})
    operating = load_json(STATE / "company_intel" / "operating_events.json", {})
    studies = load_json(STATE / "company_intel" / "event_studies.json", {})
    pilot = sorted((profiles.get("pilot") or {}).get("symbols") or [])
    companies = {}
    for symbol in pilot:
        domains = _domains()
        objects: list[dict] = []
        profile = (profiles.get("tickers") or {}).get(symbol) or {}
        identity = {"symbol": symbol, "label": symbol, "source_product": "company_profiles", "source_id": symbol}
        if profile.get("source_url"):
            identity["source_url"] = profile["source_url"]
        _brief_objects(symbol, briefs, domains, objects)
        _event_objects(symbol, operating, domains, objects)
        _study_objects(symbol, studies, domains, objects)
        objects.sort(key=lambda obj: (obj["available_on"], obj["id"]))
        _finalize(domains)
        timeline = [{"date": obj["available_on"], "object_ref": obj["id"], "type": obj["type"],
                     "source_product": obj["source_product"]} for obj in objects]
        companies[symbol] = {
            "identity": identity,
            "domains": domains,
            "intelligence_objects": objects,
            "timeline": timeline,
            "coverage": {
                "available_domains": sum(row["status"] == "available" for row in domains.values()),
                "partial_domains": sum(row["status"] == "partial" for row in domains.values()),
                "unknown_domains": sum(row["status"] == "unknown" for row in domains.values()),
                "blocked_domains": sum(row["status"] == "blocked" for row in domains.values()),
                "object_count": len(objects),
            },
        }
    result = {
        "schema_version": 1,
        "as_of": datetime.now(timezone.utc).date().isoformat(),
        "pilot_symbols": pilot,
        "intelligence_types": list(INTELLIGENCE_TYPES),
        "domains": list(BRAIN_DOMAINS),
        "source_products": list(SOURCE_PRODUCTS),
        "companies": companies,
    }
    if write:
        save_json(OUT, result)
        total = sum(company["coverage"]["object_count"] for company in companies.values())
        print(f"company_brains: wrote {len(companies)} companies, {total} reference objects")
    return result


if __name__ == "__main__":
    build()
