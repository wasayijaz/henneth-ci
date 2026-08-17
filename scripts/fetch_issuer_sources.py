#!/usr/bin/env python3
"""Discover and monitor official issuer websites for the 20-company CI pilot.

Issuer roots come only from each company's official PSX DPS profile. The monitor then
follows a bounded set of same-domain investor, financial-report, governance and news
index pages. It records URLs, validators and content hashes, not page bodies. No browser,
paid provider, model call or PDF archive is involved.

Scheduled cloud runs are limited to Monday's first 08:xx PKT cycle. Failures preserve
last-good source rows, mark the affected source degraded and exit 0.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests

from psx_data import ROOT, STATE, load_json, save_json

BASE_URL = "https://dps.psx.com.pk"
OUT = STATE / "company_intel" / "source_registry.json"
CACHE_CHECK = ROOT / ".cache" / "company_intel" / "issuer_checks.json"
PKT = timezone(timedelta(hours=5))
UA = {
    # A truthful named crawler UA avoids a documented 403 on DGKC's issuer server;
    # masquerading as Chrome made that otherwise-public page reject the request.
    "User-Agent": "Mozilla/5.0 HennethDesk/2.CI.0 issuer-source-monitor",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

PILOT_COUNT = 20
# Home + the strongest issuer-specific disclosure/index page. Forty issuer requests per
# established weekly run is the ceiling; the 30-minute market pipeline must stay cheap.
MAX_MONITORED_PAGES = 2
MAX_DOCUMENT_LINKS = 200
MAX_HTML_BYTES = 2 * 1024 * 1024
LOCAL_CADENCE_DAYS = 7
MAX_REDIRECTS = 4

_WEBSITE_RE = re.compile(
    r'class=["\'][^"\']*item__head[^"\']*["\'][^>]*>\s*WEBSITE\s*</div>'
    r'.{0,600}?<a[^>]+href=["\']([^"\']+)',
    re.I | re.S,
)
_LINK_HINT = re.compile(
    r"\b(investor|shareholder|financial|annual|quarterly|report|presentation|governance|"
    r"corporate|announcement|news|media|disclosure)\b",
    re.I,
)
_SPACE_RE = re.compile(r"\s+")
_MULTI_LABEL_PUBLIC_SUFFIXES = {"com.pk", "net.pk", "org.pk", "edu.pk", "gov.pk"}


def _now() -> datetime:
    return datetime.now(PKT)


def _stamp() -> str:
    return _now().isoformat(timespec="seconds")


def _clean(value: str) -> str:
    return _SPACE_RE.sub(" ", html.unescape(value or "")).strip()


def _root_domain(hostname: str) -> str:
    host = hostname.lower().strip(".")
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in _MULTI_LABEL_PUBLIC_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _validate_url(url: str, expected_domain: str | None = None) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("unsupported issuer URL")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("non-standard issuer port")
    host = parsed.hostname.lower().strip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local
                    or address.is_reserved or address.is_multicast):
        raise ValueError("private or reserved issuer host")
    domain = _root_domain(host)
    if expected_domain and domain != expected_domain:
        raise ValueError("issuer redirect/link left the DPS-declared domain")
    normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))
    return normalized, domain


def _bounded_get(
    session: requests.Session,
    url: str,
    expected_domain: str,
    headers: dict | None = None,
) -> tuple[requests.Response, bytes]:
    current, _ = _validate_url(url, expected_domain)
    for _ in range(MAX_REDIRECTS + 1):
        response = session.get(
            current, headers={**UA, **(headers or {})}, timeout=(10, 30),
            stream=True, allow_redirects=False,
        )
        if response.is_redirect or response.is_permanent_redirect:
            target = response.headers.get("location")
            if not target:
                raise ValueError("issuer redirect omitted Location")
            current, _ = _validate_url(urljoin(current, target), expected_domain)
            continue
        if response.status_code == 304:
            return response, b""
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise ValueError(f"issuer page is not HTML ({content_type[:60]})")
        declared = response.headers.get("content-length")
        if declared and int(declared) > MAX_HTML_BYTES:
            raise ValueError("issuer page exceeds size limit")
        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_HTML_BYTES:
                raise ValueError("issuer page exceeds size limit")
            chunks.append(chunk)
        return response, b"".join(chunks)
    raise ValueError("too many issuer redirects")


def _fetch_root(session: requests.Session, url: str, prior_pages: dict[str, dict]) -> tuple[str, str, requests.Response, bytes]:
    """Prefer HTTPS for legacy DPS URLs, falling back to the exact declared HTTP URL."""
    normalized, domain = _validate_url(url)
    candidates = [normalized]
    if normalized.startswith("http://"):
        candidates.insert(0, "https://" + normalized[len("http://"):])
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            response, body = _bounded_get(
                session, candidate, domain, _conditional_headers(prior_pages.get(candidate)),
            )
            return candidate, domain, response, body
        except (requests.RequestException, OSError, ValueError) as exc:
            last_error = exc
    raise last_error or ValueError("issuer root could not be fetched")


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, _clean(" ".join(self._parts))))
            self._href = None
            self._parts = []


class FingerprintParser(HTMLParser):
    """Build a stable visible-content fingerprint without script/style churn."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
            return
        if tag == "a" and self._ignored_depth == 0:
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            value = _clean(data)
            if value:
                self.parts.append(value)


