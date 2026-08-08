"""Fetch fundamentals + earnings calendar for every universe symbol.

Source: stockanalysis.com (server-rendered quote pages carry the full block:
market cap, EPS, P/E, forward P/E, beta, dividend yield, payout ratio, DPS, revenue,
net income, next EARNINGS DATE, ex-dividend date). These are NOT in the PSX DPS
price feed — that is why the ticker pages showed blank fundamentals.

This is slow-moving reference data: run WEEKLY (and the fundamentals agent verifies
earnings dates around results season). Writes state/fundamentals.json.

payout_ratio is NOT taken from the vendor's own `payoutRatio` field — spot-checked
against the vendor's own `dps` + `eps` on the same page, it disagrees (AKBL: dps 5.00 /
eps 17.59 = 28.4%, but the vendor's payoutRatio field says 39.37% — a different, undisclosed
basis). `dividendYield`, by contrast, checks out exactly against dps/price every time. So
payout_ratio here is computed as dps/eps — the same DPS basis the trusted div_yield already
uses — instead of trusting a vendor field that contradicts the vendor's own other numbers.

Idempotent, degrades gracefully (network fail -> keep prior file, exit 0)."""
import concurrent.futures as cf
import re
import sys
import threading
import time
from datetime import date

import requests

from build_calendar import parse_loose
from psx_data import STATE, load_json, market_symbols, research_symbols, save_json

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-desk/1.0"}
FIELDS = {
    "marketCap": "market_cap", "sharesOut": "shares_out", "eps": "eps",
    "peRatio": "pe", "forwardPE": "forward_pe", "beta": "beta",
    "dividendYield": "div_yield", "payoutRatio": "payout_ratio", "dps": "dps",
    "revenue": "revenue", "netIncome": "net_income",
    "earningsDate": "next_earnings", "exDivDate": "ex_div_date",
}


def _num(s):
    """'17.59' / '4.63%' -> float. None if unparseable."""
    if s is None:
        return None
    try:
        return float(str(s).rstrip("%").replace(",", ""))
    except ValueError:
        return None


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
    # the site's own "next earnings" field lags after a company files — it can keep showing the
    # date that was just reported for days before rolling to the new quarter. A past date is not
    # "next" (desk hard-rule #2: unknown beats a stale guess), so drop it rather than persist it.
    ed = parse_loose(out.get("next_earnings", ""), date.today())
    if ed and ed < date.today().isoformat():
        out.pop("next_earnings", None)
    # payout_ratio: recompute from dps/eps (see module docstring) rather than trust the
    # vendor's own payoutRatio field, which disagrees with the vendor's own dps+eps on the
    # same page. Leave it out entirely (not a stale guess) if either input is missing/zero.
    # eps must be POSITIVE: a lossmaking company has no payout ratio at all — dividing by a
    # negative eps yields a negative percentage that downstream copy reads as "sustainable".
    dps, eps = _num(out.get("dps")), _num(out.get("eps"))
    if dps is not None and eps is not None and eps > 0:
        out["payout_ratio"] = f"{dps / eps * 100:.2f}%"
    else:
        out.pop("payout_ratio", None)
    return out if len(out) > 3 else None


WORKERS = 6
_TL = threading.local()


def _session() -> requests.Session:
    """One Session per worker thread. requests.Session is not documented as thread-safe, so
    sharing a single one across the pool risks connection-pool races for no real gain."""
    s = getattr(_TL, "sess", None)
    if s is None:
        s = requests.Session()
        s.headers.update(UA)
        _TL.sess = s
    return s


def _one(sym: str):
    """Fetch a single ticker. Returns (symbol, data|None, error|None). Never raises — a
    thread that dies would otherwise take its ticker out of the run with no record."""
    try:
        d = scrape(sym, _session())
        time.sleep(0.25)     # politeness: 6 workers x 0.25s ~= the old serial request rate
        return sym, d, None
    except requests.RequestException as e:
        return sym, None, str(e)[:40]
    except Exception as e:  # noqa: BLE001
        return sym, None, f"{type(e).__name__}:{str(e)[:30]}"


def main():
    prior = load_json(STATE / "fundamentals.json", {"tickers": {}})

    out, failed = {}, []
    # Liquidity research gate (see psx_data.research_symbols) — one scrape per ticker, so this
    # is the wall-clock cost of the cycle. Threaded because the cost is network latency and a
    # politeness sleep, not CPU: serial, 554 names took ~10 min and blew the Actions budget.
    #
    # An earlier version of this filter claimed the listed tail "has no coverage upstream".
    # That was an untested assumption and it was wrong — a 25-name sample came back 100%
    # covered. The gate is now liquidity, which is a real reason, not a guessed one.
    # PSX ONLY. research_symbols() is market-agnostic on purpose — quant, backtest and
    # predictability all want the US names — but a fundamentals scrape looks for a Karachi filing,
    # and there is no P/E or book value to find for an American sector ETF. Filtering here keeps
    # the WORKERS pool working on names that can actually return something.
    symbols = market_symbols("PSX", research_symbols())
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for sym, data, err in ex.map(_one, symbols):
            if data:
                out[sym] = {**data, "fetched": time.strftime("%Y-%m-%d")}
                continue
            # keep last known values rather than dropping the ticker entirely
            if sym in prior.get("tickers", {}):
                out[sym] = dict(prior["tickers"][sym])
                ed = parse_loose(out[sym].get("next_earnings", ""), date.today())
                if ed and ed < date.today().isoformat():
                    out[sym].pop("next_earnings", None)
            failed.append(f"{sym}:{err}" if err else sym)

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
