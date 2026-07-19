"""Deep history. Pulls max available daily OHLC (~2008->today, 18y) for every core
symbol from Yahoo Finance (PSX names carry the '.KA' Karachi suffix). Verified to match
DPS on recent bars and — unlike the DPS EOD feed — it INCLUDES real daily high/low,
which is why the Corwin-Schultz spread estimator in liquidity.py can only run on names
that have a file here.

Stored separately in state/history_deep/{SYM}.json so it does NOT disturb the
authoritative DPS pipeline (quant/live/crosscheck stay on DPS). The dashboard uses it
for the long-range chart (5Y/10Y/Max), and backtest.py PREFERS it over the DPS series
because it is longer — which is exactly why it must not be allowed to go stale.

This was originally a ONE-TIME backfill that skipped any symbol whose file already
existed. That meant every cached series froze permanently at its first-pull date and
nothing reported it. It now refreshes stale files on a bounded rotation each run.

Safe to re-run (idempotent).
Usage: python scripts/fetch_deep_history.py [--refresh]   (--refresh forces ALL)
"""
import sys
import time
from datetime import date, datetime

import requests

from psx_data import STATE, load_json, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"}
STALE_AFTER_DAYS = 5        # a file whose last bar is older than this is refetched
DEEP_REFRESH_PER_RUN = 25   # bounded so a mass refresh spreads over cycles, not one 25-min job


