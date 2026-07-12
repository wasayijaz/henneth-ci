#!/usr/bin/env python3
"""Pre-deploy guard for the PSX Trade Desk.

Runs AFTER the data pipeline and BEFORE anything is published. It re-reads
every state file the dashboard actually consumes and asserts the shape the
UI depends on. If a check fails, it exits non-zero so the deploy is aborted
with a blank/broken board never reaching the live site.

Design rule: this catches the class of bug where a fetch degrades and a file
ends up empty or missing a field the UI joins on (e.g. quant.json without
rsi14 -> every RSI cell blanks). Cheap, deterministic, no tokens, no network.

Usage:
    python scripts/preflight.py            # human report, exit 1 on FAIL
    python scripts/preflight.py --strict   # WARN also fails (use in CI)

Exit codes: 0 = safe to deploy, 1 = do not deploy.
"""
import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state")

fails, warns = [], []


def fail(msg):
    fails.append(msg)


def warn(msg):
    warns.append(msg)


def load(name):
    """Load a state file; None if missing/unparseable (recorded as FAIL by caller)."""
    p = os.path.join(STATE, name)
    if not os.path.exists(p):
        return None, "missing"
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)


def has_nonfinite(obj):
    """True if any float in the structure is NaN/Infinity (breaks browser JSON.parse)."""
    if isinstance(obj, float):
        return not math.isfinite(obj)
    if isinstance(obj, dict):
        return any(has_nonfinite(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_nonfinite(v) for v in obj)
    return False


def check(name, required=True, min_tickers=0, ticker_fields=(), top_keys=()):
    """Generic structural check for a state file."""
    data, err = load(name)
    if data is None:
        (fail if required else warn)(f"{name}: {err}")
        return None
    if has_nonfinite(data):
        fail(f"{name}: contains NaN/Infinity — will break JSON.parse in the browser")
    for k in top_keys:
        if k not in data:
            fail(f"{name}: missing top-level key '{k}'")
    if min_tickers or ticker_fields:
        t = data.get("tickers", {})
        if not isinstance(t, dict) or len(t) < min_tickers:
            fail(f"{name}: only {len(t) if isinstance(t, dict) else 0} tickers (expected >= {min_tickers})")
        elif ticker_fields:
            # sample up to 5 tickers; every one must carry the joined fields
            sample = list(t.items())[:5]
            for sym, v in sample:
                for fld in ticker_fields:
                    if fld not in v or v[fld] is None:
                        fail(f"{name}: ticker {sym} missing '{fld}' (the UI joins on this — cells would blank)")
                        break
    return data


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # never die on a unicode dash in a message
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = ap.parse_args()

    # --- files the dashboard hard-depends on, with the exact shape the UI reads ---
    check("health.json", top_keys=("status",))
    check("quant.json", min_tickers=20, ticker_fields=("rsi14", "ret_20d", "close"))
    check("predictability.json", min_tickers=20)
    check("fairvalue.json", min_tickers=10, ticker_fields=("methods", "composite_fair", "verdict"))
    check("global.json", top_keys=("instruments",))
    check("dashboard.json")
    check("macro.json", top_keys=("regime",))

    # global.json must actually carry instruments (the ticker tape + macro page)
    gl, _ = load("global.json")
    if gl and not gl.get("instruments"):
        fail("global.json: instruments is empty — ticker tape and macro page go blank")

    # fairvalue methods must be non-empty per ticker (the new value working depends on it)
    fv, _ = load("fairvalue.json")
    if fv:
        empties = [s for s, v in list(fv.get("tickers", {}).items())[:10]
                   if not v.get("methods")]
        if empties:
            fail(f"fairvalue.json: tickers with empty methods: {', '.join(empties)}")

    # health gate: if the desk itself says data is bad, warn loudly
    h, _ = load("health.json")
    if h and h.get("status") not in ("ok", "healthy", None):
        warn(f"health.json status = '{h.get('status')}' — desk is in degraded mode")

    # --- report ---
    print("PSX Trade Desk - preflight")
    if warns:
        print(f"\n  WARN ({len(warns)}):")
        for w in warns:
            print(f"    ! {w}")
    if fails:
        print(f"\n  FAIL ({len(fails)}):")
        for f in fails:
            print(f"    x {f}")
        print("\n  RESULT: DO NOT DEPLOY — fix the above first.")
        sys.exit(1)
    if args.strict and warns:
        print("\n  RESULT: blocked (--strict, warnings present).")
        sys.exit(1)
    print(f"\n  RESULT: OK — {0 if fails else 'all'} checks passed, safe to deploy.")
    sys.exit(0)


if __name__ == "__main__":
    main()
