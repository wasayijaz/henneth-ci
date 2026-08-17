#!/usr/bin/env python3
"""Small, deterministic financial-fact normalizer.

The document extractor intentionally stores only bounded evidence.  This module
therefore accepts the transient page text during a live extraction and returns
bounded, page-linked records.  The persisted series never contains document
text.  A later rebuild can consume the durable ``company_documents.json`` rows
when their evidence is sufficient, but it will not guess a period or unit that
is not explicitly present.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any, Iterable


_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)"),
    re.compile(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", re.I),
    re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b", re.I),
)
_MONTHS = {m.lower(): i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
_PERIOD_RE = re.compile(r"\b(period|quarter|year|half[- ]year|six[- ]month|nine[- ]month|month)\b.{0,30}\b(end(?:ed)?|ended)\b", re.I)
_PERIOD_WORDS = (
    ("annual", re.compile(r"\b(annual|year[- ]end|year ended|audited financial)\b", re.I)),
    ("half_year", re.compile(r"\b(half[- ]year|six[- ]month|six months|interim)\b", re.I)),
    ("quarter", re.compile(r"\b(quarter(?:ly)?|1st quarter|2nd quarter|3rd quarter|4th quarter)\b", re.I)),
)
_HEADER_SCALE_RE = re.compile(r"\(\s*(?:rupees?|rs\.?)\s+in\s+(thousand|million|billion|mn|bn)\s*\)", re.I)
_SUFFIX_SCALE = {"thousand": 1_000, "million": 1_000_000, "mn": 1_000_000, "billion": 1_000_000_000, "bn": 1_000_000_000}


def _iso_date(day: str, month: str, year: str) -> str | None:
    try:
        if month.isdigit():
            value = date(int(year), int(month), int(day))
        else:
            value = date(int(year), _MONTHS[month.lower()], int(day))
        return value.isoformat()
    except (KeyError, ValueError):
        return None


def explicit_period_end(title: str | None, pages: Iterable[str] = ()) -> tuple[str | None, str | None, list[str]]:
    """Find a reporting period only when an explicit ending phrase is present."""
    title_text = str(title or "")
    page_text = "\n".join(str(p or "") for p in pages)
    # Prefer title: a published timestamp must never become a reporting period.
    candidates: list[tuple[str, str]] = [(title_text, "title")]
    # Evidence pages may contain the header; limit the fallback to pages with a
    # period marker so ordinary dates in directors' biographies are ignored.
    candidates.extend((p, "page") for p in page_text.split("\n") if _PERIOD_RE.search(p))
    for material, origin in candidates:
        if not _PERIOD_RE.search(material) and origin == "title":
            # Common PSX title form: "Financial Results 31.12.2023".
            if not re.search(r"\b(results?|financial statements?)\b", material, re.I):
                continue
        for pattern in _DATE_PATTERNS:
            match = pattern.search(material)
            if not match:
                continue
            groups = match.groups()
            if len(groups) != 3:
                continue
            if groups[0].isdigit():
                iso = _iso_date(groups[0], groups[1], groups[2])
            else:
                iso = _iso_date(groups[1], groups[0], groups[2])
            if iso:
                return iso, period_type(material), []
    return None, None, ["missing_period_end"]


def period_type(material: str | None) -> str | None:
    value = str(material or "")
    for kind, pattern in _PERIOD_WORDS:
        if pattern.search(value):
            return kind
    return None


def consolidation_basis(material: str | None) -> tuple[str | None, list[str]]:
    text = str(material or "")
    consolidated = bool(re.search(r"\bconsolidated\b", text, re.I))
    unconsolidated = bool(re.search(r"\bunconsolidated\b|\bseparate financial", text, re.I))
    if consolidated and unconsolidated:
        return None, ["conflicting_consolidation_labels"]
    if consolidated:
        return "consolidated", []
    if unconsolidated:
        return "unconsolidated", []
    return None, ["missing_consolidation_basis"]


def currency_and_scale(fact: dict[str, Any], evidence_text: str) -> tuple[str | None, int | None, list[str]]:
    text = f"{fact.get('unit') or ''} {fact.get('raw_value') or ''} {evidence_text}"
    flags: list[str] = []
    currency = "PKR" if re.search(r"\b(?:rs\.?|rupees?)\b|PKR|pkr/share", text, re.I) else None
    if currency is None:
        flags.append("missing_currency")
    fact_type = str(fact.get("fact_type") or "").lower()
    per_share = fact_type in {"eps", "dividend", "target_price"}
    percent = fact_type in {"change_pct", "margin"}
    multiplier = 1 if per_share or percent else fact.get("scale_multiplier")
    if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or multiplier <= 0:
        multiplier = None
    # Prefer an explicit *table header* over an extractor default.  Narrative
    # ``Rs 12 bn`` values must not scale a per-share or percentage metric.
    scale_match = _HEADER_SCALE_RE.search(evidence_text) if not per_share and not percent else None
    if scale_match:
        token = scale_match.group(1)
        if token:
            multiplier = _SUFFIX_SCALE[token.lower()]
    if multiplier is None and not per_share and not percent:
        flags.append("missing_unit_scale")
    return currency, int(multiplier) if multiplier is not None else None, flags


def normalize_fact(doc: dict[str, Any], fact: dict[str, Any], *, pages: Iterable[str] = ()) -> dict[str, Any] | None:
    """Return one bounded series row or ``None`` when no source identity exists."""
    doc_id = str(doc.get("doc_id") or "")
    ticker_values = doc.get("tickers") or fact.get("tickers") or []
    tickers = sorted({str(t).strip().upper() for t in ticker_values if str(t).strip()})
    evidence = next((e for e in fact.get("evidence") or [] if isinstance(e, dict)), {})
    source_url = evidence.get("source_url") or doc.get("source_url")
    evidence_page = evidence.get("page")
    evidence_text = str(evidence.get("text") or "")
    if not doc_id or not source_url or not tickers or not evidence_page:
        return None
    cited_page = evidence.get("page")
    page_list = [str(p or "") for p in pages]
    cited_page_text = page_list[cited_page - 1] if isinstance(cited_page, int) and 0 < cited_page <= len(page_list) else evidence_text
    # A period may come from the title or the exact page cited by this fact;
    # never borrow a reporting header from a different page in the same PDF.
    period_end, inferred_type, period_flags = explicit_period_end(doc.get("title"), [cited_page_text])
    # All table-unit and consolidation decisions are made from the cited page,
    # never from an unrelated page's header.
    basis, basis_flags = consolidation_basis(f"{doc.get('title') or ''} {cited_page_text}")
    currency, multiplier, unit_flags = currency_and_scale(fact, cited_page_text)
    flags = sorted(set(period_flags + basis_flags + unit_flags))
    raw_value = fact.get("raw_value")
    normalized = fact.get("normalized_value")
    if multiplier and isinstance(raw_value, str):
        # Extractor normalized values are raw-value based.  Apply an explicit
        # table scale only when the raw value is a plain number (no suffix).
        if not re.search(r"\b(?:m|mn|million|bn|billion|thousand)\b", raw_value, re.I):
            try:
                number = float(raw_value.replace(",", ""))
                normalized = int(number * multiplier) if number.is_integer() else number * multiplier
            except ValueError:
                flags.append("unparseable_raw_value")
    metric = str(fact.get("fact_type") or "other")
    consolidation = basis or "unknown"
    period_type_value = inferred_type or "unknown"
    # The source fact identity is stable across a transient full-page pass and
    # a later durable-evidence rebuild.  Period/unit enrichment may improve on
    # the next run, so it must not create a second row for the same fact.
    series_seed = "|".join((tickers[0], metric, doc_id, str(fact.get("fact_id") or "")))
    series_id = "series_" + hashlib.sha256(series_seed.encode("utf-8")).hexdigest()[:24]
    return {
        "series_id": series_id, "ticker": tickers[0], "metric": metric,
        "period_end": period_end, "period_type": period_type_value,
        "consolidation": consolidation, "currency": currency,
        "unit": fact.get("unit"), "unit_multiplier": multiplier,
        "raw_value": raw_value, "normalized_value": normalized,
        "document_id": doc_id, "fact_id": fact.get("fact_id"),
        "source_url": source_url, "evidence": [{"page": evidence_page, "text": evidence_text}],
        "quality_flags": flags,
    }
