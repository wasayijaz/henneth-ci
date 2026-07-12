"""Config-driven strategy engine. The desk's 50+ strategies are JSON specs in
strategies/library.json evaluated against a shared indicator library — NOT
hand-coded functions. This is what makes "50 strategies" testable and auditable.

A strategy spec:
{
  "id": "rsi2_meanrev", "name": "...", "category": "mean_reversion",
  "entry": [ {"lhs":"rsi2","op":"lt","rhs":10}, {"lhs":"close","op":"gt","rhs":"sma200"} ],
  "target_pct": 4, "stop_pct": 2.5, "max_hold_sessions": 7,
  "regime_ok": ["risk-on","neutral"]     // optional
}
entry = list of predicates, ALL must hold (logical AND) on the signal bar.

Ops: lt gt lte gte  (rhs = number or series-name)
     cross_above cross_below   (lhs crosses rhs; both series/number)
     between  (rhs = [lo,hi], inclusive)
     rising falling  (lhs vs its own prior value; rhs ignored)

Backtest/live both call `signals(spec, ind)` -> bool array aligned to bars.
Indicators computed from OHLCV (uses deep history's real high/low when present).
No eval(), no code execution — pure data. Safe to run on any spec.
"""
import numpy as np


# ---------- indicator primitives ----------
def _sma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1:] = np.convolve(x, np.ones(n) / n, "valid")
    return out


def _ema(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    k = 2 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(x, n=14):
    d = np.diff(x, prepend=x[0])
    g = np.where(d > 0, d, 0.0)
    l = np.where(d < 0, -d, 0.0)
    out = np.full(len(x), np.nan)
    if len(x) <= n:
        return out
    ag, al = g[1:n + 1].mean(), l[1:n + 1].mean()
    for i in range(n + 1, len(x)):
        ag = (ag * (n - 1) + g[i]) / n
        al = (al * (n - 1) + l[i]) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def _true_range(h, l, c):
    pc = np.concatenate([[c[0]], c[:-1]])
    return np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])


