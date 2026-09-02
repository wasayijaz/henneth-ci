"""Data health gate. Writes state/health.json. If status != ok, the desk
generates NO new signals this cycle (monitoring continues). Checks:
- universe exists and is fresh enough
- history covers >= 90% of universe and the freshest last date is recent (weekends/holidays allowed)
- the FLEET is fresh, not just the freshest symbol — see STALE_FLEET_DAYS
- a live spot-check price is sane vs cached close (catches decimal/parse breakage)."""
import sys
import time
from datetime import date, datetime, timedelta

from psx_data import STATE, intraday_last, load_json, save_json

MAX_STALE_SESSIONS_DAYS = 5  # last EOD date may lag this many calendar days

# FLEET staleness, as opposed to the single freshest date above. These two constants exist
# because the `latest` test alone is structurally blind: it is a max() over every history file,
# so ONE current core ticker reports "ok" while the entire long tail is frozen. That is not
# hypothetical — fetch_history's rotation budget collapsed to zero and 352 of 352 listed symbols
# sat 47 sessions stale behind a green health.json, which is how a wrong close reached the site.
#
# The thresholds are deliberately loose, because under CLAUDE.md Rule 6 a degraded status halts
# every new signal and a FALSE degradation is worse than none. A full listed-tier rotation now
# completes in ~4 cron runs (about two hours), so 12 calendar days is ~40x the headroom rotation
# needs; and 10% of the fleet cannot be tripped by the handful of genuinely suspended counters
# that legitimately stop printing new bars. Anything past both is a broken fetcher, not lag.
STALE_FLEET_DAYS = 12
STALE_FLEET_FRACTION = 0.10


