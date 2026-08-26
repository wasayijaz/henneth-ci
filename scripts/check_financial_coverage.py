from __future__ import annotations

import json
import subprocess
import sys

from build_financial_coverage import OUT, REQUIRED_ANNUAL_SLOT_COUNT, REQUIRED_METRICS, _period_from_doc, build
from psx_data import ROOT, STATE, load_json


FORBIDDEN_KEYS = {"normalized_value", "raw_value", "value", "amount", "eps", "revenue", "pat"}
ALLOWED_KEY_PATHS = {
    "missing_revenue_pat_eps_by_annual_period",
    "missing_metrics",
    "required_metrics",
    "present_model_ready_metrics",
}
INVENTED_FALLBACK_PERIODS = {"2026-06-30", "2025-06-30", "2024-06-30"}


def _fail(message: str) -> None:
    raise AssertionError(message)


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _walk(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield path + (str(key),), item
            yield from _walk(item, path + (str(key),))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _walk(item, path + (str(idx),))


def _assert_no_values(data: dict) -> None:
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key in FORBIDDEN_KEYS and not any(part in ALLOWED_KEY_PATHS for part in path):
            _fail(f"forbidden value-like key present at {'.'.join(path)}")
        if key in {"forecast", "valuation"} and value != "blocked_not_implemented":
            _fail(f"{'.'.join(path)} is not explicitly blocked")


def _assert_shape(data: dict, pilot: set[str]) -> None:
    symbols = data.get("pilot_symbols") or []
    if set(symbols) != pilot or len(symbols) != 20:
        _fail("expected exact 20-company pilot")
    companies = data.get("companies") or {}
    if set(companies) != set(symbols):
        _fail("company boundary mismatch")
    if not (data.get("policy") or {}).get("metadata_only"):
        _fail("metadata-only policy missing")
    for symbol in symbols:
        row = companies.get(symbol) or {}
        if row.get("symbol") != symbol:
            _fail(f"{symbol}: symbol mismatch")
        if row.get("status") not in {"queued_for_qualification", "blocked_no_candidate_documents", "complete"}:
            _fail(f"{symbol}: invalid status")
        docs = row.get("indexed_official_financial_docs")
        if not isinstance(docs, list):
            _fail(f"{symbol}: financial docs missing")
        for doc in docs:
            doc_id = doc.get("document_id")
            if not str(doc_id or "").startswith("psx:"):
                _fail(f"{symbol}: non-PSX document included")
            if doc.get("classification") not in {"financial_results", "financial_statement", "financial_results_notice"}:
                _fail(f"{symbol}: invalid financial classification")
            period = doc.get("safe_period")
            if period is not None:
                if period.get("period_type") not in {"annual", "interim", "unknown"}:
                    _fail(f"{symbol}: unsafe period source")
                if period.get("period_end") and not period.get("matched_text"):
                    _fail(f"{symbol}: non-null document period lacks source evidence")
        periods = row.get("required_annual_periods") or []
        if len(periods) != REQUIRED_ANNUAL_SLOT_COUNT:
            _fail(f"{symbol}: expected three annual slots")
        period_ends = []
        for idx, period in enumerate(periods, start=1):
            if not isinstance(period, dict):
                _fail(f"{symbol}: annual slot is not an object")
            if period.get("slot") != f"annual_period_{idx}":
                _fail(f"{symbol}: annual slot order/name mismatch")
            if period.get("period_type") != "annual":
                _fail(f"{symbol}: annual slot period_type mismatch")
            if period.get("period_end"):
                if period.get("period_end") in INVENTED_FALLBACK_PERIODS and not period.get("document_id"):
                    _fail(f"{symbol}: invented fallback annual period present")
                if period.get("source") != "title" or not period.get("matched_text") or not period.get("document_id"):
                    _fail(f"{symbol}: non-null annual period lacks title/document evidence")
                period_ends.append(period.get("period_end"))
            elif period.get("evidence_status") != "missing_explicit_annual_period_evidence":
                _fail(f"{symbol}: null annual slot lacks missing-evidence status")
        missing_rows = row.get("missing_revenue_pat_eps_by_annual_period") or []
        if len(missing_rows) != REQUIRED_ANNUAL_SLOT_COUNT:
            _fail(f"{symbol}: expected three missing-metric rows")
        for idx, item in enumerate(missing_rows, start=1):
            if item.get("slot") != f"annual_period_{idx}":
                _fail(f"{symbol}: missing row slot mismatch")
            if item.get("period_end") and item.get("period_end") not in period_ends:
                _fail(f"{symbol}: missing row period outside evidenced required periods")
            if not item.get("period_end") and item.get("period_evidence_status") != "missing_explicit_annual_period_evidence":
                _fail(f"{symbol}: unknown missing row lacks period evidence status")
            if tuple(item.get("required_metrics") or []) != REQUIRED_METRICS:
                _fail(f"{symbol}: required metric order mismatch")
            missing = set(item.get("missing_metrics") or [])
            present = set(item.get("present_model_ready_metrics") or [])
            if not missing.issubset(set(REQUIRED_METRICS)) or not present.issubset(set(REQUIRED_METRICS)):
                _fail(f"{symbol}: invalid metric vocabulary")
            if missing & present:
                _fail(f"{symbol}: metric both missing and present")
        queue = row.get("qualification_queue") or {}
        if queue.get("status") not in {"needs_owner_approved_bounded_restage", "blocked_no_candidate_documents"}:
            _fail(f"{symbol}: invalid queue status")
        for candidate in queue.get("candidate_documents") or []:
            if not str(candidate.get("document_id") or "").startswith("psx:"):
                _fail(f"{symbol}: invalid candidate document")
            if not str(candidate.get("source_url") or "").startswith("https://dps.psx.com.pk/"):
                _fail(f"{symbol}: candidate missing official URL")
            if "reason" not in candidate:
                _fail(f"{symbol}: candidate missing reason")
        audit = row.get("audit_only_series") or {}
        if "audit_only_fact_count" not in audit or audit.get("model_loadable_count") is None:
            _fail(f"{symbol}: audit-only coverage missing")


def main() -> None:
    half_year = _period_from_doc(
        {"title": "Financial Results for the Half Year Ended December 31, 2025", "doc_type": "results"},
        "financial_results",
    )
    if not half_year or half_year.get("period_type") != "interim":
        _fail("half-year title was misclassified as annual")
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot_order = list((profiles.get("pilot") or {}).get("symbols") or [])
    pilot = set(pilot_order)
    if len(pilot_order) != 20 or len(pilot) != 20:
        _fail("pilot boundary must be exactly 20")
    expected = build()
    expected_again = build()
    if _dump(expected) != _dump(expected_again):
        _fail("builder output is not deterministic")
    _assert_no_values(expected)
    _assert_shape(expected, pilot)
    before = OUT.read_bytes()
    build()
    if before != OUT.read_bytes():
        _fail("builder output is not idempotent")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_ci_slice.py")], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        _fail(result.stdout + result.stderr)
    slice_data = load_json(ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json", {"tickers": []})
    by_symbol = {row.get("symbol"): row for row in slice_data.get("tickers") or []}
    if set(by_symbol) != pilot:
        _fail("CI slice does not contain exact pilot")
    for symbol, state_row in expected.get("companies", {}).items():
        if (by_symbol.get(symbol) or {}).get("financial_coverage") != state_row:
            _fail(f"{symbol}: CI slice financial_coverage mismatch")
    print(f"financial_coverage: PASS ({len(pilot)} companies)")


if __name__ == "__main__":
    main()
