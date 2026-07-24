"""Build the PUBLIC slice — the only desk data allowed to leave the account gate.

WHY THIS EXISTS
    `state/` is the product. Publishing it as JSON lets a competitor rebuild the terminal in a
    weekend, which is exactly what middleware.js now prevents on desk.henneth.app. But the growth
    plan needs indexable public pages, and Google cannot read a page it has to log in for.

    The resolution: publish RENDERED PAGES built from a NARROWED EXTRACT, never the data layer.
    This script produces that extract. Astro then reads only files inside `site/`, so the
    marketing build is hermetic and can never reach `state/` at all.

THE ONE RULE — ALLOW-LIST, NEVER DENY-LIST
    Every field copied out is named explicitly below. A new field added to `state/` in future is
    excluded BY DEFAULT and stays excluded until someone deliberately adds it here. A deny-list
    would leak it silently on the next cycle. This is CLAUDE.md Rule 2 applied to publishing: if
    it is not explicitly allowed out, it does not go out.

WHAT IS DELIBERATELY WITHHELD (Layer 3 — the paid product)
    · every fair-value METHOD VALUE, its inputs and its workings
    · `verdict` and `mispricing_pct` — see THE DISAGREEMENT SHAPE below
    · predictability score and rank
    · any backtest result, win rate, expectancy or strategy name
    · Desk Room debate, Chair view, dissent, dated calls
    · claims / scores / broker per-call data
    · every liquidity ESTIMATOR (amihud, corwin-schultz, fht, roll, days-to-liquidate)
    · anything from fundamental_scores.json or correlation.json

THE DISAGREEMENT SHAPE (owner decision, 2026-07-21)
    An earlier draft published the fair-value verdict — one word, "undervalued" / "overvalued".
    That is a valuation CONCLUSION about a named security, published at scale, on a site whose
    legal pages are still `review_status: DRAFT`. It collides with CLAUDE.md Rule 5 (no advice
    language) and, in Pakistan, sits closer to regulated investment advice than a research note
    shown to a logged-in user who accepted terms.

    So the extract publishes the SHAPE of the models' disagreement instead: how many of the four
    sit above today's price, how many below, and whether they cluster or scatter. That is
    descriptive of the MODELS, not a conclusion about the STOCK. It is still unique — nobody else
    publishes it — and it leaves the reader with an open question rather than an answer, which is
    the point of a page whose job is to earn a signup.

    Never add `verdict`, `mispricing_pct`, `composite_fair` or `methods` here without a lawyer
    having looked at it first.

USAGE
    python scripts/build_public_slice.py            # the 20-symbol pilot
    python scripts/build_public_slice.py --all      # every eligible ticker (later phases)

Network-free, idempotent, safe to re-run. Exits non-zero ONLY on a structural problem that would
otherwise publish something wrong.
"""
import json
import re
import statistics
import sys
from datetime import date

from psx_data import STATE, ROOT, load_json

OUT_DIR = ROOT / "site" / "src" / "data" / "public"

# The pilot. Most liquid and most searched — the names a Pakistani retail investor types.
PILOT = ["OGDC", "PPL", "PSO", "HUBC", "FFC", "ENGRO", "ENGROH", "LUCK", "DGKC", "MLCF",
         "HBL", "UBL", "MCB", "MEBL", "BAFL", "SYS", "TRG", "NESTLE", "PAKT", "INDU"]

# Liquidity gate thresholds, mirrored from psx_data.research_symbols(). Only the resulting LABEL
# is published — never the ADTV figure that produced it, which is a tradability signal the paid
# product sells.
SIGNAL_ADTV = 30_000_000
RESEARCH_ADTV = 5_000_000
RESEARCH_BARS = 500


def die(msg):
    """Fail loud. A partial extract that looks complete is worse than no extract, because the
    pages built from it would state figures nobody checked."""
    print("build_public_slice: FATAL — " + msg, file=sys.stderr)
    sys.exit(1)


def liquidity_label(liq_row, bars):
    """research / signal / thin — the label only."""
    if not liq_row:
        return None
    adtv = liq_row.get("adtv_pkr")
    if not isinstance(adtv, (int, float)):
        return None
    if adtv >= SIGNAL_ADTV and bars >= RESEARCH_BARS:
        return "signal"
    if adtv >= RESEARCH_ADTV and bars >= RESEARCH_BARS:
        return "research"
    return "thin"


