"""Assemble state/dashboard.json deterministically from the state layer, so the
board always has fresh regime / movers / news / signals without depending on an LLM.
The orchestrator may still enrich agent_wire; this guarantees the core is populated.
Run at the end of every cycle (after data + agents)."""
import subprocess
import sys
import time
from pathlib import Path

from psx_data import STATE, load_config, load_json, save_json

SCRIPTS = Path(__file__).resolve().parent


def main():
    # deterministic derived layers (free, no LLM) — run via build_dashboard so the
    # already-deployed workflow picks them up without a workflow edit.
    for mod in ("compute_fairvalue", "build_signals", "build_ownership_source_manifest",
                "build_company_scenario_lab", "build_ci_work_routing_policy"):
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

    # PUBLIC RULE CONSTANTS. The dashboard's Rule 4 checker needs the risk limits, but
    # config/desk.json must NEVER be served: it holds capital_pkr (the owner's actual
    # trading capital) and the Telegram bot token. So app.js had the numbers hardcoded a
    # second time, which drifts silently the moment config changes.
    #
    # Export the RULE CONSTANTS ONLY — an allow-list, not a blocklist, so a future secret
    # added to desk.json cannot leak by default. Capital stays out; the client already asks
    # the user for their own.
    risk = load_config().get("risk", {})
    save_json(STATE / "desk_rules.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "config/desk.json (risk block, rule constants only — no capital, no secrets)",
        "rules": {k: risk.get(k) for k in (
            "max_positions", "max_total_exposure_pct", "max_same_sector_positions",
            "risk_per_trade_pct", "max_pct_per_trade",
            "stale_setup_sessions", "stale_position_sessions",
            "circuit_breaker_stops", "circuit_breaker_window_sessions",
            "circuit_breaker_cooldown_sessions", "min_avg_daily_traded_value_pkr",
        ) if risk.get(k) is not None},
    })

    # THE PUBLIC PROBE. One file, deliberately ungated, whose entire job is to be fetchable
    # without a token so watchdog.py can prove /state/ is reachable and the deploy propagated.
    #
    # That role used to be played by natal_ephem.json, which was public for an unrelated reason
    # (the /cast funnel). Two problems with borrowing it. First, PUBLICATION_RESTRUCTURE.md §5
    # cuts personal astro — flag natal off and the watchdog's only unauthenticated content check
    # silently stops testing anything, passing meaninglessly. Second, an ephemeris is STATIC
    # physics: it cannot go stale, so it could never detect the stale deploy the watchdog exists
    # to catch.
    #
    # A purpose-built probe fixes both. It carries a timestamp, so staleness is now detectable
    # without a token for the first time. It follows desk_rules.json's allow-list discipline
    # above: it is built from a literal, so nothing can leak into it by default.
    save_json(STATE / "public_probe.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "gate": "account-required",
        "note": "Deliberately public. Exists so the deploy can be health-checked without a "
                "credential. Carries no desk output — every research file requires an account.",
    })

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
