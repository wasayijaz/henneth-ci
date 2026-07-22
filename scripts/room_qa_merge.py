#!/usr/bin/env python3
"""Desk Room — merge room-verifier QA verdicts into state/rooms.json[SYM].qa.

Mirrors room_assemble.py's single-writer pattern: the room-verifier agent writes its
verdict to state/room_staging/<SYM>.qa.json; this script is the only thing that folds
those into rooms.json, so a verifier run can never race the next room_assemble.py batch.

Usage: python scripts/room_qa_merge.py [--keep]      (--keep leaves staging in place)
"""
import sys
import time

from psx_data import STATE, load_json, save_json

STAGE = STATE / "room_staging"


def main():
    if not STAGE.exists():
        print("no state/room_staging — nothing to merge")
        sys.exit(1)

    rooms = load_json(STATE / "rooms.json", {})
    files = sorted(STAGE.glob("*.qa.json"))
    if not files:
        print("no *.qa.json in room_staging — nothing to merge")
        sys.exit(1)

    today = time.strftime("%Y-%m-%d %H:%M")
    merged, skipped = [], []
    for f in files:
        sym = f.name.split(".")[0]
        if sym not in rooms:
            skipped.append(sym)
            continue
        qa = load_json(f, {})
        rooms[sym]["qa"] = {**qa, "checked": today}
        merged.append(sym)

    if merged:
        save_json(STATE / "rooms.json", rooms)

    print(f"qa: +{len(merged)} verdicts merged")
    if merged:
        print(f"  {', '.join(merged)}")
    if skipped:
        print(f"  SKIPPED {len(skipped)} (no room session in rooms.json): {', '.join(skipped)}")

    if "--keep" not in sys.argv:
        for f in files:
            f.unlink()
        print("qa staging cleared")


if __name__ == "__main__":
    main()
