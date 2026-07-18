"""Refresh the trading universe.

TWO TIERS, one universe. The desk previously covered only the KSE100 + KMI30 (~103 names), which
meant a real listed company like BBFL simply did not exist in the product — search found nothing,
and there was no page to land on. For a product users expect to be complete, an unsearchable
listed company is a bug, not a scope decision.

  core   — KSE-100 (top-N by weight) + full KMI-30.
           Gets the FULL pipeline: deep history, backtests, fundamentals, fair value, Desk Room
           debates, signals. These are the names the desk actually researches.
  listed — every remaining constituent of the KSE All Share index (ALLSHR), i.e. the rest of the
           market. Gets prices, quant basics, sector, dividends and a real page — so every listed
           company is searchable and readable — but NOT the expensive per-ticker analysis.

The tier is written onto each symbol so every downstream script can decide honestly what it can
say about a name, instead of silently implying full coverage everywhere. Scripts that are cheap
per ticker (prices, quant, dividends) should process ALL; scripts that are expensive per ticker
(deep history, backtests, Room) should filter to core.

Writes state/universe.json. Run weekly (run_cycle.py handles cadence).
"""
import sys
import time

from psx_data import STATE, index_constituents, load_config, save_json


def main():
    cfg = load_config()
    uni_cfg = cfg["universe"]
    top_n = uni_cfg["kse100_top_n"]
    cover_all = uni_cfg.get("cover_all_listed", True)

    kse = index_constituents("KSE100")
    if len(kse) < 50:
        print(f"FATAL: KSE100 constituents parse returned only {len(kse)} rows", file=sys.stderr)
        sys.exit(1)
    kmi = index_constituents("KMI30") if uni_cfg["include_kmi30"] else []

    members = {}
    for c in kse[:top_n]:
        members[c["symbol"]] = {**c, "in": ["KSE100"], "tier": "core"}
    for c in kmi:
        if c["symbol"] in members:
            members[c["symbol"]]["in"].append("KMI30")
        else:
            members[c["symbol"]] = {**c, "in": ["KMI30"], "tier": "core"}
    n_core = len(members)

    # the rest of the market, from the All Share index (every listed company)
    n_all = 0
    if cover_all:
        allshr = index_constituents("ALLSHR")
        n_all = len(allshr)
        if n_all < 200:
            # a parse failure here must not silently shrink the universe
            print(f"WARN: ALLSHR returned only {n_all} rows — keeping core tier only", file=sys.stderr)
        else:
            for c in allshr:
                s = c["symbol"]
                if s in members:
                    if "ALLSHR" not in members[s]["in"]:
                        members[s]["in"].append("ALLSHR")
                else:
                    members[s] = {**c, "in": ["ALLSHR"], "tier": "listed"}

    kmi_all = index_constituents("KMIALLSHR") if cover_all else []
    for c in kmi_all:
        s = c["symbol"]
        if s in members and "KMIALLSHR" not in members[s]["in"]:
            members[s]["in"].append("KMIALLSHR")

    n_listed = sum(1 for m in members.values() if m["tier"] == "listed")
    save_json(STATE / "universe.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "kse100_total": len(kse),
        "kmi30_total": len(kmi),
        "allshr_total": n_all,
        "tiers": {
            "core": n_core,
            "listed": n_listed,
            "_note": ("core = KSE100 + KMI30, full research pipeline. listed = the rest of the "
                      "KSE All Share, covered with prices/quant/sector/dividends and a real page, "
                      "but no deep backtests or Desk Room debates. Any script that is expensive "
                      "per ticker must filter to tier == 'core'."),
        },
        "symbols": members,
    })
    print(f"universe: {len(members)} symbols ({n_core} core [{top_n} KSE100 + {len(kmi)} KMI30], "
          f"{n_listed} listed from ALLSHR)")


if __name__ == "__main__":
    main()
