#!/usr/bin/env python3
"""Offline fixtures for exact historical PSX metadata seeding."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fetch_company_documents import seed_historical_metadata
from psx_data import STATE, save_json


def _write(path: Path, payload: dict) -> None:
    save_json(path, payload)


def _base_state(root: Path) -> tuple[Path, Path, Path]:
    state = root / "state"
    profiles = state / "company_profiles.json"
    universe = state / "universe.json"
    index = state / "research_index.json"
    _write(profiles, {
        "pilot": {"symbols": ["MLCF"]},
        "tickers": {
            "MLCF": {
                "symbol": "MLCF",
                "source_url": "https://dps.psx.com.pk/company/MLCF",
                "business_description": "Pilot profile fixture",
                "stale": False,
            },
        },
    })
    _write(universe, {
        "symbols": {
            "MLCF": {"symbol": "MLCF", "name": "Maple Leaf Cement Factory Limited", "tier": "core"},
            "FFC": {"symbol": "FFC", "name": "Fauji Fertilizer Company Limited", "tier": "core"},
        },
    })
    _write(index, {
        "documents": {
            "bk:fixture": {
                "hash": "bk:fixture",
                "source": "Topline",
                "source_type": "broker",
                "doc_type": "company_note",
                "date": "2026-01-01",
                "tickers": ["MLCF"],
                "digest": "Existing broker note",
                "digest_level": "full",
                "url": "https://example.test/note",
                "claims": [{"text": "retained"}],
                "omissions": None,
            },
        },
        "by_ticker": {
            "MLCF": [{
                "hash": "bk:fixture",
                "source": "broker",
                "doc_type": "company_note",
                "date": "2026-01-01",
                "one_line": "Existing broker note",
                "url": "https://example.test/note",
            }],
        },
        "_meta": {"built": "fixture"},
    })
    return profiles, universe, index


def _valid_doc(**overrides: object) -> dict:
    row = {
        "id": "psx:123456",
        "official_document_id": "123456",
        "ticker": "MLCF",
        "company_name": "Maple Leaf Cement Factory Limited",
        "title": "Transmission of Annual Report for the year ended June 30, 2024",
        "type": "financial_statement",
        "period": {"period_type": "annual", "period_end": "2024-06-30"},
        "published_at": "2024-10-03T09:15:00+05:00",
        "url": "https://dps.psx.com.pk/download/document/123456.pdf",
    }
    row.update(overrides)
    return row


def _manifest(path: Path, docs: list[dict]) -> Path:
    _write(path, {"schema_version": 1, "documents": docs})
    return path


def _expect_reject(root: Path, doc: dict | list[dict], reason: str) -> None:
    profiles, universe, index = _base_state(root)
    manifest_docs = doc if isinstance(doc, list) else [doc]
    manifest = _manifest(root / f"{reason}.json", manifest_docs)
    before = index.read_bytes()
    try:
        seed_historical_metadata(manifest, index, profiles, universe)
    except ValueError:
        pass
    else:
        raise AssertionError(f"{reason} was accepted")
    assert index.read_bytes() == before, f"{reason} changed research_index.json"


def main() -> int:
    live_before = (STATE / "research_index.json").read_bytes() if (STATE / "research_index.json").exists() else None
    with tempfile.TemporaryDirectory(prefix="henneth-hist-seed-") as tmp:
        root = Path(tmp)
        profiles, universe, index = _base_state(root)
        manifest = _manifest(root / "valid.json", [_valid_doc()])

        dry = seed_historical_metadata(manifest, index, profiles, universe, dry_run=True)
        assert dry["validated"] == 1 and dry["changed"] == 1 and dry["dry_run"] is True
        payload = json.loads(index.read_text(encoding="utf-8"))
        assert "psx:123456" not in payload["documents"], "dry run wrote to research_index.json"

        result = seed_historical_metadata(manifest, index, profiles, universe)
        assert result["validated"] == 1 and result["changed"] == 1 and result["symbols"] == ["MLCF"]
        payload = json.loads(index.read_text(encoding="utf-8"))
        doc = payload["documents"]["psx:123456"]
        assert doc["official_document_id"] == "123456"
        assert doc["url"] == "https://dps.psx.com.pk/download/document/123456.pdf"
        assert doc["period"] == {"period_end": "2024-06-30", "period_type": "annual"}
        assert "content_sha256" not in doc and "text" not in doc and "facts" not in doc
        by_ticker = payload["by_ticker"]["MLCF"]
        seeded_entry = next(row for row in by_ticker if row["hash"] == "psx:123456")
        assert seeded_entry["source"] == "filing" and seeded_entry["url"].endswith("/123456.pdf")
        assert any(row["hash"] == "bk:fixture" for row in by_ticker), "broker row was dropped"

        after_first = index.read_bytes()
        again = seed_historical_metadata(manifest, index, profiles, universe)
        assert again["changed"] == 0
        assert index.read_bytes() == after_first, "idempotent seed churned the index"

        cases = {
            "bad_id": _valid_doc(id="psx:abc"),
            "bad_url": _valid_doc(url="https://dps.psx.com.pk/download/document/123456.pdf?download=1"),
            "id_mismatch": _valid_doc(official_document_id="654321"),
            "wrong_pilot": _valid_doc(ticker="FFC", company_name="Fauji Fertilizer Company Limited"),
            "wrong_company": _valid_doc(company_name="Maple Leaf Cement Factory Ltd"),
            "missing_period": {k: v for k, v in _valid_doc().items() if k != "period"},
            "period_after_publication": _valid_doc(period={"period_type": "annual", "period_end": "2024-12-31"}),
            "content_field": _valid_doc(text="forbidden raw content"),
            "facts_field": _valid_doc(facts=[{"metric": "revenue"}]),
            "oversized_manifest": [_valid_doc(id=f"psx:12345{i}", official_document_id=f"12345{i}",
                                              url=f"https://dps.psx.com.pk/download/document/12345{i}.pdf")
                                   for i in range(6)],
        }
        for reason, bad_doc in cases.items():
            _expect_reject(root / reason, bad_doc, reason)

        conflict_root = root / "conflict"
        profiles, universe, index = _base_state(conflict_root)
        _manifest(conflict_root / "seed.json", [_valid_doc()])
        seed_historical_metadata(conflict_root / "seed.json", index, profiles, universe)
        conflict_manifest = _manifest(conflict_root / "conflict.json", [_valid_doc(title="Changed title")])
        before = index.read_bytes()
        try:
            seed_historical_metadata(conflict_manifest, index, profiles, universe)
        except ValueError:
            pass
        else:
            raise AssertionError("conflicting retained row was accepted")
        assert index.read_bytes() == before, "conflict changed research_index.json"

    live_after = (STATE / "research_index.json").read_bytes() if (STATE / "research_index.json").exists() else None
    assert live_after == live_before, "offline checker touched live research_index.json"
    print("historical PSX metadata seed self-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
