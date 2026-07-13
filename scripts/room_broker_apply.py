#!/usr/bin/env python3
"""Desk Room — record harvested broker calls (deterministic, zero tokens).

Takes the broker-harvester agent's returned calls (written by the weekly task to
state/room_tmp/broker_calls.json) and records each as:
  - a broker note in state/research_index.json  (shows on the Research page)
  - a dated claim in state/claims.json           (source_type "broker" -> scored ->
                                                   broker leaderboard, overall + per sector)
Idempotent: a call is keyed by broker+ticker+date+value so re-runs don't duplicate.
The desk records these to GRADE the brokers, never to follow them.

Usage: python scripts/room_broker_apply.py   (reads state/room_tmp/broker_calls.json)
"""
import hashlib
import json
import time

from psx_data import STATE, load_json, save_json

TMP = STATE / "room_tmp" / "broker_calls.json"


def _key(c):
    claim = c.get("claim") or {}
    raw = f"{c.get('broker')}|{c.get('ticker')}|{c.get('made_on')}|{claim.get('target_price')}|{claim.get('rating')}"
    return "bk:" + hashlib.sha1(raw.encode()).hexdigest()[:12]


def main():
    if not TMP.exists():
        print("  no broker_calls.json staged — nothing to record")
        return
    txt = TMP.read_text(encoding="utf-8").strip()
    if txt.startswith("```"):
        txt = txt.split("```", 2)[1].lstrip("json").strip()
    try:
        payload = json.loads(txt)
    except json.JSONDecodeError as e:
        print(f"  broker_calls.json unparseable: {e}")
        return
    calls = payload.get("calls", []) if isinstance(payload, dict) else payload
    if not calls:
        print("  harvester found 0 verifiable broker calls this week (honest result)")
        TMP.unlink(missing_ok=True)
        return

    idx = load_json(STATE / "research_index.json", {"documents": {}, "by_ticker": {}, "_meta": {}})
    led = load_json(STATE / "claims.json", {"claims": []})
    quant = load_json(STATE / "quant.json", {}).get("tickers", {})
    existing = {c.get("id") for c in led.get("claims", [])}
    added_docs = added_claims = 0

    for c in calls:
        if not (c.get("broker") and c.get("ticker") and c.get("url") and c.get("made_on")):
            continue  # every call needs broker + ticker + source + date
        key = _key(c)
        claim = c.get("claim") or {}
        # research-index broker note
        if key not in idx["documents"]:
            idx["documents"][key] = {
                "hash": key, "source": c["broker"], "source_type": "broker",
                "doc_type": "company_note", "date": c["made_on"], "tickers": [c["ticker"]],
                "digest": claim.get("text") or "",
                "digest_level": "full", "url": c.get("url"),
                "claims": [claim], "omissions": None,
            }
            entry = {"hash": key, "source": c["broker"], "doc_type": "broker call",
                     "date": c["made_on"], "one_line": (claim.get("text") or "")[:90], "url": c.get("url")}
            lst = idx["by_ticker"].setdefault(c["ticker"], [])
            if not any(e.get("hash") == key for e in lst):
                lst.insert(0, entry)
                del lst[8:]
            added_docs += 1
        # scoreable claim
        cid = "claim:" + key
        if cid not in existing:
            hd = c.get("horizon_days") or 90
            try:
                from datetime import datetime, timedelta
                resolve_by = (datetime.strptime(c["made_on"], "%Y-%m-%d") + timedelta(days=hd)).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                resolve_by = None
            led["claims"].append({
                "id": cid, "source_type": "broker", "source": c["broker"],
                "sector": c.get("sector", "other"), "ticker": c["ticker"],
                "made_on": c["made_on"], "horizon_days": hd, "resolve_by": resolve_by,
                "kind": c.get("kind", "target"),
                "claim": {"direction": claim.get("direction"), "target_price": claim.get("target_price"),
                          "text": claim.get("text", "")},
                # baseline for scoring: current close (best available proxy for the call date)
                "made_at_price": (quant.get(c["ticker"], {}) or {}).get("close"),
                "status": "pending", "source_url": c.get("url"),
            })
            added_claims += 1

    idx["_meta"]["built"] = time.strftime("%Y-%m-%d %H:%M")
    idx["_meta"]["n_documents"] = len(idx["documents"])
    save_json(STATE / "research_index.json", idx)
    save_json(STATE / "claims.json", led)
    TMP.unlink(missing_ok=True)
    print(f"broker calls recorded: {added_docs} notes, {added_claims} scoreable claims")


if __name__ == "__main__":
    main()
