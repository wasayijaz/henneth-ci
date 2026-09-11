"""Build the formal peer registry for the exact Company Intelligence pilot.

The v1 method is intentionally narrow: every company is grouped only by the
retained official/exchange sector label already present in state/sectors.json.
This is a pilot-sector cohort registry, not a comparables, valuation, or
performance model.
"""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psx_data import STATE, load_json, save_json
from build_ci_artifact_integrity import utc_z

OUT = STATE / "company_intel" / "peer_registry.json"
METHOD = "pilot_official_sector_cohort_v1"
SCHEMA_VERSION = 1


def _sector_row(sectors, sym):
    row = (sectors.get("tickers") or {}).get(sym) or {}
    return {
        "sector": row.get("sector") or None,
        "sector_code": row.get("code") or None,
    }


def build():
    profiles = load_json(STATE / "company_profiles.json", {})
    sectors = load_json(STATE / "sectors.json", {})
    universe = load_json(STATE / "universe.json", {"symbols": {}}).get("symbols", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    if len(pilot) != 20 or len(set(pilot)) != 20:
        raise SystemExit(f"peer_registry: expected 20 unique pilot symbols, got {len(pilot)}")
    if not sectors.get("source") or not sectors.get("updated"):
        raise SystemExit("peer_registry: sectors source/updated missing")
    sector_rows = {sym: _sector_row(sectors, sym) for sym in pilot}
    missing = [sym for sym, row in sector_rows.items() if not row["sector"] or not row["sector_code"]]
    if missing:
        raise SystemExit(f"peer_registry: missing official sector label/code for {', '.join(missing)}")

    groups = {}
    for sym in pilot:
        sector = sector_rows[sym]["sector"]
        code = sector_rows[sym]["sector_code"]
        key = code
        if key not in groups:
            groups[key] = {
                "sector_code": code,
                "sector": sector,
                "members": [],
            }
        groups[key]["members"].append(sym)

    companies = {}
    for sym in pilot:
        sector = sector_rows[sym]["sector"]
        code = sector_rows[sym]["sector_code"]
        key = code
        cohort = list(groups[key]["members"])
        peers = [peer for peer in cohort if peer != sym]
        member_details = [{"symbol": member, "name": (universe.get(member) or {}).get("name") or ""} for member in cohort]
        formal_peer_details = [{"symbol": member, "name": (universe.get(member) or {}).get("name") or ""} for member in peers]
        companies[sym] = {
            "symbol": sym,
            "registry_status": "available",
            "peer_set_kind": "pilot_sector_cohort",
            "method": METHOD,
            "sector": sector,
            "sector_code": code,
            "members": cohort,
            "formal_peers": peers,
            "member_details": member_details,
            "formal_peer_details": formal_peer_details,
            "international_peers": {
                "status": "unavailable",
                "reason": "no_authoritative_international_peer_registry",
                "members": [],
            },
            "limitations": [
                "pilot_boundary_only",
                "official_sector_label_only",
                "not_comparability_analysis",
                "no_valuation_or_performance_claims",
            ],
        }

    out = {
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "version": "v1",
        "as_of": sectors.get("updated") or profiles.get("updated") or utc_z(os.environ.get("HENNETH_CI_BUILD_CUTOFF_AT")),
        "source": {
            "sector_labels": sectors.get("source"),
            "pilot_symbols": "state/company_profiles.json pilot.symbols",
        },
        "pilot_symbols": pilot,
        "policy": {
            "scope": "Exact 20-company CI pilot only.",
            "peer_definition": "Other exact-pilot companies sharing the same retained official/exchange sector label.",
            "international_registry": "unavailable",
            "claims": "No valuation, performance, quality, rank, similarity, or comparability claim is made.",
        },
        "groups": [groups[key] for key in sorted(groups, key=lambda value: (groups[value]["sector"] or "", value))],
        "companies": companies,
    }
    save_json(OUT, out)
    print(f"peer_registry: {len(companies)} companies, {len(groups)} sector groups -> {OUT.relative_to(STATE.parent)}")
    return out


if __name__ == "__main__":
    build()
