#!/usr/bin/env python3
"""Pre-deploy guard for Henneth.

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
import ast
import glob
import json
import math
import os
import subprocess
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


def check_code_syntax():
    """Tier-1 code QA: a free, instant syntax gate on every publish (cloud + local + app
    tasks all route through this file). Catches "someone broke the build" before it ever
    reaches the live site — nothing else in the desk checked CODE syntax before this.
    This is NOT a substitute for the weekly /code-review deep pass (correctness, security,
    design) — just the fast, zero-cost first line that runs on literally every publish."""
    for path in sorted(glob.glob(os.path.join(ROOT, "scripts", "*.py"))):
        try:
            with open(path, encoding="utf-8") as f:
                ast.parse(f.read(), filename=path)
        except SyntaxError as e:
            fail(f"{os.path.relpath(path, ROOT)}: Python syntax error — {e.msg} (line {e.lineno})")

    # Every shipped dashboard/CI JavaScript file. Fail closed before either live surface builds.
    js_roots = [os.path.join(ROOT, "dashboard"), os.path.join(ROOT, "Henneth Desk 2.CI.0")]
    js_files = sorted(
        p for js_root in js_roots for p in glob.glob(os.path.join(js_root, "*.js"))
        if os.path.isfile(p)
    )
    node_missing = False
    for js_path in js_files:
        rel = os.path.relpath(js_path, ROOT).replace("\\", "/")
        try:
            r = subprocess.run(["node", "-c", js_path], capture_output=True, text=True, timeout=15)
            if r.returncode != 0:
                fail(f"{rel}: JS syntax error —\n{(r.stderr or r.stdout)[:300]}")
        except FileNotFoundError:
            if not node_missing:
                warn("shipped *.js: skipped JS syntax check — 'node' not found on this machine")
                node_missing = True
        except Exception as e:  # noqa: BLE001 — never let the checker itself crash the gate
            warn(f"{rel}: JS syntax check errored — {e}")


def check_provenance():
    """Tier-1 accuracy QA: run provenance_lint.py (placeholder/hollow/stale rendered content).
    A hard FAIL there means an assumed/empty/out-of-date value would reach users — block it."""
    lint = os.path.join(ROOT, "scripts", "provenance_lint.py")
    if not os.path.exists(lint):
        return
    try:
        r = subprocess.run([sys.executable, lint], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            # surface the lint's own FAIL lines (skip its header/blank lines)
            for line in r.stdout.splitlines():
                if line.strip().startswith("x "):
                    fail("provenance: " + line.strip()[2:])
            if not any(f.startswith("provenance:") for f in fails):
                fail("provenance_lint.py failed (see its output) — assumed/hollow/stale content")
    except Exception as e:  # noqa: BLE001
        warn(f"provenance_lint.py did not run — {e}")


def check_rule4():
    """Tier-1 maths QA: Rule 4 share counts and the payout-ratio sign guard.
    A FAIL here means a published golden case no longer matches CLAUDE.md — block deploy.
    The checker does not import production calculators, so it cannot rewrite them."""
    path = os.path.join(ROOT, "scripts", "check_rule4.py")
    if not os.path.exists(path):
        fail("check_rule4.py missing — Rule 4 golden cases cannot run")
        return
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            for line in (r.stdout or "").splitlines():
                if line.strip().startswith("x "):
                    fail("rule4: " + line.strip()[2:])
            if not any(f.startswith("rule4:") for f in fails):
                fail("check_rule4.py failed — " + ((r.stdout or r.stderr or "")[-200:]))
    except Exception as e:  # noqa: BLE001
        fail(f"check_rule4.py did not run — {e}")


def check_document_intelligence():
    """Offline fixtures plus live-state provenance for the CI document layer."""
    path = os.path.join(ROOT, "scripts", "check_document_intelligence.py")
    if not os.path.exists(path):
        fail("check_document_intelligence.py missing — CI evidence cannot be verified")
        return
    try:
        result = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            detail = (result.stdout or result.stderr or "")[-500:].strip()
            fail("document intelligence check failed — " + detail)
    except Exception as e:  # noqa: BLE001
        fail(f"check_document_intelligence.py did not run — {e}")


def check_company_brief_review():
    """Offline fixtures for the training-mode CI brief approval gate."""
    path = os.path.join(ROOT, "scripts", "company_brief_review.py")
    if not os.path.exists(path):
        fail("company_brief_review.py missing — CI synthesis approval cannot be verified")
        return
    try:
        result = subprocess.run([sys.executable, path, "self-check"], capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            detail = (result.stdout or result.stderr or "")[-500:].strip()
            fail("company brief review check failed — " + detail)
    except Exception as e:  # noqa: BLE001
        fail(f"company_brief_review.py did not run — {e}")


def check_financial_graph():
    """Offline fixtures for CI financial normalization and graph provenance."""
    path = os.path.join(ROOT, "scripts", "check_financial_graph.py")
    if not os.path.exists(path):
        fail("check_financial_graph.py missing — CI financial/graph contracts cannot be verified")
        return
    try:
        result = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            detail = (result.stdout or result.stderr or "")[-500:].strip()
            fail("financial graph check failed — " + detail)
    except Exception as e:  # noqa: BLE001
        fail(f"check_financial_graph.py did not run — {e}")


def check_synthesis_batch():
    """Offline fixture for token-bounded, receipt-aware CI synthesis batching."""
    path = os.path.join(ROOT, "scripts", "prepare_synthesis_batch.py")
    if not os.path.exists(path):
        fail("prepare_synthesis_batch.py missing — CI synthesis batching cannot be verified")
        return
    try:
        result = subprocess.run([sys.executable, path, "--self-check"], capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            detail = (result.stdout or result.stderr or "")[-500:].strip()
            fail("synthesis batch check failed — " + detail)
    except Exception as e:  # noqa: BLE001
        fail(f"prepare_synthesis_batch.py did not run — {e}")


def check_company_profiles():
    data, err = load("company_profiles.json")
    if data is None:
        fail(f"company_profiles.json: {err}")
        return
    rows = data.get("tickers")
    if not isinstance(rows, dict) or not rows:
        fail("company_profiles.json: missing populated tickers map")
        return
    pilot = data.get("pilot", {})
    expected = pilot.get("symbols") or []
    if expected and len(rows) < len(expected):
        fail(f"company_profiles.json: {len(rows)} rows for {len(expected)} pilot symbols")
    for sym, row in sorted(rows.items()):
        if not isinstance(row, dict):
            fail(f"company_profiles.json: {sym} row is not an object")
            continue
        if row.get("symbol") != sym:
            fail(f"company_profiles.json: {sym} row symbol mismatch")
        if not row.get("source_url"):
            fail(f"company_profiles.json: {sym} missing source_url")
        if not row.get("business_description") and not row.get("incorporation"):
            fail(f"company_profiles.json: {sym} has neither business_description nor incorporation")
        inc = row.get("incorporation")
        if inc is not None and not isinstance(inc, dict):
            fail(f"company_profiles.json: {sym} incorporation is not an object/null")


def check_ci_slice():
    path = os.path.join(ROOT, "Henneth Desk 2.CI.0", "data", "company_intelligence.json")
    if not os.path.exists(path):
        fail("Henneth Desk 2.CI.0/data/company_intelligence.json: missing generated CI slice")
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {e}")
        return
    if has_nonfinite(data):
        fail("Henneth Desk 2.CI.0/data/company_intelligence.json: contains NaN/Infinity")
    rows = data.get("tickers")
    if not isinstance(rows, list) or not rows:
        fail("Henneth Desk 2.CI.0/data/company_intelligence.json: no ticker rows")
        return
    for row in rows:
        sym = row.get("symbol") if isinstance(row, dict) else None
        if not sym:
            fail("Henneth Desk 2.CI.0/data/company_intelligence.json: row missing symbol")
            continue
        profile = row.get("profile") or {}
        if not profile.get("source_url"):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} profile missing source_url")
        if not profile.get("business_description") and not profile.get("incorporation"):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} profile has no parsed content")
        for key in ("filings", "timeline", "changes"):
            if not isinstance(row.get(key), list):
                fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} {key} is not a list")
        if not isinstance(row.get("financial_series"), dict):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} missing financial series")
        else:
            for fact in (row.get("financial_series") or {}).get("facts") or []:
                if not fact.get("document_id") or not fact.get("source_url") or not fact.get("evidence"):
                    fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} financial fact missing provenance")
                if fact.get("quality_flags") is None or not isinstance(fact.get("quality_flags"), list):
                    fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} financial fact flags invalid")
        graph = row.get("graph")
        if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} missing graph")
        if not isinstance(row.get("brief"), dict):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} missing brief status")
        if not isinstance(row.get("sources"), dict) or not isinstance(row.get("intelligence"), dict):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} missing intelligence/source maps")
        if (row.get("sources") or {}).get("status") not in ("ok", "degraded"):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} issuer monitor status missing")
        if not any(filing.get("status") == "ready" for filing in (row.get("filings") or [])):
            fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} has no ready official filing")
        for filing in row.get("filings") or []:
            if not filing.get("doc_id") or not filing.get("url"):
                fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} filing missing provenance")
            if filing.get("status") == "ready" and not filing.get("content_sha256"):
                fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} ready filing missing content hash")
            for evidence in filing.get("evidence") or []:
                if not isinstance(evidence.get("page"), int) or evidence["page"] < 1:
                    fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} invalid evidence page")
                if not evidence.get("text") or not evidence.get("source_url"):
                    fail(f"Henneth Desk 2.CI.0/data/company_intelligence.json: {sym} incomplete evidence")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # never die on a unicode dash in a message
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = ap.parse_args()

    # --- Tier-1 code QA: instant, free, blocks a broken build before anything else runs ---
    check_code_syntax()
    # --- Tier-1 accuracy QA: block assumed/hollow/stale content from reaching users ---
    check_provenance()
    # --- Tier-1 maths QA: Rule 4 + payout sign guard ---
    check_rule4()
    check_document_intelligence()
    check_company_brief_review()
    check_financial_graph()
    check_synthesis_batch()
    # --- Company intelligence shape: every populated row, not a sample ---
    check_company_profiles()
    check_ci_slice()

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

    # Per-ticker history completeness — the "No data for XXX" class: a symbol in the
    # universe with a missing/empty history/{sym}.json renders a dead ticker page that
    # the client CANNOT self-heal (the file genuinely isn't on the server). Gate it here.
    #
    # Distinguish REGRESSED tickers (previously covered — present in quant.json — now
    # missing, a real broken-cycle signal) from BRAND-NEW-TO-THE-UNIVERSE tickers (never
    # covered before, still backfilling — e.g. right after a universe expansion). Only
    # regressions count toward the hard FAIL threshold; new tickers only ever WARN, so
    # widening the universe can never block publishing everything else while it backfills.
    uni, _ = load("universe.json")
    quant_prev, _ = load("quant.json")
    prev_covered = set((quant_prev or {}).get("tickers", {})) if quant_prev else set()
    if uni and isinstance(uni.get("symbols"), dict):
        symbols = list(uni["symbols"])
        hist_dir = os.path.join(STATE, "history")
        missing = []
        for s in symbols:
            p = os.path.join(hist_dir, f"{s}.json")
            try:
                if not os.path.exists(p) or os.path.getsize(p) < 20:
                    missing.append(s)
                    continue
                with open(p, encoding="utf-8") as f:
                    if len(json.load(f)) < 2:      # need at least a couple of bars to render
                        missing.append(s)
            except Exception:
                missing.append(s)
        if symbols:
            regressed = [s for s in missing if s in prev_covered]
            new_backfilling = [s for s in missing if s not in prev_covered]
            frac = len(regressed) / len(symbols)
            # a few missing is tolerable (a new listing mid-fetch); a broad REGRESSION is a broken cycle
            if frac > 0.10:
                fail(f"history/: {len(regressed)}/{len(symbols)} previously-covered tickers lost their "
                     f"history ({frac:.0%}) — their ticker pages would show 'No data'. e.g. {', '.join(regressed[:8])}")
            elif regressed:
                warn(f"history/: {len(regressed)} previously-covered ticker(s) missing history (pages "
                     f"self-heal-retry but stay empty until refetched): {', '.join(regressed[:12])}")
            if new_backfilling:
                warn(f"history/: {len(new_backfilling)} newly-added universe ticker(s) still backfilling "
                     f"history (never gates publish): {', '.join(new_backfilling[:12])}")

    # Desk Room layer (advisory — WARN not FAIL while the loop is young, so a missing
    # dossier can't block the core desk from deploying)
    check("dossiers.json", required=False)
    check("room_queue.json", required=False)
    dj, _ = load("dossiers.json")
    if dj and dj.get("_meta", {}).get("n_tickers", 0) < 10:
        warn("dossiers.json: fewer than 10 tickers compiled")

    # health gate: if the desk itself says data is bad, warn loudly
    h, _ = load("health.json")
    if h and h.get("status") not in ("ok", "healthy", None):
        warn(f"health.json status = '{h.get('status')}' — desk is in degraded mode")

    # --- report ---
    print("Henneth - preflight")
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
