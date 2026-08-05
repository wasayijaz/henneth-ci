"""One-time backfill step: downloads each insider-disclosure PDF listed in
.firecrawl/insider-filtered.json (rows with a non-null pdf_url) and extracts raw text via pymupdf.
Writes .firecrawl/insider-pdf-text.json -- one entry per row, `text: str|None`, `error: str|None`.
No field parsing here (that's the next stage, Haiku fan-out) -- this step only gets raw text out of
the PDF, honestly, per CLAUDE.md Rule 2 (a failed fetch/parse is a null, never guessed).
Ad-hoc script, not part of the cycle pipeline.
"""
import json
import time
from pathlib import Path

import fitz  # pymupdf
import requests

ROOT = Path(__file__).resolve().parent.parent
FC = ROOT / ".firecrawl"
IN_PATH = FC / "insider-filtered.json"
OUT_PATH = FC / "insider-pdf-text.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Henneth-Desk/1.0"}
TIMEOUT = 30


def fetch_and_extract(url: str) -> tuple[str | None, str | None]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        with fitz.open(stream=resp.content, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)
        text = text.strip()
        if not text:
            return None, "empty_text"
        return text, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    data = json.loads(IN_PATH.read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r.get("pdf_url")]
    print(f"rows with pdf_url: {len(rows)}")

    out_rows = []
    ok = 0
    failed = 0
    for i, row in enumerate(rows, 1):
        text, err = fetch_and_extract(row["pdf_url"])
        out_rows.append({
            "symbol": row["symbol"],
            "date": row["date"],
            "time": row.get("time"),
            "title": row["title"],
            "pdf_url": row["pdf_url"],
            "text": text,
            "error": err,
        })
        if text:
            ok += 1
        else:
            failed += 1
        if i % 20 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)} (ok={ok} failed={failed})")
        time.sleep(0.2)  # be polite to dps.psx.com.pk

    print(f"done: ok={ok} failed={failed}")
    OUT_PATH.write_text(json.dumps({"count": len(out_rows), "rows": out_rows}, indent=2),
                         encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
