"""Contract checks for the CI causal-driver evidence map."""
from __future__ import annotations

import json
import hashlib
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "company_intel" / "causal_foundations.json"


def load(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def walk(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        raise AssertionError("nonfinite numeric value")
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"return_pct", "probability", "price", "valuation_impact", "revenue_impact", "eps_impact", "fcf_impact", "ebitda_impact"}:
                raise AssertionError(f"forbidden numeric/forecast field leaked: {key}")
            walk(value)
    elif isinstance(obj, list):
        for value in obj:
            walk(value)


def expected_edge_id(symbol, cause):
    parts = (symbol, cause.get("driver"), cause.get("target"), cause.get("statement_line"), cause.get("unit"), cause.get("edge_basis"))
    raw = "|".join(str(part or "") for part in parts)
    return "cause_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def main():
    checks = 0
    profiles = load(STATE / "company_profiles.json")
    pilot_order = list((profiles.get("pilot") or {}).get("symbols") or [])
    pilot = set(pilot_order)
    if len(pilot_order) != 20 or len(pilot) != 20:
        raise AssertionError("pilot boundary must be exactly 20")
    data = load(OUT)
    walk(data)
    if set(data.get("pilot_symbols") or []) != pilot or set(data.get("companies") or {}) != pilot:
        raise AssertionError("pilot boundary mismatch")
    if data.get("pilot_symbols") != pilot_order or list((data.get("companies") or {}).keys()) != pilot_order:
        raise AssertionError("pilot order must match company_profiles")
    policy = data.get("policy") or {}
    if not (policy.get("categorical_status_only") and policy.get("no_numeric_impact") and policy.get("no_forecast_probability_valuation_or_price")):
        raise AssertionError("policy flags missing")

    graphs = load(STATE / "company_intel" / "driver_graphs.json")
    events = load(STATE / "company_intel" / "operating_events.json")
    studies = load(STATE / "company_intel" / "event_studies.json")
    allowed_status = {
        "observed_event_with_strict_study",
        "observed_event_study_blocked",
        "observed_event_no_study",
        "driver_edge_only",
    }
    allowed_requirements = {
        "period_aligned_financial_outcomes_required",
        "strict_event_study_baseline_required",
        "event_study_required",
        "retained_official_event_link_required",
    }
    for sym, row in sorted((data.get("companies") or {}).items()):
        graph = ((graphs.get("companies") or {}).get(sym) or {})
        if row.get("symbol") != sym or row.get("sector") != graph.get("sector"):
            raise AssertionError(f"{sym} company identity/sector mismatch")
        graph_edges = [
            (edge.get("from"), edge.get("to"), edge.get("statement_line"), edge.get("unit"), edge.get("basis"))
            for edge in (graph.get("edges") or [])
        ]
        event_ids = {event.get("event_id") for event in (((events.get("companies") or {}).get(sym) or {}).get("events") or [])}
        causal_rows = row.get("causal_rows") or []
        if len(causal_rows) != len(graph_edges):
            raise AssertionError(f"{sym} causal rows must match driver edge count")
        causal_ids = [cause.get("causal_id") for cause in causal_rows]
        edge_ids = [cause.get("edge_id") for cause in causal_rows]
        if len(set(causal_ids)) != len(causal_ids) or len(set(edge_ids)) != len(edge_ids):
            raise AssertionError(f"{sym} causal/edge IDs must be unique")
        for cause in causal_rows:
            if cause.get("symbol") != sym:
                raise AssertionError(f"{sym} causal row crosses company boundary")
            edge_key = (cause.get("driver"), cause.get("target"), cause.get("statement_line"), cause.get("unit"), cause.get("edge_basis"))
            if edge_key not in graph_edges:
                raise AssertionError(f"{sym} unresolved driver edge {edge_key}")
            expected_id = expected_edge_id(sym, cause)
            if cause.get("edge_id") != expected_id or cause.get("causal_id") != expected_id:
                raise AssertionError(f"{sym} causal/edge ID mismatch")
            if cause.get("evidence_status") not in allowed_status:
                raise AssertionError(f"{sym} invalid evidence status")
            if cause.get("next_data_requirement") not in allowed_requirements:
                raise AssertionError(f"{sym} invalid next data requirement")
            if cause.get("policy") != {"numeric_impact": "blocked", "forecast": "blocked", "valuation": "blocked"}:
                raise AssertionError(f"{sym} row policy mismatch")
            for ref in cause.get("event_refs") or []:
                if ref.get("event_id") not in event_ids:
                    raise AssertionError(f"{sym} event ref does not resolve")
                event = next(item for item in (((events.get("companies") or {}).get(sym) or {}).get("events") or []) if item.get("event_id") == ref.get("event_id"))
                if event.get("symbol") != sym or event.get("company_id") != sym:
                    raise AssertionError(f"{sym} event ref crosses company boundary")
                if any(ref.get(key) != event.get(key) for key in ("event_type", "effective_date", "source_url")):
                    raise AssertionError(f"{sym} event ref metadata mismatch")
            for ref in cause.get("event_study_refs") or []:
                if ref.get("event_id") not in {item.get("event_id") for item in cause.get("event_refs") or []}:
                    raise AssertionError(f"{sym} study ref lacks retained event ref")
                study = (studies.get("studies") or {}).get(ref.get("event_id"))
                if not study or study.get("study_id") != ref.get("study_id"):
                    raise AssertionError(f"{sym} study ref does not resolve")
                if study.get("symbol") != sym:
                    raise AssertionError(f"{sym} study ref crosses company boundary")
                event = next((item for item in (((events.get("companies") or {}).get(sym) or {}).get("events") or []) if item.get("event_id") == ref.get("event_id")), None)
                if not event or study.get("event_id") != event.get("event_id") or study.get("effective_date") != event.get("effective_date"):
                    raise AssertionError(f"{sym} study/event identity mismatch")
                baseline = ((study.get("baseline") or {}).get("selected_date"))
                effective = event.get("effective_date")
                expected_strict = bool(baseline and effective and baseline < effective and ((study.get("baseline") or {}).get("status") == "available"))
                if ref.get("strict_no_lookahead") != expected_strict:
                    raise AssertionError(f"{sym} strict no-lookahead flag mismatch")
        checks += len(causal_rows)

    before = OUT.read_bytes()
    with tempfile.TemporaryDirectory() as temp_dir:
        candidate = Path(temp_dir) / "causal_foundations.json"
        env = os.environ.copy()
        env["HENNETH_CAUSAL_OUT"] = str(candidate)
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_causal_foundations.py")], capture_output=True, text=True, timeout=30, env=env)
        if result.returncode != 0:
            raise AssertionError("builder failed — " + ((result.stdout or result.stderr)[-400:]))
        if candidate.read_bytes() != before:
            raise AssertionError("builder is not byte-idempotent")

    slice_path = ROOT / "Henneth Desk 2.CI.0" / "data" / "company_intelligence.json"
    if slice_path.exists():
        slice_rows = {row.get("symbol"): row for row in load(slice_path).get("tickers") or []}
        for sym in pilot:
            if slice_rows.get(sym, {}).get("causal_foundations") != data["companies"][sym]:
                raise AssertionError(f"{sym} CI slice causal foundations mismatch")

    print(f"causal_foundations: PASS ({len(pilot)} companies, {checks} edge-resolved rows)")


if __name__ == "__main__":
    main()
