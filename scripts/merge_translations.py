#!/usr/bin/env python3
"""Desk Room — merge state-translator Urdu output into state/rooms.json.

The state-translator agent has Read/Write only (no Edit/Bash) so it cannot safely
rewrite the large shared rooms.json itself. It writes state/room_tmp_<SYM>_fields.json
(English, for its own reference) + state/room_tmp_<SYM>_fields_ur.json (Urdu, dotted-key
-> translated string). THIS script is the only thing that folds the _ur strings into
rooms.json[SYM] as "<field>_ur" siblings, mirroring room_assemble.py's single-writer
pattern. Replaces hand-typing each field via Edit, which was the token-heavy step.

Usage: python scripts/merge_translations.py [--keep]      (--keep leaves tmp files in place)
"""
import sys

from psx_data import STATE, load_json, save_json


def main():
    ur_files = sorted(STATE.glob("room_tmp_*_fields_ur.json"))
    if not ur_files:
        print("no state/room_tmp_*_fields_ur.json — nothing to merge")
        sys.exit(1)

    rooms = load_json(STATE / "rooms.json", {})
    merged, skipped = [], []

    for f in ur_files:
        sym = f.name[len("room_tmp_"):-len("_fields_ur.json")]
        if sym not in rooms:
            skipped.append((sym, "no room session in rooms.json"))
            continue

        ur = load_json(f, {})
        room = rooms[sym]
        n = 0
        for dotted_key, text in ur.items():
            *path, leaf = dotted_key.split(".")
            node = room
            ok = True
            for p in path:
                if not isinstance(node, dict) or p not in node:
                    ok = False
                    break
                node = node[p]
            if not ok or not isinstance(node, dict) or leaf not in node:
                print(f"  WARN {sym}: path '{dotted_key}' not found in rooms.json, skipped")
                continue
            node[f"{leaf}_ur"] = text
            n += 1

        merged.append((sym, n))

    if merged:
        save_json(STATE / "rooms.json", rooms)

    print(f"translations: +{sum(n for _, n in merged)} fields across {len(merged)} tickers")
    for sym, n in merged:
        print(f"  {sym}: {n} fields")
    if skipped:
        print(f"  SKIPPED {len(skipped)}: {', '.join(f'{s} ({r})' for s, r in skipped)}")

    if "--keep" not in sys.argv and merged:
        for sym, _ in merged:
            (STATE / f"room_tmp_{sym}_fields.json").unlink(missing_ok=True)
            (STATE / f"room_tmp_{sym}_fields_ur.json").unlink(missing_ok=True)
        print("tmp files cleared")


if __name__ == "__main__":
    main()
