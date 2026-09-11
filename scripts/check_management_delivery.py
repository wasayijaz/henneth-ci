from __future__ import annotations

import copy
import json
import subprocess
import sys

from build_management_delivery import OUT, build
from management_delivery import FORBIDDEN_TEXT, STATUSES, build_management_delivery
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


def _assert_safe_language(data: dict) -> None:
    allowed = {"no_advice", "no_odds_claims", "no_forward_estimates", "no_price_claims", "no_valuation", "no_valuation_claims"}
    for value in _walk_strings(data):
        lowered = value.lower()
        if lowered in allowed or lowered.startswith("blocked_"):
            continue
        for term in FORBIDDEN_TEXT:
            if term in lowered:
                _fail(f"forbidden management-delivery term present: {term}")


def _assert_match(record: dict, symbol: str) -> None:
    match = record.get("matched_event")
    if record.get("status") in {"confirmed", "contradicted"}:
        if not match or not match.get("event_id") or not match.get("evidence"):
            _fail(f"{symbol}: closed match missing event/evidence")
    if record.get("status") == "not_observed" and match:
        _fail(f"{symbol}: not_observed record has matched event")


def _assert_shape(data: dict, thesis_state: dict, signal_state: dict, confidence_state: dict, guidance_state: dict) -> int:
    symbols = list(thesis_state.get("pilot_symbols") or [])
    if len(symbols) != 20 or len(set(symbols)) != 20:
        _fail("pilot boundary must be exactly 20")
    if data.get("pilot_symbols") != symbols:
        _fail("pilot symbol order mismatch")
    if set(data.get("status_vocabulary") or []) != STATUSES:
        _fail("status vocabulary mismatch")
    companies = data.get("companies") or {}
    if set(companies) != set(symbols):
        _fail("company boundary mismatch")
    if (data.get("source") or {}).get("guidance_contradictions") != "state/company_intel/guidance_contradictions.json":
        _fail("canonical guidance source is not declared")
    total = 0
    seen_ids = set()
    for symbol in symbols:
        row = companies.get(symbol) or {}
        thesis_row = (thesis_state.get("companies") or {}).get(symbol) or {}
        signal_row = (signal_state.get("companies") or {}).get(symbol) or {}
        confidence_row = (confidence_state.get("companies") or {}).get(symbol) or {}
        guidance_row = (guidance_state.get("companies") or {}).get(symbol) or {}
        theses = thesis_row.get("theses") or []
        records = row.get("records") or []
        guidance_records = row.get("guidance_records") or []
        if row.get("active_thesis_count") != len(theses):
            _fail(f"{symbol}: active thesis count mismatch")
        if row.get("delivery_record_count") != len(records) or len(records) != len(theses):
            _fail(f"{symbol}: delivery record count mismatch")
        if row.get("guidance_object_count") != len(guidance_row.get("objects") or []):
            _fail(f"{symbol}: guidance object count mismatch")
        if row.get("guidance_record_count") != len(guidance_records):
            _fail(f"{symbol}: guidance record count mismatch")
        thesis_ids = {thesis.get("thesis_id") for thesis in theses}
        cluster_ids = {cluster.get("cluster_id") for cluster in signal_row.get("clusters") or []}
        confidence_ids = {assessment.get("confidence_id") for assessment in confidence_row.get("assessments") or []}
        guidance_ids = {obj.get("guidance_id") for obj in guidance_row.get("objects") or []}
        for record in records:
            total += 1
            rid = record.get("delivery_id")
            if not rid or rid in seen_ids:
                _fail(f"{symbol}: duplicate/missing delivery id")
            seen_ids.add(rid)
            if record.get("symbol") != symbol:
                _fail(f"{symbol}: record symbol mismatch")
            if record.get("thesis_id") not in thesis_ids:
                _fail(f"{symbol}: record references unknown thesis")
            if record.get("source_cluster_id") not in cluster_ids:
                _fail(f"{symbol}: record references unknown source cluster")
            if record.get("status") not in STATUSES:
                _fail(f"{symbol}: invalid status")
            if record.get("scorecard_type") != "categorical_status_only" or "score" in record:
                _fail(f"{symbol}: invalid categorical scorecard shape")
            source = record.get("source_assertion") or {}
            if not source.get("available_at") or not source.get("linked_event_ids") or not source.get("evidence"):
                _fail(f"{symbol}: incomplete source assertion linkage")
            link = record.get("confidence_link")
            if link and link.get("confidence_id") not in confidence_ids:
                _fail(f"{symbol}: unresolved confidence link")
            _assert_match(record, symbol)
        for record in guidance_records:
            rid = record.get("guidance_record_id")
            if not rid or rid in seen_ids:
                _fail(f"{symbol}: duplicate/missing guidance record id")
            seen_ids.add(rid)
            if record.get("guidance_id") not in guidance_ids:
                _fail(f"{symbol}: guidance record references unknown guidance object")
            if record.get("status") not in {"confirmed", "contradicted", "not_observed"}:
                _fail(f"{symbol}: invalid guidance record status")
            if record.get("scorecard_type") != "categorical_status_only" or "score" in record:
                _fail(f"{symbol}: invalid guidance categorical shape")
            source = record.get("source_guidance") or {}
            if not source.get("available_at") or not source.get("evidence"):
                _fail(f"{symbol}: guidance record source provenance missing")
            if not isinstance(record.get("guidance_review"), dict):
                _fail(f"{symbol}: guidance review metadata missing")
            if record.get("status") in {"confirmed", "contradicted"} and not record.get("matched_guidance"):
                _fail(f"{symbol}: closed guidance record missing match")
    if (data.get("summary") or {}).get("active_thesis_count") != total:
        _fail("summary active thesis count mismatch")
    return total


