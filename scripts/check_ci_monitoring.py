from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from build_ci_monitoring import OUT, build
from ci_monitoring import ALERT_TYPES, FORBIDDEN_TEXT, STATUSES, build_ci_monitoring
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
    for value in _walk_strings(data):
        lowered = value.lower()
        if lowered.startswith("no_") or lowered.startswith("blocked_"):
            continue
        for term in FORBIDDEN_TEXT:
            if term in lowered:
                _fail(f"forbidden ci-monitoring term present: {term}")


def _source_url(value: object) -> bool:
    return str(value or "").startswith(("http://", "https://"))


def _load_sources() -> tuple[dict, dict, dict, dict, dict, dict, dict, list[str]]:
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    return (
        load_json(STATE / "company_intel" / "source_registry.json", {"tickers": {}}),
        load_json(STATE / "company_source_qa.json", {"tickers": {}}),
        load_json(STATE / "company_intel" / "change_intelligence.json", {"companies": {}}),
        load_json(STATE / "company_event_ledger.json", {"companies": {}}),
        load_json(STATE / "company_intel" / "operating_events.json", {"companies": {}}),
        load_json(STATE / "company_intel" / "evidence_watchlist.json", {"companies": {}}),
        load_json(STATE / "company_intel" / "guidance_contradictions.json", {"companies": {}}),
        pilot,
    )


def _assert_alert(symbol: str, alert: dict, source_registry: dict, change_state: dict, watch_state: dict, guidance_state: dict) -> None:
    alert_type = alert.get("type")
    if alert_type not in ALERT_TYPES:
        _fail(f"{symbol}: invalid alert type {alert_type}")
    if alert.get("symbol") != symbol:
        _fail(f"{symbol}: alert crosses company boundary")
    if not alert.get("alert_id"):
        _fail(f"{symbol}: alert missing id")
    if "score" in alert or "probability" in alert:
        _fail(f"{symbol}: alert leaked score/probability")
    source = alert.get("source") or {}
    if not _source_url(source.get("source_url")):
        _fail(f"{symbol}: alert missing source URL")
    if source.get("page") is not None and (not isinstance(source.get("page"), int) or source.get("page") < 1):
        _fail(f"{symbol}: alert source page invalid")
    identity = alert.get("evidence_identity") or {}
    if alert_type == "source_page_changed":
        pages = ((source_registry.get("tickers") or {}).get(symbol) or {}).get("monitored_pages") or []
        page = next((row for row in pages if row.get("url") == source.get("source_url")), None)
        if not page:
            _fail(f"{symbol}: source-page alert does not resolve")
        if not page.get("previous_sha256") or not page.get("last_changed_at"):
            _fail(f"{symbol}: source-page alert without previous hash/change date")
        if page.get("status") not in {"ok", "healthy", "not_modified"}:
            _fail(f"{symbol}: degraded page emitted as fresh source alert")
        if identity.get("previous_sha256") != page.get("previous_sha256"):
            _fail(f"{symbol}: page alert previous hash mismatch")
    elif alert_type == "source_registry_degraded":
        row = ((source_registry.get("tickers") or {}).get(symbol) or {})
        if row.get("status") in {"ok", "healthy"} and not identity.get("missing_required_source") and not identity.get("quality_flags"):
            _fail(f"{symbol}: false source degradation alert")
        if alert.get("date") is not None:
            _fail(f"{symbol}: source degradation alert must not invent a date")
    elif alert_type == "retained_change":
        change_id = identity.get("change_id")
        item = next((row for row in (((change_state.get("companies") or {}).get(symbol) or {}).get("items") or []) if row.get("id") == change_id), None)
        if not item:
            _fail(f"{symbol}: retained-change alert does not resolve")
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        expected_url = item.get("source_url") or evidence.get("source_url")
        if source.get("source_url") != expected_url:
            _fail(f"{symbol}: retained-change source URL mismatch")
        if item.get("kind") in {"event", "financial"} and evidence.get("page") is not None:
            if not isinstance(evidence.get("page"), int) or evidence.get("page") < 1:
                _fail(f"{symbol}: retained-change source page invalid upstream")
    elif alert_type == "active_evidence_watch":
        watch_id = identity.get("watch_id")
        item = next((row for row in (((watch_state.get("companies") or {}).get(symbol) or {}).get("items") or []) if row.get("watch_id") == watch_id), None)
        if not item:
            _fail(f"{symbol}: evidence-watch alert does not resolve")
        ids = item.get("ids") or {}
        if identity.get("thesis_id") != ids.get("thesis_id") or identity.get("source_cluster_id") != ids.get("source_cluster_id"):
            _fail(f"{symbol}: evidence-watch exact IDs mismatch")
    elif alert_type == "guidance_contradiction":
        contradiction_id = identity.get("contradiction_id")
        item = next((row for row in (((guidance_state.get("companies") or {}).get(symbol) or {}).get("contradictions") or []) if row.get("contradiction_id") == contradiction_id), None)
        if not item:
            _fail(f"{symbol}: guidance contradiction alert does not resolve")


