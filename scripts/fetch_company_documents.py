#!/usr/bin/env python3
"""Incrementally index official PSX company announcements for the CI pilot.

The DPS announcements page uses a public HTML POST endpoint. This producer calls that
same endpoint for the 20 symbols already selected by ``fetch_company_profiles.py`` and
merges official documents into the existing ``state/research_index.json`` corpus.

PDFs are never committed. A small, verified current-run batch is staged under the
gitignored ``.cache/company_intel`` directory for the downstream deterministic extractor.
Network/parse failures retain the last-good corpus and exit 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from psx_data import ROOT, STATE, load_json, save_json

BASE_URL = "https://dps.psx.com.pk"
ANNOUNCEMENTS_URL = f"{BASE_URL}/announcements"
SOURCE_PAGE = f"{BASE_URL}/announcements/companies"
CURSOR_PATH = STATE / "company_intel" / "cursors.json"
INDEX_PATH = STATE / "research_index.json"
CACHE_ROOT = ROOT / ".cache" / "company_intel"
RAW_DIR = CACHE_ROOT / "raw"
QUEUE_PATH = CACHE_ROOT / "extraction_queue.json"
CHECK_PATH = CACHE_ROOT / "checks.json"

PKT = timezone(timedelta(hours=5))
UA = {"User-Agent": "Mozilla/5.0 HennethDesk/2.CI.0 official-source-indexer"}
PILOT_COUNT = 20
INITIAL_LOOKBACK_DAYS = 400
OVERLAP_DAYS = 2
PAGE_SIZE = 50
MAX_ROWS_PER_SYMBOL = 100
MAX_DOWNLOADS_PER_RUN = 24
MAX_PDF_BYTES = 12 * 1024 * 1024
LOCAL_CADENCE_HOURS = 20

_DOC_ID_RE = re.compile(r"/download/document/(\d+)\.pdf(?:$|[?#])", re.I)
_SPACE_RE = re.compile(r"\s+")
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")

_CLASSIFIERS = (
    ("material_information", re.compile(r"\b(material information|material fact)\b", re.I)),
    ("financial_results", re.compile(r"\bfinancial results?\b|\bprofit.*eps\b", re.I)),
    ("financial_statement", re.compile(
        r"\b(annual report|financial statements?|quarterly accounts?|half.?yearly accounts?)\b", re.I)),
    ("insider_disclosure", re.compile(
        r"\b(disclosure of interest|substantial shareholder|change in shareholding)\b", re.I)),
    ("corporate_briefing", re.compile(r"\b(corporate briefing|briefing session)\b", re.I)),
    ("board_meeting", re.compile(r"\bboard meeting\b", re.I)),
    ("management_change", re.compile(
        r"\b(appointment|resignation|change).{0,35}\b(chairman|chairperson|ceo|chief executive|director|cfo|secretary)\b",
        re.I)),
    ("corporate_action", re.compile(
        r"\b(dividend|bonus shares?|right issue|book closure|stock split|merger|acquisition)\b", re.I)),
    ("credit_rating", re.compile(r"\bcredit rating\b", re.I)),
    ("meeting_notice", re.compile(r"\b(annual general meeting|extraordinary general meeting|agm|egm)\b", re.I)),
)


def _now() -> datetime:
    return datetime.now(PKT)


def _stamp(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


def _clean(value: str) -> str:
    return _SPACE_RE.sub(" ", value or "").strip()


class AnnouncementTableParser(HTMLParser):
    """Parse DPS table rows without depending on a browser or third-party HTML parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict]] = []
        self._row: list[dict] | None = None
        self._cell: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = {"parts": [], "links": []}
        elif tag == "a" and self._cell is not None:
            href = attrs_map.get("href")
            if href:
                self._cell["links"].append(href)

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell is not None and self._row is not None:
            self._row.append({
                "text": _clean(" ".join(self._cell["parts"])),
                "links": self._cell["links"],
            })
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def classify_document(title: str) -> str:
    for doc_type, pattern in _CLASSIFIERS:
        if pattern.search(title):
            return doc_type
    return "company_announcement"