def _guidance_obj(symbol: str, gid: str, assertion: str, conflict: str, modality: str, available: str, evidence_sha: str, page: int = 1) -> dict:
    return {
        "guidance_id": gid,
        "symbol": symbol,
        "domain": "guidance",
        "status": "eligible",
        "statement": "management expects to continue operating discipline",
        "modality": modality,
        "topic_key": "operating_discipline",
        "assertion_key": assertion,
        "conflict_key": conflict,
        "evidence": {
            "document_id": f"psx:{gid}",
            "source_url": f"https://dps.psx.com.pk/download/document/{gid}.pdf",
            "source": "PSX DPS",
            "page": page,
            "available_on": available,
            "content_sha256": evidence_sha,
            "evidence_sha256": evidence_sha,
        },
        "policy": {
            "same_company_official_evidence": True,
            "numeric_forecast": False,
            "valuation": False,
            "advice": False,
        },
    }


def _minimal_fixture():
    symbols = ["TST"]
    thesis = {
        "pilot_symbols": symbols,
        "as_of": "2026-08-25T00:00:00+05:00",
        "companies": {
            "TST": {"theses": [{
                "thesis_id": "thesis_1",
                "symbol": "TST",
                "source_cluster_id": "cluster_1",
                "assertion_key": "guidance:operating_discipline:continue",
                "conflict_key": "guidance:operating_discipline",
                "linked_event_ids": ["event_1"],
                "evidence": [{
                    "document_id": "psx:source",
                    "content_sha256": "s" * 64,
                    "evidence_sha256": "e" * 64,
                    "source_url": "https://dps.psx.com.pk/download/document/source.pdf",
                    "page": 1,
                }],
                "monitored_assertion": "source guidance fixture",
            }]},
        },
    }
    signal = {
        "pilot_symbols": symbols,
        "as_of": "2026-08-25T00:00:00+05:00",
        "companies": {
            "TST": {"clusters": [{
                "cluster_id": "cluster_1",
                "proposition": {"modality": "continue"},
                "observations": [{
                    "event_id": "event_1",
                    "available_at": "2026-08-20T10:00:00+05:00",
                    "evidence": {
                        "document_id": "psx:source",
                        "content_sha256": "s" * 64,
                        "evidence_sha256": "e" * 64,
                        "source_url": "https://dps.psx.com.pk/download/document/source.pdf",
                        "page": 1,
                    },
                }],
            }]},
        },
    }
    confidence = {"companies": {"TST": {"assessments": [{"confidence_id": "confidence_1", "source_cluster_id": "cluster_1", "band": "medium"}]}}}
    guidance = {
        "as_of": "2026-08-26T00:00:00+05:00",
        "guidance_version": "guidance_contradictions_v1",
        "companies": {
            "TST": {
                "symbol": "TST",
                "status": "available",
                "objects": [
                    _guidance_obj("TST", "g1", "guidance:operating_discipline:continue", "guidance:operating_discipline", "continue", "2026-08-21T10:00:00+05:00", "a" * 64),
                ],
            },
        },
    }
    return thesis, signal, confidence, guidance