def fetch(symbol: str, sess: requests.Session) -> list[dict] | None:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.KA"
           f"?interval=1d&range=25y")
    r = sess.get(url, timeout=25)
    if r.status_code != 200:
        return None
    res = r.json().get("chart", {}).get("result")
    if not res:
        return None
    ts = res[0].get("timestamp") or []
    q = res[0]["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if c is None or o is None:
            continue
        out.append({
            "date": time.strftime("%Y-%m-%d", time.gmtime(t)),
            "open": round(o, 2), "high": round(h, 2) if h else round(c, 2),
            "low": round(l, 2) if l else round(c, 2), "close": round(c, 2),
            "volume": int(v) if v else 0,
        })
    return out


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def clean_series(hist, tol=0.35, win=15):
    """Repair adjustment glitches in Yahoo .KA data (dividend/bonus artifacts: a close
    that halves for a few bars then recovers). Two complementary detectors, iterated:
      1) rolling-median: a bar off the robust median of +/- `win` bars by more than `tol`
         is corrupt (catches multi-bar corrupt RUNS; a short run barely moves the median).
      2) spike-reversal: a bar whose move in AND out both exceed 40% in opposite directions
         is an isolated glitch (catches single spikes the median smooths over).
    Sustained real moves (trends, the 2008 crash) shift the whole window / don't revert, so
    they are left untouched. A repaired bar's OHLC is set to the local median.
    Returns (cleaned, n_fixed)."""
    n = len(hist)
    if n < 5:
        return hist, 0
    total = 0
    for _ in range(4):  # iterate so runs resolve fully
        closes = [b.get("close") for b in hist]
        fixed = 0
        for i in range(n):
            c = closes[i]
            if not c:
                continue
            lo, hi = max(0, i - win), min(n, i + win + 1)
            base = _median([x for x in closes[lo:hi] if x]) if hi - lo >= 5 else None
            median_bad = base and abs(c / base - 1) > tol
            spike_bad = (0 < i < n - 1 and closes[i - 1] and closes[i + 1]
                         and abs(c / closes[i - 1] - 1) > 0.40 and abs(c / closes[i + 1] - 1) > 0.40
                         and (c > closes[i - 1]) != (c > closes[i + 1]))
            if median_bad or spike_bad:
                repl = round(base, 2) if base else round((closes[i - 1] + closes[i + 1]) / 2, 2)
                hist[i]["close"] = repl
                for k in ("open", "high", "low"):
                    if hist[i].get(k):
                        hist[i][k] = repl
                hist[i]["repaired"] = True
                fixed += 1
        total += fixed
        if not fixed:
            break
    return hist, total


def main():
    refresh = "--refresh" in sys.argv
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    sess = requests.Session()
    sess.headers.update(UA)

    ok, failed, skipped, stale_refreshed = 0, [], 0, []
    # tier filter: deep Yahoo history is slow per ticker and only the core names get backtested.
    # Default to "core" so a universe file without tiers behaves exactly as before.
    core = [s for s, m in universe["symbols"].items() if (m or {}).get("tier", "core") == "core"]

    # STALENESS REFRESH. This file used to fetch a symbol once and then skip it forever
    # (`if dest.exists(): continue`), so every cached series silently froze at whatever date
    # it was first pulled. That is not a cosmetic problem: backtest.py PREFERS deep history
    # over the DPS feed, so a frozen file means the strategy numbers on that name were being
    # computed from stale prices. IBFL was the caught case — pinned at 235.0 while the live
    # price was 298, a 27% gap with no error anywhere.
    #
    # Now: never-fetched first, then the stalest files, bounded per run so a full refresh
    # spreads over a few cycles instead of blowing the Actions budget in one.
    stale = []
    for sym in core:
        fp = STATE / "history_deep" / f"{sym}.json"
        if not fp.exists():
            continue
        h = load_json(fp, [])
        last = h[-1].get("date") if isinstance(h, list) and h else None
        try:
            age = (date.today() - datetime.strptime(last, "%Y-%m-%d").date()).days if last else 9999
        except (ValueError, TypeError):
            age = 9999
        if age > STALE_AFTER_DAYS:
            stale.append((age, sym))
    stale.sort(reverse=True)                      # stalest first
    due = {s for _, s in stale[:DEEP_REFRESH_PER_RUN]}
    if stale:
        print(f"  deep staleness: {len(stale)} file(s) older than {STALE_AFTER_DAYS}d, "
              f"refreshing {len(due)} this run (stalest first)")

    for sym in core:
        dest = STATE / "history_deep" / f"{sym}.json"
        if dest.exists() and not refresh and sym not in due:
            skipped += 1
            continue
        if sym in due:
            stale_refreshed.append(sym)
        try:
            hist = fetch(sym, sess)
            if hist and len(hist) > 250:
                save_json(dest, hist)
                ok += 1
                print(f"  {sym}: {len(hist)} bars, {hist[0]['date']} -> {hist[-1]['date']}")
            else:
                failed.append((sym, f"{len(hist) if hist else 0} bars"))
        except requests.RequestException as e:
            failed.append((sym, str(e)[:50]))
        time.sleep(0.5)

    # cleaning pass over ALL files every run (idempotent, cheap) so cached series
    # get de-glitched too — this runs in the cloud since the workflow calls this script.
    total_fixed, files_touched = 0, 0
    for fp in sorted((STATE / "history_deep").glob("*.json")):
        hist = load_json(fp, [])
        if not isinstance(hist, list) or len(hist) < 3:
            continue
        hist, nfix = clean_series(hist)
        if nfix:
            save_json(fp, hist)
            total_fixed += nfix
            files_touched += 1
            print(f"  cleaned {fp.stem}: repaired {nfix} glitch bar(s)")

    save_json(STATE / "history_deep_meta.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "Yahoo Finance (.KA)",
        "ok": ok, "skipped_existing": skipped,
        "stale_refreshed": stale_refreshed,
        "stale_after_days": STALE_AFTER_DAYS,
        "glitch_bars_repaired": total_fixed, "files_cleaned": files_touched,
        "failed": [{"symbol": s, "note": n} for s, n in failed],
    })
    print(f"deep history: {ok} fetched ({len(stale_refreshed)} stale-refresh), {skipped} cached, "
          f"{total_fixed} glitch bars repaired across {files_touched} files")
    print(f"deep history: {ok} fetched, {skipped} already present, {len(failed)} failed")


if __name__ == "__main__":
    main()
