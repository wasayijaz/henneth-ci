"""Fetch fundamentals + earnings calendar for every universe symbol.

Source: stockanalysis.com (server-rendered quote pages carry the full block:
market cap, EPS, P/E, forward P/E, beta, dividend yield, payout ratio, revenue,
net income, next EARNINGS DATE, ex-dividend date). These are NOT in the PSX DPS
price feed — that is why the ticker pages showed blank fundamentals.

This is slow-moving reference data: run WEEKLY (and the fundamentals agent verifies
earnings dates around results season). Writes state/fundamentals.json.

Idempotent, degrades gracefully (network fail -> keep prior file, exit 0)."""
import re
import sys
import time

import requests

from psx_data import STATE, load_json, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"}
FIELDS = {
    "marketCap": "market_cap", "sharesOut": "shares_out", "eps": "eps",
    "peRatio": "pe", "forwardPE": "forward_pe", "beta": "beta",
    "dividendYield": "div_yield", "payoutRatio": "payout_ratio",
    "revenue": "revenue", "netIncome": "net_income",
    "earningsDate": "next_earnings", "exDivDate": "ex_div_date",
}


def scrape(symbol: str, sess: requests.Session) -> dict | None:
    url = f"https://stockanalysis.com/quote/psx/{symbol}/"
    r = sess.get(url, timeout=20)
    if r.status_code != 200:
        return None
    html = r.text
    out = {"source_url": url}
    for key, name in FIELDS.items():
        # match  key:"value"  taking the first quoted value after the key
        m = re.search(rf'{key}:"([^"]{{1,24}})"', html)
        if m and m.group(1) not in ("true", "false"):
            out[name] = m.group(1).strip()
    # numeric revenue/netincome may appear unquoted first; prefer the human "69.33B" form already captured
    return out if len(out) > 3 else None


def main():
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    prior = load_json(STATE / "fundamentals.json", {"tickers": {}})
    sess = requests.Session()
    sess.headers.update(UA)

    out, failed = {}, []
    for sym in universe["symbols"]:
        try:
            data = scrape(sym, sess)
            if data:
                out[sym] = {**data, "fetched": time.strftime("%Y-%m-%d")}
            else:
                # keep last known values rather than dropping
                if sym in prior.get("tickers", {}):
                    out[sym] = prior["tickers"][sym]
                failed.append(sym)
        except requests.RequestException as e:
            if sym in prior.get("tickers", {}):
                out[sym] = prior["tickers"][sym]
            failed.append(f"{sym}:{str(e)[:40]}")
        time.sleep(0.5)

    save_json(STATE / "fundamentals.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "stockanalysis.com",
        "tickers": out,
        "failed": failed,
    })
    print(f"fundamentals: {len(out)} tickers, {len(failed)} failed/stale")
    # surface the earnings calendar
    cal = [(s, v.get("next_earnings")) for s, v in out.items() if v.get("next_earnings")]
    print(f"  earnings dates captured for {len(cal)} tickers")
    sys.exit(0)


if __name__ == "__main__":
    main()
