"""Intraday trigger scanner. Runs each light cycle after snapshot.

For every (ticker, strategy) pair proven eligible in state/strategy_map.json, checks
whether the strategy is triggering RIGHT NOW — appends today's DPS live bar to the
ticker's history and evaluates the strategy spec via the shared engine. TradingView
is NOT used (15-min delayed); DPS is the only intraday source.

Triggers are heads-up alerts + escalation; the full pipeline still vets them.
Writes state/live_triggers.json. One alert per (ticker, strategy) per day."""
import json
import time

import numpy as np

from alert import send_alert
from psx_data import ROOT, STATE, load_json, save_json
from strategy_engine import compute_indicators, signals

LIBRARY = {s["id"]: s for s in json.loads((ROOT / "strategies" / "library.json").read_text(encoding="utf-8"))}


def main():
    smap = load_json(STATE / "strategy_map.json", {"tickers": {}})["tickers"]
    live = load_json(STATE / "live.json", {"tickers": {}})["tickers"]
    today = time.strftime("%Y-%m-%d")
    prev = load_json(STATE / "live_triggers.json", {})
    seen = set(prev.get("alerted", [])) if prev.get("date") == today else set()

    triggers, alerted = [], list(seen)
    for sym, proven in smap.items():
        lv = live.get(sym)
        if not lv or not lv.get("current"):
            continue
        base = load_json(STATE / "history_deep" / f"{sym}.json", None) or load_json(STATE / "history" / f"{sym}.json", None)
        if not base or len(base) < 220:
            continue
        if base[-1]["date"] == today:
            base = base[:-1]
        bar = {"date": today, "open": lv.get("open") or lv["current"],
               "high": lv.get("high") or lv["current"], "low": lv.get("low") or lv["current"],
               "close": lv["current"], "volume": lv.get("volume") or 0}
        ind = compute_indicators(base + [bar])

        for p in proven:
            spec = LIBRARY.get(p["id"])
            if not spec:
                continue
            sig = signals(spec, ind)
            if not bool(sig[-1]):
                continue
            trig = {"ticker": sym, "id": p["id"], "name": p["name"], "category": p["category"],
                    "price": lv["current"], "ts": time.strftime("%H:%M"),
                    "backtest": {"hit_rate": p["hit_rate"], "net_expectancy_pct": p["net_expectancy_pct"], "n": p["n"]},
                    "target_pct": p["target_pct"], "stop_pct": p["stop_pct"], "hold": p["hold"]}
            triggers.append(trig)
            key = f"{sym}:{p['id']}"
            if key not in seen:
                send_alert("LIVE TRIGGER (unvetted)",
                           f"{sym} '{p['name']}' triggering @ {lv['current']} "
                           f"(hist hit {p['hit_rate']:.0%}, net {p['net_expectancy_pct']:+.1f}%, n={p['n']}). Full pipeline will vet.")
                alerted.append(key)

    save_json(STATE / "live_triggers.json", {
        "date": today, "updated": time.strftime("%Y-%m-%d %H:%M"),
        "triggers": triggers, "alerted": alerted})

    new = len(alerted) - len(seen)
    if new > 0:
        esc = load_json(STATE / "escalation.json", {})
        save_json(STATE / "escalation.json", {
            "escalate": True, "reason": f"{new} new live strategy trigger(s)",
            "tickers": sorted({t["ticker"] for t in triggers}),
            **({"prior": esc} if esc.get("escalate") else {})})
    print(f"scan_live: {len(triggers)} active triggers, {new if new > 0 else 0} new alerts")


if __name__ == "__main__":
    main()
