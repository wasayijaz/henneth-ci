"""Fetch/refresh daily EOD history for every universe symbol.
Full history cached once per symbol in state/history/{SYM}.json, then this
just re-pulls (the endpoint returns full history anyway; cheap enough at ~65 symbols).
Trims to config history_years. Run daily pre-market."""
import sys
import time

from psx_data import STATE, eod_history, load_config, load_json, save_json


def main():
    cfg = load_config()
    universe = load_json(STATE / "universe.json", None)
    if not universe:
        print("FATAL: no universe.json — run update_universe.py first", file=sys.stderr)
        sys.exit(1)

    years = cfg["backtest"]["history_years"]
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - years * 365.25 * 86400))
    ok, failed = 0, []
    for sym in universe["symbols"]:
        try:
            hist = [d for d in eod_history(sym) if d["date"] >= cutoff]
            if len(hist) < 100:
                failed.append((sym, f"only {len(hist)} rows"))
                continue
            save_json(STATE / "history" / f"{sym}.json", hist)
            ok += 1
        except Exception as e:  # noqa: BLE001 — degrade, don't crash the cycle
            failed.append((sym, str(e)[:80]))
        time.sleep(0.4)  # be polite to DPS

    save_json(STATE / "history_meta.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "ok": ok,
        "failed": [{"symbol": s, "err": e} for s, e in failed],
    })
    print(f"history: {ok} ok, {len(failed)} failed")
    if failed:
        for s, e in failed[:10]:
            print(f"  {s}: {e}")


if __name__ == "__main__":
    main()
