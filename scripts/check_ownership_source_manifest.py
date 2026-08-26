#!/usr/bin/env python3
"""Verify the review-only ownership source manifest cannot claim ownership facts."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_ownership_source_manifest import OUT, REQUIRED_REVIEW_FIELDS, build, safe_official_url
from psx_data import STATE, load_json


def fail(message: str) -> None:
    raise AssertionError(message)


def dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def main() -> None:
    if not OUT.exists():
        fail("ownership source review manifest is missing")
    manifest = load_json(OUT, {})
    rebuilt = build(write=False)
    if dump(manifest) != dump(rebuilt):
        fail("ownership source review manifest is stale or non-deterministic")
    pilot = list(((load_json(STATE / "company_profiles.json", {}).get("pilot") or {}).get("symbols") or []))
    if len(pilot) != 20 or len(set(pilot)) != 20 or manifest.get("pilot_symbols") != pilot:
        fail("exact 20-company pilot boundary mismatch")
    if manifest.get("kind") != "ownership_source_review_manifest" or (manifest.get("policy") or {}).get("review_only") is not True:
        fail("review-only policy missing")
    if (manifest.get("policy") or {}).get("no_ownership_activation") is not True:
        fail("ownership activation guard missing")
    companies = manifest.get("companies") or {}
    if set(companies) != set(pilot):
        fail("company boundary mismatch")
    for symbol, row in companies.items():
        if symbol == "FCCL" or row.get("symbol") != symbol:
            fail(f"{symbol}: nonpilot or symbol mismatch")
        if row.get("status") not in {"review_required", "no_retained_candidate"}:
            fail(f"{symbol}: invalid review status")
        if row.get("ownership_facts") != []:
            fail(f"{symbol}: review manifest emitted ownership facts")
        if row.get("required_fields_before_activation") != REQUIRED_REVIEW_FIELDS:
            fail(f"{symbol}: activation fields drifted")
        for candidate in row.get("candidates") or []:
            if candidate.get("symbol") != symbol or candidate.get("usable_ownership_facts") is not False or candidate.get("review_required") is not True:
                fail(f"{symbol}: candidate can be misread as ownership evidence")
            if candidate.get("source_owner") not in {"issuer", "psx", "secp"} or not safe_official_url(candidate.get("source_url")):
                fail(f"{symbol}: unsafe or unknown candidate source")
            if any(key in candidate for key in ("percentage", "shares", "holder", "page")):
                fail(f"{symbol}: candidate contains ownership fact fields")
    summary = manifest.get("summary") or {}
    if summary.get("activated_company_count") != 0 or summary.get("company_count") != 20:
        fail("review manifest summary claims activation")
    if "buy" in dump(manifest).lower() or "sell" in dump(manifest).lower():
        fail("advice language leaked")
    print(f"ownership_source_manifest: PASS ({summary.get('candidate_count')} review candidates; 0 activated companies)")


if __name__ == "__main__":
    main()
