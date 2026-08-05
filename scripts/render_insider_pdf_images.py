"""One-time backfill step: for insider-disclosure PDFs that produced no extractable text
(scanned/image-only filings -- see .firecrawl/insider-pdf-text.json rows with error=="empty_text"),
re-fetch and render each page to a PNG so a vision-capable agent can read it directly. No OCR
engine is available on this machine or the cloud runner, so this replaces OCR: the image is fed
to a Haiku agent in the next stage instead of extracted text. Ad-hoc script, not part of the cycle
pipeline.
"""
import json
import re
import time
from pathlib import Path

import fitz  # pymupdf
import requests

ROOT = Path(__file__).resolve().parent.parent
FC = ROOT / ".firecrawl"
IN_PATH = FC / "insider-pdf-text.json"
IMG_DIR = FC / "insider-pdf-images"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Henneth-Desk/1.0"}
TIMEOUT = 30
ZOOM = 2.0  # 2x render for legibility


def safe_name(symbol: str, date: str, idx: int) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]", "_", f"{symbol}_{date}_{idx}")
    return s


def main():
    data = json.loads(IN_PATH.read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r.get("error") == "empty_text"]
    print(f"scanned rows to render: {len(rows)}")
    IMG_DIR.mkdir(exist_ok=True)

    out_rows = []
    ok = 0
    failed = 0
    for i, row in enumerate(rows, 1):
        try:
            resp = requests.get(row["pdf_url"], headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            with fitz.open(stream=resp.content, filetype="pdf") as doc:
                paths = []
                mat = fitz.Matrix(ZOOM, ZOOM)
                for pno, page in enumerate(doc):
                    pix = page.get_pixmap(matrix=mat)
                    fname = f"{safe_name(row['symbol'], row['date'], i)}_p{pno}.png"
                    fpath = IMG_DIR / fname
                    pix.save(str(fpath))
                    paths.append(str(fpath.relative_to(ROOT)))
            out_rows.append({
                "symbol": row["symbol"], "date": row["date"], "time": row.get("time"),
                "title": row["title"], "pdf_url": row["pdf_url"],
                "image_paths": paths, "error": None,
            })
            ok += 1
        except Exception as e:
            out_rows.append({
                "symbol": row["symbol"], "date": row["date"], "time": row.get("time"),
                "title": row["title"], "pdf_url": row["pdf_url"],
                "image_paths": [], "error": f"{type(e).__name__}: {e}",
            })
            failed += 1
        if i % 20 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)} (ok={ok} failed={failed})")
        time.sleep(0.2)

    out_path = FC / "insider-pdf-images.json"
    out_path.write_text(json.dumps({"count": len(out_rows), "rows": out_rows}, indent=2),
                         encoding="utf-8")
    print(f"done: ok={ok} failed={failed}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
