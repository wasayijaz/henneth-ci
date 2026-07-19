#!/usr/bin/env python3
"""Desk Room — batch prep (deterministic, zero tokens).

Splits the gate's run_full_now list into per-ticker dossier files under
state/room_staging/, so each Room agent reads ONE small file instead of the whole
dossiers.json, and writes its own output beside it.

Why this exists: the first coverage batch was orchestrated by hand — the orchestrator
pasted every agent's JSON back out into staging files itself. That put the entire
batch through the orchestrator's context, which is both the most expensive place to
put it and the thing that caps batch size. Agents have Write; they should use it.

Usage:
  python scripts/room_batch.py            # prep the gate's planned batch
  python scripts/room_batch.py 20         # prep the top 20 due, ignoring the daily cap
  python scripts/room_batch.py KEL PSO    # prep specific tickers
"""
import json
import shutil
import sys

from psx_data import STATE, load_json, save_json

STAGE = STATE / "room_staging"


def main():
    args = sys.argv[1:]
    dossiers = load_json(STATE / "dossiers.json", {})
    plan = load_json(STATE / "room_plan.json", {})
    meta = plan.get("_meta", {})

    if args and args[0].isdigit():
        n = int(args[0])
        due = [x["symbol"] for x in plan.get("full", [])]
        syms = due[:n]
    elif args:
        syms = [a.upper() for a in args]
    else:
        syms = meta.get("run_full_now", [])

    syms = [s for s in syms if s in dossiers]
    if not syms:
        print("nothing to prep (no planned FULLs, or none have a dossier)")
        return

    # a stale staging dir would let a previous batch's files be merged as if fresh
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True, exist_ok=True)

    for s in syms:
        save_json(STAGE / f"{s}.dossier.json", dossiers[s])

    save_json(STAGE / "_batch.json", {"tickers": syms, "n": len(syms)})
    print(f"staged {len(syms)} dossier(s) -> {STAGE}")
    print(" ".join(syms))
    print("\nAgents write to state/room_staging/<SYM>.<role>.json  (role: ta | fa | debate | chair)")


if __name__ == "__main__":
    main()
