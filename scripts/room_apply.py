#!/usr/bin/env python3
"""Desk Room — deterministic session assembler (zero tokens).

The automated task spawns the persona agents, writes each one's returned JSON to a
temp file, then calls this to assemble the session. Doing the file-wrangling here
(not in the LLM task) keeps the token cost to just the agents' reasoning.

Usage:
  python scripts/room_apply.py SYM               # assemble a FULL session
  python scripts/room_apply.py SYM --reaffirm    # material unchanged: just re-stamp
  python scripts/room_apply.py SYM --delta       # price-only refresh: update ta_memo + stamp

Temp inputs (written by the task from agent outputs), all under state/room_tmp/:
  {SYM}.ta.json     -> ta_memo object            (Meher)
  {SYM}.fa.json     -> fa_memo object            (Dr. Omar)
  {SYM}.debate.json -> {bull_case, bear_case}    (the Debate, FINAL stage)
For --delta only {SYM}.ta.json is required.

Per docs/PUBLICATION_RESTRUCTURE_V2.md §3 the Chair stage is gone: no house view,
conviction, direction, target, or dated per-ticker claims (SECP Reg 2(ha),
S.R.O.7(I)/2026). The Room ends at the bull/bear debate (Reg 2(h) commentary), so this
script no longer reads a chair file and no longer writes to state/claims.json.
"""
import json
import sys
import time
from pathlib import Path

from psx_data import STATE, load_json, save_json

TMP = STATE / "room_tmp"


def _load_tmp(sym, slot):
    p = TMP / f"{sym}.{slot}.json"
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8").strip()
    # tolerate agents that wrap JSON in ```json fences
    if txt.startswith("```"):
        txt = txt.split("```", 2)[1].lstrip("json").strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        print(f"  ! {sym}.{slot}.json unparseable: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("usage: room_apply.py SYM [--reaffirm|--delta]")
        sys.exit(2)
    sym = sys.argv[1].upper()
    mode = sys.argv[2] if len(sys.argv) > 2 else "--full"

    dossiers = load_json(STATE / "dossiers.json", {})
    d = dossiers.get(sym)
    if not d:
        print(f"  ! no dossier for {sym}")
        sys.exit(1)
    rooms = load_json(STATE / "rooms.json", {})
    now = time.strftime("%Y-%m-%d %H:%M")

    if mode == "--reaffirm":
        # ta_memo is present in every real session (full or delta); it's the marker that
        # there is something to reaffirm now that there's no house_view to key off.
        if sym in rooms and rooms[sym].get("ta_memo"):
            rooms[sym]["reaffirmed"] = now
            rooms[sym]["material_hash"] = d.get("material_hash")
            print(f"  {sym}: reaffirmed (no material change) — free")
        else:
            print(f"  ! {sym}: nothing to reaffirm")
            sys.exit(1)
        save_json(STATE / "rooms.json", rooms)
        return

    if mode == "--delta":
        ta = _load_tmp(sym, "ta")
        if not ta or sym not in rooms:
            print(f"  ! {sym}: delta needs an existing session + fresh ta.json")
            sys.exit(1)
        rooms[sym]["ta_memo"] = ta
        rooms[sym]["price_at_session"] = d.get("price")
        rooms[sym]["material_hash"] = d.get("material_hash")
        rooms[sym]["delta_updated"] = now
        save_json(STATE / "rooms.json", rooms)
        print(f"  {sym}: TA delta applied (~cheap)")
        return

    # --- FULL session ---
    ta, fa = _load_tmp(sym, "ta"), _load_tmp(sym, "fa")
    debate = _load_tmp(sym, "debate")
    missing = [n for n, v in [("ta", ta), ("fa", fa), ("debate", debate)] if not v]
    if missing:
        print(f"  ! {sym}: missing/invalid slots {missing} — session NOT written")
        sys.exit(1)

    rooms[sym] = {
        "built": now,
        "dossier_asof": d.get("asof"),
        "price_at_session": d.get("price"),
        "material_hash": d.get("material_hash"),
        "ta_memo": ta,
        "fa_memo": fa,
        "bull_case": debate.get("bull_case"),
        "bear_case": debate.get("bear_case"),
    }
    rooms["_meta"] = {"built": now, "sessions": len([k for k in rooms if k != "_meta"]),
                      "note": "Desk Room sessions per ticker; rendered on the ticker page."}
    save_json(STATE / "rooms.json", rooms)

    # tidy temp files for this ticker
    for slot in ("ta", "fa", "debate"):
        (TMP / f"{sym}.{slot}.json").unlink(missing_ok=True)
    print(f"  {sym}: FULL session written (debate is the final stage; no Chair verdict)")


if __name__ == "__main__":
    main()
