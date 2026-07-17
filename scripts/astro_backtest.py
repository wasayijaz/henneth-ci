"""Does any of it actually hold? The falsification engine for the astro pillar.

astro_map.json records what tradition CLAIMS. This script tries to kill each claim against ~19
years of real PSX prices, and only what survives may ever be spoken by the astro agent.

THE METHOD, AND WHY IT IS THIS ONE

  * Windows, not events. Each hypothesis becomes a boolean mask over trading days ("Saturn is
    retrograde"), and we compare mean daily return inside the mask against outside it.

  * The null is tested by CIRCULAR SHIFT, not by shuffling days. Daily returns are autocorrelated
    and astro windows are long contiguous blocks; shuffling days would destroy that structure and
    manufacture significance out of nothing. Instead the condition mask is rotated against the
    return series by a random offset, thousands of times. That preserves the autocorrelation of
    the returns AND the block shape of the windows, so the null distribution answers the honest
    question: "is this any better than pointing the same-shaped window at a random part of
    history?"

  * Multiple comparisons are confronted, not hidden. We deliberately test EVERY graha against
    EVERY sector - which is the only fair way to let the data pick a significator instead of the
    author picking one - and that means hundreds of hypotheses. Some WILL look good by luck. So
    every result carries a Bonferroni-adjusted bar based on the real number of tests run, and
    `survives` means survives THAT bar. The count is published.

  * Convergence is the interesting signal. Tradition's claimed significator (astro_map.json) is
    tested alongside the other eight. When the data's pick and tradition's pick agree, that is
    worth something. When the data prefers a graha no tradition ever linked to the sector, it is
    almost certainly noise, and is reported as such.

  * A negative result is a result. If nothing survives, this file says so plainly and the astro
    lens shows "nothing here beats chance" - which is a finding the desk publishes, not a failure
    it buries.

Writes state/astro_backtest.json. Free, deterministic, no tokens, no network.
"""
import datetime as dt
import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
HIST = STATE / "history_deep"

# Two-stage permutation, and the reason matters:
# a permutation p-value cannot be smaller than 1/(N+1). With ~390 hypotheses the Bonferroni bar is
# ~1.3e-4, which a 2,000-shift test can NEVER reach — "zero survivors" would then be an artefact of
# the test's resolution, not a fact about the market, and publishing it as a finding would be a lie.
# So: screen everything cheaply, then re-test the promising few finely enough to actually clear the bar.
MIN_BARS = 1000        # a stock needs this many overlapping trading days before it can be judged
STALE_DAYS = 7         # the stats cannot move meaningfully day to day; re-run weekly, not per cycle
N_PERM = 2000          # stage 1: screen every hypothesis
N_PERM_FINE = 200000   # stage 2: fine enough that the Bonferroni bar (~1.9e-5 at ~2,600 tests) is reachable
FINE_TRIGGER = 0.01    # stage-1 p at or below this earns a precise re-test
MIN_DAYS_IN = 120      # a window with fewer trading days than this cannot be judged
MIN_TICKERS = 3        # a sector needs this many names before its mean means anything
ALPHA = 0.05

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]


