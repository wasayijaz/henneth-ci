#!/usr/bin/env python3
"""Verify the owner financial-assumption handoff is review-only and current."""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path
import sys
from typing import Any
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_owner_financial_assumption_handoff import KIND, OUT, TARGET_SYMBOLS, build
from import_owner_financial_assumptions import ALLOWED_METRICS, STRICT_MINIMUM_METRICS
from psx_data import load_json


EXPECTED_PRODUCTS = {
    "MLCF": {
        "forecast": ["revenue_growth_pct", "net_margin_pct"],
        "valuation": ["revenue_growth_pct", "net_margin_pct", "exit_pe", "net_debt"],
        "market_expectations": ["exit_pe", "net_margin_pct", "revenue_growth_pct"],
    },
    "DGKC": {
        "forecast": ["revenue_growth_pct", "net_margin_pct"],
        "valuation": ["revenue_growth_pct", "net_margin_pct", "exit_pe", "net_debt"],
        "market_expectations": ["exit_pe", "net_margin_pct", "revenue_growth_pct"],
    },
}
EXPECTED_UNIQUE_MISSING = ("exit_pe", "net_debt", "net_margin_pct", "revenue_growth_pct")


def fail(message: str) -> None:
    raise AssertionError(message)


def dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _has_control_chars(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def assert_manifest_current() -> dict[str, Any]:
    if not OUT.exists():
        fail("owner financial-assumption handoff manifest is missing")
    manifest = load_json(OUT, {})
    rebuilt = build(write=False)
    if dump(manifest) != dump(rebuilt):
        fail("owner financial-assumption handoff manifest is stale or non-deterministic")
    if manifest.get("kind") != KIND or manifest.get("target_symbols") != list(TARGET_SYMBOLS):
        fail("handoff manifest kind or target boundary drifted")
    policy = manifest.get("policy") or {}
    for key in (
        "review_only",
        "secret_free",
        "no_assumption_values_in_manifest",
        "no_supabase_read_or_write",
        "does_not_approve_rows",
        "does_not_activate_formal_engines",
        "append_copy_approval_remains_manual",
    ):
        if policy.get(key) is not True:
            fail(f"handoff policy missing {key}")
    text = dump(manifest).lower()
    for forbidden in ("service_key", "apikey", "authorization", "bearer ", "password"):
        if forbidden in text:
            fail(f"secret-bearing marker leaked into manifest: {forbidden}")
    companies = manifest.get("companies") or {}
    if set(companies) != set(TARGET_SYMBOLS):
        fail("handoff company boundary mismatch")
    for symbol in TARGET_SYMBOLS:
        row = companies.get(symbol) or {}
        if row.get("status") != "input_ready_pending_owner_drafts":
            fail(f"{symbol}: expected input-ready pending owner drafts")
        if row.get("forecast_readiness_status") != "input_ready" or row.get("financial_model_inputs_status") != "ready":
            fail(f"{symbol}: source prerequisites are not ready")
        if row.get("reference_cases_can_satisfy_missing_records") is not False:
            fail(f"{symbol}: reference cases can satisfy missing records")
        refs = row.get("historical_reference_cases") or []
        if {ref.get("metric") for ref in refs} != {"revenue_growth_pct", "net_margin_pct"}:
            fail(f"{symbol}: expected historical reference-case context only")
        if any(ref.get("can_satisfy_approved_record") is not False for ref in refs):
            fail(f"{symbol}: reference case marked eligible for approval gap")
        products = row.get("products") or {}
        for product, missing in EXPECTED_PRODUCTS[symbol].items():
            product_row = products.get(product) or {}
            if product_row.get("status") != "blocked_missing_approved_records":
                fail(f"{symbol}: {product} is not blocked on missing approved records")
            if product_row.get("missing_approved_records") != missing:
                fail(f"{symbol}: {product} missing records drifted: {product_row.get('missing_approved_records')}")
            accepted = [record.get("metric") for record in product_row.get("accepted_records") or []]
            expected_accepted = ["shares_out"] if product != "market_expectations" else ["current_price", "shares_out"]
            if accepted != expected_accepted:
                fail(f"{symbol}: {product} accepted deterministic operands drifted: {accepted}")
            for record in product_row.get("accepted_records") or []:
                if record.get("record_type") != "approved_market_operand" or record.get("value_present") is not True:
                    fail(f"{symbol}: {product} accepted a non-market operand")
        missing_metrics = [record.get("metric") for record in row.get("handoff_records") or []]
        if missing_metrics != list(EXPECTED_UNIQUE_MISSING):
            fail(f"{symbol}: unique handoff metrics drifted: {missing_metrics}")
        for record in row.get("handoff_records") or []:
            if "value" in record or "row_id" in record or "approved_at" in record:
                fail(f"{symbol}: handoff record contains activating row/value fields")
            metric = record.get("metric")
            contract = record.get("contract") or {}
            if metric not in ALLOWED_METRICS:
                fail(f"{symbol}: unsupported handoff metric {metric}")
            unit, minimum, maximum = ALLOWED_METRICS[metric]
            if contract.get("unit") != unit or contract.get("minimum") != minimum or contract.get("maximum") != maximum:
                fail(f"{symbol}: metric contract drifted for {metric}")
    summary = manifest.get("summary") or {}
    if summary.get("unique_missing_company_metric_count") != 8 or summary.get("formal_products_ready_count") != 0:
        fail("handoff summary claims missing or ready count incorrectly")
    return manifest


def validate_draft(row: dict[str, Any], manifest: dict[str, Any]) -> str | None:
    row_id = str(row.get("id") or "").strip()
    try:
        uuid.UUID(row_id)
    except ValueError:
        return "invalid_row_id"
    symbol = str(row.get("symbol") or "").strip().upper()
    metric = str(row.get("metric") or "").strip()
    companies = manifest.get("companies") or {}
    company = companies.get(symbol) or {}
    required_metrics = {item.get("metric") for item in company.get("handoff_records") or []}
    if symbol not in TARGET_SYMBOLS or metric not in required_metrics:
        return "not_required_by_current_handoff"
    if row.get("approved") is not False or row.get("approved_at") is not None:
        return "draft_not_inert"
    if metric not in ALLOWED_METRICS:
        return "unsupported_metric"
    value = finite(row.get("value"))
    if value is None:
        return "non_finite_value"
    unit, minimum, maximum = ALLOWED_METRICS[metric]
    if metric in STRICT_MINIMUM_METRICS:
        in_range = minimum < value <= maximum
    else:
        in_range = minimum <= value <= maximum
    if not in_range or row.get("unit") != unit:
        return "value_or_unit_out_of_contract"
    available_on = iso_date(row.get("available_on"))
    manifest_as_of = iso_date(manifest.get("as_of"))
    if not available_on:
        return "missing_available_on"
    if manifest_as_of and available_on > manifest_as_of:
        return "available_on_after_manifest_as_of"
    source_label = str(row.get("source_label") or "").strip()
    source_url = str(row.get("source_url") or "").strip()
    rationale = str(row.get("rationale") or "").strip()
    if not source_label or len(source_label) > 500 or _has_control_chars(source_label):
        return "invalid_source_label"
    if source_url and (not source_url.startswith("https://") or len(source_url) > 2000 or _has_control_chars(source_url)):
        return "unsafe_source_url"
    if not rationale or len(rationale) > 2000 or _has_control_chars(rationale):
        return "invalid_rationale"
    return None


def assert_draft_export(path: Path, manifest: dict[str, Any]) -> None:
    rows = load_json(path, [])
    if isinstance(rows, dict):
        rows = rows.get("rows") or rows.get("drafts") or []
    if not isinstance(rows, list):
        fail("draft export must be a list or an object with rows/drafts")
    rejected: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            rejected["row_not_object"] = rejected.get("row_not_object", 0) + 1
            continue
        reason = validate_draft(row, manifest)
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        seen.add((str(row["symbol"]).upper(), str(row["metric"])))
    expected = {
        (symbol, metric)
        for symbol in TARGET_SYMBOLS
        for metric in EXPECTED_UNIQUE_MISSING
    }
    missing = sorted(f"{symbol}:{metric}" for symbol, metric in expected - seen)
    extra = sorted(f"{symbol}:{metric}" for symbol, metric in seen - expected)
    if rejected or missing or extra:
        detail = {"rejected": rejected, "missing": missing, "extra": extra}
        fail("draft export is not a complete valid handoff set: " + json.dumps(detail, sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-export", type=Path, help="Optional local JSON export of inert draft rows to validate.")
    args = parser.parse_args(argv)
    manifest = assert_manifest_current()
    if args.draft_export:
        assert_draft_export(args.draft_export, manifest)
        print("owner_financial_assumption_handoff: PASS (manifest current; draft export complete and inert)")
    else:
        print("owner_financial_assumption_handoff: PASS (manifest current; review-only, 8 company-metric drafts required)")


if __name__ == "__main__":
    main()
