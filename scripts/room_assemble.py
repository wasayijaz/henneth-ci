#!/usr/bin/env python3
"""Desk Room — merge a finished batch into state/rooms.json + state/claims.json.

The personas return/write JSON per ticker; THIS is the only writer of rooms.json, so a
persona can never clobber a sibling ticker's session and a half-finished batch can never
be published as if complete.

Reads state/room_staging/<SYM>.{ta,fa,debate,chair}.json and merges. A ticker missing its
chair file is SKIPPED (not partially written) — a session without a house view would render
as covered while showing nothing.

Usage: python scripts/room_assemble.py [--keep]      (--keep leaves staging in place)
"""
import html
import json
import shutil
import sys
import time

from psx_data import STATE, load_json, save_json

STAGE = STATE / "room_staging"
ROLES = ("ta", "fa", "debate", "chair")


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
    claims_doc = load_json(STATE / "claims.json", {})
    claims = claims_doc.get("claims", claims_doc if isinstance(claims_doc, list) else [])

    today = time.strftime("%Y-%m-%d %H:%M")
    wrote, skipped, added, empties = [], [], 0, []

    existing = {(c.get("ticker"), c.get("source"), c.get("made_on"), c.get("kind"))
                for c in claims}

    for sym in batch:
        files = {r: STAGE / f"{sym}.{r}.json" for r in ROLES}
        if not files["chair"].exists():
            skipped.append(sym)
            continue
        ta = _unwrap(load_json(files["ta"], {}), "ta_memo")
        fa = _unwrap(load_json(files["fa"], {}), "fa_memo")
        deb = load_json(files["debate"], {})
        chair = load_json(files["chair"], {})
        d = dossiers.get(sym) or {}

        rooms[sym] = unescape({
            "built": today,
            "dossier_asof": d.get("asof"),
            # material_hash + price_at_session are what room_gate reads to price the NEXT
            # cycle: unchanged material -> free reaffirm, >4% move -> cheap TA-only delta.
            # Omit them and every ticker re-runs a full 5-persona debate forever.
            "price_at_session": d.get("price"),
            "material_hash": d.get("material_hash"),
            "ta_memo": ta or None,
            "fa_memo": fa or None,
            "bull_case": deb.get("bull_case"),
            "bear_case": deb.get("bear_case"),
            "house_view": _unwrap(chair, "house_view") if "house_view" not in chair else chair["house_view"],
            "reaffirmed": False,
        })
        wrote.append(sym)

        for c in unescape(chair.get("claims_made") or []):
            # Drop empty claims. Where a persona honestly declined to call it (claim.text
            # null on a coin-flip setup), some Chairs still fold the shell into claims_made.
            # A claim asserting nothing can never be scored; filing it pads the scoreboard
            # denominator with rows that can only ever resolve as unresolvable.
            txt = (c.get("claim") or {}).get("text")
            if not txt or not str(txt).strip():
                empties.append(f"{c.get('ticker')}/{c.get('source')}")
                continue
            key = (c.get("ticker"), c.get("source"), c.get("made_on"), c.get("kind"))
            if key in existing:
                continue
            claims.append(c)
            existing.add(key)
            added += 1

    if not wrote:
        print("nothing assembled — no chair outputs found. rooms.json untouched.")
        sys.exit(1)

    rooms["_meta"] = {**rooms.get("_meta", {}), "updated": today,
                      "covered": len([k for k in rooms if k != "_meta"])}
    save_json(STATE / "rooms.json", rooms)

    if isinstance(claims_doc, dict):
        claims_doc["claims"] = claims
        claims_doc["updated"] = today
        save_json(STATE / "claims.json", claims_doc)
    else:
        save_json(STATE / "claims.json", claims)

    print(f"rooms: +{len(wrote)} sessions -> {rooms['_meta']['covered']} covered")
    print(f"  {', '.join(wrote)}")
    if skipped:
        print(f"  SKIPPED {len(skipped)} with no chair output (not partially written): {', '.join(skipped)}")
    print(f"claims: +{added} filed, {len(claims)} total")
    if empties:
        print(f"  skipped {len(empties)} empty claim(s) (persona declined to call it): {', '.join(empties)}")

    if "--keep" not in sys.argv:
        shutil.rmtree(STAGE)
        print("staging cleared")


if __name__ == "__main__":
    main()
