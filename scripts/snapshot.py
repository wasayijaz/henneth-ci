"""Intraday snapshot for the light cycle: pulls market-watch once, writes
state/live.json for universe symbols (includes intraday high/low, which the EOD
feed lacks — these accumulate real OHLC going forward via state/ohlc_daily/)."""
import time

from psx_data import STATE, load_json, market_watch, save_json


def main():
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    snap = market_watch()
    today = time.strftime("%Y-%m-%d")
    live = {s: snap[s] for s in universe["symbols"] if s in snap}
    save_json(STATE / "live.json", {"updated": time.strftime("%Y-%m-%d %H:%M"), "tickers": live})

    # accumulate true OHLC per day (survives multiple snapshots; last one of the day wins)
    ohlc = load_json(STATE / "ohlc_daily" / f"{today}.json", {})
    for s, row in live.items():
        if row.get("open") is not None:
            ohlc[s] = {k: row[k] for k in ("open", "high", "low", "current", "volume")}
    save_json(STATE / "ohlc_daily" / f"{today}.json", ohlc)
    print(f"snapshot: {len(live)} universe symbols live")


if __name__ == "__main__":
    main()
