#!/usr/bin/env python3
"""Merge state-translator output back into the source state file.

Counterpart to translate_extract.py. Reads:
  state/translate_batch.json      {"file": ..., "items": {path: english}}
  state/translate_batch_ur.json   {path: urdu}     (written by the translator agent)

Writes `<field>_ur` + `<field>_ur_hash` siblings into the source file. For plain
string arrays (paths like risks[0], risks[1]) it assembles the parallel
`<name>_ur` array plus one `<name>_ur_hash` over the joined English array.

English fields are never touched. Paths in the Urdu file that aren't in the
batch are ignored (translator can't add fields). Temp files deleted on success.

Usage: python scripts/translate_merge.py [--keep]
"""
import hashlib
import re
import sys

from psx_data import ROOT, STATE, load_json, save_json

BATCH = STATE / "translate_batch.json"
BATCH_UR = STATE / "translate_batch_ur.json"


def h12(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def resolve(data, path_parts):
    """Walk to the parent container of the final segment. Returns (parent, key)."""
    node = data
    for part in path_parts[:-1]:
        for key, idx in re.findall(r"([^\[\]]+)|\[(\d+)\]", part):
            if key:
                node = node[key]
            else:
                node = node[int(idx)]
    last = path_parts[-1]
    m = re.match(r"^(.+?)((?:\[\d+\])+)$", last)
    if m:
        node = node[m.group(1)]
        idxs = [int(i) for i in re.findall(r"\[(\d+)\]", m.group(2))]
        for i in idxs[:-1]:
            node = node[i]
        return node, idxs[-1]
    return node, last


def load_bom_tolerant(path):
    import json
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    batch = load_bom_tolerant(BATCH)
    ur = load_bom_tolerant(BATCH_UR)
    if not batch or not ur:
        print("translate_merge: batch or urdu file missing — nothing to merge")
        sys.exit(0)

    src = ROOT / batch["file"]
    data = load_json(src, None)
    if data is None:
        print(f"translate_merge: source {batch['file']} missing")
        sys.exit(1)

    merged, warned = 0, 0
    array_groups = {}  # arr_path -> {index: urdu}

    for path, english in batch["items"].items():
        urdu = ur.get(path)
        if not isinstance(urdu, str) or not urdu.strip():
            warned += 1
            continue
        m = re.match(r"^(.*?)\[(\d+)\]$", path)
        is_scalar_field = False
        if m:
            # could be a plain-string-array element OR an object field ending in index
            try:
                parent, key = resolve(data, path.split("."))
                container = parent
                is_scalar_field = not isinstance(container, list)
            except (KeyError, IndexError, TypeError):
                warned += 1
                continue
            if not is_scalar_field:
                array_groups.setdefault(m.group(1), {})[int(m.group(2))] = urdu
                continue
        try:
            parent, key = resolve(data, path.split("."))
        except (KeyError, IndexError, TypeError):
            warned += 1
            continue
        if not isinstance(parent, dict) or key not in parent:
            warned += 1
            continue
        parent[f"{key}_ur"] = urdu
        parent[f"{key}_ur_hash"] = h12(batch["items"][path])
        merged += 1

    for arr_path, idx_map in array_groups.items():
        try:
            parent, leaf = resolve(data, arr_path.split("."))
        except (KeyError, IndexError, TypeError):
            warned += len(idx_map)
            continue
        arr = parent.get(leaf) if isinstance(parent, dict) else None
        if not isinstance(arr, list):
            warned += len(idx_map)
            continue
        existing = parent.get(f"{leaf}_ur")
        ur_arr = list(existing) if isinstance(existing, list) and len(existing) == len(arr) \
            else [None] * len(arr)
        for i, urdu in idx_map.items():
            if i < len(ur_arr):
                ur_arr[i] = urdu
                merged += 1
        parent[f"{leaf}_ur"] = ur_arr
        complete = all(isinstance(u, str) and u.strip()
                       for u, s in zip(ur_arr, arr) if isinstance(s, str) and s.strip())
        if complete:
            parent[f"{leaf}_ur_hash"] = h12("\n".join(s for s in arr if isinstance(s, str)))
        else:
            parent.pop(f"{leaf}_ur_hash", None)

    save_json(src, data)
    print(f"translate_merge: +{merged} urdu fields into {batch['file']}"
          + (f" ({warned} skipped)" if warned else ""))

    if "--keep" not in sys.argv:
        BATCH.unlink(missing_ok=True)
        BATCH_UR.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
