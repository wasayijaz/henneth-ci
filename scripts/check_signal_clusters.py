from __future__ import annotations

import copy
import json
import subprocess
import sys

from build_signal_clusters import OUT, build
from psx_data import ROOT, STATE, load_json
from signal_clusters import build_signal_state, eligible_observation


def ev(symbol="MLCF", event_type="acquisition_divestment", subtype="acquisition", text=None,
       date="2026-01-01", detected="2026-01-02T09:00:00+00:00", doc="psx:1",
       url="https://dps.psx.com.pk/download/document/1.pdf", source="PSX DPS",
       flags=None, intelligence_type="reported_fact", level=1):
    text = text or "Public Announcement of offer to Acquire shares of Target Cement Limited (the Target Company)."
    return {
        "event_id": f"evt_{symbol}_{doc}_{abs(hash(text)) % 100000}",
        "company_id": symbol,
        "symbol": symbol,
        "event_type": event_type,
        "event_subtype": subtype,
        "intelligence_type": intelligence_type,
        "detected_at": detected,
        "effective_date": date,
        "description": text,
        "source_url": url,
        "source_quality_level": level,
        "confidence": 99,
        "evidence": [{
            "document_id": doc,
            "source": source,
            "source_url": url,
            "page": 1,
            "text": text,
            "content_sha256": "a" * 64,
            "evidence_sha256": f"{abs(hash((doc, text))) % (10 ** 16):016x}".ljust(64, "b"),
        }],
        "quality_flags": flags or [],
    }


def state(events, pilot=("MLCF",)):
    companies = {sym: {"events": []} for sym in pilot}
    for event in events:
        companies.setdefault(event["symbol"], {"events": []})["events"].append(event)
    return {"schema_version": 1, "pilot_symbols": list(pilot), "companies": companies}


def assert_no_cluster(name, events):
    out = build_signal_state(state(events), sorted({e["symbol"] for e in events} or {"MLCF"}), as_of="2026-12-31T00:00:00+00:00")
    clusters = [c for row in out["companies"].values() for c in row["clusters"]]
    assert not clusters, name
    assert any(row["rejection_reasons"] for row in out["companies"].values()), name + "_no_rejection"


