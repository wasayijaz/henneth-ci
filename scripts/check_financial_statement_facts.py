#!/usr/bin/env python3
"""Offline regression checks for the conservative financial statement parser."""
from __future__ import annotations

import sys

from financial_statement_facts import detect_scale_info, extract_facts


def _w(x0: float, y0: float, text: str, block: int, line: int, word: int = 0):
    width = max(8.0, float(len(text) * 5.0))
    return (x0, y0, x0 + width, y0 + 10.0, text, block, line, word)


def main() -> int:
    assert detect_scale_info("(PKR in �000�)") == (1_000, [])
    words = [
        _w(50, 40, "Consolidated", 0, 0), _w(120, 40, "Statement", 0, 0, 1),
        _w(190, 40, "of", 0, 0, 2), _w(210, 40, "Profit", 0, 0, 3),
        _w(260, 40, "or", 0, 0, 4), _w(280, 40, "Loss", 0, 0, 5),
        _w(50, 70, "For", 0, 1), _w(75, 70, "the", 0, 1, 1),
        _w(105, 70, "year", 0, 1, 2), _w(140, 70, "ended", 0, 1, 3),
        _w(180, 70, "June", 0, 1, 4), _w(220, 70, "30,", 0, 1, 5),
        _w(245, 70, "2024", 0, 1, 6),
        _w(410, 110, "2024", 1, 0), _w(500, 110, "2023", 1, 1),
        _w(350, 130, "Note", 1, 2), _w(420, 130, "(PKR", 1, 2, 1), _w(450, 130, "in", 1, 2, 2),
        _w(465, 130, "�000�)", 1, 2, 2),
        _w(50, 160, "Revenue", 2, 0), _w(350, 160, "31.1", 3, 0),
        _w(410, 160, "100", 4, 0), _w(500, 160, "90", 5, 0),
        _w(50, 180, "Cost", 6, 0), _w(80, 180, "of", 6, 0, 1),
        _w(100, 180, "sales", 6, 0, 2), _w(410, 180, "60", 7, 0),
        _w(500, 180, "55", 8, 0),
        _w(50, 200, "Gross", 9, 0), _w(85, 200, "profit", 9, 0, 1),
        _w(410, 200, "40", 10, 0), _w(500, 200, "35", 11, 0),
    ]
    page = "Consolidated Statement of Profit or Loss For the year ended June 30, 2024"
    facts = extract_facts(
        {"doc_id": "fixture", "title": "Annual Report 2024", "source_url": "https://example.test/a.pdf",
         "content_sha256": "fixture", "published_at": "2024-08-01"},
        [page], [words], [{"page": 1, "text": page, "words": words}],
    )
    assert facts, "geometry fixture emitted no facts"
    actual = {(f["line"], f["period_end"], f["consolidation"], f["scale"], f["duration_months"])
            for f in facts}
    assert actual == {
                ("revenue", "2024-06-30", "consolidated", 1_000, 12),
                ("revenue", "2023-06-30", "consolidated", 1_000, 12),
                ("gross_profit", "2024-06-30", "consolidated", 1_000, 12),
                ("gross_profit", "2023-06-30", "consolidated", 1_000, 12),
            }
    assert all(f["readiness"] == "model_loadable" and f["currency"] == "PKR" for f in facts)
    assert all("cost of sales" not in f["reported_label"].lower() for f in facts)
    print("financial statement facts self-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
