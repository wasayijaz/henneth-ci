"""Liquidity layer: how tradeable is each name, using the standard published measures.

Why this exists
---------------
Expanding the universe to the whole KSE All Share made ~350 thin names visible. Turnover
alone ("is it above X rupees") is a blunt gate: it says nothing about how much the price
moves when you trade, or what the round-trip costs. This module computes the measures the
literature and buy-side execution desks actually use, so the desk can say WHY a name is or
is not analysable rather than asserting it.

Measures (all from daily bars — no tick or quote data exists for PSX here):
  * ADTV            median daily traded value, PKR. Median not mean: one block trade should
                    not make an illiquid name look liquid.
  * Amihud (2002)   ILLIQ = mean(|return| / traded_value). Price impact per rupee traded.
                    Reported x1e6 (rupee-scaled) and, more usefully, as a PERCENTILE RANK
                    within PSX — absolute Amihud values are not comparable across markets,
                    so importing US thresholds would be meaningless here.
  * Roll (1984)     implied effective spread = 2*sqrt(-cov(r_t, r_t-1)). Undefined when the
                    serial covariance is positive (happens with trending/stale prices) —
                    reported as None, never fudged to zero.
  * Corwin-Schultz  (2012) high-low spread estimator. Needs intraday high/low, which the DPS
                    feed does NOT carry — only state/history_deep (core names) has them. So
                    this is computed where possible and null elsewhere, and the output always
                    records which estimator was available.
  * zero-volume / zero-return day fractions — staleness proxies in the spirit of Lesmond,
                    Ogden & Trzcinka (1999). A price that does not move because nothing
                    traded is not a price.
  * days-to-liquidate at a participation cap — the execution-desk question: at N% of a day's
                    volume, how many sessions to get out of a full position?

This is a MEASUREMENT module. It does not size positions and does not change CLAUDE.md
Rule 4 — that formula stays the single sizing path. Liquidity acts as an eligibility GATE
(reject / do-not-analyse), never as a hidden adjustment to share count, because a silent
adjustment here would desync the Strategist and the Auditor and read as a disagreement.

Idempotent. Missing data -> that metric is null, never guessed. Writes state/liquidity.json.
"""
import math
import statistics as st
import sys
import time

from psx_data import STATE, load_config, load_json, load_markets, market_of, save_json

WINDOW = 60          # sessions (~3 months) — long enough to survive one quiet week
MIN_BARS = 30        # below this, no liquidity claim is made at all

# Participation caps. 10-15% is the standard institutional default; 20-25% is aggressive and
# most brokers treat >25-30% as requiring sign-off. The one genuinely citable anchor is SEC
# Rule 10b-18, whose buyback safe harbour caps daily purchases at 25% of 4-week ADTV — i.e.
# the level at which a regulator presumes you are moving the price. We report BOTH a normal
# and a stress rate, because a name that liquidates in 2 days at 20% takes 4 at 10%, and the
# stressed number is the one that matters on the day you actually need out.
PARTICIPATION = 0.20
PARTICIPATION_STRESS = 0.10

# Square-root law of market impact: I(Q) = Y * sigma * sqrt(Q/V), with Y calibrated 0.5-1.0
# across developed equities and futures. Inverted against an impact budget C it gives a
# capacity: Q_max = V * (C / (Y*sigma))^2. Note the QUADRATIC sensitivity — halving the
# impact budget cuts allowed size 4x, which is why capacity collapses so fast in thin names.
# CAVEAT: Y is calibrated on developed markets. PSX small caps have thinner books, wider
# spreads and circuit breakers, so the true Y is plausibly higher and this capacity is
# optimistic. Treat as an upper bound, not a target.
IMPACT_Y = 0.75
IMPACT_BUDGET = 0.005   # 50bp of acceptable market impact

# SEC Rule 22e-4 liquidity buckets (Investment Company Act, adopted 2016-10-13) — the citable
# framework, used instead of an invented threshold table. The rule classifies at the position
# size ACTUALLY HELD, which is why days_to_liquidate below is computed from the desk's real
# max position value rather than from a notional round lot.
def sec_bucket(days):
    if days is None:
        return None
    if days <= 3:
        return "highly_liquid"      # convertible to cash in <=3 business days
    if days <= 7:
        return "moderately_liquid"  # >3 and <=7 calendar days
    return "illiquid"               # cannot be sold within 7 days without moving the price

