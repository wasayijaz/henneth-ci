"""Fetch dividend/payout history + book closures for every universe symbol.
Source: POST https://dps.psx.com.pk/payouts (symbol=SYM) -> HTML table
Columns: Symbol, Company, Sector, Dividend Announcement, Announced, Book Closure.

Dividend format: "50%(iii) (D)" = 50% of face value. PSX face value defaults to
Rs 10, but a stock split changes it (e.g. a 5-for-1 split takes Rs10 -> Rs2) and
PSX's own %-of-face text does NOT reflect that - it keeps quoting against the
OLD face value. Converting blindly at a hardcoded Rs10 silently overstates
dividend_rs (and yield_pct_at_close) by the split ratio for any name that has
split. (D)=cash dividend, (B)=bonus shares, (R)=right. Only (D) rows get cash
math. Book closure "06/05/2026 - 08/05/2026" is dd/mm/yyyy; you must own the
share BEFORE the ex-date (~2 sessions before closure start), so buy_by is
closure start minus 3 calendar days (conservative).

FACE VALUE: state/dividends_deep.json (Yahoo dividend events on the .KA
symbols) is already split-adjusted - it reports the true Rs/share paid, no
face-value math involved. calibrate_face_values() matches each PSX payout
(by book-closure date, within a window) to its Yahoo counterpart and, on a
match, uses the Yahoo Rs value directly. For a payout with no Yahoo match yet
(typically the newest/pending one - not ex'd, so absent from Yahoo) it falls
back to the most recent calibrated face value for that symbol, snapped to the
nearest canonical PSX denomination. A symbol with no deep coverage or no split
falls back to the Rs10 default, unchanged from before. This self-calibrates
per symbol every run - no hand-maintained split registry to go stale.

Writes state/dividends.json. Run daily pre-market (cheap: 1 POST per symbol)."""
import re
import time
from datetime import date, datetime, timedelta

import requests

from psx_data import HEADERS, STATE, load_json, save_json

