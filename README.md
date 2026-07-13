# PSX Trade Desk

**A multi-agent research terminal for the Pakistan Stock Exchange.**
It researches, values, backtests, debates, and monitors — then puts every call on the record and grades it.
It **never places orders**; execution is manual on your broker. This is educational research, **not advice**.

**Live:** https://wasayijaz.github.io/psx-trade-desk/ · Desk rules: [`CLAUDE.md`](CLAUDE.md) · System map: [`docs/SYSTEM-REGISTRY.md`](docs/SYSTEM-REGISTRY.md)

---

## What it does

A single-page terminal (collapsible sidebar, hard-cornered mono "Bloomberg-lite" design) over the whole PSX universe:

- **Today** — the desk's plain-English daily read: tone, favoured/avoided sectors, a short watchlist.
- **Board** — live universe heatmap, backtest-proven signals, predictability ranks, positions, news + agent wire.
- **Value** — every stock valued four ways (peer P/E, earnings-power vs bond yield, Graham, DDM); the
  median is the model fair value, with the full working expandable per row.
- **Strategies** — 52 transparent, rule-based strategies, each backtested on every stock's ~19-year history
  (win rate, expectancy after costs, out-of-sample) — you see what *actually* worked, not theory.
- **The Desk Room** (on every ticker) — named AI analyst personas research and **debate** the stock:
  a technical desk and a fundamental desk (kept separate), a bull vs a bear, and a Chair who synthesises a
  house view with an explicit dissent and dated, falsifiable calls.
- **Scores** — track records. Every dated call — the desk's own analysts **and** the brokers — is scored
  against what prices actually did. Brokers are ranked overall and per sector.
- **Research** — broker notes and company filings (results / AGM / corporate-briefing), digested and tagged.
- **Macro / Dividends / Earnings / News** — the global tape that moves PSX, a geo-risk radar, dividend
  timing (buy-by / ex-date), the earnings calendar, and a permanent news log.

Each ticker page also carries a **risk profile** (volatility, real max-drawdown with era context, liquidity,
valuation, dividend reliability), a **"questions before buying"** checklist, and **"what the brokers say."**

## Principles (locked — see `CLAUDE.md`)

- **Long-only, daily timeframe.** No shorts, no leverage, no intraday scalping.
- **All numbers come from the data layer.** No agent quotes a price from memory; unknown ≠ guessed.
- **Research, never advice.** No "buy/strong buy/guaranteed" language anywhere. Losses are expected.
- **Brokers are audited, never trusted** — every broker call is scored on the leaderboard.
- **The Auditor keeps veto**; the Room only informs the strategist.

## Architecture — free layer does the heavy lifting; agents only judge

```
DETERMINISTIC PYTHON (free, no tokens)                 AGENTS (tokens, right-sized model)
  data fetch  → quant/predictability/backtest            news · macro · market-analyst (commentary)
  fair value  → signals → dossiers → coverage gate        Desk Room: chartist · fundamentalist ·
  scoring     → leaderboards → QA (verify + design lint)   debate(bull+bear) · chair · librarian · verifier
  build_dashboard → preflight gate → deploy               broker-harvester · design-reviewer
```

**The efficiency engine.** A per-ticker *material hash* (valuation verdict, scorecard, new documents,
high-impact news, earnings proximity — **not** price) drives a coverage gate that tiers every ticker each
cycle: **reaffirm** (unchanged → last view stands, 0 tokens) · **delta** (price moved → cheap refresh) ·
**full** (material change or never covered → the ≤3/day debate). So the whole universe stays current at a
small fraction of naive cost, and new AGM/broker/news data *targets* exactly the ticker that changed.

**Three self-checking systems**, each two-layer (free deterministic lint → agent judgment):
1. **Data QA** — flags glitchy/inconsistent numbers (e.g. a bad "-83% drop") → verifier web-checks, can block.
2. **Deploy QA** — `preflight.py` gates the build; a structurally broken cycle can never publish.
3. **Design QA** — flags corner/padding/token/typography drift → design-reviewer fixes surgically.

## Automation (loops)

| Loop | When | Cost | Does |
|---|---|---|---|
| Cloud (GitHub Actions) | every 30 min + on push | free | full deterministic pipeline → deploy |
| Hourly | weekdays, market hours | cheap | data + news sentinel + position monitor |
| Daily | weekdays 17:20 PKT | ~3 agents | macro + analyst read |
| Room-loop | weekdays 17:47 PKT | ≤3 debates | Desk Room debates + QA + scoring |
| Weekly-harvest | Sat 11:00 PKT | 1 haiku agent | broker calls (Profit/Dawn/Mettis) + filings |

## Run it locally

```bash
python scripts/serve.py           # → http://localhost:8877/dashboard/
python scripts/run_cloud.py       # the whole free pipeline (fetch → quant → … → preflight)
python scripts/preflight.py       # deploy gate: exits non-zero if the data would render broken
```

Deployed free via **GitHub Pages + Actions** (no secrets). Every `push` to `main` rebuilds and redeploys.

## Data & stack

- **Prices:** PSX DPS portal (EOD `[ts, close, volume, open]` — no high/low, so ATR is a close-to-close
  proxy); **Yahoo Finance `.KA`** for ~19-year adjusted history (auto de-glitched) used on charts + long-run stats.
- **Fundamentals:** stockanalysis.com (P/E, EPS, margins, dividends, earnings dates).
- **Cross-check:** `tradingview-ta` (screener=pakistan) verifies the quant layer; a mismatch blocks signals.
- **Stack:** Python 3.14 (requests/pandas/numpy) · vanilla JS SPA (hash router, canvas charts, no framework)
  · JetBrains Mono + Pixelify Sans · GitHub Pages.

## Docs
- [`CLAUDE.md`](CLAUDE.md) — the desk rules every agent obeys.
- [`docs/SYSTEM-REGISTRY.md`](docs/SYSTEM-REGISTRY.md) — index of every agent, loop, script, and state file.
- [`docs/DESK-ROOM-PLAN.md`](docs/DESK-ROOM-PLAN.md) — the multi-agent analyst design.
- [`docs/AUTOMATION-PLAN.md`](docs/AUTOMATION-PLAN.md) — the whole-product loop map.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed and why.

---
*Educational and informational research only — not personalized investment advice. Past performance does
not guarantee future results. Investing in PSX carries risk, including the possible loss of capital.*