def _assert_shape(
    data: dict,
    source_registry: dict,
    source_qa: dict,
    change_state: dict,
    event_ledger: dict,
    operating_events: dict,
    watch_state: dict,
    guidance_state: dict,
    pilot: list[str],
) -> int:
    if len(pilot) != 20 or len(set(pilot)) != 20:
        _fail("pilot boundary must be exactly 20")
    if data.get("pilot_symbols") != pilot or list((data.get("companies") or {}).keys()) != pilot:
        _fail("pilot order/boundary mismatch")
    if set(data.get("status_vocabulary") or []) != STATUSES:
        _fail("status vocabulary mismatch")
    if set(data.get("alert_type_vocabulary") or []) != ALERT_TYPES:
        _fail("alert type vocabulary mismatch")
    policy = data.get("policy") or {}
    for key in ("research_only", "retained_state_only", "categorical_status_only", "source_provenance_required", "previous_hash_required_for_page_change", "no_browser_inference", "no_lookahead", "no_scores", "no_forecasts", "no_valuation", "no_advice"):
        if policy.get(key) is not True:
            _fail(f"policy flag missing: {key}")
    for source_name, expected in (
        ("source_registry", "state/company_intel/source_registry.json"),
        ("source_qa", "state/company_source_qa.json"),
        ("change_intelligence", "state/company_intel/change_intelligence.json"),
        ("event_ledger", "state/company_event_ledger.json"),
        ("operating_events", "state/company_intel/operating_events.json"),
        ("evidence_watchlist", "state/company_intel/evidence_watchlist.json"),
        ("guidance_contradictions", "state/company_intel/guidance_contradictions.json"),
    ):
        if (data.get("source") or {}).get(source_name) != expected:
            _fail(f"canonical source missing: {source_name}")
    total = 0
    status_counts = {status: 0 for status in STATUSES}
    seen_alerts = set()
    for symbol in pilot:
        row = (data.get("companies") or {}).get(symbol) or {}
        if row.get("symbol") != symbol or row.get("status") not in STATUSES:
            _fail(f"{symbol}: invalid monitoring row")
        status_counts[row.get("status")] += 1
        if "score" in row or "aggregate_score" in row:
            _fail(f"{symbol}: monitoring row leaked a score")
        if row.get("status") == "degraded":
            if not any(alert.get("type") == "source_registry_degraded" for alert in row.get("alerts") or []):
                _fail(f"{symbol}: degraded row without source degradation alert")
        if row.get("status") == "healthy":
            if any(alert.get("type") == "source_registry_degraded" for alert in row.get("alerts") or []):
                _fail(f"{symbol}: healthy row has source degradation alert")
        for alert in row.get("alerts") or []:
            total += 1
            aid = alert.get("alert_id")
            if aid in seen_alerts:
                _fail(f"{symbol}: duplicate alert id")
            seen_alerts.add(aid)
            _assert_alert(symbol, alert, source_registry, change_state, watch_state, guidance_state)
    if (data.get("summary") or {}).get("alert_count") != total:
        _fail("summary alert count mismatch")
    if (data.get("summary") or {}).get("status_counts") != {status: status_counts.get(status, 0) for status in sorted(STATUSES)}:
        _fail("summary status counts mismatch")
    return total


def _fixture_page(symbol: str, *, previous: bool = True, degraded: bool = False) -> dict:
    return {
        "url": f"https://example.com/{symbol.lower()}",
        "kind": "issuer_home",
        "label": "Issuer website",
        "status": "degraded" if degraded else "ok",
        "content_sha256": "c" * 64,
        "previous_sha256": "p" * 64 if previous else None,
        "first_seen_at": "2026-08-01T09:00:00+05:00",
        "last_changed_at": "2026-08-20T09:00:00+05:00",
    }


