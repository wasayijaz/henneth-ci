"""Does the sky mark TURBULENCE rather than direction? The test the desk had not run.

WHY THIS EXISTS
astro_backtest.py asked one question — "do returns go up or down?" — and answered it thoroughly:
no. But that was never all the tradition claims. Read what financial astrology actually says and
most of it is about TURMOIL and TURNING POINTS, not direction: eclipses "bring upheaval", Mercury
retrograde "brings confusion and reversals", stations "mark pivots". None of those are claims about
the mean. They are claims about VARIANCE and about where the market changes its mind.

A condition can have exactly zero effect on average return and a real effect on volatility. The
earlier tests were structurally blind to that. This one is not.

AND IT APPLIES TO EVERY STOCK
Natal charts exist for ~30 PSX names and cannot exist for the rest (PSX published no listing dates
before 2000). But these conditions need no birth chart — they are the sky itself. So whatever this
finds is available for all 104 names, which is the only honest route to an astro framework that
covers the whole board.

WHAT IS MEASURED, per condition:
  * VOLATILITY   — mean |daily return| inside the window vs outside
  * DISPERSION   — cross-sectional spread across stocks (does the market pull apart?)
  * TURNING POINTS — do 20-day swing highs/lows cluster in the window beyond its share of days?
Same circular-shift permutation, same Bonferroni + FDR. A finding here would be genuinely useful
(risk sizing, when not to enter) and it is falsifiable. A null here is another honest null.

Writes state/astro_regime.json. Weekly cadence.
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
MIN_DAYS_IN = 120
N_PERM = 2000
N_PERM_FINE = 50000
FINE_TRIGGER = 0.01
ALPHA = 0.05
SWING = 20          # a local extreme = the max/min of its +/-20 day neighbourhood
STALE_DAYS = 7


def load(p, d=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def circ_p(series, mask, rng, n_perm=N_PERM):
    """Same machinery as every other test here: rotate the mask, keep both autocorrelation and the
    block shape of astro windows. Works on any per-day quantity — |return|, dispersion, a 0/1 flag."""
    n = len(series)
    k = int(mask.sum())
    total = series.sum()
    obs = series[mask].mean() - series[~mask].mean()
    idx = np.flatnonzero(mask)
    shifts = rng.integers(1, n, size=n_perm)
    hits = 0
    CH = max(1, 4_000_000 // max(1, k))
    for i in range(0, n_perm, CH):
        s = shifts[i:i + CH]
        sums = series[(idx[None, :] + s[:, None]) % n].sum(axis=1)
        effs = sums / k - (total - sums) / (n - k)
        hits += int((np.abs(effs) >= abs(obs)).sum())
    return obs, (hits + 1) / (n_perm + 1)


def main():
    if "--force" not in sys.argv:
        prev = load(STATE / "astro_regime.json")
        if prev and prev.get("updated"):
            try:
                if (dt.datetime.now() - dt.datetime.strptime(prev["updated"], "%Y-%m-%d %H:%M")).days < STALE_DAYS:
                    print("astro_regime: fresh — weekly cadence (--force to override)")
                    sys.exit(0)
            except Exception:
                pass

    t0 = time.time()
    sky = load(STATE / "astro_history.json")
    universe = (load(STATE / "universe.json", {}) or {}).get("symbols", {})
    if not sky:
        print("astro_regime: need astro_history.json")
        sys.exit(0)

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
    dates = [d for d in sky["dates"] if d in rets and len(rets[d]) >= 20]
    idx = {d: i for i, d in enumerate(sky["dates"])}
    if len(dates) < 800:
        print("astro_regime: not enough overlapping days")
        sys.exit(0)

    w = {s: (v.get("weight_pct") or 0) for s, v in universe.items()}
    mkt = np.array([sum(w.get(s, 0) * r for s, r in rets[d].items())
                    / max(1e-9, sum(w.get(s, 0) for s in rets[d])) for d in dates])
    # the three things being tested, one value per trading day
    volat = np.abs(mkt)                                              # turbulence
    disp = np.array([float(np.std(list(rets[d].values()))) for d in dates])   # do stocks pull apart
    # turning points: is day i the max or min of its +/-SWING neighbourhood (on the index level)
    lvl = np.cumprod(1 + mkt)
    turn = np.zeros(len(dates))
    for i in range(SWING, len(dates) - SWING):
        win = lvl[i - SWING:i + SWING + 1]
        if lvl[i] == win.max() or lvl[i] == win.min():
            turn[i] = 1.0

    lon = {b: np.array([sky["bodies"][b]["lon"][idx[d]] for d in dates]) for b in BODIES}
    retro = {b: np.array([sky["bodies"][b]["retro"][idx[d]] for d in dates], dtype=bool) for b in BODIES}
    sun = lon["Sun"]
    elong = np.abs((lon["Moon"] - sun + 180) % 360 - 180)

    masks = {}
    masks["Mercury retrograde"] = retro["Mercury"]
    for b in ("Venus", "Mars", "Jupiter", "Saturn"):
        masks[f"{b} retrograde"] = retro[b]
    masks["near the new moon (+/-2d)"] = elong < 26
    masks["near the full moon (+/-2d)"] = elong > 154
    # eclipse windows: a lunation while the Sun sits near a node
    node = lon["Rahu"]
    dn = np.minimum(np.abs((sun - node + 180) % 360 - 180), np.abs((sun - (node + 180) + 180) % 360 - 180))
    core = ((elong < 26) & (dn < 15.35)) | ((elong > 154) & (dn < 9.5))
    for wide, label in ((3, "eclipse window (+/-3 sessions)"), (7, "eclipse window (+/-7 sessions)")):
        m = np.zeros(len(dates), bool)
        for i in np.where(core)[0]:
            m[max(0, i - wide):min(len(dates), i + wide + 1)] = True
        masks[label] = m
    # stations: the days around a planet turning — tradition's "pivot" claim, tested as a pivot claim
    stat = np.zeros(len(dates), bool)
    for b in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        flip = np.where(retro[b][1:] != retro[b][:-1])[0]
        for i in flip:
            stat[max(0, i - 3):min(len(dates), i + 4)] = True
    masks["within 3 days of any station"] = stat
    masks["Mercury combust"] = np.abs((lon["Mercury"] - sun + 180) % 360 - 180) < 8

    rng = np.random.default_rng(20260720)
    metrics = {"volatility (mean |daily move| of the market)": volat,
               "dispersion (how far stocks scatter that day)": disp,
               "turning points (swing high/low clustering)": turn}
    tests, skipped = [], {}
    for cond, m in masks.items():
        if not (MIN_DAYS_IN <= m.sum() <= len(dates) - MIN_DAYS_IN):
            skipped[cond] = int(m.sum())
            continue
        for mname, series in metrics.items():
            eff, p = circ_p(series, m, rng)
            if p <= FINE_TRIGGER:
                eff, p = circ_p(series, m, rng, N_PERM_FINE)
            base = float(series[~m].mean())
            tests.append({
                "condition": cond, "metric": mname, "days_in": int(m.sum()),
                "inside": round(float(series[m].mean()) * (100 if mname.startswith(("volatility", "dispersion")) else 1), 4),
                "outside": round(base * (100 if mname.startswith(("volatility", "dispersion")) else 1), 4),
                "relative_change_pct": round(100 * (float(series[m].mean()) / base - 1), 2) if base else None,
                "p_value": float(f"{p:.3g}"),
            })

    tests.sort(key=lambda t: t["p_value"])
    m_t = len(tests)
    bar = ALPHA / max(1, m_t)
    bh = 0.0
    for i, t in enumerate(tests, 1):
        if t["p_value"] <= i / m_t * ALPHA:
            bh = t["p_value"]
    for t in tests:
        t["survives_bonferroni"] = bool(t["p_value"] < bar)
        t["survives_fdr"] = bool(t["p_value"] <= bh)
    surv = [t for t in tests if t["survives_bonferroni"]]
    fdr = [t for t in tests if t["survives_fdr"]]

    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "window": {"from": dates[0], "to": dates[-1], "trading_days": len(dates)},
        "what_this_is": ("The turbulence test. The desk's earlier astro work only ever asked whether "
                         "returns go UP or DOWN, and found nothing. But most of what financial "
                         "astrology actually claims is about upheaval and turning points, not "
                         "direction — and a condition can have zero effect on the mean while moving "
                         "the variance. This measures volatility, cross-sectional dispersion, and "
                         "swing-point clustering instead."),
        "why_it_covers_every_stock": ("These conditions are the sky itself — no birth chart needed. "
                                      "Natal charts exist for ~30 PSX names and cannot exist for the "
                                      "rest, so anything demonstrated here is the only astro "
                                      "framework that can honestly reach all 104."),
        "method": {
            "test": "circular-shift permutation (preserves autocorrelation and window shape)",
            "corrections": f"Bonferroni p<{bar:.2e} across {m_t} hypotheses, plus Benjamini-Hochberg (cut {bh:.2e})",
            "market": "cap-weighted universe proxy",
            "volatility": "mean absolute daily move, in %",
            "dispersion": "standard deviation across stocks that day, in %",
            "turning_points": f"a day is a swing point if it is the high or low of its +/-{SWING}-day neighbourhood; "
                              f"the metric is the share of such days",
            "seed": 20260720,
        },
        "headline": {
            "hypotheses_tested": m_t,
            "expected_false_positives_at_p05": round(ALPHA * m_t, 1),
            "raw_hits_at_p05": len([t for t in tests if t["p_value"] < ALPHA]),
            "survivors_bonferroni": len(surv),
            "survivors_fdr": len(fdr),
            "verdict": ("The sky does not mark turbulence on PSX either. Volatility, dispersion and "
                        "turning points were tested against every major astro condition and none "
                        "survives correction — so the astro lens has no demonstrated edge on "
                        "direction OR on turmoil, and the desk says so."
                        if not surv and not fdr else
                        f"{len(surv)} Bonferroni / {len(fdr)} FDR survivors of {m_t}. The sky shows "
                        f"nothing about DIRECTION on PSX — but it appears to mark TURBULENCE, which "
                        f"is a different and more useful claim: it speaks to risk and position size, "
                        f"never to which way to bet. It now has to keep working on dated public calls."),
        },
        "survivors": surv,
        "fdr_survivors": fdr,
        "all_tests": tests,
        "untestable": skipped,
        "not_advice": "A volatility finding is a risk statement, never a direction call. It says the "
                      "ride may be rougher, not which way it goes.",
    }
    (STATE / "astro_regime.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"astro_regime: {m_t} hypotheses over {len(dates)} days in {time.time()-t0:.0f}s")
    print(f"  bar p<{bar:.2e} | SURVIVORS {len(surv)} bonf / {len(fdr)} fdr")
    for t in (surv or fdr or tests)[:12]:
        print(f"    {t['condition'][:32]:32} {t['metric'][:28]:28} in={t['inside']:.3f} "
              f"out={t['outside']:.3f} ({t['relative_change_pct']:+.1f}%) p={t['p_value']}")


if __name__ == "__main__":
    main()
