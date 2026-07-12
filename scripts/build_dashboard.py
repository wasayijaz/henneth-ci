"""Assemble state/dashboard.json deterministically from the state layer, so the
board always has fresh regime / movers / news / signals without depending on an LLM.
The orchestrator may still enrich agent_wire; this guarantees the core is populated.
Run at the end of every cycle (after data + agents)."""
import subprocess
import sys
import time
from pathlib import Path

from psx_data import STATE, load_json, save_json

SCRIPTS = Path(__file__).resolve().parent


def main():
    # deterministic derived layers (free, no LLM) — run via build_dashboard so the
    # already-deployed workflow picks them up without a workflow edit.
    for mod in ("compute_fairvalue", "build_signals"):
        try:
            __import__(mod).main()
        except Exception as e:  # noqa: BLE001 — never let a derived layer break the board
            print(f"{mod} skipped: {str(e)[:80]}")

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

    # PRE-DEPLOY GATE — this is the last step the CI pipeline runs before it copies
    # state/ into the published site (workflow runs it under `set -e`). preflight
    # trips only on STRUCTURAL corruption (empty quant, missing joined fields, NaN),
    # not on network-degraded-but-valid data, so a bad cycle aborts the job and the
    # last-good live site stays up instead of publishing a blank/broken board.
    gate = subprocess.run([sys.executable, str(SCRIPTS / "preflight.py")])
    if gate.returncode != 0:
        print("build_dashboard: PREFLIGHT FAILED — aborting so the broken board is NOT published")
        sys.exit(1)


if __name__ == "__main__":
    main()
