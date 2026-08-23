#!/usr/bin/env python3
"""Desk Room — deterministic QA verifier (zero tokens).

The first, free layer of the "verify everything the user sees" system. It re-derives
and cross-checks every user-facing number against its own source and flags anything
that doesn't hold up — the class of bug that put a glitch-driven "83% drop" on screen.
What it cannot settle (a genuinely factual claim, e.g. "when did UBL actually fall
that hard") is escalated to the LLM room-verifier agent, which web-checks it.

Checks per ticker, writing state/verify.json = { SYM: [issues], ..., _meta }:
  - price-series glitches: any |1-day move| > 40% in the SERVED deep/near history
  - drawdown honesty: an extreme all-time drawdown (>70%) that is OLD must be paired
    with a recent-decade number (the UI now does this; flagged if the data can't support it)
  - fair value integrity: methods present, composite == median(methods), mispricing
    matches price vs composite
  - freshness: quant `date` not stale
  - room session: dated calls reference a price near the session price; dissent present;
    house view price_at_session not grossly stale vs current close (formula shared with
    provenance_lint.py's publish-time gate, via psx_data.price_staleness_pct)
  - div_yield crossfoot: stated fundamentals.json div_yield feet against a trailing-365-day
    sum of the ticker's own recent dividend history (state/dividends.json)
Severity: high (wrong number shown) / medium (stale or unsupported) / low (cosmetic).
"""
import statistics
import time
from datetime import datetime, timedelta, timezone

from psx_data import STATE, load_json, price_staleness_pct, save_json

# div_yield tolerance for the recent_dividends crossfoot below: relative difference beyond
# this is flagged. Loose on purpose — dividend timing (interim vs final, upcoming vs paid)
# legitimately makes a trailing-window estimate wobble; this only catches gross mismatches.
DIV_YIELD_TOLERANCE_PCT = 15.0


def _num(s):
    """'10.57%' / '12.00' -> float. None if unparseable. fundamentals.json fields are strings
    with a trailing '%' on percentages and no unit suffix otherwise (unlike the B/M/K/T
    parser duplicated in score_fundamentals.py/compute_fairvalue.py — div_yield and dps never
    carry one), so a minimal parser is enough here rather than importing that heavier one."""
    if s is None:
        return None
    try:
        return float(str(s).rstrip("%").replace(",", "").strip())
    except ValueError:
        return None


def _series_glitches(bars):
    """Flag only REVERTING spikes (a >40% move that snaps back within 3 bars) — those are
    data glitches. A >40% move that STAYS is a real split/bonus adjustment, not an error,
    and must not be flagged. Returns [(date, pct, recent_bool)]."""
    bad = []
    n = len(bars)
    cutoff = str(datetime.now(timezone.utc).year - 10)
    for i in range(1, n - 1):
        a, b = bars[i - 1].get("close"), bars[i].get("close")
        if not (a and b) or abs(b / a - 1) <= 0.40:
            continue
        nxt = [bars[j].get("close") for j in range(i + 1, min(n, i + 4)) if bars[j].get("close")]
        reverts = any(abs(x / a - 1) < 0.15 for x in nxt)   # snaps back toward pre-move level
        if reverts:
            recent = (bars[i].get("date") or "")[:4] >= cutoff
            bad.append((bars[i].get("date"), round((b / a - 1) * 100, 1), recent))
    return bad


