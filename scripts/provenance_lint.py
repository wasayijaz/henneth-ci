#!/usr/bin/env python3
"""Accuracy / anti-assumption guard (Tier 1, deterministic, free) for the PSX Trade Desk.

The desk's whole credibility rests on NOT presenting assumed/placeholder/stale figures as
fact. Other gates check data shape (preflight), build (syntax), and design — none of them
ask "is what we're SHOWING actually grounded, current, and real?" This does, deterministically:

  1. PLACEHOLDER / STUB scan — no rendered state file may contain obvious stub markers
     (TODO / FIXME / PLACEHOLDER / TBD / lorem ipsum / <insert...>). Hard FAIL — there is no
     legitimate reason for a stub string to reach a user-facing field.
  2. HOLLOW ANALYSIS — a ticker with a Desk Room house_view whose summary/conviction is empty
     is presenting the *appearance* of analysis with no substance. Hard FAIL.
  3. STALE ANALYSIS — a house view computed at price_at_session that is now far from the
     current quant close is showing an out-of-date read as current. WARN (advisory: the desk
     is daily-timeframe so some drift is expected); hard FAIL only past a gross threshold.

Exit 0 = clean, 1 = a hard FAIL (do not publish). `--strict` makes warnings fail too.
No tokens, no network. Called by preflight.py so it gates every publish (cloud + local + app).
This is the free first line; the weekly /code-review + room-verifier remain the judgment layer.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state")

fails, warns = [], []

# Rendered, user-facing state files (NOT internal bookkeeping like *_meta / *_queue / *_plan).
RENDERED = [
    "daily_read.json", "macro.json", "rooms.json", "explainer.json", "fairvalue.json",
    "research_index.json", "leaderboard.json", "broker_scorecard.json", "dashboard.json",
    "legal.json", "astro.json", "astro_backtest.json",
]

# The astro pillar's whole defence is that its dates are COMPUTED, never recalled (CLAUDE.md
# Rule 2). A degraded or silently-wrong ephemeris must not reach users wearing the same
# confident face as a good one, so it is checked here rather than trusted.
AYANAMSA_RANGE = (23.5, 25.0)   # Lahiri drifts ~50"/yr: ~24.2 deg now, this band holds for decades

# Unambiguous stub markers only — deliberately excludes common legit words (example/test/sample
# on their own) to avoid false positives. These have no business in rendered data.
STUB = re.compile(r"\b(TODO|FIXME|PLACEHOLDER|TBD|REPLACE_ME|FILL[_ ]?IN|LOREM IPSUM|DUMMY DATA|SAMPLE DATA)\b"
                  r"|<INSERT|XXXX", re.IGNORECASE)

STALE_WARN_PCT = 15.0    # analysis price this far from current close -> advisory
STALE_FAIL_PCT = 30.0    # ... this far -> the shown read is materially wrong, block it


def load(name):
    p = os.path.join(STATE, name)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        fails.append(f"{name}: unparseable ({e})")
        return None


def walk_strings(obj, path=""):
    """Yield (json_path, string_value) for every string in a nested structure."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 1) placeholder / stub scan across rendered files
    for name in RENDERED:
        data = load(name)
        if data is None:
            continue
        for jpath, s in walk_strings(data):
            m = STUB.search(s)
            if m:
                fails.append(f"{name}: stub marker '{m.group(0)}' in field '{jpath}' — "
                             f"assumed/placeholder text would render as real content")

    # 2) hollow analysis + 3) stale analysis (Desk Room)
    rooms = load("rooms.json") or {}
    quant = (load("quant.json") or {}).get("tickers", {})
    for sym, sess in rooms.items():
        if not isinstance(sess, dict):
            continue
        hv = sess.get("house_view")
        if not hv:
            continue
        # hollow: the UI shows a "house view" section, but there's nothing in it
        if not (hv.get("summary") or "").strip() or not (hv.get("conviction") or "").strip():
            fails.append(f"rooms.json[{sym}]: house_view present but summary/conviction is empty "
                         f"— renders an empty analysis section as if the desk had a view")
        # stale: analysis was computed at a price now far from the live close
        p_sess = sess.get("price_at_session")
        p_now = (quant.get(sym) or {}).get("close")
        if isinstance(p_sess, (int, float)) and isinstance(p_now, (int, float)) and p_sess > 0:
            dev = abs(p_now / p_sess - 1) * 100
            if dev >= STALE_FAIL_PCT:
                fails.append(f"rooms.json[{sym}]: house view computed at Rs {p_sess} but close is now "
                             f"Rs {p_now} ({dev:.0f}% away) — the shown read is materially out of date")
            elif dev >= STALE_WARN_PCT:
                warns.append(f"rooms.json[{sym}]: house view {dev:.0f}% stale vs current close "
                             f"(computed at Rs {p_sess}, now Rs {p_now}) — refresh soon")

    # 4) astro: the ephemeris must be live, self-consistent, and sane — never a confident-looking stub
    astro = load("astro.json")
    if astro is not None:
        if astro.get("status") != "ok":
            warns.append(f"astro.json: status '{astro.get('status')}' ({astro.get('error')}) — "
                         f"the astro lens will show as unavailable rather than wrong")
        else:
            ayan = (astro.get("system") or {}).get("ayanamsa_deg")
            if not isinstance(ayan, (int, float)) or not (AYANAMSA_RANGE[0] <= ayan <= AYANAMSA_RANGE[1]):
                fails.append(f"astro.json: ayanamsa {ayan} is outside the sane Lahiri band "
                             f"{AYANAMSA_RANGE} — every sidereal position on the site would be wrong")
            pos = astro.get("positions") or {}
            missing = [b for b in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                                   "Rahu", "Ketu") if b not in pos]
            if missing:
                fails.append(f"astro.json: missing grahas {missing} — the nine-graha set is what the "
                             f"desk claims to compute")
            # Ketu is Rahu's exact opposite: the cheapest possible check that the maths is intact
            r, k = (pos.get("Rahu") or {}).get("lon"), (pos.get("Ketu") or {}).get("lon")
            if isinstance(r, (int, float)) and isinstance(k, (int, float)):
                if abs(((r - k) % 360) - 180) > 0.01:
                    fails.append(f"astro.json: Rahu {r} and Ketu {k} are not 180 deg apart — "
                                 f"the node computation is broken")
            if not (astro.get("events") or []):
                warns.append("astro.json: no events in the window — expected several per quarter")

    # report
    print("PSX Trade Desk - provenance/accuracy lint")
    if warns:
        print(f"\n  WARN ({len(warns)}):")
        for w in warns:
            print(f"    ! {w}")
    if fails:
        print(f"\n  FAIL ({len(fails)}):")
        for f in fails:
            print(f"    x {f}")
        print("\n  RESULT: DO NOT PUBLISH — assumed/hollow/stale content would reach users.")
        sys.exit(1)
    if args.strict and warns:
        print("\n  RESULT: blocked (--strict, warnings present).")
        sys.exit(1)
    print("\n  RESULT: OK — nothing assumed, hollow, or grossly stale in the rendered layer.")
    sys.exit(0)


if __name__ == "__main__":
    main()
