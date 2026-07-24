#!/usr/bin/env python3
"""Desk Room — merge a finished batch into state/rooms.json.

The personas return/write JSON per ticker; THIS is the only writer of rooms.json, so a
persona can never clobber a sibling ticker's session and a half-finished batch can never
be published as if complete.

Reads state/room_staging/<SYM>.{ta,fa,debate}.json and merges. A ticker missing its
`debate` file (the final stage) is SKIPPED (not partially written) — a session without
the debate would render as covered while showing nothing.

Per docs/PUBLICATION_RESTRUCTURE_V2.md §3 the Chair stage is gone: no house view,
conviction, direction, target, or dated per-ticker claims are published (SECP Reg 2(ha),
S.R.O.7(I)/2026 — a published call on a NAMED security is a licensed research service the
desk cannot offer). The Room ends at the bull/bear debate (general commentary, Reg 2(h)),
so this assembler no longer reads a chair file and no longer writes to state/claims.json.

Usage: python scripts/room_assemble.py [--keep]      (--keep leaves staging in place)
"""
import html
import json
import shutil
import sys
import time

from psx_data import STATE, load_json, save_json

STAGE = STATE / "room_staging"
ROLES = ("ta", "fa", "debate")


def unescape(o):
    """Personas emit prose inside JSON; some come back HTML-escaped ("Power Generation
    &amp; Distribution"). Fix at the boundary — the dashboard escapes on render, so
    storing pre-escaped text double-escapes it in the UI."""
    if isinstance(o, str):
        return html.unescape(o)
    if isinstance(o, list):
        return [unescape(x) for x in o]
    if isinstance(o, dict):
        return {k: unescape(v) for k, v in o.items()}
    return o


def _unwrap(d, *keys):
    """Agents sometimes wrap their payload ({"ta_memo": {...}}) and sometimes return it
    bare. Accept both rather than making the prompt carry the whole burden."""
    if not isinstance(d, dict):
        return d
    for k in keys:
        if k in d and isinstance(d[k], dict):
            return d[k]
    return d


def main():
    if not STAGE.exists():
        print("no state/room_staging — run scripts/room_batch.py first")
        sys.exit(1)

    batch = load_json(STAGE / "_batch.json", {}).get("tickers", [])
    dossiers = load_json(STATE / "dossiers.json", {})
    rooms = load_json(STATE / "rooms.json", {})

    today = time.strftime("%Y-%m-%d %H:%M")
    wrote, skipped = [], []

    for sym in batch:
        files = {r: STAGE / f"{sym}.{r}.json" for r in ROLES}
        # debate is the final stage now (no Chair) — its absence means the session is
        # incomplete, so skip rather than publish a partial room.
        if not files["debate"].exists():
            skipped.append(sym)
            continue
        ta = _unwrap(load_json(files["ta"], {}), "ta_memo")
        fa = _unwrap(load_json(files["fa"], {}), "fa_memo")
        deb = load_json(files["debate"], {})
        d = dossiers.get(sym) or {}

        rooms[sym] = unescape({
            "built": today,
            "dossier_asof": d.get("asof"),
            # material_hash + price_at_session are what room_gate reads to price the NEXT
            # cycle: unchanged material -> free reaffirm, >4% move -> cheap TA-only delta.
            # Omit them and every ticker re-runs a full debate forever.
            "price_at_session": d.get("price"),
            "material_hash": d.get("material_hash"),
            "ta_memo": ta or None,
            "fa_memo": fa or None,
            "bull_case": deb.get("bull_case"),
            "bear_case": deb.get("bear_case"),
            "reaffirmed": False,
        })
        wrote.append(sym)

    if not wrote:
        print("nothing assembled — no debate outputs found. rooms.json untouched.")
        sys.exit(1)

    rooms["_meta"] = {**rooms.get("_meta", {}), "updated": today,
                      "covered": len([k for k in rooms if k != "_meta"])}
    save_json(STATE / "rooms.json", rooms)

    print(f"rooms: +{len(wrote)} sessions -> {rooms['_meta']['covered']} covered")
    print(f"  {', '.join(wrote)}")
    if skipped:
        print(f"  SKIPPED {len(skipped)} with no debate output (not partially written): {', '.join(skipped)}")

    if "--keep" not in sys.argv:
        shutil.rmtree(STAGE)
        print("staging cleared")


if __name__ == "__main__":
    main()