def _published_at(date_text: str, time_text: str) -> str | None:
    try:
        parsed = datetime.strptime(f"{date_text} {time_text}", "%b %d, %Y %I:%M %p")
    except ValueError:
        return None
    return parsed.replace(tzinfo=PKT).isoformat(timespec="seconds")


def _document_id(symbol: str, published_at: str, title: str, url: str | None) -> tuple[str, str | None]:
    official_id = None
    if url:
        match = _DOC_ID_RE.search(url)
        official_id = match.group(1) if match else None
    if official_id:
        return f"psx:{official_id}", official_id
    identity = "|".join((symbol, published_at, _clean(title).lower(), url or ""))
    return f"psx:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}", None


def parse_announcements(html_text: str, expected_symbol: str) -> list[dict]:
    parser = AnnouncementTableParser()
    parser.feed(html_text)
    documents = []
    for cells in parser.rows:
        if len(cells) < 6:
            continue
        date_text, time_text, symbol, company_name, title = (cells[i]["text"] for i in range(5))
        symbol = symbol.upper()
        if symbol != expected_symbol:
            continue
        published_at = _published_at(date_text, time_text)
        if not published_at or not title:
            continue
        pdf_href = next((href for href in cells[5]["links"] if _DOC_ID_RE.search(href)), None)
        url = urljoin(BASE_URL, pdf_href) if pdf_href else None
        doc_id, official_id = _document_id(symbol, published_at, title, url)
        documents.append({
            "id": doc_id,
            "hash": doc_id,
            "source": "PSX DPS",
            "source_type": "filing",
            "doc_type": classify_document(title),
            "date": published_at[:10],
            "published_at": published_at,
            "tickers": [symbol],
            "company_name": company_name,
            "title": title,
            "digest": title,
            "digest_level": "headline",
            "claims": [],
            "url": url,
            "source_page": SOURCE_PAGE,
            "official_document_id": official_id,
            "omissions": None,
        })
    return documents


def _validate_official_pdf_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "dps.psx.com.pk":
        raise ValueError("document URL is not on the official DPS HTTPS host")
    if not _DOC_ID_RE.search(parsed.path):
        raise ValueError("document URL is not an official DPS PDF path")


def fetch_document_bytes(
    url: str,
    session: requests.Session | None = None,
    max_bytes: int = MAX_PDF_BYTES,
) -> tuple[bytes, dict]:
    """Return verified bounded PDF bytes and hash metadata for the extractor seam."""
    _validate_official_pdf_url(url)
    sess = session or requests.Session()
    response = sess.get(url, headers=UA, timeout=(10, 35), stream=True, allow_redirects=True)
    response.raise_for_status()
    _validate_official_pdf_url(response.url)
    declared = response.headers.get("content-length")
    if declared and int(declared) > max_bytes:
        raise ValueError(f"PDF exceeds {max_bytes} byte limit")
    chunks = []
    size = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        size += len(chunk)
        if size > max_bytes:
            raise ValueError(f"PDF exceeds {max_bytes} byte limit")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body.startswith(b"%PDF-"):
        raise ValueError("download is not a PDF")
    return body, {
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "content_length": len(body),
        "mime_type": "application/pdf",
    }


def _fetch_symbol(session: requests.Session, symbol: str, date_from: str) -> list[dict]:
    found: dict[str, dict] = {}
    for offset in range(0, MAX_ROWS_PER_SYMBOL, PAGE_SIZE):
        response = session.post(
            ANNOUNCEMENTS_URL,
            data={
                "type": "C", "symbol": symbol, "query": "", "count": PAGE_SIZE,
                "offset": offset, "date_from": date_from, "date_to": _now().date().isoformat(),
                "page": "annc",
            },
            headers=UA,
            timeout=(10, 35),
        )
        response.raise_for_status()
        if 'id="announcementsTable"' not in response.text:
            raise ValueError("DPS announcements response omitted the expected results table")
        rows = parse_announcements(response.text, symbol)
        for row in rows:
            found[row["id"]] = row
        if len(rows) < PAGE_SIZE:
            break
        time.sleep(0.15)
    return sorted(found.values(), key=lambda row: row["published_at"], reverse=True)


