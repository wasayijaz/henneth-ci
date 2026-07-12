"""Fair value + mispricing for every ticker, via several transparent methods.
Deterministic (no LLM) so it autoupdates free in the cloud pipeline. Writes
state/fairvalue.json.

Methods (each an independent estimate of 'what the share is worth'):
  1. Relative (sector P/E)   : sector-median P/E x EPS  — priced like its peers.
  2. Earnings power (bond)   : fair P/E = 100/(bond_yield+premium); x EPS. Ties value
                               to Pakistan's rate environment (high rates -> low fair P/E).
  3. Graham revised          : EPS x (8.5 + 2g) x 4.4 / Y  — classic earnings+growth value.
  4. Dividend discount (DDM) : D1/(r-g) for dividend payers (Gordon growth).

Composite = median of the available methods (robust to one aggressive model).
Mispricing % = (composite / price - 1) x 100 . Positive => screens CHEAP, negative => RICH.
Verdict bands: > +15% undervalued, < -15% overvalued, else fair.

HONESTY: rough models on limited public data (no full financials / book value). Shown
as model estimates with every method visible — research, NOT a price target."""
import re
import statistics
import time

from psx_data import STATE, load_json, save_json


def num(s):
    if s is None:
        return None
    s = str(s).replace(",", "").strip().rstrip("%")
    m = re.match(r"^-?[\d.]+", s)
    if not m:
        return None
    v = float(m.group(0))
    suf = s[len(m.group(0)):].strip().upper()[:1]
    return v * {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}.get(suf, 1)


def main():
    fund = load_json(STATE / "fundamentals.json", {"tickers": {}})["tickers"]
    quant = load_json(STATE / "quant.json", {"tickers": {}})["tickers"]
    universe = load_json(STATE / "universe.json", {"symbols": {}})["symbols"]
    macro = load_json(STATE / "macro.json", {})
    dom = macro.get("domestic", {})

    # rate environment
    bond_y = num(dom.get("pib_10y")) or num(macro.get("sbp_rate")) or 12.0  # %
    if bond_y and bond_y < 3:  # guard bad parse
        bond_y = 12.0
    riskfree = num(macro.get("sbp_rate")) or 11.5
    req_return = riskfree + 6.0  # equity required return %, for DDM

    # sector median P/E across the universe
    sect_pes = {}
    for sym, v in fund.items():
        pe = num(v.get("pe"))
        sec = universe.get(sym, {}).get("name") or "PSX"
        # use broad sector via name is weak; group by DPS sector if present in quant? fall back to market
        if pe and 0 < pe < 60:
            sect_pes.setdefault("ALL", []).append(pe)
    market_med_pe = statistics.median(sect_pes["ALL"]) if sect_pes.get("ALL") else 7.0

    out = {}
    for sym, v in fund.items():
        eps = num(v.get("eps"))
        pe = num(v.get("pe"))
        fpe = num(v.get("forward_pe"))
        price = (quant.get(sym) or {}).get("close")
        if not price:
            m = re.search(r"[\d.]+", str(v.get("market_cap", "")))
            price = None
        if not eps or eps <= 0 or not price:
            continue  # can't value lossmakers / missing EPS with these methods

        # growth estimate from forward vs trailing P/E (expected 1y earnings growth)
        g = 0.0
        if fpe and fpe > 0 and pe and pe > 0:
            g = max(0.0, min(30.0, (pe / fpe - 1) * 100))
        else:
            g = 5.0

        methods = {}
        # 1. relative (market/sector median P/E)
        methods["relative_pe"] = round(market_med_pe * eps, 2)
        # 2. earnings power vs bond
        fair_pe_bond = 100.0 / (bond_y + 4.0)
        methods["earnings_power"] = round(fair_pe_bond * eps, 2)
        # 3. Graham revised
        methods["graham"] = round(eps * (8.5 + 2 * g) * 4.4 / bond_y, 2)
        # 4. DDM (payers only)
        div = num(v.get("div_yield"))
        if div and div > 0:
            d_rs = div / 100 * price  # annual dividend Rs
            gg = min(g, req_return - 3)  # keep r-g > 0
            if req_return - gg > 1:
                methods["ddm"] = round(d_rs * (1 + gg / 100) / ((req_return - gg) / 100), 2)

        vals = [x for x in methods.values() if x and x > 0]
        if not vals:
            continue
        composite = round(statistics.median(vals), 2)
        mis = round((composite / price - 1) * 100, 1)
        verdict = "undervalued" if mis >= 15 else "overvalued" if mis <= -15 else "fair"
        out[sym] = {
            "price": round(price, 2), "eps": eps, "pe": pe, "growth_est_pct": round(g, 1),
            "methods": methods, "composite_fair": composite,
            "mispricing_pct": mis, "verdict": verdict,
            "upside_pct": mis,  # alias
        }

    ranked = sorted(out.items(), key=lambda kv: -kv[1]["mispricing_pct"])
    save_json(STATE / "fairvalue.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "inputs": {"market_median_pe": round(market_med_pe, 2), "bond_yield_pct": bond_y,
                   "required_return_pct": req_return},
        "note": "model estimates from public fundamentals; research, not a price target",
        "tickers": out,
        "most_undervalued": [s for s, _ in ranked[:10]],
        "most_overvalued": [s for s, _ in ranked[-10:]],
    })
    print(f"fairvalue: {len(out)} tickers valued (market med P/E {market_med_pe:.1f}, bond {bond_y:.1f}%)")
    print("  cheapest:", ", ".join(f"{s} {v['mispricing_pct']:+.0f}%" for s, v in ranked[:5]))
    print("  richest: ", ", ".join(f"{s} {v['mispricing_pct']:+.0f}%" for s, v in ranked[-5:]))


if __name__ == "__main__":
    main()
