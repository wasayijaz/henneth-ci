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

from psx_data import STATE, eod_history, load_config, load_json, save_json

LISTED_PER_RUN = 90        # long-tail refresh budget per run (~3 min at 1.9s each)


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
        try:
            hist = [d for d in eod_history(sym) if d["date"] >= cutoff]
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
        time.sleep(0.4)  # be polite to DPS

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
