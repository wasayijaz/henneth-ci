"""Data health gate. Writes state/health.json. If status != ok, the desk
generates NO new signals this cycle (monitoring continues). Checks:
- universe exists and is fresh enough
- history covers >= 90% of universe and last date is recent (allowing weekends/holidays)
- a live spot-check price is sane vs cached close (catches decimal/parse breakage)."""
import sys
import time
from datetime import date, datetime, timedelta

from psx_data import STATE, intraday_last, load_json, save_json

MAX_STALE_SESSIONS_DAYS = 5  # last EOD date may lag this many calendar days


def main():
    problems = []
    universe = load_json(STATE / "universe.json", None)
    if not universe:
        problems.append("universe.json missing")
        syms = []
    else:
        syms = list(universe["symbols"])
        upd = datetime.strptime(universe["updated"][:10], "%Y-%m-%d").date()
        if (date.today() - upd).days > 10:
            problems.append(f"universe stale ({universe['updated']})")

    have, latest = 0, None
    for s in syms:
        h = load_json(STATE / "history" / f"{s}.json", None)
        if h:
            have += 1
            d = h[-1]["date"]
            latest = max(latest, d) if latest else d
    if syms:
        cov = have / len(syms)
        if cov < 0.9:
            problems.append(f"history coverage {cov:.0%}")
        if latest and (date.today() - datetime.strptime(latest, "%Y-%m-%d").date()).days > MAX_STALE_SESSIONS_DAYS:
            problems.append(f"history stale (latest {latest})")

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
            break
        except Exception:  # noqa: BLE001
            continue

    # TradingView cross-check (if run this session): any FAIL degrades health
    cc = load_json(STATE / "crosscheck.json", None)
    if cc and cc.get("fails"):
        if cc.get("updated", "")[:10] == time.strftime("%Y-%m-%d"):
            problems.append(f"tv_crosscheck FAIL: {', '.join(cc['fails'])}")

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

    status = "ok" if not problems else "degraded"
    save_json(STATE / "health.json", {
        "checked": time.strftime("%Y-%m-%d %H:%M"),
        "status": status,
        "problems": problems,
        "history_symbols": have,
        "latest_eod": latest,
        "spot_check": spot,
    })
    print(f"health: {status}" + (f" — {'; '.join(problems)}" if problems else ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
