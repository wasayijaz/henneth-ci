"""Which macro drivers actually move each PSX sector? Measured, not assumed.

The desk's own docs say sectors are a macro story — oil, gold, the rupee, global risk, the cost of
money. Until now that was folklore: nothing measured it. This does, with the same discipline as the
astro backtest (which is the point — the desk's honest machinery is reusable on any claim).

METHOD
  * Sector return = equal-weight mean of member tickers' daily returns (sectors.json membership,
    >=3 members). The MARKET row is the cap-weighted KSE100 proxy.
  * Factor return = day-over-day % change of each macro series, LAGGED ONE PSX TRADING DAY.
    Global markets close after Karachi does: today's S&P move cannot reach today's PSX session,
    yesterday's does. One uniform, stated lag — no cherry-picking per factor.
    (us10y uses the CHANGE in yield, in points, not % change — yields are already a rate.)
  * Effect = OLS beta of sector return on the single factor, plus correlation.
  * Significance = circular-shift permutation (rotate the factor series against the sector series),
    which preserves the autocorrelation of BOTH sides — the same test, for the same reason, as the
    astro engine. Bonferroni + Benjamini-Hochberg both reported across every sector x factor pair.
  * Multivariate: one joint OLS per sector on all factors for a combined R^2 — how much of the
    sector's day is global tape at all.

Writes state/sector_macro.json. Free, deterministic. Weekly cadence (see STALE_DAYS).
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
MIN_MEMBERS = 3
MIN_DAYS = 750
N_PERM = 2000
N_PERM_FINE = 50000
FINE_TRIGGER = 0.01
ALPHA = 0.05
STALE_DAYS = 7


def load(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def circular_p(y, x, rng, n_perm=N_PERM):
    """beta, corr, p — rotating x against y."""
    n = len(y)
    vx = x.var()
    if vx <= 0:
        return 0.0, 0.0, 1.0
    obs_b = float(np.cov(y, x)[0, 1] / vx)
    obs_c = float(np.corrcoef(y, x)[0, 1])
    shifts = rng.integers(1, n, size=n_perm)
    hits = 0
    for i in range(0, n_perm, 2000):
        s = shifts[i:i + 2000]
        idx = (np.arange(n)[None, :] + s[:, None]) % n
        xs = x[idx]
        cs = ((xs - xs.mean(axis=1, keepdims=True)) * (y - y.mean())[None, :]).mean(axis=1) / (xs.std(axis=1) * y.std() + 1e-12)
        hits += int((np.abs(cs) >= abs(obs_c)).sum())
    return obs_b, obs_c, (hits + 1) / (n_perm + 1)


def main():
    if "--force" not in sys.argv:
        prev = load(STATE / "sector_macro.json")
        if prev and prev.get("updated"):
            try:
                age = (dt.datetime.now() - dt.datetime.strptime(prev["updated"], "%Y-%m-%d %H:%M")).days
                if age < STALE_DAYS:
                    print(f"sector_macro: last run {age}d ago — weekly cadence, skipping (--force to override)")
                    sys.exit(0)
            except Exception:
                pass

    t0 = time.time()
    mh = load(STATE / "macro_history.json")
    sectors = (load(STATE / "sectors.json", {}) or {}).get("tickers", {})
    universe = (load(STATE / "universe.json", {}) or {}).get("symbols", {})
    if not mh or not sectors:
        print("sector_macro: need macro_history.json + sectors.json first")
        sys.exit(0)

    # ---- per-ticker daily returns
    rets = {}
    for f in sorted(HIST.glob("*.json")):
        bars = load(f, [])
        prev_c = None
        for b in bars:
            c = b.get("close")
            if prev_c and c and prev_c > 0:
                r = c / prev_c - 1
                if abs(r) < 0.25:
                    rets.setdefault(b["date"], {})[f.stem] = r
            prev_c = c or prev_c
    psx_days = sorted(rets)

    # ---- factor daily returns on the factor's own calendar, then aligned to the PREVIOUS
    #      available factor day for each PSX day (the stated one-day information lag)
    fr = {}
    for name, rec in mh["factors"].items():
        s = rec["series"]
        ds = sorted(s)
        out = {}
        for a, b in zip(ds, ds[1:]):
            if name == "us10y":
                out[b] = (s[b] - s[a]) / 10.0          # ^TNX is yield*10: store change in points
            elif s[a]:
                out[b] = s[b] / s[a] - 1
        fr[name] = out
    fnames = sorted(fr)

    aligned = {n: [] for n in fnames}
    for d in psx_days:
        for n in fnames:
            # latest factor return strictly BEFORE this PSX day
            prior = None
            for back in range(1, 8):
                q = (dt.date.fromisoformat(d) - dt.timedelta(days=back)).isoformat()
                if q in fr[n]:
                    prior = fr[n][q]
                    break
            aligned[n].append(prior if prior is not None else np.nan)
    F = {n: np.array(v) for n, v in aligned.items()}

    # ---- sector series + market proxy
    members = {}
    for symb, rec in sectors.items():
        members.setdefault(rec.get("sector"), []).append(symb)
    series = {}
    for sec, syms in members.items():
        if not sec or len(syms) < MIN_MEMBERS:
            continue
        v = [float(np.mean([rets[d][s] for s in syms if s in rets[d]]))
             if sum(1 for s in syms if s in rets[d]) >= 2 else np.nan for d in psx_days]
        arr = np.array(v)
        if np.isfinite(arr).sum() >= MIN_DAYS:
            series[sec] = arr
    w = {s: (v.get("weight_pct") or 0) for s, v in universe.items()}
    mkt = []
    for d in psx_days:
        day = rets[d]
        num = sum(w.get(s, 0) * r for s, r in day.items())
        den = sum(w.get(s, 0) for s in day)
        mkt.append(num / den if den > 20 else np.nan)
    series["THE MARKET (KSE100 proxy)"] = np.array(mkt)

    rng = np.random.default_rng(20260718)
    tests = []
    joint = {}
    for sec, y0 in sorted(series.items()):
        for fn in fnames:
            x0 = F[fn]
            ok = np.isfinite(y0) & np.isfinite(x0)
            if ok.sum() < MIN_DAYS:
                continue
            y, x = y0[ok], x0[ok]
            b, c, p = circular_p(y, x, rng)
            if p <= FINE_TRIGGER:
                b, c, p = circular_p(y, x, rng, N_PERM_FINE)
            tests.append({"sector": sec, "factor": fn,
                          "beta": round(b, 4), "corr": round(c, 4),
                          "days": int(ok.sum()), "p_value": float(f"{p:.3g}")})
        # joint OLS for combined R^2
        X0 = np.column_stack([F[fn] for fn in fnames])
        ok = np.isfinite(y0) & np.isfinite(X0).all(axis=1)
        if ok.sum() >= MIN_DAYS:
            X = np.column_stack([np.ones(ok.sum()), X0[ok]])
            yv = y0[ok]
            try:
                beta, res, *_ = np.linalg.lstsq(X, yv, rcond=None)
                pred = X @ beta
                ss_res = float(((yv - pred) ** 2).sum())
                ss_tot = float(((yv - yv.mean()) ** 2).sum())
                joint[sec] = {"r2_pct": round(100 * (1 - ss_res / ss_tot), 2), "days": int(ok.sum())}
            except Exception:
                pass

    tests.sort(key=lambda t: t["p_value"])
    m = len(tests)
    bonf = ALPHA / max(1, m)
    bh_cut = 0.0
    for i, t in enumerate(tests, 1):
        if t["p_value"] <= i / m * ALPHA:
            bh_cut = t["p_value"]
    for t in tests:
        t["survives_bonferroni"] = bool(t["p_value"] < bonf)
        t["survives_fdr"] = bool(t["p_value"] <= bh_cut)
    surv = [t for t in tests if t["survives_bonferroni"]]
    fdr = [t for t in tests if t["survives_fdr"]]

    # per-sector ranked driver summary (top factors by |corr| among FDR survivors, else the best raw)
    by_sector = {}
    for sec in series:
        mine = [t for t in tests if t["sector"] == sec]
        keep = [t for t in mine if t["survives_fdr"]] or sorted(mine, key=lambda t: t["p_value"])[:1]
        keep.sort(key=lambda t: -abs(t["corr"]))
        by_sector[sec] = {
            "drivers": [{"factor": t["factor"], "corr": t["corr"], "beta": t["beta"],
                         "p_value": t["p_value"], "demonstrated": t["survives_fdr"]} for t in keep[:4]],
            "joint_r2_pct": (joint.get(sec) or {}).get("r2_pct"),
        }

    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "window": {"from": psx_days[0], "to": psx_days[-1], "psx_days": len(psx_days)},
        "method": {
            "lag": "every factor is lagged one PSX day — global sessions close after Karachi, so "
                   "yesterday's tape is the earliest information today's PSX session can price. One "
                   "uniform lag, stated, no per-factor cherry-picking.",
            "test": "circular-shift permutation on the factor series (same machinery, same reason, "
                    "as the astro backtest), Bonferroni + Benjamini-Hochberg both reported",
            "sector_returns": f"equal-weight members (>= {MIN_MEMBERS}); market = cap-weighted proxy",
            "us10y_units": "beta is per PERCENTAGE-POINT change in the US 10y yield",
            "hypotheses": m, "bonferroni_bar": float(f"{bonf:.2e}"), "fdr_cutoff": float(f"{bh_cut:.2e}"),
        },
        "headline": {
            "hypotheses_tested": m,
            "survivors_bonferroni": len(surv),
            "survivors_fdr": len(fdr),
            "read": ("Unlike astrology, the macro factors DO show demonstrated, correction-surviving "
                     "relationships with PSX sectors — which is exactly the contrast the desk's astro "
                     "page claims: the same machinery finds real effects where they exist."
                     if surv else
                     "Even the macro factors do not clear the correction on this lag — global tape "
                     "moves PSX less than assumed, and the desk says so rather than assuming."),
        },
        "by_sector": by_sector,
        "all_tests": tests,
        "note": "Descriptive attribution, not a trading signal and not advice. A demonstrated beta "
                "says what HAS tended to move a sector, not what will.",
    }
    (STATE / "sector_macro.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"sector_macro: {m} sector x factor tests over {len(psx_days)} PSX days in {time.time()-t0:.0f}s")
    print(f"  survivors: {len(surv)} bonferroni | {len(fdr)} fdr (bar {bonf:.1e}, fdr cut {bh_cut:.1e})")
    for t in surv[:14]:
        print(f"    {t['sector'][:30]:30} {t['factor']:10} corr {t['corr']:+.3f} beta {t['beta']:+.4f} p={t['p_value']}")
    print("  joint R^2 (how much of a sector's day is global tape):")
    for sec, j in sorted(joint.items(), key=lambda kv: -kv[1]["r2_pct"])[:8]:
        print(f"    {sec[:34]:34} {j['r2_pct']:5.2f}%")


if __name__ == "__main__":
    main()