def _pilot_symbols(limit: int | None, requested: str | None = None) -> list[str]:
    profiles = load_json(STATE / "company_profiles.json", {})
    symbols = list((profiles.get("pilot") or {}).get("symbols") or [])
    if not symbols:
        symbols = list((profiles.get("tickers") or {}).keys())
    if requested:
        requested_symbols = [s.strip().upper() for s in requested.split(",") if s.strip()]
        known = {str(symbol).upper() for symbol in symbols}
        symbols = [symbol for symbol in requested_symbols if symbol in known]
    cap = min(limit, PILOT_COUNT) if limit is not None else PILOT_COUNT
    return [str(symbol).upper() for symbol in symbols[:cap]]


def _cloud_schedule_skip(force: bool) -> bool:
    if force or os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return False
    now = _now()
    return not (now.hour == 8 and now.minute < 30)


def _local_cadence_skip(force: bool) -> bool:
    if force or os.environ.get("GITHUB_ACTIONS"):
        return False
    checks = load_json(CHECK_PATH, {})
    value = checks.get("last_attempt")
    if not value:
        return False
    try:
        age = _now() - datetime.fromisoformat(value)
    except ValueError:
        return False
    return timedelta(0) <= age < timedelta(hours=LOCAL_CADENCE_HOURS)


def _prepare_cache() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for path in RAW_DIR.glob("*.pdf"):
        path.unlink()
    save_json(QUEUE_PATH, {"schema_version": 1, "created_at": _stamp(), "documents": []})


def _safe_cache_path(doc_id: str) -> Path:
    safe_id = _SAFE_ID_RE.sub("_", doc_id).strip("._")
    if not safe_id:
        raise ValueError("unsafe empty document id")
    path = (RAW_DIR / f"{safe_id}.pdf").resolve()
    if RAW_DIR.resolve() not in path.parents:
        raise ValueError("cache path escaped producer directory")
    return path


def _merge_document(prior: dict | None, incoming: dict) -> dict:
    prior = dict(prior or {})
    preserve_digest = prior.get("digest_level") == "full"
    downstream = {
        key: prior.get(key)
        for key in ("claims", "omissions")
        if key in prior
    }
    merged = {**prior, **incoming, **downstream}
    if preserve_digest:
        merged["digest"] = prior.get("digest")
        merged["digest_level"] = "full"
    return merged


def _by_ticker_entry(document: dict) -> dict:
    return {
        "hash": document["id"],
        "source": "filing",
        "doc_type": document["doc_type"],
        "date": document["date"],
        "published_at": document["published_at"],
        "one_line": document["title"][:140],
        "url": document.get("url"),
    }


def _rebuild_ticker(index: dict, symbol: str) -> None:
    official = [
        _by_ticker_entry(doc)
        for doc in (index.get("documents") or {}).values()
        if symbol in (doc.get("tickers") or []) and doc.get("source") == "PSX DPS"
    ]
    other = [
        item for item in ((index.get("by_ticker") or {}).get(symbol) or [])
        if not str(item.get("hash") or "").startswith("psx:")
    ]
    combined = official + other
    deduped = {item.get("hash"): item for item in combined if item.get("hash")}
    rows = sorted(
        deduped.values(),
        key=lambda item: (item.get("published_at") or item.get("date") or "", item.get("hash") or ""),
        reverse=True,
    )[:100]
    index.setdefault("by_ticker", {})[symbol] = rows