def _content_fingerprint(body: bytes) -> str:
    parser = FingerprintParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    material = "\n".join(parser.parts + sorted(set(parser.links)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _home_fingerprint(body: bytes, base_url: str) -> str:
    """Home pages rotate banners/timestamps; fingerprint their durable research links."""
    host = urlparse(base_url).hostname or ""
    domain = _root_domain(host)
    rows = discover_high_signal_links(body, base_url, domain)
    documents = discover_document_links(body, base_url, domain)
    material = "\n".join(sorted(
        f"{row.get('url')}|{row.get('label')}" for row in rows + documents
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest() if material else _content_fingerprint(body)


def discover_issuer_url(dps_html: str) -> str | None:
    match = _WEBSITE_RE.search(dps_html)
    if not match:
        return None
    value = html.unescape(match.group(1)).strip()
    if value.startswith("//"):
        value = "https:" + value
    elif not urlparse(value).scheme:
        value = "https://" + value.lstrip("/")
    normalized, _ = _validate_url(value)
    return normalized


def _kind(label: str, url: str) -> str:
    text = f"{label} {url}".lower()
    if "governance" in text or "board" in text or "management" in text:
        return "governance"
    if "presentation" in text or "briefing" in text:
        return "presentations"
    if "investor" in text or "shareholder" in text:
        return "investor_relations"
    if "financial" in text or "annual" in text or "quarter" in text or "report" in text:
        return "financial_reports"
    if "news" in text or "announcement" in text or "media" in text or "disclosure" in text:
        return "announcements"
    return "issuer_home"


def discover_high_signal_links(body: bytes, base_url: str, domain: str,
                               symbol: str | None = None) -> list[dict]:
    parser = LinkParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    candidates: dict[str, dict] = {}
    for href, label in parser.links:
        joined = urljoin(base_url, href)
        try:
            normalized, _ = _validate_url(joined, domain)
        except (ValueError, TypeError):
            continue
        parsed = urlparse(normalized)
        if parsed.path.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")):
            continue
        if not _LINK_HINT.search(f"{label} {parsed.path}"):
            continue
        candidates[normalized] = {
            "url": normalized,
            "kind": _kind(label, normalized),
            "label": label[:120] or parsed.path[:120],
        }
    rows = list(candidates.values())
    symbol_token = (symbol or "").lower()
    symbol_specific = [row for row in rows if len(symbol_token) >= 3
                       and symbol_token in f"{row['label']} {row['url']}".lower()]
    # Group websites frequently expose investor pages for every subsidiary. If DPS points to
    # a group root and a symbol-specific path exists, do not monitor sibling companies.
    if symbol_specific:
        rows = symbol_specific
    return sorted(rows, key=lambda row: (row["kind"], row["url"]))


def _issuer_document_type(label: str, url: str) -> str:
    text = f"{label} {url}".lower()
    if "annual" in text:
        return "annual_report"
    if "quarter" in text or "half year" in text or "financial" in text:
        return "financial_report"
    if "presentation" in text or "briefing" in text:
        return "presentation"
    if "governance" in text or "code of conduct" in text:
        return "governance_document"
    return "issuer_document"


def discover_document_links(body: bytes, base_url: str, domain: str,
                            include_all: bool = False) -> list[dict]:
    """Return same-domain report/document links without downloading their content."""
    parser = LinkParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    documents: dict[str, dict] = {}
    for href, label in parser.links:
        try:
            normalized, _ = _validate_url(urljoin(base_url, href), domain)
        except (ValueError, TypeError):
            continue
        path = urlparse(normalized).path.lower()
        if not path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
            continue
        if not include_all and not _LINK_HINT.search(f"{label} {path}"):
            continue
        resource_id = "issuer:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        documents[resource_id] = {
            "id": resource_id,
            "url": normalized,
            "label": label[:180] or Path(path).name[:180],
            "document_type": _issuer_document_type(label, normalized),
            "source_page": base_url,
            "status": "discovered",
        }
    return sorted(documents.values(), key=lambda row: (row["document_type"], row["url"]))


def _conditional_headers(prior: dict | None) -> dict:
    prior = prior or {}
    headers = {}
    if prior.get("etag"):
        headers["If-None-Match"] = prior["etag"]
    if prior.get("last_modified"):
        headers["If-Modified-Since"] = prior["last_modified"]
    return headers


def _page_record(prior: dict | None, candidate: dict, response: requests.Response, body: bytes) -> dict:
    prior = dict(prior or {})
    if response.status_code == 304:
        return prior
    digest = (_home_fingerprint(body, response.url)
              if candidate.get("kind") == "issuer_home" else _content_fingerprint(body))
    content_type = (response.headers.get("content-type") or "text/html").split(";", 1)[0].strip()
    same_content = digest == prior.get("content_sha256")
    if same_content and prior.get("status") == "ok":
        return prior
    now = _stamp()
    record = {
        **prior,
        **candidate,
        "status": "ok",
        "error": None,
        "content_sha256": digest,
        "content_length": len(body),
        "content_type": content_type,
        "etag": response.headers.get("etag"),
        "last_modified": response.headers.get("last-modified"),
        "first_seen_at": prior.get("first_seen_at") or now,
        "last_changed_at": now if not same_content else prior.get("last_changed_at"),
    }
    if prior.get("content_sha256") and not same_content:
        record["previous_sha256"] = prior["content_sha256"]
    return record


def _failure_record(prior: dict | None, candidate: dict, exc: Exception) -> dict:
    prior = dict(prior or {})
    error = f"{type(exc).__name__}:{str(exc)[:120]}"
    if prior.get("status") == "degraded" and prior.get("error") == error:
        return prior
    return {**prior, **candidate, "status": "degraded", "error": error}


def _pilot_symbols(limit: int | None) -> list[str]:
    profiles = load_json(STATE / "company_profiles.json", {})
    symbols = list((profiles.get("pilot") or {}).get("symbols") or [])
    if not symbols:
        symbols = list((profiles.get("tickers") or {}).keys())
    cap = min(limit, PILOT_COUNT) if limit is not None else PILOT_COUNT
    return [str(symbol).upper() for symbol in symbols[:cap]]


def _schedule_skip(force: bool) -> bool:
    if force or os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return False
    now = _now()
    return not (now.weekday() == 0 and now.hour == 8 and now.minute < 30)


def _local_cadence_skip(force: bool) -> bool:
    if force or os.environ.get("GITHUB_ACTIONS"):
        return False
    cached = load_json(CACHE_CHECK, {})
    try:
        last = datetime.fromisoformat(cached.get("last_attempt") or "")
    except ValueError:
        return False
    return timedelta(0) <= _now() - last < timedelta(days=LOCAL_CADENCE_DAYS)


def _fetch_dps_profile(session: requests.Session, symbol: str) -> str:
    response = session.get(f"{BASE_URL}/company/{symbol}", headers=UA, timeout=(10, 30))
    response.raise_for_status()
    if urlparse(response.url).hostname != "dps.psx.com.pk":
        raise ValueError("DPS profile redirected off official host")
    return response.text


def _self_check() -> int:
    fixture = '<div class="item__head">WEBSITE</div><p><a href="http://www.example.com">Site</a></p>'
    checks = [
        discover_issuer_url(fixture) == "http://www.example.com/",
        _root_domain("ir.example.com.pk") == "example.com.pk",
        _kind("Annual Reports", "https://example.com/reports") == "financial_reports",
    ]
    links = discover_high_signal_links(
        b'<a href="/investors">Investor Relations</a><a href="https://other.test/news">News</a>',
        "https://www.example.com/", "example.com", "EXM",
    )
    checks.append(len(links) == 1 and links[0]["kind"] == "investor_relations")
    docs = discover_document_links(
        b'<a href="/reports/annual-2025.pdf">Annual Report 2025</a>'
        b'<a href="https://other.test/report.pdf">Report</a>',
        "https://www.example.com/investors", "example.com", include_all=True,
    )
    checks.append(len(docs) == 1 and docs[0]["document_type"] == "annual_report")
    try:
        _validate_url("http://127.0.0.1/private")
        checks.append(False)
    except ValueError:
        checks.append(True)
    if not all(checks):
        print("issuer_sources self-check: FAIL")
        return 1
    print("issuer_sources self-check: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_check:
        return _self_check()
    if args.limit is not None and not 1 <= args.limit <= PILOT_COUNT:
        parser.error(f"--limit must be between 1 and {PILOT_COUNT}")
    if _schedule_skip(args.force):
        print("issuer_sources: outside the weekly Monday 08:07 PKT cloud window")
        return 0
    if _local_cadence_skip(args.force):
        print(f"issuer_sources: inside {LOCAL_CADENCE_DAYS}d local cadence")
        return 0

    symbols = _pilot_symbols(args.limit)
    if not symbols:
        print("issuer_sources: no CI pilot symbols; leaving last-good state untouched")
        return 0
    prior = load_json(OUT, {"schema_version": 1, "tickers": {}})
    registry = {
        **prior,
        "schema_version": 1,
        "tickers": dict(prior.get("tickers") or {}),
    }
    session = requests.Session()
    errors = 0
    changed_pages = 0

    for symbol in symbols:
        prior_ticker = dict(registry["tickers"].get(symbol) or {})
        ticker = dict(prior_ticker)
        dps_url = f"{BASE_URL}/company/{symbol}"
        issuer_url = prior_ticker.get("issuer_url")
        try:
            if not issuer_url:
                dps_html = _fetch_dps_profile(session, symbol)
                issuer_url = discover_issuer_url(dps_html)
                if not issuer_url:
                    raise ValueError("DPS profile has no issuer website")
            prior_pages = {row["url"]: row for row in (prior_ticker.get("monitored_pages") or [])
                           if row.get("url")}
            issuer_url, domain, root_response, root_body = _fetch_root(
                session, issuer_url, prior_pages,
            )
            root_candidate = {"url": issuer_url, "kind": "issuer_home", "label": "Issuer website"}
            root_record = _page_record(prior_pages.get(issuer_url), root_candidate, root_response, root_body)
            discovered_documents = discover_document_links(root_body, root_response.url, domain)
            if root_body:
                discovered = discover_high_signal_links(root_body, root_response.url, domain, symbol)
            else:
                discovered = [
                    {"url": row["url"], "kind": row.get("kind") or "issuer_page",
                     "label": row.get("label") or row["url"]}
                    for row in prior_pages.values() if row["url"] != issuer_url
                ]
            candidates = [root_candidate] + discovered
            deduped = {row["url"]: row for row in candidates}
            ordered = [deduped[issuer_url]] + [
                row for url, row in sorted(deduped.items()) if url != issuer_url
            ]
            page_records = [root_record]
            for candidate in ordered[1:MAX_MONITORED_PAGES]:
                old = prior_pages.get(candidate["url"])
                try:
                    response, body = _bounded_get(
                        session, candidate["url"], domain, _conditional_headers(old),
                    )
                    page_records.append(_page_record(old, candidate, response, body))
                    discovered_documents.extend(discover_document_links(
                        body, response.url, domain, include_all=True,
                    ))
                except (requests.RequestException, OSError, ValueError) as exc:
                    page_records.append(_failure_record(old, candidate, exc))
                    errors += 1
                time.sleep(0.1)
            prior_documents = {
                row["id"]: row for row in (prior_ticker.get("document_links") or []) if row.get("id")
            }
            for document in discovered_documents:
                if document["id"] in prior_documents:
                    prior_documents[document["id"]] = {
                        **prior_documents[document["id"]], **document,
                        "first_seen_at": prior_documents[document["id"]].get("first_seen_at") or _stamp(),
                    }
                elif len(prior_documents) < MAX_DOCUMENT_LINKS:
                    prior_documents[document["id"]] = {**document, "first_seen_at": _stamp()}
            ticker = {
                "symbol": symbol,
                "dps_company_url": dps_url,
                "issuer_url": issuer_url,
                "root_domain": domain,
                "discovered_from": dps_url,
                "status": "degraded" if any(row.get("status") == "degraded" for row in page_records) else "ok",
                "monitored_pages": page_records,
                "document_links": sorted(prior_documents.values(), key=lambda row: row["id"]),
            }
        except (requests.RequestException, OSError, ValueError) as exc:
            errors += 1
            ticker = {
                **prior_ticker,
                "symbol": symbol,
                "dps_company_url": dps_url,
                "discovered_from": dps_url,
                "issuer_url": issuer_url,
                "root_domain": (_root_domain(urlparse(issuer_url).hostname)
                                if issuer_url and urlparse(issuer_url).hostname else None),
                "status": "degraded",
                "error": f"{type(exc).__name__}:{str(exc)[:120]}",
            }
        if ticker != prior_ticker:
            prior_hashes = {row.get("url"): row.get("content_sha256")
                            for row in (prior_ticker.get("monitored_pages") or [])}
            changed_pages += sum(
                1 for row in (ticker.get("monitored_pages") or [])
                if row.get("content_sha256") != prior_hashes.get(row.get("url"))
            )
            registry["tickers"][symbol] = ticker
        time.sleep(0.15)

    if registry != prior:
        registry["updated"] = _stamp()
        registry["source"] = "Issuer websites discovered from official PSX DPS company profiles"
        registry["pilot_count"] = len(registry["tickers"])
        registry["degraded"] = any(
            row.get("status") != "ok" for row in registry["tickers"].values()
        )
        save_json(OUT, registry)
    save_json(CACHE_CHECK, {"last_attempt": _stamp(), "errors": errors})
    print(
        f"issuer_sources: {len(symbols)} symbols, {changed_pages} new/changed page hashes, "
        f"{errors} source errors{' (last-good retained)' if errors else ''}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
