"""Refresh the trading universe: top-N KSE-100 by weight + full KMI-30.
Writes state/universe.json. Run weekly (run_cycle.py handles cadence)."""
import sys
import time

from psx_data import STATE, index_constituents, load_config, save_json


def main():
    cfg = load_config()
    top_n = cfg["universe"]["kse100_top_n"]

    kse = index_constituents("KSE100")
    if len(kse) < 50:
        print(f"FATAL: KSE100 constituents parse returned only {len(kse)} rows", file=sys.stderr)
        sys.exit(1)
    kmi = index_constituents("KMI30") if cfg["universe"]["include_kmi30"] else []

    members = {}
    for c in kse[:top_n]:
        members[c["symbol"]] = {**c, "in": ["KSE100"]}
    for c in kmi:
        if c["symbol"] in members:
            members[c["symbol"]]["in"].append("KMI30")
        else:
            members[c["symbol"]] = {**c, "in": ["KMI30"]}

    save_json(STATE / "universe.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "kse100_total": len(kse),
        "kmi30_total": len(kmi),
        "symbols": members,
    })
    print(f"universe: {len(members)} symbols ({top_n} KSE100 + {len(kmi)} KMI30, deduped)")


if __name__ == "__main__":
    main()
