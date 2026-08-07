"""Sector dossiers — the deterministic evidence pack the sector debate agents read.

WHY THIS EXISTS
  The Desk Room debates single tickers. Sector debates need the same discipline: agents must argue
  from a compiled evidence pack, never from memory (CLAUDE.md Rule 2). This script does ALL the
  arithmetic for free, so the agents spend tokens on judgement only.

  Everything here is derived from files the desk already produces:
    sectors.json      which tickers belong to which PSX sector
    quant.json        returns, RSI, liquidity, trend position
    fairvalue.json    model fair value + verdict per name
    fundamentals.json P/E, yield, payout, margins
    dividends_deep.json  18y of real payouts (for a sector income read)
    sector_macro.json which global factors measurably move this sector, with betas
    newslog.json      recent tagged news
    earnings_calendar.json  what reports next

OUTPUT  state/sector_dossiers.json  { updated, sectors: { "<Sector>": {...} } }

Idempotent, pure computation, no network. Safe to re-run; never crashes a cycle.
"""
import json
import statistics as st
from datetime import datetime, timezone, timedelta
from pathlib import Path

from psx_data import save_json

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
OUT = STATE / "sector_dossiers.json"
MIN_MEMBERS = 3          # below this a "sector view" is really a single-stock view


def load(name, default=None):
    try:
        return json.loads((STATE / name).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def fnum(x):
    try:
        return float(str(x).replace("%", "").replace(",", "").strip())
    except Exception:
        return None


def med(vals):
    vals = [v for v in vals if v is not None]
    return round(st.median(vals), 2) if vals else None


def main():
    sectors = load("sectors.json")
    quant = load("quant.json").get("tickers", {})
    fv = load("fairvalue.json").get("tickers", {})
    fund = load("fundamentals.json").get("tickers", {})
    deep = load("dividends_deep.json").get("tickers", {})
    smac = load("sector_macro.json").get("by_sector", {})
    news = load("newslog.json", [])
    cal = load("earnings_calendar.json").get("events", [])
    uni = load("universe.json").get("symbols", {})

    members = {}
    for sym, rec in (sectors.get("tickers") or {}).items():
        sec = (rec or {}).get("sector")
        if sec and sym in quant:
            members.setdefault(sec, []).append(sym)

    today = datetime.now(timezone.utc).date()
    cutoff_news = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    cutoff_div = (today - timedelta(days=365)).isoformat()

    out = {}
    for sec, syms in sorted(members.items()):
        if len(syms) < MIN_MEMBERS:
            continue
        rows = []
        for s in syms:
            q = quant.get(s, {})
            f = fund.get(s, {})
            v = fv.get(s, {})
            pays = [p for p in deep.get(s, []) if p.get("ex", "") >= cutoff_div]
            rows.append({
                "sym": s,
                "name": (uni.get(s) or {}).get("name", ""),
                "close": q.get("close"),
                "ret_1d": q.get("ret_1d"),
                "ret_20d": q.get("ret_20d"),
                "rsi14": q.get("rsi14"),
                "above_sma50": q.get("above_sma50"),
                "liquidity_rs_m": round((q.get("avg_daily_traded_value") or 0) / 1e6, 1),
                "pe": fnum(f.get("pe")),
                "div_yield_pct": fnum(f.get("div_yield")),
                "payout_pct": fnum(f.get("payout_ratio")),
                "fair_gap_pct": v.get("mispricing_pct"),
                "fair_verdict": v.get("verdict"),
                "ttm_dividend_rs": round(sum(p.get("rs", 0) for p in pays), 2) if pays else None,
            })
        rows.sort(key=lambda r: (r["ret_20d"] if r["ret_20d"] is not None else -999), reverse=True)

        # what actually moves this sector — measured, correction-survived (never assumed)
        rec = smac.get(sec, {})
        drivers = [{"factor": d["factor"], "corr": d["corr"], "beta": d["beta"], "p_value": d["p_value"]}
                   for d in (rec.get("drivers") or []) if d.get("demonstrated")]

        sec_news = []
        for n in news[-400:]:
            if n.get("ts", "") < cutoff_news:
                continue
            tk = [t for t in (n.get("tickers") or []) if t in syms]
            if tk:
                sec_news.append({"ts": n.get("ts", "")[:10], "impact": n.get("impact"),
                                 "tickers": tk, "headline": (n.get("headline") or "")[:160]})
        sec_news = sorted(sec_news, key=lambda x: (x.get("impact") or 0), reverse=True)[:8]

        upcoming = sorted(
            [{"ticker": e["ticker"], "date": e["date"], "type": e.get("type")}
             for e in cal if e.get("ticker") in syms and e.get("date", "") >= today.isoformat()],
            key=lambda e: e["date"])[:8]

        vals = [r for r in rows if r["fair_gap_pct"] is not None]
        under = [r for r in vals if r["fair_verdict"] == "undervalued"]
        over = [r for r in vals if r["fair_verdict"] == "overvalued"]

        out[sec] = {
            "n_members": len(rows),
            "breadth": {
                "above_sma50": sum(1 for r in rows if r["above_sma50"]),
                "advancing_1d": sum(1 for r in rows if (r["ret_1d"] or 0) > 0),
            },
            "returns": {
                "median_1d_pct": med([r["ret_1d"] for r in rows]),
                "median_20d_pct": med([r["ret_20d"] for r in rows]),
                "best_20d": {"sym": rows[0]["sym"], "pct": rows[0]["ret_20d"]} if rows else None,
                "worst_20d": {"sym": rows[-1]["sym"], "pct": rows[-1]["ret_20d"]} if rows else None,
            },
            "valuation": {
                "median_pe": med([r["pe"] for r in rows]),
                "median_fair_gap_pct": med([r["fair_gap_pct"] for r in rows]),
                "n_undervalued": len(under), "n_overvalued": len(over), "n_valued": len(vals),
            },
            "income": {
                "median_yield_pct": med([r["div_yield_pct"] for r in rows]),
                "median_payout_pct": med([r["payout_pct"] for r in rows]),
                "n_payers": sum(1 for r in rows if (r["div_yield_pct"] or 0) > 0),
            },
            "macro_drivers": drivers,
            "macro_joint_r2_pct": rec.get("joint_r2_pct"),
            "recent_news": sec_news,
            "upcoming_events": upcoming,
            "members": rows,
        }

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "note": ("Deterministic evidence pack per PSX sector. Every figure is computed from the "
                 "desk's own state files - agents debating a sector must cite THIS, never memory. "
                 "macro_drivers lists only correction-survived relationships; an empty list means "
                 "no global factor has a demonstrated effect on the sector, which is a finding."),
        "min_members": MIN_MEMBERS,
        "n_sectors": len(out),
        "sectors": out,
    }
    save_json(OUT, payload)
    print(f"sector_dossier: {len(out)} sectors "
          f"({sum(v['n_members'] for v in out.values())} members) -> {OUT.name}")


if __name__ == "__main__":
    main()
