"""Shared indicator math. Close/volume/open only — DPS EOD feed has no high/low,
so ATR is a close-to-close true-range proxy. Documented, deliberate."""
import numpy as np


def sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        c = np.convolve(x, np.ones(n) / n, mode="valid")
        out[n - 1:] = c
    return out


def rsi(closes: np.ndarray, n: int = 14) -> np.ndarray:
    delta = np.diff(closes, prepend=closes[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    out = np.full(len(closes), np.nan)
    if len(closes) <= n:
        return out
    avg_g = gain[1:n + 1].mean()
    avg_l = loss[1:n + 1].mean()
    for i in range(n + 1, len(closes)):
        avg_g = (avg_g * (n - 1) + gain[i]) / n
        avg_l = (avg_l * (n - 1) + loss[i]) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def atr_proxy(closes: np.ndarray, n: int = 14) -> np.ndarray:
    """Close-to-close absolute move, Wilder-smoothed. Underestimates true ATR
    (no intraday range) but consistent across the universe."""
    tr = np.abs(np.diff(closes, prepend=closes[0]))
    out = np.full(len(closes), np.nan)
    if len(closes) <= n:
        return out
    a = tr[1:n + 1].mean()
    for i in range(n + 1, len(closes)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def rolling_max(x: np.ndarray, n: int) -> np.ndarray:
    """Max of the PRIOR n values (excludes current bar)."""
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        out[i] = x[i - n:i].max()
    return out


def pct_return(closes: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(closes), np.nan)
    out[n:] = closes[n:] / closes[:-n] - 1
    return out
