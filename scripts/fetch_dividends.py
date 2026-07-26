"""Fetch dividend/payout history + book closures for every universe symbol.
Source: POST https://dps.psx.com.pk/payouts (symbol=SYM) -> HTML table
Columns: Symbol, Company, Sector, Dividend Announcement, Announced, Book Closure.

Dividend format: "50%(iii) (D)" = 50% of face value (PSX face value is Rs 10 for
nearly all mains, so 50% = Rs 5.00/share). (D)=cash dividend, (B)=bonus shares,
(R)=right. Only (D) rows get cash math. Book closure "06/05/2026 - 08/05/2026"
is dd/mm/yyyy; you must own the share BEFORE the ex-date (~2 sessions before
closure start), so buy_by is closure start minus 3 calendar days (conservative).

Writes state/dividends.json. Run daily pre-market (cheap: 1 POST per symbol)."""
import re
import time
from datetime import date, datetime, timedelta

import requests

from psx_data import HEADERS, STATE, load_json, save_json

FACE_VALUE = 10.0
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
            if r.status_code == 200:
                refreshed.add(sym)
            close = (quant.get(sym) or {}).get("close")
            for row in rows:
                if row.get("dividend_rs") and close:
                    row["yield_pct_at_close"] = round(row["dividend_rs"] / close * 100, 2)
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

    upcoming = sorted([r for r in all_rows if r.get("upcoming")], key=lambda r: r["bc_start"])
    save_json(STATE / "dividends.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "face_value_assumed": FACE_VALUE,
        "upcoming": upcoming,
        "history": all_rows,
        "failed": failed,
    })
    print(f"dividends: {len(all_rows)} payout records, {len(upcoming)} upcoming closures, {len(failed)} failed")
    for u in upcoming[:8]:
        print(f"  {u['symbol']}: {u['announcement']} closure {u['bc_start']} buy-by {u['buy_by']}")


if __name__ == "__main__":
    main()
