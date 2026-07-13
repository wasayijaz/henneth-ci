#!/usr/bin/env python3
"""Desk Room — accountability engine (deterministic, zero tokens).

Resolves dated, falsifiable calls (from our personas AND from brokers) against
what prices actually did, then rolls up two leaderboards:
  - state/leaderboard.json      : our persona track records
  - state/broker_scorecard.json : brokers overall AND per sector (a broker's
                                  bank desk and E&P desk have different records)

Owner principle: brokers are audited, never trusted. The desk holds itself to the
exact same scoring. No LLM, no network — just claims vs realized prices.

A claim resolves once today >= resolve_by:
  - direction: hit if realized price moved the claimed way vs made_at_price
  - target:    error% = |realized - target| / target; hit if within TARGET_TOL
               OR realized reached/passed the target in the claimed direction
Sector rollups carry a min-sample floor so we never over-rank a thin record.
"""
import time
from datetime import datetime, timezone

from psx_data import STATE, load_json, save_json

TARGET_TOL = 0.10       # within 10% of a price target counts as a hit
MIN_SAMPLE = 5          # below this, a (broker, sector) cell is "unranked"


def _price_now(sym, quant, live):
    return (live.get(sym, {}) or {}).get("current") or (quant.get(sym, {}) or {}).get("close")


def _resolve(c, price_now):
    made = c.get("made_at_price")
    kind = c.get("kind")
    claim = c.get("claim") or {}
    if price_now is None or made is None:
        return None
    if kind == "direction":
        want_up = claim.get("direction") == "up"
        moved_up = price_now >= made
        hit = want_up == moved_up
        return {"status": "hit" if hit else "miss", "resolved_price": price_now,
                "detail": f"{'up' if moved_up else 'down'} vs claimed {claim.get('direction')}"}
    if kind == "target":
        tgt = claim.get("target_price")
        if not tgt:
            return None
        err = abs(price_now - tgt) / tgt
        reached = (price_now >= tgt) if price_now >= made else (price_now <= tgt)
        hit = err <= TARGET_TOL or reached
        return {"status": "hit" if hit else "miss", "resolved_price": price_now,
                "detail": f"target {tgt}, realized {round(price_now, 2)}, err {round(err * 100, 1)}%"}
    return None  # thesis claims are graded by the reviewer agent, not here


def run():
    led = load_json(STATE / "claims.json", {"claims": []})
    claims = led.get("claims", [])
    quant = load_json(STATE / "quant.json", {}).get("tickers", {})
    live = load_json(STATE / "live.json", {}).get("tickers", {})
    today = datetime.now(timezone.utc).date()

    # 1) resolve anything past its horizon
    for c in claims:
        if c.get("status") not in (None, "pending"):
            continue
        rb = c.get("resolve_by")
        try:
            due = datetime.strptime(rb, "%Y-%m-%d").date() <= today if rb else False
        except (ValueError, TypeError):
            due = False
        if not due:
            c["status"] = "pending"
            continue
        res = _resolve(c, _price_now(c.get("ticker"), quant, live))
        if res:
            c["status"] = res["status"]
            c["resolved_on"] = today.isoformat()
            c["resolved_price"] = res["resolved_price"]
            c["score_detail"] = res["detail"]

    # 2) roll up
    def blank():
        return {"n": 0, "hits": 0, "target_err_sum": 0.0, "target_n": 0}

    persona, broker, broker_sector = {}, {}, {}
    for c in claims:
        if c.get("status") not in ("hit", "miss"):
            continue
        src, styp, sect = c.get("source"), c.get("source_type"), c.get("sector") or "other"
        bucket = persona if styp == "persona" else broker
        b = bucket.setdefault(src, blank())
        b["n"] += 1
        b["hits"] += 1 if c["status"] == "hit" else 0
        if styp == "broker":
            bs = broker_sector.setdefault(src, {}).setdefault(sect, blank())
            bs["n"] += 1
            bs["hits"] += 1 if c["status"] == "hit" else 0
            if c.get("kind") == "target" and c.get("score_detail") and "err" in c["score_detail"]:
                try:
                    err = float(c["score_detail"].split("err")[1].strip().rstrip("%"))
                    for x in (b, bs):
                        x["target_err_sum"] += err
                        x["target_n"] += 1
                except (IndexError, ValueError):
                    pass

    def finalize(rec):
        out = {"calls": rec["n"], "hit_rate": round(rec["hits"] / rec["n"], 2) if rec["n"] else None}
        if rec["target_n"]:
            out["avg_target_err_pct"] = round(rec["target_err_sum"] / rec["target_n"], 1)
        return out

    leaderboard = {
        "personas": {k: finalize(v) for k, v in sorted(persona.items(), key=lambda kv: -(kv[1]["hits"]))},
        "_meta": {"built": time.strftime("%Y-%m-%d %H:%M"), "resolved_calls": sum(v["n"] for v in persona.values()),
                  "note": "Desk persona track records. Every persona's future prompt includes its own hit "
                          "rate + recent misses, so the desk is held to the standard it holds brokers to."},
    }
    scorecard = {"brokers": {}, "_meta": {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "min_sample_to_rank": MIN_SAMPLE,
        "note": "Brokers ranked overall AND per sector. Below min_sample a cell is 'unranked' (too few "
                "calls to trust). Brokers are evidence to cross-examine, never taken at face value."}}
    for name, rec in sorted(broker.items(), key=lambda kv: -(kv[1]["hits"])):
        entry = finalize(rec)
        entry["by_sector"] = {}
        for sect, srec in (broker_sector.get(name, {}) or {}).items():
            s = finalize(srec)
            s["ranked"] = srec["n"] >= MIN_SAMPLE
            entry["by_sector"][sect] = s
        scorecard["brokers"][name] = entry

    save_json(STATE / "claims.json", led)  # persist resolved statuses
    save_json(STATE / "leaderboard.json", leaderboard)
    save_json(STATE / "broker_scorecard.json", scorecard)
    resolved = sum(1 for c in claims if c.get("status") in ("hit", "miss"))
    print(f"score: {len(claims)} claims, {resolved} resolved | personas {len(persona)} brokers {len(broker)}")


if __name__ == "__main__":
    run()