def disagreement(fv):
    """How the four valuation models sit relative to today's price — SHAPE ONLY.

    Returns counts and a spread bucket. Never the method values, never a direction word, never a
    percentage that could be read as a price target.
    """
    if not fv:
        return None
    methods = fv.get("methods") or {}
    price = fv.get("price")
    vals = [v for v in methods.values() if isinstance(v, (int, float)) and v > 0]
    if not isinstance(price, (int, float)) or price <= 0 or len(vals) < 2:
        return None
    above = sum(1 for v in vals if v > price * 1.02)   # 2% deadband: a model within 2% of the
    below = sum(1 for v in vals if v < price * 0.98)   # price is agreeing, not disagreeing
    agree = len(vals) - above - below
    med = statistics.median(vals)
    # Spread of the models against their own midpoint. A wide spread is the honest signal that
    # the methods do not agree and no single number should be trusted.
    spread_ratio = (max(vals) - min(vals)) / med if med else 0
    band = "wide" if spread_ratio > 1.0 else "moderate" if spread_ratio > 0.4 else "narrow"
    return {"total": len(vals), "above_price": above, "below_price": below,
            "near_price": agree, "spread": band}


def plain_read(sym, name, sector, q, fund, divs, shape, liq_label):
    """The 120–150 word plain-English read, GENERATED PER TICKER from that ticker's own data.

    Deliberately not one skeleton with numbers swapped: the sentences a stock earns depend on what
    is actually true of it. A dividend payer gets an income sentence; a lossmaker gets a different
    opening; an illiquid name gets a tradability caveat. Two stocks with different data produce
    genuinely different prose, which is the line between proprietary programmatic pages and the
    scaled thin content Google's helpful-content system targets.

    Rule 5: describes, never advises. No "buy", no "cheap", no "should".
    """
    bits = []
    bits.append(f"{name} ({sym}) trades on the Pakistan Stock Exchange in the {sector} sector.")

    pe = (fund or {}).get("pe")
    mcap = (fund or {}).get("market_cap")
    if mcap:
        bits.append(f"It carries a market capitalisation of about {mcap}.")
    if pe and pe not in ("-", "n/a"):
        bits.append(f"The shares change hands at roughly {pe} times trailing earnings.")
    else:
        bits.append("The company does not currently show positive trailing earnings, "
                    "so a price-to-earnings multiple is not meaningful for it.")

    # Momentum, described rather than judged.
    r20 = (q or {}).get("ret_20d")
    if isinstance(r20, (int, float)):
        direction = "higher" if r20 > 1 else "lower" if r20 < -1 else "broadly flat"
        if direction == "broadly flat":
            bits.append("Over the last month the price has been broadly flat.")
        else:
            bits.append(f"Over the last month the price has moved {direction} "
                        f"by about {abs(r20):.1f}%.")

    # Income, only if the company actually pays.
    if divs:
        yrs = sorted({d["ex"][:4] for d in divs if d.get("ex")})
        dy = (fund or {}).get("div_yield")
        if len(yrs) >= 2:
            span = f"{yrs[0]} to {yrs[-1]}"
            if dy and dy != "-":
                bits.append(f"It has a dividend record running from {span}, and currently shows "
                            f"a yield of {dy}.")
            else:
                bits.append(f"It has a dividend record running from {span}.")
    else:
        bits.append("The desk holds no dividend record for it.")

    # The disagreement shape — the reason to open the full desk.
    if shape:
        t, a, b = shape["total"], shape["above_price"], shape["below_price"]
        if a and b:
            bits.append(f"The desk values it {t} ways and the methods disagree: {a} sit above "
                        f"today's price and {b} below, a {shape['spread']} spread.")
        elif a:
            bits.append(f"The desk values it {t} ways; {a} of those sit above today's price, "
                        f"with a {shape['spread']} spread between them.")
        elif b:
            bits.append(f"The desk values it {t} ways; {b} of those sit below today's price, "
                        f"with a {shape['spread']} spread between them.")
        else:
            bits.append(f"The desk values it {t} ways and they cluster close to today's price.")

    if liq_label == "thin":
        bits.append("Trading volume is thin, so the spread between buying and selling prices "
                    "matters more here than the headline price does.")

    bits.append("This is research, not advice, and nothing here is a recommendation.")
    return " ".join(bits)


