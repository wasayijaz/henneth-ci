#!/usr/bin/env python3
"""Import owner-approved financial assumptions from Henneth CI Supabase.

The formal engines already accept only approved, dated, source-labelled records
from ``state/company_intel/financial_engine_assumptions.json``. This adapter is
the server-only bridge from the private Supabase table into that state file. It
is inert when the CI Supabase secrets are absent, never prints secrets, and
replaces only rows previously imported by this adapter.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
import os
from pathlib import Path
import sys
from typing import Any
import urllib.parse
import urllib.request
import uuid

from psx_data import STATE, load_json, save_json


ENV_URL = "HENNETH_CI_SUPABASE_URL"
ENV_KEY = "HENNETH_CI_SUPABASE_SERVICE_KEY"
ENV_OWNER_ID = "HENNETH_CI_OWNER_USER_ID"
TABLE = "company_financial_assumptions"
OUT = STATE / "company_intel" / "financial_engine_assumptions.json"
IMPORTED_BY = "import_owner_financial_assumptions.py"
SOURCE_PREFIX = "supabase_owner_assumption:"
ALLOWED_METRICS = {
    "revenue_growth_pct": ("pct", -100.0, 500.0),
    "net_margin_pct": ("pct", -100.0, 100.0),
    "exit_pe": ("x", 0.0, 200.0),
    "net_debt": ("PKR", -10_000_000_000_000.0, 10_000_000_000_000.0),
}


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


def _state_date(state: dict[str, Any]) -> str | None:
    for key in ("as_of", "updated", "built"):
        parsed = iso_date(state.get(key))
        if parsed:
            return parsed
    meta = state.get("meta") or state.get("_meta") or {}
    if isinstance(meta, dict):
        for key in ("as_of", "updated", "built"):
            parsed = iso_date(meta.get(key))
            if parsed:
                return parsed
    return None


def _pilot_symbols(state_dir: Path) -> set[str]:
    profiles = load_json(state_dir / "company_profiles.json", {})
    symbols = (profiles.get("pilot") or {}).get("symbols") or []
    return {str(symbol).strip().upper() for symbol in symbols if str(symbol or "").strip()}


def _cutoff(state_dir: Path) -> str:
    dates = []
    for rel in (
        "company_profiles.json",
        "company_intel/financial_model_inputs.json",
        "company_intel/forecast_readiness.json",
    ):
        parsed = _state_date(load_json(state_dir / rel, {}))
        if parsed:
            dates.append(parsed)
    return max(dates) if dates else date.today().isoformat()


def config_from_env(env: dict[str, str] | None = None) -> tuple[tuple[str, str, str] | None, list[str]]:
    env = os.environ if env is None else env
    missing = [name for name in (ENV_URL, ENV_KEY, ENV_OWNER_ID) if not str(env.get(name) or "").strip()]
    if missing:
        return None, missing
    owner_id = str(env[ENV_OWNER_ID]).strip()
    try:
        uuid.UUID(owner_id)
    except ValueError:
        return None, [ENV_OWNER_ID]
    return (str(env[ENV_URL]).rstrip("/"), str(env[ENV_KEY]), owner_id), []


def fetch_rows(url: str, key: str, owner_id: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "select": "id,user_id,symbol,metric,value,unit,available_on,source_label,source_url,rationale,approved,approved_at,created_at",
        "approved": "eq.true",
        "user_id": "eq." + owner_id,
        "order": "approved_at.asc,created_at.asc",
    })
    req = urllib.request.Request(
        f"{url}/rest/v1/{TABLE}?{params}",
        headers={
            "apikey": key,
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, list) else []


def _is_imported_record(record: dict[str, Any]) -> bool:
    source_id = str((record.get("source") or {}).get("id") or "")
    return record.get("imported_by") == IMPORTED_BY or source_id.startswith(SOURCE_PREFIX)


def _valid_record(row: dict[str, Any], pilot: set[str], cutoff: str, owner_id: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    if owner_id and str(row.get("user_id") or "").strip() != owner_id:
        return None, "row_not_owned_by_configured_owner"
    symbol = str(row.get("symbol") or "").strip().upper()
    metric = str(row.get("metric") or "").strip()
    if symbol not in pilot:
        return None, "symbol_not_in_pilot"
    if metric not in ALLOWED_METRICS:
        return None, "unsupported_metric"
    value = finite(row.get("value"))
    if value is None:
        return None, "non_finite_value"
    unit, minimum, maximum = ALLOWED_METRICS[metric]
    if metric in ("revenue_growth_pct", "net_margin_pct", "net_debt"):
        in_range = minimum <= value <= maximum
    else:
        in_range = minimum < value <= maximum
    if not in_range or row.get("unit") != unit:
        return None, "value_or_unit_out_of_contract"
    available_on = iso_date(row.get("available_on"))
    if not available_on:
        return None, "missing_available_on"
    approved_on = iso_date(row.get("approved_at"))
    if not approved_on:
        return None, "missing_approved_at"
    if available_on > approved_on:
        return None, "source_available_after_approval"
    if approved_on > cutoff:
        return None, "available_on_after_state_cutoff"
    source_label = str(row.get("source_label") or "").strip()
    rationale = str(row.get("rationale") or "").strip()
    if not source_label or len(source_label) > 500 or not rationale or len(rationale) > 2000:
        return None, "missing_source_label_or_rationale"
    source_url = str(row.get("source_url") or "").strip()
    if source_url and not source_url.startswith("https://"):
        return None, "unsafe_source_url"
    row_id = str(row.get("id") or "").strip()
    if not row_id:
        return None, "missing_id"
    source = {
        "id": SOURCE_PREFIX + row_id,
        "label": source_label,
        "path": f"supabase:{TABLE}/{row_id}",
        "available_on": approved_on,
        "source_available_on": available_on,
        "approved_on": approved_on,
    }
    if source_url:
        source["url"] = source_url
    return {
        "symbol": symbol,
        "metric": metric,
        "value": value,
        "unit": unit,
        "approved": True,
        "approval_scope": "owner_approved_formal_engine_input",
        "record_type": "approved_assumption",
        # Approval is the earliest date this subjective input may affect the
        # deterministic product; never backdate it to the source publication.
        "available_on": approved_on,
        "imported_by": IMPORTED_BY,
        "owner_rationale": rationale,
        "approved_at": row.get("approved_at"),
        "source": source,
    }, None


def imported_records(rows: list[dict[str, Any]], pilot: set[str], cutoff: str, owner_id: str | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats: dict[str, int] = {}
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("approved") is not True:
            stats["not_approved"] = stats.get("not_approved", 0) + 1
            continue
        record, reason = _valid_record(row, pilot, cutoff, owner_id)
        if record is None:
            stats[reason or "invalid"] = stats.get(reason or "invalid", 0) + 1
            continue
        key = (record["symbol"], record["metric"])
        latest[key] = record
    return [latest[key] for key in sorted(latest)], stats


def merge_assumptions(existing: dict[str, Any], imported: list[dict[str, Any]]) -> dict[str, Any]:
    preserved = [record for record in existing.get("records") or [] if isinstance(record, dict) and not _is_imported_record(record)]
    merged = preserved + imported
    return {
        **existing,
        "records": merged,
        "owner_assumption_import": {
            "imported_by": IMPORTED_BY,
            "table": TABLE,
            "imported_record_count": len(imported),
            "policy": {
                "approved_rows_only": True,
                "latest_approved_row_per_symbol_metric": True,
                "unapproved_rows_not_imported": True,
                "formal_engine_gate_unchanged": True,
            },
        },
    }


def run(
    *,
    state_dir: Path = STATE,
    output_path: Path = OUT,
    env: dict[str, str] | None = None,
    remote_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state_dir = Path(state_dir)
    output_path = Path(output_path)
    config, missing = config_from_env(env)
    if remote_rows is None:
        if missing:
            print(f"owner_financial_assumptions: dry-run missing_config={','.join(missing)}")
            return {"mode": "dry-run", "missing": missing, "imported": 0, "rejected": {}}
        assert config is not None
        try:
            remote_rows = fetch_rows(config[0], config[1], config[2])
        except Exception as exc:
            print(f"owner_financial_assumptions: degraded {type(exc).__name__}: {str(exc)[:120]}")
            return {"mode": "degraded", "missing": [], "imported": 0, "rejected": {"fetch_failed": 1}}
    pilot = _pilot_symbols(state_dir)
    cutoff = _cutoff(state_dir)
    imported, rejected = imported_records(remote_rows, pilot, cutoff, config[2] if config else None)
    existing = load_json(output_path, {"schema_version": 1, "records": []})
    save_json(output_path, merge_assumptions(existing, imported))
    rejected_text = ",".join(f"{key}={rejected[key]}" for key in sorted(rejected)) or "none"
    print(f"owner_financial_assumptions: imported={len(imported)} rejected={rejected_text}")
    return {"mode": "imported", "missing": [], "imported": len(imported), "rejected": rejected}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, default=STATE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    run(state_dir=args.state_dir, output_path=args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