# ADTV bands (PKR) for the headline grade. The B floor is deliberately 30M so it lines up
# with risk.min_avg_daily_traded_value_pkr — the existing signal gate — instead of inventing
# a second, conflicting notion of "liquid".
#
# THIS IS THE ONE GENUINELY CURRENCY-BOUND FILE in the analysis stack. quant.py, backtest.py,
# predictability.py, compute_fairvalue.py and correlation.py are all market-agnostic — they read
# state/history/{SYM}.json and never touch a currency. Here the numbers ARE rupees, so a second
# market needs its own ladder or every US name grades "A" on a PKR scale and the gate stops
# meaning anything. config/markets.json carries the per-market bands.
BANDS = [("A", 100e6), ("B", 30e6), ("C", 10e6), ("D", 2e6), ("E", 0)]


def bands_for(market: str, markets: dict):
    """Per-market ADTV ladder, falling back to the PSX bands above."""
    cfg = ((markets.get(market) or {}).get("liquidity") or {}).get("bands")
    if not cfg:
        return BANDS
    return [(g, float(floor)) for g, floor in cfg]


def _returns(closes):
    return [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]


K_CS = 3 - 2 * math.sqrt(2)   # 0.17157287525380996, the Corwin-Schultz constant
ZERO_RET_TOL = 5e-4           # LOT/FHT reference implementations treat |r| < 0.0005 as zero


def amihud(closes, values):
    """Amihud (2002) ILLIQ = mean(|r_t| / traded_value_t), reported x1e6.

    Two data rules, both load-bearing:
      * zero-VOLUME days are dropped — no trade is no observation, not infinite impact;
      * zero-RETURN days are dropped too. This is the frontier-market trap: a thin name that
        trades once at the open has real volume but a zero close-to-close return, which feeds
        ILLIQ a 0 and makes the LEAST liquid names score as the MOST liquid. Keeping those
        observations would invert the measure on exactly the stocks this gate exists to catch.

    Returns (illiq, n_obs) so callers can distrust a value built from a handful of days."""
    obs = []
    for i in range(1, len(closes)):
        if not closes[i - 1] or not values[i]:
            continue
        r = abs(closes[i] / closes[i - 1] - 1)
        if r < ZERO_RET_TOL:
            continue
        obs.append(r / values[i])
    if len(obs) < 10:
        return None, len(obs)
    return (sum(obs) / len(obs)) * 1e6, len(obs)


def roll_spread_pct(closes):
    """Roll (1984): S = 2*sqrt(-cov(r_t, r_t-1)), as % of price.

    Positive serial covariance violates the model and shows up in roughly half of real
    samples (Roll's own experience; Harris 1990 attributes it to small-sample noise). The
    modern convention — Corwin & Schultz (2012), Goyenko-Holden-Trzcinka (2009) — is to set
    those to ZERO rather than flip the sign, because sign-flipping converts estimation noise
    into fictitious spread and biases the measure up ~1.6x.

    We return None, not 0, for a per-name display value: the zero convention is for AVERAGING
    across a portfolio, and reporting "0.00% spread" on an untradeable stock would be the most
    misleading possible output. None means unknown, and the grade treats it as unknown."""
    r = _returns(closes)
    if len(r) < 20:
        return None
    a, b = r[1:], r[:-1]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (len(a) - 1)
    if cov >= 0:
        return None
    return round(2 * math.sqrt(-cov) * 100, 3)


def fht_pct(closes):
    """Fong, Holden & Trzcinka (2017) — closed-form approximation to the LOT cost measure:

        FHT = 2 * sigma * Phi^-1( (1 + z) / 2 )

    sigma = stdev of daily returns, z = proportion of zero-return days. Validated as the best
    proxy for the MAGNITUDE of transaction costs in markets without quote data — which is
    exactly PSX here. Chosen over a full LOT maximum-likelihood fit: same information, no
    optimizer, no non-convergence to handle.

    Bounded below at 0 by construction (unlike Roll and Corwin-Schultz), so a thin name can
    never report a negative or nonsensically tight cost."""
    r = _returns(closes)
    if len(r) < 20:
        return None
    z = sum(1 for x in r if abs(x) < ZERO_RET_TOL) / len(r)
    if z >= 1:
        return None                      # never moved: no cost is estimable, it is untradeable
    sigma = st.pstdev(r)
    if sigma <= 0:
        return None
    return round(2 * sigma * st.NormalDist().inv_cdf((1 + z) / 2) * 100, 3)


