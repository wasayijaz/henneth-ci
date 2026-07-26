"""Turn raw fundamentals into a plain-English scorecard an untrained user can read.
Deterministic (no LLM, no hallucination) — every verdict traces to a printed number.
Reads state/fundamentals.json, writes state/fundamental_scores.json.

Five dimensions, each a rating + one sentence:
  valuation, profitability, dividend, growth-note, size/stability.
Plus an overall one-line read. Ratings are relative to the universe (percentiles),
so 'cheap' means cheap FOR PSX, not vs global markets."""
import re
import time

import numpy as np

from psx_data import STATE, load_json, save_json


def num(s):
    """Parse '294.52B', '6.61%', '6.70', '1.30B' -> float (base units / percent)."""
    if s is None:
        return None
    s = str(s).replace(",", "").strip().rstrip("%")
    m = re.match(r"^-?[\d.]+", s)
    if not m:
        return None
    val = float(m.group(0))
    suf = s[len(m.group(0)):].strip().upper()[:1]
    return val * {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}.get(suf, 1)


def pctile(v, arr):
    arr = [x for x in arr if x is not None]
    if not arr or v is None:
        return None
    return round(float((np.array(arr) <= v).mean() * 100))


def main():
    fund = load_json(STATE / "fundamentals.json", {"tickers": {}})["tickers"]
    live = load_json(STATE / "live.json", {"tickers": {}})["tickers"]

    def live_pe(v, sym):
        """P/E off TODAY's live price, not stockanalysis.com's own scrape-time price (that
        scrape is weekly — the ratio it publishes can be a stale-price/current-EPS mismatch).
        Falls back to the scraped ratio only when we lack a live price or EPS to derive it."""
        px = (live.get(sym) or {}).get("current")
        eps = num(v.get("eps"))
        if px and eps and eps > 0:
            return round(px / eps, 2)
        return num(v.get("pe"))

    def derived_payout(v):
        """Payout ratio from the desk's OWN yield + EPS + live price, not the vendor's scraped
        figure — the scraped payout_ratio can disagree with the desk's own yield/earnings math
        because it's computed off a different price snapshot and sometimes a different EPS basis
        (TTM vs FY). Falls back to the scraped value only when yield/EPS/price aren't all present."""
        px = (live.get(sym) or {}).get("current")
        yld = num(v.get("div_yield"))
        eps = num(v.get("eps"))
        if px and yld and eps and eps > 0:
            dps = yld / 100 * px
            return round(dps / eps * 100, 1)
        return num(v.get("payout_ratio"))

    # universe distributions for relative ratings
    pes = [num(v.get("pe")) for v in fund.values()]
    ylds = [num(v.get("div_yield")) for v in fund.values()]
    margins = []
    for v in fund.values():
        rev, ni = num(v.get("revenue")), num(v.get("net_income"))
        margins.append(ni / rev * 100 if rev and ni else None)

    out = {}
    for sym, v in fund.items():
        pe = live_pe(v, sym)
        fpe = num(v.get("forward_pe"))
        yld = num(v.get("div_yield"))
        payout = derived_payout(v)
        rev, ni = num(v.get("revenue")), num(v.get("net_income"))
        margin = ni / rev * 100 if rev and ni else None
        mcap = num(v.get("market_cap"))
        beta = num(v.get("beta"))

        cards = []
        score = 0
        n = 0

        # valuation
        pr = pctile(pe, pes)
        if pe is not None and pr is not None:
            n += 1
            if pr <= 33:
                cards.append(("Valuation", "cheap", f"P/E {pe:g} is in the cheapest third of PSX names — you pay less per rupee of earnings."))
                score += 2
            elif pr <= 66:
                cards.append(("Valuation", "fair", f"P/E {pe:g} is mid-pack for PSX — priced roughly in line with peers."))
                score += 1
            else:
                cards.append(("Valuation", "expensive", f"P/E {pe:g} is in the priciest third — the market expects a lot from it."))
            if fpe and pe and fpe < pe:
                cards.append(("Forward view", "improving", f"Forward P/E {fpe:g} < trailing {pe:g} — earnings are expected to grow."))

        # profitability
        if margin is not None:
            n += 1
            if margin >= 20:
                cards.append(("Profitability", "strong", f"Keeps {margin:.0f}% of revenue as profit — a highly profitable business."))
                score += 2
            elif margin >= 8:
                cards.append(("Profitability", "healthy", f"Net margin {margin:.0f}% — solidly profitable."))
                score += 1
            elif margin > 0:
                cards.append(("Profitability", "thin", f"Net margin only {margin:.0f}% — little cushion if costs rise."))
            else:
                cards.append(("Profitability", "lossmaking", "Currently unprofitable — higher risk."))

        # dividend
        if yld is not None:
            n += 1
            safe = payout is None or payout <= 75
            if yld >= 6 and safe:
                cards.append(("Dividend", "generous & covered", f"Pays a {yld:g}% yield" + (f", using {payout:.0f}% of profit — sustainable." if payout else ".")))
                score += 2
            elif yld >= 3:
                cards.append(("Dividend", "moderate", f"{yld:g}% yield" + (f", payout {payout:.0f}%." if payout else ".")))
                score += 1
            elif yld > 0:
                cards.append(("Dividend", "small", f"{yld:g}% yield — not an income stock."))
            if payout and payout > 90:
                cards.append(("Dividend safety", "stretched", f"Pays out {payout:.0f}% of earnings — a bad year could force a cut."))
        elif yld == 0 or (v.get("div_yield") in (None, "")):
            cards.append(("Dividend", "none", "Pays no dividend — return depends entirely on price."))

        # size / stability
        if mcap:
            n += 1
            sz = "large-cap" if mcap >= 3e11 else "mid-cap" if mcap >= 5e10 else "small-cap"
            note = {"large-cap": "big, liquid, generally steadier.",
                    "mid-cap": "medium size — more room to grow, more wobble.",
                    "small-cap": "small — can move fast, thinner liquidity, higher risk."}[sz]
            b = f" Beta {beta:g} ({'moves more than' if beta and beta>1 else 'moves less than'} the market)." if beta else ""
            cards.append(("Size & stability", sz, f"{v.get('market_cap')} market cap — {note}{b}"))
            score += 1 if sz != "small-cap" else 0

        rating = "—"
        if n:
            pct = score / (n * 2)
            rating = "attractive" if pct >= 0.66 else "mixed" if pct >= 0.33 else "caution"
        overall = {
            "attractive": "Screens well on the numbers: reasonable price, real profits, and/or a covered dividend.",
            "mixed": "A balanced picture — some strengths, some flags. Read the cards below.",
            "caution": "The fundamentals raise flags (rich price, thin profit, or an unsafe payout).",
            "—": "Not enough verified fundamentals to score yet.",
        }[rating]

        out[sym] = {
            "rating": rating, "overall": overall, "cards": cards,
            "metrics": {"pe": pe, "forward_pe": fpe, "div_yield": yld,
                        "payout_ratio": payout, "net_margin": round(margin, 1) if margin is not None else None,
                        "market_cap": mcap, "beta": beta},
        }

    save_json(STATE / "fundamental_scores.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "note": "relative to the PSX universe; deterministic from stockanalysis fundamentals",
        "tickers": out,
    })
    rated = [s for s, v in out.items() if v["rating"] == "attractive"]
    print(f"fundamental scores: {len(out)} tickers | attractive: {', '.join(rated[:12])}")


if __name__ == "__main__":
    main()
