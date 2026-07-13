#!/usr/bin/env python3
"""Desk Room — the efficiency gate (deterministic, zero tokens).

Decides the CHEAPEST valid action per ticker so the agent loop almost never pays
for a full debate. This is what makes "keep the whole universe updated" affordable.

Per ticker, comparing the current dossier's material_hash to the hash stored in its
last Room session:
  REAFFIRM (Tier 0, 0 tokens)  : material fields unchanged -> last house view stands,
                                 just re-stamp "as of today". No agents run.
  DELTA    (Tier 1, ~4-6k)     : material fields unchanged BUT price moved enough that
                                 the technical read is stale -> refresh TA memo only.
  FULL     (Tier 2, ~25k)      : material change (verdict/scorecard/docs/high-impact
                                 news/earnings) OR never covered -> full 5-persona debate.

Output: state/room_plan.json -> what the daily/hourly task should actually run today,
already capped at budget.deep_dives_per_day FULLs. Everything else reaffirms for free.
"""
import time

from psx_data import STATE, load_json, save_json

PRICE_DELTA_TRIGGER = 4.0   # % move since last session that makes the TA read worth refreshing


def build():
    dossiers = load_json(STATE / "dossiers.json", {})
    rooms = load_json(STATE / "rooms.json", {})
    budget = load_json(STATE / "budget.json", {})
    cap = budget.get("deep_dives_per_day", 3)

    plan = {"reaffirm": [], "delta": [], "full": [], "_meta": {}}
    for sym, d in dossiers.items():
        if sym == "_meta":
            continue
        prior = rooms.get(sym)
        cur_hash = d.get("material_hash")
        if not prior or not prior.get("house_view"):
            plan["full"].append({"symbol": sym, "why": "never covered"})
            continue
        if prior.get("material_hash") != cur_hash:
            plan["full"].append({"symbol": sym, "why": "material change since last Room"})
            continue
        # material unchanged -> is a cheap price refresh warranted?
        cur_px = d.get("price")
        old_px = prior.get("price_at_session")
        moved = (abs(cur_px - old_px) / old_px * 100) if (cur_px and old_px) else 0
        if moved >= PRICE_DELTA_TRIGGER:
            plan["delta"].append({"symbol": sym, "why": f"price moved {moved:.1f}% since last Room"})
        else:
            plan["reaffirm"].append(sym)

    # respect the daily FULL budget: keep the highest-priority FULLs, spill the rest to tomorrow.
    # priority = order from room_queue.json (events/news first); fall back to dossier order.
    queue = load_json(STATE / "room_queue.json", {}).get("ranked", [])
    rank = {r["symbol"]: i for i, r in enumerate(queue)}
    plan["full"].sort(key=lambda x: rank.get(x["symbol"], 999))
    run_now = plan["full"][:cap]
    deferred = plan["full"][cap:]

    plan["_meta"] = {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "full_budget": cap,
        "run_full_now": [x["symbol"] for x in run_now],
        "deferred_full": [x["symbol"] for x in deferred],
        "counts": {"full_due": len(plan["full"]), "full_now": len(run_now),
                   "delta": len(plan["delta"]), "reaffirm": len(plan["reaffirm"])},
        "est_tokens_today": len(run_now) * budget.get("est_tokens_per_deep_dive", 25000)
                            + len(plan["delta"]) * 5000,
        "note": "Tiered plan. Only run_full_now get the 5-persona debate; delta get a cheap TA "
                "refresh; reaffirm cost nothing. Full universe stays current at a fraction of "
                "naive cost (naive = every ticker debated every run).",
    }
    save_json(STATE / "room_plan.json", plan)
    c = plan["_meta"]["counts"]
    print(f"gate: full_due={c['full_due']} (run {len(run_now)}/{cap}) delta={c['delta']} "
          f"reaffirm={c['reaffirm']} | est ~{plan['_meta']['est_tokens_today']//1000}k tokens today")
    return plan


if __name__ == "__main__":
    build()
