"""Fetch/refresh daily EOD history for universe symbols.

Full history cached per symbol in state/history/{SYM}.json. Trims to config history_years.

BOUNDED BY DESIGN. The universe went from ~103 (KSE100+KMI30) to 581 (every KSE All Share
constituent), and this script used to re-pull EVERY symbol on EVERY run. At ~1.9s per symbol that
is ~17 minutes — but the cloud cron fires every 30 minutes, so a naive full sweep would run almost
continuously and risk overlapping runs.

So each run refreshes:
  * every `core` symbol (KSE100 + KMI30) — these drive signals and must be current;
  * the least-recently-attempted `listed` symbols that already have a series, up to LISTED_PER_RUN
    (the attempt clock lives in state/history_meta.json — see _pick());
  * plus a small round-robin probe of listed symbols with NO history file yet (NEW_PROBE_PER_RUN).

Those last two budgets are SEPARATE and must stay separate — see the note on _pick().

The long tail therefore refreshes on a rotation over a few cycles, which is entirely adequate for
names the desk shows prices and basic quant for but does not trade or backtest.
"""
import sys
import time

import requests

from psx_data import (STATE, eod_history, load_config, load_json, market_of, save_json,
                      yahoo_symbol)

LISTED_PER_RUN = 90        # long-tail refresh budget per run (~3 min at 1.9s each)
NEW_PROBE_PER_RUN = 12     # separate, round-robin budget for symbols with no history file yet
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


def _pick(universe, cursor, attempts):
    """core + a bounded probe of never-fetched symbols + the least-recently-refreshed listed ones.

    THE TWO LONG-TAIL BUDGETS ARE SEPARATE, AND THAT SEPARATION IS THE WHOLE POINT.
    They used to be one: never-fetched symbols were prepended UNCAPPED and their count was
    subtracted from LISTED_PER_RUN. But the All Share constituent list carries ~103 PSX board
    counters (…NC non-compliant, …XD ex-dividend, …XB ex-bonus, rights) that are not companies
    and permanently return zero bars, so they never gain a history file and never left the
    never-fetched set. That made the rotation budget max(0, 90 - 103) = 0, and rest[:0] empty:
    not one listed symbol that already had a series was refreshed on ANY run, for 47 sessions,
    while health stayed green. The probe now has its own small budget and its own round-robin
    cursor, so a permanently-dead counter can delay a genuinely new listing by a few runs and
    can never again starve the refresh of companies the desk actually prices.

    THE ROTATION CLOCK IS PERSISTED STATE, NOT THE FILESYSTEM. It used to be the history file's
    st_mtime. That works locally and is meaningless in the cloud: every run starts with
    actions/checkout, which writes all 581 files fresh in git index order — alphabetical. So
    "stalest first" silently became "alphabetically first", the SAME 90 symbols were re-picked on
    every run forever, and everything from roughly the letter H onward (TATM among them) was never
    repriced again. The attempt timestamps below live in state/history_meta.json, which is committed
    by the cycle, so the clock survives checkout and the rotation actually rotates.

    Returns (todo, n_listed, next_cursor). The cursor is persisted in history_meta.json.
    """
    syms = universe["symbols"]
    core, listed = [], []
    for s, m in syms.items():
        (core if (m or {}).get("tier", "core") == "core" else listed).append(s)

    def has_file(s):
        return (STATE / "history" / f"{s}.json").exists()
    # Sorted, not universe-ordered, so the cursor addresses a stable list across runs.
    never = sorted(s for s in listed if not has_file(s))
    # Least-recently-attempted first; a symbol absent from the map has never been attempted under
    # the current clock and goes to the front. Alphabetical only as a tiebreak, so a cold start
    # converges over a few runs instead of standing still.
    have = sorted((s for s in listed if has_file(s)), key=lambda s: (attempts.get(s, ""), s))
    probe, nxt = [], 0
    if never:
        start = cursor % len(never)
        n = min(NEW_PROBE_PER_RUN, len(never))
        probe = [never[(start + i) % len(never)] for i in range(n)]
        nxt = (start + n) % len(never)
    return core + probe + have[:LISTED_PER_RUN], len(listed), nxt


def main():
    cfg = load_config()
    universe = load_json(STATE / "universe.json", None)
    if not universe:
        print("FATAL: no universe.json — run update_universe.py first", file=sys.stderr)
        sys.exit(1)

    years = cfg["backtest"]["history_years"]
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - years * 365.25 * 86400))
    prior = load_json(STATE / "history_meta.json", {}) or {}
    attempts = dict(prior.get("last_attempt") or {})
    todo, n_listed, next_cursor = _pick(universe, int(prior.get("probe_cursor") or 0), attempts)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    ok, failed = 0, []
    def fail(sym, err):
        failed.append((sym, err))

    for sym in todo:
        # Stamped before the fetch, not after, so a symbol that fails every run still moves to the
        # back of the queue instead of re-booking the same slot forever.
        attempts[sym] = stamp
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
                fail(sym, f"only {len(hist)} rows (tier {tier})")
                continue
            save_json(STATE / "history" / f"{sym}.json", hist)
            ok += 1
        except Exception as e:  # noqa: BLE001 — degrade, don't crash the cycle
            fail(sym, str(e)[:80])
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
        "new_probe_per_run": NEW_PROBE_PER_RUN,
        "probe_cursor": next_cursor,
        "note": ("Core symbols refresh every run. The listed symbols that HAVE a series rotate "
                 "least-recently-attempted first (see last_attempt), LISTED_PER_RUN each run, so "
                 "the whole tail is repriced every ~4 runs. Symbols with no series yet get a "
                 "separate round-robin probe (NEW_PROBE_PER_RUN, resumed from probe_cursor) so "
                 "the ~100 permanently-empty PSX board counters can never consume the refresh "
                 "budget. last_attempt is the rotation clock and MUST be persisted state — file "
                 "mtimes are rewritten by actions/checkout on every cloud run."),
        "last_attempt": {s: t for s, t in sorted(attempts.items()) if s in universe["symbols"]},
        "failed": [{"symbol": s, "err": e} for s, e in failed],
    })
    print(f"history: {ok} ok, {len(failed)} failed (attempted {len(todo)} of "
          f"{len(universe['symbols'])}; {n_listed} listed on rotation)")
    if failed:
        for s, e in failed[:10]:
            print(f"  {s}: {e}")


if __name__ == "__main__":
    main()