def corwin_schultz_pct(bars):
    """Corwin & Schultz (2012) high-low spread estimator, as % of price.

        beta  = [ln(H_t/L_t)]^2 + [ln(H_t+1/L_t+1)]^2
        gamma = [ln( max(H_t,H_t+1) / min(L_t,L_t+1) )]^2
        alpha = (sqrt(2*beta) - sqrt(beta)) / K - sqrt(gamma / K),   K = 3 - 2*sqrt(2)
        S     = 2*(e^alpha - 1) / (1 + e^alpha)

    Three corrections that are not optional:

    1. OVERNIGHT ADJUSTMENT. If day t+1's whole range sits above or below day t's close, the
       gap inflates gamma and drives alpha negative. Shift day t+1's range to touch the close
       first (the paper's own reference implementation does this).
    2. NEGATIVE VALUES -> ZERO, PER OBSERVATION, BEFORE AVERAGING. Corwin published a separate
       2014 note on exactly this: flooring at zero per two-day pair best matches TAQ spreads.
       Order matters — averaging first then flooring leaves large-cap portfolios with negative
       average spreads and flips the sign of the correlation with every other liquidity measure.
    3. DROP H == L DAYS. The estimator degenerates when a bar has no range. PSX has circuit
       breakers, so limit-locked days are common and would otherwise poison the estimate.

    Needs intraday high/low, which the DPS feed does not carry — only state/history_deep has
    them, so this is available for core names and null elsewhere."""
    est = []
    for i in range(len(bars) - 1):
        h1, l1, c1 = bars[i].get("high"), bars[i].get("low"), bars[i].get("close")
        h2, l2 = bars[i + 1].get("high"), bars[i + 1].get("low")
        if not all(isinstance(x, (int, float)) and x > 0 for x in (h1, l1, c1, h2, l2)):
            continue
        if h1 <= l1 or h2 <= l2:
            continue                      # limit-locked / no-range bar: estimator degenerates
        # (1) overnight adjustment — shift day t+1's range onto day t's close
        if h2 < c1:
            d = c1 - h2
            h2, l2 = h2 + d, l2 + d
        elif l2 > c1:
            d = l2 - c1
            h2, l2 = h2 - d, l2 - d
        beta = math.log(h1 / l1) ** 2 + math.log(h2 / l2) ** 2
        gamma = math.log(max(h1, h2) / min(l1, l2)) ** 2
        alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / K_CS - math.sqrt(gamma / K_CS)
        s = 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))
        est.append(max(s, 0.0))           # (2) floor per observation, then average
    return round((sum(est) / len(est)) * 100, 3) if len(est) >= 20 else None


def measure(sym, bars, deep):
    if not bars or len(bars) < MIN_BARS:
        return None
    w = bars[-WINDOW:]
    closes = [b["close"] for b in w]
    vols = [(b.get("volume") or 0) for b in w]
    values = [c * v for c, v in zip(closes, vols)]
    traded = [v for v in values if v > 0]
    if not traded:
        return None

    adtv = st.median(traded)
    r = _returns(closes)
    zero_vol = sum(1 for v in vols if not v) / len(vols)
    zero_ret = (sum(1 for x in r if abs(x) < ZERO_RET_TOL) / len(r)) if r else None
    sigma = st.pstdev(r) if len(r) > 2 else None

    cs = corwin_schultz_pct(deep[-WINDOW:]) if deep and len(deep) >= MIN_BARS else None
    roll = roll_spread_pct(closes)
    fht = fht_pct(closes)
    illiq, illiq_n = amihud(closes, values)

    # Preference order for the headline round-trip cost:
    #   Corwin-Schultz where high/low exists (uses intraday range — most information),
    #   else FHT (validated best for cost magnitude without quote data),
    #   else Roll (noisiest, and undefined about half the time).
    spread, src = ((cs, "corwin_schultz") if cs is not None else
                   (fht, "fht") if fht is not None else
                   (roll, "roll") if roll is not None else (None, None))

    return {
        "adtv_pkr": round(adtv),
        "adtv_m": round(adtv / 1e6, 2),
        "amihud_x1e6": round(illiq, 6) if illiq is not None else None,
        "amihud_obs": illiq_n,
        "roll_spread_pct": roll,
        "cs_spread_pct": cs,
        "fht_spread_pct": fht,
        "spread_pct": spread,
        "spread_estimator": src,
        "daily_sigma_pct": round(sigma * 100, 2) if sigma else None,
        "zero_volume_days_pct": round(zero_vol * 100, 1),
        "zero_return_days_pct": round(zero_ret * 100, 1) if zero_ret is not None else None,
        "bars": len(bars),
        "_sessions_used": len(w),
    }


