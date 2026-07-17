"""The test the first backtest could not run: does the NATAL method hold on PSX?

astro_backtest.py tested transits IN ISOLATION — retrograde, combust, dignity, eclipses — and found
nothing. That was never the whole tradition, and saying "astrology doesn't work on PSX" on that
basis was an overclaim. Vedic prediction is mostly about a chart:
  * SADE SATI          — Saturn crossing the 12th/1st/2nd sign from the natal Moon
  * DASHA PERIODS      — Vimshottari maha-dasha, keyed to the natal Moon's nakshatra
  * TRANSITS TO NATAL  — a transiting graha conjunct a natal point (3 degree orb)
  * DHAIYA             — Saturn in the 4th/8th from the natal Moon
Now that 29 subjects have birth dates sourced from the Exchange's own floatation workbooks, those
claims are testable. This tests them, the same way, at the same bar.

HONEST ABOUT POWER, UP FRONT
29 charts, most listed after 2010, is a SMALL sample. Sade Sati runs 7.5 years out of 29.5, so a
stock listed in 2018 may contribute one partial window or none. A null here is much weaker evidence
than the transit null was — it may mean "no effect" or simply "not enough history to see one", and
the output says which by publishing the window counts next to every result. Absence of proof is not
proof of absence, and this file is not allowed to pretend otherwise.

Same machinery as astro_backtest.py, for the same reasons: market-adjusted stock returns (raw returns
measure beta, not astrology), circular-shift permutation (preserves autocorrelation and block shape),
Bonferroni AND Benjamini-Hochberg both reported.

Writes state/astro_natal_test.json.
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
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"]
MIN_DAYS_IN = 60          # lower than the transit test: natal windows are rarer by nature
MIN_BARS = 500
N_PERM = 2000
N_PERM_FINE = 50000
FINE_TRIGGER = 0.01
ALPHA = 0.05
STALE_DAYS = 7


def load(p, d=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def circular_p(returns, mask, rng, n_perm=N_PERM):
    n = len(returns)
    k = int(mask.sum())
    total = returns.sum()
    obs = returns[mask].mean() - returns[~mask].mean()
    idx = np.flatnonzero(mask)
    shifts = rng.integers(1, n, size=n_perm)
    hits = 0
    CH = max(1, 4_000_000 // max(1, k))
    for i in range(0, n_perm, CH):
        s = shifts[i:i + CH]
        sums = returns[(idx[None, :] + s[:, None]) % n].sum(axis=1)
        effs = sums / k - (total - sums) / (n - k)
        hits += int((np.abs(effs) >= abs(obs)).sum())
    return obs, (hits + 1) / (n_perm + 1)


def main():
    if "--force" not in sys.argv:
        prev = load(STATE / "astro_natal_test.json")
        if prev and prev.get("updated"):
            try:
                age = (dt.datetime.now() - dt.datetime.strptime(prev["updated"], "%Y-%m-%d %H:%M")).days
                if age < STALE_DAYS:
                    print(f"astro_natal_test: last run {age}d ago — weekly cadence (--force to override)")
                    sys.exit(0)
            except Exception:
                pass

    t0 = time.time()
    sky = load(STATE / "astro_history.json")
    natal = load(STATE / "astro_natal.json")
    universe = (load(STATE / "universe.json", {}) or {}).get("symbols", {})
    if not sky or not natal:
        print("astro_natal_test: need astro_history.json + astro_natal.json")
        sys.exit(0)
    subjects = {k: v for k, v in (natal.get("subjects") or {}).items() if v.get("kind") == "stock"}

    # ---- price panel
    rets = {}
    for f in sorted(HIST.glob("*.json")):
        prev_c = None
        for b in load(f, []):
            c = b.get("close")
            if prev_c and c and prev_c > 0:
                r = c / prev_c - 1
                if abs(r) < 0.25:
                    rets.setdefault(b["date"], {})[f.stem] = r
            prev_c = c or prev_c
    dates = [d for d in sky["dates"] if d in rets]
    idx = {d: i for i, d in enumerate(sky["dates"])}
    if len(dates) < 500:
        print("astro_natal_test: not enough overlapping days")
        sys.exit(0)

    # market proxy (cap-weighted), for market-adjusting each stock
    w = {s: (v.get("weight_pct") or 0) for s, v in universe.items()}
    mkt = np.array([
        (sum(w.get(s, 0) * r for s, r in rets[d].items()) / max(1e-9, sum(w.get(s, 0) for s in rets[d])))
        if sum(w.get(s, 0) for s in rets[d]) > 20 else np.nan for d in dates])

    lon = {b: np.array([sky["bodies"][b]["lon"][idx[d]] for d in dates]) for b in BODIES}
    sign_i = {b: (lon[b] // 30).astype(int) % 12 for b in BODIES}

    rng = np.random.default_rng(20260719)
    tests, skipped = [], []
    for sym, rec in sorted(subjects.items()):
        arr0 = np.array([rets[d].get(sym, np.nan) for d in dates])
        ok0 = np.isfinite(arr0) & np.isfinite(mkt)
        if ok0.sum() < MIN_BARS:
            skipped.append({"subject": sym, "why": f"only {int(ok0.sum())} bars, need {MIN_BARS}"})
            continue
        # market-adjust: a natal effect must beat how the whole market moved that day
        v = float(np.var(mkt[ok0]))
        beta = float(np.cov(arr0[ok0], mkt[ok0])[0, 1] / v) if v > 0 else 1.0
        beta = max(0.0, min(3.0, beta))
        adj = arr0 - beta * mkt
        adj[~ok0] = np.nan
        ok = np.isfinite(adj)
        r = adj[ok]

        nat = rec.get("natal") or {}
        moon_i = SIGNS.index(nat["Moon"]["sign"]) if nat.get("Moon", {}).get("sign") in SIGNS else None
        if moon_i is None:
            continue
        listed = rec.get("birth", {}).get("date")

        masks = {}
        # Sade Sati: Saturn in the 12th, 1st or 2nd sign from the natal Moon
        rel_sat = (sign_i["Saturn"] - moon_i) % 12
        masks["Sade Sati (Saturn 12th/1st/2nd from natal Moon)"] = np.isin(rel_sat, [11, 0, 1])
        masks["Sade Sati — peak only (Saturn on natal Moon sign)"] = rel_sat == 0
        # Dhaiya: Saturn in the 4th or 8th from the natal Moon
        masks["Dhaiya (Saturn 4th/8th from natal Moon)"] = np.isin(rel_sat, [3, 7])
        # Jupiter's blessing: Jupiter in the 2nd/5th/7th/9th/11th from natal Moon (classical "good" houses)
        rel_jup = (sign_i["Jupiter"] - moon_i) % 12
        masks["Jupiter in a benefic house from natal Moon"] = np.isin(rel_jup, [1, 4, 6, 8, 10])
        # transits conjunct natal points (3 deg orb), per transiting graha over ANY natal point
        for tb in BODIES:
            hit = np.zeros(len(dates), bool)
            for nb in BODIES:
                nl = (nat.get(nb) or {}).get("lon")
                if nl is None:
                    continue
                sep = np.abs((lon[tb] - nl + 180) % 360 - 180)
                hit |= sep <= 3.0
            masks[f"transiting {tb} conjunct a natal point"] = hit
        # the running maha-dasha lord (a period claim, tested as a window)
        cur = rec.get("dasha", {}).get("current") or {}
        for d in (rec.get("dasha", {}).get("sequence") or []):
            m = np.array([(d["from"] <= x < d["to"]) for x in dates])
            if m.sum() >= MIN_DAYS_IN and (~m & ok).sum() >= MIN_DAYS_IN:
                masks[f"{d['lord']} maha-dasha period"] = m

        for cond, m in masks.items():
            mm = m & ok
            if mm.sum() < MIN_DAYS_IN or (~mm & ok).sum() < MIN_DAYS_IN:
                skipped.append({"subject": sym, "condition": cond, "days_in": int(mm.sum()),
                                "why": f"window too small (<{MIN_DAYS_IN} trading days) — untestable, not tested"})
                continue
            eff, p = circular_p(r, mm[ok], rng)
            n_res = N_PERM
            if p <= FINE_TRIGGER:
                eff, p = circular_p(r, mm[ok], rng, N_PERM_FINE)
                n_res = N_PERM_FINE
            tests.append({
                "subject": sym, "listed": listed, "natal_moon": nat["Moon"]["sign"],
                "condition": cond, "days_in": int(mm.sum()), "days_out": int((~mm & ok).sum()),
                "effect_pct_per_day": round(float(eff) * 100, 4),
                "p_value": float(f"{p:.3g}"), "resamples": n_res, "beta_used": round(beta, 3),
            })

    tests.sort(key=lambda t: t["p_value"])
    m_tests = len(tests)
    bar = ALPHA / max(1, m_tests)
    bh_cut = 0.0
    for i, t in enumerate(tests, 1):
        if t["p_value"] <= i / m_tests * ALPHA:
            bh_cut = t["p_value"]
    for t in tests:
        t["survives_bonferroni"] = bool(t["p_value"] < bar)
        t["survives_fdr"] = bool(t["p_value"] <= bh_cut)
    surv = [t for t in tests if t["survives_bonferroni"]]
    fdr = [t for t in tests if t["survives_fdr"]]
    raw = [t for t in tests if t["p_value"] < ALPHA]

    # pooled: the same claim across every chart at once — the fair test of a UNIVERSAL rule,
    # and far better powered than any single 10-year-old company
    pooled = {}
    for cond in {t["condition"] for t in tests if not t["condition"].endswith("maha-dasha period")}:
        rows = [t for t in tests if t["condition"] == cond]
        if len(rows) < 5:
            continue
        effs = np.array([t["effect_pct_per_day"] for t in rows])
        pooled[cond] = {
            "subjects": len(rows), "mean_effect_pct_per_day": round(float(effs.mean()), 4),
            "median_effect_pct_per_day": round(float(np.median(effs)), 4),
            "share_negative_pct": round(100 * float((effs < 0).mean()), 1),
            "reading": ("consistent direction across charts — worth a closer look"
                        if abs((effs < 0).mean() - 0.5) > 0.3 else
                        "no consistent direction across charts — what noise looks like"),
        }

    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "what_this_is": ("The natal test. The earlier backtest tested transits in isolation and found "
                         "nothing — but that was never the whole tradition, and 'astrology doesn't "
                         "work on PSX' was an overclaim on that evidence. This tests what Vedic "
                         "prediction actually rests on: Sade Sati, dashas, and transits to a real "
                         "birth chart, using the 29 charts sourced from PSX's own listing records."),
        "power_warning": (f"{len(subjects)} charts, most listed after 2010. Sade Sati runs 7.5 years "
                          f"in 29.5, so a young company contributes one partial window or none. A "
                          f"null here is WEAK evidence — it may mean 'no effect' or merely 'not "
                          f"enough history to see one'. Window counts are published beside every "
                          f"result so you can judge which. Absence of proof is not proof of absence."),
        "method": {
            "returns": "market-adjusted (r_stock - beta*r_market): raw returns measure beta, not astrology",
            "test": "circular-shift permutation; Bonferroni and Benjamini-Hochberg both reported",
            "orb": "3 degrees for transit-to-natal conjunctions",
            "min_window": f"{MIN_DAYS_IN} trading days — smaller windows are reported as untestable, not tested",
            "hypotheses": m_tests, "bonferroni_bar": float(f"{bar:.2e}"), "fdr_cutoff": float(f"{bh_cut:.2e}"),
            "seed": 20260719,
        },
        "headline": {
            "charts_tested": len({t["subject"] for t in tests}),
            "hypotheses_tested": m_tests,
            "expected_false_positives_at_p05": round(ALPHA * m_tests, 1),
            "raw_hits_at_p05": len(raw),
            "survivors_bonferroni": len(surv),
            "survivors_fdr": len(fdr),
            "verdict": (
                f"No natal claim survives correction either. Sade Sati, dashas and transits-to-natal "
                f"were tested on {len({t['subject'] for t in tests})} real birth charts and none beats "
                f"chance. BUT the honest caveat stands: with charts this young the test is weakly "
                f"powered, so this is 'not demonstrated', NOT 'disproved' — a distinction the desk "
                f"keeps making because it is the difference between honesty and a verdict we haven't "
                f"earned."
                if not surv and not fdr else
                f"{len(surv)} Bonferroni / {len(fdr)} FDR survivors of {m_tests}. The natal methods — "
                f"unlike the transit-only rules — show something that survives correction. It is not "
                f"proof: it now has to keep working on dated, public, scored calls."),
        },
        "pooled_across_charts": pooled,
        "survivors": surv,
        "fdr_survivors": fdr,
        "all_tests": tests,
        "untestable": skipped[:60],
        "untestable_count": len(skipped),
    }
    (STATE / "astro_natal_test.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"astro_natal_test: {m_tests} hypotheses on {len({t['subject'] for t in tests})} charts "
          f"in {time.time()-t0:.0f}s")
    print(f"  bar p<{bar:.2e} | raw hits {len(raw)} (expected ~{ALPHA*m_tests:.1f}) | "
          f"SURVIVORS {len(surv)} bonf / {len(fdr)} fdr")
    print(f"  untestable windows (too few days): {len(skipped)}")
    for t in (surv or fdr or tests)[:8]:
        print(f"    {t['subject']:9} {t['condition'][:44]:44} {t['effect_pct_per_day']:+.3f}%/day "
              f"in={t['days_in']:4} p={t['p_value']}")
    print("  pooled across charts:")
    for c, p in sorted(pooled.items(), key=lambda kv: -abs(kv[1]["share_negative_pct"] - 50))[:6]:
        print(f"    {c[:46]:46} n={p['subjects']:2} med {p['median_effect_pct_per_day']:+.3f}%/day "
              f"{p['share_negative_pct']:.0f}% negative")


if __name__ == "__main__":
    main()