def _stage_downloads(index: dict, candidates: list[str], session: requests.Session,
                     published_since: str | None = None) -> tuple[int, int]:
    documents = index["documents"]
    extracted = load_json(STATE / "company_documents.json", {"documents": {}})
    ready_hashes = {
        doc_id: row.get("content_sha256")
        for doc_id, row in (extracted.get("documents") or {}).items()
        if row.get("status") == "ready" and row.get("content_sha256")
    }
    priority = {
        "material_information": 0, "financial_results": 1, "financial_statement": 2,
        "corporate_action": 3, "management_change": 4,
    }
    pending = []
    for doc_id in candidates:
        document = documents[doc_id]
        if document.get("source") != "PSX DPS" or not document.get("url"):
            continue
        if published_since and str(document.get("published_at") or "")[:10] < published_since:
            continue
        # A hash in the source registry is not an extraction receipt. Restage until the
        # downstream company_documents registry confirms this exact version is ready.
        if (document.get("content_sha256")
                and ready_hashes.get(document["id"]) == document.get("content_sha256")):
            continue
        pending.append(document)
    pending.sort(key=lambda doc: (
        priority.get(doc.get("doc_type"), 9),
        -(datetime.fromisoformat(doc["published_at"]).timestamp()),
    ))

    # First batch is coverage-balanced: one highest-priority document per ticker before a
    # second from the same company. This keeps the 20-company product useful while a bounded
    # backlog catches up over later zero-cost runs.
    by_symbol: dict[str, list[dict]] = {}
    for document in pending:
        symbol = str((document.get("tickers") or [""])[0])
        by_symbol.setdefault(symbol, []).append(document)
    selected: list[dict] = []
    while len(selected) < MAX_DOWNLOADS_PER_RUN and any(by_symbol.values()):
        for symbol in sorted(by_symbol):
            if by_symbol[symbol] and len(selected) < MAX_DOWNLOADS_PER_RUN:
                selected.append(by_symbol[symbol].pop(0))

    queue = []
    verified = failed = 0
    for document in selected:
        try:
            body, metadata = fetch_document_bytes(document["url"], session=session)
            path = _safe_cache_path(document["id"])
            path.write_bytes(body)
            document.update(metadata)
            document["download"] = {"status": "verified", "checked_at": _stamp(), "error": None}
            queue.append({
                "doc_id": document["id"],
                "path": str(path),
                "sha256": metadata["content_sha256"],
                "content_length": metadata["content_length"],
                "mime_type": metadata["mime_type"],
            })
            verified += 1
        except (requests.RequestException, OSError, ValueError) as exc:
            document["download"] = {
                "status": "failed", "checked_at": _stamp(),
                "error": f"{type(exc).__name__}:{str(exc)[:120]}",
            }
            failed += 1
    save_json(QUEUE_PATH, {"schema_version": 1, "created_at": _stamp(), "documents": queue})
    return verified, failed


def _date_from(cursor: dict) -> str:
    value = cursor.get("max_published_at")
    if value:
        try:
            return (datetime.fromisoformat(value).date() - timedelta(days=OVERLAP_DAYS)).isoformat()
        except ValueError:
            pass
    return (_now().date() - timedelta(days=INITIAL_LOOKBACK_DAYS)).isoformat()


