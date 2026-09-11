"""Validate the Company Intelligence formal peer registry contract."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psx_data import STATE, load_json

ROOT = STATE.parent
METHOD = "pilot_official_sector_cohort_v1"


def main():
    profiles = load_json(STATE / "company_profiles.json", {})
    sectors = load_json(STATE / "sectors.json", {})
    registry = load_json(STATE / "company_intel" / "peer_registry.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    if len(pilot) != 20 or len(set(pilot)) != 20:
        raise SystemExit(f"company_profiles pilot is {len(pilot)}, expected exact 20 unique symbols")
    if registry.get("schema_version") != 1 or registry.get("method") != METHOD or registry.get("version") != "v1":
        raise SystemExit("peer registry missing declared schema/method/version")
    if not registry.get("as_of") or not (registry.get("source") or {}).get("sector_labels"):
        raise SystemExit("peer registry missing as_of or sector-label source")
    if registry.get("pilot_symbols") != pilot:
        raise SystemExit("peer registry pilot order/boundary mismatch")
    companies = registry.get("companies") or {}
    if set(companies) != set(pilot):
        raise SystemExit("peer registry company boundary mismatch")

    expected_by_sector = {}
    for sym in pilot:
        sector_row = (sectors.get("tickers") or {}).get(sym) or {}
        sector = sector_row.get("sector")
        code = sector_row.get("code")
        if not sector or not code:
            raise SystemExit(f"{sym}: missing retained official sector label/code")
        key = code
        expected_by_sector.setdefault(key, []).append(sym)
    groups = registry.get("groups") or []
    if len(groups) != len(expected_by_sector):
        raise SystemExit("peer registry group count mismatch")
    seen_members = []
    for group in groups:
        code = group.get("sector_code")
        members = group.get("members") or []
        if code not in expected_by_sector:
            raise SystemExit(f"unexpected peer group {code}")
        if members != expected_by_sector[code]:
            raise SystemExit(f"{code}: peer group members mismatch")
        seen_members.extend(members)
    if sorted(seen_members) != sorted(pilot) or len(seen_members) != len(set(seen_members)):
        raise SystemExit("peer registry groups must cover the pilot exactly once")
    policy = registry.get("policy") or {}
    if policy.get("international_registry") != "unavailable" or "No valuation" not in str(policy.get("claims") or ""):
        raise SystemExit("peer registry policy missing unavailable/no-claims contract")

    singleton_count = 0
    for sym in pilot:
        sector_row = (sectors.get("tickers") or {}).get(sym) or {}
        sector = sector_row.get("sector")
        code = sector_row.get("code")
        key = code
        expected_members = expected_by_sector[key]
        row = companies.get(sym) or {}
        if row.get("symbol") != sym or row.get("method") != METHOD:
            raise SystemExit(f"{sym}: missing symbol/method")
        if row.get("peer_set_kind") != "pilot_sector_cohort":
            raise SystemExit(f"{sym}: invalid peer_set_kind")
        if row.get("sector") != sector or row.get("sector_code") != code:
            raise SystemExit(f"{sym}: sector label/code mismatch")
        if row.get("members") != expected_members:
            raise SystemExit(f"{sym}: sector cohort members mismatch")
        expected_peers = [peer for peer in expected_members if peer != sym]
        if row.get("formal_peers") != expected_peers:
            raise SystemExit(f"{sym}: formal peer list mismatch")
        if sym in (row.get("formal_peers") or []):
            raise SystemExit(f"{sym}: self appears in formal_peers")
        if not expected_peers:
            singleton_count += 1
        international = row.get("international_peers") or {}
        if international.get("status") != "unavailable" or international.get("members") != []:
            raise SystemExit(f"{sym}: international registry must be explicitly unavailable")
        limitations = set(row.get("limitations") or [])
        for required in ("pilot_boundary_only", "official_sector_label_only", "not_comparability_analysis", "no_valuation_or_performance_claims"):
            if required not in limitations:
                raise SystemExit(f"{sym}: missing limitation {required}")

    slice_data = load_json(ROOT / "ci-app" / "data" / "company_intelligence.json", {})
    slice_rows = {row.get("symbol"): row for row in (slice_data.get("tickers") or []) if isinstance(row, dict)}
    if set(slice_rows) == set(pilot):
        for sym in pilot:
            if slice_rows[sym].get("peer_registry") != companies[sym]:
                raise SystemExit(f"{sym}: CI slice peer_registry mismatch")
            if [row.get("symbol") for row in companies[sym].get("member_details") or []] != companies[sym]["members"]:
                raise SystemExit(f"{sym}: CI slice member_details mismatch")
            if [row.get("symbol") for row in companies[sym].get("formal_peer_details") or []] != companies[sym]["formal_peers"]:
                raise SystemExit(f"{sym}: CI slice formal_peer_details mismatch")

    if singleton_count < 1:
        raise SystemExit("peer registry should expose empty formal_peers for singleton pilot sectors")
    print(f"peer_registry: PASS ({len(pilot)} companies, {len(expected_by_sector)} sector groups, {singleton_count} singleton cohorts)")


if __name__ == "__main__":
    main()
