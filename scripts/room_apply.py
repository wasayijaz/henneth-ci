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
  {SYM}.debate.json -> {bull_case, bear_case}    (the Debate)
  {SYM}.chair.json  -> {house_view, claims_made} (the Chair)
For --delta only {SYM}.ta.json is required.
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
        if sym in rooms and rooms[sym].get("house_view"):
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
    debate, chair = _load_tmp(sym, "debate"), _load_tmp(sym, "chair")
    missing = [n for n, v in [("ta", ta), ("fa", fa), ("debate", debate), ("chair", chair)] if not v]
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
        "house_view": chair.get("house_view"),
    }
    rooms["_meta"] = {"built": now, "sessions": len([k for k in rooms if k != "_meta"]),
                      "note": "Desk Room sessions per ticker; rendered on the ticker page."}
    save_json(STATE / "rooms.json", rooms)

    # append the Chair's dated calls to the ledger (replace this ticker's prior pending calls)
    new_claims = chair.get("claims_made") or []
    if new_claims:
        led = load_json(STATE / "claims.json", {"claims": []})
        led["claims"] = [c for c in led.get("claims", []) if c.get("ticker") != sym] + new_claims
        save_json(STATE / "claims.json", led)

    # tidy temp files for this ticker
    for slot in ("ta", "fa", "debate", "chair"):
        (TMP / f"{sym}.{slot}.json").unlink(missing_ok=True)
    print(f"  {sym}: FULL session written ({len(new_claims)} dated calls appended)")


if __name__ == "__main__":
    main()
