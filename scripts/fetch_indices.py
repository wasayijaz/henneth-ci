"""Capture the real PSX index levels, daily, and keep them.

Two things needed this and neither could be fixed with what the desk had:
  * MARKET-RELATIVE CLAIMS. The astro readings claim a name "underperforms the KSE100". Scoring
    that needs the index level at the claim and at resolution. Without it, room_score would grade
    a market-relative claim on the ABSOLUTE price move — marking a stock that fell 2% while the
    market fell 8% as a HIT for "underperforms", when it plainly outperformed. Silent, and it would
    have discredited the whole scorecard.
  * NO INDEX HISTORY EXISTS. Yahoo's ^KSE is monthly and stops in 2021; stooq has nothing; DPS
    publishes indices live-only. So astro_backtest had to rebuild KSE100/KMI30 from constituents
    and label them proxies. Nobody can hand us the past — but from today we can simply keep it.
    In a year this file IS the index history the desk currently lacks.

Source: dps.psx.com.pk/indices (PSX's own live board). Append-only: one row per PKT trading date,
never rewrites a past row. Network failure -> keep what we have, exit 0.
Writes state/indices.json.
"""
import datetime as dt
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import psx_data  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "indices.json"
PKT = dt.timezone(dt.timedelta(hours=5))
# KSE100/KMI30/KSE30 are the headline benchmarks. The two ALL-SHARE indices matter more for this
# desk than their profile suggests: the universe runs well past the KSE100 constituents, so a
# claim about a mid-cap graded against the KSE100 is graded against an index it isn't in.
# ALLSHR covers every listed company; KMIALLSHR is its Shariah-compliant counterpart — together
# they give an honest benchmark for any ticker the desk covers. BKTI/OGTI are the two sector
# indices with enough weight in the universe to be useful comparators.
WANT = ("KSE100", "KMI30", "KSE30", "ALLSHR", "KMIALLSHR", "BKTI", "OGTI")


def main():
    STATE.mkdir(exist_ok=True)
    data = {"history": {}, "live": {}}
    if OUT.exists():
        try:
            data = json.loads(OUT.read_text(encoding="utf-8"))
            data.setdefault("history", {})
            data.setdefault("live", {})
        except Exception:
            pass

    try:
        html = psx_data._get("/indices").text
        rows = psx_data._parse_table_rows(html)
    except Exception as e:
        print(f"indices: fetch failed ({type(e).__name__}) — keeping {len(data['history'])} stored days")
        sys.exit(0)

    live = {}
    for cells in rows:
        if len(cells) < 4:
            continue
        name = (cells[0] or "").strip().upper()
        if name not in WANT:
            continue
        try:
            live[name] = float(str(cells[3]).replace(",", ""))
        except (ValueError, IndexError):
            continue

    if "KSE100" not in live:
        print("indices: KSE100 not found in the DPS board — markup may have changed; keeping stored data")
        sys.exit(0)

    today = dt.datetime.now(PKT).date().isoformat()
    data["live"] = live
    data["live_at"] = dt.datetime.now(PKT).strftime("%Y-%m-%d %H:%M")
    # append-only: the first capture of a date wins, so a late-session re-run can't rewrite history
    if today not in data["history"]:
        data["history"][today] = live
    data["updated"] = time.strftime("%Y-%m-%d %H:%M")
    data["source"] = "https://dps.psx.com.pk/indices (PSX's own board), captured once per trading day"
    data["note"] = ("Append-only index levels. The desk started keeping these on the first run of "
                    "this script because no daily PSX index history is purchasable or scrapeable "
                    "anywhere the desk can reach — Yahoo's ^KSE is monthly and dead since 2021. "
                    "Everything before the earliest date here is unavailable, and the backtests say "
                    "so by labelling their constituent-rebuilt indices as proxies.")
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    hist = sorted(data["history"])
    print(f"indices: {' · '.join(f'{k} {v:,.0f}' for k, v in live.items())}")
    print(f"  history: {len(hist)} day(s) kept ({hist[0]} -> {hist[-1]})")


if __name__ == "__main__":
    main()