def _self_check() -> int:
    fixture = """<table><tbody><tr><td>Jul 31, 2026</td><td>8:51 AM</td>
    <td><a href='/company/MLCF'><strong>MLCF</strong></a></td>
    <td>Maple Leaf Cement Factory Limited</td><td>MLCF-Financial Results</td>
    <td><a href='/download/document/280589.pdf'>PDF</a></td></tr></tbody></table>"""
    rows = parse_announcements(fixture, "MLCF")
    checks = [
        len(rows) == 1,
        rows[0]["id"] == "psx:280589",
        rows[0]["published_at"] == "2026-07-31T08:51:00+05:00",
        rows[0]["doc_type"] == "financial_results",
        rows[0]["url"] == f"{BASE_URL}/download/document/280589.pdf",
    ]
    if not all(checks):
        print("company_documents self-check: FAIL")
        return 1
    for unsafe in ("http://dps.psx.com.pk/download/document/1.pdf", "https://example.com/x.pdf"):
        try:
            _validate_official_pdf_url(unsafe)
            print("company_documents self-check: FAIL (unsafe URL accepted)")
            return 1
        except ValueError:
            pass
    print("company_documents self-check: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="run outside cadence/schedule gate")
    parser.add_argument("--limit", type=int, help="restrict pilot symbols for a manual run")
    parser.add_argument("--symbols", help="comma-separated pilot symbols for a bounded manual batch")
    parser.add_argument("--metadata-only", action="store_true", help="do not stage PDF bytes")
    parser.add_argument("--published-since", help="stage only documents published on/after YYYY-MM-DD")
    parser.add_argument("--self-check", action="store_true", help="run parser/security fixtures")
    args = parser.parse_args(argv)
    if args.self_check:
        return _self_check()
    if args.published_since:
        try:
            datetime.strptime(args.published_since, "%Y-%m-%d")
        except ValueError:
            parser.error("--published-since must be YYYY-MM-DD")
    if args.limit is not None and not 1 <= args.limit <= PILOT_COUNT:
        parser.error(f"--limit must be between 1 and {PILOT_COUNT}")
    if _cloud_schedule_skip(args.force):
        print("company_documents: outside the once-daily 08:07 PKT cloud window")
        return 0
    if _local_cadence_skip(args.force):
        print(f"company_documents: inside {LOCAL_CADENCE_HOURS}h local cadence")
        return 0

    symbols = _pilot_symbols(args.limit, args.symbols)
    if not symbols:
        print("company_documents: no CI pilot symbols; leaving last-good state untouched")
        return 0
    _prepare_cache()

    prior_index = load_json(INDEX_PATH, {"documents": {}, "by_ticker": {}, "_meta": {}})
    index = {
        "documents": dict(prior_index.get("documents") or {}),
        "by_ticker": dict(prior_index.get("by_ticker") or {}),
        "_meta": dict(prior_index.get("_meta") or {}),
    }
    prior_cursors = load_json(CURSOR_PATH, {"schema_version": 1, "source": SOURCE_PAGE, "tickers": {}})
    cursors = {
        "schema_version": 1,
        "source": SOURCE_PAGE,
        "tickers": dict(prior_cursors.get("tickers") or {}),
    }

    session = requests.Session()
    session.headers.update(UA)
    changed_ids: list[str] = []
    ticker_errors: dict[str, str] = {}
    fetched_rows = 0
    for symbol in symbols:
        prior_cursor = dict(cursors["tickers"].get(symbol) or {})
        try:
            rows = _fetch_symbol(session, symbol, _date_from(prior_cursor))
            fetched_rows += len(rows)
            symbol_changed = False
            for incoming in rows:
                doc_id = incoming["id"]
                merged = _merge_document(index["documents"].get(doc_id), incoming)
                if merged != index["documents"].get(doc_id):
                    index["documents"][doc_id] = merged
                    changed_ids.append(doc_id)
                    symbol_changed = True
            _rebuild_ticker(index, symbol)
            published_values = [row["published_at"] for row in rows]
            if prior_cursor.get("max_published_at"):
                published_values.append(prior_cursor["max_published_at"])
            max_published = max(published_values, default=None)
            recovered = prior_cursor.get("status") == "degraded"
            if symbol_changed or recovered or symbol not in cursors["tickers"]:
                cursors["tickers"][symbol] = {
                    "last_success": _stamp(),
                    "max_published_at": max_published,
                    "status": "ok",
                    "error": None,
                }
        except (requests.RequestException, ValueError) as exc:
            message = f"{type(exc).__name__}:{str(exc)[:120]}"
            ticker_errors[symbol] = message
            cursors["tickers"][symbol] = {
                **prior_cursor,
                "status": "degraded",
                "error": message,
                "last_attempt": _stamp(),
            }
        time.sleep(0.15)

    download_candidates = list(dict.fromkeys(changed_ids + list(index["documents"])))
    verified = failed_downloads = 0
    if not args.metadata_only:
        verified, failed_downloads = _stage_downloads(index, download_candidates, session, args.published_since)

    index_changed = index != prior_index
    cursor_changed = cursors != prior_cursors
    if index_changed:
        index["_meta"] = {
            **index.get("_meta", {}),
            "built": time.strftime("%Y-%m-%d %H:%M"),
            "n_documents": len(index["documents"]),
            "official_psx_documents": sum(
                1 for doc in index["documents"].values() if doc.get("source") == "PSX DPS"),
            "official_psx_source": SOURCE_PAGE,
        }
        save_json(INDEX_PATH, index)
    if cursor_changed:
        # Cursor advances only after the corpus write succeeds. A crash before here safely refetches.
        save_json(CURSOR_PATH, cursors)
    save_json(CHECK_PATH, {"last_attempt": _stamp(), "ticker_errors": ticker_errors})

    print(
        f"company_documents: {len(symbols)} symbols, {fetched_rows} rows seen, "
        f"{len(set(changed_ids))} metadata changes, {verified} PDFs staged, "
        f"{failed_downloads} PDF failures, {len(ticker_errors)} ticker failures"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
