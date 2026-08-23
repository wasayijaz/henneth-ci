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


def _live_pe(fsc, fund, sym):
    """P/E off TODAY's live price (score_fundamentals.py's live_pe, already computed once —
    reused here rather than re-derived, so this file and the Room dossier never disagree with
    the Screener over a stale-vs-live P/E). Falls back to fundamentals.json's own scrape-time
    ratio only when no score exists yet for the symbol."""
    m = (fsc.get(sym) or {}).get("metrics") or {}
    pe = m.get("pe")
    return pe if pe is not None else num((fund.get(sym) or {}).get("pe"))


def main():
    fund = load_json(STATE / "fundamentals.json", {"tickers": {}})["tickers"]
    fsc = load_json(STATE / "fundamental_scores.json", {"tickers": {}})["tickers"]
    quant = load_json(STATE / "quant.json", {"tickers": {}})["tickers"]
    universe = load_json(STATE / "universe.json", {"symbols": {}})["symbols"]
    sectors = load_json(STATE / "sectors.json", {"tickers": {}})["tickers"]
    macro = load_json(STATE / "macro.json", {})
    dom = macro.get("domestic", {})

    # rate environment
    bond_y = num(dom.get("pib_10y")) or num(macro.get("sbp_rate")) or 12.0  # %
    if bond_y and bond_y < 3:  # guard bad parse
        bond_y = 12.0
    riskfree = num(macro.get("sbp_rate")) or 11.5
    req_return = riskfree + 6.0  # equity required return %, for DDM

    # Median P/E per REAL PSX sector (fetch_sectors.py), plus the market median as a fallback.
    # This method is documented and rendered as "priced like its PEERS"; until sectors existed it
    # silently used the whole-market median, so the label promised peers and the number meant market.
    # A sector needs MIN_PEERS real P/Es before its median is meaningful — below that, say so and
    # fall back to the market rather than quietly passing off a 2-stock median as a peer group.
    MIN_PEERS = 3
    sect_of = {s: r.get("sector") for s, r in sectors.items()}
    sect_pes, all_pes = {}, []
    for sym, v in fund.items():
        pe = _live_pe(fsc, fund, sym)
        if pe and 0 < pe < 60:
            all_pes.append(pe)
            sec = sect_of.get(sym)
            if sec:
                sect_pes.setdefault(sec, []).append(pe)
    market_med_pe = statistics.median(all_pes) if all_pes else 7.0
    sect_med_pe = {s: statistics.median(pes) for s, pes in sect_pes.items() if len(pes) >= MIN_PEERS}

    out = {}
    for sym, v in fund.items():
        eps = num(v.get("eps"))
        pe = _live_pe(fsc, fund, sym)
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
        # 1. relative: priced like its actual sector peers, market median only if the peer group
        #    is too thin to mean anything. The basis is published so the claim stays checkable.
        my_sector = sect_of.get(sym)
        peer_pe = sect_med_pe.get(my_sector)
        methods["relative_pe"] = round((peer_pe if peer_pe else market_med_pe) * eps, 2)
        rel_basis = ({"basis": "sector", "sector": my_sector, "median_pe": round(peer_pe, 2),
                      "n_peers": len(sect_pes.get(my_sector, []))}
                     if peer_pe else
                     {"basis": "market", "sector": my_sector,
                      "median_pe": round(market_med_pe, 2), "n_peers": len(all_pes),
                      "why": f"fewer than {MIN_PEERS} peers with a usable P/E in this sector"})
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
            "price": round(price, 2), "eps": eps, "eps_basis": v.get("eps_basis", "unknown"),
            "pe": pe, "growth_est_pct": round(g, 1),
            "methods": methods, "relative_pe_basis": rel_basis, "sector": my_sector,
            "composite_fair": composite,
            "mispricing_pct": mis, "verdict": verdict,
            "upside_pct": mis,  # alias
        }

    ranked = sorted(out.items(), key=lambda kv: -kv[1]["mispricing_pct"])
    save_json(STATE / "fairvalue.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "inputs": {"market_median_pe": round(market_med_pe, 2), "bond_yield_pct": bond_y,
                   "required_return_pct": req_return, "min_peers_for_sector_median": MIN_PEERS,
                   "sector_median_pe": {s: round(p, 2) for s, p in sorted(sect_med_pe.items())}},
        "note": ("model estimates from public fundamentals; research, not a price target. "
                 "relative_pe is the median P/E of the stock's own PSX sector x EPS — each ticker's "
                 "relative_pe_basis says whether real peers or (for thin sectors) the market was used."),
        "tickers": out,
        "most_undervalued": [s for s, _ in ranked[:10]],
        "most_overvalued": [s for s, _ in ranked[-10:]],
    })
    print(f"fairvalue: {len(out)} tickers valued (market med P/E {market_med_pe:.1f}, bond {bond_y:.1f}%)")
    print("  cheapest:", ", ".join(f"{s} {v['mispricing_pct']:+.0f}%" for s, v in ranked[:5]))
    print("  richest: ", ", ".join(f"{s} {v['mispricing_pct']:+.0f}%" for s, v in ranked[-5:]))


if __name__ == "__main__":
    main()
