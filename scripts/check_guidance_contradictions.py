from __future__ import annotations

import copy
import json
import subprocess
import sys

from build_guidance_contradictions import OUT, build
from guidance_contradictions import FORBIDDEN_TEXT, build_guidance_state
from psx_data import ROOT, STATE, load_json


def _fail(message: str) -> None:
    raise AssertionError(message)


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _fixture_doc(text: str, doc_id: str = "psx:fixture:1", page: int = 1) -> dict:
    return {
        "documents": {
            doc_id: {
                "doc_id": doc_id,
                "tickers": ["TST"],
                "source": "PSX",
                "source_url": "https://dps.psx.com.pk/download/document.pdf",
                "retrieved_at": "2026-08-20T10:00:00+05:00",
                "content_sha256": "a" * 64,
                "evidence": [{
                    "document_id": doc_id,
                    "source_url": "https://dps.psx.com.pk/download/document.pdf",
                    "page": page,
                    "text": text,
                    "content_sha256": "a" * 64,
                    "evidence_sha256": doc_id.rjust(64, "b")[-64:],
                }],
            }
        }
    }


def _assert_safe(data: dict) -> None:
    for value in _walk_strings(data):
        lowered = value.lower()
        if lowered.startswith(("no_", "unknown", "state/", "same_company", "exact_", "guidance_", "retained_")):
            continue
        for term in FORBIDDEN_TEXT:
            if term in lowered:
                _fail(f"forbidden guidance term present: {term}")


def _assert_shape(data: dict, pilot: list[str]) -> int:
    if data.get("pilot_symbols") != sorted(pilot):
        _fail("pilot boundary mismatch")
    if set(data.get("companies") or {}) != set(pilot):
        _fail("company boundary mismatch")
    ids = set()
    total = 0
    for symbol, row in (data.get("companies") or {}).items():
        if row.get("symbol") != symbol:
            _fail(f"{symbol}: symbol mismatch")
        if row.get("status") not in {"available", "no_guidance_objects"}:
            _fail(f"{symbol}: invalid status")
        objects = row.get("objects")
        contradictions = row.get("contradictions")
        if not isinstance(objects, list) or not isinstance(contradictions, list):
            _fail(f"{symbol}: objects/contradictions must be arrays")
        if row.get("object_count") != len(objects):
            _fail(f"{symbol}: object count mismatch")
        if row.get("contradiction_count") != len(contradictions):
            _fail(f"{symbol}: contradiction count mismatch")
        if not objects and row.get("status") != "no_guidance_objects":
            _fail(f"{symbol}: empty row must be explicit no_guidance_objects")
        for obj in objects:
            total += 1
            if obj.get("guidance_id") in ids:
                _fail(f"{symbol}: duplicate guidance id")
            ids.add(obj.get("guidance_id"))
            if obj.get("symbol") != symbol or obj.get("domain") not in {"guidance", "risks"}:
                _fail(f"{symbol}: invalid guidance object symbol/domain")
            if obj.get("assertion_type") not in {"delivery_promise", "management_priority", "project_capacity_action", "stated_risk", "operating_constraint"}:
                _fail(f"{symbol}: invalid guidance assertion type")
            if not obj.get("assertion_key") or not obj.get("conflict_key") or not obj.get("modality"):
                _fail(f"{symbol}: missing normalized keys")
            evidence = obj.get("evidence") or {}
            if not evidence.get("source_url") or not evidence.get("document_id") or not evidence.get("available_on"):
                _fail(f"{symbol}: missing source URL/document/available-on provenance")
            if not isinstance(evidence.get("page"), int) or evidence["page"] <= 0:
                _fail(f"{symbol}: invalid page provenance")
            policy = obj.get("policy") or {}
            if policy.get("numeric_forecast") or policy.get("valuation") or policy.get("advice"):
                _fail(f"{symbol}: forbidden policy flag enabled")
        object_ids = {obj.get("guidance_id") for obj in objects}
        for contradiction in contradictions:
            if contradiction.get("status") != "exact_key_conflict":
                _fail(f"{symbol}: invalid contradiction status")
            if contradiction.get("match_rule") != "same_company_exact_normalized_conflict_key_incompatible_modalities":
                _fail(f"{symbol}: invalid contradiction match rule")
            if set(contradiction.get("object_ids") or []) - object_ids:
                _fail(f"{symbol}: contradiction references unknown object")
            if len(contradiction.get("evidence") or []) != 2:
                _fail(f"{symbol}: contradiction missing paired evidence")
    return total


def _adversarial() -> None:
    exact = {
        "documents": {
            "psx:fixture:1": _fixture_doc("The Company expects to expand operations in the north region during the coming year.")["documents"]["psx:fixture:1"],
            "psx:fixture:2": _fixture_doc("The Company expects to reduce operations in the north region during the coming year.", "psx:fixture:2", 2)["documents"]["psx:fixture:2"],
            "psx:fixture:3": _fixture_doc("The Company expects revenue to grow by 10 percent next year.", "psx:fixture:3", 3)["documents"]["psx:fixture:3"],
            "psx:fixture:4": _fixture_doc("Management discussed market conditions and operational matters.", "psx:fixture:4", 4)["documents"]["psx:fixture:4"],
        }
    }
    result = build_guidance_state(exact, ["TST"], as_of="2026-08-20T10:00:00+05:00")
    row = result["companies"]["TST"]
    if row["object_count"] != 2:
        _fail("strict fixture should emit only two non-numeric guidance objects")
    if row["contradiction_count"] != 1:
        _fail("exact normalized-key conflict was not detected")
    loose = copy.deepcopy(exact)
    loose["documents"]["psx:fixture:2"]["evidence"][0]["text"] = "The Company expects to reduce costs through discipline."
    loose_result = build_guidance_state(loose, ["TST"], as_of="2026-08-20T10:00:00+05:00")
    if loose_result["companies"]["TST"]["contradiction_count"] != 0:
        _fail("loose topic conflict produced a contradiction")
    empty = build_guidance_state({"documents": {}}, ["TST"], as_of="2026-08-20T10:00:00+05:00")
    if empty["companies"]["TST"]["status"] != "no_guidance_objects" or not empty["companies"]["TST"]["unknowns"]:
        _fail("empty state must be explicit no_guidance_objects")


def main() -> None:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = sorted((profiles.get("pilot") or {}).get("symbols") or [])
    documents = load_json(STATE / "company_documents.json", {"documents": {}})
    expected = build_guidance_state(documents, pilot)
    if _dump(expected) != _dump(build_guidance_state(documents, pilot, as_of=expected.get("as_of"))):
        _fail("pure builder is not deterministic when as_of is fixed")
    _assert_safe(expected)
    _adversarial()
    total = _assert_shape(expected, pilot)
    real = build()
    if _dump({**expected, "as_of": real.get("as_of")}) != _dump(real):
        _fail("writer output differs from pure builder")
    before = OUT.read_bytes()
    build()
    if before != OUT.read_bytes():
        _fail("builder output is not idempotent")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_ci_slice.py")], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        _fail(result.stdout + result.stderr)
    slice_data = load_json(ROOT / "ci-app" / "data" / "company_intelligence.json", {"tickers": []})
    by_symbol = {row.get("symbol"): row for row in slice_data.get("tickers") or []}
    for symbol, state_row in real.get("companies", {}).items():
        if (by_symbol.get(symbol) or {}).get("guidance_contradictions") != state_row:
            _fail(f"{symbol}: CI slice guidance_contradictions mismatch")
    print(f"guidance_contradictions: PASS ({len(pilot)} companies, {total} guidance/risk objects)")


if __name__ == "__main__":
    main()