def verify():
    quant = load_json(STATE / "quant.json", {}).get("tickers", {})
    fair = load_json(STATE / "fairvalue.json", {}).get("tickers", {})
    rooms = load_json(STATE / "rooms.json", {})
    claims = load_json(STATE / "claims.json", {}).get("claims", [])
    fund = load_json(STATE / "fundamentals.json", {}).get("tickers", {})
    div_hist = {}
    for d in load_json(STATE / "dividends.json", {}).get("history", []):
        div_hist.setdefault(d.get("symbol"), []).append(d)
    today = datetime.now(timezone.utc).date()
    cutoff_div = (today - timedelta(days=365)).isoformat()

    out = {}
    for sym, q in quant.items():
        issues = []

        # freshness
        qd = q.get("date")
        try:
            age = (today - datetime.strptime(qd, "%Y-%m-%d").date()).days if qd else 999
            if age > 6:
                issues.append({"sev": "medium", "field": "quant.date",
                               "msg": f"quant is {age} days stale ({qd})"})
        except (ValueError, TypeError):
            issues.append({"sev": "medium", "field": "quant.date", "msg": "unparseable quant date"})

        # served price series glitches (deep preferred, else near history)
        deep = load_json(STATE / "history_deep" / f"{sym}.json", None)
        hist = deep if isinstance(deep, list) else load_json(STATE / "history" / f"{sym}.json", [])
        if isinstance(hist, list) and len(hist) > 30:
            g = _series_glitches(hist)
            recent_g = [x for x in g if x[2]]
            if recent_g:
                issues.append({"sev": "high", "field": "price_series",
                               "msg": f"{len(recent_g)} reverting price glitch(es) in the last decade "
                                      f"(e.g. {recent_g[0][0]} {recent_g[0][1]}%) — recent stats may be wrong",
                               "escalate": True})
            elif g:
                issues.append({"sev": "low", "field": "price_series",
                               "msg": f"{len(g)} old (pre-decade) price glitch(es) — affects only long-run stats"})

        # fair value integrity
        fv = fair.get(sym)
        if fv and fv.get("methods"):
            m = [v for v in fv["methods"].values() if isinstance(v, (int, float))]
            if m:
                med = statistics.median(m)
                if fv.get("composite_fair") and abs(med - fv["composite_fair"]) / fv["composite_fair"] > 0.02:
                    issues.append({"sev": "high", "field": "fairvalue.composite",
                                   "msg": f"composite {fv['composite_fair']} != median(methods) {round(med, 1)}"})
                # wide method spread => the 'fair value' is model-assumption-driven, flag for honesty
                if min(m) > 0 and max(m) / min(m) > 3:
                    issues.append({"sev": "low", "field": "fairvalue.spread",
                                   "msg": f"methods disagree {round(max(m) / min(m), 1)}x — treat composite as a rough screen"})

        # room session consistency
        r = rooms.get(sym)
        if r and r.get("house_view"):
            if not r["house_view"].get("dissent"):
                issues.append({"sev": "medium", "field": "room.dissent", "msg": "house view missing a dissent line"})
            sp = r.get("price_at_session")
            for c in [c for c in claims if c.get("ticker") == sym]:
                mp = c.get("made_at_price")
                if sp and mp and abs(mp / sp - 1) > 0.05:
                    issues.append({"sev": "medium", "field": "claim.price",
                                   "msg": f"a {c.get('source')} call was priced at {mp} vs session price {sp}"})
            # room price staleness: same formula provenance_lint.py already gates publish on
            # (STALE_WARN_PCT/STALE_FAIL_PCT there), via the shared psx_data.price_staleness_pct
            # helper — persisted here per ticker so the UI can surface it, not just a build-time
            # console WARN.
            dev = price_staleness_pct(sp, q.get("close"))
            if dev is not None and dev >= 15.0:
                issues.append({"sev": "high" if dev >= 30.0 else "medium", "field": "room.price_staleness",
                               "msg": f"house view computed at Rs {sp} vs current close Rs {q.get('close')} "
                                      f"({dev:.0f}% stale)", "room_price_stale_pct": round(dev, 1)})

        # div_yield crossfoot: reconcile the stated fundamentals.json div_yield against a
        # trailing-365-day sum of this ticker's OWN recent_dividends (state/dividends.json,
        # excluding not-yet-ex upcoming rows), using the desk's canonical div_yield formula
        # (dps/price, see fetch_fundamentals.py's module docstring) — dps here rebuilt from the
        # actual dividend history instead of trusted blind. Window mirrors sector_dossier.py's
        # existing ttm_dividend_rs trailing-365-day convention, applied to this file's own
        # bc_start/dividend_rs fields. Deterministic catch for the class of bug HMB's LLM
        # room-verifier found (div_yield not footing against its own dossier dividends).
        f = fund.get(sym)
        stated_yield = _num((f or {}).get("div_yield"))
        px = q.get("close")
        paid = [d for d in div_hist.get(sym, [])
                if d.get("kind") == "D" and not d.get("upcoming") and (d.get("bc_start") or "") >= cutoff_div]
        if stated_yield is not None and px and paid:
            ttm_dps = sum(d.get("dividend_rs") or 0 for d in paid)
            implied_yield = ttm_dps / px * 100
            if stated_yield > 0 and abs(implied_yield / stated_yield - 1) * 100 > DIV_YIELD_TOLERANCE_PCT:
                issues.append({"sev": "medium", "field": "fundamentals.div_yield",
                               "msg": f"stated div_yield {stated_yield:g}% vs {implied_yield:.2f}% implied by "
                                      f"trailing-365d dividends (Rs {ttm_dps:.2f}/share at close Rs {px}) "
                                      f"— {abs(implied_yield / stated_yield - 1) * 100:.0f}% off",
                               "escalate": True})

        if issues:
            out[sym] = issues

    highs = sum(1 for v in out.values() for i in v if i["sev"] == "high")
    escalate = sorted({s for s, v in out.items() for i in v if i.get("escalate")})
    out["_meta"] = {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "tickers_with_issues": len([k for k in out if k != "_meta"]),
        "high_severity": highs,
        "escalate_to_agent": escalate,
        "note": "Deterministic QA. 'high' = a wrong number may be on screen. 'escalate_to_agent' names "
                "tickers whose factual claims the LLM room-verifier should web-check.",
    }
    save_json(STATE / "verify.json", out)
    print(f"verify: {out['_meta']['tickers_with_issues']} tickers flagged, {highs} high-severity, "
          f"{len(escalate)} to escalate")
    return out


if __name__ == "__main__":
    verify()