def _adversarial(thesis_state: dict, signal_state: dict, operating_events: dict, confidence_state: dict, guidance_state: dict) -> None:
    base = build_management_delivery(thesis_state, signal_state, operating_events, confidence_state, guidance_state)
    loose = copy.deepcopy(operating_events)
    eng = ((loose.get("companies") or {}).get("ENGROH") or {}).get("events") or []
    if eng:
        event = copy.deepcopy(eng[0])
        event["event_id"] = "evt_loose_same_symbol"
        event["detected_at"] = "2026-08-22T16:09:00+05:00"
        event["effective_date"] = "2026-08-22"
        event["description"] = "Generic management update with no exact proposition."
        ((loose.get("companies") or {}).get("ENGROH") or {}).setdefault("events", []).append(event)
    loose_result = build_management_delivery(thesis_state, signal_state, loose, confidence_state, guidance_state)
    if _dump(base.get("companies", {}).get("ENGROH", {}).get("records")) != _dump(loose_result.get("companies", {}).get("ENGROH", {}).get("records")):
        _fail("loose same-symbol event changed thesis management delivery")

    early = copy.deepcopy(operating_events)
    ubl_events = ((early.get("companies") or {}).get("UBL") or {}).get("events") or []
    if ubl_events:
        event = copy.deepcopy(ubl_events[0])
        event["event_id"] = "evt_early_exact"
        event["detected_at"] = "2026-01-01T00:00:00+05:00"
        ((early.get("companies") or {}).get("UBL") or {}).setdefault("events", []).append(event)
    early_result = build_management_delivery(thesis_state, signal_state, early, confidence_state, guidance_state)
    if _dump(base.get("companies", {}).get("UBL", {}).get("records")) != _dump(early_result.get("companies", {}).get("UBL", {}).get("records")):
        _fail("non-later exact event changed thesis management delivery")

    linked = copy.deepcopy(operating_events)
    linked_event = copy.deepcopy((((linked.get("companies") or {}).get("ENGROH") or {}).get("events") or [])[0])
    linked_event["event_id"] = "evt_linked_source_observation"
    linked_event["detected_at"] = "2026-08-22T16:09:00+05:00"
    ((linked.get("companies") or {}).get("ENGROH") or {}).setdefault("events", []).append(linked_event)
    linked_theses = copy.deepcopy(thesis_state)
    linked_theses["companies"]["ENGROH"]["theses"][0]["linked_event_ids"].append("evt_linked_source_observation")
    linked_result = build_management_delivery(linked_theses, signal_state, linked, confidence_state, guidance_state)
    if linked_result["companies"]["ENGROH"]["records"][0]["status"] != "not_observed":
        _fail("linked source event self-confirmed thesis delivery")

    cutoff_events = copy.deepcopy(operating_events)
    cutoff_event = copy.deepcopy((((cutoff_events.get("companies") or {}).get("ENGROH") or {}).get("events") or [])[0])
    cutoff_event["event_id"] = "evt_between_source_observations"
    cutoff_event["detected_at"] = "2026-08-20T00:00:00+05:00"
    ((cutoff_events.get("companies") or {}).get("ENGROH") or {}).setdefault("events", []).append(cutoff_event)
    cutoff_signals = copy.deepcopy(signal_state)
    cutoff_cluster = cutoff_signals["companies"]["ENGROH"]["clusters"][0]
    later_source_obs = copy.deepcopy(cutoff_cluster["observations"][0])
    later_source_obs["observation_id"] = "obs_later_source_cutoff"
    later_source_obs["event_id"] = "evt_later_source_cutoff"
    later_source_obs["available_at"] = "2026-08-25T00:00:00+05:00"
    cutoff_cluster["observations"].append(later_source_obs)
    cutoff_result = build_management_delivery(thesis_state, cutoff_signals, cutoff_events, confidence_state, guidance_state)
    if cutoff_result["companies"]["ENGROH"]["records"][0]["status"] != "not_observed":
        _fail("candidate before latest source-cluster availability self-confirmed thesis delivery")

    thesis, signal, confidence, guidance = _minimal_fixture()
    fixture = build_management_delivery(thesis, signal, {"companies": {"TST": {"events": []}}}, confidence, guidance)
    if fixture.get("as_of") != guidance["as_of"]:
        _fail("newer guidance cutoff was not promoted to the management-delivery cutoff")
    if fixture["companies"]["TST"]["guidance_records"][0]["status"] != "not_observed":
        _fail("single guidance object should not confirm itself")
    contradicted_guidance = copy.deepcopy(guidance)
    contradicted_guidance["companies"]["TST"]["objects"].append(
        _guidance_obj("TST", "g2", "guidance:operating_discipline:stop", "guidance:operating_discipline", "stop", "2026-08-22T10:00:00+05:00", "d" * 64, 2)
    )
    contradicted = build_management_delivery(thesis, signal, {"companies": {"TST": {"events": []}}}, confidence, contradicted_guidance)
    if contradicted["companies"]["TST"]["guidance_records"][0]["status"] != "contradicted":
        _fail("later exact conflict key with incompatible modality did not contradict guidance record")
    confirmed_guidance = copy.deepcopy(guidance)
    confirmed_guidance["companies"]["TST"]["objects"].append(
        _guidance_obj("TST", "g2", "guidance:operating_discipline:continue", "guidance:operating_discipline", "continue", "2026-08-22T10:00:00+05:00", "d" * 64, 2)
    )
    confirmed = build_management_delivery(thesis, signal, {"companies": {"TST": {"events": []}}}, confidence, confirmed_guidance)
    if confirmed["companies"]["TST"]["guidance_records"][0]["status"] != "confirmed":
        _fail("later exact assertion key did not confirm guidance record")
    cloned_guidance = copy.deepcopy(guidance)
    clone = _guidance_obj("TST", "g2", "guidance:operating_discipline:continue", "guidance:operating_discipline", "continue", "2026-08-22T10:00:00+05:00", "a" * 64)
    clone["evidence"]["document_id"] = "psx:g1"
    cloned_guidance["companies"]["TST"]["objects"].append(clone)
    cloned = build_management_delivery(thesis, signal, {"companies": {"TST": {"events": []}}}, confidence, cloned_guidance)
    if cloned["companies"]["TST"]["guidance_records"][0]["status"] != "not_observed":
        _fail("same-evidence cloned guidance object self-confirmed")