def grade(m, bands=None):
    """Headline A-E from turnover, downgraded one notch for a wide spread or stale trading.
    Turnover says how much you can trade; spread and staleness say what it costs you.

    `bands` is per-market (see bands_for) — the turnover figure is in the market's own currency,
    so it must be graded against that market's ladder."""
    bands = bands or BANDS
    letter = next(g for g, floor in bands if m["adtv_pkr"] >= floor)
    sp, zv = m.get("spread_pct"), m.get("zero_volume_days_pct") or 0
    if (sp is not None and sp > 1.5) or zv > 10:
        i = min([g for g, _ in bands].index(letter) + 1, len(bands) - 1)
        letter = bands[i][0]
    return letter


def main():
    cfg = load_config()
    capital = cfg.get("capital_pkr", 0)
    risk = cfg.get("risk", {})
    liq_cfg = cfg.get("liquidity", {})
    research_min = liq_cfg.get("research_min_adtv_pkr", 5_000_000)
    research_min_bars = liq_cfg.get("research_min_bars", 500)
    signal_min = risk.get("min_avg_daily_traded_value_pkr", 30_000_000)
    max_pos_value = capital * risk.get("max_pct_per_trade", 8) / 100

    universe = load_json(STATE / "universe.json", {"symbols": {}})
    markets = load_markets()
    out = {}
    for sym in universe["symbols"]:
        bars = load_json(STATE / "history" / f"{sym}.json", None)
        deep = load_json(STATE / "history_deep" / f"{sym}.json", None)
        m = measure(sym, bars, deep)
        if not m:
            continue
        # Execution view: sessions to build or exit a FULL position at each participation rate.
        dtl = (max_pos_value / (m["adtv_pkr"] * PARTICIPATION)) if m["adtv_pkr"] else None
        dtl_s = (max_pos_value / (m["adtv_pkr"] * PARTICIPATION_STRESS)) if m["adtv_pkr"] else None
        m["days_to_liquidate"] = round(dtl, 2) if dtl else None
        m["days_to_liquidate_stress"] = round(dtl_s, 2) if dtl_s else None
        m["sec_bucket"] = sec_bucket(dtl_s)   # classify on the STRESSED rate, not the easy one
        m["capacity_1day_pkr"] = round(m["adtv_pkr"] * PARTICIPATION)
        # impact-budgeted capacity from the square-root law (see IMPACT_Y note above)
        sig = (m.get("daily_sigma_pct") or 0) / 100
        if sig > 0:
            m["capacity_at_50bp_pkr"] = round(m["adtv_pkr"] * (IMPACT_BUDGET / (IMPACT_Y * sig)) ** 2)
        # Per-market thresholds. `adtv_pkr` keeps its name for schema compatibility with every
        # existing consumer, but for a non-PSX symbol the figure is in THAT market's currency —
        # which is exactly why it cannot be graded or gated against the rupee ladder.
        mkt = market_of(sym, universe)
        mcfg = (markets.get(mkt) or {}).get("liquidity") or {}
        m["market"] = mkt
        m["currency"] = (markets.get(mkt) or {}).get("currency", "PKR")
        m["grade"] = grade(m, bands_for(mkt, markets))
        m["research_eligible"] = bool(
            m["adtv_pkr"] >= mcfg.get("research_min_adtv", research_min)
            and m["bars"] >= research_min_bars)
        # A market with signals_enabled:false can never produce a setup, whatever its turnover.
        # US coverage is research-tier by decision, not by accident — see config/markets.json.
        m["signal_eligible"] = bool(
            (markets.get(mkt) or {}).get("signals_enabled", True)
            and m["adtv_pkr"] >= mcfg.get("signal_min_adtv", signal_min))
        out[sym] = m

    # Amihud is scale-dependent and NOT comparable across markets, so an absolute threshold
    # imported from US literature would be meaningless on PSX. Rank within PSX instead.
    # Amihud's own procedure also trims the top and bottom 1% of the ILLIQ distribution — the
    # measure is extremely right-skewed and a couple of near-zero-volume names would otherwise
    # set the scale for everyone else.
    ranked = sorted([s for s in out if out[s].get("amihud_x1e6") is not None],
                    key=lambda s: out[s]["amihud_x1e6"])          # ascending: liquid -> illiquid
    cut = int(len(ranked) * 0.01) if len(ranked) >= 100 else 0
    for i, s in enumerate(ranked):
        in_tail = i < cut or i >= len(ranked) - cut
        # 100 = most liquid (lowest price impact), 0 = most illiquid
        out[s]["amihud_pctile"] = round((1 - i / max(len(ranked) - 1, 1)) * 100, 1)
        if in_tail:
            out[s]["amihud_tail"] = True   # in the trimmed 1% tail: value is extreme, treat with care

    save_json(STATE / "liquidity.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "window_sessions": WINDOW,
        "participation_cap": PARTICIPATION,
        "capital_pkr": capital,
        "max_position_value_pkr": max_pos_value,
        "thresholds": {
            "research_min_adtv_pkr": research_min,
            "research_min_bars": research_min_bars,
            "signal_min_adtv_pkr": signal_min,
        },
        "method": {
            "adtv": "median daily close*volume over the window (median resists block-trade spikes; ADV is unstable in thin names)",
            "amihud": "Amihud (2002) mean(|r|/traded value) x1e6, zero-volume AND zero-return days dropped; percentile ranked within PSX, 1% tails flagged",
            "roll": "Roll (1984) 2*sqrt(-cov(r_t,r_t-1)); null (not zero) when serial covariance >= 0",
            "fht": "Fong, Holden & Trzcinka (2017) 2*sigma*Phi^-1((1+z)/2); closed-form LOT approximation, best cost proxy without quote data",
            "corwin_schultz": "Corwin & Schultz (2012) high-low estimator with overnight adjustment, per-observation zero floor, H==L bars dropped; needs high/low so core (deep history) only",
            "days_to_liquidate": f"max position value / ({PARTICIPATION:.0%} of ADTV); stress variant at {PARTICIPATION_STRESS:.0%}",
            "sec_bucket": "SEC Rule 22e-4 classification, applied to the STRESSED days-to-liquidate",
            "capacity_at_50bp": f"square-root law inverted at a {IMPACT_BUDGET:.2%} impact budget with Y={IMPACT_Y}; developed-market calibration, so an upper bound on PSX",
        },
        "caveats": [
            "Every constant here is calibrated on developed markets. Nothing in this file has been validated on PSX data.",
            "Turnover ratio is NOT computed: it requires FREE FLOAT, and using total shares outstanding would badly overstate illiquidity for the many PSX names with large locked-up sponsor or government holdings. Better absent than wrong.",
        ],
        "tickers": out,
    })

    g = {}
    for v in out.values():
        g[v["grade"]] = g.get(v["grade"], 0) + 1
    res = sum(1 for v in out.values() if v["research_eligible"])
    sig = sum(1 for v in out.values() if v["signal_eligible"])
    cs_n = sum(1 for v in out.values() if v.get("cs_spread_pct") is not None)
    print(f"liquidity: {len(out)} tickers  grades " + " ".join(f"{k}={g.get(k,0)}" for k, _ in BANDS))
    print(f"  research-eligible {res} · signal-eligible {sig} · Corwin-Schultz available for {cs_n}")
    sys.exit(0)


if __name__ == "__main__":
    main()
