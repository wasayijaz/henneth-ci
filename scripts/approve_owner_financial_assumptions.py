#!/usr/bin/env python3
"""Manually append approved copies of private CI financial-assumption drafts.

This is a server-only handoff. It requires the Henneth CI Supabase service
credential and the configured owner UUID, validates the draft row, then inserts
a new approved copy with the current approval timestamp. The original draft is
left untouched.

Absent configuration is a safe no-op. Network/API failures degrade without
printing credentials.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Callable
import urllib.parse
import urllib.request
import uuid

from import_owner_financial_assumptions import (
    ALLOWED_METRICS,
    ENV_KEY,
    ENV_OWNER_ID,
    ENV_URL,
    TABLE,
    finite,
    iso_date,
)
from psx_data import STATE, load_json


SELECT_FIELDS = (
    "id,user_id,symbol,metric,value,unit,available_on,source_label,source_url,"
    "rationale,approved,approved_at,created_at"
)
SCRIPT_ID = "approve_owner_financial_assumptions.py"
FetchDraft = Callable[[str, str, str, str], dict[str, Any] | None]
InsertApproval = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def _pilot_symbols(state_dir: Path) -> set[str]:
    profiles = load_json(Path(state_dir) / "company_profiles.json", {})
    symbols = (profiles.get("pilot") or {}).get("symbols") or []
    return {str(symbol).strip().upper() for symbol in symbols if str(symbol or "").strip()}


def _config_from_env(env: dict[str, str] | None = None) -> tuple[tuple[str, str, str] | None, list[str]]:
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


def _has_control_chars(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _clean_row_id(row_id: str) -> str | None:
    text = str(row_id or "").strip()
    try:
        return str(uuid.UUID(text))
    except ValueError:
        return None


def _fetch_draft(url: str, key: str, owner_id: str, row_id: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode({
        "select": SELECT_FIELDS,
        "id": "eq." + row_id,
        "user_id": "eq." + owner_id,
        "limit": "1",
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
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    return None


def _insert_approval(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{url}/rest/v1/{TABLE}",
        method="POST",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "apikey": key,
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body) if body else {}
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    return parsed if isinstance(parsed, dict) else {}


def _validate_draft(
    row: dict[str, Any],
    *,
    row_id: str,
    owner_id: str,
    pilot: set[str],
    approved_at: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if str(row.get("id") or "").strip() != row_id:
        return None, "row_id_mismatch"
    if str(row.get("user_id") or "").strip() != owner_id:
        return None, "row_not_owned_by_configured_owner"
    if row.get("approved") is not False:
        return None, "draft_not_unapproved"
    if row.get("approved_at") is not None:
        return None, "draft_already_has_approved_at"

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
    approved_on = iso_date(approved_at)
    if not available_on or not approved_on:
        return None, "missing_approval_or_source_date"
    if available_on > approved_on:
        return None, "source_available_after_approval"

    source_label = str(row.get("source_label") or "").strip()
    source_url = str(row.get("source_url") or "").strip()
    rationale = str(row.get("rationale") or "").strip()
    if not source_label or len(source_label) > 500 or _has_control_chars(source_label):
        return None, "invalid_source_label"
    if source_url and (not source_url.startswith("https://") or len(source_url) > 2000 or _has_control_chars(source_url)):
        return None, "unsafe_source_url"
    if not rationale or len(rationale) > 2000 or _has_control_chars(rationale):
        return None, "invalid_rationale"

    payload: dict[str, Any] = {
        "user_id": owner_id,
        "symbol": symbol,
        "metric": metric,
        "value": value,
        "unit": unit,
        "available_on": available_on,
        "source_label": source_label,
        "source_url": source_url or None,
        "rationale": rationale,
        "approved": True,
        "approved_at": approved_at,
    }
    return payload, None


def approval_timestamp(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def run(
    row_ids: list[str],
    *,
    state_dir: Path = STATE,
    env: dict[str, str] | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    fetch_draft: FetchDraft = _fetch_draft,
    insert_approval: InsertApproval = _insert_approval,
) -> dict[str, Any]:
    cleaned_ids: list[str] = []
    invalid_ids = 0
    for row_id in row_ids:
        cleaned = _clean_row_id(row_id)
        if cleaned:
            cleaned_ids.append(cleaned)
        else:
            invalid_ids += 1

    if not cleaned_ids:
        print("owner_financial_assumption_approval: no valid row ids")
        return {"mode": "noop", "approved": 0, "rejected": {"invalid_row_id": invalid_ids}}

    config, missing = _config_from_env(env)
    if missing:
        print(f"owner_financial_assumption_approval: dry-run missing_config={','.join(missing)}")
        return {"mode": "dry-run", "approved": 0, "rejected": {"invalid_row_id": invalid_ids} if invalid_ids else {}, "missing": missing}
    assert config is not None
    url, key, owner_id = config
    pilot = _pilot_symbols(Path(state_dir))
    approved_at = approval_timestamp(now)
    rejected: dict[str, int] = {"invalid_row_id": invalid_ids} if invalid_ids else {}
    approved = 0

    for row_id in cleaned_ids:
        try:
            draft = fetch_draft(url, key, owner_id, row_id)
        except Exception as exc:  # noqa: BLE001 - fail closed and avoid secret-bearing details
            reason = f"fetch_failed_{type(exc).__name__}"
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        if not draft:
            rejected["draft_not_found"] = rejected.get("draft_not_found", 0) + 1
            continue
        payload, reason = _validate_draft(draft, row_id=row_id, owner_id=owner_id, pilot=pilot, approved_at=approved_at)
        if payload is None:
            rejected[reason or "invalid_draft"] = rejected.get(reason or "invalid_draft", 0) + 1
            continue
        if dry_run:
            approved += 1
            continue
        try:
            insert_approval(url, key, payload)
            approved += 1
        except Exception as exc:  # noqa: BLE001 - fail closed and avoid secret-bearing details
            reason = f"insert_failed_{type(exc).__name__}"
            rejected[reason] = rejected.get(reason, 0) + 1

    mode = "dry-run" if dry_run else "approved"
    rejected_text = ",".join(f"{name}={rejected[name]}" for name in sorted(rejected)) or "none"
    print(f"owner_financial_assumption_approval: {mode}={approved} rejected={rejected_text}")
    return {
        "mode": mode,
        "approved": approved,
        "rejected": rejected,
        "approved_at": approved_at,
        "script": SCRIPT_ID,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, default=STATE)
    parser.add_argument("--row-id", action="append", required=True, help="Draft row UUID to approve; repeat for multiple rows.")
    parser.add_argument("--dry-run", action="store_true", help="Validate drafts but do not insert approved copies.")
    args = parser.parse_args(argv)
    run(args.row_id, state_dir=args.state_dir, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
