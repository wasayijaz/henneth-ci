"""Assemble state/dashboard.json deterministically from the state layer, so the
board always has fresh regime / movers / news / signals without depending on an LLM.
The orchestrator may still enrich agent_wire; this guarantees the core is populated.
Run at the end of every cycle (after data + agents)."""
import time

from psx_data import STATE, load_json, save_json


def main():
    quant = load_json(STATE / "quant.json", {"tickers": {}})["tickers"]
    macro = load_json(STATE / "macro.json", {})
    geo = load_json(STATE / "georisk.json", {})
    news = load_json(STATE / "newslog.json", [])
    pred = load_json(STATE / "predictability.json", {"tickers": {}})["tickers"]
    signals = load_json(STATE / "signals.json", {"active": []})
    positions = load_json(STATE / "positions.json", {"open": []})
    runlog = load_json(STATE / "runlog.json", [])
    prev = load_json(STATE / "dashboard.json", {})

    movers = sorted(quant.items(), key=lambda kv: -(kv[1].get("ret_1d") or 0))
    top = [{"ticker": s, "ret_1d": v["ret_1d"], "close": v["close"]} for s, v in movers[:5]]
    bottom = [{"ticker": s, "ret_1d": v["ret_1d"], "close": v["close"]} for s, v in movers[-5:]]
    top_pred = sorted(pred.items(), key=lambda kv: -kv[1]["score"])[:10]

    dash = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "regime": macro.get("regime", "unknown"),
        "geo_risk": {"score": geo.get("score"), "band": geo.get("band")} if geo else None,
        "signals": signals.get("active", []),
        "positions": positions.get("open", []),
        "top_predictable": [{"ticker": s, "score": v["score"]} for s, v in top_pred],
        "movers_up": top, "movers_down": bottom,
        "news": news[-15:],
        # keep whatever the orchestrator/agents last wrote for agent_wire, else a note
        "agent_wire": prev.get("agent_wire", []),
        "runlog_tail": runlog[-5:],
    }
    save_json(STATE / "dashboard.json", dash)
    print(f"dashboard: regime={dash['regime']} geo={dash['geo_risk']} "
          f"movers={len(top)}/{len(bottom)} news={len(dash['news'])}")


if __name__ == "__main__":
    main()