def _adversarial() -> None:
    pilot = ["TST"]
    source_qa = {"_meta": {"updated": "2026-08-25 00:00"}, "tickers": {"TST": {"ticker": "TST", "issuer_url": "https://example.com/tst", "registry_status": "ok", "source_ids": ["src_tst"], "monitored_page_count": 1, "document_link_count": 0, "quality_flags": [], "missing_required_source": False}}}
    change_state = {"_meta": {"updated": "2026-08-25 00:00"}, "companies": {"TST": {"ticker": "TST", "status": "quiet", "items": []}}}
    empty = {"companies": {"TST": {}}}
    guidance = {"as_of": "2026-08-25T00:00:00+05:00", "companies": {"TST": {"symbol": "TST", "contradictions": []}}}
    registry = {"updated": "2026-08-25T00:00:00+05:00", "tickers": {"TST": {"symbol": "TST", "status": "ok", "issuer_url": "https://example.com/tst", "monitored_pages": [_fixture_page("TST", previous=True)], "document_links": []}}}
    result = build_ci_monitoring(registry, source_qa, change_state, empty, empty, empty, guidance, pilot_symbols=pilot)
    if result["companies"]["TST"]["status"] != "healthy":
        _fail("valid changed source page should keep row healthy")
    if not any(alert.get("type") == "source_page_changed" for alert in result["companies"]["TST"]["alerts"]):
        _fail("valid prior-hash source page change did not alert")

    no_previous = copy.deepcopy(registry)
    no_previous["tickers"]["TST"]["monitored_pages"] = [_fixture_page("TST", previous=False)]
    no_previous_result = build_ci_monitoring(no_previous, source_qa, change_state, empty, empty, empty, guidance, pilot_symbols=pilot)
    if any(alert.get("type") == "source_page_changed" for alert in no_previous_result["companies"]["TST"]["alerts"]):
        _fail("source page first-seen row emitted change alert")

    degraded_page = copy.deepcopy(registry)
    degraded_page["tickers"]["TST"]["monitored_pages"] = [_fixture_page("TST", previous=True, degraded=True)]
    degraded_page_result = build_ci_monitoring(degraded_page, source_qa, change_state, empty, empty, empty, guidance, pilot_symbols=pilot)
    if any(alert.get("type") == "source_page_changed" for alert in degraded_page_result["companies"]["TST"]["alerts"]):
        _fail("degraded page emitted fresh change alert")

    degraded_registry = copy.deepcopy(registry)
    degraded_registry["tickers"]["TST"]["status"] = "degraded"
    degraded_registry_result = build_ci_monitoring(degraded_registry, source_qa, change_state, empty, empty, empty, guidance, pilot_symbols=pilot)
    if degraded_registry_result["companies"]["TST"]["status"] != "degraded":
        _fail("degraded registry did not degrade row")

    stale_registry = {"updated": "2026-08-25T00:00:00+05:00", "tickers": {"TST": {"symbol": "TST", "status": "ok", "issuer_url": "https://example.com/tst", "monitored_pages": [], "document_links": [{"url": "https://example.com/report.pdf", "first_seen_at": "2026-01-01T00:00:00+05:00"}]}}}
    stale_result = build_ci_monitoring(stale_registry, source_qa, change_state, empty, empty, empty, guidance, pilot_symbols=pilot)
    if stale_result["companies"]["TST"]["status"] != "stale":
        _fail("old retained source/change timestamps did not mark stale")


def main() -> None:
    source_registry, source_qa, change_state, event_ledger, operating_events, watch_state, guidance_state, pilot = _load_sources()
    expected = build_ci_monitoring(
        source_registry,
        source_qa,
        change_state,
        event_ledger,
        operating_events,
        watch_state,
        guidance_state,
        pilot_symbols=pilot,
    )
    expected_again = build_ci_monitoring(
        source_registry,
        source_qa,
        change_state,
        event_ledger,
        operating_events,
        watch_state,
        guidance_state,
        pilot_symbols=pilot,
    )
    if _dump(expected) != _dump(expected_again):
        _fail("pure builder is not deterministic")
    _assert_safe_language(expected)
    _adversarial()
    total = _assert_shape(expected, source_registry, source_qa, change_state, event_ledger, operating_events, watch_state, guidance_state, pilot)
    real = build()
    if _dump(real) != _dump(expected):
        _fail("writer output differs from pure builder")
    before = OUT.read_bytes()
    build()
    if before != OUT.read_bytes():
        _fail("builder output is not idempotent")
    with tempfile.TemporaryDirectory() as tmpdir:
        first = Path(tmpdir) / "first.json"
        second = Path(tmpdir) / "second.json"
        for path in (first, second):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_ci_monitoring.py"), "--out", str(path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                _fail((result.stdout or "") + (result.stderr or ""))
        if first.read_bytes() != second.read_bytes():
            _fail("builder output is not byte-idempotent")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_ci_slice.py")], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        _fail(result.stdout + result.stderr)
    slice_data = load_json(ROOT / "ci-app" / "data" / "company_intelligence.json", {"tickers": []})
    by_symbol = {row.get("symbol"): row for row in slice_data.get("tickers") or []}
    if set(by_symbol) != set(pilot):
        _fail("CI slice pilot boundary mismatch")
    real = load_json(OUT, {})
    for symbol, state_row in real.get("companies", {}).items():
        if (by_symbol.get(symbol) or {}).get("monitoring") != state_row:
            _fail(f"{symbol}: CI slice monitoring mismatch")
    print(f"ci_monitoring: PASS ({len(pilot)} companies, {total} alerts)")


if __name__ == "__main__":
    main()
