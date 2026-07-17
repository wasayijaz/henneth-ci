"""Daily history for the macro factors that plausibly move PSX sectors.

The desk's sector story is macro (flows, oil, gold, FX, global risk) — but until now the desk held
only live snapshots of these, no history, so "banks fall when rates rise" was an assumption, not a
measurement. This fetches the history so sector_macro.py can measure it.

Factors (Yahoo symbols, all with deep daily history):
  oil        CL=F     WTI front month
  gold       GC=F     COMEX gold
  usdpkr     PKR=X    US dollar vs Pakistani rupee (up = rupee weaker)
  sp500      ^GSPC    global risk appetite
  em_equity  EEM      EM flows proxy (what foreign money does to markets like ours)
  us10y      ^TNX     US 10-year yield (global cost of money; drives EM debt pressure)
  dollar     DX-Y.NYB dollar index (EM headwind when strong)

Incremental: keeps what it has, appends missing days. Network failure -> keep old file, exit 0.
Writes state/macro_history.json.
"""
import datetime as dt
import json
import pathlib
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "macro_history.json"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
FACTORS = {
    "oil": "CL=F", "gold": "GC=F", "usdpkr": "PKR=X", "sp500": "^GSPC",
    "em_equity": "EEM", "us10y": "^TNX", "dollar": "DX-Y.NYB",
}
START = "2007-01-01"


def fetch(symbol: str, sess) -> dict:
    """date -> close, full daily history."""
    p1 = int(dt.datetime.fromisoformat(START).replace(tzinfo=dt.timezone.utc).timestamp())
    p2 = int(time.time())
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol)}"
         f"?period1={p1}&period2={p2}&interval=1d")
    r = sess.get(u, timeout=30)
    res = r.json()["chart"]["result"][0]
    ts = res.get("timestamp") or []
    cl = res["indicators"]["quote"][0].get("close") or []
    out = {}
    for t, c in zip(ts, cl):
        if c is not None:
            out[dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")] = round(float(c), 4)
    return out


def main():
    STATE.mkdir(exist_ok=True)
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8")).get("factors", {})
        except Exception:
            prev = {}
    sess = requests.Session()
    sess.headers.update(HDRS)
    factors, failed = {}, []
    for name, sym in FACTORS.items():
        try:
            series = fetch(sym, sess)
            if len(series) < 1000:
                raise RuntimeError(f"only {len(series)} bars")
            factors[name] = {"symbol": sym, "series": series}
            print(f"  {name:10} {sym:9} {len(series)} days ({min(series)} -> {max(series)})")
        except Exception as e:
            failed.append(name)
            if name in prev:
                factors[name] = prev[name]
                print(f"  {name:10} {sym:9} FETCH FAILED ({type(e).__name__}) — kept previous "
                      f"({len(prev[name].get('series', {}))} days)")
            else:
                print(f"  {name:10} {sym:9} FETCH FAILED ({type(e).__name__}) — no previous, skipped")
        time.sleep(0.4)

    if not factors:
        print("macro_history: nothing fetched and nothing cached — leaving state untouched")
        sys.exit(0)
    OUT.write_text(json.dumps({
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "note": ("Daily closes for the global factors the desk's sector attribution runs on. "
                 "usdpkr up = rupee weaker. us10y is the yield x10 (Yahoo quotes ^TNX that way)."),
        "factors": factors,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"macro_history: {len(factors)} factors written" + (f" ({len(failed)} failed)" if failed else ""))


if __name__ == "__main__":
    main()
