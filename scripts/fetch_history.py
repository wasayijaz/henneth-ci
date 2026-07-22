"""Fetch/refresh daily EOD history for universe symbols.

Full history cached per symbol in state/history/{SYM}.json. Trims to config history_years.

BOUNDED BY DESIGN. The universe went from ~103 (KSE100+KMI30) to 554 (every KSE All Share
constituent), and this script used to re-pull EVERY symbol on EVERY run. At ~1.9s per symbol that
is ~17 minutes — but the cloud cron fires every 30 minutes, so a naive full sweep would run almost
continuously and risk overlapping runs.

So each run refreshes:
  * every `core` symbol (KSE100 + KMI30) — these drive signals and must be current;
  * any symbol with NO history file yet — first backfill has priority;
  * plus the STALEST `listed` symbols, up to LISTED_PER_RUN.

The long tail therefore refreshes on a rotation over a few cycles, which is entirely adequate for
names the desk shows prices and basic quant for but does not trade or backtest.
"""
import sys
import time

import requests

from psx_data import (STATE, eod_history, load_config, load_json, market_of, save_json,
                      yahoo_symbol)

LISTED_PER_RUN = 90        # long-tail refresh budget per run (~3 min at 1.9s each)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"}


def _yahoo_daily(symbol: str, universe: dict, years: int) -> list[dict]:
    """Daily EOD for a NON-PSX market, in the exact shape psx_data.eod_history returns.

    The shape is the whole point. `state/history/{SYM}.json` is the seam every expensive consumer
    reads — quant.py, backtest.py, predictability.py, compute_fairvalue.py, correlation.py — and
    none of them contains PSX-specific logic. Write a US series in the same shape and the entire
    analysis stack works on it unmodified. Nothing downstream needed changing to cover a second
    market; that is why this is four characters of URL and one dispatch, not a port."""
    rng = f"{max(2, years + 1)}y"
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(symbol, universe)}"
           f"?interval=1d&range={rng}")
    r = requests.get(url, headers=UA, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    res = (r.json().get("chart") or {}).get("result")
    if not res:
        raise RuntimeError("no result")
    ts = res[0].get("timestamp") or []
    q = res[0]["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(ts):
        c, o, v = q["close"][i], q["open"][i], q["volume"][i]
        if c is None:
            continue
        out.append({
            "date": time.strftime("%Y-%m-%d", time.gmtime(t)),
            "close": round(float(c), 2),
            "volume": int(v) if v else 0,
            # An index (^GSPC, ^VIX) has no open on some bars; fall back to the close rather than
            # dropping the bar, which would silently shorten the series the backtest sees.
            "open": round(float(o if o is not None else c), 2),
        })
    return out


def _pick(universe):
    """core + never-fetched first, then the stalest listed symbols up to the budget."""
    syms = universe["symbols"]
    core, listed = [], []
    for s, m in syms.items():
        (core if (m or {}).get("tier", "core") == "core" else listed).append(s)

    def age(s):
        p = STATE / "history" / f"{s}.json"
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0        # missing file sorts first — needs its initial backfill
    missing = [s for s in listed if age(s) == 0.0]
    rest = sorted((s for s in listed if age(s) > 0.0), key=age)
    budget = max(0, LISTED_PER_RUN - len(missing))
    return core + missing + rest[:budget], len(listed)


def main():
    cfg = load_config()
    universe = load_json(STATE / "universe.json", None)
    if not universe:
        print("FATAL: no universe.json — run update_universe.py first", file=sys.stderr)
        sys.exit(1)

    years = cfg["backtest"]["history_years"]
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - years * 365.25 * 86400))
    todo, n_listed = _pick(universe)
    ok, failed = 0, []
    for sym in todo:
        mkt = market_of(sym, universe)
        try:
            # DPS is authoritative for PSX (CLAUDE.md: prices come from the data layer). Every
            # other market has no DPS entry at all, so it routes to Yahoo — same output shape.
            src = eod_history(sym) if mkt == "PSX" else _yahoo_daily(sym, universe, years)
            hist = [d for d in src if d["date"] >= cutoff]
            # A recent listing legitimately has few bars — that is not a failure, and dropping it
            # would make the company invisible again. Keep anything with a usable series; only the
            # core tier needs the long history that signals and backtests depend on.
            tier = ((universe["symbols"].get(sym) or {}).get("tier", "core"))
            floor = 100 if tier == "core" else 20
            if len(hist) < floor:
                failed.append((sym, f"only {len(hist)} rows (tier {tier})"))
                continue
            save_json(STATE / "history" / f"{sym}.json", hist)
            ok += 1
        except Exception as e:  # noqa: BLE001 — degrade, don't crash the cycle
            failed.append((sym, str(e)[:80]))
        time.sleep(0.4)  # be polite to the upstream feed

    # Coverage map: which symbols actually have a usable price series. The All Share constituent
    # list includes PSX board artifacts that are not tradeable companies — ex-dividend (…XD) and
    # ex-bonus (…XB) counters, and non-compliant (…NC) counters — which return zero bars. Surfacing
    # those in search would be a worse bug than the one that started this (a missing real company),
    # so the dashboard filters search to symbols listed here. Written every run, never guessed.
    cov = {}
    for sym in universe["symbols"]:
        p = STATE / "history" / f"{sym}.json"
        try:
            n = len(load_json(p, []))
        except Exception:
            n = 0
        if n > 0:
            cov[sym] = n
    save_json(STATE / "coverage.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "n_with_history": len(cov),
        "n_universe": len(universe["symbols"]),
        "note": ("Symbols with a usable price series. Universe members absent here returned zero "
                 "bars from DPS — almost always non-tradeable board counters (…XD ex-dividend, "
                 "…XB ex-bonus, …NC non-compliant), not real listed companies."),
        "bars": cov,
    })

    save_json(STATE / "history_meta.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "ok": ok,
        "attempted": len(todo),
        "with_history": len(cov),
        "listed_total": n_listed,
        "listed_per_run": LISTED_PER_RUN,
        "note": ("Core symbols refresh every run; the listed long tail rotates on a stalest-first "
                 "budget so a 554-symbol universe cannot outrun the 30-minute cron."),
        "failed": [{"symbol": s, "err": e} for s, e in failed],
    })
    print(f"history: {ok} ok, {len(failed)} failed (attempted {len(todo)} of "
          f"{len(universe['symbols'])}; {n_listed} listed on rotation)")
    if failed:
        for s, e in failed[:10]:
            print(f"  {s}: {e}")


if __name__ == "__main__":
    main()