def main():
    problems = []
    universe = load_json(STATE / "universe.json", None)
    if not universe:
        problems.append("universe.json missing")
        syms, foreign = [], []
    else:
        # Measure coverage against TRADEABLE symbols only. The universe is the whole KSE All Share,
        # whose constituent list includes PSX board counters that are not companies and never have
        # a price series (…XD ex-dividend, …XB ex-bonus, …NC non-compliant). Counting those as
        # "missing history" drove coverage to 82% and would have flipped health to degraded — which
        # under CLAUDE.md Rule 6 halts all new signals. A false degradation is worse than none.
        #
        # NON-PSX SYMBOLS ARE EXCLUDED FROM THIS GATE, deliberately. Under Rule 6 a degraded
        # status halts every new signal, and the desk's signals are PSX-only (US coverage is
        # research-tier — config/markets.json signals_enabled:false). A Yahoo hiccup on XLE must
        # not be able to stop the desk publishing PSX research. Their freshness is still reported
        # below as `foreign_*`, so a US outage is visible; it just cannot gate the home market.
        cov = load_json(STATE / "coverage.json", None)
        home = [s for s, m in universe["symbols"].items()
                if ((m or {}).get("market") or "PSX") == "PSX"]
        if cov and cov.get("bars"):
            syms = [s for s in home if s in cov["bars"]]
        else:
            syms = list(home)
        foreign = [s for s in universe["symbols"] if s not in set(home)]
        upd = datetime.strptime(universe["updated"][:10], "%Y-%m-%d").date()
        if (date.today() - upd).days > 10:
            problems.append(f"universe stale ({universe['updated']})")

    # `latest` answers "is ANY price current". `stale_fleet` answers "are the prices we SHOW
    # current" — the question that went unasked while 352 tickers published a July close.
    fleet_cutoff = (date.today() - timedelta(days=STALE_FLEET_DAYS)).isoformat()
    have, latest, stale_fleet, oldest = 0, None, [], None
    for s in syms:
        h = load_json(STATE / "history" / f"{s}.json", None)
        if h:
            have += 1
            d = h[-1]["date"]
            latest = max(latest, d) if latest else d
            oldest = min(oldest, d) if oldest else d
            if d < fleet_cutoff:
                stale_fleet.append(s)
    if syms:
        cov = have / len(syms)
        if cov < 0.9:
            problems.append(f"history coverage {cov:.0%}")
        if latest and (date.today() - datetime.strptime(latest, "%Y-%m-%d").date()).days > MAX_STALE_SESSIONS_DAYS:
            problems.append(f"history stale (latest {latest})")
        if have and len(stale_fleet) / have > STALE_FLEET_FRACTION:
            problems.append(
                f"{len(stale_fleet)} of {have} tradeable symbols have no bar since {fleet_cutoff} "
                f"(oldest {oldest}) — the refresh rotation is not reaching them; "
                f"e.g. {', '.join(sorted(stale_fleet)[:5])}")

    # live sanity spot-check on a heavyweight
    spot = None
    for probe in ("HUBC", "OGDC", "LUCK"):
        try:
            tick = intraday_last(probe)
            h = load_json(STATE / "history" / f"{probe}.json", None)
            if tick and h:
                ref = h[-1]["close"]
                dev = abs(tick["price"] / ref - 1)
                spot = {"symbol": probe, "live": tick["price"], "cached_close": ref,
                        "deviation_pct": round(dev * 100, 2)}
                if dev > 0.15:
                    problems.append(f"{probe} live {tick['price']} vs cached {ref} deviates {dev:.0%}")
                break   # a comparison was actually made — that is what ends the loop
            # No exception, but no usable pair either (intraday_last returned nothing, or the
            # history file is missing). The `break` used to sit out here, so the fallbacks after
            # HUBC were unreachable and a silent None left spot_check null with no problem logged.
        except Exception:  # noqa: BLE001
            continue

    # TradingView cross-check (if run this session): only a GENUINE error degrades health.
    # tv_crosscheck now separates real glitches (`fails`: close off >12%, i.e. decimal/split/
    # wrong-symbol) from explainable `drift` (TV's 15-min lag + adjusted-vs-unadjusted feed).
    # Per CLAUDE.md a TV-vs-DPS mismatch is NOT an error, so `drift` never degrades health.
    cc = load_json(STATE / "crosscheck.json", None)
    cc_drift = []
    if cc and cc.get("updated", "")[:10] == time.strftime("%Y-%m-%d"):
        if cc.get("fails"):
            problems.append(f"tv_crosscheck ERROR (likely data glitch): {', '.join(cc['fails'])}")
        cc_drift = cc.get("drift", [])

    # Calendar freshness (Ramadan guard, CLAUDE.md): if session times haven't been re-verified
    # in 60 days, degrade — force a human check rather than silently trading wrong hours.
    cal = load_json(STATE / "calendar.json", {})
    stu = cal.get("session_times_updated")
    try:
        age = (date.today() - datetime.strptime(stu, "%Y-%m-%d").date()).days if stu else 9999
        if age > 60:
            problems.append(f"stale_calendar: session times last verified {stu or 'never'} ({age}d ago) — re-check vs PSX/SBP notice")
    except (ValueError, TypeError):
        problems.append("stale_calendar: session_times_updated missing/unparseable in calendar.json")

    # Non-PSX coverage: REPORTED, never gating (see the note above `home`). A US outage shows up
    # here as an advisory so it is visible and fixable, without halting PSX signals under Rule 6.
    f_have = sum(1 for s in foreign if load_json(STATE / "history" / f"{s}.json", None))
    advisories = ([f"tv drift (lag/adjustment, not an error): {', '.join(cc_drift)}"] if cc_drift else [])
    if foreign and f_have < len(foreign):
        advisories.append(f"non-PSX history {f_have}/{len(foreign)} — research-tier only, does not gate signals")

    status = "ok" if not problems else "degraded"
    save_json(STATE / "health.json", {
        "checked": time.strftime("%Y-%m-%d %H:%M"),
        "status": status,
        "problems": problems,
        "advisories": advisories,
        "history_symbols": have,
        "foreign_symbols": len(foreign),
        "foreign_with_history": f_have,
        "latest_eod": latest,
        # Reported even when under threshold: `latest_eod` alone reads green during a total
        # rotation failure, so the fleet numbers are what make that failure visible at a glance.
        "oldest_eod": oldest,
        "stale_fleet": len(stale_fleet),
        "stale_fleet_cutoff": fleet_cutoff,
        "spot_check": spot,
    })
    print(f"health: {status}" + (f" — {'; '.join(problems)}" if problems else ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