def _atr(h, l, c, n=14):
    tr = _true_range(h, l, c)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    a = tr[1:n + 1].mean()
    for i in range(n + 1, len(c)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def _adx(h, l, c, n=14):
    up = h[1:] - h[:-1]
    dn = l[:-1] - l[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = _true_range(h, l, c)[1:]
    N = len(c)
    plus_di = np.full(N, np.nan)
    minus_di = np.full(N, np.nan)
    adx = np.full(N, np.nan)
    if N <= 2 * n:
        return adx, plus_di, minus_di
    atr = tr[:n].sum()
    pdm = plus_dm[:n].sum()
    mdm = minus_dm[:n].sum()
    dx_hist = []
    for i in range(n, len(tr)):
        atr = atr - atr / n + tr[i]
        pdm = pdm - pdm / n + plus_dm[i]
        mdm = mdm - mdm / n + minus_dm[i]
        pdi = 100 * pdm / atr if atr else 0
        mdi = 100 * mdm / atr if atr else 0
        plus_di[i + 1] = pdi
        minus_di[i + 1] = mdi
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0
        dx_hist.append(dx)
        if len(dx_hist) == n:
            adx[i + 1] = np.mean(dx_hist)
        elif len(dx_hist) > n:
            adx[i + 1] = (adx[i] * (n - 1) + dx) / n
    return adx, plus_di, minus_di


def _stoch(h, l, c, n=14, d=3):
    k = np.full(len(c), np.nan)
    for i in range(n - 1, len(c)):
        ll, hh = l[i - n + 1:i + 1].min(), h[i - n + 1:i + 1].max()
        k[i] = 100 * (c[i] - ll) / (hh - ll) if hh > ll else 50
    return k, _sma(k, d)


def _willr(h, l, c, n=14):
    out = np.full(len(c), np.nan)
    for i in range(n - 1, len(c)):
        hh, ll = h[i - n + 1:i + 1].max(), l[i - n + 1:i + 1].min()
        out[i] = -100 * (hh - c[i]) / (hh - ll) if hh > ll else -50
    return out


def _cci(h, l, c, n=20):
    tp = (h + l + c) / 3
    out = np.full(len(c), np.nan)
    for i in range(n - 1, len(c)):
        w = tp[i - n + 1:i + 1]
        md = np.abs(w - w.mean()).mean()
        out[i] = (tp[i] - w.mean()) / (0.015 * md) if md else 0
    return out


def _roll_max(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        out[i] = x[i - n:i].max()
    return out


def _roll_min(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        out[i] = x[i - n:i].min()
    return out


def _obv(c, v):
    out = np.zeros(len(c))
    for i in range(1, len(c)):
        out[i] = out[i - 1] + (v[i] if c[i] > c[i - 1] else -v[i] if c[i] < c[i - 1] else 0)
    return out


def _pctile_rank(x, n):
    """Rolling percentile rank of the current value within the last n."""
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        w = x[i - n:i + 1]
        out[i] = (w <= x[i]).mean() * 100
    return out


def compute_indicators(hist: list[dict]) -> dict:
    c = np.array([b["close"] for b in hist], float)
    o = np.array([b.get("open", b["close"]) for b in hist], float)
    h = np.array([b.get("high", b["close"]) for b in hist], float)
    l = np.array([b.get("low", b["close"]) for b in hist], float)
    v = np.array([b.get("volume", 0) for b in hist], float)
    n = len(c)
    macd = _ema(c, 12) - _ema(c, 26)
    macd_sig = _ema(np.nan_to_num(macd), 9)
    bb_mid = _sma(c, 20)
    bb_std = np.array([c[i - 19:i + 1].std() if i >= 19 else np.nan for i in range(n)])
    adx, pdi, mdi = _adx(h, l, c)
    stoch_k, stoch_d = _stoch(h, l, c)
    vol20 = _sma(v, 20)
    obv = _obv(c, v)
    safe_std = np.where(bb_std > 0, bb_std, np.nan)
    bb_width = (bb_std * 4) / np.where(bb_mid > 0, bb_mid, np.nan)
    ind = {
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "prev_close": np.concatenate([[c[0]], c[:-1]]),
        "sma10": _sma(c, 10), "sma20": bb_mid, "sma50": _sma(c, 50),
        "sma100": _sma(c, 100), "sma200": _sma(c, 200),
        "ema9": _ema(c, 9), "ema20": _ema(c, 20), "ema50": _ema(c, 50),
        "rsi2": _rsi(c, 2), "rsi7": _rsi(c, 7), "rsi14": _rsi(c, 14),
        "macd": macd, "macd_signal": macd_sig, "macd_hist": macd - macd_sig,
        "bb_upper": bb_mid + 2 * bb_std, "bb_mid": bb_mid, "bb_lower": bb_mid - 2 * bb_std,
        "bb_pctb": (c - (bb_mid - 2 * bb_std)) / (4 * safe_std),
        "bb_width": bb_width, "bb_width_rank": _pctile_rank(bb_width, 120),
        "stoch_k": stoch_k, "stoch_d": stoch_d,
        "atr14": _atr(h, l, c), "adx14": adx, "plus_di": pdi, "minus_di": mdi,
        "willr14": _willr(h, l, c), "cci20": _cci(h, l, c),
        "donch_hi20": _roll_max(h, 20), "donch_lo20": _roll_min(l, 20),
        "donch_hi55": _roll_max(h, 55), "donch_lo55": _roll_min(l, 55),
        "hi252": _roll_max(h, 252), "lo252": _roll_min(l, 252),
        "roc10": np.concatenate([[np.nan] * 10, c[10:] / c[:-10] - 1]) * 100,
        "roc20": np.concatenate([[np.nan] * 20, c[20:] / c[:-20] - 1]) * 100,
        "roc60": np.concatenate([[np.nan] * 60, c[60:] / c[:-60] - 1]) * 100,
        "vol_sma20": vol20, "vol_surge": np.divide(v, vol20, out=np.full(n, np.nan), where=vol20 > 0),
        "vol_rank": _pctile_rank(np.nan_to_num(np.abs(np.diff(c, prepend=c[0]) / c)), 120),
        "obv": obv, "obv_ema20": _ema(obv, 20),
        "atr_pct": np.divide(_atr(h, l, c), c, out=np.full(n, np.nan), where=c > 0) * 100,
    }
    ind["rsi14_prev"] = np.concatenate([[np.nan], ind["rsi14"][:-1]])
    ind["stoch_k_prev"] = np.concatenate([[np.nan], stoch_k[:-1]])
    return ind


# ---------- condition evaluation ----------
def _resolve(ref, ind, n):
    if isinstance(ref, (int, float)):
        return np.full(n, float(ref))
    return ind.get(ref, np.full(n, np.nan))


def _eval_cond(cond, ind, n):
    lhs = _resolve(cond["lhs"], ind, n)
    op = cond["op"]
    with np.errstate(invalid="ignore"):
        if op in ("lt", "gt", "lte", "gte"):
            rhs = _resolve(cond["rhs"], ind, n)
            return {"lt": lhs < rhs, "gt": lhs > rhs,
                    "lte": lhs <= rhs, "gte": lhs >= rhs}[op]
        if op == "between":
            lo, hi = cond["rhs"]
            return (lhs >= lo) & (lhs <= hi)
        if op in ("cross_above", "cross_below"):
            rhs = _resolve(cond["rhs"], ind, n)
            prev_l = np.concatenate([[np.nan], lhs[:-1]])
            prev_r = np.concatenate([[np.nan], rhs[:-1]])
            if op == "cross_above":
                return (prev_l <= prev_r) & (lhs > rhs)
            return (prev_l >= prev_r) & (lhs < rhs)
        if op in ("rising", "falling"):
            prev_l = np.concatenate([[np.nan], lhs[:-1]])
            return lhs > prev_l if op == "rising" else lhs < prev_l
    return np.zeros(n, bool)


def signals(spec: dict, ind: dict) -> np.ndarray:
    n = len(ind["close"])
    out = np.ones(n, bool)
    for cond in spec.get("entry", []):
        c = _eval_cond(cond, ind, n)
        out &= np.where(np.isnan(c.astype(float)) if c.dtype != bool else False, False, c)
    # invalidate warmup bars where key indicators are NaN
    warm = np.zeros(n, bool)
    for cond in spec.get("entry", []):
        for ref in (cond["lhs"], cond.get("rhs")):
            if isinstance(ref, str) and ref in ind:
                warm |= np.isnan(ind[ref])
    out &= ~warm
    return out
