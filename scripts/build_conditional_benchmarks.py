"""Build Conditional Historical Benchmarks v1 from retained state."""
from __future__ import annotations
import argparse
from pathlib import Path
from conditional_benchmarks import build_conditional_benchmarks
from psx_data import STATE, load_json, save_json

OUT = STATE / "company_intel" / "conditional_benchmarks.json"

def build(out_path: Path | None = None):
    profiles = load_json(STATE / "company_profiles.json", {})
    pilot = list((profiles.get("pilot") or {}).get("symbols") or [])
    events = load_json(STATE / "company_intel" / "operating_events.json", {})
    studies = load_json(STATE / "company_intel" / "event_studies.json", {})
    sectors = load_json(STATE / "sectors.json", {}).get("tickers") or {}
    result = build_conditional_benchmarks(pilot, events, studies, sectors)
    cutoffs = sorted(str(row.get("data_cutoff")) for row in (studies.get("studies") or {}).values() if row.get("data_cutoff"))
    result["as_of"] = cutoffs[-1] if cutoffs else "unknown"
    save_json(out_path or OUT, result)
    total = sum(row["benchmark_count"] for row in result["companies"].values())
    print(f"conditional_benchmarks: {total} event benchmarks across {len(pilot)} companies")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path); args = parser.parse_args(); build(args.out)