def main() -> None:
    thesis_state = load_json(STATE / "company_intel" / "thesis_monitoring.json", {"companies": {}})
    signal_state = load_json(STATE / "company_intel" / "signal_clusters.json", {"companies": {}})
    operating_events = load_json(STATE / "company_intel" / "operating_events.json", {"companies": {}})
    confidence_state = load_json(STATE / "company_intel" / "intelligence_confidence.json", {"companies": {}})
    guidance_state = load_json(STATE / "company_intel" / "guidance_contradictions.json", {"companies": {}})
    expected = build_management_delivery(thesis_state, signal_state, operating_events, confidence_state, guidance_state)
    expected_again = build_management_delivery(thesis_state, signal_state, operating_events, confidence_state, guidance_state)
    if _dump(expected) != _dump(expected_again):
        _fail("pure builder is not deterministic")
    _assert_safe_language(expected)
    _adversarial(thesis_state, signal_state, operating_events, confidence_state, guidance_state)
    total = _assert_shape(expected, thesis_state, signal_state, confidence_state, guidance_state)
    real = build()
    if _dump(expected) != _dump(real):
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
    pilot = list(thesis_state.get("pilot_symbols") or [])
    if set(by_symbol) != set(pilot):
        _fail("CI slice does not contain exact pilot")
    for symbol, state_row in real.get("companies", {}).items():
        if (by_symbol.get(symbol) or {}).get("management_delivery") != state_row:
            _fail(f"{symbol}: CI slice management_delivery mismatch")
    print(f"management_delivery: PASS ({len(pilot)} companies, {total} thesis records)")


if __name__ == "__main__":
    main()