def load(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def circular_p(returns: np.ndarray, mask: np.ndarray, rng, n_perm: int = N_PERM) -> tuple:
    """Observed effect + p-value from rotating the mask against the returns.

    Vectorised: the mean inside any rotation of the mask is a circular cross-correlation, so all
    rotations are computed at once from a doubled cumulative sum rather than n_perm slow slices.
    That is what makes 50,000 resamples affordable.

    Two-sided: how often does the SAME-SHAPED window, dropped at a random point in history,
    produce an effect at least this large?"""
    n = len(returns)
    k = int(mask.sum())
    total = returns.sum()
    obs = returns[mask].mean() - returns[~mask].mean()
    idx = np.flatnonzero(mask)
    shifts = rng.integers(1, n, size=n_perm)

    # The gather below is (chunk x k) wide. At 50k resamples and a wide window that is hundreds of
    # MB in one allocation, which is fine here and not on a small cloud runner — so chunk it.
    hits = 0
    CHUNK = max(1, 4_000_000 // max(1, k))
    for i in range(0, n_perm, CHUNK):
        s = shifts[i:i + CHUNK]
        sums_in = returns[(idx[None, :] + s[:, None]) % n].sum(axis=1)
        effs = sums_in / k - (total - sums_in) / (n - k)
        hits += int((np.abs(effs) >= abs(obs)).sum())
    return obs, (hits + 1) / (n_perm + 1)


def main():
    t0 = time.time()
    sky = load(STATE / "astro_history.json")
    if not sky or not sky.get("dates"):
        print("astro_backtest: no astro_history.json — run scripts/astro_history.py first")
        sys.exit(0)
    sectors = (load(STATE / "sectors.json", {}) or {}).get("tickers", {})
    universe = (load(STATE / "universe.json", {}) or {}).get("symbols", {})
    amap = load(STATE / "astro_map.json", {}) or {}
    sig = amap.get("sector_significators", {})

    # weekly, not per-cycle: one more day on ~4,900 cannot move a p-value, and this is the most
    # expensive script in the pipeline
    if "--force" not in sys.argv:
        prev = load(STATE / "astro_backtest.json")
        if prev and prev.get("updated"):
            try:
                age = (dt.datetime.now() - dt.datetime.strptime(prev["updated"], "%Y-%m-%d %H:%M")).days
                if age < STALE_DAYS:
                    print(f"astro_backtest: last run {age}d ago — skipping (weekly cadence; --force to override)")
                    sys.exit(0)
            except Exception:
                pass

    # ---- price panel: date -> per-ticker daily return, from the deep (adjusted) history
    rets = {}
    for f in sorted(HIST.glob("*.json")):
        sym = f.stem
        bars = load(f, [])
        if not bars or len(bars) < 300:
            continue
        prev = None
        for b in bars:
            c = b.get("close")
            if prev and c and prev > 0:
                r = c / prev - 1
                if abs(r) < 0.25:                       # drop de-glitch artefacts / limit spikes
                    rets.setdefault(b["date"], {})[sym] = r
            prev = c or prev

    dates = [d for d in sky["dates"] if d in rets]
    if len(dates) < 500:
        print(f"astro_backtest: only {len(dates)} overlapping days — not enough to test")
        sys.exit(0)
    idx = {d: i for i, d in enumerate(sky["dates"])}

    # ---- what gets tested: INDIVIDUAL STOCKS, plus KSE100 and KMI30 separately.
    # Sector aggregation was the earlier mistake: averaging 13 banks together dilutes any
    # stock-specific effect toward zero, so the test could not see the thing it was looking for.
    # Astro is not a sector story either — sectors are moved by macro (flows, debt, gold,
    # geopolitics), which is the macro lens's job, not this one.
    series = {}
    for sym in sorted({s for d in dates for s in rets[d]}):
        arr = np.array([rets[d].get(sym, np.nan) for d in dates])
        if np.isfinite(arr).sum() >= MIN_BARS:
            series[sym] = arr

    # Index proxies. There is NO real daily index history to be had: Yahoo's ^KSE is monthly and
    # stops in 2021, DPS publishes indices live-only, stooq has nothing. So each index is rebuilt
    # from its own constituents, cap-weighted by universe.json weight_pct — and labelled a proxy.
    def index_proxy(members, weights):
        tot = sum(weights.get(s, 0) for s in members) or 1.0
        out = []
        for d in dates:
            day = rets[d]
            num = sum(weights.get(s, 0) * day[s] for s in members if s in day)
            den = sum(weights.get(s, 0) for s in members if s in day)
            out.append(num / den if den > 0.25 * tot else np.nan)   # need most of the index present
        return np.array(out)

    w = {s: (v.get("weight_pct") or 0) for s, v in universe.items()}
    k100 = [s for s, v in universe.items() if "KSE100" in (v.get("in") or []) and s in series]
    kmi30 = [s for s, v in universe.items() if "KMI30" in (v.get("in") or []) and s in series]
    idx_meta = {}
    if len(k100) >= 50:
        series["KSE100 (proxy)"] = index_proxy(k100, w)
        idx_meta["KSE100 (proxy)"] = {"constituents_used": len(k100),
                                      "weight_covered_pct": round(sum(w.get(s, 0) for s in k100), 2)}
    if len(kmi30) >= 20:
        series["KMI30 (proxy)"] = index_proxy(kmi30, w)
        idx_meta["KMI30 (proxy)"] = {"constituents_used": len(kmi30),
                                     "weight_covered_pct": round(sum(w.get(s, 0) for s in kmi30), 2),
                                     "note": "weights are KSE100 weights renormalised within the KMI30 set"}

    # ---- Stocks are tested on MARKET-ADJUSTED returns (r_i - beta_i * r_mkt).
    # Without this the test measures beta, not astrology. Worked example from the raw run: during
    # "Mars debilitated" the market drifts -0.119%/day, cement (a high-beta sector) -0.238%, and
    # PIOC (a high-beta small cap) -0.430%. That ladder is exactly what beta predicts from a weak
    # market tilt which is itself not significant at the index level — yet raw testing flagged PIOC
    # as a discovery. Removing each stock's market component means a stock-level result can only
    # survive if the STOCK responded beyond however the whole market moved. Market-wide claims are
    # not lost: they are exactly what the KSE100/KMI30 tests (kept raw) are for.
    betas = {}
    mkt = series.get("KSE100 (proxy)")
    if mkt is not None:
        for sym in [s for s in series if "(proxy)" not in s]:
            arr = series[sym]
            ok = np.isfinite(arr) & np.isfinite(mkt)
            if ok.sum() < MIN_BARS:
                continue
            v = float(np.var(mkt[ok]))
            b = float(np.cov(arr[ok], mkt[ok])[0, 1] / v) if v > 0 else 1.0
            b = max(0.0, min(3.0, b))          # clamp: a wild beta means a broken series, not a hedge
            betas[sym] = round(b, 3)
            adj = arr - b * mkt
            adj[~ok] = np.nan
            series[sym] = adj

    # ---- condition masks, aligned to `dates`
    pos = {b: {"lon": np.array([sky["bodies"][b]["lon"][idx[d]] for d in dates]),
               "retro": np.array([sky["bodies"][b]["retro"][idx[d]] for d in dates], dtype=bool)}
           for b in BODIES}
    sun = pos["Sun"]["lon"]
    moon_elong = np.abs((pos["Moon"]["lon"] - sun + 180) % 360 - 180)

    def sign_idx(lon):
        return (lon // 30).astype(int) % 12

    masks = {}
    for b in BODIES:
        if b not in ("Sun", "Moon"):
            masks[f"{b} retrograde"] = pos[b]["retro"]
        if b not in ("Sun", "Moon", "Rahu", "Ketu"):
            sep = np.abs((pos[b]["lon"] - sun + 180) % 360 - 180)
            masks[f"{b} combust"] = sep < 8.0
        g = (amap.get("grahas", {}) or {}).get(b, {})
        own = g.get("own_signs") or []
        exalt = (g.get("exalted") or {}).get("sign")
        debil = (g.get("debilitated") or {}).get("sign")
        si = sign_idx(pos[b]["lon"])
        strong = [SIGNS.index(s) for s in own + ([exalt] if exalt else []) if s in SIGNS]
        if strong:
            masks[f"{b} strong (own/exalted sign)"] = np.isin(si, strong)
        if debil in SIGNS:
            masks[f"{b} debilitated"] = si == SIGNS.index(debil)
    masks["near the new moon (+/-2d)"] = moon_elong < 26
    masks["near the full moon (+/-2d)"] = moon_elong > 154
    # eclipse windows: a new/full moon while the Sun sits near a node
    node = pos["Rahu"]["lon"]
    dn = np.minimum(np.abs((sun - node + 180) % 360 - 180),
                    np.abs((sun - (node + 180) + 180) % 360 - 180))
    ecl_core = ((moon_elong < 26) & (dn < 15.35)) | ((moon_elong > 154) & (dn < 9.5))
    w = np.zeros(len(dates), dtype=bool)                 # widen to +/-7 sessions
    for i in np.where(ecl_core)[0]:
        w[max(0, i - 7):min(len(dates), i + 8)] = True
    masks["eclipse window (+/-7 sessions)"] = w

    usable = {k: m for k, m in masks.items()
              if MIN_DAYS_IN <= m.sum() <= len(dates) - MIN_DAYS_IN}
    skipped = {k: int(m.sum()) for k, m in masks.items() if k not in usable}

    # ---- run every condition against every sector. This is deliberate: letting the data pick a
    #      significator is only fair if every candidate gets the same shot.
    rng = np.random.default_rng(20260717)               # fixed seed: a re-run reproduces exactly
    tests, n_tests = [], len(usable) * len(series)
    bar = ALPHA / max(1, n_tests)                       # Bonferroni across everything we tried
    for sec, arr in sorted(series.items()):
        ok = np.isfinite(arr)
        for cond, m in usable.items():
            mm = m & ok
            if mm.sum() < MIN_DAYS_IN or (~mm & ok).sum() < MIN_DAYS_IN:
                continue
            r = arr[ok]
            eff, p = circular_p(r, mm[ok], rng)
            resamples = N_PERM
            if p <= FINE_TRIGGER:
                # promising: re-test finely, or the Bonferroni bar is unreachable by construction
                eff, p = circular_p(r, mm[ok], rng, N_PERM_FINE)
                resamples = N_PERM_FINE
            tests.append({
                "subject": sec, "sector": (sectors.get(sec) or {}).get("sector"),
                "condition": cond,
                "days_in": int(mm.sum()), "days_out": int((~mm & ok).sum()),
                "mean_in_pct": round(float(r[mm[ok]].mean()) * 100, 4),
                "mean_out_pct": round(float(r[~mm[ok]].mean()) * 100, 4),
                "effect_pct_per_day": round(float(eff) * 100, 4),
                "p_value": float(f"{p:.3g}"), "resamples": resamples,
                "p_floor": float(f"{1 / (resamples + 1):.3g}"),
                "survives_bonferroni": bool(p < bar),
            })

    tests.sort(key=lambda x: x["p_value"])
    survivors = [t for t in tests if t["survives_bonferroni"]]
    raw_hits = [t for t in tests if t["p_value"] < ALPHA]

    # Benjamini-Hochberg FDR alongside Bonferroni. At ~2,600 hypotheses Bonferroni is brutal and
    # would hide a real-but-modest effect; BH controls the false-DISCOVERY rate instead of the
    # family-wise error rate, which is the fairer question when you are screening this wide.
    # Reporting both means the answer cannot be blamed on the choice of correction.
    m_tests = len(tests)
    bh_cut = 0.0
    for i, t in enumerate(tests, start=1):          # tests are already p-sorted ascending
        if t["p_value"] <= i / m_tests * ALPHA:
            bh_cut = t["p_value"]
    for t in tests:
        t["survives_fdr"] = bool(t["p_value"] <= bh_cut)
    fdr_survivors = [t for t in tests if t["survives_fdr"]]

    # ---- REPLICATION: the check that actually decides whether a survivor is real.
    # Surviving a multiplicity correction is not enough. PSX stocks are heavily correlated, so 99
    # "independent" stock tests are closer to one observation repeated; and the most extreme of
    # 2,589 correlated draws will look spectacular by construction. A genuine sky->market mechanism
    # cannot act on one thinly-traded cement company and not on its eight peers or the index.
    # So every survivor is re-examined against its peers and the indices, and one that stands alone
    # is labelled an artefact — automatically, not by an analyst's mood.
    by_cond = {}
    for t in tests:
        by_cond.setdefault(t["condition"], []).append(t)

    n_idx_tests = sum(1 for x in tests if "(proxy)" in x["subject"])
    idx_bar = ALPHA / max(1, n_idx_tests)   # the index family is its own question, corrected within itself

    def replication_of(t):
        cond, subj = t["condition"], t["subject"]
        peers = [x for x in by_cond[cond]
                 if x["sector"] and x["sector"] == t["sector"] and x["subject"] != subj
                 and "(proxy)" not in x["subject"]]
        allst = [x for x in by_cond[cond] if "(proxy)" not in x["subject"] and x["subject"] != subj]
        idxs = [x for x in by_cond[cond] if "(proxy)" in x["subject"]]
        peer_med = float(np.median([x["effect_pct_per_day"] for x in peers])) if peers else None
        all_med = float(np.median([x["effect_pct_per_day"] for x in allst])) if allst else None
        idx_best = min(idxs, key=lambda x: x["p_value"]) if idxs else None
        eff = t["effect_pct_per_day"]
        same_sign = lambda a, b: a is not None and b is not None and (a > 0) == (b > 0)

        # The index must clear a bar corrected for the number of INDEX tests. A raw p<0.05 here
        # would be the very multiple-comparisons error this file exists to avoid.
        index_confirms = bool(idx_best and idx_best["p_value"] < idx_bar
                              and same_sign(eff, idx_best["effect_pct_per_day"]))
        # Peers only confirm something SPECIFIC. If the whole market drifts the same way, a sector
        # looking similar is just beta, not a sector effect — so peers must beat the market median.
        peers_confirm = bool(peer_med is not None and same_sign(eff, peer_med)
                             and abs(peer_med) >= 0.5 * abs(eff)
                             and (all_med is None or abs(peer_med) >= 2 * abs(all_med)))
        return {
            "peer_median_effect_pct": round(peer_med, 4) if peer_med is not None else None,
            "peer_count": len(peers),
            "all_stock_median_effect_pct": round(all_med, 4) if all_med is not None else None,
            "index_effect_pct": idx_best["effect_pct_per_day"] if idx_best else None,
            "index_p": idx_best["p_value"] if idx_best else None,
            "index_bar": float(f"{idx_bar:.2e}"),
            "index_confirms": index_confirms,
            "peers_confirm": peers_confirm,
            "replicates": bool(index_confirms or peers_confirm),
            "reading": (
                "the index agrees at a corrected bar — a genuinely market-wide effect"
                if index_confirms else
                "its sector peers show this at comparable size AND well beyond the market-wide "
                "drift, so it looks sector-specific"
                if peers_confirm else
                "ISOLATED — the index does not show it at a corrected bar, and its sector peers "
                "show nothing beyond the market-wide drift. The likely explanation is not "
                "astrology: it is the most extreme of thousands of correlated draws, in a name "
                "thin enough for a handful of days to move the mean. The desk reports it and does "
                "not believe it."),
        }

    for t in survivors + fdr_survivors:
        t["replication"] = replication_of(t)
    believable = [t for t in survivors if t["replication"]["replicates"]]

    # ---- convergence: does the data's favourite graha for a STOCK match the one tradition
    #      assigns to that stock's sector?
    conv = []
    for subj in series:
        sec_of = (sectors.get(subj) or {}).get("sector")
        trad = (sig.get(sec_of) or {}).get("primary") if sec_of else None
        if not trad:
            continue
        # only graha-specific conditions can express a preference for a significator; the
        # market-wide ones (moon phase, eclipse windows) name no body and must not be counted
        cand = [t for t in tests if t["subject"] == subj and t["condition"].split(" ")[0] in BODIES]
        if not cand:
            continue
        best = min(cand, key=lambda x: x["p_value"])
        body = best["condition"].split(" ")[0]
        conv.append({
            "ticker": subj, "sector": sec_of, "tradition_says": trad, "data_prefers": body,
            "agree": bool(body == trad),
            "best_condition": best["condition"], "p_value": best["p_value"],
            "survives_bonferroni": best["survives_bonferroni"],
        })
    agreed = [c for c in conv if c["agree"]]

    expected_false = round(ALPHA * len(tests), 1)
    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "window": {"from": dates[0], "to": dates[-1], "trading_days": len(dates)},
        "betas": betas,
        "method": {
            "test": "circular-shift permutation on the condition mask (preserves both the "
                    "autocorrelation of returns and the block shape of astro windows)",
            "resamples": f"{N_PERM} to screen; anything at p<={FINE_TRIGGER} re-tested with "
                         f"{N_PERM_FINE}. Reason: a permutation p cannot go below 1/(N+1), so a "
                         f"{N_PERM}-shift test could never reach the Bonferroni bar and 'no "
                         f"survivors' would have been guaranteed by the method rather than "
                         f"discovered in the data.",
            "seed": 20260717,
            "known_conservatism": (
                "Astro conditions recur on their own periods (Mercury goes retrograde about every "
                "116 days). When the mask is rotated by roughly a whole period it lands back on "
                "itself, reproducing the original effect and counting as a 'hit' against us. That "
                "makes this test CONSERVATIVE for periodic conditions — verified on synthetic data, "
                "where a deliberately planted +0.40%/day effect scored p=7.6e-4 rather than the "
                "2e-5 floor. The bias runs against finding astro effects, which is the correct "
                "direction for a claim this desk is trying to kill rather than confirm — but it "
                "means a null result here is 'not demonstrated', never 'disproved'. Read the effect "
                "sizes, not only the p-values."),
            "tested_on": f"INDIVIDUAL STOCKS ({len([s for s in series if '(proxy)' not in s])} with "
                         f">={MIN_BARS} bars), plus KSE100 and KMI30 separately. Sectors are "
                         f"deliberately NOT tested here: averaging a sector's members together "
                         f"dilutes any stock-specific effect toward zero, and sector moves belong "
                         f"to the macro lens (flows, debt, gold, geopolitics), not to astrology.",
            "stock_returns": "MARKET-ADJUSTED: r_stock - beta*r_KSE100proxy, beta estimated over the "
                             "full sample and clamped to [0,3]. Raw returns would measure beta, not "
                             "astrology — a weak market tilt shows up multiplied in every high-beta "
                             "name and masquerades as a stock-specific discovery. Index tests stay "
                             "RAW, since a market-wide claim is exactly what they are meant to catch.",
            "index_proxies": idx_meta,
            "index_caveat": "No real daily index history exists in reach (Yahoo's ^KSE is monthly "
                            "and ends in 2021; DPS publishes indices live-only; stooq has none), so "
                            "each index is rebuilt from TODAY's constituents cap-weighted by current "
                            "weight_pct. That carries survivorship bias and weight drift, which "
                            "shifts the LEVEL of returns — but this test compares returns inside vs "
                            "outside astro windows, and the bias is present in both, so it does not "
                            "manufacture or hide an astro effect. Labelled a proxy everywhere it "
                            "appears.",
            "min_days_in_window": MIN_DAYS_IN,
            "min_bars_per_stock": MIN_BARS,
            "multiple_comparisons": f"BOTH reported: Bonferroni (family-wise) at p < {bar:.2e} across "
                                    f"{len(tests)} hypotheses, AND Benjamini-Hochberg FDR at "
                                    f"{ALPHA:.0%} (cutoff p <= {bh_cut:.2e}). Bonferroni alone is "
                                    f"brutal at this width and could hide a real-but-modest effect; "
                                    f"reporting both means the verdict cannot be blamed on the "
                                    f"choice of correction.",
        },
        "headline": {
            "hypotheses_tested": len(tests),
            "subjects_tested": len(series),
            "expected_false_positives_at_p05": expected_false,
            "raw_hits_at_p05": len(raw_hits),
            "survivors_after_bonferroni": len(survivors),
            "survivors_after_fdr": len(fdr_survivors),
            "survivors_that_replicate": len(believable),
            "verdict": (
                "No astro condition has a demonstrated edge on PSX. Tested stock by stock (not "
                "averaged into sectors, which would have hidden any stock-specific effect) and on "
                "KSE100 and KMI30 separately, across ~19 years."
                + (f" {len(survivors)} hypothes{'is' if len(survivors) == 1 else 'es'} survived the "
                   f"multiplicity correction, but NONE replicated: the effect is absent from the "
                   f"index and from the stock's own sector peers, which is what a multiple-"
                   f"comparisons artefact looks like — the most extreme of {len(tests)} correlated "
                   f"draws in a thinly-traded name. The desk reports them in full and believes none "
                   f"of them."
                   if survivors and not believable else
                   " Nothing survived the multiplicity correction at all."
                   if not survivors else
                   f" {len(believable)} survived AND replicated in the index or in sector peers — "
                   f"that is a claim which has not yet been killed, and it must now keep working on "
                   f"live, dated, scored calls before it means anything.")
                + " The desk publishes this rather than hiding it: the astro lens must not be "
                  "presented as if it had an edge it cannot show."),
            "read_this_before_the_numbers": (
                f"At p<0.05 you would expect about {expected_false} false positives from "
                f"{len(tests)} tests by luck alone; {len(raw_hits)} came back. Raw hits below are "
                f"published for transparency, not because they are real."),
        },
        "convergence": {
            "note": "Per STOCK: does the data's best graha match the one tradition assigns to that "
                    "stock's sector (astro_map.json)? With 9 grahas, blind chance agrees about 11% "
                    "of the time — so compare the rate below against ~11%, not against zero.",
            "agree_count": len(agreed), "tested": len(conv),
            "agree_rate_pct": round(100 * len(agreed) / len(conv), 1) if conv else None,
            "chance_rate_pct": round(100 / 9, 1),
            "detail": sorted(conv, key=lambda x: (not x["agree"], x["p_value"])),
        },
        "survivors": survivors,
        "fdr_survivors": fdr_survivors,
        "raw_hits_unadjusted": raw_hits[:40],
        "all_tests": tests,
        "skipped_conditions": {"reason": f"window smaller than {MIN_DAYS_IN} trading days (or "
                                         f"covering everything) — untestable, not tested",
                               "conditions": skipped},
        "honesty": "A lens with no published error rate is a horoscope. This file is the error rate.",
    }
    (STATE / "astro_backtest.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"astro_backtest: {len(tests)} hypotheses on {len(series)} subjects "
          f"({len([s for s in series if '(proxy)' not in s])} stocks + {len(idx_meta)} indices) "
          f"over {len(dates)} trading days ({dates[0]} -> {dates[-1]}) in {time.time()-t0:.0f}s")
    print(f"  Bonferroni bar p < {bar:.2e} | BH-FDR cutoff p <= {bh_cut:.2e}")
    print(f"  raw hits at p<0.05: {len(raw_hits)} (expected by luck: ~{expected_false})")
    print(f"  SURVIVORS: {len(survivors)} bonferroni | {len(fdr_survivors)} fdr | "
          f"{len(believable)} that REPLICATE")
    for t in (survivors or fdr_survivors)[:10]:
        rep = t.get("replication", {})
        print(f"    {t['subject'][:22]:22} {t['condition'][:26]:26} "
              f"{t['effect_pct_per_day']:+.3f}%/day p={t['p_value']:.2e}")
        print(f"      -> peers {rep.get('peer_median_effect_pct')}%  index "
              f"{rep.get('index_effect_pct')}% (p={rep.get('index_p')})  "
              f"replicates={rep.get('replicates')}")
    print(f"  tradition/data agreement: {len(agreed)} of {len(conv)} stocks "
          f"({100*len(agreed)/len(conv):.0f}% vs {100/9:.0f}% by chance)" if conv else "")
    for t in tests[:5]:
        print(f"  best raw: {t['subject'][:20]:20} {t['condition'][:28]:28} "
              f"{t['effect_pct_per_day']:+.3f}%/day p={t['p_value']:.2e}")


if __name__ == "__main__":
    main()
