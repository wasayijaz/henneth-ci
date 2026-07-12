"""Fetch the global markets that drive PSX. Writes state/global.json.

Why each matters for PSX (long-only KSE names):
- Brent/WTI crude: Pakistan imports ~all its oil. Higher crude = wider import bill,
  weaker PKR, inflation pressure (bad for market); but OMCs/refiners (PSO, ATRL, NRL)
  and E&Ps (OGDC, PPL, MARI, POL) move WITH oil. Two-sided — annotated per group.
- S&P 500 / Dow: global risk appetite proxy. Risk-on abroad -> foreign flows into
  frontier markets like PSX; risk-off -> outflows.
- Gold: safe-haven; also a PKR/inflation hedge signal for local sentiment.
- BTC / ETH: global risk/liquidity barometer (retail risk appetite).
- USD/PKR: the single biggest macro lever. PKR weakness = imported inflation =
  SBP stays hawkish = discount-rate headwind for equities.

Pakistan-domestic numbers (SBP policy rate, CPI, IMF, debt/borrowing, reserves) are
NOT on Yahoo — the macro-agent fills state/macro.json with those from web sources.
This script owns only the live global instruments (deterministic, every full cycle).

Degrades gracefully: any symbol that fails keeps its prior value; never crashes."""
import sys
import time

import requests

from psx_data import STATE, load_json, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"}

# symbol: (label, group, psx_read)
INSTRUMENTS = {
    "BZ=F":    ("Brent crude", "energy", "↑ = import bill up, PKR/inflation risk; E&P + refiners rise"),
    "CL=F":    ("WTI crude", "energy", "global oil proxy"),
    "^GSPC":   ("S&P 500", "risk", "global risk-on/off; frontier flows follow"),
    "^DJI":    ("Dow Jones", "risk", "global risk appetite"),
    "^VIX":    ("VIX", "risk", "fear gauge; high = risk-off = PSX outflows"),
    "GC=F":    ("Gold", "safe_haven", "safe-haven + PKR/inflation hedge sentiment"),
    "BTC-USD": ("Bitcoin", "crypto", "global liquidity / retail risk barometer"),
    "ETH-USD": ("Ethereum", "crypto", "risk appetite"),
    "PKR=X":   ("USD/PKR", "fx", "biggest lever: weak PKR = imported inflation = hawkish SBP = equity headwind"),
    "DX-Y.NYB": ("US Dollar Index", "fx", "strong USD pressures EM/frontier currencies incl PKR"),
}


def fetch(symbol: str, sess: requests.Session) -> dict | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo"
    r = sess.get(url, timeout=15)
    if r.status_code != 200:
        return None
    res = r.json().get("chart", {}).get("result")
    if not res:
        return None
    meta = res[0]["meta"]
    closes = [c for c in (res[0]["indicators"]["quote"][0].get("close") or []) if c is not None]
    price = meta.get("regularMarketPrice")
    if price is None or not closes:
        return None
    # 1d change from the last two settled daily closes (robust across weekends)
    chg_1d = (closes[-1] / closes[-2] - 1) * 100 if len(closes) >= 2 else None
    chg_1mo = (closes[-1] / closes[0] - 1) * 100 if len(closes) > 1 else None
    return {
        "price": round(price, 2),
        "chg_1d_pct": round(chg_1d, 2) if chg_1d is not None else None,
        "chg_1mo_pct": round(chg_1mo, 2) if chg_1mo is not None else None,
    }


def main():
    prior = load_json(STATE / "global.json", {"instruments": {}}).get("instruments", {})
    sess = requests.Session()
    sess.headers.update(UA)

    out, failed = {}, []
    for sym, (label, group, read) in INSTRUMENTS.items():
        data = None
        try:
            data = fetch(sym, sess)
        except requests.RequestException:
            pass
        if data:
            out[sym] = {"label": label, "group": group, "psx_read": read, **data}
        else:
            failed.append(sym)
            if sym in prior:
                out[sym] = {**prior[sym], "stale": True}
        time.sleep(0.25)

    save_json(STATE / "global.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "Yahoo Finance",
        "note": "Pakistan-domestic macro (SBP rate, CPI, IMF, debt) is in macro.json, filled by macro-agent",
        "instruments": out,
        "failed": failed,
    })
    print(f"global: {len(out)} instruments, {len(failed)} failed")
    for sym, v in out.items():
        print(f"  {v['label']}: {v['price']} ({v.get('chg_1d_pct')}% 1d)")
    sys.exit(0)


if __name__ == "__main__":
    main()