def main():
    want_all = "--all" in sys.argv

    universe = load_json(STATE / "universe.json", {}).get("symbols") or {}
    sectors = load_json(STATE / "sectors.json", {}).get("tickers") or {}
    liq = load_json(STATE / "liquidity.json", {}).get("tickers") or {}
    fvall = load_json(STATE / "fairvalue.json", {}).get("tickers") or {}
    quant = load_json(STATE / "quant.json", {}).get("tickers") or {}
    fund = load_json(STATE / "fundamentals.json", {}).get("tickers") or {}
    divall = load_json(STATE / "dividends_deep.json", {}).get("tickers") or {}
    hmeta = load_json(STATE / "history_meta.json", {})

    if not universe:
        die("universe.json is empty or missing — refusing to publish an empty slice.")
    if not sectors:
        die("sectors.json has no ticker map — every page needs a sector, refusing to guess.")

    wanted = sorted(universe) if want_all else PILOT
    out, skipped = {}, {}

    for sym in wanted:
        u = universe.get(sym)
        if not u:
            skipped[sym] = "not in universe"
            continue
        sec = (sectors.get(sym) or {}).get("sector")
        if not sec:
            skipped[sym] = "no sector"
            continue
        q = quant.get(sym)
        if not q or not isinstance(q.get("close"), (int, float)):
            skipped[sym] = "no quant close"
            continue

        bars = 0
        hm = hmeta.get(sym) if isinstance(hmeta, dict) else None
        if isinstance(hm, dict):
            bars = hm.get("bars") or hm.get("n") or 0
        if not bars:
            bars = (liq.get(sym) or {}).get("bars") or 0

        shape = disagreement(fvall.get(sym))
        label = liquidity_label(liq.get(sym), bars)
        f = fund.get(sym) or {}
        # Dividend history is public record (PSX/CDC announce it) — dates and amounts only.
        divs = [{"ex": d["ex"], "rs": d["rs"]}
                for d in (divall.get(sym) or [])
                if isinstance(d, dict) and d.get("ex") and isinstance(d.get("rs"), (int, float))]
        divs = divs[-24:]        # last ~6 years is plenty for a public page

        out[sym] = {
            "symbol": sym,
            "name": u.get("name") or sym,
            "sector": sec,
            "indices": [i for i in (u.get("in") or []) if isinstance(i, str)],
            "liquidity": label,
            # Public-record figures from the fundamentals scrape. Strings, exactly as reported.
            "market_cap": f.get("market_cap"),
            "pe": f.get("pe"),
            "div_yield": f.get("div_yield"),
            # SHAPE ONLY — see the module docstring. Never the values.
            "model_disagreement": shape,
            "dividends": divs,
            "read": plain_read(sym, u.get("name") or sym, sec, q, f, divs, shape, label),
            "as_of": q.get("date"),
        }

    if not out:
        die("no tickers survived the filters — refusing to write an empty file.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": date.today().isoformat(),
        "note": ("Public slice. Rendered into static pages on henneth.app. Contains no valuation "
                 "workings, no backtests, no Desk Room content and no predictability data — see "
                 "scripts/build_public_slice.py for the allow-list."),
        "count": len(out),
        "tickers": out,
    }
    path = OUT_DIR / "tickers.json"
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- context.json: replaces the two `../state/` reads in the Astro build ----------------
    # site/src/pages/index.astro (hero board) and site/src/lib/anchors.ts (calculator defaults)
    # currently read ../state/ directly, which is why Vercel's "include files outside the root
    # directory" is switched on for the marketing project. Once both read THIS file instead, that
    # setting can be turned off and the marketing build can no longer reach the data layer at all.
    macro = load_json(STATE / "macro.json", {})
    num = lambda x: x if isinstance(x, (int, float)) else None
    board = []
    for sym, u in sorted(universe.items(), key=lambda kv: -(kv[1].get("weight_pct") or 0)):
        q = quant.get(sym)
        if not q or not isinstance(q.get("ret_1d"), (int, float)):
            continue
        if u.get("tier") != "core":
            continue
        board.append({"sym": sym, "pct": q["ret_1d"]})
        if len(board) >= 15:
            break

    with_ret = [s for s, r in quant.items() if isinstance(r.get("ret_1d"), (int, float))]
    breadth = (round(100 * sum(1 for s in with_ret if quant[s]["ret_1d"] > 0) / len(with_ret))
               if with_ret else None)

    """The homepage 'proven-strategy signals' panel.

    ORDERING CHANGED DELIBERATELY (2026-07-21). The hero previously ranked these by
    `net_expectancy_pct` and showed the top four — which publishes the backtest engine's own
    ranking of which setups it rates most highly. The expectancy VALUE was never shown, but the
    ORDER is the conclusion, and this file's allow-list withholds backtest results.

    So the panel now orders by index weight — a public fact — and still reports the true thing:
    these names currently carry a setup that cleared the desk's bar. The generic category
    (breakout / trend / momentum) stays because it is standard market taxonomy, not the desk's
    work; the strategy NAME, its win rate and its expectancy never leave."""
    smap = load_json(STATE / "strategy_map.json", {}).get("tickers") or {}
    sig = []
    for sym, u in sorted(universe.items(), key=lambda kv: -(kv[1].get("weight_pct") or 0)):
        lst = smap.get(sym)
        q = quant.get(sym)
        if not lst or not q or not isinstance(q.get("close"), (int, float)):
            continue
        cat = (lst[0] or {}).get("category")
        sig.append({
            "sym": sym,
            "name": re.sub(r"\s+(Limited|Ltd\.?|Company Limited)$", "", u.get("name") or sym,
                           flags=re.I).upper(),
            "tag": (cat or "").upper() or None,
            "close": q["close"],
            "pct": q.get("ret_1d"),
        })
        if len(sig) >= 4:
            break

    ctx = {
        "generated": date.today().isoformat(),
        "note": "Macro anchors + board snapshot for the marketing site. No per-ticker research.",
        "macro": {
            "sbp_rate": num(macro.get("sbp_rate")),
            "cpi_yoy": num(macro.get("cpi_yoy")),
            "tbill_6m": num((macro.get("domestic") or {}).get("tbill_6m")),
            "regime": macro.get("regime"),
            "updated": (macro.get("updated") or "")[:10] or None,
        },
        "board": board,
        "signals": sig,
        "breadth_pct": breadth,
        "as_of": (board and quant[board[0]["sym"]].get("date")) or None,
    }
    (OUT_DIR / "context.json").write_text(
        json.dumps(ctx, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- changelog.json: the marketing site's "Latest updates" section ---------------------
    # state/changelog.json is ALREADY the public-safe output of scripts/build_changelog.py — it
    # fails closed on any release with no `<!--public ... -->` block and tripwires on internal
    # terms before it is ever written. So this is a straight copy, not a second filter pass. It
    # still goes through this allow-list, explicitly, rather than the marketing build reading
    # state/ directly — same hermetic-build rule as everything else in this file.
    log = load_json(STATE / "changelog.json", {})
    releases = [
        {"date": r.get("date"), "version": r.get("version"), "title": r.get("title"),
         "notes": [n for n in (r.get("notes") or []) if isinstance(n, str)]}
        for r in (log.get("releases") or [])
        if isinstance(r, dict) and r.get("date") and r.get("version") and r.get("notes")
    ][:6]
    changelog = {
        "generated": date.today().isoformat(),
        "note": "Public release notes only. Mirrors state/changelog.json — see CLAUDE.md Rule 2.",
        "current": log.get("current"),
        "releases": releases,
    }
    (OUT_DIR / "changelog.json").write_text(
        json.dumps(changelog, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- strategy_levels.json: replaces the strategies/library.json readFileSync in the Astro
    # build (site/src/pages/tools/strategy-level-calculator.astro). Only the non-directive
    # methodology fields — id/name/category/stop_pct/target_pct. Never win rate, expectancy or
    # backtest results (CLAUDE.md Rule 2 allow-list). strategies/library.json also carries a
    # cp1252 byte in some `description` fields; since description is never copied out, that byte
    # never reaches this file or the Astro build.
    lib = load_json(ROOT / "strategies" / "library.json", [])
    levels = [
        {"id": s["id"], "name": s["name"], "category": s.get("category"),
         "stop_pct": s["stop_pct"], "target_pct": s["target_pct"]}
        for s in (lib if isinstance(lib, list) else [])
        if isinstance(s, dict) and isinstance(s.get("stop_pct"), (int, float))
        and isinstance(s.get("target_pct"), (int, float))
        and s["stop_pct"] > 0 and s["target_pct"] > 0
    ]
    strategy_levels = {
        "generated": date.today().isoformat(),
        "note": "Strategy id/name/stop_pct/target_pct only — methodology, never a call on a "
                "named security. See scripts/build_public_slice.py allow-list.",
        "strategies": levels,
    }
    (OUT_DIR / "strategy_levels.json").write_text(
        json.dumps(strategy_levels, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"build_public_slice: wrote {len(out)} tickers -> {path.relative_to(ROOT)}")
    print(f"build_public_slice: wrote strategy_levels -> "
          f"{(OUT_DIR / 'strategy_levels.json').relative_to(ROOT)} ({len(levels)} strategies)")
    print(f"build_public_slice: wrote context   -> {(OUT_DIR / 'context.json').relative_to(ROOT)}")
    print(f"build_public_slice: wrote changelog -> {(OUT_DIR / 'changelog.json').relative_to(ROOT)}"
          f" ({len(releases)} release(s))")
    if skipped:
        print(f"build_public_slice: skipped {len(skipped)} "
              f"(a ticker with incomplete data is skipped, never published with gaps):")
        for s, why in list(skipped.items())[:12]:
            print(f"    {s:10} {why}")


if __name__ == "__main__":
    main()
