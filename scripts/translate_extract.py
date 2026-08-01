#!/usr/bin/env python3
"""Extract untranslated English fields from a state file into a tiny batch file.

Token-efficiency layer for the state-translator agent. The hash check (skip
already-translated, unchanged fields) happens HERE, deterministically and for
free — the LLM only ever sees strings that genuinely need translating, and only
those strings. It never reads the source JSON, existing Urdu, or structure.

Usage:
  python scripts/translate_extract.py <state-file> <pattern> [<pattern> ...]

Patterns are dotted paths into the JSON. Two wildcards:
  []   every element of an array        e.g. drivers[]  risks[]  sectors[].why
  *    every key of a dict at that level e.g. *.ta_memo.read (all room symbols)

Output: state/translate_batch.json
  {"file": "<source path>", "items": {"<concrete dotted path>": "<english>", ...}}

A field is included only if its `_ur` sibling is missing OR `_ur_hash` no longer
matches the English (source changed since last translation).

Optional flag: --max N  keeps only the LAST N extracted fields PER PATTERN
(arrays are appended chronologically in this repo, so "last" = newest). Use on
append-only logs (newslog.json) to avoid backfilling the whole history.

Exit code 0 always (safe in pipelines). Prints the item count; "0 fields" means
the orchestrator can skip the translator agent entirely — no LLM call.
"""
import hashlib
import re
import sys

from psx_data import ROOT, STATE, load_json, save_json

BATCH = STATE / "translate_batch.json"


def h12(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def split_pattern(pattern: str) -> list[str]:
    """'sectors[].why' -> ['sectors', '[]', 'why']; '*.ta_memo.read' -> ['*', 'ta_memo', 'read']"""
    parts = []
    for seg in pattern.split("."):
        if seg.endswith("[]"):
            parts.extend([seg[:-2], "[]"])
        else:
            parts.append(seg)
    return [p for p in parts if p]


def walk(node, parts, path, out):
    """Collect (concrete_path, parent_dict_or_list, leaf_key) for every match."""
    if not parts:
        return
    seg, rest = parts[0], parts[1:]

    if seg == "[]":
        if isinstance(node, list):
            for i, el in enumerate(node):
                p = f"{path}[{i}]"
                if rest:
                    walk(el, rest, p, out)
                else:
                    out.append((p, node, i))
        return

    if seg == "*":
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{path}.{k}" if path else k
                if rest:
                    walk(v, rest, p, out)
                else:
                    out.append((p, node, k))
        return

    if isinstance(node, dict) and seg in node:
        p = f"{path}.{seg}" if path else seg
        if rest:
            walk(node[seg], rest, p, out)
        else:
            out.append((p, node, seg))


def needs_translation(parent, key) -> str | None:
    """Return the English string if this field needs (re)translation, else None."""
    val = parent[key]
    if isinstance(key, int):
        # bare string inside a plain string array — parent is the list itself;
        # per-element _ur siblings are impossible, handled at array level by caller
        return None
    if not isinstance(val, str) or not val.strip():
        return None
    ur, urh = parent.get(f"{key}_ur"), parent.get(f"{key}_ur_hash")
    if isinstance(ur, str) and ur.strip() and urh == h12(val):
        return None
    return val


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)

    argv = sys.argv[1:]
    max_items = None
    if "--max" in argv:
        i = argv.index("--max")
        max_items = int(argv[i + 1])
        del argv[i:i + 2]

    src = ROOT / argv[0]
    patterns = argv[1:]
    data = load_json(src, None)
    if data is None:
        print(f"translate_extract: {argv[0]} not found — 0 fields")
        BATCH.unlink(missing_ok=True)
        sys.exit(0)

    items = {}
    for pattern in patterns:
        pat_items = {}
        matches = []
        walk(data, split_pattern(pattern), "", matches)
        # plain string arrays (e.g. risks[]): translate whole array as one unit
        array_units = {}
        for path, parent, key in matches:
            if isinstance(key, int):
                m = re.match(r"^(.*)\[\d+\]$", path)
                array_units.setdefault(m.group(1), parent)
                continue
            eng = needs_translation(parent, key)
            if eng is not None:
                pat_items[path] = eng
        for arr_path, arr in array_units.items():
            # find the array's parent dict to check the <name>_ur sibling
            *ppath, leaf = re.split(r"\.", arr_path)
            node = data
            for p in ppath:
                m = re.match(r"^(.+)\[(\d+)\]$", p)
                node = node[m.group(1)][int(m.group(2))] if m else node[p]
            joined = "\n".join(s for s in arr if isinstance(s, str))
            ur, urh = node.get(f"{leaf}_ur"), node.get(f"{leaf}_ur_hash")
            if (isinstance(ur, list) and len(ur) == len(arr) and urh == h12(joined)
                    and all(isinstance(x, str) and x.strip() for x in ur)):
                continue
            for i, s in enumerate(arr):
                if isinstance(s, str) and s.strip():
                    pat_items[f"{arr_path}[{i}]"] = s
        # --max caps each pattern to its LAST N fields (newest, arrays append-only)
        if max_items is not None and len(pat_items) > max_items:
            pat_items = dict(list(pat_items.items())[-max_items:])
        items.update(pat_items)

    if not items:
        print("translate_extract: 0 fields — skip translator, no LLM call needed")
        BATCH.unlink(missing_ok=True)
        sys.exit(0)

    save_json(BATCH, {"file": argv[0], "items": items})
    print(f"translate_extract: {len(items)} fields -> state/translate_batch.json")


if __name__ == "__main__":
    main()
