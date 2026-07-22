"""PSX DPS portal client. Single source of truth for market data.

Endpoints (unofficial, verified live 2026-07-12):
  /timeseries/eod/{SYM}  -> {"data": [[unix_ts, close, volume, open], ...]} newest first
  /timeseries/int/{SYM}  -> {"data": [[unix_ts, price, volume], ...]} intraday ticks, newest first
  /indices/{INDEX}       -> HTML constituents table (symbol, name, ldcp, current, ..., idx wtg %)
  /market-watch          -> HTML table of all symbols with LDCP/open/high/low/current/volume
"""
import json
import re
import time
from pathlib import Path

import requests

BASE = "https://dps.psx.com.pk"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) psx-trade-desk/1.0"}

_session = requests.Session()
_session.headers.update(HEADERS)


def _get(path: str, retries: int = 3, timeout: int = 20) -> requests.Response:
    last = None
    for i in range(retries):
        try:
            r = _session.get(f"{BASE}{path}", timeout=timeout)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} on {path}")
        except requests.RequestException as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise last


def eod_history(symbol: str) -> list[dict]:
    """Daily history, oldest first: [{date, close, volume, open}]. No high/low in this feed."""
    payload = _get(f"/timeseries/eod/{symbol}").json()
    rows = payload.get("data") or []
    out = []
    for row in reversed(rows):  # API is newest-first
        ts, close, volume, opn = row[0], row[1], row[2], row[3]
        out.append({
            "date": time.strftime("%Y-%m-%d", time.gmtime(ts)),
            "close": float(close),
            "volume": int(volume),
            "open": float(opn),
        })
    return out


def intraday_last(symbol: str) -> dict | None:
    """Most recent tick: {ts, price, volume} or None."""
    payload = _get(f"/timeseries/int/{symbol}").json()
    rows = payload.get("data") or []
    if not rows:
        return None
    ts, price, vol = rows[0][0], rows[0][1], rows[0][2]
    return {"ts": int(ts), "price": float(price), "volume": int(vol)}


_ROW_RE = re.compile(r"<tr.*?</tr>", re.S)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _parse_table_rows(html: str) -> list[list[str]]:
    rows = []
    for tr in _ROW_RE.findall(html):
        cells = [_TAG_RE.sub("", c).replace("&amp;", "&").strip() for c in _CELL_RE.findall(tr)]
        if cells:
            rows.append(cells)
    return rows


def index_constituents(index: str) -> list[dict]:
    """Constituents of KSE100 / KMI30 etc: [{symbol, name, weight_pct}] sorted by weight desc."""
    html = _get(f"/indices/{index}").text
    out = []
    for cells in _parse_table_rows(html):
        # data rows: SYMBOL, NAME, LDCP, CURRENT, CHANGE, CHANGE%, IDX WTG%, ...
        if len(cells) < 7 or cells[0] in ("SYMBOL", ""):
            continue
        try:
            weight = float(cells[6].replace(",", "").replace("%", ""))
        except ValueError:
            weight = 0.0
        out.append({"symbol": cells[0], "name": cells[1], "weight_pct": weight})
    out.sort(key=lambda x: -x["weight_pct"])
    return out


def market_watch() -> dict[str, dict]:
    """Live snapshot of all symbols: {SYM: {ldcp, open, high, low, current, volume}}."""
    html = _get("/market-watch").text
    # header names come from data-name attributes on th
    header = re.findall(r'<th[^>]*data-name="([^"]+)"', html)
    snap = {}
    for cells in _parse_table_rows(html):
        if len(cells) < len(header) or cells[0] == "SYMBOL" or not cells[0]:
            continue
        row = dict(zip(header, cells))
        sym = row.get("symbol", cells[0]).split()[0]

        def num(key):
            v = row.get(key, "").replace(",", "")
            try:
                return float(v)
            except ValueError:
                return None

        snap[sym] = {
            "ldcp": num("ldcp"), "open": num("open"), "high": num("high"),
            "low": num("low"), "current": num("current"),
            "volume": num("volume"), "sector": row.get("sector", ""),
        }
    return snap


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _clean(o):
    """Recursively replace NaN/Infinity with None so output is valid JSON
    (browsers reject the Infinity/NaN literals Python emits by default)."""
    import math
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(_clean(obj), indent=1, ensure_ascii=False, allow_nan=False),
                   encoding="utf-8")
    tmp.replace(path)


