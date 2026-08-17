#!/usr/bin/env python3
"""Fetch compact company profiles from DPS public company pages.

Small 2.CI.0 source layer:
  - PSX-only, keyed by the desk's canonical universe symbols.
  - Top 20 most-liquid research-eligible pilot.
  - Monthly cadence, with --force and --limit for manual verification.
  - Merge/retain prior rows; failures keep the last good row and are recorded.

This is reference context for dossiers and explainers, not a trading signal.
Network failures degrade to stale/failed metadata and exit 0.
"""
import argparse
import html
import re
import sys
import time
from datetime import datetime

import requests

from psx_data import BASE, STATE, _get, load_json, market_symbols, research_symbols, save_json

OUT = STATE / "company_profiles.json"
PILOT_COUNT = 20
TTL_DAYS = 30
FAILED_RETRY_DAYS = 1
MAX_DESCRIPTION_CHARS = 700

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_BUSINESS_RE = re.compile(r"Business\s+Description.*?<p[^>]*>(.*?)</p>", re.I | re.S)
_INC_RE = re.compile(r"\bincorporated\b(?P<tail>.{0,220})", re.I | re.S)


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = _TAG_RE.sub(" ", value)
    return _WS_RE.sub(" ", value).strip()


def _clip(value: str, limit: int = MAX_DESCRIPTION_CHARS) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _parse_date(text: str) -> dict | None:
    for pattern, fmt in (
        (r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b", "%B %d, %Y"),
        (r"\b(\d{1,2} [A-Z][a-z]+ \d{4})\b", "%d %B %Y"),
        (r"\b([A-Z][a-z]+ \d{1,2} \d{4})\b", "%B %d %Y"),
    ):
        m = re.search(pattern, text)
        if not m:
            continue
        try:
            return {
                "precision": "date",
                "value": datetime.strptime(m.group(1), fmt).date().isoformat(),
                "matched_text": m.group(1),
            }
        except ValueError:
            continue
    m = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if m:
        return {"precision": "year", "value": m.group(1), "matched_text": m.group(1)}
    return None


def _incorporation(html_text: str) -> dict | None:
    text = _clean_text(html_text)
    m = _INC_RE.search(text)
    if not m:
        return None
    tail = _clean_text(m.group(0))
    parsed = _parse_date(tail) or {"precision": "mention", "value": None, "matched_text": tail[:160]}
    parsed["context"] = _clip(tail, 240)
    return parsed


def _business_description(html_text: str) -> str | None:
    m = _BUSINESS_RE.search(html_text)
    if not m:
        return None
    desc = _clean_text(m.group(1))
    return _clip(desc) if desc else None


def _profile(symbol: str) -> dict:
    response = _get(f"/company/{symbol}", retries=2, timeout=20)
    body = response.text
    desc = _business_description(body)
    inc = _incorporation(body)
    if not desc and not inc:
        raise RuntimeError("no profile fields parsed")
    return {
        "symbol": symbol,
        "source": "PSX DPS company page",
        "source_url": f"{BASE}/company/{symbol}",
        "fetched": time.strftime("%Y-%m-%d"),
        "business_description": desc,
        "incorporation": inc,
        "stale": False,
    }


def _target_symbols(limit: int | None) -> list[str]:
    universe = load_json(STATE / "universe.json", {"symbols": {}}).get("symbols", {})
    liquidity = load_json(STATE / "liquidity.json", {"tickers": {}}).get("tickers", {})
    allowed = set(market_symbols("PSX", research_symbols()))

    ranked = []
    for sym in allowed:
        meta = liquidity.get(sym) or {}
        if not meta.get("research_eligible"):
            continue
        try:
            adtv = float(meta.get("adtv_pkr") or 0)
        except (TypeError, ValueError):
            adtv = 0.0
        ranked.append((adtv, sym))
    if ranked:
        symbols = [sym for _, sym in sorted(ranked, key=lambda item: (-item[0], item[1]))]
    else:
        symbols = sorted(s for s in allowed if s in universe)

    cap = limit if limit is not None else PILOT_COUNT
    return symbols[:cap]


def _age_days(value: str | None, fmt: str) -> float | None:
    if not value:
        return None
    try:
        age = datetime.now() - datetime.strptime(value, fmt)
    except ValueError:
        return None
    if age.total_seconds() < 0:
        return None
    return age.total_seconds() / 86400


def _complete_row(row: dict | None) -> bool:
    return bool(
        row
        and not row.get("stale")
        and row.get("source_url")
        and (row.get("business_description") or row.get("incorporation"))
    )


def _symbols_due(prior: dict, symbols: list[str], force: bool, limit: int | None) -> list[str]:
    if force or limit is not None:
        return symbols

    last_attempt_age = _age_days(prior.get("updated"), "%Y-%m-%d %H:%M")
    retry_failed_now = last_attempt_age is None or last_attempt_age >= FAILED_RETRY_DAYS
    rows = prior.get("tickers", {}) or {}
    due = []
    waiting = 0
    for sym in symbols:
        row = rows.get(sym)
        fetched_age = _age_days(row.get("fetched") if isinstance(row, dict) else None, "%Y-%m-%d")
        if _complete_row(row) and fetched_age is not None and fetched_age < TTL_DAYS:
            continue
        if not _complete_row(row) and not retry_failed_now:
            waiting += 1
            continue
        due.append(sym)
    if not due:
        print("company_profiles: all pilot rows inside cadence "
              f"(good rows {TTL_DAYS}d, failed rows {FAILED_RETRY_DAYS}d)")
    elif waiting:
        print(f"company_profiles: {waiting} failed/incomplete row(s) waiting for "
              f"{FAILED_RETRY_DAYS}d retry cadence")
    return due


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="refresh even inside the monthly TTL")
    parser.add_argument("--limit", type=int, help="fetch only the first N pilot symbols for verification")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")

    prior = load_json(OUT, {"tickers": {}})
    targets = _target_symbols(args.limit)
    if not targets:
        print("company_profiles: no PSX research-eligible symbols found; leaving state untouched")
        return 0
    due = _symbols_due(prior, targets, args.force, args.limit)
    if not due:
        return 0

    rows = dict(prior.get("tickers") or {})
    failed = []
    fetched = 0
    for sym in due:
        try:
            rows[sym] = _profile(sym)
            fetched += 1
            print(f"  {sym}: profile captured")
        except (requests.RequestException, RuntimeError, ValueError) as e:
            failed.append({"symbol": sym, "error": f"{type(e).__name__}:{str(e)[:80]}"})
            if sym in rows:
                rows[sym] = {**rows[sym], "stale": True}
                print(f"  {sym}: failed, kept prior profile")
            else:
                print(f"  {sym}: failed, no prior profile")
        except Exception as e:  # noqa: BLE001 - provider parse failures must not crash the cycle
            failed.append({"symbol": sym, "error": f"{type(e).__name__}:{str(e)[:80]}"})
            if sym in rows:
                rows[sym] = {**rows[sym], "stale": True}
        time.sleep(0.25)

    save_json(OUT, {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "https://dps.psx.com.pk/company/{symbol}",
        "cadence_days": TTL_DAYS,
        "pilot": {
            "method": "Top 20 PSX research-eligible tickers by liquidity. Keys are desk universe symbols.",
            "target_count": len(targets),
            "symbols": targets,
            "due_this_run": due,
        },
        "stale": bool(failed),
        "degraded": bool(failed),
        "failed": failed,
        "tickers": rows,
    })
    print(f"company_profiles: {fetched} fetched, {len(failed)} failed, {len(rows)} retained")
    return 0


if __name__ == "__main__":
    sys.exit(main())
