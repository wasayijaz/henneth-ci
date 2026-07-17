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
N_PERM = 2000          # stage 1: screen every hypothesis
N_PERM_FINE = 50000    # stage 2: only for candidates that could plausibly survive
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
    amap = load(STATE / "astro_map.json", {}) or {}
    sig = amap.get("sector_significators", {})
    if not sectors:
        print("astro_backtest: no sectors.json — cannot test sectors")
        sys.exit(0)

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

    # ---- per-sector equal-weight daily return series (and the market as all names)
    members = {}
    for symb, rec in sectors.items():
        members.setdefault(rec.get("sector"), []).append(symb)
    series = {}
    for sec, syms in members.items():
        if not sec or len(syms) < MIN_TICKERS:
            continue
        v = []
        for d in dates:
            day = rets[d]
            vals = [day[s] for s in syms if s in day]
            v.append(float(np.mean(vals)) if len(vals) >= max(2, MIN_TICKERS - 1) else np.nan)
        arr = np.array(v)
        if np.isfinite(arr).sum() >= 500:
            series[sec] = arr
    series["THE MARKET"] = np.array([float(np.mean(list(rets[d].values()))) if rets[d] else np.nan
                                     for d in dates])

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
                "sector": sec, "condition": cond,
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

    # ---- convergence: where the data's favourite graha for a sector matches tradition's
    conv = []
    for sec in series:
        trad = (sig.get(sec) or {}).get("primary")
        if not trad:
            continue
        # only graha-specific conditions can express a preference for a significator; the
        # market-wide ones (moon phase, eclipse windows) name no body and must not be counted
        cand = [t for t in tests if t["sector"] == sec and t["condition"].split(" ")[0] in BODIES]
        if not cand:
            continue
        best = min(cand, key=lambda x: x["p_value"])
        body = best["condition"].split(" ")[0]
        conv.append({
            "sector": sec, "tradition_says": trad, "data_prefers": body,
            "agree": bool(body == trad),
            "best_condition": best["condition"], "p_value": best["p_value"],
            "survives_bonferroni": best["survives_bonferroni"],
        })
    agreed = [c for c in conv if c["agree"]]

    expected_false = round(ALPHA * len(tests), 1)
    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "window": {"from": dates[0], "to": dates[-1], "trading_days": len(dates)},
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
            "sector_returns": f"equal-weight mean of member tickers (min {MIN_TICKERS} names)",
            "market": "equal-weight mean of every universe ticker with history (PSX index history "
                      "is not in the data layer, so this is the proxy and is labelled as one)",
            "min_days_in_window": MIN_DAYS_IN,
            "multiple_comparisons": f"Bonferroni: {len(tests)} hypotheses tested, so the bar is "
                                    f"p < {bar:.2e}, not p < {ALPHA}",
        },
        "headline": {
            "hypotheses_tested": len(tests),
            "expected_false_positives_at_p05": expected_false,
            "raw_hits_at_p05": len(raw_hits),
            "survivors_after_bonferroni": len(survivors),
            "verdict": (
                "Nothing survived. On PSX's own history, no astro condition tested here beats "
                "chance once the number of hypotheses is accounted for. The desk publishes this "
                "rather than hiding it: the astro lens has no demonstrated edge and must not be "
                "presented as if it had one."
                if not survivors else
                f"{len(survivors)} of {len(tests)} hypotheses survived a Bonferroni-corrected bar. "
                f"Survival is not proof — it is a claim that has not yet been killed, and it now "
                f"has to keep working on live, dated, scored calls before it means anything."),
            "read_this_before_the_numbers": (
                f"At p<0.05 you would expect about {expected_false} false positives from "
                f"{len(tests)} tests by luck alone; {len(raw_hits)} came back. Raw hits below are "
                f"published for transparency, not because they are real."),
        },
        "convergence": {
            "note": "Where the data's best graha for a sector matches the one tradition names in "
                    "astro_map.json. Agreement is mildly interesting; disagreement means the "
                    "traditional mapping has no support here.",
            "agree_count": len(agreed), "tested": len(conv), "detail": sorted(
                conv, key=lambda x: (not x["agree"], x["p_value"])),
        },
        "survivors": survivors,
        "raw_hits_unadjusted": raw_hits[:40],
        "all_tests": tests,
        "skipped_conditions": {"reason": f"window smaller than {MIN_DAYS_IN} trading days (or "
                                         f"covering everything) — untestable, not tested",
                               "conditions": skipped},
        "honesty": "A lens with no published error rate is a horoscope. This file is the error rate.",
    }
    (STATE / "astro_backtest.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"astro_backtest: {len(tests)} hypotheses over {len(dates)} trading days "
          f"({dates[0]} -> {dates[-1]}) in {time.time()-t0:.0f}s")
    print(f"  Bonferroni bar p < {bar:.2e}")
    print(f"  raw hits at p<0.05: {len(raw_hits)} (expected by luck: ~{expected_false})")
    print(f"  SURVIVORS: {len(survivors)}")
    for t in survivors[:10]:
        print(f"    {t['sector'][:28]:28} {t['condition'][:30]:30} "
              f"{t['effect_pct_per_day']:+.3f}%/day p={t['p_value']:.5f}")
    print(f"  tradition/data agreement: {len(agreed)} of {len(conv)} sectors")
    for t in tests[:5]:
        print(f"  best raw: {t['sector'][:26]:26} {t['condition'][:28]:28} "
              f"{t['effect_pct_per_day']:+.3f}%/day p={t['p_value']:.5f}")


if __name__ == "__main__":
    main()