def load_config() -> dict:
    return json.loads((ROOT / "config" / "desk.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------
# MARKETS. PSX is the home market and everything here defaults to it, so a universe entry with no
# `market` field behaves exactly as it did before config/markets.json existed. See
# docs/PUBLICATION_RESTRUCTURE.md section 7.

_DEFAULT_MARKET = "PSX"


def load_markets() -> dict:
    """Per-market config. Missing file degrades to a PSX-only desk rather than crashing —
    a US layer that fails to load must never take the home market down with it."""
    try:
        return json.loads((ROOT / "config" / "markets.json").read_text(encoding="utf-8"))["markets"]
    except (OSError, ValueError, KeyError):
        return {}


def market_of(symbol: str, universe: dict | None = None) -> str:
    """Which market a symbol belongs to. Defaults to PSX for every pre-existing entry."""
    if universe is None:
        universe = load_json(STATE / "universe.json", {"symbols": {}})
    return ((universe.get("symbols", {}).get(symbol) or {}).get("market") or _DEFAULT_MARKET)


def yahoo_symbol(symbol: str, universe: dict | None = None) -> str:
    """The ticker as Yahoo spells it.

    This one function is the entire data-layer cost of adding a market. PSX names carry the
    Karachi suffix (`FFC` -> `FFC.KA`); a US ticker is itself.

    An EXPLICIT `yahoo` field on the universe entry wins, and index symbols rely on it. Yahoo
    spells the S&P 500 `^GSPC`, but the desk's own symbol has to survive being a FILENAME
    (state/history/{SYM}.json) and then a URL PATH the browser fetches — and `^` is unsafe in a
    URL, so it would arrive percent-encoded or not at all. So the desk calls it `US500` and maps
    it here. Never let an upstream vendor's punctuation become a filename."""
    if universe is None:
        universe = load_json(STATE / "universe.json", {"symbols": {}})
    meta = universe.get("symbols", {}).get(symbol) or {}
    if meta.get("yahoo"):
        return meta["yahoo"]
    mkt = meta.get("market") or _DEFAULT_MARKET
    suffix = (load_markets().get(mkt) or {}).get("yahoo_suffix", ".KA")
    if symbol.startswith("^") or symbol.endswith(suffix or "\0"):
        return symbol
    return f"{symbol}{suffix}"


def market_symbols(market: str = _DEFAULT_MARKET, symbols: list[str] | None = None) -> list[str]:
    """Filter to one market. Defaults to PSX.

    WHY THIS EXISTS. Adding a second market to universe.json silently widened the input of every
    script that iterates it — including the ones whose SOURCE is PSX-specific. `fetch_intraday.py`
    would ask DPS for XLE, `fetch_dividends_deep.py` would ask Yahoo for `US500.KA`, and
    `fetch_fundamentals.py` would look for a Karachi filing for an American sector ETF. None of
    those crash; they just fail 23 times a cycle and, worse, spend a bounded per-run fetch budget
    on symbols that can never succeed — which STARVES the real PSX names those budgets exist for.

    So: anything whose data SOURCE is PSX wraps its symbol list in this. Anything that is pure
    maths over state/history/{SYM}.json (quant, backtest, predictability, correlation, fair value)
    deliberately does NOT — those are market-agnostic and US coverage is the point."""
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    syms = universe.get("symbols", {})
    pool = symbols if symbols is not None else list(syms)
    return [s for s in pool if ((syms.get(s) or {}).get("market") or _DEFAULT_MARKET) == market]


def research_symbols() -> list[str]:
    """The names the expensive pipeline (backtests, fundamentals, predictability, fair value)
    is allowed to run on: tier=core plus any listed name that cleared the liquidity RESEARCH
    gate in state/liquidity.json.

    One helper, one definition. These scripts previously each carried their own
    `tier == "core"` filter, so a change to the rule meant editing every copy and any missed
    copy would silently analyse a different set than the others.

    Fails CLOSED to core-only: if liquidity.json is missing or unreadable (first run, or a
    failed cycle), we analyse the smaller known-good set rather than fanning out over the
    whole market on a gate we cannot verify."""
    universe = load_json(STATE / "universe.json", {"symbols": {}})
    core = [s for s, m in universe.get("symbols", {}).items()
            if (m or {}).get("tier", "core") == "core"]
    liq = load_json(STATE / "liquidity.json", None)
    if not liq or not liq.get("tickers"):
        return core
    promoted = [s for s, m in liq["tickers"].items()
                if m.get("research_eligible") and s in universe.get("symbols", {})]
    return sorted(set(core) | set(promoted))
