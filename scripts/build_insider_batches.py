"""One-time backfill step: splits the 80 text-extracted and 132 image-rendered insider-disclosure
rows into small batch files for the Haiku parallel fan-out (field extraction). Ad-hoc, not part of
the cycle pipeline.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FC = ROOT / ".firecrawl"
BATCH_DIR = FC / "batches"
BATCH_DIR.mkdir(exist_ok=True)

TEXT_BATCH_SIZE = 20
IMAGE_BATCH_SIZE = 8


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main():
    text_data = json.loads((FC / "insider-pdf-text.json").read_text(encoding="utf-8"))
    text_rows = [r for r in text_data["rows"] if r.get("text")]
    print(f"text rows: {len(text_rows)}")

    image_data = json.loads((FC / "insider-pdf-images.json").read_text(encoding="utf-8"))
    image_rows = [r for r in image_data["rows"] if r.get("image_paths")]
    print(f"image rows: {len(image_rows)}")

    manifest = {"text_batches": [], "image_batches": []}

    for i, batch in enumerate(chunks(text_rows, TEXT_BATCH_SIZE)):
        fname = f"text_batch_{i:02d}.json"
        (BATCH_DIR / fname).write_text(json.dumps(batch, indent=2), encoding="utf-8")
        manifest["text_batches"].append(fname)

    for i, batch in enumerate(chunks(image_rows, IMAGE_BATCH_SIZE)):
        fname = f"image_batch_{i:02d}.json"
        (BATCH_DIR / fname).write_text(json.dumps(batch, indent=2), encoding="utf-8")
        manifest["image_batches"].append(fname)

    (BATCH_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(manifest['text_batches'])} text batches, {len(manifest['image_batches'])} image batches")


if __name__ == "__main__":
    main()