def main():
    checks = 0
    # 1 DGKC table of contents is not semantic evidence.
    assert_no_cluster("dgkc_toc", [ev("DGKC", "debt_refinancing", "credit_event", "AFFECTING COMPANY STRATEGY 47 DEFAULT IN PAYMENT OF DEBTS 49 DGKC Annual Report 2025")]); checks += 1
    # 2 Old CCP historical recounting is outside registry.
    assert_no_cluster("old_ccp", [ev("DGKC", "regulatory_change", "regulatory_action", "CCP issued Show Cause Notice on October 28, 2008 for cement prices.")]); checks += 1
    # 3 BOP MOU is omitted from initial registry; not a contract award.
    assert_no_cluster("bop_mou", [ev("BOP", "contract_tender", "contract", "The Bank of Punjab signed an MOU with NUST for student expenses.")]); checks += 1
    # 4 Historical agreement noun/recounting without current stage is rejected.
    assert_no_cluster("historical_agreement", [ev("MLCF", text="The Company entered into an agreement with Supplier Limited in 2018 and continues operations.")]); checks += 1
    # 5 Generic CEO governance wording has no named person/change verb.
    assert_no_cluster("generic_ceo", [ev("BOP", "management_change", "management_change", "The President/CEO is appointed by the Government of Punjab and is Chief Executive.")]); checks += 1
    # 6 FCCL acquisition noun phrase without effective date/stage is rejected.
    assert_no_cluster("fccl_noun_phrase", [ev("FCCL", text="Acquisition of Polypropylene Bags Manufacturing plant at Hattar KPK.", date=None, flags=["unknown_effective_date"])]) ; checks += 1

    # 7 Mirrored issuer/PSX documents are the same originator, not corroboration.
    psx = ev("MLCF", text="Public Announcement of offer to Acquire shares of Target Cement Limited (the Target Company).", doc="psx:7", source="PSX DPS", url="https://dps.psx.com.pk/download/document/7.pdf")
    issuer = ev("MLCF", text=psx["description"], doc="issuer:7", source="Issuer website", url="https://issuer.example.com/offer.pdf")
    out = build_signal_state(state([psx, issuer]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    clusters = out["companies"]["MLCF"]["clusters"]
    assert len(clusters) == 1 and clusters[0]["assessment"] == "single_source" and clusters[0]["confidence"]["components"]["originator_count"] == 1 and clusters[0]["confidence"]["components"]["distributor_count"] == 2
    checks += 1
    # 8 Exact duplicate same distributor dedupes into one member with duplicate metadata.
    dup = copy.deepcopy(psx); dup["event_id"] = "evt_duplicate"
    out = build_signal_state(state([psx, dup]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    cluster = out["companies"]["MLCF"]["clusters"][0]
    assert len(cluster["observations"]) == 1 and cluster["observations"][0]["duplicates"]
    checks += 1
    # 9 Generic filings are rejected.
    assert_no_cluster("generic_filings", [ev("MLCF", "filing", "notice", "Quarterly financial statements filed with exchange.")]); checks += 1
    # 10 Different targets remain separate propositions.
    t1 = ev("MLCF", text="Public Announcement of offer to Acquire shares of Alpha Cement Limited (the Target Company).")
    t2 = ev("MLCF", text="Public Announcement of offer to Acquire shares of Beta Cement Limited (the Target Company).", doc="psx:2")
    out = build_signal_state(state([t1, t2]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    assert len(out["companies"]["MLCF"]["clusters"]) == 2
    checks += 1
    # 11 Schedule/permit language is not contradiction registry.
    assert_no_cluster("schedule_permit", [ev("MLCF", "regulatory_change", "permit", "Permit schedule revised for plant maintenance.")]); checks += 1
    # 12 Periods/effective dates separate otherwise identical assertions.
    p1 = ev("MLCF", date="2026-01-01")
    p2 = ev("MLCF", date="2026-02-01", doc="psx:22")
    out = build_signal_state(state([p1, p2]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    assert len(out["companies"]["MLCF"]["clusters"]) == 2
    checks += 1
    # 13 Sequential stages are not contradiction.
    intention = ev("MLCF", text="Public Announcement of Intention for the acquisition of Target Cement Limited.", doc="psx:31")
    completed = ev("MLCF", text="The acquisition of Target Cement Limited has been completed.", doc="psx:32")
    out = build_signal_state(state([intention, completed]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    assert len(out["companies"]["MLCF"]["clusters"]) == 2 and {c["assessment"] for c in out["companies"]["MLCF"]["clusters"]} == {"single_source", "supersession"}
    checks += 1
    # 14 Registry-defined incompatible assertions are contested.
    terminated = ev("MLCF", text="The acquisition of Target Cement Limited has been terminated.", doc="psx:33")
    out = build_signal_state(state([completed, terminated]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    assert {c["assessment"] for c in out["companies"]["MLCF"]["clusters"]} == {"inconsistent"}
    checks += 1
    named = ev("UBL", "management_change", "management_change", "Mr. Shoukat Ali has been appointed as the Company Secretary of UBL with immediate effect.", doc="psx:34")
    out = build_signal_state(state([named], ["UBL"]), ["UBL"], as_of="2026-12-31T00:00:00+00:00")
    prop = out["companies"]["UBL"]["clusters"][0]["proposition"]
    assert prop["person"] == "Mr. Shoukat Ali" and prop["role"] == "Company Secretary" and prop["verb"] == "appointment"
    checks += 1
    # 15 Missing/unknown fields reject.
    bad = ev("MLCF"); bad["effective_date"] = None
    assert eligible_observation(bad, "2026-12-31T00:00:00+00:00")[0] is None
    checks += 1
    # 16 Future cutoff rejects pre-as-of.
    assert eligible_observation(ev("MLCF", detected="2027-01-01T00:00:00+00:00"), "2026-12-31T00:00:00+00:00")[0] is None
    checks += 1
    # 17 Invalid provenance rejects.
    invalid = ev("MLCF"); invalid["evidence"][0]["source_url"] = "file:///tmp/x.pdf"; invalid["evidence"][0]["content_sha256"] = ""
    assert eligible_observation(invalid, "2026-12-31T00:00:00+00:00")[0] is None
    checks += 1
    # 18 Confidence is transparent band/components only, no percentage field.
    out = build_signal_state(state([psx]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    conf = out["companies"]["MLCF"]["clusters"][0]["confidence"]
    assert "band" in conf and "components" in conf and "value" not in conf and "probability" not in conf
    checks += 1
    # 19 Order invariant pure state.
    a = build_signal_state(state([t1, t2, psx]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    b = build_signal_state(state([psx, t2, t1]), ["MLCF"], as_of="2026-12-31T00:00:00+00:00")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    checks += 1

    before = OUT.read_bytes() if OUT.exists() else None
    real = build()
    pilot = set(real["pilot_symbols"])
    # 20 Exact 20-company coverage.
    assert len(pilot) == 20 and set(real["companies"]) == pilot
    checks += 1
    # 21 Invalid draft clusters disappear; no broad convergence status/source.
    all_clusters = [c for row in real["companies"].values() for c in row.get("clusters", [])]
    assert real["source"] == "state/company_intel/operating_events.json"
    assert not any(c.get("status") == "convergent" or c.get("assessment") == "convergent" for c in all_clusters)
    assert len(all_clusters) < 51
    checks += 1
    # 22 Builder idempotency and exact CI slice seam.
    after = OUT.read_bytes()
    build()
    assert after == OUT.read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_ci_slice.py")], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    slice_state = load_json(ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json", {"tickers": []})
    by_symbol = {row.get("symbol"): row for row in slice_state.get("tickers") or []}
    assert set(by_symbol) == pilot
    for sym in pilot:
        assert by_symbol[sym].get("signal_clusters") == real["companies"][sym]
    assert before is None or OUT.read_bytes()
    checks += 1
    print(f"signal_clusters: PASS ({checks} adversarial/real-state assertions, {len(all_clusters)} clusters)")


if __name__ == "__main__":
    main()
