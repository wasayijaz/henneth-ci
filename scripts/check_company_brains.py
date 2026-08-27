"""Validate the compact Company Brain contract and source resolution."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_company_brains import OUT, build
from intelligence_types import BRAIN_DOMAINS, DOMAIN_STATUSES, INTELLIGENCE_TYPES, SOURCE_PRODUCTS
from psx_data import STATE, load_json
from ci_checker_helpers import without_root_meta

def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _sources() -> dict:
    return {
        "company_briefs": load_json(STATE / "company_briefs.json", {}),
        "operating_events": load_json(STATE / "company_intel" / "operating_events.json", {}),
        "event_studies": load_json(STATE / "company_intel" / "event_studies.json", {}),
    }


def _resolves(sources: dict, symbol: str, product: str, source_id: str) -> bool:
    if product == "company_briefs":
        history = (((sources[product].get("companies") or {}).get(symbol) or {}).get("history") or [])
        return any(brief.get("status") == "owner_approved" and brief.get("brief_id")
                   and source_id.startswith(f"{brief['brief_id']}:") for brief in history)
    if product == "operating_events":
        events = (((sources[product].get("companies") or {}).get(symbol) or {}).get("events") or [])
        return any(event.get("event_id") == source_id for event in events)
    if product == "event_studies":
        study = (sources[product].get("studies") or {}).get(source_id)
        return bool(study and study.get("symbol") == symbol and study.get("study_id"))
    return False


def _check_company(symbol: str, company: dict, sources: dict, seen_ids: set[str]) -> None:
    identity = company.get("identity") or {}
    if identity.get("symbol") != symbol or identity.get("source_product") != "company_profiles":
        raise AssertionError(f"{symbol}: invalid profile identity")
    domains = company.get("domains") or {}
    if tuple(domains) != BRAIN_DOMAINS or len(domains) != 21:
        raise AssertionError(f"{symbol}: exact 21-domain contract mismatch")

    objects = company.get("intelligence_objects") or []
    by_id = {}
    for obj in objects:
        oid = obj.get("id")
        if not oid or oid in seen_ids:
            raise AssertionError(f"{symbol}: duplicate object id {oid}")
        seen_ids.add(oid)
        by_id[oid] = obj
        if obj.get("type") not in INTELLIGENCE_TYPES or obj.get("type") in {"forecast", "scenario"}:
            raise AssertionError(f"{symbol}: forbidden or unknown object type")
        if obj.get("source_product") not in SOURCE_PRODUCTS:
            raise AssertionError(f"{symbol}: unsupported source product")
        if not isinstance(obj.get("source_id"), str) or not _resolves(
            sources, symbol, obj["source_product"], obj["source_id"]
        ):
            raise AssertionError(f"{symbol}: unresolved source {obj.get('source_product')}:{obj.get('source_id')}")
        available_on = obj.get("available_on")
        if not isinstance(available_on, str) or len(available_on) != 10:
            raise AssertionError(f"{symbol}: missing available_on")
        if "available_date" in obj:
            raise AssertionError(f"{symbol}: obsolete available_date field")
        if not obj.get("evidence_refs"):
            raise AssertionError(f"{symbol}: missing evidence")
        if len(_dump(obj)) > 1800:
            raise AssertionError(f"{symbol}: object is not compact")

    for name, row in domains.items():
        if row.get("status") not in DOMAIN_STATUSES:
            raise AssertionError(f"{symbol}: invalid {name} status")
        refs = row.get("object_refs")
        if not isinstance(refs, list) or refs != sorted(set(refs)):
            raise AssertionError(f"{symbol}: unstable refs in {name}")
        if any(ref not in by_id for ref in refs):
            raise AssertionError(f"{symbol}: unresolved domain ref in {name}")
        if refs and row.get("status") not in {"available", "partial"}:
            raise AssertionError(f"{symbol}: populated {name} not available")
        if name in {"forecasts", "valuation"} and (row.get("status") != "blocked" or refs):
            raise AssertionError(f"{symbol}: {name} must remain blocked and empty")

    timeline = company.get("timeline") or []
    expected = [{"date": obj["available_on"], "object_ref": obj["id"], "type": obj["type"],
                 "source_product": obj["source_product"]} for obj in objects]
    if timeline != expected or [(row["date"], row["object_ref"]) for row in timeline] != sorted(
        (row["date"], row["object_ref"]) for row in timeline
    ):
        raise AssertionError(f"{symbol}: timeline mismatch")
    coverage = company.get("coverage") or {}
    if coverage.get("object_count") != len(objects):
        raise AssertionError(f"{symbol}: coverage mismatch")


def main() -> None:
    if not OUT.exists():
        raise AssertionError("company_brains.json is missing")
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot_order = list((profiles.get("pilot") or {}).get("symbols") or [])
    pilot = set(pilot_order)
    if len(pilot_order) != 20 or len(pilot) != 20:
        raise AssertionError("pilot boundary must be exactly 20")
    brain = load_json(OUT, {})
    if set(brain.get("pilot_symbols") or []) != pilot or set(brain.get("companies") or {}) != pilot:
        raise AssertionError("exact 20-company pilot mismatch")
    if brain.get("intelligence_types") != list(INTELLIGENCE_TYPES):
        raise AssertionError("intelligence type registry mismatch")
    if brain.get("domains") != list(BRAIN_DOMAINS) or brain.get("source_products") != list(SOURCE_PRODUCTS):
        raise AssertionError("brain registry mismatch")
    sources = _sources()
    seen_ids: set[str] = set()
    for symbol in sorted(pilot):
        _check_company(symbol, brain["companies"][symbol], sources, seen_ids)
    if _dump(without_root_meta(brain)) != _dump(without_root_meta(build(write=False))):
        raise AssertionError("company_brains rebuild is not deterministic")
    total = sum(company["coverage"]["object_count"] for company in brain["companies"].values())
    print(f"company_brains: PASS ({len(pilot)} companies, {total} reference objects)")


if __name__ == "__main__":
    main()
