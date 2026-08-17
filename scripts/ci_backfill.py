#!/usr/bin/env python3
"""Manual Company Intelligence backfill orchestrator.

This is a training-mode runner for owner-invoked backfills. It keeps each batch
small, immediately extracts verified bytes, then rebuilds the private CI slice.
It does not change scheduled cadence, add providers, or call any model.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

from psx_data import STATE, load_json, save_json

DEFAULT_BATCH_SIZE = 4
CURSOR_PATH = STATE / "company_intel" / "backfill_cursor.json"


def _pilot_symbols() -> list[str]:
    profiles = load_json(STATE / "company_profiles.json", {})
    symbols = list((profiles.get("pilot") or {}).get("symbols") or [])
    if not symbols:
        symbols = list((profiles.get("tickers") or {}).keys())
    return [str(symbol).upper() for symbol in symbols[:20]]


def _status() -> None:
    research = load_json(STATE / "research_index.json", {"documents": {}})
    docs = load_json(STATE / "company_documents.json", {"documents": {}})
    queue = load_json(STATE / "document_synthesis_queue.json", {"queue": [], "history": []})
    series = load_json(STATE / "company_financial_series.json", {"tickers": {}})
    graph = load_json(STATE / "company_intel" / "company_graph.json", {"nodes": [], "edges": []})
    cursor = load_json(CURSOR_PATH, {})
    print("ci_backfill status")
    print(f" official PSX metadata: {sum(1 for d in (research.get('documents') or {}).values() if d.get('source') == 'PSX DPS')}")
    print(f" extracted documents: {sum(1 for d in (docs.get('documents') or {}).values() if d.get('status') == 'ready')}")
    print(f" synthesis queue pending: {len(queue.get('queue') or [])}")
    print(f" financial-series tickers: {len(series.get('tickers') or {})}")
    print(f" graph: {len(graph.get('nodes') or [])} nodes / {len(graph.get('edges') or [])} edges")
    print(f" cursor next_index: {cursor.get('next_index', 0)} completed_batches: {cursor.get('completed_batches', 0)}")


def _run(script: str, *args: str, dry_run: bool = False) -> int:
    cmd = [sys.executable, f"scripts/{script}", *args]
    print(" ".join(cmd))
    if dry_run:
        return 0
    completed = subprocess.run(cmd)
    return completed.returncode


def _cursor(symbols: list[str], reset: bool) -> dict:
    if reset:
        return {"schema_version": 1, "symbols": symbols, "next_index": 0, "completed_batches": 0, "receipts": []}
    prior = load_json(CURSOR_PATH, {"schema_version": 1, "next_index": 0, "completed_batches": 0, "receipts": []})
    prior_symbols = prior.get("symbols") or []
    if prior_symbols and prior_symbols != symbols:
        return {"schema_version": 1, "next_index": 0, "completed_batches": 0, "receipts": [],
                "reset_reason": "pilot symbol list changed"}
    return {**prior, "schema_version": 1, "symbols": symbols}


def _write_cursor(cursor: dict, batch: list[str]) -> dict:
    now = time.strftime("%Y-%m-%d %H:%M")
    receipts = list(cursor.get("receipts") or [])
    receipts.append({"completed_at": now, "symbols": batch})
    cursor = {
        **cursor,
        "next_index": int(cursor.get("next_index") or 0) + len(batch),
        "completed_batches": int(cursor.get("completed_batches") or 0) + 1,
        "last_completed_at": now,
        "receipts": receipts[-40:],
    }
    save_json(CURSOR_PATH, cursor)
    return cursor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="print current corpus counts")
    parser.add_argument("--dry-run", action="store_true", help="show commands without running them")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--batches", type=int, default=1, help="number of bounded batches to run")
    parser.add_argument("--start", type=int, help="zero-based pilot start offset; overrides cursor for this run")
    parser.add_argument("--reset-cursor", action="store_true", help="restart the durable manual backfill cursor")
    parser.add_argument("--issuer-sources", action="store_true", help="also refresh issuer source registry")
    parser.add_argument("--metadata-only", action="store_true", help="skip PDF downloads for metadata-only proof runs")
    parser.add_argument("--preflight", action="store_true", help="run the full publish preflight after successful batches")
    args = parser.parse_args(argv)

    if args.status:
        _status()
        return 0
    if args.batch_size < 1 or args.batches < 1 or (args.start is not None and args.start < 0):
        parser.error("batch-size/batches must be positive and start must be zero or greater")

    symbols = _pilot_symbols()
    if not symbols:
        print("ci_backfill: no CI pilot symbols")
        return 0

    failures: list[str] = []
    completed: list[list[str]] = []
    cursor = _cursor(symbols, args.reset_cursor)
    start_index = args.start if args.start is not None else int(cursor.get("next_index") or 0)
    if start_index >= len(symbols):
        start_index = 0
        cursor = {**cursor, "next_index": 0}

    for batch_no in range(args.batches):
        start = start_index + batch_no * args.batch_size
        batch = symbols[start:start + args.batch_size]
        if not batch:
            break
        symbol_arg = ",".join(batch)
        print(f"ci_backfill batch {batch_no + 1}: {', '.join(batch)}")
        fetch_args = ["--force", "--symbols", symbol_arg]
        if args.metadata_only:
            fetch_args.append("--metadata-only")
        for script, script_args in (
            ("fetch_company_documents.py", fetch_args),
            ("document_intelligence.py", []),
            ("build_financial_series.py", []),
        ):
            rc = _run(script, *script_args, dry_run=args.dry_run)
            if rc != 0:
                failures.append(script)
                break
        if args.issuer_sources and not failures:
            rc = _run("fetch_issuer_sources.py", "--force", "--symbols", symbol_arg, dry_run=args.dry_run)
            if rc != 0:
                failures.append("fetch_issuer_sources.py")
        if not failures:
            for script in ("build_source_qa.py", "build_company_graph.py", "build_ci_slice.py"):
                rc = _run(script, dry_run=args.dry_run)
                if rc != 0:
                    failures.append(script)
                    break
        if not failures:
            completed.append(batch)
        if failures:
            break
        time.sleep(1.0)

    if args.preflight and not failures:
        rc = _run("preflight.py", dry_run=args.dry_run)
        if rc != 0:
            failures.append("preflight.py")

    if not failures and not args.dry_run and args.start is None:
        for batch in completed:
            cursor = _write_cursor(cursor, batch)

    _status()
    if failures:
        print(f"ci_backfill: failed at {failures[0]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
