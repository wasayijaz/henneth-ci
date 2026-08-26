"""Build first-class Guidance & Contradictions state for Company Intelligence."""
from __future__ import annotations

from guidance_contradictions import build_guidance_state
from psx_data import STATE, load_json, save_json


OUT = STATE / "company_intel" / "guidance_contradictions.json"


def build() -> dict:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = (profiles.get("pilot") or {}).get("symbols") or []
    documents = load_json(STATE / "company_documents.json", {"documents": {}})
    result = build_guidance_state(documents, pilot)
    save_json(OUT, result)
    total = sum((row.get("object_count") or 0) for row in result.get("companies", {}).values())
    conflicts = sum((row.get("contradiction_count") or 0) for row in result.get("companies", {}).values())
    print(f"guidance_contradictions: {len(result.get('companies', {}))} companies, {total} objects, {conflicts} contradictions")
    return result


if __name__ == "__main__":
    build()
