"""One-time backfill step: merges the 21 out_*_batch_*.json Haiku-extraction outputs
(.firecrawl/batches/out_text_batch_NN.json, out_image_batch_NN.json) into one unified
structured dataset. Ad-hoc, not part of cycle pipeline.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = ROOT / ".firecrawl" / "batches"
OUT_PATH = ROOT / ".firecrawl" / "insider-structured.json"


def main():
    manifest = json.loads((BATCH_DIR / "manifest.json").read_text(encoding="utf-8"))
    all_rows = []
    missing = []
    for fname in manifest["text_batches"] + manifest["image_batches"]:
        out_fname = "out_" + fname
        out_path = BATCH_DIR / out_fname
        if not out_path.exists():
            missing.append(out_fname)
            continue
        rows = json.loads(out_path.read_text(encoding="utf-8-sig"))
        source = "text" if fname.startswith("text_") else "image"
        for r in rows:
            r["source"] = source
        all_rows.extend(rows)

    print(f"merged {len(all_rows)} rows from {len(manifest['text_batches']) + len(manifest['image_batches']) - len(missing)} batch files")
    if missing:
        print(f"MISSING output files: {missing}")

    OUT_PATH.write_text(json.dumps({"count": len(all_rows), "rows": all_rows}, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