FACE_VALUE = 10.0
CANONICAL_FACE_VALUES = [10.0, 5.0, 2.0, 1.0]      # PSX main-board denominations
DEEP_MATCH_WINDOW_DAYS = 45                         # book-closure <-> Yahoo ex-date tolerance
ROW_RE = re.compile(r"<tr><td>.*?</td></tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
DIV_RE = re.compile(r"([\d.]+)%(?:\(([ivxf]+)\))?\s*\(([DBR])\)", re.I)
BC_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")


def parse_rows(html: str, symbol: str) -> list[dict]:
    out = []
    for tr in ROW_RE.findall(html):
        cells = [TAG_RE.sub("", c).replace("&amp;", "&").strip() for c in CELL_RE.findall(tr)]
        if len(cells) < 6:
            continue
        m = DIV_RE.search(cells[3])
        bc = BC_RE.search(cells[5])
        if not m:
            continue
        pct, period, kind = float(m.group(1)), (m.group(2) or "").upper(), m.group(3).upper()
        row = {
            "symbol": symbol,
            "announcement": cells[3],
            "pct_of_face": pct,
            "period": period,          # I/II/III/IV interim, F final
            "kind": kind,              # D cash, B bonus, R right
            "dividend_rs": round(pct / 100 * FACE_VALUE, 2) if kind == "D" else None,
            "announced": cells[4],
        }
        if bc:
            try:
                s = datetime.strptime(bc.group(1), "%d/%m/%Y").date()
                e = datetime.strptime(bc.group(2), "%d/%m/%Y").date()
                row["bc_start"] = s.isoformat()
                row["bc_end"] = e.isoformat()
                row["buy_by"] = (s - timedelta(days=3)).isoformat()
                row["upcoming"] = s >= date.today()
            except ValueError:
                row["upcoming"] = False
        else:
            row["upcoming"] = False
        out.append(row)
    return out


def _nearest_deep_event(deep: list[dict], bc_start: str):
    """Closest Yahoo dividend event to a PSX book-closure start, or None if none within window."""
    if not deep or not bc_start:
        return None
    target = date.fromisoformat(bc_start)
    best, best_gap = None, None
    for ev in deep:
        try:
            gap = abs((date.fromisoformat(ev["ex"]) - target).days)
        except ValueError:
            continue
        if best_gap is None or gap < best_gap:
            best, best_gap = ev, gap
    if best is not None and best_gap <= DEEP_MATCH_WINDOW_DAYS:
        return best
    return None


def apply_correct_face_value(rows: list[dict], deep_tickers: dict):
    """Recompute dividend_rs for every cash-dividend row using dividends_deep.json as ground
    truth wherever a matching (already-ex'd) Yahoo event exists, falling back to the symbol's
    most recently calibrated face value for rows Yahoo hasn't seen yet (new/pending payouts).
    Mutates rows in place; returns {symbol: calibrated_face_value} for symbols where a split
    was detected, for logging."""
    by_symbol: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("kind") == "D" and row.get("pct_of_face"):
            by_symbol.setdefault(row["symbol"], []).append(row)

    calibrated = {}
    for sym, sym_rows in by_symbol.items():
        deep = deep_tickers.get(sym) or []
        if not deep:
            continue
        # Direct matches first: exact Yahoo-reported Rs value, no face-value math needed.
        matches = []  # (bc_start, implied_face_value) for rows we could match
        for row in sym_rows:
            ev = _nearest_deep_event(deep, row.get("bc_start"))
            if ev is None:
                continue
            row["dividend_rs"] = ev["rs"]
            implied = ev["rs"] / (row["pct_of_face"] / 100)
            matches.append((row["bc_start"], implied))
        if not matches:
            continue
        # Fallback face value for unmatched (pending) rows: most recent calibration, snapped to
        # the nearest canonical denomination so float drift in the Yahoo amount doesn't leak in.
        matches.sort(key=lambda m: m[0])
        implied_latest = matches[-1][1]
        face = min(CANONICAL_FACE_VALUES, key=lambda c: abs(c - implied_latest))
        if face != FACE_VALUE:
            calibrated[sym] = face
        for row in sym_rows:
            if _nearest_deep_event(deep, row.get("bc_start")) is None:
                row["dividend_rs"] = round(row["pct_of_face"] / 100 * face, 2)
    return calibrated


LISTED_DIV_PER_RUN = 60      # long-tail payout refresh budget per run (~35s at 0.35s each)


def main():
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    quant = load_json(STATE / "quant.json", {"tickers": {}})["tickers"]
    prior = load_json(STATE / "dividends.json", {"history": []})
    sess = requests.Session()
    sess.headers.update(HEADERS)

    all_rows, failed = [], []
    # Payout history is genuinely useful for every listed name, but one POST per symbol across
    # 554 names is too slow for a 30-minute cycle. Core every run; the listed tail rotates
    # stalest-first within a budget, so full coverage still arrives within a few cycles.
    # PSX ONLY — this posts to the DPS announcements endpoint, which has no US symbols, and
    # LISTED_DIV_PER_RUN is a bounded budget that must not be spent on names that cannot return.
    _syms = {s: m for s, m in universe["symbols"].items()
             if ((m or {}).get("market") or "PSX") == "PSX"}
    _core = [s for s, m in _syms.items() if (m or {}).get("tier", "core") == "core"]
    _listed = [s for s in _syms if s not in set(_core)]
    _seen = {d.get("symbol") for d in (prior.get("history") or [])} if isinstance(prior, dict) else set()
    _fresh = [s for s in _listed if s not in _seen]          # never fetched -> first in line
    _rest = [s for s in _listed if s in _seen]
    refreshed = set()
    for sym in _core + (_fresh + _rest)[:LISTED_DIV_PER_RUN]:
        try:
            r = sess.post("https://dps.psx.com.pk/payouts", data={"symbol": sym}, timeout=20)
            rows = parse_rows(r.text, sym) if r.status_code == 200 else []
            # Gate on ROWS, not on HTTP 200. `refreshed` tells the merge below to drop every prior
            # row for this symbol and keep only what we just parsed, so marking a symbol refreshed
            # on a 200 that yielded nothing (endpoint hiccup, markup change, parse miss) silently
            # deletes its entire payout history — and appends nothing to `failed`, so the run still
            # reports clean. A symbol with genuinely zero payouts has no prior rows to lose.
            if rows:
                refreshed.add(sym)
            all_rows.extend(rows)
        except requests.RequestException as e:
            failed.append({"symbol": sym, "err": str(e)[:80]})
        time.sleep(0.35)

    # MERGE, don't replace. history is written wholesale below, so without carrying the prior
    # rows forward every symbol outside this run's 60-name batch is DELETED — the opposite of
    # the rotation described above, which promises "full coverage still arrives within a few
    # cycles". Coverage would flicker rather than accumulate, and _seen (read back out of this
    # same file) could never grow past one batch. Keep prior rows for any symbol we did not
    # successfully re-fetch; a symbol that answered 200 is authoritative and overwrites.
    _today = date.today().isoformat()
    for row in (prior.get("history") or []) if isinstance(prior, dict) else []:
        if row.get("symbol") in refreshed:
            continue
        # `upcoming` was frozen at parse time (see parse_rows), so a retained row would keep
        # advertising a book closure that has since passed. Re-derive it from bc_start.
        bcs = row.get("bc_start")
        row["upcoming"] = bool(bcs) and bcs >= _today
        all_rows.append(row)

    # Correct dividend_rs for every row (fresh AND retained) against dividends_deep.json before
    # deriving yield — a retained row from before a split was detected would otherwise keep
    # publishing its old wrong Rs amount forever, since it's never re-parsed from PSX text.
    deep = load_json(STATE / "dividends_deep.json", {"tickers": {}}).get("tickers", {})
    calibrated = apply_correct_face_value(all_rows, deep)

    for row in all_rows:
        close = (quant.get(row["symbol"]) or {}).get("close")
        if row.get("dividend_rs") and close:
            row["yield_pct_at_close"] = round(row["dividend_rs"] / close * 100, 2)

    upcoming = sorted([r for r in all_rows if r.get("upcoming")], key=lambda r: r["bc_start"])
    save_json(STATE / "dividends.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "face_value_assumed": FACE_VALUE,
        "face_value_calibrated": calibrated,   # {symbol: current par value} for split names only
        "upcoming": upcoming,
        "history": all_rows,
        "failed": failed,
    })
    print(f"dividends: {len(all_rows)} payout records, {len(upcoming)} upcoming closures, {len(failed)} failed")
    if calibrated:
        print(f"  face-value split fix applied: {calibrated}")
    for u in upcoming[:8]:
        print(f"  {u['symbol']}: {u['announcement']} closure {u['bc_start']} buy-by {u['buy_by']}")


if __name__ == "__main__":
    main()
